// SPDX-License-Identifier: Apache-2.0
//
// L1 純模擬執行檔：跑一次開環或閉環模擬，把每個時間步吐成 CSV。
//
// 設計原則（見 docs/measurement.md）：
//   · 這支程式**不畫圖、不做分析**，只產生原始資料。
//   · 所有參數從 CLI 進來，沒有寫死的魔術數字。
//   · 同樣的參數 + 同樣的 seed 必須產生**逐 byte 相同**的輸出。
//
// 為什麼執行檔是 C++ 而不是 Python：
//   ① plant 是 C++，用 Python 呼叫要綁定層，多一層麻煩
//   ② L1 要跑大量參數掃描（W6 的 λ、W8 的 slew），速度有差
//   ③ 對上 JD 的 C/C++
// 但**實驗編排與畫圖用 Python** —— 這是誠實的分工，不是為了炫技。
//
// ★ 兩條輸出管道，用途不同，不要混：
//   stdout = CSV（純資料，pandas 直接吃得下，不含任何註解行）
//   stderr = 這次執行**生效的完整參數**（證據用）
//   為什麼要分開：CLI 可以覆寫 plant 參數，一旦可以覆寫，
//   CSV 本身就不再自證是用什麼參數跑出來的。把參數印到 stderr，
//   bench/exp01_sysid.py 才有東西可以存進 meta 檔。
//   混在 stdout 裡則會汙染 CSV。
#include "plant/thermal_plant.hpp"

#include <cstdio>
#include <cstdlib>
#include <string>

namespace
{

struct Args
{
    double dt = 0.1;         ///< 離散步長 (s)
    double seconds = 600.0;  ///< 總模擬時間 (s)
    unsigned seed = 0;       ///< 亂數種子
    double powerBase = 150.0;///< 基準功耗 (W)
    double powerStep = 400.0;///< 階躍後功耗 (W)
    double powerAtS = -1.0;  ///< 功耗階躍時刻 (s)，負數 = 不階躍
    double pwmBase = 40.0;   ///< 基準 PWM (%)
    double pwmStep = 60.0;   ///< 階躍後 PWM (%)
    double pwmAtS = -1.0;    ///< PWM 階躍時刻 (s)，負數 = 不階躍（開環系統識別用）
};

double parseD(const char* s)
{
    return std::strtod(s, nullptr);
}

void usage()
{
    std::fprintf(stderr,
                 "usage: sim [options]   (CSV -> stdout, params -> stderr)\n"
                 "  --dt <s>            離散步長，預設 0.1\n"
                 "  --seconds <s>       總時間，預設 600\n"
                 "  --seed <n>          亂數種子，預設 0\n"
                 "  --power-base <W>    基準功耗，預設 150\n"
                 "  --power-step <W>    階躍後功耗，預設 400\n"
                 "  --power-at <s>      功耗階躍時刻，負數=不階躍\n"
                 "  --pwm-base <%%>      基準 PWM，預設 40\n"
                 "  --pwm-step <%%>      階躍後 PWM，預設 60\n"
                 "  --pwm-at <s>        PWM 階躍時刻，負數=不階躍\n"
                 "  --noise-sigma <C>   覆寫量測雜訊 σ\n"
                 "  --lsb <C>           覆寫量化步階\n"
                 "  --dead-time <s>     覆寫傳輸死區 θ\n"
                 "\n"
                 "後三個是給止損路徑用的（見 plan 的「簡化 plant」）：\n"
                 "先把雜訊與死區關掉確認圖做得出來，再逐項加回去。\n");
}

} // namespace

int main(int argc, char** argv)
{
    Args a;
    thermal::PlantParams p;

    for (int i = 1; i < argc; ++i)
    {
        const std::string k = argv[i];
        if (k == "--help" || k == "-h")
        {
            usage();
            return 0;
        }
        // ⚠️ 計畫的迴圈條件是 `i + 1 < argc`，少給值的旗標會被**安靜忽略**：
        //    `sim --seed` 會跑出 seed=0 的資料，而你以為那是你指定的 seed。
        //    安靜的錯誤在證據鏈上比崩潰危險得多，所以這裡直接報錯離開。
        if (i + 1 >= argc)
        {
            std::fprintf(stderr, "option %s 少了值\n", argv[i]);
            return 2;
        }
        const char* v = argv[++i];

        if (k == "--dt")               a.dt = parseD(v);
        else if (k == "--seconds")     a.seconds = parseD(v);
        else if (k == "--seed")        a.seed = static_cast<unsigned>(std::strtoul(v, nullptr, 10));
        else if (k == "--power-base")  a.powerBase = parseD(v);
        else if (k == "--power-step")  a.powerStep = parseD(v);
        else if (k == "--power-at")    a.powerAtS = parseD(v);
        else if (k == "--pwm-base")    a.pwmBase = parseD(v);
        else if (k == "--pwm-step")    a.pwmStep = parseD(v);
        else if (k == "--pwm-at")      a.pwmAtS = parseD(v);
        else if (k == "--noise-sigma") p.noiseSigma = parseD(v);
        else if (k == "--lsb")         p.lsb = parseD(v);
        else if (k == "--dead-time")   p.deadTime = parseD(v);
        else
        {
            std::fprintf(stderr, "unknown option: %s\n", k.c_str());
            usage();
            return 2;
        }
    }

    if (a.dt <= 0.0 || a.seconds <= 0.0)
    {
        std::fprintf(stderr, "--dt 與 --seconds 必須為正\n");
        return 2;
    }

    // ── 證據：這次執行到底用了什麼（stderr，不汙染 CSV）─────────────────
    std::fprintf(stderr,
                 "dt=%g\nseconds=%g\nseed=%u\n"
                 "power_base=%g\npower_step=%g\npower_at=%g\n"
                 "pwm_base=%g\npwm_step=%g\npwm_at=%g\n"
                 "t_amb=%g\nrth_max=%g\nrth_min=%g\nflow_exp=%g\n"
                 "tau_die=%g\ntau_sense=%g\ntau_fan=%g\ndead_time=%g\n"
                 "rpm_max=%g\npwm_min_spin=%g\nlsb=%g\nnoise_sigma=%g\n",
                 a.dt, a.seconds, a.seed, a.powerBase, a.powerStep, a.powerAtS,
                 a.pwmBase, a.pwmStep, a.pwmAtS, p.tAmb, p.rthMax, p.rthMin,
                 p.flowExp, p.tauDie, p.tauSense, p.tauFan, p.deadTime,
                 p.rpmMax, p.pwmMinSpin, p.lsb, p.noiseSigma);

    thermal::ThermalPlant plant(p, a.dt, a.seed);

    // CSV 標頭 —— ★ 欄位名一旦定下來就不要改，bench/*.py 依賴它。
    std::printf("t_s,pwm,power_w,t_sense_c,t_die_c,rpm,fan_power_rel\n");

    const int n = static_cast<int>(a.seconds / a.dt);
    for (int i = 0; i < n; ++i)
    {
        const double t = i * a.dt;
        const double pwm =
            (a.pwmAtS >= 0.0 && t >= a.pwmAtS) ? a.pwmStep : a.pwmBase;
        const double pw =
            (a.powerAtS >= 0.0 && t >= a.powerAtS) ? a.powerStep : a.powerBase;

        const double tSense = plant.step(pwm, pw);

        std::printf("%.3f,%.4f,%.4f,%.4f,%.4f,%.2f,%.6f\n", t, pwm, pw, tSense,
                    plant.dieTemp(), plant.rpm(), plant.fanPowerRel());
    }
    return 0;
}
