// SPDX-License-Identifier: Apache-2.0
//
// 熱模型的手動驗收工具（W3 D6）。
//
// 它不是測試 —— 測試是 test/test_plant.cpp，由 CI 檢查。
// 這支程式的用途是「用眼睛看曲線合不合物理直覺」，以及印出
// docs/plant-model.md 裡那張穩態對照表的實際數字。
//
//   ./build/plant_probe            預設：pwm 50%、150 W、跑 300 秒
//   ./build/plant_probe 100 400    pwm 100%、400 W（Fig 3 的飽和條件）
#include "plant/thermal_plant.hpp"

#include <cmath>
#include <cstdio>
#include <cstdlib>

namespace {

/** 解析穩態值：T = T_amb + P·Rth(pwm)。必須與 step() 內的公式一致。 */
double analytic(double pwm, double powerW, const thermal::PlantParams& p)
{
    const double q = (pwm < p.pwmMinSpin) ? 0.0 : pwm / 100.0;
    const double rth =
        p.rthMin + (p.rthMax - p.rthMin) * (1.0 - std::pow(q, p.flowExp));
    return p.tAmb + powerW * rth;
}

} // namespace

int main(int argc, char** argv)
{
    const double pwm = (argc > 1) ? std::atof(argv[1]) : 50.0;
    const double powerW = (argc > 2) ? std::atof(argv[2]) : 150.0;

    const thermal::PlantParams p;
    const double dt = 0.1;
    thermal::ThermalPlant plant(p, dt, /*seed=*/0);

    std::printf("pwm=%.0f%%  P=%.0f W   dt=%.2f s   seed=0\n", pwm, powerW, dt);
    std::printf("%8s %10s %10s %9s\n", "t (s)", "sensed", "die", "rpm");

    const double want = analytic(pwm, powerW, p);
    const double band632 = p.tAmb + 0.632 * (want - p.tAmb);
    double t632 = -1.0;

    const int steps = 3000; // 300 s
    for (int i = 0; i < steps; ++i)
    {
        const double now = i * dt;
        const double t = plant.step(pwm, powerW);

        if (t632 < 0.0 && plant.sensedAnalog() >= band632)
        {
            t632 = now;
        }

        // 前 15 秒每秒印一次，才看得見死區；之後每 10 秒一次。
        const bool fine = (now < 15.0) && (i % 10 == 0);
        const bool coarse = (now >= 15.0) && (i % 100 == 0);
        if (fine || coarse)
        {
            std::printf("%8.1f %10.3f %10.3f %9.0f\n", now, t,
                        plant.dieTemp(), plant.rpm());
        }
    }

    std::printf("\n--- 驗收 ---\n");
    std::printf("穩態解析值 T_amb + P*Rth   = %8.3f C\n", want);
    std::printf("模型 300 s 後的類比讀值    = %8.3f C   (差 %+.3f)\n",
                plant.sensedAnalog(), plant.sensedAnalog() - want);
    std::printf("到達 63.2%% 的時間          = %8.1f s   "
                "(預期 ~ tauDie+tauSense+theta = %.1f s)\n",
                t632, p.tauDie + p.tauSense + p.deadTime);
    return 0;
}
