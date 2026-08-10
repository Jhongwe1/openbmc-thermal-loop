"""L2 資料載入：把 swampd 的 `zone_0.log` / `pidcore.*` 轉成與 `bench/sim`
CSV 同構的 DataFrame —— 讓 L1/L2 共用**同一套**指標與產圖程式。

兩份 log 的性格完全不同（讀上游原始碼 + exp06 實測的結論）：

    zone_0.log   DbusPidZone::writeLog() 直寫，**每輪都寫、沒有節流** ——
                 週期、recover_s 這類「時間」的量測只能用它。
    pidcore.*    ec::LogContext()，**「內容變了 OR 距上次 60 s」才寫一筆**
                 （logThrottle，exp06 實測靜態間隔 60.0~67.6 s）。

★ 節流的正確處理（W6 學費的下半場）：
    量「週期」不能用 pidcore（LOG.md 2026-08-11）；但**畫值的曲線可以
    直接對時間軸連線** —— 兩筆之間沒寫 = 內容沒變，兩點之間的直線
    恰好就是事實（常數段）。真正的地雷有兩個：
      (a) 對 index（筆數）而不是對時間畫 —— 稀疏段會被壓扁而且看不出來；
      (b) 假設等間隔去做視窗統計 —— metrics.py 的視窗全部吃**時間**
          （2026-08-09 的改寫，那些 docstring 預言的就是這裡），
          所以欄位對齊之後可以直接餵。

單位換算只有一個常數：RPM_PER_PCT = 150（tune.py 定義，這裡 import ——
一個常數只定義一次，與指標同一條紀律）。
"""

import argparse
import hashlib
import json
import pathlib
import subprocess
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import metrics  # noqa: E402
from tune import RPM_PER_PCT  # noqa: E402


def bridge_epoch0_ms(bridge_csv: pathlib.Path) -> float:
    """讀 bridge 落在 CSV 旁邊的 meta，拿對時錨點。

    zone_0.log 與 pidcore.* 記牆上時鐘 epoch_ms、bridge CSV 記相對秒 ——
    沒有這個錨點，L2 的三份資料（plant 側、zone 側、pidcore 側）對不上，
    更疊不上 L1。
    """
    meta_path = bridge_csv.with_name(bridge_csv.stem + "_meta.json")
    return float(json.loads(meta_path.read_text())["epoch0_ms"])


def zone_frame(path: pathlib.Path, epoch0_ms: float) -> pd.DataFrame:
    """zone_0.log → 與 sim CSV 同構的欄位。

    實際標頭（swampd c5e5955，exp06/exp07 皆同）：
        epoch_ms,setpt,requester,fan0,fan0_raw,fan0_pwm,fan0_pwm_raw,
        die0,die0_raw,failsafe

    ⚠️ `fan0_pwm` 是 **0~1 的小數**不是百分比（實測 30% 記成 0.3）——
       ×100 之後才能餵 metrics 的 pwm 視窗（recover_s 的門檻是 90）。
    ⚠️ `setpt` 是外圈熱 PID 的輸出（RPM）。除以 RPM_PER_PCT 得到
       「PWM 等效值」，這是 L1/L2 疊圖的共同量綱。
    """
    df = pd.read_csv(path)
    out = pd.DataFrame({
        "t_s": (df["epoch_ms"] - epoch0_ms) / 1000.0,
        "t_sense_c": df["die0"],
        "pwm": df["fan0_pwm"] * 100.0,
        "rpm_setpt": df["setpt"],
        "pwm_equiv": df["setpt"] / RPM_PER_PCT,
        "failsafe": df["failsafe"],
    })
    return out


def pidcore_frame(path: pathlib.Path, epoch0_ms: float) -> pd.DataFrame:
    """pidcore.die0 → 積分軌跡（含節流的稀疏時間軸）。

    實際標頭（swampd -g，c5e5955）：
        epoch_ms,input,setpoint,error,proportionalTerm,integralTerm1,
        integralTerm2,derivativeTerm,feedFwdTerm,output1,output2,minOut,
        maxOut,integralTerm3,output3,integralTerm,output

    取最後的 `integralTerm`（箝位後、真正被下一輪使用的那個值），
    RPM 量綱 ÷ 150 = %PWM 等效 —— 與 L1 sim 的 `integral` 欄同量綱，
    Fig 3 的第三面板才能兩層直接疊。
    """
    df = pd.read_csv(path)
    out = pd.DataFrame({
        "t_s": (df["epoch_ms"] - epoch0_ms) / 1000.0,
        "integral_rpm": df["integralTerm"],
        "integral": df["integralTerm"] / RPM_PER_PCT,
        "error": df["error"],
        "output_rpm": df["output"],
    })
    return out


def _setpoint_from_config(config_path: pathlib.Path) -> float:
    """setpoint 的唯一來源是 swampd 設定檔 —— 不在這裡寫死 65。

    A/B 兩份設定的 setpoint 由 test_swampd_config.py 保證相同，
    所以讀 tuned 那份就足以代表兩個 arm。
    """
    config = json.loads(config_path.read_text())
    for pid in config["zones"][0]["pids"]:
        if pid["name"] == "die0":
            return float(pid["setpoint"])
    raise SystemExit(f"{config_path} 裡沒有 die0 PID")


def summarise(data_dir: pathlib.Path, config_path: pathlib.Path,
              swampd_bin: pathlib.Path | None) -> dict:
    """兩個 arm 的 L2 指標算一次、落成 JSON —— 圖只讀不算（與 Fig 2/3 同紀律）。

    指標全部來自 bench/metrics.py 的同一份定義：
      · `recover_s` 吃 zone_0.log（**無節流**，時間量測只能用它）
      · `integral_max` 吃 pidcore（節流**不影響最大值**：極值出現在
        「值有變」的那一筆，而「值有變」必寫 —— 這是節流語意的直接推論）
    """
    setpoint = _setpoint_from_config(config_path)
    out = {"setpoint_c": setpoint, "arms": {}}
    for arm in ("clamp", "open"):
        bridge_csv = data_dir / f"exp07_L2_{arm}_plant.csv"
        epoch0 = bridge_epoch0_ms(bridge_csv)
        bmeta = json.loads(
            bridge_csv.with_name(bridge_csv.stem + "_meta.json").read_text())
        up_at = float(bmeta["args"]["power_at"])
        down_at = float(bmeta["args"]["power_down_at"])

        zone = zone_frame(data_dir / f"exp07_L2_{arm}_zone0.log", epoch0)
        pid = pidcore_frame(data_dir / f"exp07_L2_{arm}_pidcore.die0", epoch0)
        zone_up = zone[zone["t_s"] >= up_at]
        pid_up = pid[pid["t_s"] >= up_at]

        out["arms"][arm] = {
            "recover_s": metrics.recover_s(zone[zone["t_s"] >= down_at],
                                           setpoint),
            "integral_max_pwm_equiv": metrics.integral_max(pid_up),
            "integral_max_rpm": float(pid_up["integral_rpm"].abs().max()),
            "t_peak_c": metrics.t_peak_c(zone_up),
            "pwm_max": float(zone_up["pwm"].max()),
            "rpm_setpt_max": float(zone_up["rpm_setpt"].max()),
            "zone_rows": int(len(zone)),
            "pidcore_rows": int(len(pid)),
            "power_schedule": {"up_at_s": up_at, "down_at_s": down_at,
                               "base_w": float(bmeta["args"]["power_base"]),
                               "step_w": float(bmeta["args"]["power_step"])},
        }
    if swampd_bin is not None and swampd_bin.exists():
        out["swampd_sha256"] = hashlib.sha256(
            swampd_bin.read_bytes()).hexdigest()
    out["repo_commit"] = subprocess.getoutput("git rev-parse --short HEAD")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default="bench/data", type=pathlib.Path)
    ap.add_argument("--config", default="config/swampd/config.tuned.json",
                    type=pathlib.Path)
    ap.add_argument("--swampd-bin", default=None, type=pathlib.Path,
                    help="算 sha256 進 summary（證據：跑的是哪一顆二進位）")
    ap.add_argument("--swampd-rev", default=None,
                    help="上游 worktree 的 git rev（由呼叫者驗證後傳入）")
    args = ap.parse_args()

    out = summarise(args.data, args.config, args.swampd_bin)
    if args.swampd_rev:
        out["swampd_rev"] = args.swampd_rev
    path = args.data / "exp07_L2_summary.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {path}")
    for arm, m in out["arms"].items():
        print(f"{arm:>6}  recover_s={m['recover_s']:.1f}s  "
              f"integral_max={m['integral_max_pwm_equiv']:.1f}%PWM"
              f"({m['integral_max_rpm']:.0f} RPM)  "
              f"t_peak={m['t_peak_c']:.2f}  pwm_max={m['pwm_max']:.1f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
