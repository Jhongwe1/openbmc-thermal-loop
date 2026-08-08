#!/usr/bin/env bash
#
# exp02 —— 兩點符號檢查：把溫度 PID 的比例係數設成指定值，餵兩個溫度點，記錄輸出。
#
#   ./tools/sign_check.sh  500      # 正係數（對 temp 型別而言是錯的符號）
#   ./tools/sign_check.sh -500      # 負係數
#
#   REPEATS=3 ./tools/sign_check.sh -500     # 改重複次數（預設 5）
#   KEEP_CONFIG=1 ./tools/sign_check.sh 500  # 跑完**不要**還原（除錯時才用）
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
#
# ★★ 為什麼跑完一定要還原（2026-08-09 補）
#   這支腳本會把**錯的符號**部署到 BMC 上。原本跑完就結束，那台機器就帶著
#   錯的係數繼續跑，而且沒有任何提示。下一個實驗會踩到，症狀是
#   「風扇越熱轉越慢」—— **剛好就是這支腳本要示範的那個 bug**，
#   除錯的人會非常困惑。`mutation_check.sh` 用「備份 + trap 還原」是這個專案
#   自己立的標準，這裡照做。
set -euo pipefail

KP="${1:?用法: ./tools/sign_check.sh <proportionalCoeff>，例如 500 或 -500}"
COLD_C="${COLD_C:-55}"      # 低於 setpoint 的溫度點
HOT_C="${HOT_C:-75}"        # 高於 setpoint 的溫度點
SETTLE_S="${SETTLE_S:-10}"  # 注入到達之後再等幾秒（溫度 PID 是 1 Hz）
# 協定（docs/measurement.md §1）要求至少 5 次重複。這條路徑是數位、決定性的，
# 所以重複的意義不是求平均，是**證明它決定性** —— 報「五次完全相同」。
REPEATS="${REPEATS:-5}"

cd "$(dirname "$0")/.."

SSHOPTS=(-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR)
S=(sshpass -p 0penBmc ssh -n "${SSHOPTS[@]}" -p 2222 root@127.0.0.1)
SCP=(sshpass -p 0penBmc scp -P 2222 "${SSHOPTS[@]}")

OUTDIR="${OUTDIR:-bench/data/exp02_signcheck}"
mkdir -p "${OUTDIR}"
TAG="kp${KP}"
BASELINE="config/swampd/config.baseline.json"

TMPCONF="$(mktemp)"

# ── 還原：不管怎麼結束都要把 BMC 放回 baseline ────────────────────────
restore_bmc() {
    local status=$?
    unlink "${TMPCONF}" 2>/dev/null || true
    if [ "${KEEP_CONFIG:-0}" = "1" ]; then
        echo
        echo "⚠️ KEEP_CONFIG=1：BMC 上留著 proportionalCoeff = ${KP}（錯的符號）。" >&2
        echo "   下一個實驗會讀到它。要還原：./tools/sign_check.sh 0" >&2
        return $status
    fi
    echo
    echo "==> 還原 BMC 設定為 ${BASELINE}"
    "${SCP[@]}" "${BASELINE}" root@127.0.0.1:/etc/thermal-loop/config.json >/dev/null || true
    # ⚠️ reset-failed 不是可有可無：測試床的 drop-in 有 StartLimitBurst=3
    #    （W2 刻意加的，理由見 LOG.md 2026-08-05）。跑到這裡時 swampd 很可能
    #    已經處在 start-limit-hit 狀態，restart 會直接被拒絕。
    "${S[@]}" 'systemctl reset-failed phosphor-pid-control; systemctl restart phosphor-pid-control' || true
    sleep 3
    # ★★ 還原要**驗證**，不能只是印一行「已還原」。
    #    第一版就是印了「已還原成 baseline」但 swampd 其實根本沒起來 ——
    #    一個假的成功訊息比沒有訊息更糟，因為它會讓人停止檢查。
    if "${S[@]}" 'systemctl is-active phosphor-pid-control' >/dev/null 2>&1; then
        echo "==> 已還原成 baseline（所有 PID 係數為 0），swampd active"
    else
        echo "❌ 還原失敗：swampd 沒有回到 active。" >&2
        "${S[@]}" 'systemctl status phosphor-pid-control --no-pager | tail -n 15' >&2 || true
        echo "   BMC 現在的狀態不乾淨，下一個實驗不要直接跑。" >&2
        [ "$status" -eq 0 ] && status=1
    fi
    return $status
}
trap restore_bmc EXIT

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
"${S[@]}" 'rm -f /tmp/pidlog/pidcore.die0; systemctl reset-failed phosphor-pid-control; systemctl restart phosphor-pid-control'
sleep 5
"${S[@]}" 'systemctl is-active phosphor-pid-control'

# ── 2. 中繼資料 —— 沒有它，這批 CSV 指不回任何一個版本 ────────────────
#    exp01 有 exp01_sysid_meta.txt，exp02/03 一開始沒有：
#    kp500.csv 是 159 bytes 的純數字，說不出是在什麼上面量的。
# ⚠️ 每一個 Kp 一份 meta，不是整個目錄共用一份。
#    **Kp 就是這個實驗的自變因** —— 共用一份的話，後跑的那次會把前一次的
#    中繼資料蓋掉，於是 kp-500.csv 旁邊躺著一份寫著 `kp=500` 的 meta。
#    （第一版就是這樣寫的，跑完第二組才發現。）
META="${OUTDIR}/${TAG}_meta.txt"
{
    echo "# exp02 — 兩點符號檢查。欄位定義見 docs/measurement.md §4。"
    echo "# repo_dirty=yes 是正常的：資料一定在收錄它的那個 commit **之前**產生。"
    echo "captured_at=$(date +%F)"
    echo "repo_commit=$(git rev-parse --short HEAD)"
    echo "repo_dirty=$( [ -n "$(git status --porcelain)" ] && echo yes || echo no )"
    echo "image=$(grep -m1 '主線映像' docs/env-baseline.md | cut -d'`' -f2)"
    echo "swampd_version=$(grep -m1 -F '`phosphor-pid-control`' docs/env-baseline.md | cut -d'`' -f4)"
    echo "bmc_build_id=$("${S[@]}" '. /etc/os-release && echo $BUILD_ID')"
    echo "bmc_kernel=$("${S[@]}" 'uname -r')"
    echo "independent_variable=die0 proportionalCoeff"
    echo "kp=${KP}"
    echo "cold_c=${COLD_C}"
    echo "hot_c=${HOT_C}"
    echo "setpoint_c=$(python3 -c "import json;print(json.load(open('${BASELINE}'))['zones'][0]['pids'][0]['setpoint'])")"
    echo "out_lim_min=$(python3 -c "import json;print(json.load(open('${BASELINE}'))['zones'][0]['pids'][0]['pid']['outLim_min'])")"
    echo "out_lim_max=$(python3 -c "import json;print(json.load(open('${BASELINE}'))['zones'][0]['pids'][0]['pid']['outLim_max'])")"
    echo "sample_period_s=$(python3 -c "import json;print(json.load(open('${BASELINE}'))['zones'][0]['pids'][0]['pid']['samplePeriod'])")"
    echo "settle_s=${SETTLE_S}"
    echo "repeats=${REPEATS}"
    echo "# ↓ 這次實際部署到 BMC 的完整設定（唯一的變因就在裡面）"
    sed 's/^/config| /' "${TMPCONF}"
} > "${META}"
echo "==> 寫出 ${META}"

# ── 3. 兩個溫度點 × REPEATS 次 ────────────────────────────────────
CSV="${OUTDIR}/${TAG}.csv"
echo "repeat,temp_set_c,input_c,setpoint_c,error_c,proportionalTerm,output_unclamped,output_clamped" > "${CSV}"

# ⚠️ **重複的是「注入 → 等 → 讀」這個量測序列，不是 swampd 的啟動。**
#
#    第一版每一輪都重啟一次 swampd（想讓每輪完全獨立），結果第 2 輪就撞上
#    **這個專案自己加的 `StartLimitBurst=3`**（W2 為了不讓測試床被重啟風暴
#    拖垮而加的，見 LOG.md 2026-08-05）——
#    `Job for phosphor-pid-control.service failed because start of the service
#     was attempted too often.`
#
#    而且重啟本來就沒有必要：這組參數 ki = kd = slew = 0，
#    輸出是 `clamp(kp × error)`，**沒有任何內部狀態**。
#    每一輪重新注入兩個溫度點就是一次完整、獨立的量測。
#
#    ★ 教訓：**做防護的設定會咬到自己的自動化。** 那不是設定寫錯 ——
#      `StartLimitBurst=3` 在測試床上是對的。要改的是「別把重啟塞進迴圈」。
for r in $(seq 1 "${REPEATS}"); do
  echo "==> 第 ${r}/${REPEATS} 次"
  for T in "${COLD_C}" "${HOT_C}"; do
    echo "    注入 ${T} °C"
    # ★ 用 --verify 不用 --read：--read 只證明 QEMU 收下了，
    #   --verify 證明 BMC 的 hwmon 真的看到了（見 runbook 坑 29）。
    ./tools/set_die_temp.py "${T}" --verify
    sleep "${SETTLE_S}"
    # pidcore.die0 欄位（上游 DumpContextHeader）：
    #   epoch_ms,input,setpoint,error,proportionalTerm,integralTerm1,integralTerm2,
    #   derivativeTerm,feedFwdTerm,output1,output2,minOut,maxOut,
    #   integralTerm3,output3,integralTerm,output
    #        1      2      3        4          5              6            7
    #        8            9           10      11    12    13
    #        14            15      16          17
    LINE="$("${S[@]}" 'tail -n 1 /tmp/pidlog/pidcore.die0')"
    echo "${r},${T},${LINE}" | awk -F, '{printf "%s,%s,%s,%s,%s,%s,%s,%s\n", $1, $2, $4, $5, $6, $7, $12, $19}' >> "${CSV}"
  done
done

echo
echo "==> 結果（${CSV}）"
column -s, -t < "${CSV}"

# ── 4. 決定性檢查：五次要完全一樣 ─────────────────────────────────
#     這條路徑是數位的，所以「重複」報的不是中位數與範圍，是**逐點相同**。
#     真的出現差異的話，那個差異本身才是要報的東西 —— 不可以偷偷取平均。
echo
python3 - "${CSV}" "${REPEATS}" <<'PY'
import csv, sys
rows = list(csv.DictReader(open(sys.argv[1])))
expected = int(sys.argv[2])
by_repeat = {}
for r in rows:
    by_repeat.setdefault(r["repeat"], []).append(
        tuple(r[k] for k in r if k != "repeat"))
repeats = sorted(by_repeat)
if len(repeats) != expected:
    sys.exit(f"❌ 只有 {len(repeats)} 次重複，協定要求 {expected} 次")
first = by_repeat[repeats[0]]
differing = [r for r in repeats[1:] if by_repeat[r] != first]
if differing:
    print(f"⚠️ 第 {differing} 次與第 {repeats[0]} 次不同 —— 這條路徑不是決定性的。")
    print("   不要取平均：先弄清楚為什麼會變。")
    sys.exit(1)
print(f"✅ {len(repeats)} 次重複逐點完全相同 —— 這條量測路徑是決定性的。")
PY
