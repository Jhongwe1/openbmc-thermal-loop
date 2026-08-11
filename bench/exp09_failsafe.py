"""exp09：failsafe 偵測延遲 —— 停止推送溫度後，swampd 多久把 PWM 拉到 failsafePercent。

⚠️ 編號：計畫寫的是 `exp04_failsafe`，但 exp04 在稽核時已給了注入路徑；
   measurement.md 曾把 exp09 預留給 W9 的 L1/L2 對照 —— 實驗一律按
   **執行順序**編號（§4.0），failsafe 今天先做，所以它拿 exp09，
   L1/L2 對照順延 exp10。

實驗協定（七欄，定義見 docs/measurement.md）
--------------------------------------------------
假設     : 停止推送溫度後，約 sensor timeout（5 s）+ 檢查節奏 + 寫出
           延遲之內，zone 進 failsafe、PWM 跳到 failsafePercent（100%）。
自變因   : 「是否繼續推送溫度」—— 一次性事件（t0 = 300 s），不是掃描。
控制變因 : config = config.tuned.json 唯一改 die0 的 timeout 0 → 5
           （由本腳本生成並逐欄驗證，不是手改）、恆定負載 150 W
           （無階躍 —— 這個實驗量的是偵測路徑，不是控制性能）、
           swampd 未修改二進位 @ c5e5955、每 run 換 seed。
應變因   : t1 − t0（failsafe 欄 0 → 1）、t2 − t0（PWM 到 255/255）。
           兩者都從 zone_0.log 讀（每輪一行、無節流、自帶 epoch_ms），
           t0 從 bridge meta 算（epoch0_ms + stop_push_at；絕對節拍，
           1500 s 累積誤差 ~1 ms，W7 實測）。
重複     : 5 次獨立 run（seed 1~5），報中位數與 min~max。
原始資料 : bench/data/exp09_failsafe/run<K>_{zone0.log,plant.csv,plant_meta.json}
產圖     : python bench/plot.py --fig 4

★ 為什麼 t1 用 zone_0.log 而不是計畫寫的 busctl monitor
------------------------------------------------------
讀上游原始碼（c5e5955）發現：`DbusPidZone::failSafe()` 是**純 getter**
（zone.cpp:586 只回傳 getFailSafeMode()），整個 codebase 沒有對這個屬性
的 PropertiesChanged emit —— **busctl monitor 永遠等不到訊號**，
計畫的量法量不到 t1。zone_0.log 每輪（0.1 s）寫一行、最後一欄就是
failsafe、自帶 epoch_ms —— t1 與 t2 同一份 log、同一條時間軸。
（busctl get-property 仍用於 L3 的單點驗證：Gate 4 DoD 的
「FailSafe 讀出 true」，見 docs/failsafe.md。）

★ 延遲的組成（Fig 4 要標的四段）
--------------------------------
  t1 − t0 = timeout（config 5 s）
          + 逾時檢查的節奏（updateSensors 隨外圈，實測 1000 ms —— 相位
            均勻分布，這就是 run 間抖動的主要來源）
          + D-Bus 傳遞與 log 寫出（毫秒級）
  t2 − t1 = 內圈風扇迴路（實測 100 ms）+ sysfs 寫出（本實驗是普通檔案）
⚠️ 不要說「100 ms 內觸發」—— sensor timeout 本來就是秒級設定，
   量到的是 N ≈ 5~6 s，而且要說得出它由哪幾段組成。
"""

import json
import pathlib
import statistics
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

RUNS = [1, 2, 3, 4, 5]
STOP_AT_S = 300.0
RUN_SECONDS = 330.0
TIMEOUT_S = 5

#: zone_0.log 的 `fan0_pwm` 是 **0~1 的比例**（×100 才是 %），failsafe 拉滿
#: 就是 1.0。★ 不要用 `fan0_pwm_raw`：本 rig 的 writePath 是 write-only 的
#: 普通檔案，swampd 讀不回 raw，那一欄**恆為 -1** —— 第一版用它，單元測試
#: 用照想像造的假資料（0~255）全綠，真資料一來 t2 永遠找不到。
#: 見 parse_l2.py 的 P22（同一個欄位語意，同一天學兩次）。
PWM_FULL = 1.0

#: 事件窗內 zone log 相鄰行距的上限（秒）。主迴圈每 0.1 s 寫一行，
#: 行距遠大於它代表**量測環境在凍結**（WSL 被宿主搶走 CPU、VM 暫停…），
#: wall-clock 的事件時刻就不可信。2026-08-11 run1 實測：session 中斷期間
#: 每 ~33.5 s 凍 1.4~1.55 s，t1−t0 被撐到 17.3 s（真值 ~5.5 s）。
MAX_GAP_S = 0.5

REPO = pathlib.Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "bench/data/exp09_failsafe"
CONF_SRC = REPO / "config/swampd/config.tuned.json"
CONF_DST = pathlib.Path("/tmp/config.failsafe.json")


def make_config(src: pathlib.Path, dst: pathlib.Path) -> None:
    """生成實驗 config：與部署 config 的差異**只有** die0 的 timeout。

    改完再整份重新比對一次 —— 「我只改了一個欄位」要是機器檢查的結論，
    不是我的說法（與 exp05/exp07/exp08 的 check_single_variable 同一條紀律）。
    """
    cfg = json.loads(src.read_text())
    die0 = [s for s in cfg["sensors"] if s["name"] == "die0"]
    if len(die0) != 1:
        raise SystemExit(f"預期恰好一顆 die0，找到 {len(die0)}")
    if die0[0]["timeout"] != 0:
        raise SystemExit(
            f"部署 config 的 die0 timeout 應為 0（W3 的決定），"
            f"現在是 {die0[0]['timeout']} —— 先弄清楚誰動了它")
    die0[0]["timeout"] = TIMEOUT_S
    dst.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")

    # 逐欄驗證：兩份 config 的差異恰好是那一個欄位
    a = json.loads(src.read_text())
    b = json.loads(dst.read_text())
    [s for s in a["sensors"] if s["name"] == "die0"][0]["timeout"] = TIMEOUT_S
    if a != b:
        raise SystemExit("生成的 config 與「tuned + timeout」不一致 —— 中止")


def detect_events(zone, t0_ms: float) -> dict:
    """從 zone_0.log 找 t1（failsafe 0→1）與 t2（PWM 拉滿 1.0）。

    ★ 三個前提都要驗，不滿足就大聲失敗（不回傳看起來像數字的垃圾）：
      ① t0 之前的最後一筆 failsafe 必須是 0 —— swampd 開機**先進**
        failsafe（initializeCache，docs/failsafe.md §1），如果 t0 時還沒
        退出來，量到的「延遲」其實是開機殘留，整個 run 無效。
      ② t0 之前的最後一筆 PWM 必須 < 1.0 —— PWM 已經在頂上的話，
        「跳變」根本無從觀測。
      ③ 事件窗（t0 − 2 s ~ t2 + 1 s）內 log 的相鄰行距不得超過
        MAX_GAP_S —— 行距爆掉代表量測環境在凍結（VM 暫停 / CPU 被搶），
        事件的 wall-clock 時刻不可信，整個 run 作廢（run1 實抓，
        見模組 docstring 常數註解）。
    """
    before = zone[zone["epoch_ms"] < t0_ms]
    if len(before) == 0:
        raise SystemExit("zone log 在 t0 之前沒有任何資料 —— 對時錯了？")
    if int(before["failsafe"].iloc[-1]) != 0:
        raise SystemExit(
            "t0 時 zone 還在 failsafe（開機殘留或提早失效）—— run 無效")
    if float(before["fan0_pwm"].iloc[-1]) >= PWM_FULL:
        raise SystemExit("t0 時 PWM 已拉滿 —— 跳變無從觀測，run 無效")

    after = zone[zone["epoch_ms"] >= t0_ms]
    fs = after[after["failsafe"].astype(int) == 1]
    if len(fs) == 0:
        raise SystemExit("t0 之後從未進 failsafe —— timeout 沒生效？")
    t1_ms = float(fs["epoch_ms"].iloc[0])

    pwm = after[after["fan0_pwm"].astype(float) >= PWM_FULL]
    if len(pwm) == 0:
        raise SystemExit("t0 之後 PWM 從未拉滿 —— failsafePercent 沒生效？")
    t2_ms = float(pwm["epoch_ms"].iloc[0])

    window = zone[(zone["epoch_ms"] >= t0_ms - 2000.0) &
                  (zone["epoch_ms"] <= t2_ms + 1000.0)]
    max_gap_s = float(window["epoch_ms"].diff().max()) / 1000.0
    if max_gap_s > MAX_GAP_S:
        raise SystemExit(
            f"事件窗內 log 行距最大 {max_gap_s:.2f} s（> {MAX_GAP_S} s）——"
            f"量測環境在凍結，wall-clock 時刻不可信，run 無效")

    return {"t1_ms": t1_ms, "t2_ms": t2_ms, "max_gap_s": max_gap_s}


def main() -> int:
    import pandas as pd

    make_config(CONF_SRC, CONF_DST)
    print(f"config: {CONF_DST}（與 {CONF_SRC.name} 唯一差異 = die0 timeout "
          f"0 → {TIMEOUT_S}，已逐欄驗證）")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = []
    for k in RUNS:
        print(f"\n=== run {k}/{len(RUNS)}（{RUN_SECONDS:.0f} s 即時）===",
              flush=True)
        subprocess.run(
            ["bash", str(REPO / "harness/l2_failsafe.sh")],
            env={**__import__("os").environ,
                 "CONF": str(CONF_DST), "RUN_ID": str(k), "SEED": str(k),
                 "STOP_AT": str(STOP_AT_S), "RUN_SECONDS": str(RUN_SECONDS)},
            check=True)

        meta = json.loads(
            (OUT_DIR / f"run{k}_plant_meta.json").read_text())
        t0_ms = meta["epoch0_ms"] + STOP_AT_S * 1000.0
        zone = pd.read_csv(OUT_DIR / f"run{k}_zone0.log")
        ev = detect_events(zone, t0_ms)
        rows.append({
            "run": k,
            "t0_epoch_ms": t0_ms,
            "t1_minus_t0_s": (ev["t1_ms"] - t0_ms) / 1000.0,
            "t2_minus_t0_s": (ev["t2_ms"] - t0_ms) / 1000.0,
            "t2_minus_t1_s": (ev["t2_ms"] - ev["t1_ms"]) / 1000.0,
        })
        r = rows[-1]
        print(f"run {k}: t1-t0 = {r['t1_minus_t0_s']:.3f} s, "
              f"t2-t0 = {r['t2_minus_t0_s']:.3f} s")

    def stat(key):
        vals = [r[key] for r in rows]
        return {"median": statistics.median(vals),
                "min": min(vals), "max": max(vals)}

    summary = {k: stat(k)
               for k in ("t1_minus_t0_s", "t2_minus_t0_s", "t2_minus_t1_s")}

    meta = {
        "experiment": "exp09_failsafe",
        "config_source": str(CONF_SRC.relative_to(REPO)),
        "config_delta": {"sensors[die0].timeout": [0, TIMEOUT_S]},
        "stop_push_at_s": STOP_AT_S,
        "run_seconds": RUN_SECONDS,
        "timeout_s": TIMEOUT_S,
        "runs": rows,
        "summary": summary,
        "swampd": "unmodified upstream @ c5e5955 (see docs/env-baseline.md)",
        "repo_commit": subprocess.getoutput("git rev-parse --short HEAD"),
    }
    meta_path = OUT_DIR / "exp09_meta.json"
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    print(f"\nwrote {meta_path}")

    print(f"\n{'':>10} {'median':>8} {'min':>8} {'max':>8}")
    for key, label in (("t1_minus_t0_s", "t1-t0 (s)"),
                       ("t2_minus_t0_s", "t2-t0 (s)"),
                       ("t2_minus_t1_s", "t2-t1 (s)")):
        s = summary[key]
        print(f"{label:>10} {s['median']:>8.3f} {s['min']:>8.3f} "
              f"{s['max']:>8.3f}")
    print(f"\n組成：timeout {TIMEOUT_S} s + 逾時檢查節奏（外圈 1 Hz，"
          f"相位均勻 → 抖動 ~1 s）+ D-Bus/寫出（ms 級）；"
          f"t2-t1 ≈ 內圈 100 ms + 檔案寫出")
    return 0


if __name__ == "__main__":
    sys.exit(main())
