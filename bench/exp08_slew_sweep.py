"""exp08：slew rate limit 掃描 —— 聲學 / 熱裕度 / 功耗的三方取捨（Fig 5）。

⚠️ 編號：計畫寫的是 `exp05_slew_sweep`，但 exp05 在 W6 已經給了 λ 整定。
   實驗一律按執行順序編號（見 exp05_tuning.py 開頭與 docs/measurement.md §4.0）。
   claims.json 的 `reversals_reduction_ratio` 在 2026-08-09 稽核時就已把
   source 指向 `exp08_*`，今天只是照走。

實驗協定（七欄，定義見 docs/measurement.md）
--------------------------------------------------
假設     : slew 越緊（值越小），PWM 方向反轉次數越少（聽覺越平順），
           但負載切換時風扇跟不上 → 峰值溫度上升。
           相對風扇功耗的方向**事先不確定**：slew 拖慢上衝（省）也拖慢
           回降（費）—— 這正是要掃描而不是猜兩個點的理由。
自變因   : slewNeg / slewPos（成對對稱：−S / +S）—— 唯一。0 = 不限制。
控制變因 : plant 參數全預設、★ Kp/Ki 固定在 λ=0.5τ（不是 W6 部署選定的
           2.0τ —— 這是刻意偏離，理由見下）、
           integralLimit 固定 [0, 100]（W7 的 tuned 側）、outLim [0, 100]、
           setpoint 65 °C、控制器取樣 1.0 s、dt 0.1 s、
           ★ anti-windup 固定 **parity**（上游語意；理由見下）、
           ★ 負載固定 square：150 W ↔ 250 W，全週期 240 s，自 t=300 s 起
           兩層機器檢查（check_single_variable）：
             ① 同一組 slew 的五次執行，除 seed 外逐項相同
             ② 八組 slew 之間，除 slew_neg/slew_pos 外逐項相同
應變因   : reversals_per_min（聲學代理）、t_peak_c（熱裕度代價）、
           fan_power_rel（相對功耗，N³ 模型推算不是量到的瓦數）
重複     : 5 個 seed（0~4），報中位數與 min~max
原始資料 : bench/data/exp08_slew<S>_seed<K>.csv
產圖     : python bench/plot.py --fig 5

★★ 為什麼整定基準是 λ=0.5τ，不是 W6 部署選定的 λ=2.0τ（偏離計畫）
------------------------------------------------------------------
先導試探（2026-08-11，設計階段，參數同本檔但 λ=2.0τ、週期 120 s）：
八組 slew 的 reversals_per_min **全部相同**（1.0/min），slew ≥ 1 的五組連
t_peak_c 都逐位相同 —— slew 在低增益整定上是**死旋鈕**。機制：

  · λ=2.0τ 的雜訊步幅 ≈ σ√2·Kc ≈ 0.10 %PWM —— slew 要 < 0.1 %/s
    才咬得到雜訊，而那時追蹤已經癱瘓（20% 的負載沿要走 200 s）。
  · 追方波只需要 ~0.33 %/s 的平均斜率，slew ≥ 0.5 連負載沿都咬不到。

也就是說：slew 要治的病（高頻方向反轉）是**高增益的病**；W6 部署選了
低增益，病已經用 λ 治掉了。在已經安靜的整定上掃 slew，量到的只有
「無效果」。所以本實驗回答的是取捨空間的另一條邊：

  Fig 2：付出峰值溫度，用 λ 放大買安靜（整條閉環響應都變慢）。
  Fig 5：留在 λ=0.5τ（峰值好），用 slew 選擇性地砍高斜率事件 ——
         聲學買到多少、峰值付出多少，兩條購買路線才有得比。

W7 教訓 #1 原話：「對照的差異只在機制有機會生效的區段顯形，
實驗設計的一半工作是製造那個區段」—— 這裡的「區段」就是高增益整定。

★ 為什麼 anti-windup 用 parity 而不是 exp05/exp07 的 clamp
----------------------------------------------------------
Fig 5 宣稱量的是**上游 slew 機制**的取捨。上游 `ec::pid()` 在
「slewNeg 或 slewPos 有設定」時，每一輪都把積分回算成
`integralTerm = output − proportionalTerm` —— 這個回算**本身就是
被量機制的一部分**（它讓積分不會在 slew 鉗制期間堆積）。
`controller/pi.cpp` 的通用路徑（clamp 等模式）slew 之後不做這個回算，
行為與上游不同。parity 路徑是「上游此刻的行為」，證據鏈在 W5：
72 組參數與真上游編譯單元逐步一致到 1e-12（test_parity_upstream.cpp）、
mutation C1~C5 守著。exp05/exp07 用 clamp 沒有問題 —— 它們的 slew
全為 0，回算不觸發，兩條路徑等價；slew 一開就不等價了。

★ 為什麼負載是方波而不是單階躍（Fig 2/Fig 3 都是單階躍）
--------------------------------------------------------
單階躍的穩態段只剩感測雜訊在動：slew 對雜訊的抑制量得到，但
「跟不上熱瞬變」的代價顯不出來 —— 沒有瞬變可以跟不上，各組的
t_peak_c 會疊在一起，「取捨」就不成立（W6 已證 reversals 對 λ 不敏感，
量到的是雜訊的時間結構）。方波讓控制器一直有追蹤任務。
sine 也能做到，但方波的機制在圖上直接可見：每個沿之後，不限 slew 的
組立刻跳、限 slew 的組以固定斜率爬 —— 讀者不需要頻域知識就看得懂。
（計畫還列了 sine 選項；沒有實驗消費它，所以 sim.cpp 只實作 square。）

★ 為什麼全週期是 240 s（半週期 120 s）
--------------------------------------
λ=0.5τ 的閉環時間常數 ≈ 22 s、穩定 ≈ 3λ ≈ 66 s < 半週期 120 s ——
每個電平段都是「先追、再穩」：追蹤段有大信號斜坡（slew 咬它），
穩態段有雜訊反轉（聲學的主場）。半週期太短（先導試過 60 s）時整段
都在追、永遠到不了穩態，reversals 量到的是軌跡形狀不是雜訊結構
（軌跡單調上升 → 幾乎零反轉，八組都一樣）。
指標的 tail 視窗 120 s（metrics.py 預設）＝ 正好最後一個完整半週期。

★ 為什麼是 250 W 而不是 W6 的 300 W
------------------------------------
可控上限 (65−25)/0.12 = 333.3 W（見 exp05_tuning.py）。W6 的 300 W
留 10% 餘裕是對「不限 slew」的控制器算的；本實驗最緊的組（0.25 %/s）
在沿之後會長時間落後，落後期間溫度比穩態更高、需要的 PWM 峰值也更高。
300 W 會讓緊的組撞進 PWM=100% 飽和 —— 飽和期間輸出不動、反轉為 0，
「聽起來安靜」就成了飽和的假象而不是 slew 的效果。250 W 把整條掃描
留在線性區，每一組的差異才都來自 slew 本身。

★ 為什麼指標只算 t ≥ 300 s：同 exp05（暖機超調不是擾動抑制能力）。
"""

import argparse
import inspect
import json
import pathlib
import statistics
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import metrics  # noqa: E402
import tune  # noqa: E402

SEEDS = [0, 1, 2, 3, 4]

#: 0 = 不限制（基準）。其餘 7 個值以 2 為倍率覆蓋「完全跟不上」到
#: 「幾乎不限」：0.25 %/s 走完一次 ~25% PWM 的負載沿要 100 s（接近全週期，
#: 完全跟不上）；16 %/s 兩個控制步就到位（幾乎等於不限）。
#: ★ 0 不是「最緊」而是「最鬆」—— 它不能畫在數值軸的原點上
#:   （畫圖時作為水平基準線處理，見 plot.py fig5 的註解）。
SLEW_VALUES = [0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0]

LAMBDA_MULT = 0.5            # ★ 高增益側（理由見 docstring；偏離計畫）
SETPOINT = 65.0
POWER_BASE, POWER_STEP = 150.0, 250.0
POWER_AT, POWER_PERIOD = 300.0, 240.0
SECONDS, DT, CTRL_TS = 1500.0, 0.1, 1.0   # 300 暖機 + 5 個全週期
OUT_MIN, OUT_MAX = 0.0, 100.0
INTEGRAL_MIN, INTEGRAL_MAX = 0.0, 100.0
ANTI_WINDUP = "parity"

METRIC_FROM_S = POWER_AT

METRIC_KEYS = ("reversals_per_min", "t_peak_c", "fan_power_rel", "pwm_pp")


def _default_of(fn, name: str):
    """讀函式的預設參數值 —— meta 記錄真正生效的值，不硬編（見 exp05）。"""
    return inspect.signature(fn).parameters[name].default


def run_one(sim: str, slew: float, gains: dict, seed: int,
            out_dir: pathlib.Path) -> tuple[pathlib.Path, dict]:
    """跑一次閉環模擬。回傳 (CSV 路徑, 這次執行生效的參數)。"""
    out = out_dir / f"exp08_slew{slew}_seed{seed}.csv"
    cmd = [
        sim, "--closed-loop",
        "--setpoint", str(SETPOINT),
        "--kp", repr(-gains["Kc"]),
        "--ki", repr(-gains["Ki"]),
        "--ctrl-ts", str(CTRL_TS),
        "--dt", str(DT),
        "--seconds", str(SECONDS),
        "--power-base", str(POWER_BASE),
        "--power-step", str(POWER_STEP),
        "--power-at", str(POWER_AT),
        "--power-profile", "square",
        "--power-period", str(POWER_PERIOD),
        "--out-min", str(OUT_MIN),
        "--out-max", str(OUT_MAX),
        "--integral-min", str(INTEGRAL_MIN),
        "--integral-max", str(INTEGRAL_MAX),
        "--anti-windup", ANTI_WINDUP,
        # ★ 上游語意：slewNeg 是負值、slewPos 是正值、0 = 不限。
        #   對稱掃描（−S/+S）讓自變因是一個純量，圖的橫軸才有唯一定義。
        "--slew-neg", repr(-slew),
        "--slew-pos", repr(slew),
        "--seed", str(seed),
    ]
    with out.open("w") as fh:
        proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE, check=True)
    params = dict(
        line.split("=", 1)
        for line in proc.stderr.decode().splitlines() if "=" in line
    )
    return out, params


def check_single_variable(all_params: dict) -> None:
    """★★ 兩層機器檢查（承 exp05，第三層是本實驗新加的）：

    ① 同一組 slew 內：五次執行除 seed 外逐項相同
    ② 八組之間：除 slew_neg / slew_pos 外逐項相同
    ③ 八組的 (slew_neg, slew_pos) 互不重複 —— exp05 的檢查只比
       「每組 vs 第一組」，兩個非基準組手滑寫成同一個值抓不到；
       這裡組數多（8 組），值又都是手打的浮點，值得多一道。
    """
    for slew in SLEW_VALUES:
        ref_seed = SEEDS[0]
        ref = all_params[(slew, ref_seed)]
        for seed in SEEDS[1:]:
            for key, value in all_params[(slew, seed)].items():
                if key == "seed":
                    continue
                if ref.get(key) != value:
                    raise SystemExit(
                        f"控制變因被破壞（slew={slew} 組內）："
                        f"seed {seed} 的 {key}={value}，"
                        f"但 seed {ref_seed} 是 {ref.get(key)}"
                    )

    base = all_params[(SLEW_VALUES[0], SEEDS[0])]
    allowed = {"slew_neg", "slew_pos"}
    for slew in SLEW_VALUES[1:]:
        other = all_params[(slew, SEEDS[0])]
        for key, value in other.items():
            if key in allowed or key == "seed":
                continue
            if base.get(key) != value:
                raise SystemExit(
                    f"控制變因被破壞（slew 組之間）：slew={slew} 的 "
                    f"{key}={value}，但 slew={SLEW_VALUES[0]} 是 {base.get(key)}"
                )

    pairs = [(all_params[(s, SEEDS[0])].get("slew_neg"),
              all_params[(s, SEEDS[0])].get("slew_pos")) for s in SLEW_VALUES]
    if len(set(pairs)) != len(pairs):
        raise SystemExit(f"自變因有重複：八組的 (slew_neg, slew_pos) = {pairs}")


def metrics_for(csv: pathlib.Path) -> dict:
    """算一份 CSV 的指標。只算 t ≥ 300 s（暖機裁掉，理由見 docstring）。"""
    import pandas as pd
    df = pd.read_csv(csv)
    after = df[df["t_s"] >= METRIC_FROM_S].reset_index(drop=True)
    return {
        "reversals_per_min": metrics.reversals_per_min(after),
        "t_peak_c": metrics.t_peak_c(after),
        "fan_power_rel": metrics.fan_power_rel(after),
        "pwm_pp": metrics.pwm_pp(after),
        "pwm_max": float(after["pwm"].max()),
    }


def summarise_runs(rows: list[dict]) -> dict:
    """五個 seed 的中位數與 min~max（誠實準則第 2 條）。NaN 傳遞，不掩蓋。"""
    out = {}
    for key in (*METRIC_KEYS, "pwm_max"):
        values = [r[key] for r in rows]
        if any(v != v for v in values):          # NaN
            out[key] = {"median": None, "min": None, "max": None,
                        "note": "至少一個 seed 是 NaN"}
        else:
            out[key] = {"median": statistics.median(values),
                        "min": min(values), "max": max(values)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="bench/data")
    ap.add_argument("--sim", default="build/sim")
    ap.add_argument("--fit", default="bench/data/exp01_fit.txt")
    args = ap.parse_args()

    k, tau, theta = tune.load_fit(pathlib.Path(args.fit))
    gains = tune.imc_pi(k, tau, theta, LAMBDA_MULT * tau)
    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_params: dict = {}
    table: dict = {}
    for slew in SLEW_VALUES:
        rows = []
        for seed in SEEDS:
            csv, params = run_one(args.sim, slew, gains, seed, out_dir)
            all_params[(slew, seed)] = params
            rows.append(metrics_for(csv))
            print(f"wrote {csv}")
        table[str(slew)] = {
            "metrics": summarise_runs(rows),
            "per_seed": {str(s): r for s, r in zip(SEEDS, rows, strict=True)},
        }

    check_single_variable(all_params)
    print(f"控制變因檢查通過：組內只有 seed 不同、組間只有 slew_neg/slew_pos "
          f"不同、八組互不重複（{len(SLEW_VALUES)} × {len(SEEDS)} = "
          f"{len(SLEW_VALUES) * len(SEEDS)} 次執行）")

    # 對 unlimited（slew=0）的反轉率下降比 —— claims 的
    # reversals_reduction_ratio 從這張表挑「選定的 slew」來填，
    # 選定本身是看完 Fig 5 的取捨曲線之後的人工決定，不在這裡自動挑。
    # ★ 主數字是**按 seed 配對**的比值中位數（W7 recover_s_ratio 的慣例：
    #   兩組共用同一組 seed，配對消掉 seed 間的水平差異）；
    #   median-of-medians 一併存檔當交叉檢查，兩者應該一致。
    base_seed = table[str(SLEW_VALUES[0])]["per_seed"]
    base_rev = table[str(SLEW_VALUES[0])]["metrics"]["reversals_per_min"]["median"]
    ratios = {}
    for slew in SLEW_VALUES[1:]:
        per = table[str(slew)]["per_seed"]
        paired = [base_seed[s]["reversals_per_min"] / per[s]["reversals_per_min"]
                  for s in per
                  if per[s]["reversals_per_min"] and
                  base_seed[s]["reversals_per_min"] == base_seed[s]["reversals_per_min"]]
        rev = table[str(slew)]["metrics"]["reversals_per_min"]["median"]
        ratios[str(slew)] = {
            "paired_median": (statistics.median(paired) if paired else None),
            "paired_min": (min(paired) if paired else None),
            "paired_max": (max(paired) if paired else None),
            "median_of_medians": (None if not rev or base_rev is None
                                  else base_rev / rev),
        }

    meta = {
        "experiment": "exp08_slew_sweep",
        "fopdt": {"k": k, "tau": tau, "theta": theta, "source": args.fit},
        "lambda_mult": LAMBDA_MULT,
        "gains": {**gains, "kp_used": -gains["Kc"], "ki_used": -gains["Ki"]},
        "setpoint_c": SETPOINT,
        "power_w": {"base": POWER_BASE, "step": POWER_STEP, "at_s": POWER_AT,
                    "profile": "square", "period_s": POWER_PERIOD},
        "controllable_power_limit_w": (SETPOINT - 25.0) / 0.12,
        "ctrl_ts_s": CTRL_TS,
        "dt_s": DT,
        "seconds": SECONDS,
        "seeds": SEEDS,
        "slew_values": SLEW_VALUES,
        "out_lim": [OUT_MIN, OUT_MAX],
        "integral_limit": [INTEGRAL_MIN, INTEGRAL_MAX],
        "anti_windup": ANTI_WINDUP,
        "metrics_computed_from_s": METRIC_FROM_S,
        "metric_settings": {
            "reversals_deadband": _default_of(metrics.reversals_per_min,
                                              "deadband"),
            "reversals_tail_s": _default_of(metrics.reversals_per_min, "tail_s"),
            "pwm_pp_tail_s": _default_of(metrics.pwm_pp, "tail_s"),
        },
        "slew_table": table,
        "reversals_ratio_vs_unlimited": ratios,
        "repo_commit": subprocess.getoutput("git rev-parse --short HEAD"),
        "sim_params": {str(s): all_params[(s, SEEDS[0])] for s in SLEW_VALUES},
    }
    meta_path = out_dir / "exp08_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {meta_path}")

    print()
    print(f"{'slew':>7} {'rev/min':>9} {'ratio_vs_0':>10} {'Tpeak':>8}"
          f" {'fanpow':>8} {'pwm_pp':>8} {'pwm_max':>8}")
    for slew in SLEW_VALUES:
        m = table[str(slew)]["metrics"]

        def med(key, m=m):
            v = m[key]["median"]
            return "NaN" if v is None else f"{v:.3f}"

        entry = ratios.get(str(slew))
        ratio = entry["paired_median"] if entry else None
        ratio_s = "-" if ratio is None else f"{ratio:.2f}"
        print(f"{slew:>7} {med('reversals_per_min'):>9} {ratio_s:>10}"
              f" {med('t_peak_c'):>8} {med('fan_power_rel'):>8}"
              f" {med('pwm_pp'):>8} {med('pwm_max'):>8}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
