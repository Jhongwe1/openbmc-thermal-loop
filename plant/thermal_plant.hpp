// SPDX-License-Identifier: Apache-2.0
//
// 單節點伺服器熱系統的集總參數模型。
//
// 這個檔案是整個專案唯一「100% 是我自己的」東西。控制器有現成的
// （上游 ec::pid()），抗飽和有現成的，Redfish 有現成的 —— 只有這個被控對象
// 與圍繞它的量測方法學是我寫的。
//
// 物理推導、每個參數的理由、以及哪些是【判】工程判斷而非查證事實，
// 全部寫在 docs/plant-model.md。**改這裡的任何數字，那份文件要同步改。**
#pragma once

#include <cstddef>
#include <deque>
#include <random>

namespace thermal
{

/**
 * 熱模型的參數。單位一律是 SI 或工程慣用單位，寫在每一行後面。
 *
 * 這些值是 order-of-magnitude 合理的工程判斷，不是從某台真實機器量來的。
 * 面試講到它們時要用「我的理解是」開頭 —— 見 docs/plant-model.md 的【判】標記。
 */
struct PlantParams
{
    double tAmb = 25.0;         ///< 機房進風溫度 (°C)
    double rthMax = 0.35;       ///< 風扇停轉時的熱阻 (°C/W)：自然對流
    double rthMin = 0.12;       ///< 風扇滿速時的熱阻 (°C/W)：強制對流
    double flowExp = 0.8;       ///< 強制對流的經驗指數 n，Rth ∝ 1/v^n
    double tauDie = 45.0;       ///< 元件+散熱片的熱時間常數 (s)
    double tauSense = 3.0;      ///< 感測器本身熱容造成的遲滯 (s)
    double tauFan = 1.5;        ///< 風扇機械慣性，PWM→RPM 的一階時間常數 (s)
    double deadTime = 3.0;      ///< 傳輸死區時間 θ (s)：氣流路徑 + 取樣週期
    double rpmMax = 15000.0;    ///< 滿速轉速 (RPM)：伺服器 40mm 風扇
    double pwmMinSpin = 12.0;   ///< 低於此 PWM (%) 風扇不轉 —— 真實的非線性
    double lsb = 0.0625;        ///< 溫感解析度 (°C)。★ 實測值，見下方註解
    double noiseSigma = 0.05;   ///< 量測雜訊標準差 (°C)：ADC + 環境
};

// ★ lsb = 0.0625 不是抄來的，是在測試床上量到的（exp04）。
//   證據是**階梯本身**不是單一個點：細掃注入值之後，BMC 的讀值只落在
//   7 個相異階上，階距在 62 與 63 m°C 之間交替（一格 = 62.5 m°C = 1/16 °C）。
//   原始資料 bench/data/exp04_injection/sweep.csv。
//
//   ⚠️ 2026-08-09 更正：這裡原本寫的是「設 40.000，BMC 讀回 39.938，差 1/16」。
//      **那個推導不成立** —— 40.000 剛好在 1/16 的格點上，純量化器應該回 40.000。
//      那 62 m°C 的差是 QEMU setter `(temp*256-128)/1000` 截斷造成的**系統性偏壓**，
//      不是量化。數字對，但是靠巧合對的。完整推導見 docs/plant-model.md §2.1。
//
//   計畫範本寫的是 0.5（一般溫感的量級），但**我有真的數字就用真的**。
//   這一步讓 L1 模擬與 L2 實機的量化行為一致 —— 兩層的圖要能直接疊，
//   量化步階就不能是兩個不同的數字。
//
//   ⚠️ 這個模型只複製**量化**，不複製那個 −1 LSB 偏壓：偏壓是注入路徑的產物，
//      真實硬體上不會有。L2 拿 sensedAnalog() 寫進晶片時它才會出現，
//      而 L1/L2 對照要扣掉它 —— 見 docs/plant-model.md §2.1。

/**
 * 單節點伺服器熱系統的集總參數模型。
 *
 * ★ 設計約束：step() 只依賴內部狀態與輸入，**不做任何 IO**。
 *   這是它能同時服務 L1 純模擬、L2 D-Bus 橋接與 L0 gtest 的原因，
 *   也是「同一份 plant model 貫穿三層」這個宣稱能成立的前提。
 *   一旦 step() 裡出現讀檔、讀時鐘或發 D-Bus，L0 就測不動它，
 *   L1 與 L2 也就不再是同一個被控對象。
 */
class ThermalPlant
{
  public:
    /**
     * @param p     參數
     * @param dt    離散時間步長 (s)。要遠小於最快的時間常數 tauFan
     * @param seed  亂數種子。★ 固定 seed = 可重現 = 別人 clone 得到同一張圖
     */
    ThermalPlant(const PlantParams& p, double dt = 0.1, unsigned seed = 0);

    /**
     * 推進一個時間步。
     *
     * @param pwm     風扇 PWM 百分比 0~100
     * @param powerW  元件功耗 (W)
     * @return  **感測器讀到的**溫度：含傳輸死區、感測器遲滯、雜訊、量化。
     *          這是 L1 模擬要用的值（模型自己模擬整條量測鏈）。
     */
    double step(double pwm, double powerW);

    /**
     * 感測器位置的「類比」溫度：含死區與遲滯，**但不含雜訊與量化**。
     *
     * ★ 這是 L2 要用的值。L2 把它寫進 QEMU 的 tmp421，
     *   由**真的**晶片模型與**真的** kernel driver 去做量化。
     *   如果 L2 改用 step() 的回傳值，量化會發生兩次，
     *   量到的解析度誤差會是實際的兩倍 —— 那會讓 L1/L2 的比較失去意義。
     */
    double sensedAnalog() const { return tSense_; }

    /** 元件本體溫度 (°C)：模型內部真值，現實中量不到。 */
    double dieTemp() const { return tDie_; }

    /** 目前轉速 (RPM)。 */
    double rpm() const { return rpm_; }

    /** 相對風扇功耗，滿速為 1.0（親和定律：P ∝ N³）。W6 的聲學/功耗代價要用。 */
    double fanPowerRel() const;

  private:
    PlantParams p_;
    double dt_;
    std::mt19937 rng_;                  ///< ★ 固定 seed = 可重現
    std::normal_distribution<double> noise_;
    double tDie_;
    double tSense_;
    double rpm_;
    std::deque<double> delay_;          ///< 傳輸死區：固定長度的純延遲佇列
};

} // namespace thermal
