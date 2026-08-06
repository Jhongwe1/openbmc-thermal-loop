// SPDX-License-Identifier: Apache-2.0
#include "plant/identify.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <numeric>

namespace thermal
{

namespace
{

/** 取序列尾端 n 點的平均，當作階躍後的穩態值 y∞。 */
double tailMean(const std::vector<double>& y, std::size_t n)
{
    n = std::clamp<std::size_t>(n, 1, y.size());
    return std::accumulate(y.end() - static_cast<std::ptrdiff_t>(n), y.end(),
                           0.0) /
           static_cast<double>(n);
}

/**
 * 取 [from - n, from) 這段的平均，當作階躍前的基準值 y0。
 *
 * ⚠️ 計畫範本是 `y0 = y[iStep]` —— **單一個點**。
 *    那個點含雜訊（σ = 0.05）又被量化（LSB = 0.0625），單點誤差可到 0.19 °C。
 *    exp01 的溫度變化只有約 6 °C，0.19 就是 3% 的 K 誤差，
 *    而 bench/claims.json 對 tau 的容差只有 10%。
 *    **基準值錯了，K、t₁、t₂ 三個東西會一起錯**，因為門檻是從 y0 算的。
 *    取平均是免費的：雜訊按 1/√n 縮小，100 點就把 σ 砍到十分之一。
 */
double baselineMean(const std::vector<double>& y, std::size_t from,
                    std::size_t n)
{
    if (from == 0)
    {
        return y.empty() ? 0.0 : y.front();
    }
    n = std::clamp<std::size_t>(n, 1, from);
    const auto first = y.begin() + static_cast<std::ptrdiff_t>(from - n);
    const auto last = y.begin() + static_cast<std::ptrdiff_t>(from);
    return std::accumulate(first, last, 0.0) / static_cast<double>(n);
}

/**
 * 找出響應第一次跨過 target 的時刻，跨過的那一格用線性內插。
 *
 * 內插不是為了好看：取樣間隔 0.1 s，不內插的話 t₁ 與 t₂ 各有 ±0.05 s 的
 * 量化誤差，而 τ = 1.5(t₂ − t₁) 會把這個誤差放大 1.5 倍。
 */
double crossingTime(const std::vector<double>& t, const std::vector<double>& y,
                    double y0, double target, std::size_t from)
{
    const bool rising = target > y0;
    for (std::size_t i = from + 1; i < y.size(); ++i)
    {
        const bool crossed = rising ? (y[i] >= target) : (y[i] <= target);
        if (crossed)
        {
            const double dy = y[i] - y[i - 1];
            const double frac =
                (std::fabs(dy) < 1e-12) ? 0.0 : (target - y[i - 1]) / dy;
            return t[i - 1] + frac * (t[i] - t[i - 1]);
        }
    }
    return t.back(); // 沒跨過：資料太短或根本沒響應
}

} // namespace

Fopdt identifyTwoPoint(const std::vector<double>& t,
                       const std::vector<double>& y, double stepAtS, double du,
                       double baselineS)
{
    Fopdt f;
    if (t.size() != y.size() || t.size() < 10 || std::fabs(du) < 1e-12)
    {
        return f;
    }

    const std::size_t iStep = static_cast<std::size_t>(
        std::lower_bound(t.begin(), t.end(), stepAtS) - t.begin());
    if (iStep + 2 >= t.size())
    {
        return f;
    }

    const double dt = t[1] - t[0];
    const auto nBase =
        static_cast<std::size_t>(std::max(1.0, baselineS / std::max(dt, 1e-9)));

    const double y0 = baselineMean(y, iStep, nBase);
    const double yInf = tailMean(y, y.size() / 10);

    f.k = (yInf - y0) / du;

    const double t1 = crossingTime(t, y, y0, y0 + 0.283 * (yInf - y0), iStep);
    const double t2 = crossingTime(t, y, y0, y0 + 0.632 * (yInf - y0), iStep);

    f.tau = 1.5 * (t2 - t1);
    f.theta = (t2 - f.tau) - stepAtS;
    if (f.theta < 0.0)
    {
        f.theta = 0.0; // 死區不可能是負的；擬合出負值代表 τ 被高估了
    }
    if (f.tau <= 0.0)
    {
        return f; // 下面要除以 tau
    }

    // 殘差：用擬合出來的 FOPDT 重建響應，與實測逐點比對。
    // ★ 這一項是「反造假設計」的一部分 —— 沒有殘差的擬合是畫上去的。
    //   殘差 RMS 要標在 Fig 1 上，讀者才知道那條黑線離資料多遠。
    double sum = 0.0;
    std::size_t n = 0;
    for (std::size_t i = iStep; i < t.size(); ++i)
    {
        const double dtau = t[i] - stepAtS - f.theta;
        const double model =
            (dtau <= 0.0) ? y0
                          : y0 + f.k * du * (1.0 - std::exp(-dtau / f.tau));
        sum += (y[i] - model) * (y[i] - model);
        ++n;
    }
    f.residualRms = (n > 0) ? std::sqrt(sum / static_cast<double>(n)) : 0.0;
    return f;
}

} // namespace thermal
