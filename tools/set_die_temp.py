#!/usr/bin/env python3
"""從 QEMU 的模擬硬體層注入溫度（route (b')）。

用法：
    ./tools/set_die_temp.py 40           # 把 die0 那顆 tmp421 設成 40 °C
    ./tools/set_die_temp.py 80 --read    # 設完從 QMP 讀回來確認
    ./tools/set_die_temp.py 80 --verify  # 設完等到 BMC 真的看到，否則失敗
    ./tools/set_die_temp.py --read       # 只讀，不寫
    ./tools/set_die_temp.py --list       # 列出這台機器上所有 tmp421

★ 這支工具在做什麼（也就是：溫度到底是從哪一層進去的）
    tmp421 是一顆真的 i2c 溫度晶片，QEMU 有它的行為模型（hw/sensor/tmp421.c）。
    這個模型把溫度存在一個 QOM property `temperature0`（單位：千分之一度 C），
    而 QOM property 可以從外面經由 QMP（QEMU Machine Protocol）寫入。

    寫進去之後，**下游完全是真的**：

        QEMU tmp421 模型
          -> i2c 匯流排（也是模擬的）
          -> guest 裡的 Linux tmp421 driver（真的 kernel driver）
          -> /sys/class/hwmon/hwmonN/temp1_input（真的 hwmon sysfs）
          -> dbus-sensors 的 hwmontempsensor（真的上游 daemon）
          -> D-Bus 的 xyz.openbmc_project.Sensor.Value
          -> bmcweb（Redfish）與 swampd（PID 控制）

    也就是說，注入點在「晶片」這一層，不是在 BMC 內部。
    這比 route (a) 的 external sensor 多走了 kernel driver 與 hwmon 兩層。

★ `--read` 與 `--verify` 是兩件不同的事，不要互相取代
    `--read`   從 **QMP** 把值讀回來 —— 那是**注入端**，只證明 QEMU 收下了。
    `--verify` 從 **BMC 的 hwmon sysfs** 讀 —— 那是**接收端**，證明整條
               i2c → driver → sysfs 真的把值送到了，而且送到的是預期的那個值。

    兩者會差**整整一個量化階**（設 40.000：`--read` 印 39.9960，
    BMC 看到的是 39.938）。所以拿 `--read` 當 sanity check 的人，
    永遠不會發現 BMC 實際看到的低了一格。**要驗真的進去了，用 `--verify`。**

    ⚠️ `--verify` 需要 `sshpass` 並且會連進 BMC。沒有 `--verify` 時
       這支工具**完全不碰 ssh**（它本來就只是 QMP 客戶端）。

★ 為什麼不用計畫寫的 route (b)（dbus-sensors 的 ExternalSensor）
    這個映像裡沒有那個 daemon。根因在上游 vendor layer：
      meta-facebook/recipes-phosphor/sensors/dbus-sensors_%.bbappend
      FACEBOOK_REMOVED_DBUS_SENSORS = "... external ..."
      PACKAGECONFIG:remove = "${FACEBOOK_REMOVED_DBUS_SENSORS}"
    見 LOG.md 2026-08-05 那則。

★ 誠實標註
    這是**模擬的**晶片，不是真的硬體。它證明的是「從 i2c 晶片到 Redfish 的
    整條軟體路徑是通的、每一層讀到什麼值」，不是「真實硬體上的溫度」。
"""

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time

DEFAULT_SOCK = "/tmp/qmp-bletchley.sock"
# die0：i2c bus 0 上位址 0x4f 的那顆。
# 裝置樹路徑 /ahb/apb/bus@1e78a000/i2c@80/tmp421@4f，在 guest 裡是 hwmon0。
# 這台 bletchley 上共有 10 顆 tmp421，用 --list 可以全部列出來。
DEFAULT_BUS = 0
DEFAULT_ADDR = 0x4F
# tmp421 有 1 個本地通道 + 3 個遠端通道。QEMU 的 temperature0 對應 Linux 的
# temp1_input（本地），temperature1 對應 temp2_input，依此類推。
# hwmontempsensor 的設定裡 "Name" 綁 temp1、"Name1" 綁 temp2 —— 我們只用 temp1。
DEFAULT_CHANNEL = 0
# ★ tmp421 的量程。QEMU 的 setter 會檢查並**回錯誤**（不是安靜截斷）：
#     hw/sensor/tmp421.c
#     static const int32_t mins[2] = { -40000, -55000 };
#     static const int32_t maxs[2] = { 127000, 150000 };
#     if (temp >= maxs[ext_range] || temp < mins[ext_range]) { error_setg(...); }
#   用哪一組看晶片 CONFIG 暫存器的 range 位元 —— 見下面 EXT_RANGE 的推導。
#
#   為什麼需要夾制：W5 之後熱模型會自動餵值進來，而 0 RPM + 400 W 的開環穩態
#   是 165 °C —— **超出這顆感測器的量程**。沒有夾制的話整個實驗會在半路
#   噴例外中斷；夾制之後實驗跑得完，而且 stderr 上留下「感測器飽和了」的紀錄。
#   ⚠️ 夾制發生時 BMC 讀到的值與模型的值**不一致**，那一段數據不能用來擬合。
SENSOR_MIN_C = -40.0
SENSOR_MAX_C = 126.999

# ★ EXT_RANGE：這台機器上的 tmp421 走的是標準量程（−40 ~ 127 °C），不是擴充量程。
#
#   這**不是猜的，是從兩份原始碼推出來的**：
#     1. QEMU `tmp421_reset()`：`s->config[0] = 0;`
#        —— CONFIG_REG_1 的 RANGE 位元（bit 2）開機就是 0。
#     2. Linux `drivers/hwmon/tmp421.c`：driver 只做
#        `config &= ~TMP421_CONFIG_SHUTDOWN;`，而且 `if (config != config_orig)`
#        才寫回。config_orig = 0、清 SHUTDOWN 之後還是 0 → **它根本不寫**。
#        （driver 另外會動 CONFIG_REG_2 的 REN 位元，那是通道致能，不是量程。）
#
#   所以整條路上沒有人設過 RANGE 位元。
#
#   ★ 而且就算設了，下面的預測值也**不會變**：擴充量程的 offset 是 64*256 = 16384，
#     它是 16 的倍數，所以它在 `reg & ~0xf` 這個遮罩下可以進出自如。
#     兩種量程只在「int16_t 溢位」與「負溫度」上才會分家，本專案不在那個區間。
EXT_RANGE = False

# --verify 連 BMC 的方式。全部可以用環境變數覆寫，因為 harness 換 port 時
# 不應該要改程式碼。
BMC_HOST = os.environ.get("BMC_HOST", "127.0.0.1")
BMC_SSH_PORT = os.environ.get("BMC_SSH_PORT", "2222")
BMC_USER = os.environ.get("BMC_USER", "root")
BMC_PASS = os.environ.get("BMC_PASS", "0penBmc")


# ═══════════════════════════════════════════════════════════════════════
#  注入路徑的傳遞特性：把「我以為的」變成「會被執行的預測」
# ═══════════════════════════════════════════════════════════════════════
#
# 這一段是 exp04 的核心。實驗與完整證據見 bench/exp04_injection.py 與
# bench/data/exp04_injection/，推導見 docs/plant-model.md §2.1。
#
# ⚠️ 全部要用 C 的整數語意，不能用 Python 的 //。
#    C 的整數除法**往 0 截**，Python 的 // **往下取整**，負溫度時兩者不同。


def _c_div(numerator: int, denominator: int) -> int:
    """C 的整數除法：商往 0 截斷（Python 的 `//` 是往負無窮取整）。"""
    quotient = abs(numerator) // abs(denominator)
    same_sign = (numerator >= 0) == (denominator > 0)
    return quotient if same_sign else -quotient


def _div_round_closest(x: int, d: int) -> int:
    """Linux 的 `DIV_ROUND_CLOSEST(x, d)`（include/linux/math.h）。

    正負號一致時加半個除數再截，不一致時減半個除數 —— 效果是「四捨五入、
    .5 遠離 0」。直接寫 `(x + d // 2) // d` 在負值時會差一格。
    """
    half = _c_div(d, 2)
    return _c_div(x + half, d) if (x > 0) == (d > 0) else _c_div(x - half, d)


def expected_hwmon_mC(requested_mC: int, ext_range: bool = EXT_RANGE) -> int:
    """預測這個要求值最後會在 BMC 的 `temp1_input` 變成什麼（單位：m°C）。

    三段運算串起來，每一段都指得回一份原始碼：

    ① QEMU 的 setter —— `hw/sensor/tmp421.c`::

           s->temperature[i] = (int16_t)((temp * 256 - 128) / 1000) + offset;

       ★ 那個 `- 128` 是半個 LSB 的預先扣除（8.8 定點數的 1/2 格 = 128/256）。
         配上 C 的往 0 截斷，效果是**把值壓到自己那一格的正下方** ——
         這就是整條路徑上那個 −1 LSB 系統性偏壓的來源，**不是量化**。

    ② 晶片暫存器只保留 4 個小數位元 —— 同一份檔案的 `tmp421_read()`::

           s->buf[len++] = (((uint16_t) s->temperature[i]) >> 8);
           s->buf[len++] = (((uint16_t) s->temperature[i]) >> 0) & 0xf0;

       所以 driver 拼回來的 16 位元暫存器值 = `temperature & 0xfff0`。

    ③ Linux driver 的還原 —— `drivers/hwmon/tmp421.c` 的 `temp_from_raw()`::

           int temp = reg & ~0xf;
           if (extended) temp -= 64 * 256; else temp = (s16)temp;
           return DIV_ROUND_CLOSEST(temp * 1000, 256);

    逐步算 42500 m°C：

        (42500*256 - 128)/1000 = 10879.872  --往 0 截-->  10879
        10879 & ~0xf                                   =  10864
        DIV_ROUND_CLOSEST(10864*1000, 256) = 42437.5   -->  42438

    這個算式命中 bench/data/exp04_injection/ 裡**每一個**實測點，零誤差；
    test/python/test_injection_model.py 拿那些 CSV 當回歸測試守著它。
    """
    offset = 64 * 256 if ext_range else 0

    # ① QEMU setter。int16_t 的截斷要自己做 —— Python 的 int 沒有寬度。
    stored = _to_int16(_c_div(requested_mC * 256 - 128, 1000) + offset)

    # ② 暫存器只吐得出高 12 位元；driver 讀回來是無號 16 位元。
    reg = stored & 0xFFF0

    # ③ driver 還原成 m°C。
    temp = reg & ~0xF
    temp = temp - 64 * 256 if ext_range else _to_int16(temp)
    return _div_round_closest(temp * 1000, 256)


def _to_int16(value: int) -> int:
    """C 的 `(int16_t)` 轉型：取低 16 位元並以二補數解讀。"""
    value &= 0xFFFF
    return value - 0x10000 if value >= 0x8000 else value


# 一個 LSB 是 16/256 °C = 0.0625 °C = **62.5 m°C**。
#
# ⚠️ 它不是整數，所以 hwmon 上相鄰兩階的差會在 **62 與 63 之間交替** ——
#    不要寫成「階距是 63」。exp04 的自我檢查斷言的是 `gap ∈ {62, 63}`，
#    看到單一個數字反而代表掃描範圍太窄、沒跨過足夠多的格點。
LSB_mC = 62.5


# ═══════════════════════════════════════════════════════════════════════
#  QMP
# ═══════════════════════════════════════════════════════════════════════


class Qmp:
    """最小的 QMP client。QMP 是一行一個 JSON 物件的 request/response 協定。"""

    def __init__(self, path):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(10)
        self.sock.connect(path)
        self.stream = self.sock.makefile("rw", encoding="utf-8", newline="\n")
        self._read()                    # QEMU 連上就會先送一則 greeting
        self.cmd("qmp_capabilities")    # 必須先握手，否則其他指令一律被拒

    def _read(self):
        while True:
            line = self.stream.readline()
            if not line:
                raise RuntimeError("QMP 連線被關閉")
            msg = json.loads(line)
            if "event" in msg:          # 非同步事件（例如 RTC_CHANGE），跳過
                continue
            return msg

    def cmd(self, name, **args):
        self.stream.write(json.dumps({"execute": name, "arguments": args}) + "\n")
        self.stream.flush()
        msg = self._read()
        if "error" in msg:
            raise RuntimeError(f"{name} 失敗：{msg['error']}")
        return msg.get("return")


def find_tmp421(qmp):
    """走 QOM 樹找出所有 tmp421，回傳 [(bus, addr, qom_path), ...]。

    ⚠️ 不要把 QOM 路徑寫死。這些裝置掛在 /machine/unattached/device[N]，
    N 是 QEMU 內部的建立順序，換版本或換 machine 就會變。
    穩定的識別方式是 (parent_bus, address) —— 那對應真實的 i2c 拓撲。
    """
    found = []
    seen = set()
    queue = ["/machine"]
    while queue:
        path = queue.pop(0)
        if path in seen:
            continue
        seen.add(path)
        try:
            children = qmp.cmd("qom-list", path=path)
        except RuntimeError:
            continue
        for child in children:
            ctype = child.get("type", "")
            if not ctype.startswith("child<"):
                continue
            cpath = f"{path}/{child['name']}"
            if ctype == "child<tmp421>":
                addr = qmp.cmd("qom-get", path=cpath, property="address")
                bus_link = qmp.cmd("qom-get", path=cpath, property="parent_bus")
                # bus_link 形如 /machine/soc/i2c/bus[0]/aspeed.i2c.bus.0
                bus = int(bus_link.rsplit(".", 1)[-1])
                found.append((bus, addr, cpath))
            queue.append(cpath)
    return sorted(found)


# ═══════════════════════════════════════════════════════════════════════
#  BMC 端（只有 --verify 會走到這裡）
# ═══════════════════════════════════════════════════════════════════════


def hwmon_input_path(bus: int, addr: int, channel: int) -> str:
    """BMC 上那顆晶片的 temp<N>_input 路徑（用 shell glob，hwmonN 的編號會變）。"""
    # QEMU 的 temperature0 = Linux 的 temp1_input，所以要 +1。
    return (f"/sys/bus/i2c/devices/{bus}-{addr:04x}/hwmon/hwmon*/"
            f"temp{channel + 1}_input")


def read_hwmon_mC(bus: int, addr: int, channel: int) -> int:
    """從 BMC 讀一次 hwmon 讀值（m°C）。**每次都是一個新的 ssh 連線。**

    ⚠️ 不要為了快而改成「開一條 ssh 跑迴圈」——那會把「讀取延遲」與
       「快取窗口」混在一起，而 exp04 的 cache.csv 正是要量後者。
    """
    if shutil.which("sshpass") is None:
        raise SystemExit("--verify 需要 sshpass（sudo apt install sshpass）")
    cmd = [
        "sshpass", "-p", BMC_PASS,
        "ssh", "-n",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "LogLevel=ERROR",
        "-o", "ConnectTimeout=10",
        "-p", BMC_SSH_PORT, f"{BMC_USER}@{BMC_HOST}",
        f"cat {hwmon_input_path(bus, addr, channel)}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(
            f"讀不到 BMC 的 hwmon（離開碼 {proc.returncode}）：{proc.stderr.strip()}"
        )
    out = proc.stdout.strip().splitlines()
    if not out:
        raise SystemExit("BMC 回了空的 hwmon 讀值 —— 忘了 sshpass 的話 ssh 會安靜回 0")
    return int(out[0])


def wait_until_expected(bus: int, addr: int, channel: int, expected: int,
                        timeout_s: float = 5.0, interval_s: float = 0.2):
    """輪詢 BMC 的 hwmon，直到讀值等於預測值，或超時。

    回傳 (成功?, 最後讀到的值, 等了幾秒)。

    ★ 為什麼是「等到等於預測值」而不是 `sleep 2`
      `sleep` 只是**希望**它好了；比對預測值是**確認**它好了。
      而且這一步把「我對這條傳遞路徑的理解」變成一個會執行的斷言：
      QEMU 或 kernel 哪天換了行為，注入會**大聲失敗**，
      而不是安靜地給你偏掉的資料。

    ⚠️ 這個「等到等於預測值」的邏輯**不可以拿去產生 exp04 的量測資料**。
       那會讓資料變成同義反覆（我等到它等於我的預測，然後宣稱它等於我的預測）。
       量測要用 bench/exp04_injection.py 裡的**穩定性判定**，那條與預測值無關。
    """
    deadline = time.monotonic() + timeout_s
    started = time.monotonic()
    last = None
    while True:
        last = read_hwmon_mC(bus, addr, channel)
        if last == expected:
            return True, last, time.monotonic() - started
        if time.monotonic() >= deadline:
            return False, last, time.monotonic() - started
        time.sleep(interval_s)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("degc", nargs="?", type=float, help="要設定的溫度（°C）")
    ap.add_argument("--socket", default=DEFAULT_SOCK, help=f"QMP socket（預設 {DEFAULT_SOCK}）")
    ap.add_argument("--bus", type=int, default=DEFAULT_BUS, help="i2c bus 編號")
    ap.add_argument("--addr", type=lambda s: int(s, 0), default=DEFAULT_ADDR,
                    help="i2c 位址（可寫 0x4f）")
    ap.add_argument("--channel", type=int, default=DEFAULT_CHANNEL,
                    help="tmp421 通道 0~3（0 = 本地 = temp1_input）")
    ap.add_argument("--read", action="store_true", help="從 QMP 讀回目前值（注入端）")
    ap.add_argument("--verify", action="store_true",
                    help="等到 BMC 的 hwmon 真的看到預測值，否則以非零離開碼失敗（接收端）")
    ap.add_argument("--verify-timeout", type=float, default=5.0,
                    help="--verify 最多等幾秒（預設 5）")
    ap.add_argument("--list", action="store_true", help="列出所有 tmp421")
    args = ap.parse_args()

    if args.verify and args.degc is None:
        ap.error("--verify 要搭配一個溫度值（沒注入就沒有東西可以驗）")

    try:
        qmp = Qmp(args.socket)
    except (FileNotFoundError, ConnectionRefusedError):
        sys.exit(f"連不上 {args.socket} —— QEMU 沒開，或這台是舊版 run_bmc.sh 起的（沒有 -qmp）")

    devices = find_tmp421(qmp)
    if args.list:
        for bus, addr, path in devices:
            t0 = qmp.cmd("qom-get", path=path, property="temperature0")
            print(f"i2c-{bus:<3} 0x{addr:02x}  {path}  temperature0={t0/1000:.3f} C")
        return 0

    match = [p for bus, addr, p in devices if bus == args.bus and addr == args.addr]
    if not match:
        sys.exit(f"找不到 i2c-{args.bus} 位址 0x{args.addr:02x} 上的 tmp421（用 --list 看有哪些）")
    path = match[0]
    prop = f"temperature{args.channel}"

    requested_mC = None
    if args.degc is not None:
        # QEMU 這個 property 的單位是「千分之一度 C」。
        wrote = args.degc
        requested_mC = int(round(args.degc * 1000))
        try:
            qmp.cmd("qom-set", path=path, property=prop, value=requested_mC)
        except RuntimeError as err:
            if "out of range" not in str(err):
                raise
            wrote = max(SENSOR_MIN_C, min(SENSOR_MAX_C, args.degc))
            requested_mC = int(round(wrote * 1000))
            print(f"⚠️  感測器飽和：{args.degc} °C 超出 tmp421 量程，"
                  f"夾制到 {wrote} °C 後重寫。"
                  f"\n    這一段的模型值與 BMC 讀值不一致，不可用來擬合。",
                  file=sys.stderr)
            qmp.cmd("qom-set", path=path, property=prop, value=requested_mC)
        print(f"set i2c-{args.bus} 0x{args.addr:02x} {prop} = {wrote} C")

    if args.read or (args.degc is None and not args.verify):
        millidegc = qmp.cmd("qom-get", path=path, property=prop)
        print(f"read back (QMP, injection side): {millidegc/1000:.4f} C  ({millidegc} m°C)")

    if args.verify:
        expected = expected_hwmon_mC(requested_mC)
        ok, actual, waited = wait_until_expected(
            args.bus, args.addr, args.channel, expected, args.verify_timeout)
        verdict = "OK" if ok else "FAILED"
        print(f"verify (BMC hwmon, receiving side): {verdict}  "
              f"expected={expected} actual={actual} m°C  waited={waited:.2f}s")
        if not ok:
            print(
                f"注入沒有在 {args.verify_timeout}s 內到達 BMC，或到達的值與預測不符"
                f"（差 {actual - expected} m°C）。\n"
                f"可能的原因：QEMU / kernel 換了轉換行為、i2c 沒通、"
                f"或這顆晶片的 CONFIG range 位元被誰設過了。\n"
                f"預測式的推導與實測點見 bench/exp04_injection.py 與 docs/plant-model.md。",
                file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
