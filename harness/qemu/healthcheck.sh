#!/usr/bin/env bash
# 對一台跑起來的 BMC 做能力盤點，決定它適不適合本專案。
#
#   SSH_PORT=2222 ./harness/qemu/healthcheck.sh > /tmp/health.txt
#
# ⚠️ BMC 上的 coreutils 是 BusyBox，不是 GNU。BusyBox 的 head 不接受
#    `head -5` 這種簡寫，必須寫 `head -n 5`。所有跑在 BMC 端的指令都要注意。
set -uo pipefail
P="${SSH_PORT:-2222}"; R="${REDFISH_PORT:-2443}"
BMC_USER="${BMC_USER:-root}"; BMC_PASS="${BMC_PASS:-0penBmc}"

SSH_OPTS="-p ${P} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=20"
if command -v sshpass >/dev/null 2>&1; then
  S="sshpass -p ${BMC_PASS} ssh ${SSH_OPTS} ${BMC_USER}@127.0.0.1"
else
  S="ssh ${SSH_OPTS} ${BMC_USER}@127.0.0.1"     # 沒有 sshpass 時會互動要密碼
fi
C="curl -sk -u ${BMC_USER}:${BMC_PASS} --max-time 30 https://127.0.0.1:${R}"
# Chassis 的 id 每個平台不同(bletchley 是 Bletchley_Front_Panel_Board)，不可寫死
CHASSIS="$(${C}/redfish/v1/Chassis 2>/dev/null | jq -r '.Members[0]."@odata.id" // empty')"
hdr() { printf '\n=== %s ===\n' "$1"; }

hdr "0. 身分與版本"
$S 'uname -a; echo; cat /etc/os-release'

hdr "1. 熱控 daemon(兩套堆疊都看)"
$S 'ls -l /usr/bin/swampd 2>&1;
    systemctl status phosphor-pid-control --no-pager 2>&1 | head -n 6;
    systemctl status phosphor-fan-control@0 --no-pager 2>&1 | head -n 6'

hdr "2. swampd 設定來源(檔案 or entity-manager D-Bus)"
$S 'ls -l /usr/share/swampd/config.json 2>&1;
    ls /usr/share/entity-manager/configurations/ 2>&1 | head -n 20'

hdr "3. 感測器相關 D-Bus 服務"
$S 'busctl list --no-pager 2>&1 | grep -Ei "sensor|entitymanager|fanctrl|hwmon"'

hdr "4. 現有溫度感測器"
$S 'busctl call xyz.openbmc_project.ObjectMapper /xyz/openbmc_project/object_mapper \
      xyz.openbmc_project.ObjectMapper GetSubTreePaths sias \
      /xyz/openbmc_project/sensors 0 1 xyz.openbmc_project.Sensor.Value 2>&1 | tr " " "\n" | head -n 30'

hdr "5. 風扇控制 zone(Manual / FailSafe)"
$S 'busctl tree xyz.openbmc_project.State.FanCtrl --no-pager 2>&1 | head -n 20'

hdr "6. hwmon 實體(Fig 6 要對照)"
$S 'ls /sys/class/hwmon/ 2>&1;
    for h in /sys/class/hwmon/hwmon*; do echo "$h -> $(cat $h/name 2>/dev/null)"; done 2>&1 | head -n 20'

hdr "7. Redfish:Chassis 清單"
$C/redfish/v1/Chassis | jq -r '.Members[]."@odata.id"' 2>&1

hdr "8. Redfish:Thermal(已棄用,可能不存在)"
$C"${CHASSIS}"/Thermal | jq -r '.["@odata.type"] // .error.code' 2>&1

hdr "9. Redfish:ThermalSubsystem(新)"
$C"${CHASSIS}"/ThermalSubsystem | jq -r '.["@odata.type"] // .error.code' 2>&1

hdr "10. Redfish:Sensors collection"
$C"${CHASSIS}"/Sensors | jq -r '.Members[]."@odata.id"' 2>&1 | head -n 15

hdr "11. 檔案系統可寫性(先看掛載旗標，再實際試寫)"
$S 'grep -E " (/|/etc|/usr/share|/var|/run) " /proc/mounts;
    echo "---";
    touch /etc/.wtest 2>/dev/null && { echo "/etc 可寫"; unlink /etc/.wtest; } || echo "/etc 唯讀";
    touch /usr/share/.wtest 2>/dev/null && { echo "/usr/share 可寫"; unlink /usr/share/.wtest; } \
      || echo "/usr/share 唯讀 ← 設定放 /etc，用 systemd drop-in 指過去"'

hdr "12. 開機耗時"
# 這個映像沒有 systemd-analyze。FinishTimestampMonotonic 的單位是微秒。
$S 'systemctl show -p KernelTimestampMonotonic -p UserspaceTimestampMonotonic -p FinishTimestampMonotonic;
    systemd-analyze blame --no-pager 2>/dev/null | head -n 8 || echo "(systemd-analyze 不在此映像)"'

hdr "13. ★ swampd 目前的實際狀態(本專案的起點)"
$S 'journalctl -u phosphor-pid-control --no-pager -n 15 2>&1'
