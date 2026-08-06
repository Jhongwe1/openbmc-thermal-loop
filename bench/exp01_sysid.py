"""exp01：開環系統識別 —— PWM 階躍，量 K / tau / theta。

實驗協定（七欄，定義見 docs/measurement.md）
--------------------------------------------------
假設     : PWM 從 40% 階躍到 60% 之後，感測溫度會在 theta 秒後開始下降，
           並以時間常數 tau 趨近新的穩態。**K 必為負**（風扇越快溫度越低）。
           兩點法擬出的 tau 會略小於 tau_die + tau_sense、theta 會略大於
           設定的死區，因為 FOPDT 只有一個時間常數而模型有兩個一階環節；
           **可檢查的不變量是 tau + theta**。
自變因   : PWM（唯一）
控制變因 : power_w 固定 150 W、dt = 0.1 s、階躍時刻固定 300 s、總長 900 s、
           plant 參數全部使用預設值。
           ★ 這一條不是用寫的 —— sim 每次執行都把生效的完整參數印到 stderr，
             本腳本收下來逐一比對，除了 seed 以外有任何一項不同就中止。
應變因   : 感測溫度序列 -> 兩點法算出的 K / tau / theta / 擬合殘差
重複     : 5 個 seed（0~4），報**中位數與 min~max**，不報最好看的那一次
原始資料 : bench/data/exp01_sysid_seed<K>.csv
產圖     : python bench/plot.py --fig 1

這支腳本不畫圖
--------------
實驗與呈現分離：改圖不用重跑實驗，重跑實驗不動樣式。
擬合也不在這裡重寫 —— 呼叫 C++ 的 build/identify_csv，
因為識別邏輯只能有一份，而那一份有 gtest 守著。
"""

import argparse
import pathlib
import statistics
import subprocess
import sys

SEEDS = [0, 1, 2, 3, 4]
STEP_AT_S = 300.0
PWM_BASE, PWM_STEP = 40.0, 60.0
POWER_W = 150.0
SECONDS = 900.0
DT = 0.1

DU = PWM_STEP - PWM_BASE


def run_one(sim: str, seed: int, out_dir: pathlib.Path) -> tuple[pathlib.Path, dict[str, str]]:
    """跑一次模擬。回傳 (CSV 路徑, 這次執行生效的參數)。

    sim 的 stdout 是 CSV、stderr 是參數，兩條管道分開收。
    """
    out = out_dir / f"exp01_sysid_seed{seed}.csv"
    cmd = [
        sim,
        "--seconds", str(SECONDS),
        "--dt", str(DT),
        "--seed", str(seed),
        "--power-base", str(POWER_W),
        "--pwm-base", str(PWM_BASE),
        "--pwm-step", str(PWM_STEP),
        "--pwm-at", str(STEP_AT_S),
    ]
    with out.open("w") as fh:
        proc = subprocess.run(cmd, stdout=fh, stderr=subprocess.PIPE, check=True)

    params = dict(
        line.split("=", 1) for line in proc.stderr.decode().splitlines() if "=" in line
    )
    return out, params


def fit_one(identifier: str, csv: pathlib.Path) -> dict[str, float]:
    """對一份 CSV 跑兩點法。擬合來自**檔案**，不是來自一次新的模擬。"""
    proc = subprocess.run(
        [identifier, str(csv), "--step-at", str(STEP_AT_S), "--du", str(DU)],
        capture_output=True,
        check=True,
    )
    lines = proc.stdout.decode().splitlines()
    return {k: float(v) for k, v in (ln.split("=", 1) for ln in lines if "=" in ln)}


def check_single_variable(all_params: dict[int, dict[str, str]]) -> None:
    """★ 把「自變因必須只有一個」變成程式會檢查的事。

    實驗協定裡最容易被忽略也最容易被抓包的一條，就是「我以為只改了一個變因」。
    這裡逐項比對五次執行的參數，除了 seed 以外任何一項不同就中止 ——
    **寧可現在中止，也不要產生一批說不清楚是怎麼來的資料。**
    """
    reference_seed = SEEDS[0]
    reference = all_params[reference_seed]
    for seed in SEEDS[1:]:
        for key, value in all_params[seed].items():
            if key == "seed":
                continue
            if reference.get(key) != value:
                raise SystemExit(
                    f"控制變因被破壞：seed {seed} 的 {key}={value}，"
                    f"但 seed {reference_seed} 是 {reference.get(key)}"
                )


def summarise(values: list[float]) -> tuple[float, float, float]:
    """回傳 (中位數, 最小, 最大)。**誠實準則第 2 條：不報最好看的那一次。**"""
    return statistics.median(values), min(values), max(values)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="bench/data")
    ap.add_argument("--sim", default="build/sim")
    ap.add_argument("--identify", default="build/identify_csv")
    args = ap.parse_args()

    out_dir = pathlib.Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    csvs: dict[int, pathlib.Path] = {}
    all_params: dict[int, dict[str, str]] = {}
    for seed in SEEDS:
        path, params = run_one(args.sim, seed, out_dir)
        csvs[seed], all_params[seed] = path, params
        print(f"wrote {path}")

    check_single_variable(all_params)
    print(f"控制變因檢查通過：{len(SEEDS)} 次執行只有 seed 不同")

    fits = {seed: fit_one(args.identify, csvs[seed]) for seed in SEEDS}

    # ── 實驗中繼資料 ──────────────────────────────────────────────────
    # 沒有它，三個月後你看不懂這批 CSV 是什麼條件跑出來的。
    commit = subprocess.getoutput("git rev-parse --short HEAD")
    meta_lines = [
        "# exp01 — 開環系統識別。欄位定義見 docs/measurement.md。",
        f"step_at_s={STEP_AT_S}",
        f"pwm_base={PWM_BASE}",
        f"pwm_step={PWM_STEP}",
        f"du={DU}",
        f"power_w={POWER_W}",
        f"seconds={SECONDS}",
        f"dt={DT}",
        f"seeds={SEEDS}",
        f"repo_commit={commit}",
        "# ↓ 以下是 sim 回報的、這批資料實際生效的 plant 參數",
    ]
    meta_lines += [
        f"{k}={v}" for k, v in all_params[SEEDS[0]].items() if k != "seed"
    ]
    meta = out_dir / "exp01_sysid_meta.txt"
    meta.write_text("\n".join(meta_lines) + "\n")
    print(f"wrote {meta}")

    # ── 擬合結果 ──────────────────────────────────────────────────────
    fit_lines = ["# exp01 兩點法擬合結果。由 build/identify_csv 從上面那些 CSV 算出。"]
    for key in ("k", "tau", "theta", "residual_rms"):
        values = [fits[seed][key] for seed in SEEDS]
        median, lo, hi = summarise(values)
        fit_lines += [
            f"{key}={median:.6f}",
            f"{key}_min={lo:.6f}",
            f"{key}_max={hi:.6f}",
        ]
    # 每個 seed 的原始擬合值也留著 —— 中位數要能被別人自己算一次
    for seed in SEEDS:
        f = fits[seed]
        fit_lines.append(
            f"seed{seed}=k:{f['k']:.6f},tau:{f['tau']:.4f},"
            f"theta:{f['theta']:.4f},residual_rms:{f['residual_rms']:.6f}"
        )
    # tau + theta 是模型階數不匹配下的守恆量（見 LOG.md 2026-08-07）
    sums = [fits[seed]["tau"] + fits[seed]["theta"] for seed in SEEDS]
    median, lo, hi = summarise(sums)
    fit_lines += [
        f"tau_plus_theta={median:.4f}",
        f"tau_plus_theta_min={lo:.4f}",
        f"tau_plus_theta_max={hi:.4f}",
    ]
    fit = out_dir / "exp01_fit.txt"
    fit.write_text("\n".join(fit_lines) + "\n")
    print(f"wrote {fit}")

    # ── 螢幕摘要 ──────────────────────────────────────────────────────
    print()
    print(f"{'seed':>5} {'K':>12} {'tau':>9} {'theta':>9} {'tau+theta':>11} {'resid':>9}")
    for seed in SEEDS:
        f = fits[seed]
        print(
            f"{seed:>5} {f['k']:>12.6f} {f['tau']:>9.3f} {f['theta']:>9.3f} "
            f"{f['tau'] + f['theta']:>11.3f} {f['residual_rms']:>9.4f}"
        )
    for label, key in (("K", "k"), ("tau", "tau"), ("theta", "theta")):
        values = [fits[seed][key] for seed in SEEDS]
        median, lo, hi = summarise(values)
        print(f"{label:>9} 中位數 {median:.6f}   範圍 {lo:.6f} ~ {hi:.6f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
