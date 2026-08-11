"""exp09 的事件偵測 —— zone_0.log 裡找 t1（failsafe 0→1）與 t2（PWM 拉滿）。

★ 這個函數是 Fig 4 全部時序數字的來源。它守三類錯：
  ① 開機殘留 —— swampd 開機就在 failsafe（initializeCache），
    「全域找第一個 1」量到的是開機時刻不是逾時偵測；
  ② schema 誤解 —— 第一版用 `fan0_pwm_raw`（0~255 的想像），但本 rig 的
    writePath 是 write-only 檔案，那一欄**恆為 -1**。用照想像造的假資料
    測試全綠、真資料一跑就爆（2026-08-11 實抓）——所以這裡有一個
    **用真實 log 行**的測試（學 test_parse_l2 的做法）；
  ③ 環境凍結 —— WSL 被宿主搶 CPU 時 log 行距爆開，wall-clock 事件時刻
    不可信（run1 實測 t1−t0 被撐到 17.3 s，真值 ~5.5 s）。

⚠️ 假資料的行距刻意做成 100 ms（真實節奏）：detect_events 的前提 ③
   會拒絕行距 > 0.5 s 的事件窗，稀疏的合成資料會被當成凍結誤殺。
"""

import io
import pathlib
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "bench"))

from exp09_failsafe import detect_events  # noqa: E402

T0 = 10_000.0  # epoch_ms


def zone_frame(rows):
    """rows: (epoch_ms, failsafe, fan0_pwm 0~1)"""
    return pd.DataFrame(
        [{"epoch_ms": e, "failsafe": f, "fan0_pwm": p}
         for e, f, p in rows])


def dense_rows(t_from, t_to, failsafe_at=None, pwm_full_at=None,
               pwm_normal=0.30, skip=None):
    """每 100 ms 一行（真實節奏），事件時刻由參數給。"""
    rows = []
    t = t_from
    while t <= t_to:
        if skip is None or not (skip[0] <= t < skip[1]):
            fs = 1 if (failsafe_at is not None and t >= failsafe_at) else 0
            pwm = 1.0 if (pwm_full_at is not None and t >= pwm_full_at) \
                else pwm_normal
            rows.append((t, fs, pwm))
        t += 100.0
    return rows


def normal_run():
    """典型 run：開機殘留 → 正常段 → t0 → 逾時 → failsafe → 下一輪 PWM 拉滿。"""
    boot = [(1_000.0, 1, 1.0), (2_000.0, 0, 0.30)]
    return zone_frame(
        boot + dense_rows(8_000.0, 15_600.0,
                          failsafe_at=15_200.0, pwm_full_at=15_300.0))


def test_finds_t1_and_t2_after_t0():
    ev = detect_events(normal_run(), T0)
    assert ev["t1_ms"] == 15_200.0
    assert ev["t2_ms"] == 15_300.0


def test_boot_residue_is_not_mistaken_for_the_event():
    """★ 防（mutation E1）：忘了先裁到 t0 之後。

    開機段就有 failsafe=1 與 PWM=1.0 —— 全域找第一筆會回 1000 ms，
    比 t0 還早：一個「負延遲」，而且沒有任何錯誤訊息。
    """
    ev = detect_events(normal_run(), T0)
    assert ev["t1_ms"] > T0
    assert ev["t2_ms"] > T0


def test_still_in_failsafe_at_t0_is_rejected_loudly():
    """防（mutation E2）：t0 時還沒退出開機 failsafe —— 量到的是開機
    殘留不是逾時偵測，這種 run 必須整個作廢。

    ★ 資料刻意**恰好只違反這一個前提**：PWM 正常（0.45）、行距密集、
      t0 之後事件齊全 —— E2 把檢查廢掉後函數會一路走完並回傳數字,
      測試才會紅。第一版資料同時違反兩個前提，守門員互相頂替，
      E2 就活下來了（2026-08-11 mutation 實抓）。
    """
    df = zone_frame(dense_rows(8_000.0, 15_600.0,
                               failsafe_at=8_000.0,  # 從頭到尾都在 failsafe
                               pwm_full_at=15_300.0, pwm_normal=0.45))
    with pytest.raises(SystemExit):
        detect_events(df, T0)


def test_pwm_already_pinned_at_t0_is_rejected_loudly():
    """恰好只違反「PWM 已拉滿」這一個前提（failsafe 在 t0 前是 0）。"""
    rows = [(e, f, 1.0)
            for e, f, _ in dense_rows(8_000.0, 15_600.0,
                                      failsafe_at=15_200.0)]
    with pytest.raises(SystemExit):
        detect_events(zone_frame(rows), T0)


def test_never_entering_failsafe_is_rejected_loudly():
    df = zone_frame(dense_rows(8_000.0, 20_000.0))
    with pytest.raises(SystemExit):
        detect_events(df, T0)


def test_no_data_before_t0_is_rejected_loudly():
    df = zone_frame(dense_rows(15_000.0, 16_000.0, failsafe_at=15_200.0,
                               pwm_full_at=15_300.0))
    with pytest.raises(SystemExit):
        detect_events(df, T0)


def test_frozen_environment_is_rejected_loudly():
    """★ 防 schema 之外的第三類錯:事件窗內 log 行距 > 0.5 s = 量測環境
    在凍結,wall-clock 不可信。run1 的實際死法(session 中斷期間每
    ~33.5 s 凍 1.4~1.55 s,t1−t0 被撐到 17.3 s)。"""
    df = zone_frame(dense_rows(8_000.0, 15_600.0,
                               failsafe_at=15_200.0, pwm_full_at=15_300.0,
                               skip=(12_000.0, 13_500.0)))  # 1.5 s 的凍結
    with pytest.raises(SystemExit):
        detect_events(df, T0)


REAL_SAMPLE = """\
epoch_ms,setpt,requester,fan0,fan0_raw,fan0_pwm,fan0_pwm_raw,die0,die0_raw,failsafe
1786427953874,3000,Minimum,4471,4471,0.3,-1,64.375,64.375,0
1786427953974,3000,Minimum,4471,4471,0.3,-1,64.375,64.375,0
1786427954074,3000,Minimum,4471,4471,0.3,-1,64.375,64.375,1
1786427954174,3000,Minimum,5173,5173,1,-1,64.375,64.375,1
"""


def test_real_zone_log_rows_parse_and_detect():
    """★ 真實樣本行(run1 zone_0.log 逐字複製)—— 守 schema 本身。

    第一版的教訓:合成資料照「我以為的格式」造,測試全綠,真資料一跑
    就爆(`fan0_pwm_raw` 恆 -1)。合成資料測邏輯、真樣本測 contract,
    兩種都要有 —— test_parse_l2 的做法,這次真的照抄。
    注意真行裡 `fan0_pwm` 拉滿時印的是整數 `1` 不是 `1.0`,
    `requester` 是字串 —— 這些都是合成資料想像不到的細節。
    """
    df = pd.read_csv(io.StringIO(REAL_SAMPLE))
    t0 = 1786427953874.0 + 150.0  # 兩行之後停止推值
    ev = detect_events(df, t0)
    assert ev["t1_ms"] == 1786427954074.0
    assert ev["t2_ms"] == 1786427954174.0
    assert ev["t2_ms"] - ev["t1_ms"] == 100.0  # 恰好一個內圈週期
