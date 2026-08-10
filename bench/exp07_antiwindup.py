"""exp07：anti-windup A/B —— 量化上游既有的積分箝位值多少（L1 側）。

⚠️ 編號：計畫叫它 exp03，但 exp03 在 W5 已經給了跨層追蹤
   （`bench/data/exp03_trace/`）。實驗一律按**執行順序**編號，
   理由見 exp05 頂部與 docs/measurement.md §4.0。

實驗協定（七欄，定義見 docs/measurement.md）
--------------------------------------------------
假設     : 放開積分箝位後，飽和期間積分項持續累加；
           飽和解除（負載降回、溫度回落過 setpoint）之後，
           PWM 需要更久才降下來。預期 recover_s(open) > recover_s(clamp)，
           而**飽和期間兩組的溫度曲線幾乎重合** ——
           兩組輸出都頂在同一個 out_max 上，plant 看到的輸入相同，
           差異只存在於積分這個內部狀態。
自變因   : integralLimit —— 唯一。
           clamp arm [0, 100]（%PWM，鏡射 swampd 的 [0, 15000] RPM ÷ 150）
           open  arm [-1e6, 1e6]（大到永遠夾不到 ＝ 等同關閉）
           ★ 兩組都走 `--anti-windup clamp`：讓「箝位範圍」是唯一的差異，
             與 L2 的設定檔 diff（也只差 integralLimit 兩行）完全同構。
             計畫的做法是 none vs clamp —— 那會同時改兩個旗標；
             none 與「夾不到的 clamp」效果相同但語意不同，取同構的那個。
控制變因 : plant 參數全預設、setpoint 65 °C、Kp/Ki ＝ W6 採用的 λ=2τ 那組、
           負載 150 → 400 W @ 300 s → 150 W @ 900 s、ctrl-ts 1.0 s、dt 0.1 s、
           slew 固定 0、兩組共用 seed {0..4}
           ★ 兩層機器檢查（check_single_variable，與 exp05 同款）：
             ① 同一 arm 的五次執行，除 seed 外逐項相同
             ② 兩 arm 之間，除 integral_min/integral_max 外逐項相同
應變因   : recover_s（主指標）、integral_max、t_peak_c、pwm_max、sat_frac
重複     : 5 seeds，報中位數與 min~max
原始資料 : bench/data/exp07_aw<arm>_seed<K>.csv
產圖     : python bench/plot.py --fig 3

★ 負載為什麼是 400 W（exp05 刻意是 300 W）
------------------------------------------
可控功率上限 = (65−25)/0.12 = 333.3 W（推導見 exp05 頂部；
test_plant.cpp 的 SaturationCaseHolds 守著這個前提）。
400 W 超過它 → 風扇滿速也壓不回 setpoint → 飽和必然發生、積分必然累到頂。
**「Fig 2 要不飽和、Fig 3 要飽和」是實驗設計，不是參數手滑。**

★ 為什麼一定要有第二段階躍（900 s 降回 150 W）
----------------------------------------------
沒有它，只看得到 windup 發生（積分爬升），看不到它的**代價** ——
「溫度已經回落、風扇還在全速」只存在於飽和解除之後，
recover_s 在那之前根本沒有定義。這一段就是整張 Fig 3 的理由。
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

#: arm 名稱 → integralLimit（%PWM 量綱）。這就是整個實驗唯一的自變因。
ARMS = {
    "clamp": (0.0, 100.0),
    "open": (-1e6, 1e6),
}

SETPOINT = 65.0
POWER_BASE, POWER_STEP = 150.0, 400.0
POWER_UP_AT, POWER_DOWN_AT = 300.0, 900.0
SECONDS, DT, CTRL_TS = 1500.0, 0.1, 1.0
OUT_MIN, OUT_MAX = 0.0, 100.0
ANTI_WINDUP = "clamp"

#: W6 採用的整定。exp07 引用它而不是自己選 —— Fig 3 的前提是
#: 「係數固定在 Fig 2 選定的那組」，自變因才只有 integralLimit。
ADOPTED_LAMBDA_KEY = "2.0tau"

METRIC_KEYS = ("recover_s", "integral_max", "t_peak_c", "pwm_max", "sat_frac")


def _default_of(fn, name: str):
    """讀函式的預設參數值 —— 不硬編，理由見 exp05 的同名函式。"""
    return inspect.signature(fn).parameters[name].default


def adopted_gains(meta_path: pathlib.Path, fit_path: pathlib.Path):
    """讀 W6 採用的 Kp/Ki，並用 exp01 的擬合重算一次交叉驗證。

    ★ 為什麼要交叉驗證而不是直接抄：
      exp05 的 meta 是檔案，檔案會過期 —— 如果哪天 exp01 重量測了
      （fit 變了）而 exp05 沒重跑，這裡安靜引用舊 meta 的話，
      「係數來自 Fig 1 的量測」這條證據鏈就斷了而且沒有人知道。
      test_swampd_config.py 守的是設定檔那一份，這裡守 L1 這一份。
    """
    meta = json.loads(meta_path.read_text())
    entry = meta["lambda_table"][ADOPTED_LAMBDA_KEY]
    kp, ki = float(entry["kp_used"]), float(entry["ki_used"])

    k, tau, theta = tune.load_fit(fit_path)
    gains = tune.imc_pi(k, tau, theta, 2.0 * tau)
    for got, want, name in ((kp, -gains["Kc"], "kp"), (ki, -gains["Ki"], "ki")):
        if abs(got - want) > 1e-9 * abs(want):
            raise SystemExit(
                f"exp05 meta 的 {name}={got} 與由 {fit_path} 重算的 {want} "
                "不一致 —— exp01 重量測過但 exp05 沒重跑？先把鏈修好再跑 A/B。")
    return kp, ki


def run_one(sim: str, arm: str, kp: float, ki: float, seed: int,
            out_dir: pathlib.Path) -> tuple[pathlib.Path, dict]:
    """跑一次閉環模擬。回傳 (CSV 路徑, 這次執行生效的參數)。"""
    lim_lo, lim_hi = ARMS[arm]
    out = out_dir / f"exp07_aw{arm}_seed{seed}.csv"
    cmd = [
        sim, "--closed-loop",
        "--setpoint", str(SETPOINT),
        "--kp", repr(kp),
        "--ki", repr(ki),
        "--ctrl-ts", str(CTRL_TS),
        "--dt", str(DT),
        "--seconds", str(SECONDS),
        "--power-base", str(POWER_BASE),
        "--power-step", str(POWER_STEP),
        "--power-at", str(POWER_UP_AT),
        "--power-down-at", str(POWER_DOWN_AT),
        "--out-min", str(OUT_MIN),
        "--out-max", str(OUT_MAX),
        # ★ 自變因只有下面這兩個值
        "--integral-min", repr(lim_lo),
        "--integral-max", repr(lim_hi),
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
    """★★ 「自變因只有一個」的機器版（與 exp05 同款，兩層）。

    ① 同一 arm 內：五次執行除了 seed 以外逐項相同
    ② 兩 arm 之間：除了 integral_min / integral_max 以外逐項相同，
       而且那兩個值**必須**不同 —— 「兩組其實一樣」正是地雷 #10
       （A/B 跑出兩條重疊的線）最無聊也最真實的成因。
    """
    arms = list(ARMS)
    for arm in arms:
        ref = all_params[(arm, SEEDS[0])]
        for seed in SEEDS[1:]:
            for key, value in all_params[(arm, seed)].items():
                if key == "seed":
                    continue
                if ref.get(key) != value:
                    raise SystemExit(
                        f"控制變因被破壞（{arm} 組內）：seed {seed} 的 "
                        f"{key}={value}，但 seed {SEEDS[0]} 是 {ref.get(key)}")

    allowed = {"integral_min", "integral_max"}
    base = all_params[(arms[0], SEEDS[0])]
    other = all_params[(arms[1], SEEDS[0])]
    for key, value in other.items():
        if key in allowed or key == "seed":
            continue
        if base.get(key) != value:
            raise SystemExit(
                f"控制變因被破壞（arm 之間）：{arms[1]} 的 {key}={value}，"
                f"但 {arms[0]} 是 {base.get(key)}")
    for key in allowed:
        if base.get(key) == other.get(key):
            raise SystemExit(
                f"自變因沒有變：兩個 arm 的 {key} 都是 {other.get(key)} —— "
                "這批資料不是 A/B，是同一組跑兩次")


def metrics_for(csv: pathlib.Path) -> dict:
    """算一份 CSV 的指標。視窗劃分是這個實驗的一部分：

    · `recover_s`：只吃 **t ≥ power_down_at** 的那段（飽和解除後）。
      理由見 metrics.recover_s 的 docstring —— 整段餵進去會命中暖機段。
      ⚠️ 刻意**不** reset_index：metrics 的實作必須用位置不用標籤，
      這裡就是它每天要面對的輸入形狀（mutation P17 守的就是這件事）。
    · 其餘指標：吃 **t ≥ power_up_at**（階躍後全段，含飽和與恢復），
      與 exp05「指標只算階躍之後」同一條理由（暖機不是量測對象）。
    · `sat_frac`：飽和視窗 [up, down) 內 PWM 貼頂（≥ 99.99）的時間比例 ——
      「飽和真的發生了」的直接證據，兩組都該接近 1。
    """
    import pandas as pd
    df = pd.read_csv(csv)
    after_up = df[df["t_s"] >= POWER_UP_AT]
    after_down = df[df["t_s"] >= POWER_DOWN_AT]
    sat_window = df[(df["t_s"] >= POWER_UP_AT) & (df["t_s"] < POWER_DOWN_AT)]
    return {
        "recover_s": metrics.recover_s(after_down, SETPOINT),
        "integral_max": metrics.integral_max(after_up),
        "t_peak_c": metrics.t_peak_c(after_up),
        "pwm_max": float(after_up["pwm"].max()),
        "sat_frac": float((sat_window["pwm"] >= 99.99).mean()),
    }


def summarise_runs(rows: list[dict]) -> dict:
    """五個 seed 的中位數與 min~max。NaN 要傳染整組 —— 理由見 exp05。"""
    out = {}
    for key in METRIC_KEYS:
        values = [r[key] for r in rows]
        if any(v != v for v in values):          # NaN
            out[key] = {"median": None, "min": None, "max": None,
                        "note": "至少一個 seed 量不到（NaN）"}
        else:
            out[key] = {"median": statistics.median(values),
                        "min": min(values), "max": max(values)}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="bench/data")
    ap.add_argument("--sim", default="build/sim")
    ap.add_argument("--fit", default="bench/data/exp01_fit.txt")
    ap.add_argument("--tuning-meta", default="bench/data/exp05_tuning_meta.json")
    args = ap.parse_args()

    kp, ki = adopted_gains(pathlib.Path(args.tuning_meta),
                           pathlib.Path(args.fit))
    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    all_params: dict = {}
    table: dict = {}
    for arm in ARMS:
        rows = []
        for seed in SEEDS:
            csv, params = run_one(args.sim, arm, kp, ki, seed, out_dir)
            all_params[(arm, seed)] = params
            rows.append(metrics_for(csv))
            print(f"wrote {csv}")
        table[arm] = {
            "integral_limit": list(ARMS[arm]),
            "metrics": summarise_runs(rows),
            "per_seed": {str(s): r for s, r in zip(SEEDS, rows, strict=True)},
        }

    check_single_variable(all_params)
    print(f"控制變因檢查通過：組內只有 seed 不同、組間只有 integralLimit 不同"
          f"（{len(ARMS)} × {len(SEEDS)} = {len(ARMS) * len(SEEDS)} 次執行）")

    meta = {
        "experiment": "exp07_antiwindup",
        "gains": {
            "kp": kp, "ki": ki,
            "source": f"{args.tuning_meta} 的 lambda_table[{ADOPTED_LAMBDA_KEY}]"
                      "（W6 採用組），並用 exp01_fit 重算交叉驗證",
        },
        "setpoint_c": SETPOINT,
        "power_w": {"base": POWER_BASE, "step": POWER_STEP,
                    "up_at_s": POWER_UP_AT, "down_at_s": POWER_DOWN_AT},
        "controllable_power_limit_w": (SETPOINT - 25.0) / 0.12,
        "ctrl_ts_s": CTRL_TS,
        "dt_s": DT,
        "seconds": SECONDS,
        "seeds": SEEDS,
        "out_lim": [OUT_MIN, OUT_MAX],
        "anti_windup": ANTI_WINDUP,
        "arms": {name: list(lim) for name, lim in ARMS.items()},
        "metric_windows": {"most_from_s": POWER_UP_AT,
                           "recover_from_s": POWER_DOWN_AT},
        "metric_settings": {
            "recover_pwm_threshold": _default_of(metrics.recover_s,
                                                 "pwm_threshold"),
        },
        "table": table,
        "repo_commit": subprocess.getoutput("git rev-parse --short HEAD"),
        "sim_params": {arm: all_params[(arm, SEEDS[0])] for arm in ARMS},
    }
    meta_path = out_dir / "exp07_antiwindup_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {meta_path}")

    print()
    print(f"{'arm':>6} {'recover_s':>10} {'I_max':>10} {'Tpeak':>8}"
          f" {'pwm_max':>8} {'sat_frac':>9}")
    for arm in ARMS:
        m = table[arm]["metrics"]

        def med(key, m=m):
            v = m[key]["median"]
            return "NaN" if v is None else f"{v:.3f}"

        print(f"{arm:>6} {med('recover_s'):>10} {med('integral_max'):>10}"
              f" {med('t_peak_c'):>8} {med('pwm_max'):>8} {med('sat_frac'):>9}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
