#!/usr/bin/env python3
"""從 QEMU 的模擬硬體層注入溫度（route (b')）。

用法：
    ./tools/set_die_temp.py 40           # 把 die0 那顆 tmp421 設成 40 °C
    ./tools/set_die_temp.py 80 --read    # 設完讀回來確認
    ./tools/set_die_temp.py --read       # 只讀，不寫
    ./tools/set_die_temp.py --list       # 列出這台機器上所有 tmp421

★ 這支工具在做什麼（面試會問「你的溫度是從哪裡進去的」）
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
import socket
import sys

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
#   用哪一組看晶片 CONFIG 暫存器的 range 位元，那個位元從 QOM 讀不到，
#   所以這裡不硬猜：先照使用者給的值寫，被拒絕才夾制到保守的那一組再試一次。
#
#   為什麼需要這個：W5 之後熱模型會自動餵值進來，而 0 RPM + 400 W 的開環穩態
#   是 165 °C —— **超出這顆感測器的量程**。沒有夾制的話整個實驗會在半路
#   噴例外中斷；夾制之後實驗跑得完，而且 stderr 上留下「感測器飽和了」的紀錄。
#   ⚠️ 夾制發生時 BMC 讀到的值與模型的值**不一致**，那一段數據不能用來擬合。
SENSOR_MIN_C = -40.0
SENSOR_MAX_C = 126.999


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
    ap.add_argument("--read", action="store_true", help="讀回目前值")
    ap.add_argument("--list", action="store_true", help="列出所有 tmp421")
    args = ap.parse_args()

    try:
        qmp = Qmp(args.socket)
    except (FileNotFoundError, ConnectionRefusedError):
        sys.exit(f"連不上 {args.socket} —— QEMU 沒開，或這台是舊版 run_bmc.sh 起的（沒有 -qmp）")

    devices = find_tmp421(qmp)
    if args.list:
        for bus, addr, path in devices:
            t0 = qmp.cmd("qom-get", path=path, property="temperature0")
            print(f"i2c-{bus:<3} 0x{addr:02x}  {path}  temperature0={t0/1000:.3f} C")
        return

    match = [p for bus, addr, p in devices if bus == args.bus and addr == args.addr]
    if not match:
        sys.exit(f"找不到 i2c-{args.bus} 位址 0x{args.addr:02x} 上的 tmp421（用 --list 看有哪些）")
    path = match[0]
    prop = f"temperature{args.channel}"

    if args.degc is not None:
        # QEMU 這個 property 的單位是「千分之一度 C」，而且它內部存成
        # 8.8 定點數：value = (temp*256 - 128)/1000 + offset。
        # 所以寫進去再讀回來會有 1/256 ≈ 0.0039 °C 的量化誤差，這是正常的。
        wrote = args.degc
        try:
            qmp.cmd("qom-set", path=path, property=prop,
                    value=int(round(args.degc * 1000)))
        except RuntimeError as err:
            if "out of range" not in str(err):
                raise
            wrote = max(SENSOR_MIN_C, min(SENSOR_MAX_C, args.degc))
            print(f"⚠️  感測器飽和：{args.degc} °C 超出 tmp421 量程，"
                  f"夾制到 {wrote} °C 後重寫。"
                  f"\n    這一段的模型值與 BMC 讀值不一致，不可用來擬合。",
                  file=sys.stderr)
            qmp.cmd("qom-set", path=path, property=prop,
                    value=int(round(wrote * 1000)))
        print(f"set i2c-{args.bus} 0x{args.addr:02x} {prop} = {wrote} C")

    if args.read or args.degc is None:
        millidegc = qmp.cmd("qom-get", path=path, property=prop)
        print(f"read back: {millidegc/1000:.4f} C  ({millidegc} m°C)")


if __name__ == "__main__":
    main()
