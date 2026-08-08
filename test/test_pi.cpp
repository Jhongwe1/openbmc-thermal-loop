// SPDX-License-Identifier: Apache-2.0
//
// controller/pi.cpp 的 L0 測試。
//
// 這一組測試的目標不是「PI 會不會動」，是「四種抗飽和策略各自真的在做它宣稱
// 的事」。特別是 AntiWindup::None —— 它存在的唯一理由就是當對照組，所以
// 一定要有一個測試證明**它真的會 windup**。沒有那個測試，其他三種「解決了
// windup」的說法就沒有被比較的對象。
#include "controller/pi.hpp"

#include <gtest/gtest.h>

#include <vector>

namespace
{

using control::AntiWindup;
using control::Pi;
using control::PiParams;

PiParams basic()
{
    PiParams p;
    p.kp = 1.0;
    p.ki = 1.0;
    p.ts = 1.0;
    p.outMin = 0.0;
    p.outMax = 50.0;
    p.integralMin = -1e9;
    p.integralMax = 1e9;
    p.antiWindup = AntiWindup::Clamp;
    return p;
}

/// 誤差為 0 時，輸出就只剩前饋項。
/// 這條同時釘住了前饋的定義：(setpoint + offset) * gain，而不是 setpoint * gain。
TEST(Pi, ZeroErrorLeavesOnlyTheFeedForwardTerm)
{
    PiParams p = basic();
    p.kp = 3.0;
    p.ki = 0.0;
    p.feedFwdOffset = 5.0;
    p.feedFwdGain = 0.4;
    p.outMax = 1e6;

    Pi pi(p);
    EXPECT_DOUBLE_EQ(pi.step(50.0, 50.0), (50.0 + 5.0) * 0.4);
}

/// ① 積分箝位：長時間同號誤差之後，積分項停在 integralMax，不會繼續長。
TEST(Pi, ClampCapsTheIntegral)
{
    PiParams p = basic();
    p.kp = 0.0;
    p.integralMax = 10.0;
    p.outMax = 1e6; // 刻意不讓輸出箝位，才確定測到的是積分箝位

    Pi pi(p);
    for (int i = 0; i < 20; ++i)
    {
        pi.step(0.0, 5.0); // error = +5 每一輪
    }
    EXPECT_DOUBLE_EQ(pi.integral(), 10.0);
}

/// slew：第一輪不受限（沒有 lastOutput 可以比），第二輪起每輪最多變化
/// slewPos * ts。這個「第一輪不受限」的語意是照抄上游的。
TEST(Pi, SlewLimitsTheStepChange)
{
    PiParams p = basic();
    p.kp = 100.0;
    p.ki = 0.0;
    p.slewPos = 5.0;
    p.outMax = 1e6;

    Pi pi(p);
    EXPECT_DOUBLE_EQ(pi.step(9.0, 10.0), 100.0); // error = 1，第一輪不受 slew 限
    EXPECT_DOUBLE_EQ(pi.step(0.0, 10.0), 105.0); // 未限速會是 1000，被壓到 +5
}

/// ★ 對照組：沒有任何抗飽和處理時，積分真的會爆掉，而且解除飽和之後
///   要花明顯更多輪才降得下來。
///
/// 這個測試在量的是「windup 的代價」，不是「輸出對不對」。
TEST(Pi, WithoutAntiWindupTheIntegralBlowsUpAndRecoveryIsSlower)
{
    PiParams none = basic();
    none.antiWindup = AntiWindup::None;
    PiParams clamped = basic();
    // ★ 這個 60 是有算過的，不是隨便填的。
    //   kp = 1、error = +10 時 pTerm = 10，所以積分上限必須 > outMax - 10 = 40，
    //   箝位後的輸出才**仍然會飽和**。第一次寫成 20，輸出停在 30 —— 兩邊
    //   根本沒有進入飽和，整個實驗在量一件沒發生的事。
    //   抓到它的是下面那兩行「前提斷言」，不是主斷言。
    clamped.integralMax = 60.0;

    Pi a(none);
    Pi b(clamped);

    // 20 輪正誤差：兩邊都會頂到 outMax = 50
    for (int i = 0; i < 20; ++i)
    {
        a.step(0.0, 10.0);
        b.step(0.0, 10.0);
    }
    EXPECT_DOUBLE_EQ(a.lastOutput(), 50.0);
    EXPECT_DOUBLE_EQ(b.lastOutput(), 50.0);

    // 積分的差距就是 windup 的量
    EXPECT_GT(a.integral(), 100.0);
    EXPECT_DOUBLE_EQ(b.integral(), 60.0);

    // 誤差反號之後，要幾輪才離開上限？
    auto stepsToLeaveCeiling = [](Pi& pi) {
        for (int i = 1; i <= 500; ++i)
        {
            if (pi.step(20.0, 10.0) < 50.0) // error = -10
            {
                return i;
            }
        }
        return 0;
    };
    const int slow = stepsToLeaveCeiling(a);
    const int fast = stepsToLeaveCeiling(b);

    EXPECT_GT(slow, 0);
    EXPECT_GT(fast, 0);
    EXPECT_GT(slow, fast) << "沒有抗飽和的那一版應該慢很多，slow=" << slow
                          << " fast=" << fast;
}

/// ② 條件積分：積分會停在一個高原，不再成長。
///
/// ⚠️ 不能斷言「只要 lastOutput 到達 outMax 就不准累加」。輸出**剛好等於**上限
///    的那一輪，未箝位值並沒有超出範圍 —— 那代表控制器正好用滿，不是飽和，
///    這一步的累加是合法的。我第一版就是這樣寫的，測試紅在第 4 輪。
///    差別在「unsat > outMax」與「out == outMax」，一個字之差。
TEST(Pi, ConditionalIntegralReachesAPlateau)
{
    PiParams cond = basic();
    cond.antiWindup = AntiWindup::Conditional;
    PiParams none = basic();
    none.antiWindup = AntiWindup::None;

    Pi pi(cond);
    Pi unbounded(none);

    std::vector<double> trajectory;
    for (int i = 0; i < 30; ++i)
    {
        pi.step(0.0, 10.0); // error = +10 每一輪
        unbounded.step(0.0, 10.0);
        trajectory.push_back(pi.integral());
    }

    // 前提：這個參數組合真的把輸出推到上限了
    ASSERT_DOUBLE_EQ(pi.lastOutput(), cond.outMax);

    // 後 20 輪的積分應該完全不動 —— 那就是「條件積分生效」的樣子
    for (size_t i = trajectory.size() - 20; i < trajectory.size(); ++i)
    {
        EXPECT_DOUBLE_EQ(trajectory[i], trajectory.back())
            << "第 " << i << " 輪的積分還在動";
    }

    // 而沒有任何處理的那一版，同樣 30 輪之後積分是它的好幾倍
    EXPECT_GT(unbounded.integral(), 5.0 * pi.integral());
}

/// ③ 標準回算的自我一致性：沒有飽和的時候，回算應該是**空操作**
///   —— 因為 out - pTerm - dTerm - ffTerm 剛好就是那一輪的積分。
///
/// 這條測試的價值在於：它會抓到「我在回算裡少扣了某一項」這種錯。
/// 少扣一項的話，未飽和時兩者就會分家，而那是不該發生的。
TEST(Pi, BackCalculationIsANoOpWhileUnsaturated)
{
    PiParams bc = basic();
    bc.antiWindup = AntiWindup::BackCalculation;
    bc.feedFwdGain = 0.3;
    bc.feedFwdOffset = 2.0;
    bc.kd = 0.5;
    bc.outMax = 1e6; // 不飽和

    PiParams cl = bc;
    cl.antiWindup = AntiWindup::Clamp;

    Pi a(bc);
    Pi b(cl);
    for (double input : {9.0, 8.0, 7.5, 9.5, 10.0, 10.5})
    {
        EXPECT_NEAR(a.step(input, 10.0), b.step(input, 10.0), 1e-12);
        EXPECT_NEAR(a.integral(), b.integral(), 1e-12);
    }
}

/// reset() 要真的把狀態清乾淨，包含「第一輪」旗標 —— 否則重置後的第一步
/// 會被 slew 限制住，而它沒有可以參考的 lastOutput。
TEST(Pi, ResetRestoresTheFirstStepSemantics)
{
    PiParams p = basic();
    p.kp = 100.0;
    p.ki = 0.0;
    p.slewPos = 5.0;
    p.outMax = 1e6;

    Pi pi(p);
    pi.step(9.0, 10.0);
    pi.step(0.0, 10.0);
    pi.reset();

    EXPECT_DOUBLE_EQ(pi.integral(), 0.0);
    EXPECT_DOUBLE_EQ(pi.lastOutput(), 0.0);
    EXPECT_DOUBLE_EQ(pi.step(0.0, 10.0), 1000.0); // 又是「第一輪」，不受 slew 限
}

} // namespace
