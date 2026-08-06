#!/usr/bin/env bash
#
# 負向驗證（mutation testing）—— 這支腳本檢查的不是 plant，是**測試套件**。
#
# 為什麼需要它
# ------------
# `meson test` 顯示全綠，只證明「目前的程式碼沒有觸發任何斷言」。
# 它**不**證明「如果程式碼壞了，斷言會叫」。一個永遠會過的測試也是綠的。
#
# 做法：把已知的錯誤一個一個植入 plant，重編、重跑測試，記錄哪些測試變紅，
# 然後把原始碼還原。**每一個植入的錯誤都必須至少被一個測試抓到**；
# 有任何一個活下來（survivor），代表測試套件在那個方向上是瞎的。
#
# 用法
# ----
#   ./tools/mutation_check.sh            # 用 build/
#   ./tools/mutation_check.sh mybuild    # 用別的 build 目錄
#
# 離開碼：0 = 全部被抓到；1 = 有 survivor（測試套件有漏洞）。
#         所以它可以直接掛進 CI（W10）。
#
# ⚠️ 安全性：本腳本會**暫時改寫** plant/ 底下的原始碼。
#    它用「備份到暫存目錄 → trap EXIT 還原」，不是 `git checkout --`，
#    因為後者會連你還沒 commit 的改動一起洗掉。
#
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO" || exit 1

BUILD="${1:-build}"
SRC="plant/thermal_plant.cpp"
HDR="plant/thermal_plant.hpp"

if [ ! -d "$BUILD" ]; then
    echo "找不到 build 目錄 '$BUILD'。先跑：meson setup $BUILD" >&2
    exit 2
fi

# ── 備份與還原 ────────────────────────────────────────────────────────
# trap ... EXIT 的意思是「不管這支腳本怎麼結束（正常、出錯、Ctrl-C），
# 都要執行 restore」。沒有它，中途按 Ctrl-C 會讓 plant 停在被植入錯誤的狀態。
BACKUP="$(mktemp -d)"
cp "$SRC" "$HDR" "$BACKUP/"

restore() {
    cp "$BACKUP/$(basename "$SRC")" "$SRC"
    cp "$BACKUP/$(basename "$HDR")" "$HDR"
    rm -rf "$BACKUP"
}
trap restore EXIT

# ── 字面替換（用 python 而不是 sed，避開跳脫地獄）──────────────────────
# 這些字串裡有 (、)、*、/、.，在 sed/perl 的正規表示式裡全都要跳脫，
# 一個寫錯就變成「沒替換到但也沒報錯」——那會讓整份報告變成假的綠。
subst() {
    python3 - "$1" "$2" "$3" <<'PY'
import pathlib, sys
path, old, new = sys.argv[1], sys.argv[2], sys.argv[3]
p = pathlib.Path(path)
s = p.read_text()
if old not in s:
    sys.exit(3)          # 找不到 => 實作已經改過，這個 mutation 過期了
p.write_text(s.replace(old, new, 1))
PY
}

PASS=0
SURVIVED=0

run_case() {
    local name="$1" file="$2" from="$3" to="$4"

    if ! subst "$file" "$from" "$to"; then
        printf '%-38s  ⚠ 過期（找不到要替換的字串）\n' "$name"
        SURVIVED=$((SURVIVED + 1))
        return
    fi

    local failed
    if ! meson compile -C "$BUILD" >/dev/null 2>&1; then
        # 編不過也算被抓到：錯誤在編譯期就被擋下來了，比執行期更早。
        printf '%-38s  ✅ 編不過\n' "$name"
        PASS=$((PASS + 1))
        restore_sources
        return
    fi

    # ⚠️ 一定要 --print-errorlogs。沒有它，meson 只印「1/1 plant FAIL」，
    #    gtest 的 [  FAILED  ] 行不會出現，下面的 grep 會永遠抓不到東西
    #    ——整張表會變成一片「沒有任何測試變紅」的假象。（2026-08-07 踩過）
    failed=$(meson test -C "$BUILD" --print-errorlogs 2>&1 \
        | grep -oE '\[  FAILED  \] [A-Za-z]+\.[A-Za-z]+' \
        | sed 's/.*\] //' | sort -u | paste -sd, -)

    if [ -z "$failed" ]; then
        printf '%-38s  ❌ 沒有任何測試變紅\n' "$name"
        SURVIVED=$((SURVIVED + 1))
    else
        printf '%-38s  ✅ %s\n' "$name" "$failed"
        PASS=$((PASS + 1))
    fi
    restore_sources
}

restore_sources() {
    cp "$BACKUP/$(basename "$SRC")" "$SRC"
    cp "$BACKUP/$(basename "$HDR")" "$HDR"
}

# ── 植入的錯誤清單 ────────────────────────────────────────────────────
# 挑選原則：每一條都是「我真的可能寫錯」的錯，不是為了湊數的隨機變異。
#   M1/M2 符號錯     —— 控制系統最貴的一種 bug（W5 地雷 #9）
#   M3    死區沒生效 —— FOPDT 的 theta 會被吃進 tau
#   M4    離散化寫反 —— dt/tau 與 tau/dt 長得幾乎一樣
#   M5    亂數共用   —— 破壞可重現性，而且不會有任何錯誤訊息
#   M6    實驗前提消失 —— 飽和不再發生，Fig 3 會變成兩條重疊的線
echo "植入的錯誤                              哪些測試抓到了"
echo "--------------------------------------  --------------------------------"

run_case "M1 熱阻內插符號反" "$SRC" \
    '(1.0 - std::pow(q, p_.flowExp))' '(std::pow(q, p_.flowExp))'

run_case "M2 功耗項符號反" "$SRC" \
    'p_.tAmb + powerW * rth' 'p_.tAmb - powerW * rth'

run_case "M3 死區佇列拿掉" "$SRC" \
    'const double tArrived = delay_.front();' \
    'const double tArrived = tDie_;'

run_case "M4 一階離散化寫反" "$SRC" \
    'tDie_ += (tSs - tDie_) * dt_ / p_.tauDie;' \
    'tDie_ += (tSs - tDie_) * p_.tauDie / dt_;'

run_case "M5 rng 改成全域共用" "$SRC" \
    'const double raw = tSense_ + noise_(rng_);' \
    'static std::mt19937 shared(0);
    const double raw = tSense_ + noise_(shared);'

run_case "M6 rthMin 調小（飽和條件消失）" "$HDR" \
    'double rthMin = 0.12;' 'double rthMin = 0.08;'

# ── 收尾 ──────────────────────────────────────────────────────────────
meson compile -C "$BUILD" >/dev/null 2>&1

echo
if [ "$SURVIVED" -eq 0 ]; then
    echo "全部 $PASS 個植入的錯誤都至少被一個測試抓到。"
    exit 0
fi
echo "⚠️ 有 $SURVIVED 個 mutation 活下來 —— 測試套件在那些方向上抓不到錯。"
exit 1
