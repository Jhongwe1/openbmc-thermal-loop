"""exp05：λ 整定對照 —— 三組 λ 的閉環負載擾動響應。

⚠️ 編號：計畫寫的是 `exp02_tuning`，但 exp02 在 W5 已經給了符號檢查
   （`bench/data/exp02_signcheck/`）、exp03 給了跨層追蹤、exp04 給了注入路徑。
   實驗一律**按執行順序**編號，不按計畫的章節順序 ——
   重編一個已經有資料的號碼，等於讓舊圖的 caption 指向新資料。
   （見 docs/measurement.md §4.0 與 bench/claims.json 的 note）

實驗協定（七欄，定義見 docs/measurement.md）
--------------------------------------------------
假設     : λ 越大 → 閉環增益越低 → **負載擾動下的峰值偏差越大、
           穩定越慢，但穩態 PWM 的抖動幅度越小**。
           ★ 注意方向：這是**擾動抑制**不是 setpoint 追蹤。
             setpoint 階躍時「高增益 → 超調大」；負載擾動時剛好相反，
             高增益壓得住偏差。計畫 §4 的驗收標準寫的是前者，
             照抄會得到「趨勢相反」的結論然後去查一個沒錯的符號。
             （見 LOG.md 2026-08-11）
自變因   : λ（唯一）—— 透過 IMC-PI 換算成 Kc/Ki，其他一切不動
控制變因 : plant 參數全預設、setpoint 65 °C、
           負載 150 W → 300 W @ 300 s、控制器取樣 1.0 s、dt 0.1 s、
           anti-windup 固定 clamp、integralLimit 固定 [0, 100]、slew 固定 0
           ★ 兩層機器檢查（見 check_single_variable）：
             ① 同一組 λ 的五次執行，除 seed 外逐項相同
             ② 三組 λ 之間，除 kp/ki 外逐項相同
應變因   : overshoot_c / settle_s / pwm_pp / reversals_per_min /
           fan_power_rel / t_peak_c —— 全部來自 bench/metrics.py
重複     : 5 個 seed（0~4），報中位數與 min~max
原始資料 : bench/data/exp05_tuning_lam<L>tau_seed<K>.csv
產圖     : python bench/plot.py --fig 2

★ 為什麼負載階躍是 300 W 而不是計畫寫的 400 W
----------------------------------------------
不是試出來的，是**從 plant 參數算出來的**：

    可控功率上限 = (setpoint − t_amb) / rth_min = (65 − 25) / 0.12 = 333.3 W

超過它，風扇滿速也壓不到 setpoint —— **不管控制器多好**。
實測 400 W 時三組 λ 的 PWM 全部貼在 100%、settle_s 全是 NaN，
三條線疊在一起，**這張圖會什麼都證明不了**。

300 W 留了 10% 餘裕（滿速穩態 61 °C），實測三組的 PWM 峰值 93~96%，
控制律有作用空間。**400 W 那個極端留給 W7 的 Fig 3 —— 那裡就是要飽和。**
「Fig 2 要不飽和、Fig 3 要飽和」這個區分本身就是實驗設計，寫在
docs/measurement.md。

★ 為什麼指標只算階躍之後
------------------------
軌跡從冷機（25 °C）開始，前 100 秒有一段暖機超調，峰值比階躍造成的
峰值還可能高。把它算進 `t_peak_c` / `overshoot_c`，量到的就是
「開機行為」而不是「擾動抑制能力」，而**三組 λ 的開機行為差異很小**。

原始 CSV 保留全程（資料完整），裁切只發生在算指標的時候，
裁切點記在 meta 裡。
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
LAMBDA_MULTS = [0.5, 1.0, 2.0]

SETPOINT = 65.0
POWER_BASE, POWER_STEP, POWER_AT = 150.0, 300.0, 300.0
SECONDS, DT, CTRL_TS = 1200.0, 0.1, 1.0

#: L1 控制器的輸出是 PWM 百分比，所以積分箝位的量綱也是百分比。
#: 上界 = outMax（**絕對值**，不是 outMax−outMin 的寬度）——
#: 這個區別在 L1 看不出來（outMin 剛好是 0），但在 swampd 那側
#: outLim 是 3000~15000，寫錯就會把輸出鎖在 12000 RPM。
#: 完整推導見 config/swampd/README.md。
OUT_MIN, OUT_MAX = 0.0, 100.0
INTEGRAL_MIN, INTEGRAL_MAX = 0.0, 100.0
ANTI_WINDUP = "clamp"

#: 指標的計算起點。全程資料仍然完整寫進 CSV。
METRIC_FROM_S = POWER_AT

METRIC_KEYS = ("overshoot_c", "settle_s", "pwm_pp", "reversals_per_min",
               "fan_power_rel", "t_peak_c")


def _default_of(fn, name: str):
    """讀一個函式的預設參數值。

    ★ 不硬編。meta 要記錄的是**真正生效的** deadband / tail_s，
      而它們的唯一定義在 bench/metrics.py。抄一份到這裡，
      改了那邊卻沒改這裡的那天，meta 會安靜地說謊。
    """
    return inspect.signature(fn).parameters[name].default


def run_one(sim: str, lam_mult: float, gains: dict, seed: int,
            out_dir: pathlib.Path) -> tuple[pathlib.Path, dict]:
    """跑一次閉環模擬。回傳 (CSV 路徑, 這次執行生效的參數)。"""
    out = out_dir / f"exp05_tuning_lam{lam_mult}tau_seed{seed}.csv"
    cmd = [
        sim, "--closed-loop",
        "--setpoint", str(SETPOINT),
        # ★ temp 型別 + error = setpoint − input ⇒ 係數取負（W5 的符號檢查）
        "--kp", repr(-gains["Kc"]),
        "--ki", repr(-gains["Ki"]),
        "--ctrl-ts", str(CTRL_TS),
        "--dt", str(DT),
        "--seconds", str(SECONDS),
        "--power-base", str(POWER_BASE),
        "--power-step", str(POWER_STEP),
        "--power-at", str(POWER_AT),
        "--out-min", str(OUT_MIN),
        "--out-max", str(OUT_MAX),
        "--integral-min", str(INTEGRAL_MIN),
        "--integral-max", str(INTEGRAL_MAX),
        "--anti-windup", ANTI_WINDUP,
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
    """★★ 把「自變因只有一個」變成程式會檢查的事 —— 這裡要檢查**兩層**。

    ① 同一組 λ 內：五次執行除了 seed 以外逐項相同
    ② 三組 λ 之間：除了 kp / ki 以外逐項相同

    第二層是 exp01 沒有的。少了它，「我只改了 λ」就只是我的說法：
    真正會發生的事是某次手滑把 --seconds 一起改了，
    而**那批資料看起來完全正常**。

    ⚠️ 允許不同的鍵刻意寫死成 {"kp", "ki"}，不是「凡是不同就放行」。
       λ 本身不在 sim 的參數裡（它只透過 Kc/Ki 生效），所以這裡
       比對的是**真正送進控制器的東西**，不是我以為我送了什麼。
    """
    for mult in LAMBDA_MULTS:
        ref_seed = SEEDS[0]
        ref = all_params[(mult, ref_seed)]
        for seed in SEEDS[1:]:
            for key, value in all_params[(mult, seed)].items():
                if key == "seed":
                    continue
                if ref.get(key) != value:
                    raise SystemExit(
                        f"控制變因被破壞（λ={mult}τ 組內）："
                        f"seed {seed} 的 {key}={value}，"
                        f"但 seed {ref_seed} 是 {ref.get(key)}"
                    )

    base = all_params[(LAMBDA_MULTS[0], SEEDS[0])]
    allowed = {"kp", "ki"}
    for mult in LAMBDA_MULTS[1:]:
        other = all_params[(mult, SEEDS[0])]
        for key, value in other.items():
            if key in allowed or key == "seed":
                continue
            if base.get(key) != value:
                raise SystemExit(
                    f"控制變因被破壞（λ 組之間）：λ={mult}τ 的 {key}={value}，"
                    f"但 λ={LAMBDA_MULTS[0]}τ 是 {base.get(key)}"
                )
        for key in allowed:
            if base.get(key) == other.get(key):
                raise SystemExit(
                    f"自變因沒有變：λ={mult}τ 與 λ={LAMBDA_MULTS[0]}τ 的 "
                    f"{key} 都是 {other.get(key)} —— 這批資料不是三組不同的整定"
                )


def metrics_for(csv: pathlib.Path) -> dict:
    """算一份 CSV 的六個指標。**只算階躍之後**，理由見模組 docstring。"""
    import pandas as pd
    df = pd.read_csv(csv)
    after = df[df["t_s"] >= METRIC_FROM_S].reset_index(drop=True)
    m = metrics.summarise(after, SETPOINT)
    # settle_s 是絕對時刻；換算成「階躍後多久」才讀得懂。NaN 傳遞下去。
    m["settle_after_step_s"] = m["settle_s"] - METRIC_FROM_S
    m["integral_max"] = metrics.integral_max(after)
    m["pwm_max"] = float(after["pwm"].max())
    return m


def summarise_runs(rows: list[dict]) -> dict:
    """五個 seed 的中位數與 min~max。**誠實準則第 2 條：不報最好看的那一次。**

    ⚠️ NaN 要留著。`settle_s` 在系統從未穩定時是 NaN，
       用 0 或最大值代替會讓「沒穩定」在指標表上消失。
       中位數遇到 NaN 就整組報 NaN —— 那是正確的行為。
    """
    out = {}
    for key in (*METRIC_KEYS, "settle_after_step_s", "integral_max", "pwm_max"):
        values = [r[key] for r in rows]
        if any(v != v for v in values):          # NaN
            out[key] = {"median": None, "min": None, "max": None,
                        "note": "至少一個 seed 從未穩定（NaN）"}
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
    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_params: dict = {}
    table: dict = {}
    for mult in LAMBDA_MULTS:
        gains = tune.imc_pi(k, tau, theta, mult * tau)
        rows = []
        for seed in SEEDS:
            csv, params = run_one(args.sim, mult, gains, seed, out_dir)
            all_params[(mult, seed)] = params
            rows.append(metrics_for(csv))
            print(f"wrote {csv}")
        table[f"{mult}tau"] = {
            **gains,
            "kp_used": -gains["Kc"],
            "ki_used": -gains["Ki"],
            "swampd_equivalent": tune.to_swampd_rpm(gains),
            "metrics": summarise_runs(rows),
            "per_seed": {str(s): r for s, r in zip(SEEDS, rows, strict=True)},
        }

    check_single_variable(all_params)
    print(f"控制變因檢查通過：組內只有 seed 不同、組間只有 kp/ki 不同"
          f"（{len(LAMBDA_MULTS)} × {len(SEEDS)} = "
          f"{len(LAMBDA_MULTS) * len(SEEDS)} 次執行）")

    meta = {
        "experiment": "exp05_tuning",
        "fopdt": {"k": k, "tau": tau, "theta": theta, "source": args.fit},
        "setpoint_c": SETPOINT,
        "power_w": {"base": POWER_BASE, "step": POWER_STEP, "at_s": POWER_AT},
        "controllable_power_limit_w": (SETPOINT - 25.0) / 0.12,
        "ctrl_ts_s": CTRL_TS,
        "dt_s": DT,
        "seconds": SECONDS,
        "seeds": SEEDS,
        "out_lim": [OUT_MIN, OUT_MAX],
        "integral_limit": [INTEGRAL_MIN, INTEGRAL_MAX],
        "anti_windup": ANTI_WINDUP,
        "metrics_computed_from_s": METRIC_FROM_S,
        "metric_settings": {
            "reversals_deadband": _default_of(metrics.reversals_per_min,
                                              "deadband"),
            "reversals_tail_s": _default_of(metrics.reversals_per_min, "tail_s"),
            "pwm_pp_tail_s": _default_of(metrics.pwm_pp, "tail_s"),
            "settle_band_c": _default_of(metrics.settle_s, "band"),
            "settle_hold_s": _default_of(metrics.settle_s, "hold_s"),
        },
        "lambda_table": table,
        "repo_commit": subprocess.getoutput("git rev-parse --short HEAD"),
        "sim_params": {f"{m}tau": all_params[(m, SEEDS[0])]
                       for m in LAMBDA_MULTS},
    }
    meta_path = out_dir / "exp05_tuning_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {meta_path}")

    print()
    print(f"{'λ':>7} {'Kc':>9} {'Ki':>10} {'peak dev':>9} {'settle':>8}"
          f" {'pwm_pp':>8} {'rev/min':>8} {'fanpow':>8} {'Tpeak':>8}"
          f" {'I_max':>8}")
    for mult in LAMBDA_MULTS:
        e = table[f"{mult}tau"]
        m = e["metrics"]

        def med(key, m=m):
            v = m[key]["median"]
            return "NaN" if v is None else f"{v:.3f}"

        print(f"{mult:>6.1f}τ {e['Kc']:>9.4f} {e['Ki']:>10.6f}"
              f" {med('overshoot_c'):>9} {med('settle_after_step_s'):>8}"
              f" {med('pwm_pp'):>8} {med('reversals_per_min'):>8}"
              f" {med('fan_power_rel'):>8} {med('t_peak_c'):>8}"
              f" {med('integral_max'):>8}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
