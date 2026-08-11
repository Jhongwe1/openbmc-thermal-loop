#!/usr/bin/env bash
#
# W8 exp09:failsafe 偵測延遲 —— 單次 run。
# 重複(5 次)、config 生成與單變因驗證、事件解析都在 bench/exp09_failsafe.py;
# 這支只負責一次「起匯流排 → 起 bridge(帶停止推值)→ 起 swampd → 收檔」。
#
# 用法(由 exp09_failsafe.py 呼叫;手動跑要自己給環境變數):
#   CONF=/tmp/config.failsafe.json RUN_ID=1 SEED=1 harness/l2_failsafe.sh
#
# 時間線(預設):
#   0        bridge 起,開始推溫度(恆定 150 W,無負載階躍)
#   ~2 s     swampd 起 —— 開機即 failsafe(initializeCache,見 docs/failsafe.md §1)
#   ~數秒    第一批有效讀值 → 退出初始 failsafe → 正常調節
#   0~300 s  收斂到 setpoint(config.tuned 的 λ=2τ 閉環 ≈ 88 s,3× 留裕)
#   300 s    ★ t0:bridge 停止推值(D-Bus 值凍結;plant/tach/PWM 照常)
#   ~305 s   sensor timeout(5 s)到期 → failsafe → PWM 拉 100%
#   330 s    收工
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

CONF="${CONF:?need CONF (swampd config with timeout=5)}"
RUN_ID="${RUN_ID:?need RUN_ID (1..5)}"
SEED="${SEED:-$RUN_ID}"
SWAMPD="${SWAMPD:-$HOME/work/ppc-l2/build/swampd}"
RUN_SECONDS="${RUN_SECONDS:-330}"
STOP_AT="${STOP_AT:-300}"
PLANT_LIB="${PLANT_LIB:-build/libplant_cabi.so}"
OUT_DIR="bench/data/exp09_failsafe"

if [ ! -x "$SWAMPD" ]; then
    echo "swampd 不在 $SWAMPD —— 先建上游(worktree ~/work/ppc-l2)" >&2
    exit 2
fi

BUSDIR=/tmp/obmcbus
LOGDIR=/tmp/pidlog_failsafe
mkdir -p "$BUSDIR" /tmp/sys "$LOGDIR" "$OUT_DIR"

if [ ! -S "$BUSDIR/socket" ]; then
    dbus-daemon --config-file="$REPO/harness/obmcbus.conf" --fork
fi
export DBUS_SYSTEM_BUS_ADDRESS="unix:path=$BUSDIR/socket"

# 乾淨起點(unlink 不是 rm -rf,見 CLAUDE.md 沙箱規則)
find "$LOGDIR" -maxdepth 1 -type f -exec unlink {} \; 2>/dev/null || true
printf '76' > /tmp/sys/pwm0
printf '0'  > /tmp/sys/fan0_input

python harness/dbus_bridge.py \
    --lib "$PLANT_LIB" \
    --csv "$OUT_DIR/run${RUN_ID}_plant.csv" \
    --seconds "$RUN_SECONDS" --seed "$SEED" \
    --power-at -1 --power-down-at -1 \
    --stop-push-at "$STOP_AT" &
BRIDGE_PID=$!
sleep 2   # sensor 與 mock mapper 先上桌

"$SWAMPD" -c "$CONF" -l "$LOGDIR" -g > "$LOGDIR/swampd.stdout" 2>&1 &
SWAMPD_PID=$!

trap 'kill $SWAMPD_PID $BRIDGE_PID 2>/dev/null || true' EXIT

wait "$BRIDGE_PID"

# ★ Gate 4 DoD:「busctl 讀出 FailSafe 為 true」。
#   bridge 已結束(t=330 s)、推值早在 t=300 s 停止、swampd 還活著且
#   已在 failsafe —— 這一刻讀屬性,存檔當證據。
#   注意這是**驗證**不是量測:FailSafe 是純 getter、從不發
#   PropertiesChanged(docs/failsafe.md),時序一律從 zone_0.log 量。
busctl get-property xyz.openbmc_project.State.FanCtrl \
    /xyz/openbmc_project/settings/fanctrl/zone0 \
    xyz.openbmc_project.Control.Mode FailSafe \
    > "$OUT_DIR/run${RUN_ID}_failsafe_property.txt" 2>&1 || true

kill "$SWAMPD_PID" 2>/dev/null || true
wait "$SWAMPD_PID" 2>/dev/null || true
trap - EXIT

cp "$LOGDIR/zone_0.log" "$OUT_DIR/run${RUN_ID}_zone0.log"
echo "exp09 run $RUN_ID done:"
ls -la "$OUT_DIR"/run"${RUN_ID}"_*
