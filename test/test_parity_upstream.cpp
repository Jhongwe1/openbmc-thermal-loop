// SPDX-License-Identifier: Apache-2.0
//
// 把我的 PI 與**真正的上游 ec::pid()** 逐步比對。
//
// 上游那三個編譯單元（pid/ec/pid.cpp、pid/ec/logging.cpp、pid/tuning.cpp）
// 是由 meson 從 subprojects/phosphor-pid-control 拉下來、用同一個編譯器編進
// 這個測試的。釘住的 commit 見 subprojects/phosphor-pid-control.wrap，
// 與這台 BMC 映像裡的 swampd 同一版（docs/env-baseline.md）。
//
// ★ 三個設計決定，每一個都會被問：
//
//   1. 比對的是**序列**不是單點。PID 有狀態，單點一致證明不了什麼；
//      真正會分歧的是積分與 slew 的路徑相依行為。
//
//   2. 輸入序列必須包含「爬升 → 飽和 → 解除」。**那正是 anti-windup 的作用
//      區間。不製造飽和的測試等於沒測。**
//
//   3. 分歧不藏起來、也不改我的實作去配合。分歧寫成一個獨立的測試，
//      量出它的量級，記在 docs/upstream.md。
#include "controller/pi.hpp"
#include "pid/ec/pid.hpp"

#include <gtest/gtest.h>

#include <cmath>
#include <string>
#include <vector>

namespace
{

using control::AntiWindup;
using control::Pi;
using control::PiParams;

/// 爬升 → 飽和 → 解除 的輸入序列（單位：°C，設定點在 40~80 之間掃）。
///
/// 前段緩慢逼近並越過設定點（讓積分累積、輸出撞上限），
/// 中段停在高溫（維持飽和），後段快速降回設定點以下（解除飽和，
/// 這一段才看得出 windup 有沒有被處理）。
std::vector<double> rampThenSaturateThenRelease()
{
    std::vector<double> v;
    for (double x = 20.0; x <= 120.0; x += 2.5) // 爬升並越過
    {
        v.push_back(x);
    }
    for (int i = 0; i < 30; ++i) // 維持飽和
    {
        v.push_back(120.0);
    }
    for (double x = 120.0; x >= 20.0; x -= 5.0) // 解除
    {
        v.push_back(x);
    }
    for (int i = 0; i < 20; ++i) // 停在設定點以下
    {
        v.push_back(20.0);
    }
    return v;
}

struct Fixture
{
    pid_control::ec::pid_info_t up{};
    PiParams mineParams{};

    Fixture(double slewPos, double slewNeg, double ffGain, double kd)
    {
        // 兩邊填**完全一樣**的參數。刻意逐欄寫出來而不是寫一個轉換函式：
        // 轉換函式如果哪一欄漏了，測試會綠 —— 而它綠的原因是兩邊都是 0。
        up.ts = 1.0;
        up.proportionalCoeff = -2.0; // temp 型別要負的（見 exp02 符號檢查）
        up.integralCoeff = -0.5;
        up.derivativeCoeff = kd;
        up.feedFwdOffset = 3.0;
        up.feedFwdGain = ffGain;
        up.integralLimit.min = -40.0;
        up.integralLimit.max = 40.0;
        up.outLim.min = 30.0;
        up.outLim.max = 100.0;
        up.slewNeg = slewNeg;
        up.slewPos = slewPos;

        mineParams.ts = up.ts;
        mineParams.kp = up.proportionalCoeff;
        mineParams.ki = up.integralCoeff;
        mineParams.kd = up.derivativeCoeff;
        mineParams.feedFwdOffset = up.feedFwdOffset;
        mineParams.feedFwdGain = up.feedFwdGain;
        mineParams.integralMin = up.integralLimit.min;
        mineParams.integralMax = up.integralLimit.max;
        mineParams.outMin = up.outLim.min;
        mineParams.outMax = up.outLim.max;
        mineParams.slewNeg = up.slewNeg;
        mineParams.slewPos = up.slewPos;
        mineParams.antiWindup = AntiWindup::UpstreamParity;
    }
};

/**
 * 主測試：掃一批參數組合，每一組跑一整條輸入序列，逐步比對。
 *
 * 容差 1e-12 而不是 1e-9：兩邊是同一個編譯器、同一組浮點運算、同樣的順序，
 * 所以**應該是逐位元相同**。容差放鬆會掩蓋掉真正的邏輯差異。
 * 這裡留 1e-12 只是不想在 -ffast-math 之類的環境下變成硬性 bit 比較。
 */
TEST(UpstreamParity, MatchesAcrossStepBattery)
{
    const auto inputs = rampThenSaturateThenRelease();
    int combos = 0;

    for (double setpoint : {40.0, 65.0, 80.0})
    {
        for (double slewPos : {0.0, 2.0, 5.0})
        {
            for (double slewNeg : {0.0, -3.0})
            {
                for (double kd : {0.0, 1.5})
                  for (double ffGain : {0.0, 0.4})
                {
                    // ★ ffGain 一定要掃到非零。
                    //   我第一版只掃 0，理由是「ff != 0 時會分歧」——那是把兩件事
                    //   搞混了。分歧的是**我自己的標準回算**（下一個測試在管）；
                    //   UpstreamParity 這個模式的規格是「不管參數是什麼，都跟上游
                    //   一模一樣」。漏掉 ff != 0 的話，「回算時多扣了前饋」這種錯
                    //   會完全沒有測試抓得到 —— 這是我做 mutation 設計時才發現的。
                    Fixture f(slewPos, slewNeg, ffGain, kd);
                    Pi mine(f.mineParams);
                    ++combos;

                    for (size_t i = 0; i < inputs.size(); ++i)
                    {
                        const double u = pid_control::ec::pid(
                            &f.up, inputs[i], setpoint, nullptr);
                        const double m = mine.step(inputs[i], setpoint);
                        ASSERT_NEAR(u, m, 1e-12)
                            << "  step=" << i << "  input=" << inputs[i]
                            << "  setpoint=" << setpoint
                            << "  slewPos=" << slewPos
                            << "  slewNeg=" << slewNeg << "  kd=" << kd;
                        ASSERT_NEAR(f.up.integral, mine.integral(), 1e-12)
                            << "  積分先分家了，step=" << i;
                    }
                }
            }
        }
    }
    EXPECT_EQ(combos, 3 * 3 * 2 * 2 * 2);
}

/// 序列真的有製造飽和嗎？——「不製造飽和的測試等於沒測」，所以這件事
/// 本身要有一個測試守著，不能靠我相信自己設計的序列。
TEST(UpstreamParity, TheBatteryActuallySaturatesBothLimits)
{
    Fixture f(0.0, 0.0, 0.0, 0.0);
    Pi mine(f.mineParams);
    bool hitMax = false;
    bool hitMin = false;
    for (double input : rampThenSaturateThenRelease())
    {
        const double out = mine.step(input, 65.0);
        hitMax = hitMax || (out >= f.mineParams.outMax);
        hitMin = hitMin || (out <= f.mineParams.outMin);
    }
    EXPECT_TRUE(hitMax) << "序列沒有把輸出推到上限，anti-windup 那一段沒被測到";
    EXPECT_TRUE(hitMin) << "序列沒有把輸出推到下限";
}

/**
 * ★ 刻意保留的分歧。
 *
 * 上游在 slew 生效時把積分回算成 (output - proportionalTerm)，
 * **沒有扣掉 derivativeTerm 與 feedFwdTerm**。當 feedFwdGain != 0 且
 * slew 有設定時，我的標準回算與上游會分家。
 *
 * 我沒有改我的實作去配合上游，因為我不確定哪一個是對的。
 * 這個測試量出分歧的量級，數字寫進 docs/upstream.md 的候選 1。
 */
TEST(UpstreamParity, DivergesWhenSlewAndFeedForwardCoexist)
{
    const auto inputs = rampThenSaturateThenRelease();

    Fixture f(2.0, -3.0, 0.4, 0.0); // slew 有設定 + 前饋不為零
    PiParams standard = f.mineParams;
    standard.antiWindup = AntiWindup::BackCalculation; // 我的標準回算

    Pi mine(standard);

    double maxDiff = 0.0;
    double maxIntegralDiff = 0.0;
    size_t firstDivergence = inputs.size();

    for (size_t i = 0; i < inputs.size(); ++i)
    {
        const double u = pid_control::ec::pid(&f.up, inputs[i], 65.0, nullptr);
        const double m = mine.step(inputs[i], 65.0);
        const double d = std::fabs(u - m);
        if (d > 1e-12 && i < firstDivergence)
        {
            firstDivergence = i;
        }
        maxDiff = std::max(maxDiff, d);
        maxIntegralDiff =
            std::max(maxIntegralDiff, std::fabs(f.up.integral - mine.integral()));
    }

    // 這個測試斷言的是「分歧存在且量級可觀」，不是「輸出應該等於某個數字」。
    // 前者是我對上游行為的理解；後者會把我自己的實作細節焊死在測試裡。
    EXPECT_LT(firstDivergence, inputs.size())
        << "預期會分歧但沒有分歧 —— 上游可能改了行為，回頭讀 pid.cpp";
    EXPECT_GT(maxDiff, 1.0);

    std::cout << "[分歧量測] 第一個分岔的時間步 = " << firstDivergence
              << "\n              輸出最大差 = " << maxDiff
              << "\n              積分最大差 = " << maxIntegralDiff
              << "\n              （參數：slewPos=2, slewNeg=-3, ffGain=0.4,"
                 " setpoint=65）\n";
}

/// 反過來確認分歧的**成因**：把前饋關掉、slew 留著，兩者就該一致。
/// 這條是上一個測試的控制組 —— 沒有它，「分歧來自前饋」只是我的說法。
TEST(UpstreamParity, NoDivergenceWhenFeedForwardIsZero)
{
    Fixture f(2.0, -3.0, 0.0, 0.0);
    PiParams standard = f.mineParams;
    standard.antiWindup = AntiWindup::BackCalculation;
    Pi mine(standard);

    for (double input : rampThenSaturateThenRelease())
    {
        const double u = pid_control::ec::pid(&f.up, input, 65.0, nullptr);
        ASSERT_NEAR(u, mine.step(input, 65.0), 1e-12);
    }
}

} // namespace
