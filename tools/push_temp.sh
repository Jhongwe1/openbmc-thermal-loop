#!/usr/bin/env bash
# ⚠️⚠️ 這是 **W2 的舊路線（route (a)）**，對目前的設定**不會動**。
#      要注入溫度請用 `./tools/set_die_temp.py <溫度> --verify`。
#
# ─────────────────────────────────────────────────────────────────────────
#  為什麼不會動（2026-08-09 實測）
#
#    $ ./tools/push_temp.sh 80 --read
#    Failed to set property Value on interface xyz.openbmc_project.Sensor.Value:
#    Unknown object '/xyz/openbmc_project/extsensors/temperature/die0'.
#
#  route (a) 的 external sensor 是 **swampd 依設定檔自己建立**的（HostSensor）。
#  W3 把 `config/swampd/config.baseline.json` 的 die0 換成 route (b′)
#  （讀 dbus-sensors 的 `/xyz/openbmc_project/sensors/temperature/die0`）之後，
#  swampd 就不再建立那個 extsensors 物件了 —— 服務名還在，物件沒了。
#
#  這支腳本的註解裡還寫著「die0 的 timeout 是 5 秒，所以要 --hold」——
#  **那也過期了**：現在的設定是 `timeout: 0`（理由見 config/swampd/README.md）。
#
#  為什麼留著它而不是刪掉：它是 W2 route (a) 那條路真的走過的證據，
#  而且 `--hold` 那段註解記錄了「passive sensor 會 stale」這個踩過的坑。
#  刪掉的話那段推理只剩 git 歷史。**但留著就必須讓它自己說清楚它是舊的** ——
#  一個安靜失敗的工具比沒有工具更浪費時間。
# ─────────────────────────────────────────────────────────────────────────
#
# 往 BMC 裡的 external sensor 推一個溫度值（route (a)：swampd 自己 own 的 extsensors）。
#
#   ./tools/push_temp.sh 72.5              推一次
#   ./tools/push_temp.sh 72.5 --read       推完讀回來確認
#   ./tools/push_temp.sh 72.5 --hold 30    每 2 秒重推一次，維持 30 秒
#   ROUTE_A_ANYWAY=1 ./tools/push_temp.sh 72.5    跳過下面的擋門，硬跑
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

# ── 擋門：先確認那個物件真的在，不在就講清楚為什麼 ────────────────────
#    沒有這一段的話，使用者拿到的是 `Unknown object '...'`，
#    那句話不會告訴他「這條路線已經換掉了，去用 set_die_temp.py」。
if [[ "${ROUTE_A_ANYWAY:-0}" != "1" ]]; then
  if ! $S "busctl introspect ${SVC} ${OBJ} >/dev/null 2>&1"; then
    cat >&2 <<'EOF'
⚠️  這條路線（route (a) 的 external sensor）在目前的設定上不存在。

    swampd 只有在設定檔把 die0 的 readPath 指到
    /xyz/openbmc_project/extsensors/... 時才會建立那個物件。
    W3 之後 die0 走的是 route (b′)：真的 tmp421 -> hwmon -> dbus-sensors。

    要注入溫度請用：

        ./tools/set_die_temp.py 72.5 --verify

    （--verify 會等到 BMC 的 hwmon 真的看到預測值，見 runbook §8 坑 29。）

    真的要跑舊路線（例如重現 W2 的實驗），先把設定換回去，
    或設 ROUTE_A_ANYWAY=1 硬跑。
EOF
    exit 3
  fi
fi

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
