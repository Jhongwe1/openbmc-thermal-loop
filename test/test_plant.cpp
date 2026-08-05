// SPDX-License-Identifier: Apache-2.0
//
// L0 測試：把「用眼睛看曲線」變成「CI 會檢查的斷言」。
//
// 本週兩個，W4 補到七個（MonotonicInPower / DeadTime / TimeConstant /
// Determinism / SaturationCaseHolds）。
#include "plant/thermal_plant.hpp"

#include <cmath>

#include <gtest/gtest.h>

namespace
{

using thermal::PlantParams;
using thermal::ThermalPlant;

/** 跑到穩態，回傳最後 100 步（10 s）的平均感測溫度。 */
double settle(double pwm, double powerW, const PlantParams& p = {},
              double dt = 0.1, double seconds = 600.0)
{
    ThermalPlant plant(p, dt, /*seed=*/0);
    const int n = static_cast<int>(seconds / dt);
    double acc = 0.0;
    for (int i = 0; i < n; ++i)
    {
        const double t = plant.step(pwm, powerW);
        if (i >= n - 100)
        {
            acc += t;
        }
    }
    return acc / 100.0;
}

/**
 * 解析穩態值：T = T_amb + P·Rth(pwm)。
 *
 * ⚠️ 這個函式**複製了** step() 裡的熱阻公式。
 *    如果兩邊同時寫錯同一個地方，這個測試會通過而錯誤不會被抓到。
 *    這是它的已知弱點 —— 所以下面第二個測試（MonotonicInPwm）
 *    刻意**不用**這個函式：它只斷言「方向對不對」，
 *    是完全獨立的一道防線。
 */
double analytic(double pwm, double powerW, const PlantParams& p = {})
{
    const double q = (pwm < p.pwmMinSpin) ? 0.0 : pwm / 100.0;
    const double rth =
        p.rthMin + (p.rthMax - p.rthMin) * (1.0 - std::pow(q, p.flowExp));
    return p.tAmb + powerW * rth;
}

/**
 * 穩態溫度要符合 T_amb + P·Rth(pwm)。
 *
 * 容差 0.1 °C 的來歷（不是隨便填的）：
 *   量化 LSB 0.0625 → 單點誤差 ≤ 0.031
 *   雜訊 σ 0.05，平均 100 點 → 0.005
 *   600 s / τ_die 45 s ≈ 13 個時間常數 → 收斂殘差可忽略
 * 三項相加約 0.04，取 0.1 留一倍餘裕。
 * **容差要能說出來歷，否則它只是「調到會過為止」。**
 */
TEST(Plant, SteadyStateMatchesAnalytic)
{
    for (const double pwm : {0.0, 30.0, 60.0, 100.0})
    {
        const double got = settle(pwm, 150.0);
        const double want = analytic(pwm, 150.0);
        EXPECT_NEAR(got, want, 0.1) << "  pwm=" << pwm;
    }
}

/**
 * 穩態溫度必須隨 PWM 單調遞減。
 *
 * ★ 這是抓「符號錯誤」的第一道防線。
 *   W5 調 PID 係數時如果曲線跑反了，你會問「是 plant 寫反了還是係數反了？」
 *   —— 這個測試是綠的，就能一秒排除 plant，把搜尋範圍砍半。
 */
TEST(Plant, MonotonicInPwm)
{
    double prev = 1e9;
    for (const double pwm : {0.0, 20.0, 40.0, 60.0, 80.0, 100.0})
    {
        const double t = settle(pwm, 150.0);
        EXPECT_LT(t, prev) << "  pwm=" << pwm << " 溫度沒有隨轉速上升而下降";
        prev = t;
    }
}

} // namespace
