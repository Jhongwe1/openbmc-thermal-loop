// SPDX-License-Identifier: Apache-2.0
//
// L0 測試：把「用眼睛看曲線」變成「CI 會檢查的斷言」。
//
// 七個測試分成四類：
//   靜態正確性  SteadyState / MonotonicInPwm / MonotonicInPower
//   動態正確性  DeadTimeDelaysResponse / TimeConstantIsInExpectedRange
//   可信度      DeterminismSameSeedSameTrace（同 seed 逐點相同）
//   ★ 實驗前提  SaturationCaseHolds（測的不是程式，是實驗設計還有沒有效）
#include "plant/thermal_plant.hpp"

#include <algorithm>
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

/**
 * 穩態溫度必須隨功耗單調遞增。
 *
 * 跟上一個測試是同一種防線的另一半：上一個管 Rth 這條路的符號，
 * 這一個管 T_ss = T_amb + P·Rth 裡 P 的符號。
 */
TEST(Plant, MonotonicInPower)
{
    double prev = -1e9;
    for (const double powerW : {50.0, 100.0, 150.0, 250.0, 400.0})
    {
        const double t = settle(60.0, powerW);
        EXPECT_GT(t, prev) << "  power=" << powerW << " 溫度沒有隨功耗上升";
        prev = t;
    }
}

/** 死區視窗內的最大偏移，數位與類比兩條路各量一份。 */
struct DeadWindowDeviation
{
    double digital; ///< step() 回傳值：含雜訊與量化 = **BMC 真的讀到什麼**
    double analog;  ///< sensedAnalog()：不含雜訊與量化 = **物理量本身**
};

/**
 * 在 150 W 穩定後階躍到 400 W，量「階躍後前 nWindow 步」相對階躍前的最大偏移。
 *
 * 抽成函式是為了讓下面的測試能用**同一段實驗**跑兩組參數，
 * 唯一的差別是 deadTime —— 也就是一個單變因 A/B。
 */
DeadWindowDeviation deadWindowDeviation(const PlantParams& p, int nWindow)
{
    ThermalPlant plant(p, /*dt=*/0.1, /*seed=*/0);
    for (int i = 0; i < 6000; ++i) // 先在低功耗穩定
    {
        plant.step(60.0, 150.0);
    }
    const double beforeDigital = plant.step(60.0, 150.0);
    const double beforeAnalog = plant.sensedAnalog();

    DeadWindowDeviation d{0.0, 0.0};
    for (int i = 0; i < nWindow; ++i)
    {
        const double t = plant.step(60.0, 400.0);
        d.digital = std::max(d.digital, std::fabs(t - beforeDigital));
        d.analog =
            std::max(d.analog, std::fabs(plant.sensedAnalog() - beforeAnalog));
    }
    return d;
}

/**
 * 階躍之後的前 θ 秒，感測值應該幾乎不動 —— 死區真的存在。
 *
 * ★ 這個測試有兩個斷言，守的是兩件不同的事。**兩個都不能砍。**
 *
 * ① **純延遲是物理性質**：類比值（無雜訊、無量化）在 θ 內必須幾乎不動。
 *    容差取半個 LSB 的意思是「這點變動連量化器都看不見」——
 *    是一個有物理意義的門檻，不是調到會過為止的數字。
 *    實測 3.18e-06 °C（那是 T_die 還在漸近收斂的殘餘），餘裕約 10000 倍。
 *
 * ② **死區在雜訊下仍然辨認得出來**：用一台 deadTime = 0 的 plant 當對照組，
 *    其餘參數與視窗長度完全相同（單變因），斷言「有死區的偏移 < 對照組的一半」。
 *    實測 0.19 vs 1.06。**這個斷言不需要任何猜出來的容差，也不綁 seed。**
 *
 * ⚠️ 2026-08-07 的教訓（見 LOG.md）：計畫原本寫 `EXPECT_LT(dev, 2 * lsb)`，
 *    紅了。根因不是死區壞掉，是**那個容差只算了量化、忘了雜訊**：
 *    σ = 0.05 的兩個讀值相減 σ√2 ≈ 0.071，28 個樣本取最大約 2.6σ ≈ 0.185，
 *    量化到格點就是 0.1875 —— 與實測分毫不差。
 *    **絕對容差要把每一個誤差來源都算進去；算漏一項，測試就會冤枉被測物。**
 */
TEST(Plant, DeadTimeDelaysResponse)
{
    const PlantParams p;
    const int nWindow = static_cast<int>(p.deadTime / 0.1) - 2; // 留 2 步餘裕

    const DeadWindowDeviation got = deadWindowDeviation(p, nWindow);

    // ① 純延遲：物理量在死區內不該動
    EXPECT_LT(got.analog, 0.5 * p.lsb)
        << "  死區內類比值變動超過半個量化格 —— 純延遲可能沒生效";

    // ② 對照組：唯一的自變因是 deadTime
    //    註：deadTime = 0 時佇列長度會被夾到 1（見 ThermalPlant 建構式），
    //    所以對照組仍有 1 個 dt 的延遲。那是這份實作能表達的「最短死區」。
    PlantParams noDeadTime = p;
    noDeadTime.deadTime = 0.0;
    const DeadWindowDeviation control = deadWindowDeviation(noDeadTime, nWindow);

    EXPECT_LT(got.digital, 0.5 * control.digital)
        << "  有死區與沒死區量到的偏移差不多 —— 死區沒有讓響應延後"
        << "\n  有死區 = " << got.digital << "，對照組 = " << control.digital;
}

/**
 * 到達 63.2% 的時間要落在 (θ, θ + τ_die + τ_sense + 餘裕) 之間。
 *
 * 抓的是一階離散化寫反（dt/tau 寫成 tau/dt）與步驟順序寫反。
 */
TEST(Plant, TimeConstantIsInExpectedRange)
{
    PlantParams p;
    ThermalPlant plant(p, /*dt=*/0.1, /*seed=*/0);

    for (int i = 0; i < 12000; ++i) // 到穩態
    {
        plant.step(60.0, 150.0);
    }
    const double t0 = plant.step(60.0, 150.0);
    const double tFinal = settle(60.0, 400.0);
    const double target = t0 + 0.632 * (tFinal - t0);

    int steps = 0;
    while (plant.step(60.0, 400.0) < target && steps < 20000)
    {
        ++steps;
    }
    const double t63 = steps * 0.1;

    EXPECT_GT(t63, p.deadTime);
    EXPECT_LT(t63, p.deadTime + p.tauDie + p.tauSense + 20.0);
}

/**
 * 同一個 seed 跑兩次，必須逐點完全相同。
 *
 * ★ 這條守的是「別人 clone 我的 repo 跑一次，會得到跟我一模一樣的圖」。
 *   最常見的破法是把 rng 寫成 static 或全域的 —— 那樣兩個 plant 會共用亂數流。
 */
TEST(Plant, DeterminismSameSeedSameTrace)
{
    PlantParams p;
    ThermalPlant a(p, 0.1, /*seed=*/42);
    ThermalPlant b(p, 0.1, /*seed=*/42);
    for (int i = 0; i < 5000; ++i)
    {
        ASSERT_DOUBLE_EQ(a.step(55.0, 200.0), b.step(55.0, 200.0))
            << "  step " << i;
    }
}

/**
 * ★ 這個測試測的不是程式，是「我的實驗設計有沒有製造出飽和」。
 *
 * 如果 pwm=100 且 P=400 時穩態溫度仍然高於 setpoint，
 * 代表控制器即使全速也降不下來 —— 這正是 windup 的必要條件。
 * 沒有這個條件，Fig 3 的 A/B 兩條線會一模一樣。
 */
TEST(Plant, SaturationCaseHolds)
{
    constexpr double kSetpoint = 65.0;
    const double t = settle(/*pwm=*/100.0, /*powerW=*/400.0);
    EXPECT_GT(t, kSetpoint)
        << "  全速仍降不到 setpoint 是 Fig 3 的實驗前提，"
           "此處不成立則 anti-windup 實驗無效";
}

} // namespace
