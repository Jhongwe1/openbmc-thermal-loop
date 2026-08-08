#!/usr/bin/env bash
#
# 把一顆感測器從 device tree 一路追到 Redfish，並把每一層的**原始輸出**存檔。
#
#   ./tools/trace_sensor.sh            # 用預設的 die0（bus 0, 0x4f）
#   TRACE_TEMP_C=42.5 ./tools/trace_sensor.sh
#
# 產出：
#   bench/data/exp03_trace/raw/*.txt   ← 每一條指令的原始輸出（證據）
#   bench/data/exp03_trace/live.dtb    ← kernel 實際使用的 device tree blob
#   bench/data/exp03_trace/live.dts    ← 上面那份反編譯的結果
#   bench/data/exp03_trace/layers.json ← 抽出來的五層字串，給 plot_fig6.py 吃
#
# ★ 為什麼每一層都要存原始輸出
#   Fig 6 的反造假設計是「每一格都是我機器上的真實字串」。如果圖是手打的，
#   那句話就無從查證。存了原始輸出之後，圖上的任何一格都指得回一個檔案，
#   而那個檔案是某一條指令的 stdout。
#
# ★ 為什麼 device tree 取的是 /sys/firmware/fdt，不是映像裡的 .dtb
#   /sys/firmware/fdt 是 kernel **實際載入**的那一份，包含 bootloader 可能做過的
#   修改（記憶體大小、MAC、chosen/bootargs…）。映像裡的 .dtb 是「應該載入的」。
#   兩者通常一樣，但「通常」不是證據。
#
# ★ 為什麼不在 BMC 上跑 dtc
#   這個映像沒有 dtc。把 blob 抓回開發機再反編譯，順便讓 blob 本身進 repo。
set -euo pipefail

cd "$(dirname "$0")/.."

BUS="${TRACE_BUS:-0}"
ADDR="${TRACE_ADDR:-004f}"
NAME="${TRACE_NAME:-die0}"
BOARD="${TRACE_BOARD:-Thermal_Loop_Demo}"
TEMP_C="${TRACE_TEMP_C:-42.5}"

DEV="${BUS}-${ADDR}"
OUT="bench/data/exp03_trace"
RAW="${OUT}/raw"
mkdir -p "${RAW}"

SSHOPTS=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR)
S=(sshpass -p 0penBmc ssh -n "${SSHOPTS[@]}" -p 2222 root@127.0.0.1)
SCP=(sshpass -p 0penBmc scp -P 2222 "${SSHOPTS[@]}")

# cap <檔名> <遠端指令> —— 跑一條指令，原樣存檔，順便印出來。
#
# ★ 為什麼要 `|| true`
#   這支腳本的工作是「把機器上真正的樣子存下來」，而**失敗也是機器真正的樣子**。
#   44_config_without_hardware.txt 那一條刻意去 ls 一個不存在的路徑，就是要留下
#   `No such file or directory` 當證據。沒有 `|| true` 的話 set -e 會在那裡把整支
#   腳本殺掉，而且殺得很安靜——後面幾段看起來「有檔案」，其實是上一輪的殘留。
cap() {
  local f="${RAW}/$1"; shift
  {
    echo "\$ $*"
    "${S[@]}" "$*" 2>&1 || true
  } > "${f}"
  echo "--- ${f}"
  cat "${f}"
}

echo "############ 0. 注入一個已知溫度（讓五層看到同一個值）############"
./tools/set_die_temp.py "${TEMP_C}" --read | tee "${RAW}/00_inject.txt"
sleep 5

echo
echo "############ 1. device tree ############"
"${SCP[@]}" root@127.0.0.1:/sys/firmware/fdt "${OUT}/live.dtb" >/dev/null
dtc -I dtb -O dts -o "${OUT}/live.dts" "${OUT}/live.dtb" 2>/dev/null
NODE_PATH="$("${S[@]}" "readlink -f /sys/bus/i2c/devices/${DEV}/of_node")"
echo "of_node = ${NODE_PATH}"
cap 10_dts_node.txt "N=/sys/bus/i2c/devices/${DEV}/of_node; echo compatible=\$(tr -d '\\0' < \$N/compatible); echo reg=\$(hexdump -C \$N/reg | head -n 1); echo node=\$(basename \$(readlink -f \$N))"

# 從反編譯的 dts 抓出那個節點的原文（給 Fig 6 用）
python3 - "${OUT}/live.dts" "${NODE_PATH}" > "${RAW}/11_dts_snippet.txt" <<'PY'
import re, sys
dts, ofpath = sys.argv[1], sys.argv[2]
node = ofpath.rstrip("/").split("/")[-1]          # e.g. tmp421@4f
parent = ofpath.rstrip("/").split("/")[-2]        # e.g. i2c@80
text = open(dts).read()
# 找到 parent 區塊，再在裡面找 node 區塊，把兩層都印出來
m = re.search(r"(\t+)" + re.escape(parent) + r" \{", text)
pstart = m.start()
indent = m.group(1)
pend = text.index("\n" + indent + "};", pstart)
block = text[pstart:pend]
n = re.search(r"(\t+)" + re.escape(node) + r" \{", block)
nindent = n.group(1)
nend = block.index("\n" + nindent + "};", n.start()) + len("\n" + nindent + "};")
# parent 的標頭幾行（開頭那行 + compatible / reg / status），然後標明略過了什麼，
# 再接目標節點。★ 不能只挑「看起來相關」的行然後直接接起來 —— 那會產生一段
# 少了 `};` 的、不合法的 dts。圖上放一段編不過的程式碼跟放假資料沒兩樣。
before = block[: n.start()]
siblings = len(re.findall(r"\n\t+[\w-]+@[0-9a-f]+ \{", before))
# 只留 parent 自己的屬性：在第一個子節點出現之前的那一段。
first_child = re.search(r"\n\t+[\w-]+@[0-9a-f]+ \{", before)
own = before[: first_child.start()] if first_child else before
head = [ln for ln in own.splitlines()
        if re.search(re.escape(parent) + r" \{|compatible|status =|reg =|bus-frequency", ln)]
print("\n".join(head))
if siblings:
    # 省略標記用英文：這段字串會原樣進 Fig 6。
    print(nindent + "/* ... %d more device nodes on this bus, elided ... */" % siblings)
print(block[n.start():nend])
print(indent + "};")
PY
cat "${RAW}/11_dts_snippet.txt"

echo
echo "############ 2. kernel 綁定 ############"
cap 20_binding.txt "D=/sys/bus/i2c/devices/${DEV}; echo name=\$(cat \$D/name); echo driver=\$(readlink -f \$D/driver); echo modalias=\$(cat \$D/modalias)"

echo
echo "############ 3. hwmon / sysfs ############"
cap 30_hwmon.txt "H=\$(ls -d /sys/bus/i2c/devices/${DEV}/hwmon/hwmon* | head -n 1); echo path=\$H; echo name=\$(cat \$H/name); echo temp1_input=\$(cat \$H/temp1_input)"

echo
echo "############ 4. entity-manager 的設定物件（dts 與 D-Bus 之間的那一環）############"
cap 40_em.txt "busctl tree xyz.openbmc_project.EntityManager | grep -i ${BOARD}"

# ★ 一顆感測器要出現在 D-Bus 上，需要「硬體在」與「設定在」兩個條件同時成立。
#   這台機器同時給了我兩種失敗模式，值得原樣存下來：
#     · 有硬體沒設定：dts 宣告 10 顆 tmp421，kernel 全綁上了，只有 die0 有 EM 設定
#     · 有設定沒硬體：FRONT_PANEL_TEMP 有 EM 設定（SI7020 @ bus10 0x40），
#                     但 QEMU 沒有模擬那顆晶片，sysfs 裡根本沒有 10-0040
cap 42_counts.txt "echo hwmon_named_tmp421=\$(grep -l tmp421 /sys/class/hwmon/hwmon*/name | wc -l); echo dbus_temperature_sensors=\$(busctl call xyz.openbmc_project.ObjectMapper /xyz/openbmc_project/object_mapper xyz.openbmc_project.ObjectMapper GetSubTreePaths sias /xyz/openbmc_project/sensors/temperature 0 1 xyz.openbmc_project.Sensor.Value | tr ' ' '\\n' | grep -c openbmc)"
cap 43_em_all_configs.txt "busctl tree xyz.openbmc_project.EntityManager"
cap 44_config_without_hardware.txt "busctl introspect xyz.openbmc_project.EntityManager /xyz/openbmc_project/inventory/system/board/Bletchley_Front_Panel_Board/FRONT_PANEL_TEMP | grep -E '\\.(Bus|Address|Name|Type) ' ; echo 'ls /sys/bus/i2c/devices/10-0040:'; ls -d /sys/bus/i2c/devices/10-0040 2>&1"
echo "--- dts 裡宣告了幾顆 tmp421（在開發機上數，不在 BMC 上數）---"
grep -c 'tmp421@' "${OUT}/live.dts" | tee "${RAW}/45_dts_tmp421_count.txt"

echo
echo "############ 5. D-Bus ############"
cap 50_dbus_owner.txt "busctl call xyz.openbmc_project.ObjectMapper /xyz/openbmc_project/object_mapper xyz.openbmc_project.ObjectMapper GetObject sas /xyz/openbmc_project/sensors/temperature/${NAME} 0"
cap 51_dbus_value.txt "busctl get-property xyz.openbmc_project.HwmonTempSensor /xyz/openbmc_project/sensors/temperature/${NAME} xyz.openbmc_project.Sensor.Value Value"
cap 52_dbus_unit.txt "busctl get-property xyz.openbmc_project.HwmonTempSensor /xyz/openbmc_project/sensors/temperature/${NAME} xyz.openbmc_project.Sensor.Value Unit"
cap 53_dbus_assoc.txt "busctl get-property xyz.openbmc_project.HwmonTempSensor /xyz/openbmc_project/sensors/temperature/${NAME} xyz.openbmc_project.Association.Definitions Associations"

echo
echo "############ 6. Redfish ############"
cap 60_redfish_collection.txt "curl -sk -u root:0penBmc https://127.0.0.1:443/redfish/v1/Chassis/${BOARD}/Sensors"
cap 61_redfish_sensor.txt "curl -sk -u root:0penBmc https://127.0.0.1:443/redfish/v1/Chassis/${BOARD}/Sensors/temperature_${NAME}"

echo
echo "############ 7. 組出 layers.json ############"
python3 - "${OUT}" "${DEV}" "${NAME}" "${BOARD}" "${NODE_PATH}" "${TEMP_C}" <<'PY'
import json, pathlib, re, subprocess, sys, datetime

out, dev, name, board, ofpath, temp = sys.argv[1:7]
raw = pathlib.Path(out) / "raw"


def txt(fn: str) -> str:
    """讀回某一條指令的原始輸出（去掉第一行的 `$ 指令`）。"""
    lines = (raw / fn).read_text().splitlines()
    return "\n".join(lines[1:]).strip()


def raw_text(fn: str) -> str:
    """讀回不是由 cap() 產生的檔案（沒有 `$ 指令` 那一行，也不能去頭）。"""
    return (raw / fn).read_text().rstrip("\n")


def field(fn: str, key: str) -> str:
    for ln in txt(fn).splitlines():
        if ln.startswith(key + "="):
            return ln.split("=", 1)[1].strip()
    return ""


redfish = json.loads(txt("61_redfish_sensor.txt"))
hwmon_path = field("30_hwmon.txt", "path")
raw_milli = field("30_hwmon.txt", "temp1_input")
dbus_value = txt("51_dbus_value.txt").split()[-1]
dbus_unit = txt("52_dbus_unit.txt").split()[-1].strip('"')
assoc = txt("53_dbus_assoc.txt")

doc = {
    "captured_at": datetime.date.today().isoformat(),
    "platform": "bletchley  (QEMU machine bletchley-bmc)",
    "sensor": name,
    "i2c_device": dev,
    "injected_temp_c": float(temp),
    "how_dts_obtained": "scp root@bmc:/sys/firmware/fdt  →  dtc -I dtb -O dts",
    "layers": [
        {
            "key": "dts",
            "title": "1. Device Tree",
            "subtitle": ofpath,
            "lines": raw_text("11_dts_snippet.txt").splitlines(),
            "value": None,
            "unit": None,
            "evidence": "raw/11_dts_snippet.txt",
        },
        {
            "key": "driver",
            "title": "2. Kernel driver binding",
            "subtitle": field("20_binding.txt", "driver"),
            "lines": [
                'compatible = "' + field("10_dts_node.txt", "compatible") + '"',
                "modalias   = " + field("20_binding.txt", "modalias"),
                "name       = " + field("20_binding.txt", "name"),
            ],
            "value": None,
            "unit": None,
            "evidence": "raw/20_binding.txt",
        },
        {
            "key": "hwmon",
            "title": "3. hwmon sysfs",
            "subtitle": hwmon_path,
            "lines": [
                "name         = " + field("30_hwmon.txt", "name"),
                "temp1_input  = " + raw_milli,
            ],
            "value": raw_milli,
            "unit": "m°C",
            "evidence": "raw/30_hwmon.txt",
        },
        {
            "key": "dbus",
            "title": "4. D-Bus",
            "subtitle": "/xyz/openbmc_project/sensors/temperature/" + name,
            "lines": [
                "service      = xyz.openbmc_project.HwmonTempSensor",
                "Value        = " + dbus_value,
                "Unit         = " + dbus_unit.split(".")[-1],
                "Associations = " + assoc,
            ],
            "value": dbus_value,
            "unit": "°C",
            "evidence": "raw/51_dbus_value.txt",
        },
        {
            "key": "redfish",
            "title": "5. Redfish",
            "subtitle": redfish["@odata.id"],
            "lines": [
                "Id           = " + redfish["Id"],
                "Reading      = " + str(redfish["Reading"]),
                "ReadingUnits = " + redfish["ReadingUnits"],
                "Status       = " + redfish["Status"]["State"] + " / " + redfish["Status"]["Health"],
            ],
            "value": str(redfish["Reading"]),
            "unit": redfish["ReadingUnits"],
            "evidence": "raw/61_redfish_sensor.txt",
        },
    ],
    # ★ 邊的文字一律英文：圖上不放中文（這台沒有 CJK 字型，而且裝了也不行 ——
    #   那會讓「別人 clone 跑一次得到同一張圖」依賴他們的字型設定）。
    "edges": [
        "kernel matches the compatible string to a driver",
        "driver registers with the hwmon subsystem",
        "entity-manager Configuration lets dbus-sensors claim this chip",
        "bmcweb resolves the association into a Chassis URI",
    ],
}
pathlib.Path(out, "layers.json").write_text(
    json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
)
print(json.dumps(doc, indent=2, ensure_ascii=False))
PY

echo
echo "==> 完成：${OUT}/layers.json"
