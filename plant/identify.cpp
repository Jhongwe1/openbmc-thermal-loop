// SPDX-License-Identifier: Apache-2.0
#include "plant/identify.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>
// <numeric> 在 2026-08-09 把兩個平均改成用時間框之後就用不到了
// （std::accumulate 沒了）。用不到的 include 要拿掉 —— 它會讓下一個人
// 以為這裡還在用標準演算法，而且 -Werror 不會提醒。

namespace thermal
{

namespace
{

/**
 * 取序列**最後 fraction 比例的時間**的平均，當作階躍後的穩態值 y∞。
 *
 * ★ 與 baselineMean 同一個理由：用時間框，不是用列數框。
 *   原本寫的是 `tailMean(y, y.size() / 10)`（最後 10 % 的**列**）——
 *   非等間隔的軌跡上，「最後 10 % 的列」與「最後 10 % 的時間」是兩件事。
 *   等間隔時兩者逐點相同，所以這個改動**不會動到 exp01 已經量到的數字**
 *   （已驗證：重跑五個 seed，K/tau/theta 逐位元相同）。
 */
double tailMean(const std::vector<double>& t, const std::vector<double>& y,
                double fraction)
{
    if (y.empty())
    {
        return 0.0;
    }
    const double tEnd = t.back();
    const double start = tEnd - fraction * (tEnd - t.front());
    double sum = 0.0;
    std::size_t n = 0;
    for (std::size_t i = 0; i < y.size(); ++i)
    {
        if (t[i] >= start)
        {
            sum += y[i];
            ++n;
        }
    }
    return (n > 0) ? sum / static_cast<double>(n) : y.back();
}

/**
 * 取階躍前 windowS 秒的平均，當作基準值 y0。
 *
 * ⚠️ 計畫範本是 `y0 = y[iStep]` —— **單一個點**。
 *    那個點含雜訊（σ = 0.05）又被量化（LSB = 0.0625），單點誤差可到 0.19 °C。
 *    exp01 的溫度變化只有約 6 °C，0.19 就是 3% 的 K 誤差，
 *    而 bench/claims.json 對 tau 的容差只有 10%。
 *    **基準值錯了，K、t₁、t₂ 三個東西會一起錯**，因為門檻是從 y0 算的。
 *    取平均是免費的：雜訊按 1/√n 縮小，100 點就把 σ 砍到十分之一。
 *
 * ★★ 視窗用**時間**框，不是用列數框（2026-08-09 改）。
 *    原本的寫法是 `n = baselineS / dt`，而 `dt` 是從序列的**前兩點**推出來的。
 *    對 `bench/sim` 產生的等間隔資料那沒問題，但 W9 的 L1 vs L2 對照要把
 *    **從 BMC 收回來的軌跡**餵進同一個函式 —— 那一側的取樣間隔本來就會抖。
 *    列數框在非等間隔資料上會**安靜地**涵蓋錯誤的時間長度：
 *    不會報錯，只會給你一個看起來很正常、但基準值不對的 K。
 *    （`bench/metrics.py` 的 `fan_power_rel` 有一模一樣的問題，同一天一起修。）
 */
double baselineMean(const std::vector<double>& t, const std::vector<double>& y,
                    std::size_t from, double windowS)
{
    if (from == 0)
    {
        return y.empty() ? 0.0 : y.front();
    }
    const double start = t[from] - windowS;
    double sum = 0.0;
    std::size_t n = 0;
    for (std::size_t i = from; i-- > 0;)
    {
        if (t[i] < start)
        {
            break;
        }
        sum += y[i];
        ++n;
    }
    if (n == 0)
    {
        // 視窗比一個取樣間隔還短：退回最靠近階躍的那一點，並且**只有這一點**。
        return y[from - 1];
    }
    return sum / static_cast<double>(n);
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

    const double y0 = baselineMean(t, y, iStep, baselineS);
    const double yInf = tailMean(t, y, 0.1);

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
