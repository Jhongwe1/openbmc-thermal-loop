"""L2：把同一份 C++ plant 接上私有 D-Bus，讓**未修改的** swampd 與它閉環。

架構（swampd 是上游編出來的二進位，一個 byte 都沒改）：

    swampd ──寫 PWM──▶ /tmp/sys/pwm0 ──▶ 本程式讀（0~255 → %）
       ▲                                        │
       │                              plant_step(pwm%, power(t))
       │                                        │
       ├─◀ PropertiesChanged(Value) ◀── 溫度 ◀──┤
       └─◀ /tmp/sys/fan0_input ◀──── RPM ◀──────┘

為什麼要一個假的 ObjectMapper（計畫沒料到的坑）：
    swampd 讀 D-Bus 感測器前**一定**先問 mapper 這個物件在哪個服務上 ——
    dbushelper.cpp:37 的 getService() 呼叫 xyz.openbmc_project.ObjectMapper
    的 GetObject。私有匯流排上沒有 mapper，照計畫的 bridge 直接起 swampd
    會在建 sensor 時就失敗。上游自己的單元測試也是 mock 掉這一層
    （test/dbushelper_mock.hpp），所以「假 mapper」是有上游背書的測試手法。
    簽名從原始碼抄：GetObject(s path, as interfaces) → a{sas}
    （mapper.append(std::string) 是 's'，不要想當然寫成 'o'）。

還需要提供什麼、不需要提供什麼（全部讀 dbushelper.cpp 得來）：
    · GetAll(Sensor.Value) 一定要有 "Value"；"Unit" 給 DegreesC。
    · MinValue/MaxValue 不用 —— 設定檔 ignoreDbusMinMax: true。
    · Availability / threshold 介面不用 —— 缺席時上游 catch 掉，
      分別視為 available 與「無臨界警報」（UNC_FAILSAFE 預設關）。

為什麼是即時執行：
    swampd 的兩個迴路週期（100 ms / 1000 ms，exp06 實測）掛在牆上時鐘，
    快轉不了。所以 L2 的 1500 秒實驗就是真的 25 分鐘 ——
    這也是它只跑 1 個 seed 的原因：統計（5 seeds）由 L1 提供，
    L2 的任務是「趨勢在上游二進位上重現」。

節拍用絕對期限（deadline），不用 sleep(dt)：
    sleep(dt) 的誤差會**累積**（每步晚一點，一千步後晚幾秒）；
    absolute deadline 的誤差不會 —— 晚了就少睡，節拍追回來。
    W5 學的「量測工具比現象慢」同一家族：節拍器自己不準，量什麼都歪。
"""

import argparse
import asyncio
import ctypes
import json
import pathlib
import sys
import time

from dbus_next import BusType, PropertyAccess
from dbus_next.aio import MessageBus
from dbus_next.errors import DBusError
from dbus_next.service import ServiceInterface, dbus_property, method

SENSOR_PATH = "/xyz/openbmc_project/sensors/temperature/die0"
SENSOR_IFACE = "xyz.openbmc_project.Sensor.Value"
BRIDGE_NAME = "xyz.openbmc_project.ThermalLoopBridge"
MAPPER_NAME = "xyz.openbmc_project.ObjectMapper"
MAPPER_PATH = "/xyz/openbmc_project/object_mapper"


class MockObjectMapper(ServiceInterface):
    """只實作 swampd 用到的那一個方法。其餘一概不假裝有。"""

    def __init__(self, answers: dict):
        super().__init__(MAPPER_NAME)
        self._answers = answers

    @method()
    def GetObject(self, path: "s", interfaces: "as") -> "a{sas}":  # noqa: F821, F722, N802
        if path in self._answers:
            return {self._answers[path]: [SENSOR_IFACE]}
        raise DBusError("xyz.openbmc_project.Common.Error.ResourceNotFound",
                        f"mock mapper: unknown path {path}")


class SensorValue(ServiceInterface):
    """xyz.openbmc_project.Sensor.Value 的最小實作。

    swampd 的 DbusPassive 先 GetAll 拿初值，之後靠 PropertiesChanged 更新
    （push 模型 —— 這也是設定檔 timeout: 0 的理由，見 config/swampd/README.md）。
    """

    def __init__(self, initial: float):
        super().__init__(SENSOR_IFACE)
        self._value = float(initial)

    @dbus_property(access=PropertyAccess.READ)
    def Value(self) -> "d":  # noqa: F821, N802
        return self._value

    @dbus_property(access=PropertyAccess.READ)
    def Unit(self) -> "s":  # noqa: F821, N802
        return "xyz.openbmc_project.Sensor.Value.Unit.DegreesC"

    def push(self, value: float) -> None:
        self._value = float(value)
        self.emit_properties_changed({"Value": self._value})


def load_plant(lib_path: pathlib.Path):
    lib = ctypes.CDLL(str(lib_path))
    lib.plant_create.restype = ctypes.c_void_p
    lib.plant_create.argtypes = [ctypes.c_double, ctypes.c_uint]
    lib.plant_destroy.argtypes = [ctypes.c_void_p]
    for fn in (lib.plant_step,):
        fn.restype = ctypes.c_double
        fn.argtypes = [ctypes.c_void_p, ctypes.c_double, ctypes.c_double]
    for fn in (lib.plant_rpm, lib.plant_die):
        fn.restype = ctypes.c_double
        fn.argtypes = [ctypes.c_void_p]
    return lib


def read_pwm_pct(path: pathlib.Path,
                 fallback_raw: float) -> tuple[float, float]:
    """讀 swampd 寫的 pwm 檔（0~255 raw）→ 百分比。

    swampd 與本程式非同步地讀寫同一個檔，偶爾會讀到寫到一半的空檔 ——
    那不是錯誤，沿用上一個值就好（零階保持，跟真硬體的暫存器一樣）。
    """
    try:
        text = path.read_text().strip()
        raw = float(text) if text else fallback_raw
    except (OSError, ValueError):
        raw = fallback_raw
    return raw / 255.0 * 100.0, raw


async def run(args) -> int:
    lib = load_plant(pathlib.Path(args.lib))
    plant = lib.plant_create(args.dt, args.seed)

    pwm_path = pathlib.Path(args.pwm_path)
    tach_path = pathlib.Path(args.tach_path)
    pwm_path.parent.mkdir(parents=True, exist_ok=True)
    # 初值：swampd 起來之前先給一個「風扇 PID 下限」的世界（30% = raw 76），
    # 與 W2 在 BMC 上實測的初始狀態一致。tach 給 plant 的初始轉速。
    if not pwm_path.exists():
        pwm_path.write_text("76")
    tach_path.write_text("0")

    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    sensor = SensorValue(initial=25.0)
    bus.export(SENSOR_PATH, sensor)
    await bus.request_name(BRIDGE_NAME)
    mapper = MockObjectMapper({SENSOR_PATH: BRIDGE_NAME})
    bus.export(MAPPER_PATH, mapper)
    await bus.request_name(MAPPER_NAME)
    print(f"bridge: sensor at {SENSOR_PATH}, mock mapper up", flush=True)

    csv = pathlib.Path(args.csv)
    csv.parent.mkdir(parents=True, exist_ok=True)

    # ★ 對時錨點：zone_0.log 與 pidcore.* 記的是牆上時鐘 epoch_ms，
    #   bridge 的 CSV 記的是相對秒。沒有這個錨點，L1/L2 疊圖對不上時間軸。
    epoch0_ms = time.time() * 1000.0
    meta = {
        "epoch0_ms": epoch0_ms,
        "args": {k: (str(v) if isinstance(v, pathlib.Path) else v)
                 for k, v in vars(args).items()},
    }
    meta_path = csv.with_name(csv.stem + "_meta.json")
    meta_path.write_text(json.dumps(meta, indent=2) + "\n")

    n = int(args.seconds / args.dt)
    raw = 76.0
    t0 = time.monotonic()
    deadline = t0
    with csv.open("w") as fh:
        fh.write("t_s,pwm,power_w,t_sense_c,t_die_c,rpm\n")
        for i in range(n):
            t = i * args.dt
            power = args.power_base
            if args.power_at >= 0.0 and t >= args.power_at:
                power = args.power_step
            if args.power_down_at >= 0.0 and t >= args.power_down_at:
                power = args.power_base
            pwm_pct, raw = read_pwm_pct(pwm_path, raw)
            sensed = lib.plant_step(plant, pwm_pct, power)
            rpm = lib.plant_rpm(plant)
            tach_path.write_text(f"{rpm:.0f}")
            sensor.push(sensed)
            fh.write(f"{t:.3f},{pwm_pct:.4f},{power:.4f},{sensed:.4f},"
                     f"{lib.plant_die(plant):.4f},{rpm:.2f}\n")

            deadline += args.dt
            delay = deadline - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)

    lag = time.monotonic() - t0 - args.seconds
    print(f"bridge: done, {n} steps in {args.seconds:.0f} s "
          f"(schedule lag at end: {lag * 1000.0:+.0f} ms)", flush=True)
    lib.plant_destroy(plant)
    bus.disconnect()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--lib", default="build/libplant_cabi.so")
    ap.add_argument("--pwm-path", default="/tmp/sys/pwm0")
    ap.add_argument("--tach-path", default="/tmp/sys/fan0_input")
    ap.add_argument("--csv", required=True,
                    help="plant 側軌跡的輸出（欄位對齊 bench/sim 的 CSV）")
    ap.add_argument("--dt", type=float, default=0.1)
    ap.add_argument("--seconds", type=float, default=1500.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--power-base", type=float, default=150.0)
    ap.add_argument("--power-step", type=float, default=400.0)
    ap.add_argument("--power-at", type=float, default=300.0)
    ap.add_argument("--power-down-at", type=float, default=900.0)
    args = ap.parse_args()
    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
