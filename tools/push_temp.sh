#!/usr/bin/env bash
# 往 BMC 裡的 external sensor 推一個溫度值（route (a)：swampd 自己 own 的 extsensors）。
#
#   ./tools/push_temp.sh 72.5              推一次
#   ./tools/push_temp.sh 72.5 --read       推完讀回來確認
#   ./tools/push_temp.sh 72.5 --hold 30    每 2 秒重推一次，維持 30 秒
#
# ★ 為什麼要有 --hold：設定檔給 die0 的 timeout 是 5 秒。超過 5 秒沒有新值，
#   swampd 判定該感測器 stale，整個 zone 進 failsafe（風扇拉到 failsafePercent）。
#   所以「推一次就走」只能證明值進得去，不能維持一個穩定的工作點。
#
# ★ 服務名不要照抄任何文件。route (a) 的 extsensors 是 swampd 自己建立的
#   （HostSensor 類別，走 host bus）。2026-08-05 在 bletchley 上實測到的名字是
#     xyz.openbmc_project.Hwmon.external
#   不是 xyz.openbmc_project.ExternalSensor —— 那是 route (b) 的 dbus-sensors。
#   自己查的方法：
#     ssh -p 2222 root@127.0.0.1 'busctl list --no-pager | grep -i external'
set -euo pipefail

T="${1:?usage: push_temp.sh <degC> [--read] [--hold <seconds>]}"
shift
READ_BACK=0
HOLD=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --read) READ_BACK=1; shift ;;
    --hold) HOLD="${2:?--hold needs a number of seconds}"; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

P="${SSH_PORT:-2222}"
BMC_USER="${BMC_USER:-root}"; BMC_PASS="${BMC_PASS:-0penBmc}"
SVC="${EXT_SENSOR_SVC:-xyz.openbmc_project.Hwmon.external}"
OBJ="${EXT_SENSOR_PATH:-/xyz/openbmc_project/extsensors/temperature/die0}"
IFACE=xyz.openbmc_project.Sensor.Value

SSH_OPTS="-n -p ${P} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=20"
# -n 把 ssh 的 stdin 接到 /dev/null。少了它，ssh 會把呼叫端還沒讀完的 stdin
# 吃光 —— 在迴圈或管線裡用時會讓後面的步驟安靜地不執行（見 LOG.md 2026-08-04）。
if command -v sshpass >/dev/null 2>&1; then
  S="sshpass -p ${BMC_PASS} ssh ${SSH_OPTS} ${BMC_USER}@127.0.0.1"
else
  S="ssh ${SSH_OPTS} ${BMC_USER}@127.0.0.1"
fi

push_once() {
  $S "busctl set-property ${SVC} ${OBJ} ${IFACE} Value d ${T}"
}

push_once
echo "pushed ${T} degC to ${OBJ}"

if [[ "${HOLD}" -gt 0 ]]; then
  echo "holding for ${HOLD}s (re-push every 2s, because timeout=5s)"
  end=$(( $(date +%s) + HOLD ))
  while [[ $(date +%s) -lt ${end} ]]; do
    sleep 2
    push_once
  done
  echo "hold finished"
fi

if [[ "${READ_BACK}" -eq 1 ]]; then
  echo -n "read back: "
  $S "busctl get-property ${SVC} ${OBJ} ${IFACE} Value"
fi
