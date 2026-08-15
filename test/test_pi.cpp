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

// ═══════════════════════════════════════════════════════════════════════
//  取樣週期 ts —— 這三條是 2026-08-09 稽核補的
//
//  在此之前**每一個測試的 ts 都是 1.0**，於是所有乘上或除以 ts 的算術
//  完全沒有被測到（乘 1 跟不乘看起來一樣）。實測植入四個「忘了乘 ts」的錯，
//  四個全部活下來。
//
//  ts = 0.1 不是隨便挑的：那是 config/swampd/config.baseline.json 裡
//  風扇 PID 的 samplePeriod ——「repo 自己在用的那個值從來沒被驗過」。
//
//  ⚠️ 每一條都要用**手算得出來的**期望值，不能寫「跟另一個實作比」——
//     兩邊都忘了乘 ts 的話那種測試會是綠的。
// ═══════════════════════════════════════════════════════════════════════

/// 積分是 `ki · e · ts`，不是 `ki · e`。
TEST(Pi, IntegralScalesWithTheSamplePeriod)
{
    PiParams p = basic();
    p.kp = 0.0;
    p.ki = 2.0;
    p.ts = 0.1;
    p.outMax = 1e6;

    Pi pi(p);
    for (int i = 0; i < 10; ++i)
    {
        pi.step(0.0, 5.0); // error = +5 每一輪
    }
    // 10 輪 × 5 × 2.0 × 0.1 = 10.0。忘了乘 ts 的話會是 100.0。
    EXPECT_DOUBLE_EQ(pi.integral(), 10.0);
}

/// slew 的單位是「**每秒**最多變化多少」，不是「每步」，所以要乘 ts。
///
/// 這一條很容易寫錯，而且寫錯之後 ts = 1.0 的測試全部照樣綠 ——
/// 錯誤只在取樣週期不是一秒時才顯現，而風扇迴路正好是 0.1 s。
///
/// ⚠️ **上升與下降是兩個獨立的欄位（slewPos / slewNeg），要分別測。**
///    我第一版只測了 slewPos，`mutation_check.sh` 的 C10（slewNeg 不乘 ts）
///    當場活下來 —— 一個只驗一半的測試，看起來跟驗完整一樣綠。
TEST(Pi, SlewRateIsPerSecondNotPerStep)
{
    PiParams p = basic();
    p.kp = 100.0;
    p.ki = 0.0;
    p.ts = 0.1;
    p.slewPos = 5.0;
    p.slewNeg = -5.0;
    p.outMin = -1e6;
    p.outMax = 1e6;

    Pi up(p);
    EXPECT_DOUBLE_EQ(up.step(9.0, 10.0), 100.0); // 第一輪不受 slew 限
    // 未限速會是 1000；每秒最多 +5、這一步只有 0.1 s → 最多 +0.5。
    EXPECT_DOUBLE_EQ(up.step(0.0, 10.0), 100.5);

    Pi down(p);
    EXPECT_DOUBLE_EQ(down.step(0.0, 10.0), 1000.0); // 第一輪
    // 未限速會掉到 0；每秒最多 −5、這一步 0.1 s → 最多 −0.5。
    EXPECT_DOUBLE_EQ(down.step(10.0, 10.0), 999.5);
}

/// D 項算的是**變化率**：`(e − e_prev) / ts`，所以 ts 在分母。
///
/// ⚠️ 少了這個除法，D 項的量綱會從「每秒」變成「每步」——
///    取樣越密 D 項越弱，剛好與物理相反。
TEST(Pi, DerivativeIsARateSoTheSamplePeriodDivides)
{
    PiParams p = basic();
    p.kp = 0.0;
    p.ki = 0.0;
    p.kd = 2.0;
    p.ts = 0.5;
    p.outMin = -1e6;
    p.outMax = 1e6;

    Pi pi(p);
    pi.step(10.0, 10.0); // error = 0，先建立 lastError_
    // error 從 0 跳到 +4：dTerm = 2.0 × 4 / 0.5 = 16。不除 ts 的話是 8。
    EXPECT_DOUBLE_EQ(pi.step(6.0, 10.0), 16.0);
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

/// ★ 追蹤時間常數 Tt：它決定積分被拉回來的**速度**。
///
/// 這一條存在的理由是「`BackCalculation` 這個名字要名副其實」。
/// W5 的實作只有 Tt = ts 那一個特例，而且是**隱含**的 —— 沒有參數、
/// 沒有文件 —— 讀這段程式的人看不出 Tt 是多少，也沒有旋鈕可以改它。
///
/// 兩個斷言各自釘住一件事：
///   · `Tt = ts`（預設）要**完全等於** W5 的舊行為 `out − pTerm − dTerm − ffTerm`
///   · `Tt` 變大，飽和時累積的積分要**明顯變多**（拉得慢）
TEST(Pi, TrackingTimeConstantSetsHowFastTheIntegralIsPulledBack)
{
    auto integralAfterSaturating = [](double trackingTimeS) {
        PiParams p = basic();
        p.antiWindup = AntiWindup::BackCalculation;
        p.trackingTimeS = trackingTimeS;
        Pi pi(p);
        // 100 輪：Tt = 10·ts 那一組是幾何收斂，公比 0.9，
        // 100 輪之後殘差 0.9^100 ≈ 3e-5 —— 遠小於下面的容差。
        for (int i = 0; i < 100; ++i)
        {
            pi.step(0.0, 10.0); // error = +10，輸出很快就頂到 outMax = 50
        }
        return pi.integral();
    };

    // Tt = ts：一步拉回。穩態積分 = outMax − kp·e = 50 − 1×10 = 40。
    // ★ 這個 40 是手算的，不是跑出來抄的 —— 它同時證明預設值沒有改變舊行為。
    const double fast = integralAfterSaturating(0.0);
    EXPECT_DOUBLE_EQ(fast, 40.0);

    // Tt = 10·ts：每一步只拉回十分之一，所以積分會爬到高得多的地方才平衡。
    //
    //   遞迴式（飽和之後）：I' = I + ki·e·ts + (outMax − (kp·e + I + ki·e·ts))·ts/Tt
    //                          = I + 10 + (50 − (10 + I + 10))/10
    //                          = 0.9·I + 13
    //   不動點：I = 0.9·I + 13  ->  I* = **130**
    //
    // ⚠️ 我第一版把不動點寫成 140 —— 那是 I_cand（累加後、回算前）的值，
    //    不是**存下來**的積分。測試紅了才發現，而且它紅得很有用：
    //    如果我當時把容差放寬到 ±15 讓它過，這條測試就再也分不出
    //    「Tt 有生效」與「Tt 差一步」。
    const double slow = integralAfterSaturating(10.0);
    EXPECT_NEAR(slow, 130.0, 0.01);
    EXPECT_GT(slow, fast);
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
