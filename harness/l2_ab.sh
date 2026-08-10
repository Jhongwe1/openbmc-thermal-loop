#!/usr/bin/env bash
#
# W7 L2:同一個 anti-windup A/B,被測物換成**未修改的**上游 swampd 二進位。
#
# 用法: harness/l2_ab.sh clamp   # integralLimit [0, 15000](config.tuned.json)
#       harness/l2_ab.sh open    # ±1e6,等同關閉(config.nowindup.json)
#
# 為什麼一次跑一個 arm、只跑 1 個 seed:
#   L2 是即時的 —— swampd 的兩個迴路週期(100 ms / 1000 ms,exp06 實測)
#   掛在牆上時鐘,快轉不了,1500 s 就是真的 25 分鐘。
#   統計(5 seeds)由 L1 提供;L2 的任務是「趨勢在上游二進位上重現」。
#
# 私有匯流排:dbus-daemon 用 harness/obmcbus.conf 起在 /tmp/obmcbus/socket,
# swampd 與 bridge 都用 DBUS_SYSTEM_BUS_ADDRESS 指過去 ——
# 不碰系統匯流排、不需要 root、砍掉即忘。
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

ARM="${1:?usage: harness/l2_ab.sh clamp|open}"
SWAMPD="${SWAMPD:-$HOME/work/ppc-l2/build/swampd}"
RUN_SECONDS="${RUN_SECONDS:-1500}"
# 可覆寫 plant 共享庫的位置。用途:tools/mutation_check.sh 跑的時候會反覆
# 改壞並重建 build/,那段時間要 L2 跑就把 .so 先複製到 build/ 外面再指過來。
PLANT_LIB="${PLANT_LIB:-build/libplant_cabi.so}"

case "$ARM" in
    clamp) CONF="$REPO/config/swampd/config.tuned.json" ;;
    open)  CONF="$REPO/config/swampd/config.nowindup.json" ;;
    *) echo "unknown arm: $ARM (want clamp|open)" >&2; exit 2 ;;
esac
if [ ! -x "$SWAMPD" ]; then
    echo "swampd 不在 $SWAMPD —— 先建上游(worktree ~/work/ppc-l2,見 LOG.md)" >&2
    exit 2
fi

BUSDIR=/tmp/obmcbus
LOGDIR="/tmp/pidlog_$ARM"
mkdir -p "$BUSDIR" /tmp/sys "$LOGDIR"

if [ ! -S "$BUSDIR/socket" ]; then
    dbus-daemon --config-file="$REPO/harness/obmcbus.conf" --fork
fi
export DBUS_SYSTEM_BUS_ADDRESS="unix:path=$BUSDIR/socket"

# 乾淨起點:舊 log 清掉(unlink 不是 rm -rf,見 CLAUDE.md 的沙箱規則),
# PWM/tach 檔回到 swampd 起動前的世界(30% = raw 76,W2 在 BMC 實測的初值)。
find "$LOGDIR" -maxdepth 1 -type f -exec unlink {} \; 2>/dev/null || true
printf '76' > /tmp/sys/pwm0
printf '0'  > /tmp/sys/fan0_input

python harness/dbus_bridge.py \
    --lib "$PLANT_LIB" \
    --csv "bench/data/exp07_L2_${ARM}_plant.csv" \
    --seconds "$RUN_SECONDS" --seed 0 &
BRIDGE_PID=$!
sleep 2   # 讓 sensor 與 mock mapper 先上桌,swampd 一起來就找得到

"$SWAMPD" -c "$CONF" -l "$LOGDIR" -g > "$LOGDIR/swampd.stdout" 2>&1 &
SWAMPD_PID=$!

trap 'kill $SWAMPD_PID $BRIDGE_PID 2>/dev/null || true' EXIT

wait "$BRIDGE_PID"
kill "$SWAMPD_PID" 2>/dev/null || true
wait "$SWAMPD_PID" 2>/dev/null || true
trap - EXIT

cp "$LOGDIR/zone_0.log" "bench/data/exp07_L2_${ARM}_zone0.log"
for f in "$LOGDIR"/pidcore.* "$LOGDIR"/pidcoeffs.*; do
    [ -f "$f" ] && cp "$f" "bench/data/exp07_L2_${ARM}_$(basename "$f")"
done
echo "L2 $ARM done:"
ls -la bench/data/exp07_L2_${ARM}_* "$LOGDIR/swampd.stdout"
