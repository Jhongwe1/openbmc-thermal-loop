"""對外宣稱的數字 vs 從資料重新算出的數字 —— 不符就以非零離開碼失敗。

這支腳本是 `bench/claims.json` 的執行面:README 與履歷引用的每一個數字,
在這裡都有一條「從資料算回來」的路徑。**沒有計算路徑的宣稱,不該存在**
—— 反過來也一樣,所以兩個方向的完整性都會檢查。CI(W10)每次 push 都跑。

兩類宣稱,差別在「資料哪裡來」:

  rerun 類(exp01/05/07/08,L1 模擬)
      CI 會先重跑模擬、覆寫 bench/data/ 的 CSV,再執行本腳本。
      模擬是決定性的(workflow 另有逐 byte 的 `git diff` 檢查),
      所以這一類斷言抓的是「程式碼或參數被改到,數字跟著漂」。

  recompute 類(exp06/09/10,L2 私有匯流排與 L3 QEMU BMC)
      CI 上沒有 QEMU 也沒有 L2 rig,**量測**無法重做;但原始 log 都進了
      git,**推導**可以重做。這一類斷言抓的是「分析程式碼被改到,
      同一份原始資料推出不同的數字」。
      ★ 它斷言的是推導的可重現性,不是量測的可重現性 —— 量測那一半
      由 docs/measurement.md 的實驗協定與逐 rep 量具健康檢查守。
      (W9 時原本打算把 exp10 標成 informational「只報告不斷言」;
      改成 recompute 斷言是刻意升級 —— informational 會讓推導程式碼
      悄悄漂移而 CI 永遠綠。)

慣例(由 test/python/test_assert_metrics.py 逐一釘死):

  · 「A/B 比值」= 兩臂共用 seed 時**逐 seed 配對**相除後取中位數。
    配對版與「中位數相除」版差 ~0.4%(13.73 vs 13.79),
    測試用 1e-6 的相對容差釘的是配對版 —— 別在重構時換成另一種。
  · 峰值類指標(t_peak)先裁到擾動之後(meta 的 metrics_computed_from_s),
    不然量到的是冷機暖機;尾窗類指標(pwm_pp、reversals)自帶 tail
    視窗,裁不裁結果相同,所以不裁。
  · 統計一律 median(誠實準則第 2 條:不挑最好看的那次)。

用法:
    python bench/assert_metrics.py                    # 全部
    python bench/assert_metrics.py --only fopdt_tau_s
    python bench/assert_metrics.py --list
"""

import argparse
import json
import pathlib
import statistics
import sys

import pandas as pd

BENCH = pathlib.Path(__file__).resolve().parent
DATA = BENCH / "data"

sys.path.insert(0, str(BENCH))
import exp06_cascade  # noqa: E402
import exp09_failsafe  # noqa: E402
import metrics  # noqa: E402

# exp05_tuning_meta.json 的 metrics_computed_from_s:峰值只在擾動之後找。
EXP05_CROP_S = 300.0
# Fig 5 / README 選定的 slew 工作點與「不限制」哨兵(claims.json 的 note)。
EXP08_FREE_SLEW = "0.0"
EXP08_REFERENCE_SLEW = "0.5"


# ── 小工具 ────────────────────────────────────────────────────────────

def band(value: float, tolerance_pct: float) -> tuple[float, float]:
    """宣稱值的允收區間 [lo, hi]。

    sorted() 不是裝飾:value 為負時 (1−t)·value > (1+t)·value,
    不排序的話區間上下顛倒、斷言永遠失敗 —— fopdt_k 就是負的。
    (計畫 W10 的範本正是這樣寫的,照抄第一個紅的就是它。)
    """
    lo, hi = sorted((value * (1.0 - tolerance_pct),
                     value * (1.0 + tolerance_pct)))
    return lo, hi


def _csvs(pattern: str) -> list[pathlib.Path]:
    files = sorted(DATA.glob(pattern))
    if not files:
        raise FileNotFoundError(f"bench/data/{pattern} 一個都沒有 —— "
                                "rerun 類要先跑對應的 exp 腳本")
    return files


def _median_over(files: list[pathlib.Path], fn) -> float:
    return statistics.median(fn(pd.read_csv(f)) for f in files)


def _fit() -> dict[str, float]:
    """exp01_fit.txt 的 key=value 行(seedN 彙整行與註解自動略過)。"""
    out: dict[str, float] = {}
    for line in (DATA / "exp01_fit.txt").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        try:
            out[key] = float(val)
        except ValueError:
            continue
    return out


# ── rerun 類(exp01/05/07/08)──────────────────────────────────────────

def _exp05_median(lam: str, fn) -> float:
    return _median_over(_csvs(f"exp05_tuning_lam{lam}tau_seed*.csv"), fn)


def _pwm_jitter_reduction_ratio() -> float:
    return (_exp05_median("0.5", metrics.pwm_pp)
            / _exp05_median("2.0", metrics.pwm_pp))


def _peak_deviation_cost_c() -> float:
    def peak(df: pd.DataFrame) -> float:
        return metrics.t_peak_c(df[df["t_s"] >= EXP05_CROP_S])
    return _exp05_median("2.0", peak) - _exp05_median("0.5", peak)


def _reversals_ratio_lambda() -> float:
    return (_exp05_median("0.5", metrics.reversals_per_min)
            / _exp05_median("2.0", metrics.reversals_per_min))


def _fan_power_rel_lambda_spread_pct() -> float:
    meds = [_exp05_median(lam, metrics.fan_power_rel)
            for lam in ("0.5", "1.0", "2.0")]
    return (max(meds) - min(meds)) / statistics.median(meds) * 100.0


def _recover_s_ratio() -> float:
    meta = json.loads((DATA / "exp07_antiwindup_meta.json").read_text())
    setpoint = float(meta["setpoint_c"])
    down_at = float(meta["power_w"]["down_at_s"])

    def rec(path: pathlib.Path) -> float:
        df = pd.read_csv(path)
        return metrics.recover_s(df[df["t_s"] >= down_at], setpoint)

    pairs = zip(_csvs("exp07_awopen_seed*.csv"),
                _csvs("exp07_awclamp_seed*.csv"), strict=True)
    return statistics.median(rec(o) / rec(c) for o, c in pairs)


def _reversals_reduction_ratio() -> float:
    pairs = zip(_csvs(f"exp08_slew{EXP08_FREE_SLEW}_seed*.csv"),
                _csvs(f"exp08_slew{EXP08_REFERENCE_SLEW}_seed*.csv"),
                strict=True)
    return statistics.median(
        metrics.reversals_per_min(pd.read_csv(free))
        / metrics.reversals_per_min(pd.read_csv(tight))
        for free, tight in pairs)


# ── recompute 類(exp06/09/10)─────────────────────────────────────────

def _zone_rows() -> list[dict]:
    text = (DATA / "exp06_cascade" / "zone_0.log").read_text()
    return exp06_cascade.parse_zone_log(text)


def _fan_cycle_ms() -> float:
    return exp06_cascade.fan_cycle_ms(_zone_rows())["median"]


def _thermal_update_ms() -> float:
    return exp06_cascade.thermal_update_ms(_zone_rows())["median"]


def _failsafe_detect_s() -> float:
    vals = []
    for k in (1, 2, 3, 4, 5):
        run_dir = DATA / "exp09_failsafe"
        meta = json.loads((run_dir / f"run{k}_plant_meta.json").read_text())
        t0_ms = meta["epoch0_ms"] + meta["args"]["stop_push_at"] * 1000.0
        zone = pd.read_csv(run_dir / f"run{k}_zone0.log")
        ev = exp09_failsafe.detect_events(zone, t0_ms)
        vals.append((ev["t2_ms"] - t0_ms) / 1000.0)
    return statistics.median(vals)


def _e2e_inject_to_redfish_s() -> float:
    df = pd.read_csv(DATA / "exp10_latency" / "events.csv")
    kept = df[df["warmup"].astype(str) != "True"]
    return float(kept["total_redfish_s"].median())


# ── 宣稱 → 計算路徑(順序照 claims.json)──────────────────────────────

COMPUTE = {
    "fopdt_k_c_per_pct": ("rerun", lambda: _fit()["k"]),
    "fopdt_tau_s": ("rerun", lambda: _fit()["tau"]),
    "fopdt_theta_s": ("rerun", lambda: _fit()["theta"]),
    "fopdt_tau_plus_theta_s": ("rerun", lambda: _fit()["tau_plus_theta"]),
    "pwm_jitter_reduction_ratio": ("rerun", _pwm_jitter_reduction_ratio),
    "peak_deviation_cost_c": ("rerun", _peak_deviation_cost_c),
    "reversals_ratio_lambda": ("rerun", _reversals_ratio_lambda),
    "fan_power_rel_lambda_spread_pct":
        ("rerun", _fan_power_rel_lambda_spread_pct),
    "fan_cycle_ms": ("recompute", _fan_cycle_ms),
    "thermal_update_ms": ("recompute", _thermal_update_ms),
    "recover_s_ratio": ("rerun", _recover_s_ratio),
    "reversals_reduction_ratio": ("rerun", _reversals_reduction_ratio),
    "failsafe_detect_s": ("recompute", _failsafe_detect_s),
    "e2e_inject_to_redfish_s": ("recompute", _e2e_inject_to_redfish_s),
}


def load_claims() -> dict:
    raw = json.loads((BENCH / "claims.json").read_text())
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def main() -> int:
    ap = argparse.ArgumentParser(
        description="重算每個 claim 並與 claims.json 比對(CI 的斷言步驟)")
    ap.add_argument("--only", help="只檢查這一個 claim")
    ap.add_argument("--list", action="store_true",
                    help="列出全部 claim 與其計算類別")
    args = ap.parse_args()

    claims = load_claims()

    # 兩個方向的完整性:宣稱沒有計算路徑=不可驗證;計算路徑沒有宣稱=殭屍。
    missing = [n for n in claims if n not in COMPUTE]
    orphans = [n for n in COMPUTE if n not in claims]
    for n in missing:
        print(f"FAIL {n}: claims.json 有這個宣稱,但沒有計算路徑 —— "
              "沒有計算路徑的宣稱不該存在")
    for n in orphans:
        print(f"FAIL {n}: 有計算路徑,但 claims.json 沒有這個宣稱")
    if missing or orphans:
        return 1

    if args.list:
        for name, (mode, _fn) in COMPUTE.items():
            print(f"{mode:9s} {name}")
        return 0

    if args.only and args.only not in claims:
        print(f"FAIL --only {args.only}: 沒有這個 claim(--list 看全名)")
        return 1

    ok = True
    for name, c in claims.items():
        if args.only and name != args.only:
            continue
        if c["value"] is None:
            print(f"SKIP [{'—':9s}] {name}: value 尚未量測(null)")
            continue
        mode, fn = COMPUTE[name]
        lo, hi = band(c["value"], c["tolerance_pct"])
        try:
            actual = fn()
        except Exception as e:
            # 紅燈證明 R1 實抓的洞:改壞的 plant 讓 pwm_pp 掉到 0,
            # 比值計算除以零,整支腳本 traceback —— 後面的 claim 全部
            # 沒被檢查。檢查器的失敗要「記下來、繼續查」,不是倒地。
            ok = False
            print(f"FAIL [{mode:9s}] {name}: 計算路徑丟出例外 —— {e!r}")
            continue
        passed = lo <= actual <= hi
        ok = ok and passed
        print(f"{'PASS' if passed else 'FAIL'} [{mode:9s}] {name}: "
              f"{actual:.6g}(宣稱 {c['value']:.6g} "
              f"±{c['tolerance_pct']:.0%} → 允收 [{lo:.6g}, {hi:.6g}])")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
