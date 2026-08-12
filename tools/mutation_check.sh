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
IDN="plant/identify.cpp"
CTL="controller/pi.cpp"
MET="bench/metrics.py"
STD="tools/set_die_temp.py"
PRV="bench/provenance.py"
SIM="bench/sim.cpp"
PRS="bench/parse_l2.py"
EX9="bench/exp09_failsafe.py"
EXA="bench/exp10_latency.py"
AST="bench/assert_metrics.py"

if [ ! -d "$BUILD" ]; then
    echo "找不到 build 目錄 '$BUILD'。先跑：meson setup $BUILD" >&2
    exit 2
fi

# ── 開工前：確認該有的測試真的在這個 build 裡 ──────────────────────────
#
# ★ 為什麼需要這一段（坑 27 的自動化版）
#   `upstream-parity` 是 auto，缺 subproject 時 parity 測試會**安靜地消失**，
#   而 `meson test` 依然回報全綠。那種情況下這支腳本會把 C1~C11 全部判成
#   survivor —— 訊息是「測試套件有漏洞」，但真正的原因是「那個測試根本沒建」。
#   **診斷訊息指錯方向，比沒有訊息更浪費時間。**
EXPECTED_TESTS="plant identify pi closed_loop parity_upstream metrics"
AVAILABLE="$(meson test -C "$BUILD" --list 2>/dev/null)"
MISSING=""
for t in $EXPECTED_TESTS; do
    case " $(echo "$AVAILABLE" | sed 's#.* / ##' | paste -sd' ' -) " in
        *" $t "*) ;;
        *) MISSING="$MISSING $t" ;;
    esac
done
if [ -n "$MISSING" ]; then
    echo "⚠️ 這個 build 少了測試：$MISSING" >&2
    echo "   在植入錯誤之前就少了測試，跑下去只會得到一堆誤報的 survivor。" >&2
    echo "   parity_upstream 不見的話見 runbook §8 坑 27（要 allow_fallback）。" >&2
    exit 2
fi

# ── 備份與還原 ────────────────────────────────────────────────────────
# trap ... EXIT 的意思是「不管這支腳本怎麼結束（正常、出錯、Ctrl-C），
# 都要執行 restore」。沒有它，中途按 Ctrl-C 會讓 plant 停在被植入錯誤的狀態。
BACKUP="$(mktemp -d)"
ALL_SOURCES="$SRC $HDR $IDN $CTL $MET $STD $PRV $SIM $PRS $EX9 $EXA $AST"
# shellcheck disable=SC2086
cp $ALL_SOURCES "$BACKUP/"

restore() {
    restore_sources
    rm -rf "$BACKUP"
}
trap restore EXIT
# ⚠️ 光有 EXIT 不夠(2026-08-11 用慘痛方式實測):bash 收到**未攔截的**
#    SIGTERM/SIGINT 時直接死,EXIT trap 不會執行 —— 上面註解裡「Ctrl-C
#    也會還原」在那之前是一句沒驗證過的話。被 pkill 的那一輪把 P4 突變體
#    留在 bench/metrics.py 裡,九個測試從此恆紅,而下一輪 mutation 的
#    每一個案例都被那九個紅「誤抓」—— 整張表變成假的。
#    這裡把訊號轉成 exit,EXIT trap 才會接手還原。
trap 'exit 143' INT TERM

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
    # 跑一次，兩種格式各抓一次。
    #
    # gtest：  [  FAILED  ] Suite.Case
    # pytest： FAILED test/python/test_metrics.py::test_case - AssertionError...
    #
    # ⚠️ 測試名稱可能含數字、底線，參數化 gtest 還會有 `Suite/0.Case`。
    #    原本的 [A-Za-z]+ 對它們全部抓不到 —— 而抓不到的症狀是
    #    「沒有任何測試變紅」，也就是**假的 survivor**。
    local log
    log=$(meson test -C "$BUILD" --print-errorlogs 2>&1)
    failed=$(
        {
            printf '%s\n' "$log" \
                | grep -oE '\[  FAILED  \] [A-Za-z_][A-Za-z0-9_/]*\.[A-Za-z0-9_/]+' \
                | sed 's/.*\] //'
            printf '%s\n' "$log" \
                | grep -oE '^FAILED [^ ]+::[A-Za-z0-9_]+' \
                | sed 's#^FAILED .*/##; s#\.py::#.#'
        } | sort -u | paste -sd, -
    )

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
    # ⚠️ 迴圈而不是逐行 cp：這份清單加過三次（identify、controller、Python），
    #    每一次都有可能忘了同步還原那一行。忘了的後果是**植入的錯誤留在原始碼裡**，
    #    而且 git status 會顯示一個你以為自己沒改過的檔案。
    local f
    for f in $ALL_SOURCES; do
        cp "$BACKUP/$(basename "$f")" "$f"
    done
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

# ── 識別演算法（plant/identify.cpp）────────────────────────────────────
#   I1  兩點法的係數 1.5 是從 t₂−t₁ = ⅔τ 推導出來的，不是調出來的
#   I2  28.3% 這個百分比也是推導出來的 —— 改了就消不掉 theta
#   I3  升降方向判斷 —— 只跑降溫方向的測試抓不到，所以有 HandlesRisingResponse
#   I4  基準值改回單點 —— 這是我刻意偏離計畫的地方，必須有測試守著，
#       否則哪天被「簡化」回去，不會有任何人發現（單點也會吐出正常的數字）
run_case "I1 兩點法係數 1.5 -> 1.0" "$IDN" \
    'f.tau = 1.5 * (t2 - t1);' 'f.tau = 1.0 * (t2 - t1);'

run_case "I2 28.3% 改成 40%" "$IDN" \
    '0.283 * (yInf - y0)' '0.400 * (yInf - y0)'

run_case "I3 crossingTime 方向判斷反向" "$IDN" \
    'const bool rising = target > y0;' 'const bool rising = target < y0;'

# ⚠️ I4 刻意寫成「把視窗縮到零」而不是「整段換成 y[iStep]」。
#    後者會讓變數變成未使用，被 -Werror 擋在編譯期 ——
#    腳本會回報「✅ 編不過」，看起來過關，但**斷言根本沒被執行到**。
#    「編不過」是比「測試變紅」弱的證據，設計 mutation 時要避開它。
#
#    視窗歸零之後，迴圈第一輪就 break、n = 0，走到「退回單一點」那條路 ——
#    也就是計畫原本的寫法。
#
#    ⚠️ 寫成 `const double start = t[from];` 會讓 windowS 變成未使用參數，
#       -Werror 擋在編譯期 —— 又變成那個「✅ 編不過」的弱證據。
#       用 std::min(windowS, 0.0) 讓參數仍然被讀到，效果一樣是視窗歸零。
run_case "I4 基準值改回單點（計畫原本的寫法）" "$IDN" \
    'const double start = t[from] - windowS;' \
    'const double start = t[from] - std::min(windowS, 0.0);'

# I5 是配合 2026-08-09 把視窗從「列數」改成「時間」而加的：
# 把時間比較改成「大於」，視窗會變成階躍**之後**的那一段 —— 完全錯的基準值。
run_case "I5 基準視窗取到階躍之後" "$IDN" \
    'if (t[i] < start)' 'if (t[i] > start)'

# ── 控制器（controller/pi.cpp，W5）────────────────────────────────────
#
# C1~C3 動的是 AntiWindup::UpstreamParity 那條路徑 —— 它的規格不是「好的控制器」，
# 是「上游 ec::pid() 此刻的行為」，所以只有 parity 測試能判它對錯。
# 這三條剛好就是我讀原始碼時，計畫給的虛擬碼寫錯的那三個地方：
# 如果 parity 測試抓不到它們，那份測試等於沒有在證明「我讀懂了上游」。
#
# C4~C5 動的是我自己的兩個策略。
run_case "C1 上游回算條件 || 改成 &&" "$CTL" \
    'p_.slewNeg != 0.0 || p_.slewPos != 0.0' \
    'p_.slewNeg != 0.0 && p_.slewPos != 0.0'

run_case "C2 上游回算多扣前饋" "$CTL" \
    'integralTerm = output - pTerm;' \
    'integralTerm = output - pTerm - ffTerm;'

run_case "C3 上游最後那次箝位拿掉" "$CTL" \
    'integralTerm = clamp(integralTerm, p_.integralMin, p_.integralMax);

    integral_ = integralTerm;' \
    'integral_ = integralTerm;'

run_case "C4 條件積分永不生效" "$CTL" \
    'if (worseHigh || worseLow)' 'if (worseHigh && worseLow)'

# 「少扣前饋」在 Tt 版本裡等價於「回算時把 ffTerm 加回去」：
#   I = I_cand + (out − unsat)·ts/Tt，unsat 裡含 ffTerm；
#   多加一個 ffTerm 就等於回算時沒把它扣掉（= 上游的行為）。
run_case "C5 標準回算少扣前饋" "$CTL" \
    'candidate = clamp(candidate + (out - unsat) * p_.ts / tt,' \
    'candidate = clamp(candidate + (out - unsat + ffTerm) * p_.ts / tt,'

# ── 取樣週期 ts（2026-08-09 稽核補的）────────────────────────────────
#
# ★ 為什麼這六條特別重要：在補之前，**每一個測試的 ts 都是 1.0**。
#   乘 1 跟不乘看起來完全一樣，所以每一處「× ts」「÷ ts」都沒有被測到。
#   實測 C6~C9 四個植入的錯**全部活了下來**，整套測試依然全綠 ——
#   那是這次稽核找到最大的一個測試盲區。
#
#   而且這不是理論問題：config/swampd/config.baseline.json 裡風扇 PID 的
#   samplePeriod 就是 **0.1**。之前驗過的 ts = 1.0 是我實際上不會用的那個值。
#
# C6/C10/C11 動我自己的 step()，C7/C8/C9 動上游相容路徑 ——
# 兩條路徑各有一份 ts 算術，要分別植入才涵蓋得到。
run_case "C6 積分不乘 ts（我的 step）" "$CTL" \
    'candidate = integral_ + error * p_.ki * p_.ts;' \
    'candidate = integral_ + error * p_.ki;'

run_case "C7 積分不乘 ts（上游相容路徑）" "$CTL" \
    'integralTerm += error * p_.ki * p_.ts;' \
    'integralTerm += error * p_.ki;'

run_case "C8 slew 不乘 ts（上游相容路徑）" "$CTL" \
    'output = std::max(output, lastOutput_ + p_.slewNeg * p_.ts);' \
    'output = std::max(output, lastOutput_ + p_.slewNeg);'

run_case "C9 微分不除 ts（上游相容路徑）" "$CTL" \
    'const double dTerm = p_.kd * ((error - lastError_) / p_.ts);' \
    'const double dTerm = p_.kd * (error - lastError_);'

# ⚠️ C10/C11 是計畫的修復清單裡**沒有**的兩條。
#    清單只列了上游那條路徑的 slew 與微分，但我自己的 step() 也各有一份 ——
#    而且原本同樣沒有任何 ts != 1 的測試碰過它們。
#    「同一個錯誤在兩個地方」是最容易只修一半的情形。
run_case "C10 slew 不乘 ts（我的 step）" "$CTL" \
    'out = std::max(out, lastOutput_ + p_.slewNeg * p_.ts);' \
    'out = std::max(out, lastOutput_ + p_.slewNeg);'

run_case "C11 微分不除 ts（我的 step）" "$CTL" \
    '(p_.kd != 0.0) ? p_.kd * (error - lastError_) / p_.ts : 0.0;' \
    '(p_.kd != 0.0) ? p_.kd * (error - lastError_) : 0.0;'

# ── 回算的追蹤時間常數 Tt（2026-08-09 補回 backCalcGain 時一起加的）──
#
# 計畫的 PiParams 本來有這個參數，W5 實作時默默刪掉了，於是 BackCalculation
# 退化成「Tt = ts」的特例。補回來之後一定要有 mutation 守著，
# 否則哪天有人把它「簡化」掉，測試不會有任何反應（預設值本來就是那個特例）。
# ⚠️ C12 刻意寫成「忽略參數」而不是「把 * p_.ts / tt 整段刪掉」——
#    後者會讓 tt 變成未使用變數，被 -Werror 擋在編譯期，
#    腳本回報「✅ 編不過」看起來過關，但**斷言根本沒被執行到**。
#    而且「忽略參數」才是真的會再發生一次的那種退化：W5 就是這樣弄丟它的。
run_case "C12 回算忽略 trackingTimeS（退回 W5 的行為）" "$CTL" \
    'const double tt = (p_.trackingTimeS > 0.0) ? p_.trackingTimeS : p_.ts;' \
    'const double tt = p_.ts;'

run_case "C13 Tt 與 ts 的比例寫反" "$CTL" \
    'candidate = clamp(candidate + (out - unsat) * p_.ts / tt,' \
    'candidate = clamp(candidate + (out - unsat) * tt / p_.ts,'

# ── 誤差定義（閉環的方向由它決定）────────────────────────────────────
#
# ⚠️ `const double error = setpoint - input;` 在這個檔案裡出現**兩次**
#    （我的 step() 一次、上游相容路徑一次），而 subst 只換第一個。
#    所以這一條動到的是**我自己的 step()** —— 上游那條由 parity 顧。
#    這是「同一行程式在兩個地方」的第三個例子（前兩個是 slew 與微分的 ts）。
run_case "C14 誤差定義反向（我的 step）" "$CTL" \
    'const double error = setpoint - input;' \
    'const double error = input - setpoint;'

# ── Python 這一側（bench/metrics.py、tools/set_die_temp.py）────────────
#
# ★ 為什麼 Python 的 mutation 不需要另一套跑法
#   pytest 已經接進 `meson test`（見 test/meson.build），所以上面那個 run_case
#   原封不動就能用：改 .py -> meson compile（對 Python 是 no-op）-> meson test。
#   多寫一套「Python 專用的 mutation 流程」只會多一個會走味的地方。
#
# ⚠️ 為什麼一定要有這一段
#   metrics.py 是**全專案每個應變因的唯一定義來源**，而它到 2026-08-09 為止
#   一個測試都沒有。補了測試之後如果不做負向驗證，就只是把「沒測試」
#   換成「有一組沒被證明會咬人的測試」—— 這個專案從 W3 起就不接受那個。

run_case "P1 t_peak_c 取 min 而不是 max" "$MET" \
    'return float(df["t_sense_c"].max())' \
    'return float(df["t_sense_c"].min())'

run_case "P2 t_peak_c 抓錯欄位（模型真值）" "$MET" \
    'return float(df["t_sense_c"].max())' \
    'return float(df["t_die_c"].max())'

run_case "P3 尾段視窗變成頭段" "$MET" \
    'return df[df["t_s"] >= t_end - tail_s]' \
    'return df[df["t_s"] <= t_end - tail_s]'

run_case "P4 視窗起點正負號寫反" "$MET" \
    'return df[df["t_s"] >= t_end - tail_s]' \
    'return df[df["t_s"] >= t_end + tail_s]'

run_case "P5 尾段取最大值而不是平均" "$MET" \
    'return float(tail_window(df, tail_s)["fan_power_rel"].mean())' \
    'return float(tail_window(df, tail_s)["fan_power_rel"].max())'

# ★ P6/P7 動的是注入路徑的預測式。它們的守門員是 exp04 那批**實測 CSV** ——
#   也就是說，這兩條同時證明了「那些 CSV 是有在承重的證據，不是裝飾」。
run_case "P6 QEMU setter 的 −128 拿掉" "$STD" \
    'stored = _to_int16(_c_div(requested_mC * 256 - 128, 1000) + offset)' \
    'stored = _to_int16(_c_div(requested_mC * 256, 1000) + offset)'

run_case "P7 C 的整數除法改成 Python 的 //" "$STD" \
    '    quotient = abs(numerator) // abs(denominator)
    same_sign = (numerator >= 0) == (denominator > 0)
    return quotient if same_sign else -quotient' \
    '    return numerator // denominator'

# ★ P8 植的是一個**真的發生過**的退化：caption 記 HEAD 而不是資料的 commit。
#   那讓「clone 下來跑一次得到同一張圖」變成假話，而且**看不出來** ——
#   每一張圖單獨看都很正常，要真的去 clone 一份才會發現。
run_case "P8 caption 退回記 HEAD" "$PRV" \
    'head = _git("log", "-1", "--format=%h", "--", *paths)' \
    'head = _git("rev-parse", "--short", "HEAD")'

# ── W6 的四個新指標（2026-08-11）──────────────────────────────────────
#
# ★ P11 與 P15 特別重要：它們植入的**就是計畫給的那份實作**。
#   也就是說，這兩條同時回答了「我為什麼不照抄計畫」——
#   如果照抄的版本能通過我的測試，那我的偏離就只是個人品味；
#   它們會變紅，才證明那兩處偏離真的有守到東西。

run_case "P9  overshoot 忘了下限 0" "$MET" \
    'return max(0.0, t_peak_c(df) - setpoint)' \
    'return t_peak_c(df) - setpoint'

run_case "P10 overshoot 相減方向反" "$MET" \
    'return max(0.0, t_peak_c(df) - setpoint)' \
    'return max(0.0, setpoint - t_peak_c(df))'

# ★ P11 = 計畫 W6 §2 給的 settle_s 實作（用列數框 hold_s）。
#   守門員是 test_settle_window_is_defined_by_time_not_by_row_count。
run_case "P11 settle_s 改回列數框（計畫的寫法）" "$MET" \
    '    entered = None
    for i in range(t.size):
        if not inside[i]:
            entered = None
            continue
        if entered is None:
            entered = t[i]
        if t[i] - entered >= hold_s:
            return float(entered)
    return float("nan")' \
    '    dt = float(t[1] - t[0]) if t.size > 1 else 1.0
    n_hold = max(1, int(hold_s / dt))
    run = 0
    for i in range(t.size):
        run = run + 1 if inside[i] else 0
        if run >= n_hold:
            return float(t[i - n_hold + 1])
    return float("nan")'

run_case "P12 settle_s 回確認時刻而非進入時刻" "$MET" \
    '            return float(entered)' \
    '            return float(t[i])'

run_case "P13 settle_s 離開帶內不重新計時" "$MET" \
    '        if not inside[i]:
            entered = None
            continue' \
    '        if not inside[i]:
            continue'

run_case "P14 pwm_pp 取全程而不是尾段" "$MET" \
    '    w = tail_window(df, tail_s)
    return float(w["pwm"].max() - w["pwm"].min())' \
    '    w = df
    return float(w["pwm"].max() - w["pwm"].min())'

# ★ P15 = 計畫 W6 §2 給的 reversals 分母（用 tail_s 而不是實際跨度）。
#   守門員是 test_reversals_denominator_is_the_actual_span_not_the_requested_window。
run_case "P15 reversals 分母改回 tail_s（計畫的寫法）" "$MET" \
    'return reversals * 60.0 / span_s' \
    'return reversals * 60.0 / tail_s'

run_case "P16 reversals 的 deadband 失效" "$MET" \
    'd = d[np.abs(d) > deadband]' \
    'd = d[np.abs(d) > 0.0]'

# ── W7 的兩個新指標 ＋ sim 的第二段階躍（2026-08-11）───────────────────
#
# ★ P17 與 W6 的 P11/P15 同一個家族：植入的**就是計畫給的那份實作**。
#   計畫的 recover_s 偽碼拿 index 的**標籤**去餵 iloc（**位置**）——
#   exp07 永遠傳「從 power_down_at 起裁切」的 DataFrame 進來，
#   標籤不從 0 開始，兩者就對不上。
#   守門員是 test_recover_s_uses_positions_not_index_labels。

run_case "P17 recover_s 改回計畫的寫法（標籤當位置）" "$MET" \
    '    below = np.nonzero(sensed <= setpoint)[0]
    if below.size == 0:
        return float("nan")
    i0 = int(below[0])

    released = np.nonzero(pwm[i0:] < pwm_threshold)[0]
    if released.size == 0:
        return float("nan")
    return float(t[i0 + int(released[0])] - t[i0])' \
    '    below = df.index[df["t_sense_c"] <= setpoint]
    if len(below) == 0:
        return float("nan")
    i0 = int(below[0])
    after = df.iloc[i0:]
    low = after.index[after["pwm"] < pwm_threshold]
    if len(low) == 0:
        return float("nan")
    return float(df["t_s"].iloc[int(low[0])] - df["t_s"].iloc[i0])'

run_case "P18 recover_s 門檻方向反" "$MET" \
    'released = np.nonzero(pwm[i0:] < pwm_threshold)[0]' \
    'released = np.nonzero(pwm[i0:] > pwm_threshold)[0]'

run_case "P19 recover_s 從整段開頭找 PWM" "$MET" \
    'released = np.nonzero(pwm[i0:] < pwm_threshold)[0]' \
    'released = np.nonzero(pwm < pwm_threshold)[0]'

run_case "P20 integral_max 忘了絕對值" "$MET" \
    'return float(df[col].abs().max())' \
    'return float(df[col].max())'

run_case "P21 integral_max 缺欄回 0 而不是 NaN" "$MET" \
    '    if col not in df.columns:
        return float("nan")' \
    '    if col not in df.columns:
        return 0.0'

# B1 動的是 bench/sim.cpp —— 降回條件不生效的話，Fig 3 的負載曲線就沒有
# 第二段階躍：A/B 只看得到 windup 發生、看不到它的代價（地雷 #10 的近親）。
run_case "B1 sim 的 power-down-at 不生效" "$SIM" \
    '        if (a.powerDownAtS >= 0.0 && t >= a.powerDownAtS)
        {
            pw = a.powerBase;
        }' \
    '        if (a.powerDownAtS >= 0.0 && t >= a.powerDownAtS)
        {
            pw = a.powerStep;
        }'

# ── 方波負載（bench/sim.cpp，W8）──────────────────────────────────────
#
# Fig 5 的 40 份 CSV 全靠這個波形。S1~S3 是「波形錯但 CSV 看起來完全正常」
# 的三種寫法（恆為高、高低顛倒、相位沒對 power-at）—— 每一種都會讓
# 整條掃描量到別的東西。守門員是 test_sim_cli.py 的五段逐段斷言。
run_case "S1 方波半週期忘了除 2（恆為 step）" "$SIM" \
    'pw = (phase < a.powerPeriodS / 2.0) ? a.powerStep : a.powerBase;' \
    'pw = (phase < a.powerPeriodS) ? a.powerStep : a.powerBase;'

run_case "S2 方波高低顛倒" "$SIM" \
    'pw = (phase < a.powerPeriodS / 2.0) ? a.powerStep : a.powerBase;' \
    'pw = (phase < a.powerPeriodS / 2.0) ? a.powerBase : a.powerStep;'

run_case "S3 方波相位忘了以 power-at 為原點" "$SIM" \
    'const double phase = std::fmod(t - a.powerAtS, a.powerPeriodS);' \
    'const double phase = std::fmod(t, a.powerPeriodS);'

# S4：square 的參數沒進 stderr dump —— exp08 的單變因檢查讀的就是這份 dump，
# 沒進 dump 的參數等於躲過了機器檢查（與 test_power_down_at_is_recorded 同族）。
run_case "S4 方波參數沒進參數 dump" "$SIM" \
    '"power_profile=square\npower_period=%g\n"' \
    '""'

# ── failsafe 事件偵測（bench/exp09_failsafe.py，W8）──────────────────
#
# E1 是「看起來完全正常的負延遲」：swampd 開機就在 failsafe
# （initializeCache），忘了裁到 t0 之後，全域第一個 failsafe=1 是
# **開機殘留** —— 量到的是開機時刻不是逾時偵測，方向剛好偏袒好看。
run_case "E1 exp09 事件搜尋忘了裁到 t0 後" "$EX9" \
    'after = zone[zone["epoch_ms"] >= t0_ms]' \
    'after = zone'

# E2：run 有效性前提被拿掉 —— t0 時還在開機 failsafe 的 run 會被
# 當成正常資料收下，而它的「延遲」是垃圾。
run_case "E2 exp09 的 t0 前狀態檢查失效" "$EX9" \
    'if int(before["failsafe"].iloc[-1]) != 0:' \
    'if False:'

# ── 端到端延遲分析(bench/exp10_latency.py,W9)────────────────────────
#
# T1:②的基準拿成注入時刻 —— 段差仍是正數、量綱正確,只是把①偷進②。
# T5 是 E1 的同族:事件搜尋忘了裁到 t0 之後,抓到上一輪的殘影,
# 這次的後果是**負的延遲**被悄悄收下。守門員:test_exp10.py。
run_case "T1 exp10 的②段偷含了①(基準錯拿注入時刻)" "$EXA" \
    '"seg2_s": t_zone_bmc - t_dbus_bmc,' \
    '"seg2_s": (t_zone_bmc + offset) - t0,'

run_case "T2 exp10 量具健康看平均不看最大" "$EXA" \
    'max_gap = max(gaps) if gaps else float("inf")' \
    'max_gap = min(gaps) if gaps else float("inf")'

run_case "T3 exp10 的 p95 偷換成 max" "$EXA" \
    '"p95": statistics.quantiles(vals, n=20, method="inclusive")[18],' \
    '"p95": vals[-1],'

run_case "T4 exp10 拿注入值而非量化預測值比對" "$EXA" \
    'EXPECTED_C = tuple(expected_hwmon_mC(int(round(c * 1000))) / 1000.0
                   for c in LEVELS_C)' \
    'EXPECTED_C = LEVELS_C'

run_case "T5 exp10 序列建構忘了去重(dbus 每變化發兩則)" "$EXA" \
    '        if lev != last:
            dbus_seq.append((lev, ts))' \
    '        if True:
            dbus_seq.append((lev, ts))'

run_case "T6 exp10 統計忘了排除暖身" "$EXA" \
    '    kept = [r for r in rows if not r["warmup"]]' \
    '    kept = rows'

# ── L2 載入器（bench/parse_l2.py，W7）────────────────────────────────
#
# 這兩條的守門員都在 test_parse_l2.py，樣本行取自真實 log。
# P22 的後果是「假好看」：0~1 的值永遠低於 90% 門檻，recover_s 秒回 0，
# windup 最嚴重的那組反而拿到最漂亮的數字 —— 方向剛好偏袒造假。
run_case "P22 zone 的 pwm 少乘 100" "$PRS" \
    '"pwm": df["fan0_pwm"] * 100.0,' \
    '"pwm": df["fan0_pwm"],'

# P23 抓成箝位**前**的欄位：clamp arm 的第三面板會畫出一條「穿過
# 箝位線」的曲線 —— 機制圖直接說謊，而兩個欄位在多數樣本上相等。
run_case "P23 pidcore 抓箝位前的 integralTerm1" "$PRS" \
    '"integral_rpm": df["integralTerm"],
        "integral": df["integralTerm"] / RPM_PER_PCT,' \
    '"integral_rpm": df["integralTerm1"],
        "integral": df["integralTerm1"] / RPM_PER_PCT,'

# ── AM 系列:assert_metrics.py(W10)———————————————————————
# CI 的最後一道閘門如果自己是壞的,前面所有測試的意義都會被它洗掉。
# 「檢查器要被檢查」不是修辭 —— 下面每一條都是檢查器安靜失效的真實方式。

# AM1 植回計畫 W10 範本的原始寫法:lo=v(1−t)、hi=v(1+t) 不排序。
# value<0 時區間上下顛倒(fopdt_k = −0.31),斷言恆 FAIL ——
# 方向是「誤報」不是「漏報」,但誤報的檢查器會被人加 || true 繞過,
# 下場一樣。守門員:test_band_handles_negative_claims。
run_case "AM1 允收區間不排序(計畫的寫法)" "$AST" \
    'lo, hi = sorted((value * (1.0 - tolerance_pct),
                     value * (1.0 + tolerance_pct)))' \
    'lo = value * (1.0 - tolerance_pct)
    hi = value * (1.0 + tolerance_pct)'

# AM2 配對比值退化成「兩組中位數相除」:13.727 → 13.79,差 0.4%,
# 允收區間(±15%)照樣過 —— 只有 rel=1e-3 的釘死測試分得出來。
# 守門員:test_paired_ratio_convention_pinned。
run_case "AM2 recover 比值不配對(中位數相除)" "$AST" \
    'pairs = zip(_csvs("exp07_awopen_seed*.csv"),
                _csvs("exp07_awclamp_seed*.csv"), strict=True)
    return statistics.median(rec(o) / rec(c) for o, c in pairs)' \
    'opens = _csvs("exp07_awopen_seed*.csv")
    clamps = _csvs("exp07_awclamp_seed*.csv")
    return (statistics.median(rec(o) for o in opens)
            / statistics.median(rec(c) for c in clamps))'

# AM3 失敗聚合變成「最後一個說了算」:中段 FAIL 被尾端 PASS 洗白,
# CI 恆綠 —— 一個永遠是綠的 CI 跟沒有 CI 一樣(Gate 7 原文)。
# 守門員:test_tampered_claim_fails(竄改的就是中段的 claim)。
run_case "AM3 失敗聚合被最後一項覆寫" "$AST" \
    'ok = ok and passed' \
    'ok = passed'

# AM4 e2e 忘了排除暖身 rep:median 位置偏移,量到的混入尚未穩定的
# 前兩筆 —— 與 T6(exp10 統計忘了排除暖身)同病,但這裡是檢查器側。
# 守門員:test_e2e_uses_only_non_warmup_reps(獨立重算 + n=28)。
run_case "AM4 e2e 檢查不排除暖身" "$AST" \
    'kept = df[df["warmup"].astype(str) != "True"]' \
    'kept = df'

# ── 收尾 ──────────────────────────────────────────────────────────────
meson compile -C "$BUILD" >/dev/null 2>&1

echo
if [ "$SURVIVED" -eq 0 ]; then
    echo "全部 $PASS 個植入的錯誤都至少被一個測試抓到。"
    exit 0
fi
echo "⚠️ 有 $SURVIVED 個 mutation 活下來 —— 測試套件在那些方向上抓不到錯。"
exit 1
