// SPDX-License-Identifier: Apache-2.0
//
// FOPDT（First Order Plus Dead Time）系統識別。
//
// 這裡是「從一條階躍響應曲線反推出模型參數」的地方。W6 調 PI 係數時，
// 用的就是這裡算出來的 K / tau / theta —— **不是試出來的**。
#pragma once

#include <vector>

namespace thermal
{

/**
 * 一階加死區模型：G(s) = K · e^(−θs) / (τs + 1)
 */
struct Fopdt
{
    double k = 0.0;           ///< 增益 (°C / %PWM)。**風扇迴路必為負**
    double tau = 0.0;         ///< 時間常數 (s)
    double theta = 0.0;       ///< 死區時間 (s)
    double residualRms = 0.0; ///< 擬合殘差 RMS (°C)，標在 Fig 1 上
};

/**
 * 兩點法 FOPDT 識別。
 *
 * @param t          時間序列 (s)，等間隔遞增
 * @param y          響應序列（感測溫度）
 * @param stepAtS    階躍發生的時刻 (s)
 * @param du         輸入變化量（PWM 從 40 到 60 則 du = 20）
 * @param baselineS  取階躍前多少秒的平均當基準值 y0（預設 10 s）
 *
 * ★ 為什麼是 28.3% 與 63.2%（要說得出來）：
 *   一階階躍響應 y = A(1 − e^(−(t−θ)/τ))。
 *     y/A = 0.632 → t₂ = θ + τ
 *     y/A = 0.283 → t₁ = θ + τ/3
 *   兩式相減**把 θ 消掉**：t₂ − t₁ = ⅔τ  ⇒  τ = 1.5(t₂ − t₁)，再回代得 θ。
 *   選這兩個百分比的唯一理由就是「相減能消掉 θ」。
 *
 * ★ 為什麼用兩點法而不是最小平方擬合：
 *   兩點法只需要兩個時刻，對量化雜訊不敏感，而且每一步都可以手算驗證。
 *   最小平方對 theta 是非線性的，要迭代，而且結果不好解釋給人聽。
 *   **能手算驗證的方法，在證據鏈上比較值錢。**
 *
 * @return 無法識別時（資料太短、du 為 0）回傳全 0 的 Fopdt。
 */
Fopdt identifyTwoPoint(const std::vector<double>& t,
                       const std::vector<double>& y, double stepAtS, double du,
                       double baselineS = 10.0);

} // namespace thermal
