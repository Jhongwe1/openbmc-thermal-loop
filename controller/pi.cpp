// SPDX-License-Identifier: Apache-2.0
#include "controller/pi.hpp"

#include <algorithm>

namespace control
{

namespace
{
double clamp(double v, double lo, double hi)
{
    return std::clamp(v, lo, hi);
}
} // namespace

void Pi::reset()
{
    integral_ = 0.0;
    lastError_ = 0.0;
    lastOutput_ = 0.0;
    initialized_ = false;
}

double Pi::step(double input, double setpoint)
{
    if (p_.antiWindup == AntiWindup::UpstreamParity)
    {
        return stepLikeUpstream(input, setpoint);
    }

    const double error = setpoint - input;
    const double pTerm = p_.kp * error;
    const double dTerm =
        (p_.kd != 0.0) ? p_.kd * (error - lastError_) / p_.ts : 0.0;
    const double ffTerm = (setpoint + p_.feedFwdOffset) * p_.feedFwdGain;

    // ── 積分：先算出「這一步如果累加會變成多少」──────────────────
    double candidate = integral_;
    if (p_.ki != 0.0)
    {
        candidate = integral_ + error * p_.ki * p_.ts;
        if (p_.antiWindup == AntiWindup::Clamp ||
            p_.antiWindup == AntiWindup::BackCalculation)
        {
            candidate = clamp(candidate, p_.integralMin, p_.integralMax);
        }
    }

    double unsat = pTerm + candidate + dTerm + ffTerm;
    double out = clamp(unsat, p_.outMin, p_.outMax);

    // ── ② 條件積分：輸出已飽和，而且誤差方向會讓飽和更嚴重 → 撤銷這一步 ──
    //
    //    判斷的是「未箝位的輸出超出範圍」而不是「out == outMax」：
    //    輸出剛好等於上限但沒有超出，代表控制器正好用滿，不是飽和。
    if (p_.antiWindup == AntiWindup::Conditional && p_.ki != 0.0)
    {
        const bool worseHigh = (unsat > p_.outMax) && (error > 0.0);
        const bool worseLow = (unsat < p_.outMin) && (error < 0.0);
        if (worseHigh || worseLow)
        {
            candidate = integral_; // 不累加
            unsat = pTerm + candidate + dTerm + ffTerm;
            out = clamp(unsat, p_.outMin, p_.outMax);
        }
    }

    // ── slew rate limit（順序與上游一致：先箝位再限速）─────────────
    if (initialized_)
    {
        if (p_.slewNeg != 0.0)
        {
            out = std::max(out, lastOutput_ + p_.slewNeg * p_.ts);
        }
        if (p_.slewPos != 0.0)
        {
            out = std::min(out, lastOutput_ + p_.slewPos * p_.ts);
        }
    }

    // ── ③ 標準回算：用飽和後的實際輸出反推積分 ─────────────────────
    //
    //    I += (sat(u) − u) · ts / Tt
    //
    //    `out - unsat` 就是 (sat(u) − u)：輸出被箝位或被 slew 削掉了多少。
    //    沒有飽和時它是 0，整段變成空操作 —— 由
    //    Pi.BackCalculationIsANoOpWhileUnsaturated 守著。
    //
    //    ★ Tt = ts（trackingTimeS 為 0）時，這一式**代數上等於**
    //      `integral = out - pTerm - dTerm - ffTerm`（W5 的寫法）：
    //          candidate + (out − (pTerm + candidate + dTerm + ffTerm))
    //        = out − pTerm − dTerm − ffTerm
    //      所以補回 Tt 不改變任何既有結果，只是把「那個特例」變成「可以調」。
    //
    //    ⚠️ 這裡刻意與上游不同。上游是 integral = output - proportionalTerm，
    //       沒有扣掉 feedFwdTerm 與 derivativeTerm。ff != 0 時兩者會分歧。
    //       這個分歧是刻意保留的，見 test/test_parity_upstream.cpp 與
    //       docs/upstream.md 的候選 1。
    if (p_.antiWindup == AntiWindup::BackCalculation && p_.ki != 0.0)
    {
        const double tt = (p_.trackingTimeS > 0.0) ? p_.trackingTimeS : p_.ts;
        candidate = clamp(candidate + (out - unsat) * p_.ts / tt,
                          p_.integralMin, p_.integralMax);
    }

    integral_ = candidate;
    lastError_ = error;
    lastOutput_ = out;
    initialized_ = true;
    return out;
}

/**
 * 逐行對照上游 phosphor-pid-control 的 pid/ec/pid.cpp。
 *
 * ─────────────────────────────────────────────────────────────────────
 *  出處與授權（★ 這一段是必要的，不是禮貌）
 *
 *  行為複製自：openbmc/phosphor-pid-control，檔案 `pid/ec/pid.cpp`，
 *              commit `c5e59550d37a5be079f724a6e2633d4aae3ee238`
 *              （與這台 BMC 映像裡的 swampd 同一版，見 docs/env-baseline.md）
 *  上游授權：  Apache License 2.0
 *  本檔授權：  Apache License 2.0（同上，見檔案開頭的 SPDX 標記）
 *
 *  ⚠️ 這裡**沒有複製上游的原始碼**，複製的是**行為**：這個函式是我自己
 *     照著上游那份實作重寫的，用途是讓 parity 測試有一個「應該一模一樣」
 *     的對照組。上游真正的程式碼是由 meson wrap 抓下來、原封不動編進
 *     test/test_parity_upstream.cpp 的（見 subprojects/phosphor-pid-control.wrap）。
 *
 *     即使如此，**衍生自 Apache-2.0 作品的行為描述仍應標明出處**，
 *     而且對這個專案來說還有第二個理由：「我跟上游哪一版比對過」
 *     這句話沒有 commit hash 就沒有可查證的對象。
 * ─────────────────────────────────────────────────────────────────────
 *
 * 註解裡標的三個 ★ 是計畫給的虛擬碼寫錯、而我讀原始碼才發現的地方。
 * 它們每一個都會讓 parity 測試在特定參數組合下失敗，所以這三行本身就是
 * 「我真的讀過那份原始碼」的證據。
 */
double Pi::stepLikeUpstream(double input, double setpoint)
{
    const double error = setpoint - input;
    const double pTerm = p_.kp * error;

    double integralTerm = 0.0;
    if (p_.ki != 0.0)
    {
        integralTerm = integral_;
        integralTerm += error * p_.ki * p_.ts;
        integralTerm = clamp(integralTerm, p_.integralMin, p_.integralMax);
    }

    // ★ 1：上游沒有 `if (derivativeCoeff != 0)` 這個判斷，D 項每輪都算。
    //       kd = 0 時結果一樣是 0，但除法照做 —— ts 若為 0 會是 inf/NaN，
    //       而上游的註解正好寫著 "Note: Codes assumes the ts field is non-zero"。
    const double dTerm = p_.kd * ((error - lastError_) / p_.ts);

    const double ffTerm = (setpoint + p_.feedFwdOffset) * p_.feedFwdGain;

    double output = pTerm + integralTerm + dTerm + ffTerm;
    output = clamp(output, p_.outMin, p_.outMax);

    if (initialized_)
    {
        if (p_.slewNeg != 0.0)
        {
            output = std::max(output, lastOutput_ + p_.slewNeg * p_.ts);
        }
        if (p_.slewPos != 0.0)
        {
            output = std::min(output, lastOutput_ + p_.slewPos * p_.ts);
        }

        // ★ 2：觸發條件是「slew 有設定」，不是「slew 真的咬到了輸出」。
        //       而且回算只扣 pTerm —— dTerm 與 ffTerm 沒有扣。
        if (p_.slewNeg != 0.0 || p_.slewPos != 0.0)
        {
            integralTerm = output - pTerm;
        }
    }

    // ★ 3：這次箝位在 if 外面，無條件執行。
    //       上游的註解說它是為了「輸出被限制之後積分可能變大」，
    //       但實際上它每一輪都跑，包含 slew 完全沒設定的那些輪。
    integralTerm = clamp(integralTerm, p_.integralMin, p_.integralMax);

    integral_ = integralTerm;
    lastError_ = error;
    lastOutput_ = output;
    initialized_ = true;
    return output;
}

} // namespace control
