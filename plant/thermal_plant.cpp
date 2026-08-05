// SPDX-License-Identifier: Apache-2.0
#include "plant/thermal_plant.hpp"

#include <algorithm>
#include <cmath>
#include <cstddef>

namespace thermal
{

ThermalPlant::ThermalPlant(const PlantParams& p, double dt, unsigned seed) :
    p_(p), dt_(dt), rng_(seed), noise_(0.0, p.noiseSigma), tDie_(p.tAmb),
    tSense_(p.tAmb), rpm_(0.0)
{
    // 死區時間用固定長度的佇列實現：θ / dt 個時間步。
    // 佇列先填滿環境溫度，代表「開機時管路裡的空氣就是環境溫度」。
    const auto n = static_cast<std::size_t>(std::lround(p_.deadTime / dt_));
    delay_.assign(n > 0 ? n : 1, p_.tAmb);
}

double ThermalPlant::step(double pwm, double powerW)
{
    pwm = std::clamp(pwm, 0.0, 100.0);

    // 1) 風扇：PWM -> RPM，一階慣性 + 起轉死區。
    //    pwmMinSpin 是真實的非線性：PWM 太低風扇根本不轉，
    //    而不是「轉得很慢」。低負載時控制器在這個門檻附近來回，
    //    就會出現 hunting（風扇忽開忽停），這是真實 BMC 的老問題。
    const double rpmCmd =
        (pwm < p_.pwmMinSpin) ? 0.0 : p_.rpmMax * (pwm / 100.0);
    rpm_ += (rpmCmd - rpm_) * dt_ / p_.tauFan;

    // 2) 氣流 -> 熱阻（強制對流）。
    //    q 是相對風量 0~1，Rth 在 rthMax（停轉）與 rthMin（滿速）之間，
    //    用 q^n 內插。n = flowExp = 0.8 是強制對流的經驗指數。
    const double q = std::clamp(rpm_ / p_.rpmMax, 0.0, 1.0);
    const double rth =
        p_.rthMin + (p_.rthMax - p_.rthMin) * (1.0 - std::pow(q, p_.flowExp));

    // 3) 元件溫度：一階趨近穩態 T_ss = T_amb + P·Rth。
    const double tSs = p_.tAmb + powerW * rth;
    tDie_ += (tSs - tDie_) * dt_ / p_.tauDie;

    // 4) 傳輸死區時間：**純延遲**，用佇列實現。
    //    ⚠️ 死區與遲滯是兩件事。死區是「訊號整段往後平移」，
    //    遲滯是「訊號被低通濾波、變圓」。把死區用一階濾波器近似
    //    是常見錯誤，會讓後面的 FOPDT 擬合把 θ 算進 τ 裡。
    delay_.push_back(tDie_);
    const double tArrived = delay_.front();
    delay_.pop_front();

    // 5) 感測器本身的熱容造成的遲滯：又一個一階。
    //    ⚠️ 步驟 4 與 5 的順序不能反。物理上熱空氣要先「流到」感測器
    //    （延遲），感測器才開始「慢慢熱起來」（遲滯）。順序寫反，
    //    FOPDT 擬合會得到不同的 θ 與 τ。
    tSense_ += (tArrived - tSense_) * dt_ / p_.tauSense;

    // 6) 量測鏈：雜訊 + 量化。
    //    這一層是「感測器讀到什麼」，不是「溫度是多少」。
    //    lsb 量化是 W6 討論「為什麼不用 D 項」的物理依據 ——
    //    微分項會把量化階梯放大成尖刺。
    const double raw = tSense_ + noise_(rng_);
    return std::round(raw / p_.lsb) * p_.lsb;
}

double ThermalPlant::fanPowerRel() const
{
    const double q = std::clamp(rpm_ / p_.rpmMax, 0.0, 1.0);
    return q * q * q; // 親和定律：功率 ∝ 轉速³
}

} // namespace thermal
