// SPDX-License-Identifier: Apache-2.0
//
// L0 測試：兩點法識別。
//
// ★ 這一組測試的價值在於「我知道正確答案」。
//   真實系統上你永遠不知道真正的 tau 與 theta 是多少，所以無從驗證識別方法。
//   在自己寫的 plant 上，正確答案就寫在 PlantParams 裡 ——
//   **先在知道答案的系統上驗方法，再把方法拿去用在不知道答案的系統上。**
#include "plant/identify.hpp"
#include "plant/thermal_plant.hpp"

#include <algorithm>
#include <cmath>
#include <vector>

#include <gtest/gtest.h>

namespace
{

using thermal::Fopdt;
using thermal::PlantParams;
using thermal::ThermalPlant;

struct Trace
{
    std::vector<double> t;
    std::vector<double> y;
    double stepAtS = 0.0;
};

/**
 * 產生一條開環 PWM 階躍響應：先在 pwmA 穩定，再階躍到 pwmB。
 *
 * @param settleS  階躍前先跑多久（不記錄）
 * @param preS     階躍前記錄多久（給基準值取平均用）
 * @param postS    階躍後記錄多久
 */
Trace makeStepTrace(const PlantParams& p, double pwmA, double pwmB,
                    double powerW, unsigned seed = 0, double dt = 0.1,
                    double settleS = 200.0, double preS = 200.0,
                    double postS = 600.0)
{
    ThermalPlant plant(p, dt, seed);
    Trace tr;

    const int nSettle = static_cast<int>(settleS / dt);
    for (int i = 0; i < nSettle; ++i)
    {
        plant.step(pwmA, powerW);
    }

    const int nPre = static_cast<int>(preS / dt);
    for (int i = 0; i < nPre; ++i)
    {
        tr.t.push_back(static_cast<double>(i) * dt);
        tr.y.push_back(plant.step(pwmA, powerW));
    }

    tr.stepAtS = tr.t.back() + dt;
    const int nPost = static_cast<int>(postS / dt);
    for (int i = 0; i < nPost; ++i)
    {
        tr.t.push_back(tr.stepAtS + static_cast<double>(i) * dt);
        tr.y.push_back(plant.step(pwmB, powerW));
    }
    return tr;
}

/**
 * 在已知答案的 plant 上，識別出來的 K/tau/theta 要落在合理範圍。
 *
 * 這裡把雜訊關掉、量化調細，是為了讓斷言測的是**方法本身**。
 * 雜訊下的表現由 SurvivesNoiseAndQuantisation 那一條負責。
 */
TEST(Identify, RecoversKnownTimeConstants)
{
    PlantParams p;
    p.noiseSigma = 0.0;
    p.lsb = 0.01;

    const Trace tr = makeStepTrace(p, 40.0, 60.0, 150.0);
    const Fopdt f = thermal::identifyTwoPoint(tr.t, tr.y, tr.stepAtS, 20.0);

    // ⚠️ 這一行是符號檢查的第一道防線。
    //    W5 地雷 #9（PID 係數符號搞反）的根源就是「K 是負的」這件事。
    //    風扇轉快 → 溫度降 → ΔT/ΔPWM < 0。今天先在測試裡把它釘住。
    EXPECT_LT(f.k, 0.0) << "  風扇越快溫度越低，K 必須為負";

    // tau 應該落在 tau_die 與 (tau_die + tau_sense) 的量級。
    // 不能要求剛好等於 tau_die：感測器那一段一階遲滯會把它撐大一些，
    // 而 FOPDT 只有一個 tau 可以放兩個一階環節。
    EXPECT_GT(f.tau, 0.5 * p.tauDie);
    EXPECT_LT(f.tau, 2.0 * (p.tauDie + p.tauSense));

    // theta 應該接近設定的死區時間，且會被 tau_sense 「看起來」撐大。
    EXPECT_GT(f.theta, 0.5 * p.deadTime);
    EXPECT_LT(f.theta, p.deadTime + p.tauSense + 5.0);

    // 擬合殘差要小 —— 沒有雜訊時，殘差就是「FOPDT 這個模型形狀對不對」。
    EXPECT_LT(f.residualRms, 0.5) << "  無雜訊下殘差還這麼大，代表模型形狀不對";
}

/**
 * ★ 開了雜訊與量化之後，識別結果不該跑掉太多。
 *
 * 這一條守的是「exp01 的五個 seed 會給出一致的 K/tau/theta」——
 * 如果識別方法對雜訊敏感，那五個 seed 的範圍會大到報不出中位數。
 * **這也是選兩點法而不是最小平方的理由，這裡把它變成斷言。**
 */
TEST(Identify, SurvivesNoiseAndQuantisation)
{
    PlantParams clean;
    clean.noiseSigma = 0.0;
    clean.lsb = 0.01;
    const Trace trClean = makeStepTrace(clean, 40.0, 60.0, 150.0);
    const Fopdt ref =
        thermal::identifyTwoPoint(trClean.t, trClean.y, trClean.stepAtS, 20.0);

    const PlantParams noisy; // 預設值：sigma = 0.05、lsb = 0.0625
    const Trace tr = makeStepTrace(noisy, 40.0, 60.0, 150.0);
    const Fopdt f = thermal::identifyTwoPoint(tr.t, tr.y, tr.stepAtS, 20.0);

    EXPECT_NEAR(f.k, ref.k, 0.05 * std::fabs(ref.k)) << "  K 偏離超過 5%";
    EXPECT_NEAR(f.tau, ref.tau, 0.15 * ref.tau) << "  tau 偏離超過 15%";
    EXPECT_NEAR(f.theta, ref.theta, 0.5 + 0.3 * ref.theta)
        << "  theta 偏離太多";
}

/**
 * 反向的階躍（PWM 降、溫度升）也要算得對。
 *
 * crossingTime() 裡有一個 `rising` 判斷，方向寫反的話這一條會紅。
 * 上一條不會 —— 因為它只跑降溫方向。
 */
TEST(Identify, HandlesRisingResponse)
{
    PlantParams p;
    p.noiseSigma = 0.0;
    p.lsb = 0.01;

    const Trace tr = makeStepTrace(p, 60.0, 40.0, 150.0, 0); // 風扇變慢 → 升溫
    const Fopdt f = thermal::identifyTwoPoint(tr.t, tr.y, tr.stepAtS, -20.0);

    EXPECT_LT(f.k, 0.0) << "  du 為負、ΔT 為正 => K 仍然必須是負的";
    EXPECT_GT(f.tau, 0.5 * p.tauDie);
    EXPECT_LT(f.tau, 2.0 * (p.tauDie + p.tauSense));
    EXPECT_GT(f.theta, 0.5 * p.deadTime);
}

/**
 * ★ 基準值取平均，必須讓五個 seed 的 K 更集中。
 *
 * 為什麼要有這一條：把 y0 從「階躍前那一個點」改成「階躍前 10 秒的平均」
 * 是我的工程判斷（計畫範本是單點）。**判斷如果沒有測試守著，
 * 它遲早會在某次重構裡被改回去，而且沒有人會發現**——
 * 因為單點版本也會跑出一組看起來很正常的數字。
 *
 * 斷言方式刻意用**相對比較**而不是絕對門檻：
 * 同一批 seed、同一份資料，只改 baselineS 這一個變因，比較 K 的離散程度。
 * 理論預期是雜訊按 1/√n 縮小，100 點應該把離散度砍到十分之一量級。
 */
TEST(Identify, BaselineAveragingReducesSeedSpread)
{
    const PlantParams p; // 預設值：有雜訊、有量化
    constexpr unsigned kSeeds = 5;

    auto spreadOfK = [&](double baselineS) {
        double lo = 1e9;
        double hi = -1e9;
        for (unsigned s = 0; s < kSeeds; ++s)
        {
            const Trace tr = makeStepTrace(p, 40.0, 60.0, 150.0, s);
            const Fopdt f =
                thermal::identifyTwoPoint(tr.t, tr.y, tr.stepAtS, 20.0,
                                          baselineS);
            lo = std::min(lo, f.k);
            hi = std::max(hi, f.k);
        }
        return hi - lo;
    };

    const double singlePoint = spreadOfK(0.1); // 0.1 s = 一個取樣點
    const double averaged = spreadOfK(10.0);   // 10 s = 100 點

    EXPECT_LT(averaged, 0.5 * singlePoint)
        << "  取平均沒有讓 K 更集中 —— 基準值可能又被改回單點\n"
        << "  單點離散 = " << singlePoint << "，取平均離散 = " << averaged;
}

/**
 * 垃圾輸入要回傳全 0，不能崩、也不能回傳看起來很正常的數字。
 */
TEST(Identify, RejectsUnusableInput)
{
    const std::vector<double> t{0.0, 0.1, 0.2};
    const std::vector<double> y{25.0, 25.0, 25.0};

    const Fopdt tooShort = thermal::identifyTwoPoint(t, y, 0.1, 20.0);
    EXPECT_EQ(tooShort.tau, 0.0);

    PlantParams p;
    p.noiseSigma = 0.0;
    const Trace tr = makeStepTrace(p, 40.0, 60.0, 150.0);
    const Fopdt zeroDu = thermal::identifyTwoPoint(tr.t, tr.y, tr.stepAtS, 0.0);
    EXPECT_EQ(zeroDu.k, 0.0) << "  du = 0 會讓 K 變成除以零";
}

} // namespace
