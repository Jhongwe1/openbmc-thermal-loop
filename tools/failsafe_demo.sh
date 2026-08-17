#!/usr/bin/env bash
# failsafe 的互動演示:停止推送溫度 → sensor timeout → zone 進 failsafe。
#
# 這是 exp09(Fig 4)那個量測 rig 的**單次、縮時**版:同一支未修改的上游
# swampd 二進位、同一份 plant、同一個「timeout 0→5 是唯一差異」的 config
# 生成方式;差別只有時間軸(收斂段 120 s 而非 300 s)與輸出目錄
# (/tmp/demo_failsafe,不寫進 bench/data —— 這不是量測,量測見
# bench/exp09_failsafe.py 與 figures/fig4_failsafe.png)。
#
#   ./tools/failsafe_demo.sh                # 120 s 收斂 + 30 s failsafe 段
#   STOP_AT=60 RUN_SECONDS=90 ./tools/failsafe_demo.sh   # 更短(收斂勉強)
#
# 需要:build/libplant_cabi.so(meson compile -C build)與上游 swampd
# 二進位(預設 ~/work/ppc-l2/build/swampd,可用 SWAMPD= 覆蓋)。
#
# ★ 為什麼不在 QEMU 映像裡演:部署設定的 die0 是 passive D-Bus 感測器,
#   timeout 刻意為 0(passive 的時間戳綁在「值有沒有變」上,非零 timeout
#   會把穩定的溫度誤判成感測器死亡 —— config/swampd/README.md、
#   LOG.md 2026-08-06)。有 stale 偵測語意的是這個 rig 的推送式 sensor。
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"

STOP_AT="${STOP_AT:-120}"
RUN_SECONDS="${RUN_SECONDS:-150}"
SEED="${SEED:-1}"
SWAMPD="${SWAMPD:-$HOME/work/ppc-l2/build/swampd}"
PLANT_LIB="build/libplant_cabi.so"
CONF=/tmp/config.demo.json
OUT=/tmp/demo_failsafe
LOGDIR=/tmp/pidlog_demo
ZLOG="$LOGDIR/zone_0.log"

[ -x "$SWAMPD" ] || { echo "swampd not found at $SWAMPD (build the upstream worktree first)" >&2; exit 2; }
[ -f "$PLANT_LIB" ] || { echo "$PLANT_LIB missing (run: meson compile -C build)" >&2; exit 2; }

# config: same generation rule as exp09 -- die0 timeout 0->5 is the ONLY change.
python3 - "$CONF" <<'EOF'
import json, sys, copy
src = json.load(open("config/swampd/config.tuned.json"))
dst = copy.deepcopy(src)
for s in dst["sensors"]:
    if s["name"] == "die0":
        s["timeout"] = 5
diffs = [(a, b) for a, b in zip(
    json.dumps(src, sort_keys=True).split(","),
    json.dumps(dst, sort_keys=True).split(",")) if a != b]
assert len(diffs) == 1 and "timeout" in diffs[0][1], diffs
json.dump(dst, open(sys.argv[1], "w"), indent=2)
print(f"config written: {sys.argv[1]} (single diff vs tuned: die0 timeout 0->5)")
EOF

mkdir -p /tmp/obmcbus /tmp/sys "$LOGDIR" "$OUT"
find "$LOGDIR" -maxdepth 1 -type f -exec unlink {} \; 2>/dev/null || true
printf '76' > /tmp/sys/pwm0
printf '0'  > /tmp/sys/fan0_input

if [ ! -S /tmp/obmcbus/socket ]; then
    dbus-daemon --config-file="$REPO/harness/obmcbus.conf" --fork
fi
export DBUS_SYSTEM_BUS_ADDRESS="unix:path=/tmp/obmcbus/socket"

echo "== starting plant bridge (constant 150 W, push stops at t=${STOP_AT}s) =="
python3 harness/dbus_bridge.py \
    --lib "$PLANT_LIB" --csv "$OUT/demo_plant.csv" \
    --seconds "$RUN_SECONDS" --seed "$SEED" \
    --power-at -1 --power-down-at -1 \
    --stop-push-at "$STOP_AT" &
BRIDGE_PID=$!
sleep 2

echo "== starting UNMODIFIED upstream swampd (same binary version as the BMC image) =="
"$SWAMPD" -c "$CONF" -l "$LOGDIR" -g > "$LOGDIR/swampd.stdout" 2>&1 &
SWAMPD_PID=$!
trap 'kill $SWAMPD_PID $BRIDGE_PID 2>/dev/null || true' EXIT

# ---- live view: one status line per second, banners on events ------------
# ⚠️ 不要 tail zone_0.log 做即時顯示:swampd 的 log 是塊緩衝(ofstream),
#    檔案的最後一行幾乎永遠是被 4 KB 塊切斷的半行,而且落後數秒。
#    live 一律讀即時來源:swampd 每個內圈直寫的 /tmp/sys/pwm0、
#    busctl 讀 FailSafe 屬性與 bridge 的 Sensor.Value。
#    精確時序(t1/t2)由收尾段從落地後的完整 zone log 算。
START=$(date +%s)
announced_t0=0
announced_fs=0
announced_pwm=0
while kill -0 "$BRIDGE_PID" 2>/dev/null; do
    sleep 1
    rel=$(( $(date +%s) - START ))
    pwm_raw=$(cat /tmp/sys/pwm0 2>/dev/null || echo "")
    pwm_pct=$(awk -v r="$pwm_raw" 'BEGIN{ if (r=="") print "?"; else printf "%.0f", r/255*100 }')
    # || true:bridge/swampd 結束的瞬間 busctl 會失敗,而本腳本
    # set -o pipefail —— 沒兜住的話,demo 會在最後一秒無聲死掉,
    # cp 與 summary 全部不跑(2026-08-18 預跑實測)。
    die0=$(busctl get-property xyz.openbmc_project.ThermalLoopBridge \
             /xyz/openbmc_project/sensors/temperature/die0 \
             xyz.openbmc_project.Sensor.Value Value 2>/dev/null \
           | awk '{printf "%.2f", $2}' || true)
    fs=$(busctl get-property xyz.openbmc_project.State.FanCtrl \
             /xyz/openbmc_project/settings/fanctrl/zone0 \
             xyz.openbmc_project.Control.Mode FailSafe 2>/dev/null \
           | awk '{print $2}' || true)
    echo "[t=${rel}s] die0=${die0:-?} C   pwm0=${pwm_raw:-?}/255 (${pwm_pct}%)   FailSafe=${fs:-?}"
    if [ "$announced_t0" -eq 0 ] && [ "$rel" -ge "$STOP_AT" ]; then
        announced_t0=1
        echo ""
        echo "############################################################"
        echo "##  t0: temperature push STOPPED. D-Bus value is frozen. ##"
        echo "##  swampd sees no update; sensor timeout is 5 s.        ##"
        echo "############################################################"
        echo ""
    fi
    if [ "$announced_fs" -eq 0 ] && [ "$announced_t0" -eq 1 ] && [ "$fs" = "true" ]; then
        announced_fs=1
        echo ""
        echo "############################################################"
        echo "##  FAILSAFE: busctl now reads FailSafe = true.           ##"
        echo "##  (property polled once per second, right column)       ##"
        echo "############################################################"
        echo ""
    fi
    if [ "$announced_pwm" -eq 0 ] && [ "$announced_fs" -eq 1 ] && [ "$pwm_raw" = "255" ]; then
        announced_pwm=1
        echo ">> PWM at failsafePercent: /tmp/sys/pwm0 = 255/255 (100%)"
    fi
done

kill "$SWAMPD_PID" 2>/dev/null || true
wait "$SWAMPD_PID" 2>/dev/null || true
trap - EXIT
cp "$ZLOG" "$OUT/zone_0.log" 2>/dev/null || true

# ---- exact numbers from the log (same method as exp09, single run) -------
python3 - "$OUT" "$STOP_AT" <<'EOF'
import json, pathlib, sys
out = pathlib.Path(sys.argv[1]); stop_at = float(sys.argv[2])
meta = json.loads((out / "demo_plant_meta.json").read_text())
t0_ms = meta["epoch0_ms"] + stop_at * 1000.0
rows = [l.split(",") for l in (out / "zone_0.log").read_text().splitlines()[1:] if l]
t1_ms = next((float(r[0]) for r in rows if float(r[0]) > t0_ms and r[-1].strip() == "1"), None)
t2_ms = next((float(r[0]) for r in rows if t1_ms and float(r[0]) >= t1_ms and float(r[5]) >= 1.0), None)
print("\n== summary (this run; the 5-run measurement is Fig 4) ==")
if t1_ms: print(f"  t1 - t0 (push stopped -> failsafe flag) : {(t1_ms-t0_ms)/1000:.3f} s")
if t2_ms: print(f"  t2 - t0 (push stopped -> PWM at 100%)   : {(t2_ms-t0_ms)/1000:.3f} s")
print("  composition: sensor timeout 5 s + outer-loop check phase (~0-1 s)")
print("               + one inner cycle (100 ms) + ms-level writes")
print("  measured median over 5 runs: see bench/claims.json failsafe_detect_s")
EOF
echo
echo "done. raw output in $OUT (not part of bench/data -- this is a demo, not a measurement)"
