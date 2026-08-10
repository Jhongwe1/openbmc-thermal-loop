"""從 FOPDT 參數算 IMC-PI 係數。**λ 是唯一旋鈕。**

為什麼不是 Ziegler–Nichols
--------------------------
ZN 的設計目標是**四分之一衰減比**（約 25% 超調），為「快」犧牲穩定度。
風扇熱控的成本函數剛好相反：

  · 超調在熱控上意義不大（溫度過低不會壞），**但風扇轉速震盪使用者聽得見**
  · 熱時間常數數十秒，追求快沒有價值
  · 有可觀死區時間時 ZN 本來就容易過度激進
  · ★ **實務上也做不了**：ZN 要把系統推到臨界持續振盪，而真實迴路有
    slew limit 與輸出飽和，量不到乾淨的 Ku、Tu

所以走：開環階躍 → 擬 FOPDT（W4，見 bench/data/exp01_fit.txt）
        → λ 整定（本檔）→ 閉環階躍驗證（exp05）。

公式（IMC-PI，一階加死區）
--------------------------
    Kc = τ / ( |K| · (λ + θ) )
    Ti = τ
    Ki = Kc / Ti

λ 的物理意義是**期望的閉環時間常數**。θ 出現在分母，代表死區越大、
增益就得越保守 —— 這是公式自己告訴你的，不是調出來的。

  | λ        | 效果                     | 適用           |
  |----------|--------------------------|----------------|
  | 0.5τ     | 快、有超調               | 追求響應速度   |
  | 1.0τ     | 平衡                     | 一般           |
  | **2.0τ** | 慢、幾乎無超調、風扇平順 | **本專案採用** |

⚠️ 符號：上游 `ec::pid()` 的誤差定義是 `error = setpoint − input`，
   而 `temp` 型別的製程增益 K 是**負的**（風扇越快溫度越低）。
   所以實際填進設定檔的係數是 **−Kc**。證據見 bench/data/exp02_signcheck/。
   這裡回傳的 Kc **恆為正**（公式用 |K|），取負號是呼叫端的責任 ——
   分開才看得出「哪一步在做符號」。

用法
----
    python bench/tune.py                      # 讀 exp01_fit.txt，印三組
    python bench/tune.py --lambda-mult 2.0    # 只印一組
    python bench/tune.py --json               # 給實驗腳本吃
"""

import argparse
import json
import pathlib
import sys

#: L1 模擬的 PWM→RPM 斜率 (RPM/%PWM)。
#: plant/thermal_plant.cpp: `rpmCmd = rpmMax * (pwm / 100.0)`，rpmMax = 15000。
RPM_PER_PCT = 150.0

DEFAULT_FIT = pathlib.Path("bench/data/exp01_fit.txt")


def imc_pi(k: float, tau: float, theta: float, lam: float) -> dict:
    """IMC-PI。回傳的 Kc **恆為正**（用 |K|）。

    ⚠️ 三個容易寫錯而且不會報錯的地方，各有一條測試守著：
       ① `λ + θ` 寫成 `λ − θ`：λ 大的時候仍然給出合理數字
       ② `Ki = Kc / Ti` 寫成 `Kc * Ti`：量級差好幾個數量級，
          但因為輸出還是會被 outLim 箝住，圖上看起來只是「比較兇」
       ③ 忘了 `abs(k)`：K 是負的 → Kc 變負 → 呼叫端再取一次負號
          → **符號錯兩次變成對的**，而你完全不知道自己錯過
    """
    if tau <= 0.0:
        raise ValueError(f"tau 必須為正，收到 {tau}")
    if theta < 0.0:
        raise ValueError(f"theta 不可為負，收到 {theta}")
    if lam <= 0.0:
        raise ValueError(f"lambda 必須為正，收到 {lam}")
    if k == 0.0:
        raise ValueError("K = 0：這個系統的輸入對輸出沒有作用，算不出 PI 係數")

    kc = tau / (abs(k) * (lam + theta))
    ti = tau
    return {"lambda_s": lam, "Kc": kc, "Ti": ti, "Ki": kc / ti}


def to_swampd_rpm(gains: dict, rpm_per_pct: float = RPM_PER_PCT) -> dict:
    """把 L1 的係數（%PWM/°C）換算成 swampd 外圈的係數（RPM/°C）。

    ★★ 為什麼需要換算 —— 這是 L1/L2 疊圖最容易踩的坑

      · **L1**（bench/sim）是單迴路：控制器直接輸出 PWM，
        所以 Kc 的單位是 `%PWM/°C`（因為 K 的單位是 `°C/%PWM`）
      · **L2**（swampd）是串級：外圈熱 PID 輸出的是 **RPM setpoint**，
        再交給內圈風扇 PID 去追，所以它的 Kc 單位是 `RPM/°C`

      **同一組「λ 係數」填進兩邊會差 150 倍**，而症狀是
      「L2 的輸出永遠貼在 outLim 上」——看起來像飽和，其實是量綱錯。

    ⚠️ 這個換算成立的前提（**這就是串級控制的設計假設本身**）：
       把內圈當成一個**靜態增益** `150 RPM/%PWM`，也就是假設
       「內圈快到外圈看不見它的動態」。swampd 的內圈 10 Hz、外圈 1 Hz，
       相差 10 倍，這個假設大致成立 —— 但**不是完全成立**，
       而那個殘差正是 docs/cascade.md 要量的東西。

    ⚠️ 換算忽略了兩個真實的非線性：
       ① 起轉死區 `pwmMinSpin = 12%`（低於它風扇不轉）
       ② 風扇機械慣性 `tauFan`
       所以這是**近似**，不是等式。用它來對齊 L1/L2 時要記得。
    """
    return {
        "lambda_s": gains["lambda_s"],
        "Kc_rpm_per_c": gains["Kc"] * rpm_per_pct,
        "Ti": gains["Ti"],
        "Ki_rpm_per_c_s": gains["Ki"] * rpm_per_pct,
        "rpm_per_pct": rpm_per_pct,
    }


def load_fit(path: pathlib.Path) -> tuple:
    """讀 exp01 的擬合結果。**不接受手動輸入的 K/τ/θ 當預設值。**

    ★ 為什麼一定要從檔案讀
      係數是從 Fig 1 的量測長出來的。允許手打的話，總有一天圖上的
      「λ = 2τ」會對應到一組不是從那份 CSV 算出來的數字，
      而**那張圖看起來完全正常**。CLI 仍留 --k/--tau/--theta 覆寫，
      但它們會在輸出裡標成 override —— 蓋掉可以，蓋得無聲不行。
    """
    if not path.exists():
        raise SystemExit(
            f"找不到 {path} —— 它由 W4 的 bench/exp01_sysid.py 產生。"
            "λ 整定的唯一輸入是那份擬合結果，沒有它算不了。"
        )
    fit = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            fit[key.strip()] = value.strip()
    try:
        return float(fit["k"]), float(fit["tau"]), float(fit["theta"])
    except KeyError as exc:
        raise SystemExit(f"{path} 缺少 {exc} 欄") from exc


def main() -> int:
    ap = argparse.ArgumentParser(description="FOPDT -> IMC-PI 係數")
    ap.add_argument("--fit", type=pathlib.Path, default=DEFAULT_FIT)
    ap.add_argument("--k", type=float, default=None, help="覆寫製程增益 K")
    ap.add_argument("--tau", type=float, default=None, help="覆寫時間常數 τ")
    ap.add_argument("--theta", type=float, default=None, help="覆寫死區 θ")
    ap.add_argument("--lambda-mult", type=float, action="append", default=None,
                    help="λ = 這個倍數 × τ。可重複，預設 0.5 1.0 2.0")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    k, tau, theta = load_fit(a.fit)
    overrides = {}
    if a.k is not None:
        k, overrides["k"] = a.k, a.k
    if a.tau is not None:
        tau, overrides["tau"] = a.tau, a.tau
    if a.theta is not None:
        theta, overrides["theta"] = a.theta, a.theta

    mults = a.lambda_mult or [0.5, 1.0, 2.0]
    rows = []
    for mult in mults:
        g = imc_pi(k, tau, theta, mult * tau)
        rows.append({
            "lambda_mult": mult,
            **g,
            # 填進設定檔的值：temp 型別要取負（見模組 docstring）
            "kp_used_pwm": -g["Kc"],
            "ki_used_pwm": -g["Ki"],
            "swampd": to_swampd_rpm(g),
        })

    if a.json:
        print(json.dumps({
            "fopdt": {"k": k, "tau": tau, "theta": theta},
            "overrides": overrides,
            "source": str(a.fit),
            "rows": rows,
        }, indent=2))
        return 0

    if overrides:
        print(f"⚠️ 覆寫（不是來自 {a.fit}）：{overrides}", file=sys.stderr)
    print(f"# FOPDT  K={k:.6f} °C/%PWM  tau={tau:.4f} s  theta={theta:.4f} s")
    print(f"# 來源   {a.fit}")
    print()
    print(f"{'λ':>8} {'λ (s)':>10} {'Kc':>10} {'Ti (s)':>10} {'Ki':>10}"
          f" {'kp填入':>10} {'ki填入':>10} {'Kc(RPM/°C)':>12}")
    for r in rows:
        print(f"{r['lambda_mult']:>7.1f}τ {r['lambda_s']:>10.3f}"
              f" {r['Kc']:>10.5f} {r['Ti']:>10.3f} {r['Ki']:>10.6f}"
              f" {r['kp_used_pwm']:>10.5f} {r['ki_used_pwm']:>10.6f}"
              f" {r['swampd']['Kc_rpm_per_c']:>12.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
