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
#include "controller/pi.hpp"
#include "plant/thermal_plant.hpp"

#include <cmath>
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
    double powerDownAtS = -1.0; ///< 功耗降回 base 的時刻 (s)，負數 = 不降（W7）
    double pwmBase = 40.0;   ///< 基準 PWM (%)
    double pwmStep = 60.0;   ///< 階躍後 PWM (%)
    double pwmAtS = -1.0;    ///< PWM 階躍時刻 (s)，負數 = 不階躍（開環系統識別用）

    // ── 閉環（W6）──────────────────────────────────────────────────────
    bool closedLoop = false;
    double setpoint = 65.0;  ///< 目標溫度 (°C)

    /// ★ 控制器的取樣週期，**與 --dt 是兩件不同的事**。
    ///
    /// plant 每 `dt` 推進一次（物理），控制器每 `ctrlTs` 才算一次新輸出。
    /// 預設 1.0 是為了對齊 swampd 外圈熱 PID 的 `updateThermalsTimeMS = 1000`。
    ///
    /// 混為一談就是地雷 #12：L1 每 100 ms 更新一次控制輸出、L2 是一秒一次，
    /// 兩條線的暫態怎麼調參數都疊不起來 —— 因為那不是參數問題。
    double ctrlTs = 1.0;
};

/// 控制器參數與 anti-windup 策略分開放：前者原封不動交給 control::Pi，
/// 後者要先從字串解析，失敗時得說得出「合法的值有哪些」。
struct CtrlArgs
{
    control::PiParams pi{};
    std::string antiWindup = "clamp";
};

double parseD(const char* s)
{
    return std::strtod(s, nullptr);
}

/// 把 --anti-windup 的字串轉成列舉。回傳 false = 不認得。
///
/// ⚠️ 不認得的時候**不要**默默用預設值。這個旗標決定 Fig 3 的 A/B 兩組是
///    哪兩個策略，打錯字而被安靜忽略的話，兩組會跑出一模一樣的資料，
///    而那正是 W7 最怕的失敗模式（地雷 #10）。
bool parseAntiWindup(const std::string& s, control::AntiWindup& out)
{
    if (s == "none")             out = control::AntiWindup::None;
    else if (s == "clamp")       out = control::AntiWindup::Clamp;
    else if (s == "conditional") out = control::AntiWindup::Conditional;
    else if (s == "backcalc")    out = control::AntiWindup::BackCalculation;
    else if (s == "parity")      out = control::AntiWindup::UpstreamParity;
    else return false;
    return true;
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
                 "  --power-down-at <s> 功耗降回 base 的時刻，負數=不降（W7，"
                 "要配合 --power-at）\n"
                 "  --pwm-base <%%>      基準 PWM，預設 40\n"
                 "  --pwm-step <%%>      階躍後 PWM，預設 60\n"
                 "  --pwm-at <s>        PWM 階躍時刻，負數=不階躍\n"
                 "  --noise-sigma <C>   覆寫量測雜訊 σ\n"
                 "  --lsb <C>           覆寫量化步階\n"
                 "  --dead-time <s>     覆寫傳輸死區 θ\n"
                 "\n"
                 "後三個是給止損路徑用的（見 plan 的「簡化 plant」）：\n"
                 "先把雜訊與死區關掉確認圖做得出來，再逐項加回去。\n"
                 "\n"
                 "閉環（W6）——CSV 會多一欄 integral：\n"
                 "  --closed-loop       開啟閉環。★ 與 --pwm-at 互斥\n"
                 "  --setpoint <C>      目標溫度，預設 65\n"
                 "  --ctrl-ts <s>       ★ 控制器取樣週期，預設 1.0（外圈 1 Hz）\n"
                 "                      與 --dt 不同：dt 是物理步長，這是控制週期\n"
                 "  --kp <>             比例增益。temp 迴路要用**負值**\n"
                 "  --ki <>             積分增益（每秒），同樣是負值\n"
                 "  --kd <>             微分增益，預設 0（本專案不用 D）\n"
                 "  --out-min <%%>       輸出下限，預設 0\n"
                 "  --out-max <%%>       輸出上限，預設 100\n"
                 "  --integral-min <>   積分箝位下限，預設 -1e9（等於不箝）\n"
                 "  --integral-max <>   積分箝位上限，預設  1e9\n"
                 "  --slew-neg <>/s     每秒最大下降量（負值），0 = 不限\n"
                 "  --slew-pos <>/s     每秒最大上升量（正值），0 = 不限\n"
                 "  --tracking-time <s> 回算的追蹤時間常數 Tt，0 = 退化成 Tt=ts\n"
                 "  --anti-windup <s>   none|clamp|conditional|backcalc|parity\n");
}

} // namespace

int main(int argc, char** argv)
{
    Args a;
    thermal::PlantParams p;
    CtrlArgs c;

    for (int i = 1; i < argc; ++i)
    {
        const std::string k = argv[i];
        if (k == "--help" || k == "-h")
        {
            usage();
            return 0;
        }
        // ★ 唯一不吃值的旗標，要在「少了值就報錯」那一關之前處理，
        //   否則 `sim --closed-loop` 會被判成「--closed-loop 少了值」。
        if (k == "--closed-loop")
        {
            a.closedLoop = true;
            continue;
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
        else if (k == "--power-down-at") a.powerDownAtS = parseD(v);
        else if (k == "--pwm-base")    a.pwmBase = parseD(v);
        else if (k == "--pwm-step")    a.pwmStep = parseD(v);
        else if (k == "--pwm-at")      a.pwmAtS = parseD(v);
        else if (k == "--noise-sigma") p.noiseSigma = parseD(v);
        else if (k == "--lsb")         p.lsb = parseD(v);
        else if (k == "--dead-time")   p.deadTime = parseD(v);
        else if (k == "--setpoint")      a.setpoint = parseD(v);
        else if (k == "--ctrl-ts")       a.ctrlTs = parseD(v);
        else if (k == "--kp")            c.pi.kp = parseD(v);
        else if (k == "--ki")            c.pi.ki = parseD(v);
        else if (k == "--kd")            c.pi.kd = parseD(v);
        else if (k == "--out-min")       c.pi.outMin = parseD(v);
        else if (k == "--out-max")       c.pi.outMax = parseD(v);
        else if (k == "--integral-min")  c.pi.integralMin = parseD(v);
        else if (k == "--integral-max")  c.pi.integralMax = parseD(v);
        else if (k == "--slew-neg")      c.pi.slewNeg = parseD(v);
        else if (k == "--slew-pos")      c.pi.slewPos = parseD(v);
        else if (k == "--tracking-time") c.pi.trackingTimeS = parseD(v);
        else if (k == "--anti-windup")   c.antiWindup = v;
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

    // ★ W7：第二段階躍（降回 base）。時序顛倒或沒有第一段就直接報錯 ——
    //   安靜接受一個不可能的負載曲線，產出的 CSV 看起來完全正常，
    //   而它會被拿去畫 Fig 3。
    if (a.powerDownAtS >= 0.0 &&
        (a.powerAtS < 0.0 || a.powerDownAtS <= a.powerAtS))
    {
        std::fprintf(stderr,
                     "--power-down-at (%g) 需要一個更早的 --power-at (%g)："
                     "沒有先上去，就沒有「降回來」可言。\n",
                     a.powerDownAtS, a.powerAtS);
        return 2;
    }

    int stepsPerCtrl = 1;
    if (a.closedLoop)
    {
        // ⚠️ 閉環時 PWM 由控制器決定，--pwm-at 不會有任何作用。
        //    安靜忽略它的話，你會拿到一份「以為有 PWM 階躍」的閉環資料 ——
        //    那種 CSV 看起來完全正常，而且會被拿去畫圖。
        if (a.pwmAtS >= 0.0)
        {
            std::fprintf(stderr,
                         "--closed-loop 與 --pwm-at 互斥：閉環的 PWM 由控制器"
                         "決定，給了 --pwm-at 也不會生效。\n");
            return 2;
        }

        if (a.ctrlTs <= 0.0)
        {
            std::fprintf(stderr, "--ctrl-ts 必須為正\n");
            return 2;
        }

        // ★★ 控制週期必須是 dt 的整數倍，不整除就停。
        //
        //    不擋的話：ctrl-ts=0.15、dt=0.1 → 每 lround(1.5)=2 步更新一次，
        //    也就是**實際控制週期 0.2 s**，但傳給 PI 的 ts 是 0.15 ——
        //    積分項會系統性地少算 25%，而且沒有任何錯誤訊息。
        //    這正是 W5 教會我的那個 ts 盲區：乘錯一個時間常數不會崩潰，
        //    只會讓每個數字都偏一點點。
        const double ratio = a.ctrlTs / a.dt;
        const double rounded = std::round(ratio);
        if (rounded < 1.0 || std::fabs(ratio - rounded) > 1e-9)
        {
            std::fprintf(stderr,
                         "--ctrl-ts (%g) 必須是 --dt (%g) 的正整數倍，"
                         "現在的比值是 %g。\n",
                         a.ctrlTs, a.dt, ratio);
            return 2;
        }
        stepsPerCtrl = static_cast<int>(rounded);

        if (!parseAntiWindup(c.antiWindup, c.pi.antiWindup))
        {
            std::fprintf(stderr,
                         "不認得的 --anti-windup: %s\n"
                         "合法值：none clamp conditional backcalc parity\n",
                         c.antiWindup.c_str());
            return 2;
        }

        // ★ 控制器的 ts 是 ctrlTs，不是 dt。這一行就是本週的重點。
        c.pi.ts = a.ctrlTs;

        // 符號警告而不是報錯：W5 的符號檢查實驗**刻意**要跑正的 kp，
        // 擋掉的話那個實驗就做不了。但沉默也不行 —— 正回饋的症狀是
        // 「鎖在起始誤差那一邊」，看起來像收斂，不像發散。
        if (c.pi.kp > 0.0 || c.pi.ki > 0.0)
        {
            std::fprintf(stderr,
                         "⚠️ kp=%g ki=%g 有正值。temp 迴路的誤差定義是 "
                         "setpoint-input，係數要用負的，否則是正回饋。\n",
                         c.pi.kp, c.pi.ki);
        }
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

    // ★ W7 的新參數**只在有用到時**追加一行 —— 開環 stderr 的既有排列
    //   一個 byte 都不能動（exp01 的 meta 已進 git，理由見下一段註解）。
    if (a.powerDownAtS >= 0.0)
    {
        std::fprintf(stderr, "power_down_at=%g\n", a.powerDownAtS);
    }

    // ★ 閉環的參數**追加**在後面，不插進上面那一段。
    //
    //   理由：bench/exp01_sysid.py 把整份 stderr 存成 meta 檔，而那些 meta
    //   檔已經在 git 裡、Fig 1 的可重現性靠它們。開環模式多印一行（哪怕是
    //   `mode=open-loop`）都會讓「重跑 exp01 得到同一份 meta」變成假的。
    //   **既有的證據不因為新功能而改變** —— 這是加功能時最容易忽略的一條。
    if (a.closedLoop)
    {
        std::fprintf(stderr,
                     "closed_loop=1\nsetpoint=%g\nctrl_ts=%g\n"
                     "steps_per_ctrl=%d\nkp=%g\nki=%g\nkd=%g\n"
                     "out_min=%g\nout_max=%g\n"
                     "integral_min=%g\nintegral_max=%g\n"
                     "slew_neg=%g\nslew_pos=%g\ntracking_time_s=%g\n"
                     "anti_windup=%s\n",
                     a.setpoint, a.ctrlTs, stepsPerCtrl, c.pi.kp, c.pi.ki,
                     c.pi.kd, c.pi.outMin, c.pi.outMax, c.pi.integralMin,
                     c.pi.integralMax, c.pi.slewNeg, c.pi.slewPos,
                     c.pi.trackingTimeS, c.antiWindup.c_str());
    }

    thermal::ThermalPlant plant(p, a.dt, a.seed);
    control::Pi pi(c.pi);

    // CSV 標頭 —— ★ 欄位名一旦定下來就不要改，bench/*.py 依賴它。
    //
    // ⚠️ 閉環**多一欄** `integral`，開環沒有。兩種 schema 是刻意的：
    //    開環的積分項恆為 0（根本沒有控制器），多輸出一欄零除了讓
    //    exp01 那五份已經進 git 的 CSV 全部作廢之外沒有任何好處。
    //    W7 的 Fig 3 第三面板（積分軌跡）吃的就是閉環這一欄。
    if (a.closedLoop)
    {
        std::printf("t_s,pwm,power_w,t_sense_c,t_die_c,rpm,fan_power_rel,"
                    "integral\n");
    }
    else
    {
        std::printf("t_s,pwm,power_w,t_sense_c,t_die_c,rpm,fan_power_rel\n");
    }

    // 閉環第一次呼叫控制器時還沒有量測值可用。plant 的感測器初值就是環境
    // 溫度（thermal_plant.cpp: `tSense_(p.tAmb)`），所以用它 —— 不要用
    // setpoint（那等於假裝一開機就已經到位，第一步的誤差會是假的 0）。
    double lastSensed = p.tAmb;
    double pwm = a.pwmBase;

    const int n = static_cast<int>(a.seconds / a.dt);
    for (int i = 0; i < n; ++i)
    {
        const double t = i * a.dt;

        // 負載曲線：base →（power-at）step →（power-down-at）base。
        // 上去製造飽和、降回來讓飽和解除 —— recover_s 量的就是解除後那段。
        double pw = a.powerBase;
        if (a.powerAtS >= 0.0 && t >= a.powerAtS)
        {
            pw = a.powerStep;
        }
        if (a.powerDownAtS >= 0.0 && t >= a.powerDownAtS)
        {
            pw = a.powerBase;
        }

        if (a.closedLoop)
        {
            // ★ 控制器只在它自己的取樣時刻更新；其餘時間 PWM 保持不變。
            //   這就是「零階保持」，也是真實 swampd 的行為。
            if (i % stepsPerCtrl == 0)
            {
                pwm = pi.step(lastSensed, a.setpoint);
            }
        }
        else
        {
            pwm = (a.pwmAtS >= 0.0 && t >= a.pwmAtS) ? a.pwmStep : a.pwmBase;
        }

        lastSensed = plant.step(pwm, pw);

        if (a.closedLoop)
        {
            std::printf("%.3f,%.4f,%.4f,%.4f,%.4f,%.2f,%.6f,%.6f\n", t, pwm,
                        pw, lastSensed, plant.dieTemp(), plant.rpm(),
                        plant.fanPowerRel(), pi.integral());
        }
        else
        {
            std::printf("%.3f,%.4f,%.4f,%.4f,%.4f,%.2f,%.6f\n", t, pwm, pw,
                        lastSensed, plant.dieTemp(), plant.rpm(),
                        plant.fanPowerRel());
        }
    }
    return 0;
}
