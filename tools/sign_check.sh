#!/usr/bin/env bash
#
# 兩點符號檢查：把溫度 PID 的比例係數設成指定值，餵兩個溫度點，記錄輸出。
#
#   ./tools/sign_check.sh  500      # 正係數（對 temp 型別而言是錯的符號）
#   ./tools/sign_check.sh -500      # 負係數
#
# ★ 這個實驗在回答什麼
#   ec::pid() 的誤差定義是 error = setpoint - input。input 是絕對溫度時，
#   溫度上升會讓 error 變負；要讓輸出（風扇轉速需求）上升，比例係數必須是負的。
#   上面那句話是從原始碼推出來的，不是量出來的 —— 所以要量。
#
# ★ 為什麼觀察的是「溫度 PID 的輸出」而不是 PWM
#   swampd 是串級的：溫度 PID（1 Hz）算出 RPM setpoint，風扇 PID（10 Hz）
#   才把 RPM 誤差轉成 PWM。本專案的風扇 PID 係數目前是 0，所以 PWM 不會動；
#   要驗溫度 PID 的符號，就要看溫度 PID 自己的輸出。
#   swampd 的 -g（core logging）把每一輪的中間量寫進 /tmp/pidlog/pidcore.die0，
#   欄位見上游 pid/ec/logging.cpp 的 DumpContextHeader()。
#
# ★ 為什麼係數用 ±500 而不是計畫寫的 ±100
#   die0 的 outLim_min 是 3000 RPM（zone 的 minThermalOutput）。誤差是 ±10 °C，
#   Kp=100 時 |輸出| 只有 1000，兩個溫度點都會被箝到 3000，看起來一模一樣 ——
#   實驗會「成功地什麼都沒測到」。Kp=500 讓其中一點落在 5000，另一點才對比得出來。
#   （這本身就是結果：符號錯 + 箝位，症狀不是「風扇變慢」，是「風扇卡在最低速
#     而且看起來一切正常」。）
set -euo pipefail

KP="${1:?用法: ./tools/sign_check.sh <proportionalCoeff>，例如 500 或 -500}"
COLD_C="${COLD_C:-55}"      # 低於 setpoint 的溫度點
HOT_C="${HOT_C:-75}"        # 高於 setpoint 的溫度點
SETTLE_S="${SETTLE_S:-10}"  # 每個溫度點等幾秒（溫度 PID 是 1 Hz）

cd "$(dirname "$0")/.."

SSHOPTS=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR)
S=(sshpass -p 0penBmc ssh -n "${SSHOPTS[@]}" -p 2222 root@127.0.0.1)
SCP=(sshpass -p 0penBmc scp -P 2222 "${SSHOPTS[@]}")

OUTDIR="${OUTDIR:-bench/data/exp02_signcheck}"
mkdir -p "${OUTDIR}"
TAG="kp${KP}"

TMPCONF="$(mktemp)"
trap 'rm -f "${TMPCONF}"' EXIT

# ── 1. 產生只改一個欄位的設定檔 ────────────────────────────────────
#    刻意用程式改而不是手動編輯：單變因實驗最怕的就是「我以為我只改了一個地方」。
python3 - "$KP" "$TMPCONF" <<'PY'
import json, sys
kp, out = float(sys.argv[1]), sys.argv[2]
cfg = json.load(open("config/swampd/config.baseline.json"))
n = 0
for zone in cfg["zones"]:
    for pid in zone["pids"]:
        if pid["name"] == "die0":
            pid["pid"]["proportionalCoeff"] = kp
            n += 1
assert n == 1, f"預期剛好改到一個 die0 PID，實際改到 {n} 個"
json.dump(cfg, open(out, "w"), indent=2)
PY

echo "==> 部署設定：die0 proportionalCoeff = ${KP}"
"${SCP[@]}" "${TMPCONF}" root@127.0.0.1:/etc/thermal-loop/config.json >/dev/null
# 清掉舊的 core log，才不會讀到上一輪的尾巴
"${S[@]}" 'rm -f /tmp/pidlog/pidcore.die0 && systemctl restart phosphor-pid-control'
sleep 5
"${S[@]}" 'systemctl is-active phosphor-pid-control'

# ── 2. 兩個溫度點 ──────────────────────────────────────────────────
CSV="${OUTDIR}/${TAG}.csv"
echo "temp_set_c,input_c,setpoint_c,error_c,proportionalTerm,output_unclamped,output_clamped" > "${CSV}"

for T in "${COLD_C}" "${HOT_C}"; do
  echo "==> 注入 ${T} °C"
  ./tools/set_die_temp.py "${T}" --read
  sleep "${SETTLE_S}"
  # pidcore.die0 欄位（上游 DumpContextHeader）：
  #   epoch_ms,input,setpoint,error,proportionalTerm,integralTerm1,integralTerm2,
  #   derivativeTerm,feedFwdTerm,output1,output2,minOut,maxOut,
  #   integralTerm3,output3,integralTerm,output
  #        1      2      3        4          5              6            7
  #        8            9           10      11    12    13
  #        14            15      16          17
  LINE="$("${S[@]}" 'tail -n 1 /tmp/pidlog/pidcore.die0')"
  echo "    raw: ${LINE}"
  echo "${T},${LINE}" | awk -F, '{printf "%s,%s,%s,%s,%s,%s,%s\n", $1, $3, $4, $5, $6, $11, $18}' >> "${CSV}"
done

echo
echo "==> 結果（${CSV}）"
column -s, -t < "${CSV}"
