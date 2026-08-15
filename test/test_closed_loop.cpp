// SPDX-License-Identifier: Apache-2.0
//
// 把 controller/ 與 plant/ 接起來的**閉環**測試。
//
// ★ 為什麼一定要有這一支（2026-08-09 補）
//
//   在此之前，controller/ 只被證明了一件事：「它的算術跟上游 ec::pid() 一樣」。
//   **那不等於「它是一個能收斂的控制器」。** 兩個實作可以逐位元一致地一起錯。
//   `grep ThermalPlant test/` 在此之前完全不命中 controller —— 也就是說
//   這個專案有一個 plant、有一個 controller，卻沒有任何測試把它們接起來過。
//
//   更諷刺的是：W5 花了兩分鐘在真的 BMC 上量出「係數符號要是負的」
//   （exp02，見 docs/measurement.md），而**程式碼這一側沒有任何測試在守它**。
//   PositiveGainRunsAway 就是那個實驗的程式碼版本。
//
// ★ 這一支測的是「行為」，不是「數值」
//   斷言全部寫成**不等式與方向**（會不會收斂、誰比誰快），不是
//   「第 300 秒應該是 64.87 °C」。後者會把 plant 的實作細節焊死在測試裡，
//   改一個 seed 或一個參數就假性失敗，然後大家開始改容差。
//
// ⚠️ 容差一律要說得出來歷（σ、LSB、收斂殘差），不可以「調到會過為止」。
//    這是 W4 D1 學到的教訓，見 LOG.md 2026-08-07。
#include "controller/pi.hpp"
#include "plant/thermal_plant.hpp"

#include <gtest/gtest.h>

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <numeric>
#include <vector>

namespace
{

using control::AntiWindup;
using control::Pi;
using control::PiParams;

/// plant 的離散步長。要遠小於最快的時間常數 tauFan = 1.5 s。
constexpr double kPlantDt = 0.1;

/// 量測雜訊底：σ 與量化誤差獨立，所以平方相加開根號。
/// 量化的 RMS 是 LSB/√12（均勻分布在 ±半個 LSB 之間的標準差）。
/// 這個數字是**推導出來的**，不是量出來的 —— 它是所有容差的來源。
double noiseFloor(const thermal::PlantParams& p)
{
    return std::hypot(p.noiseSigma, p.lsb / std::sqrt(12.0));
}

struct Schedule
{
    double powerBase = 150.0;
    double powerStep = 150.0;
    double stepAtS = -1.0;    ///< 負數 = 不階躍
    double releaseAtS = -1.0; ///< 負數 = 不回復
};

struct Trace
{
    std::vector<double> t;
    std::vector<double> sensed;
    std::vector<double> pwm;

    /// 最後 window_s 秒的平均感測溫度。
    double tailMean(double windowS) const
    {
        const double tEnd = t.back();
        double sum = 0.0;
        std::size_t n = 0;
        for (std::size_t i = 0; i < t.size(); ++i)
        {
            if (t[i] >= tEnd - windowS)
            {
                sum += sensed[i];
                ++n;
            }
        }
        return sum / static_cast<double>(n);
    }
};

/// 跑一次閉環。控制器每 `pp.ts` 秒動一次，plant 每 kPlantDt 秒動一次 ——
/// 這個比例本身就是 swampd 的樣子（溫度迴路 1 Hz，plant 連續在變）。
Trace runClosedLoop(const PiParams& pp, const Schedule& sched, double seconds,
                    double setpoint, unsigned seed = 0)
{
    const thermal::PlantParams plantParams; // 預設值 = docs/plant-model.md 參數表
    thermal::ThermalPlant plant(plantParams, kPlantDt, seed);
    Pi pi(pp);

    Trace out;
    double pwm = 0.0;
    double sensed = plantParams.tAmb;
    const int stepsPerControl =
        std::max(1, static_cast<int>(std::lround(pp.ts / kPlantDt)));
    const int n = static_cast<int>(seconds / kPlantDt);

    for (int i = 0; i < n; ++i)
    {
        const double t = i * kPlantDt;
        if (i % stepsPerControl == 0)
        {
            pwm = pi.step(sensed, setpoint);
        }
        double power = sched.powerBase;
        if (sched.stepAtS >= 0.0 && t >= sched.stepAtS)
        {
            power = sched.powerStep;
        }
        if (sched.releaseAtS >= 0.0 && t >= sched.releaseAtS)
        {
            power = sched.powerBase;
        }
        sensed = plant.step(pwm, power);
        out.t.push_back(t);
        out.sensed.push_back(sensed);
        out.pwm.push_back(pwm);
    }
    return out;
}

/// W4 量到的 FOPDT（K = −0.3147 °C/%PWM、τ = 43.97 s、θ = 7.20 s）
/// 用 SIMC/lambda 整定出來的一組係數。λ 取 θ（中等激進）：
///     Kc = τ / (K·(λ+θ)) = 43.97 / (−0.3147 × 14.4) ≈ −9.7
///     Ti = min(τ, 4(λ+θ)) = 44        ->  ki = Kc/Ti ≈ −0.22
///
/// ⚠️ **這不是 W6 的整定結果**，W6 才會正式做 λ 掃描並產出 Fig 2。
///    這裡只需要「一組講得出來歷、而且會收斂」的係數，
///    好讓閉環行為有東西可以測。隨手填的係數會讓失敗的原因變成兩種。
PiParams tunedForCooling()
{
    PiParams p;
    p.kp = -9.7; // ★ 負的 —— exp02 在真的 BMC 上量過（docs/measurement.md）
    p.ki = -0.22;
    p.ts = 1.0;
    p.outMin = 0.0;
    p.outMax = 100.0;
    p.integralMin = -400.0;
    p.integralMax = 400.0;
    p.antiWindup = AntiWindup::Clamp;
    return p;
}

// ═══════════════════════════════════════════════════════════════════════

/// ★ 這個閉環真的會收斂到 setpoint。
///
/// 容差的來歷（不是調出來的）：
///   雜訊底 = √(σ² + (LSB/√12)²) = √(0.05² + 0.0625²/12) = 0.0532 °C
///   取最後 120 秒的平均之後，隨機成分被平均掉大半；
///   剩下的是量化格點與殘餘極限環，所以留 **3 個雜訊底** 的餘裕。
TEST(ClosedLoop, ConvergesToSetpointWithNegativeGain)
{
    const thermal::PlantParams plantParams;
    const double setpoint = 65.0;
    const Trace trace = runClosedLoop(tunedForCooling(), Schedule{}, 900.0,
                                      setpoint);

    const double tolerance = 3.0 * noiseFloor(plantParams);
    const double steady = trace.tailMean(120.0);

    EXPECT_NEAR(steady, setpoint, tolerance)
        << "穩態誤差 " << (steady - setpoint) << " °C，容差 " << tolerance;

    // 前提斷言：控制量真的落在**可調範圍內**，不是靠撞到邊界才停住的。
    // 沒有這一條，一個永遠輸出 0% 的控制器也可能「剛好」讓溫度接近 setpoint。
    const double finalPwm = trace.pwm.back();
    EXPECT_GT(finalPwm, plantParams.pwmMinSpin)
        << "風扇停在起轉門檻以下，這不是閉環控制的結果";
    EXPECT_LT(finalPwm, 100.0) << "輸出貼在上限，代表這個工作點根本達不到";
}

/// ★★ 符號檢查的程式碼版本 —— exp02 在真的 BMC 上量到的那件事。
///
/// `ec::pid()` 的誤差是 `setpoint − input`。input 是**絕對溫度**時，
/// 把係數的符號弄反，等於把整條迴路從負回饋變成**正回饋**。
///
/// ⚠️ **我第一版把症狀寫錯了，測試紅了才發現。**
///    我以為「正係數 = 越熱輸出越低 = 風扇停掉 = 溫度飆高」。
///    實測是**風扇衝到 100% 並鎖死，溫度停在 43 °C —— 比目標低 22 度**。
///
///    根因是「正回饋會往起始誤差的那一邊鎖死」，所以**落到哪一個極限
///    取決於初始條件**：
///      · 起點比 setpoint 冷 → error > 0 → 輸出衝上限 → 更冷 → 鎖在 100 %
///      · 起點比 setpoint 熱 → error < 0 → 輸出撞下限 → 更熱 → 鎖在 0 %
///    兩個都是穩定的鎖死狀態。這個測試把**兩個分支都測出來**。
///
/// ★ 這才是符號錯真正的樣子，而且比我原本以為的更難發現：
///   「風扇 100 %、溫度 43 °C」在監控畫面上看起來**完全健康** ——
///   沒有過溫告警、沒有 failsafe，只是**永遠全速在燒電**。
///   exp02 在 BMC 上量到的兩個點裡也各有一個停在 `outLim_min`，
///   **只看單一個點分不出符號對錯** —— 這正是那個實驗要用兩個點的原因。
TEST(ClosedLoop, WrongSignLatchesAtALimitInsteadOfControlling)
{
    PiParams wrongSign = tunedForCooling();
    wrongSign.kp = -wrongSign.kp; // +9.7
    wrongSign.ki = -wrongSign.ki; // +0.22

    // ── 分支 A：起點（tAmb = 25 °C）比 setpoint 冷 ──────────────────
    {
        const double setpoint = 65.0;
        const Trace trace = runClosedLoop(wrongSign, Schedule{}, 900.0,
                                          setpoint);
        EXPECT_DOUBLE_EQ(trace.pwm.back(), wrongSign.outMax)
            << "起點在 setpoint 之下時，正回饋應該把輸出鎖在**上限**";
        // 100 % 風扇、150 W 的穩態是 25 + 150×0.12 = 43 °C。
        EXPECT_LT(trace.tailMean(120.0), setpoint - 15.0)
            << "鎖在全速之後溫度應該遠**低於** setpoint（一直在浪費風扇功耗）";
    }

    // ── 分支 B：setpoint 低於這個工作點做得到的最低溫（43 °C）───────
    //   於是溫度一定會爬到 setpoint 之上，誤差翻負，鎖在**下限**。
    {
        const double setpoint = 30.0;
        const Trace trace = runClosedLoop(wrongSign, Schedule{}, 900.0,
                                          setpoint);
        EXPECT_DOUBLE_EQ(trace.pwm.back(), wrongSign.outMin)
            << "誤差翻負之後，正回饋應該把輸出鎖在**下限**（風扇停掉）";
        // 0 RPM、150 W 的開環穩態是 25 + 150×0.35 = 77.5 °C。
        EXPECT_GT(trace.tailMean(120.0), 70.0)
            << "風扇停掉之後溫度應該爬到自然對流的穩態";
    }

    // ── 對照組：同一個 plant、同一組 |係數|，符號正確就收斂 ─────────
    //   沒有這一條，上面的失敗也可能是「這個 plant 根本控不動」造成的。
    const Trace ok = runClosedLoop(tunedForCooling(), Schedule{}, 900.0, 65.0);
    EXPECT_LT(std::fabs(ok.tailMean(120.0) - 65.0), 1.0)
        << "對照組沒收斂 —— 那上面那些失敗就不能歸因於符號";
}

/// ★ 抗飽和真的有用：飽和解除之後，`None` 花更多輪才離開上限。
///
/// 製造飽和的方式與 docs/plant-model.md §2 的設計一致：
/// 功耗階躍到 400 W，此時**即使風扇滿速**穩態也是 73 °C > setpoint 65 ——
/// 誤差持續為正，積分持續累加。然後把功耗放回 150 W 解除飽和。
///
/// 這正是 Fig 3（W7 核心實驗）要量的那個過程，只是這裡在 L1 上、用不等式斷言。
TEST(ClosedLoop, AntiWindupRecoversFasterThanNone)
{
    const Schedule saturating{150.0, 400.0, 200.0, 600.0};
    const double setpoint = 65.0;

    auto stepsAboveCeilingAfterRelease = [&](AntiWindup mode) {
        PiParams p = tunedForCooling();
        p.antiWindup = mode;
        const Trace trace = runClosedLoop(p, saturating, 1400.0, setpoint);

        int held = 0;
        for (std::size_t i = 0; i < trace.t.size(); ++i)
        {
            if (trace.t[i] >= saturating.releaseAtS && trace.pwm[i] >= 99.999)
            {
                ++held;
            }
        }
        return held;
    };

    const int none = stepsAboveCeilingAfterRelease(AntiWindup::None);
    const int clamped = stepsAboveCeilingAfterRelease(AntiWindup::Clamp);
    const int backCalc =
        stepsAboveCeilingAfterRelease(AntiWindup::BackCalculation);

    // 前提：這個劇本真的把輸出推到上限了。不製造飽和的實驗等於沒做。
    ASSERT_GT(none, 0) << "沒有飽和 —— 這個劇本量不到 anti-windup 的效果";

    EXPECT_GT(none, clamped)
        << "沒有抗飽和的那一版應該卡在上限更久  none=" << none
        << "  clamp=" << clamped;
    EXPECT_GT(none, backCalc)
        << "沒有抗飽和的那一版應該卡在上限更久  none=" << none
        << "  backcalc=" << backCalc;
}

/// 決定性：同一組參數、同一個 seed，兩次跑出來要**逐點相同**。
/// 沒有這一條，上面三個測試的「差異」可能只是亂數。
TEST(ClosedLoop, SameSeedGivesTheSameTrajectory)
{
    const Trace a = runClosedLoop(tunedForCooling(), Schedule{}, 300.0, 65.0, 7);
    const Trace b = runClosedLoop(tunedForCooling(), Schedule{}, 300.0, 65.0, 7);
    ASSERT_EQ(a.sensed.size(), b.sensed.size());
    for (std::size_t i = 0; i < a.sensed.size(); ++i)
    {
        ASSERT_DOUBLE_EQ(a.sensed[i], b.sensed[i]) << "第 " << i << " 步就不同了";
        ASSERT_DOUBLE_EQ(a.pwm[i], b.pwm[i]);
    }
}

} // namespace
