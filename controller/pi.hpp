// SPDX-License-Identifier: Apache-2.0
//
// 單迴路 PI 控制器。
//
// 設計約束（與 plant/thermal_plant.hpp 同一套）：
//   · step() 不做任何 IO —— 才進得了 gtest 與 CI
//   · 誤差定義刻意與上游 ec::pid() 一致：error = setpoint - input
//     （這代表 temp 型別要用負係數；證據見 bench/data/exp02_signcheck/）
//   · 內部狀態只有 integral_ / lastError_ / lastOutput_，方便與上游逐步比對
#pragma once

namespace control
{

/**
 * 抗飽和策略。
 *
 * 積分飽和（windup）是這樣發生的：輸出已經頂到上限（風扇 100%）但誤差還在，
 * 積分項繼續累加。等誤差終於反號，那一堆累積的積分要花很久才「放完」，
 * 於是風扇該降不降。
 *
 * 前四個是教科書上的做法，我自己實作。第五個不是我的品味，是上游的行為。
 */
enum class AntiWindup
{
    /// 什麼都不做。**這是對照組** —— 用來證明 windup 真的會發生。
    None,

    /// ① 積分箝位：把積分項限制在 [integralMin, integralMax]。
    ///    簡單，但箝位值難選：太緊犧牲穩態精度，太鬆等於沒箝。
    Clamp,

    /// ② 條件積分：輸出飽和、而且誤差方向會加劇飽和時，這一步不累加。
    ///    不需要調參，但「方向」的判斷要小心。
    Conditional,

    /// ③ 回算（back-calculation / tracking anti-windup）：
    ///    用飽和後的**實際**輸出反推積分，把積分往「不會造成飽和」的方向拉回。
    ///
    ///    標準式（Åström & Hägglund）：
    ///        I += ki·e·ts + (sat(u) − u)·ts/Tt
    ///
    ///    `Tt` 是**追蹤時間常數**（`PiParams::trackingTimeS`）：
    ///    它決定積分被拉回來的**速度**。Tt 小 = 拉得快 = 幾乎不 windup，
    ///    但飽和邊緣的行為會比較躁；Tt 大 = 拉得慢 = 比較平順但恢復慢。
    ///
    ///    這裡也把前饋與微分那兩份扣掉 —— 與上游不同，見 UpstreamParity。
    BackCalculation,

    /// ★ 逐行複製上游 pid/ec/pid.cpp 的行為，只為了 parity 測試。
    ///
    /// 它不等於上面任何一個，因為上游是 ①＋③ 的混合，而且它那版回算有三個
    /// 我讀原始碼才發現的細節（計畫給的虛擬碼三個都寫錯了）：
    ///   1. 回算只扣 proportionalTerm，**沒有扣 feedFwdTerm 與 derivativeTerm**
    ///   2. 回算的觸發條件是「slewNeg 或 slewPos 有設定」，
    ///      **不是「slew 真的限制住了輸出」**
    ///   3. 最後那次 integral 箝位是**無條件執行**的，不在 slew 的判斷式裡面
    ///
    /// 為什麼不讓它跟上面四種共用程式碼：這條路徑的規格不是「一個好的控制器」，
    /// 是「上游此刻的行為」。共用的話，我哪天改進自己的實作，會連比對基準一起
    /// 改掉，而那正是 parity 測試唯一要防的事。
    UpstreamParity,
};

struct PiParams
{
    double kp = 0.0;
    double ki = 0.0;  ///< 每秒的積分增益（與上游 integralCoeff 同語意）
    double ts = 1.0;  ///< 取樣週期 (s)

    /// 微分增益。**本專案不用 D**（理由見 README：量化雜訊會被差分放大、
    /// 上游那版是對誤差微分所以改 setpoint 會 kick）。留這個欄位只有一個目的：
    /// 上游無條件計算 D 項，parity 測試要蓋到 kd != 0 的情形。
    double kd = 0.0;

    double outMin = 0.0;
    double outMax = 100.0;

    double integralMin = -1e9;  ///< 對應上游 integralLimit_min
    double integralMax = 1e9;   ///< 對應上游 integralLimit_max

    double slewNeg = 0.0;  ///< 每秒最大下降量（負值），0 = 不限制
    double slewPos = 0.0;  ///< 每秒最大上升量（正值），0 = 不限制

    double feedFwdOffset = 0.0;
    double feedFwdGain = 0.0;

    /// 回算的**追蹤時間常數 Tt (s)**，只在 AntiWindup::BackCalculation 生效。
    ///
    /// `0`（預設）= 「Tt 等於 ts」的極限情形，也就是**一步就把積分拉回來**。
    /// 那正是這個專案 W5 實作的行為 —— 所以預設值不改變任何既有結果。
    ///
    /// ★ 為什麼把它補回來（2026-08-09）
    ///   計畫的 `PiParams` 本來有一個 `backCalcGain`，W5 實作時**默默刪掉了**，
    ///   而且沒有記進偏離紀錄。刪掉之後 `BackCalculation` 這個名字就名不副實：
    ///   它不是可調的標準回算，是 Tt = ts 的那一個特例。
    ///   「這個實作沒有那個參數」與「Tt = ts，理由是……」是兩種完全不同的
    ///   狀態：前者是實作缺口，後者是有意識的取捨。叫作 BackCalculation 的
    ///   東西，應該說得出它的 Tt 是多少。
    ///
    /// ★ 為什麼是「時間常數 Tt」而不是計畫寫的「增益 backCalcGain」
    ///   Tt 有單位（秒），是控制文獻的標準寫法，而且**與 ts 無關** ——
    ///   換取樣週期時行為不會跟著變。增益版本得寫成 1/Tt，
    ///   改 ts 時還要重算，而那正是 W5 的 ts 盲區教會我的事。
    ///
    /// ⚠️ `Tt < ts` 會**過度修正**（一步拉過頭），慣例是取 `Tt ≥ ts`，
    ///    經驗值 `Tt ≈ Ti` 或 `Tt = √(Ti·Td)`。這裡不強制，但會在下面註明。
    double trackingTimeS = 0.0;

    AntiWindup antiWindup = AntiWindup::Clamp;
};

class Pi
{
  public:
    explicit Pi(const PiParams& p) : p_(p) {}

    /** 推進一步，回傳控制輸出。 */
    double step(double input, double setpoint);

    void reset();

    double integral() const
    {
        return integral_;
    }
    double lastOutput() const
    {
        return lastOutput_;
    }

  private:
    /// 逐行對照上游 pid/ec/pid.cpp 的實作，供 AntiWindup::UpstreamParity 使用。
    double stepLikeUpstream(double input, double setpoint);

    PiParams p_;
    double integral_ = 0.0;
    double lastError_ = 0.0;
    double lastOutput_ = 0.0;
    /// 上游用 pid_info_t::initialized 兼作「第一輪」旗標：slew 與回算都不在
    /// 第一輪生效（沒有 lastOutput 可以比）。這裡保留同樣的語意。
    bool initialized_ = false;
};

} // namespace control
