"""bench/metrics.py 的 L0 測試。

★ 為什麼這份檔案存在
    `metrics.py` 是**全專案每一個應變因的唯一定義來源**
    （docs/measurement.md §2 自己這樣寫），而在 2026-08-09 之前它**一個測試都沒有**。
    對照組（稽核當下的數字）：C++ 那一側有 26 個 gtest case
    加上 21 個被證明會咬人的 mutation；Python 這一側只有 `ruff`，
    而 ruff 只查風格，不查算得對不對。

    這很重要是因為 W7 的主要宣稱 `recover_s_ratio` 就是這裡的函式算出來的。
    等它寫完再補測試，等於讓 Fig 3 的數字先進 README、測試後到 ——
    順序反了。

★ 每一條測試都要說得出「它防的是哪一種寫錯」
    否則就只是一堆讓覆蓋率好看的斷言。每個 test 的 docstring 都寫了。
"""

import pandas as pd
import pytest

import metrics


def trace(t_s, **columns) -> pd.DataFrame:
    """做一份最小的軌跡。欄位名與 bench/sim.cpp 的 CSV 標頭一致。"""
    return pd.DataFrame({"t_s": t_s, **columns})


# ═══════════════════════════════════════════════════════════════════════
#  t_peak_c
# ═══════════════════════════════════════════════════════════════════════


def test_t_peak_c_takes_the_maximum_not_the_last_sample():
    """防：`.max()` 被寫成 `.min()` 或 `.iloc[-1]`。

    刻意讓**峰值出現在中間**，而且結尾比開頭低 —— 這樣三種寫法會給出
    三個不同的答案。峰值放在最後一筆的話，`.max()` 與 `.iloc[-1]` 分不出來。
    """
    df = trace([0.0, 1.0, 2.0, 3.0], t_sense_c=[30.0, 71.5, 40.0, 25.0])
    assert metrics.t_peak_c(df) == pytest.approx(71.5)


def test_t_peak_c_reads_the_sensed_column_not_the_die_column():
    """防：抓錯欄位。

    `t_die_c` 是模型內部真值，真實系統上量不到。用它算出來的「峰值」
    會比感測值高、而且**永遠對不上實機**，但數字看起來完全正常。
    """
    df = trace([0.0, 1.0],
               t_sense_c=[40.0, 45.0],
               t_die_c=[90.0, 95.0],
               fan_power_rel=[1.0, 1.0])
    assert metrics.t_peak_c(df) == pytest.approx(45.0)


# ═══════════════════════════════════════════════════════════════════════
#  fan_power_rel
# ═══════════════════════════════════════════════════════════════════════


def test_fan_power_rel_on_a_constant_trace_is_that_constant():
    """基本正確性：常數進去，同一個常數出來，而且與 tail_s 無關。"""
    df = trace([i * 0.1 for i in range(600)], fan_power_rel=[0.42] * 600)
    assert metrics.fan_power_rel(df, tail_s=10.0) == pytest.approx(0.42)
    assert metrics.fan_power_rel(df, tail_s=1e6) == pytest.approx(0.42)


def test_fan_power_rel_averages_the_tail_not_the_head():
    """★ 防：`tail` 被寫成 `head`，或視窗長度算錯。

    前段 1.0、最後 120 秒 0.5。取尾段 → 0.5；取頭段 → 1.0；
    整段平均 → 介於兩者之間。**三種寫錯各自給出不同的數字**，
    所以這一條同時擋掉三種。
    """
    dt = 0.1
    n_head, n_tail = 3000, 1201       # 300 s + 120.0 s（含端點）
    t = [i * dt for i in range(n_head + n_tail)]
    values = [1.0] * n_head + [0.5] * n_tail
    df = trace(t, fan_power_rel=values)
    assert metrics.fan_power_rel(df, tail_s=120.0) == pytest.approx(0.5)


def test_fan_power_rel_window_longer_than_the_trace_uses_everything():
    """邊界：要求的尾段比整份資料還長時要平均全部，不可以爆掉。"""
    df = trace([0.0, 1.0, 2.0], fan_power_rel=[0.0, 0.5, 1.0])
    assert metrics.fan_power_rel(df, tail_s=1e9) == pytest.approx(0.5)


def test_fan_power_rel_window_is_defined_by_time_not_by_row_count():
    """★★ 防：用「列數」而不是「時間」框視窗（原本的寫法）。

    這份軌跡**刻意不是等間隔的**：
      · 前段 t = 0, 10, 20, 30, 40（每 10 秒一筆），值固定 9.0
      · 後段 t = 40.5 ~ 60.5（每 0.5 秒一筆，共 41 筆），值 0.01 遞增到 0.41

    要求最後 20 秒（t_end = 60.5，所以視窗是 t >= 40.5）：

    · **用時間框（正確）**：涵蓋後段全部 41 筆，等差數列平均
      = (0.01 + 0.41) / 2 = **0.21**
    · **用列數框（原本的寫法）**：取樣週期從**前兩列**推出來是 10 秒，
      n = int(20 / 10) = 2 → 只取最後兩列 = (0.40 + 0.41) / 2 = **0.405**

    兩個答案差了將近一倍，而且**用列數框的那個沒有任何錯誤訊息**。
    這正是原本那段程式最危險的地方：L2 從 BMC 收資料時取樣間隔本來就會抖。
    """
    sparse_t = [0.0, 10.0, 20.0, 30.0, 40.0]
    dense_t = [40.0 + 0.5 * i for i in range(1, 42)]        # 40.5 ~ 60.5
    sparse_v = [9.0] * len(sparse_t)
    dense_v = [i / 100.0 for i in range(1, 42)]             # 0.01 ~ 0.41

    df = trace(sparse_t + dense_t, fan_power_rel=sparse_v + dense_v)

    assert metrics.fan_power_rel(df, tail_s=20.0) == pytest.approx(0.21)
    # 而且它明顯不等於「最後兩列的平均」——那是舊寫法會給的答案。
    assert metrics.fan_power_rel(df, tail_s=20.0) != pytest.approx(0.405)


# ═══════════════════════════════════════════════════════════════════════
#  overshoot_c（W6）
# ═══════════════════════════════════════════════════════════════════════


def test_overshoot_is_zero_when_the_temperature_never_reaches_setpoint():
    """防：忘了下限 0，回一個負的「超調」。

    負的超調不是超調，是沒到 —— 而 −8 °C 這種數字進了指標表，
    讀圖的人會以為那是「比目標低 8 度的裕度」。
    """
    df = trace([0.0, 1.0, 2.0], t_sense_c=[50.0, 57.0, 55.0])
    assert metrics.overshoot_c(df, setpoint=65.0) == pytest.approx(0.0)


def test_overshoot_subtracts_in_the_right_direction():
    """防：寫成 `setpoint − max`。

    刻意讓峰值與 setpoint 差一個**不對稱**的量：71.5 − 65 = 6.5，
    反過來是 −6.5。用對稱的數字（例如剛好差 5 和 −5）分不出來。
    """
    df = trace([0.0, 1.0, 2.0], t_sense_c=[60.0, 71.5, 66.0])
    assert metrics.overshoot_c(df, setpoint=65.0) == pytest.approx(6.5)


def test_overshoot_reads_the_sensed_column_not_the_die_column():
    """★ 防：`overshoot_c` 自己寫一次 `.max()` 卻抓 `t_die_c`。

    這一條與 `test_t_peak_c_reads_the_sensed_column_not_the_die_column`
    看起來重複，但**它防的是不同的事**：那一條守 `t_peak_c`，
    這一條守「`overshoot_c` 有沒有真的複用 `t_peak_c`」。
    哪天有人把它改成獨立實作、順手抓錯欄位，只有這一條會紅。
    """
    df = trace([0.0, 1.0],
               t_sense_c=[60.0, 66.0],
               t_die_c=[90.0, 95.0])
    assert metrics.overshoot_c(df, setpoint=65.0) == pytest.approx(1.0)


# ═══════════════════════════════════════════════════════════════════════
#  settle_s（W6）
# ═══════════════════════════════════════════════════════════════════════


def test_settle_requires_a_sustained_hold_not_a_moment_inside():
    """★ 進去一下下又跑掉，不算穩定。

    震盪的系統會反覆穿越那條帶。少了「維持」這個條件的話，
    **震盪越厲害的系統反而拿到越漂亮的 settle_s** —— 剛好相反。
    """
    t = [i * 0.1 for i in range(3000)]              # 0 ~ 299.9 s
    temp = [80.0] * 3000
    for i in range(1000, 1050):                     # 100.0 ~ 104.9 s 在帶內
        temp[i] = 65.0
    df = trace(t, t_sense_c=temp)
    assert pd.isna(metrics.settle_s(df, setpoint=65.0))


def test_settle_returns_the_moment_of_entry_not_the_moment_of_confirmation():
    """回傳「進入的時刻」，不是「維持滿 hold_s 的時刻」。

    兩者差一個常數 hold_s，所以寫錯的話**趨勢完全正確、只是整組偏移** ——
    是那種對照圖上看不出來、但每個數字都錯的錯誤。
    """
    t = [i * 0.1 for i in range(3000)]              # 0 ~ 299.9 s
    temp = [80.0 if i < 500 else 65.0 for i in range(3000)]   # 50.0 s 起在帶內
    df = trace(t, t_sense_c=temp)
    assert metrics.settle_s(df, setpoint=65.0) == pytest.approx(50.0)


def test_settle_restarts_the_clock_after_leaving_the_band():
    """離開帶內之後要重新計時，不可以把前後兩段加起來。

    前段待 40 s、離開、後段待 100 s，hold = 60 s。
    正確答案是後段的起點；把兩段加總的寫法會回前段的起點。
    """
    t = [i * 0.1 for i in range(3000)]
    temp = []
    for i in range(3000):
        ts = i * 0.1
        if 10.0 <= ts < 50.0 or ts >= 100.0:
            temp.append(65.0)
        else:
            temp.append(80.0)
    df = trace(t, t_sense_c=temp)
    assert metrics.settle_s(df, setpoint=65.0) == pytest.approx(100.0)


def test_settle_window_is_defined_by_time_not_by_row_count():
    """★★ 防：用「列數」框 hold_s（計畫給的實作就是這樣寫的）。

    這份軌跡刻意**不是等間隔**的：
      · 稀疏段 t = 0, 10, 20, 30（每 10 s），溫度 80 —— 帶外
      · 密集段 t = 30.5 ~ 40.0（每 0.5 s，20 筆），溫度 65 —— 帶內，只有 9.5 s
      · 帶外一段
      · 最後 t = 100.0 起（每 0.5 s）長時間 65 —— 帶內

    · **用時間框（正確）**：第一段只維持 9.5 s < 60 s，不算 → 回 **100.0**
    · **用列數框（計畫的寫法）**：dt 從前兩列推成 10 s，
      `n_hold = int(60 / 10) = 6`，第一段有 20 筆 ≥ 6 → 回 **30.5**

    兩個答案差 70 秒，而且用列數框的那個**不會報錯**。
    這與 2026-08-09 在 `tail_window` 修掉的是同一個念頭寫出來的錯 ——
    ★ **找到一個 bug 要去找它的兄弟。**
    """
    sparse_t = [0.0, 10.0, 20.0, 30.0]
    dense_in = [30.5 + 0.5 * i for i in range(20)]          # 30.5 ~ 40.0
    gap_t = [40.5 + 0.5 * i for i in range(100)]            # 40.5 ~ 90.0
    tail_t = [100.0 + 0.5 * i for i in range(200)]          # 100.0 ~ 199.5

    t = sparse_t + dense_in + gap_t + tail_t
    temp = ([80.0] * len(sparse_t) + [65.0] * len(dense_in)
            + [80.0] * len(gap_t) + [65.0] * len(tail_t))

    df = trace(t, t_sense_c=temp)
    assert metrics.settle_s(df, setpoint=65.0) == pytest.approx(100.0)
    # 而且它明顯不是 30.5 —— 那是用列數框會給的答案。
    assert metrics.settle_s(df, setpoint=65.0) != pytest.approx(30.5)


def test_settle_never_settling_is_nan_not_a_number():
    """從未穩定要回 NaN。

    回 0、回 −1、回軌跡長度都是「一個看起來像答案的數字」，
    它們會一路流進指標表與 claims.json，而**沒有人會發現**。
    """
    t = [i * 0.1 for i in range(1000)]
    df = trace(t, t_sense_c=[90.0] * 1000)
    assert pd.isna(metrics.settle_s(df, setpoint=65.0))


# ═══════════════════════════════════════════════════════════════════════
#  pwm_pp（W6）
# ═══════════════════════════════════════════════════════════════════════


def test_pwm_pp_is_peak_to_peak_of_the_tail_not_of_the_whole_run():
    """★ 防：忘了取尾段。

    前 300 s 從 0 掃到 100（那是暫態），最後 120 s 固定 70。
    · 只看尾段（正確）→ **0**
    · 看全程 → **100**
    暫態的擺幅本來就大，混進「穩態震盪幅度」會讓三組 λ 全部看起來一樣糟。
    """
    dt = 0.1
    n_head, n_tail = 3000, 1201
    t = [i * dt for i in range(n_head + n_tail)]
    pwm = [i / 30.0 for i in range(n_head)] + [70.0] * n_tail
    df = trace(t, pwm=pwm)
    assert metrics.pwm_pp(df, tail_s=120.0) == pytest.approx(0.0)


def test_pwm_pp_is_max_minus_min_not_a_standard_deviation():
    """防：寫成 `.std()` 或 `.mean()`。

    這一段的 max−min = 8.0，而它的標準差、平均值都不是 8.0。
    """
    t = [i * 1.0 for i in range(5)]
    df = trace(t, pwm=[60.0, 68.0, 62.0, 66.0, 64.0])
    assert metrics.pwm_pp(df, tail_s=1e6) == pytest.approx(8.0)


# ═══════════════════════════════════════════════════════════════════════
#  reversals_per_min（W6）
# ═══════════════════════════════════════════════════════════════════════


def test_reversals_ignores_jitter_below_the_deadband():
    """量化／數值精度造成的正負跳動不該算成方向反轉。

    恆定 50 上面疊 ±0.01 的交替抖動，deadband 預設 0.05 → 全部濾掉。
    沒有 deadband 的話這條軌跡會回一個非常大的數字，
    而 W8 的 slew 掃描結論就是錯的。
    """
    t = [i * 0.1 for i in range(2000)]
    pwm = [50.0 + 0.01 * (1 if i % 2 else -1) for i in range(2000)]
    df = trace(t, pwm=pwm)
    assert metrics.reversals_per_min(df) == pytest.approx(0.0)


def test_reversals_counts_direction_changes_above_the_deadband():
    """基本正確性：真的來回擺動要被算到。

    每秒 ±2 交替 31 筆 → 30 個差分、29 次符號改變，跨度 30 s
    → 29 × 60 / 30 = 58 次／分鐘。
    """
    t = [float(i) for i in range(31)]
    pwm = [50.0 + 2.0 * (i % 2) for i in range(31)]
    df = trace(t, pwm=pwm)
    assert metrics.reversals_per_min(df, tail_s=1e6) == pytest.approx(58.0)


def test_reversals_denominator_is_the_actual_span_not_the_requested_window():
    """★★ 防：分母寫成 `tail_s`（計畫給的實作就是這樣寫的）。

    軌跡只有 30 秒，但要求的視窗是 120 秒。
    · **用實際跨度 30 s（正確）** → 29 × 60 / 30 = **58**／分鐘
    · **用 tail_s = 120 s（計畫的寫法）** → 29 × 60 / 120 = **14.5**／分鐘

    差 4 倍，而且錯的方向是**低估** —— 一份太短的資料會讓風扇看起來
    比實際安靜四倍，不會有任何警告。與 `tail_window` 同一個原則：
    ★ **視窗的真實長度要問資料，不要問參數。**
    """
    t = [float(i) for i in range(31)]
    pwm = [50.0 + 2.0 * (i % 2) for i in range(31)]
    df = trace(t, pwm=pwm)
    assert metrics.reversals_per_min(df, tail_s=120.0) == pytest.approx(58.0)
    assert metrics.reversals_per_min(df, tail_s=120.0) != pytest.approx(14.5)


def test_reversals_on_a_monotonic_ramp_is_zero():
    """單調上升沒有方向反轉。

    防的是「把差分不為零就當成一次反轉」—— 那種寫法在斜坡上會
    回一個等於取樣率的數字，看起來像極了嚴重震盪。
    """
    t = [float(i) for i in range(61)]
    df = trace(t, pwm=[float(i) for i in range(61)])
    assert metrics.reversals_per_min(df, tail_s=1e6) == pytest.approx(0.0)


# ═══════════════════════════════════════════════════════════════════════
#  recover_s（W7）
# ═══════════════════════════════════════════════════════════════════════


def test_recover_s_measures_from_first_cooling_to_first_pwm_release():
    """基本正確性 ＋ 防「從整段開頭找 PWM」。

    軌跡刻意在**溫度回落之前**放一段 PWM 低於門檻的凹陷（t=1 的暫態）：
    從整段開頭找「PWM < 90」會命中那個凹陷，回 1.0 秒的錯誤值。
    正確答案：溫度在 t=6 首次 ≤ 65，其後 PWM 在 t=9 首次 < 90 → 3.0 s。
    """
    t = [float(i) for i in range(12)]
    temp = [80.0, 75.0, 72.0, 70.0, 69.0, 68.0,
            65.0, 64.0, 63.0, 62.0, 61.0, 60.0]
    pwm = [100.0, 85.0, 100.0, 100.0, 100.0, 100.0,
           100.0, 100.0, 100.0, 89.0, 60.0, 40.0]
    df = trace(t, t_sense_c=temp, pwm=pwm)
    assert metrics.recover_s(df, setpoint=65.0) == pytest.approx(3.0)


def test_recover_s_is_nan_when_the_temperature_never_cools():
    """飽和從未解除（溫度一直高於 setpoint）→ 實驗設計錯了，回 NaN。

    回 0 的話，windup 最嚴重的那組（永遠降不下來）反而拿到最漂亮的
    「恢復 0 秒」—— 與 settle_s 的 NaN 是同一條紀律。
    """
    t = [float(i) for i in range(300)]
    df = trace(t, t_sense_c=[100.0] * 300, pwm=[100.0] * 300)
    assert pd.isna(metrics.recover_s(df, setpoint=65.0))


def test_recover_s_is_nan_when_the_pwm_never_releases():
    """溫度回落了但 PWM 到軌跡結束都 ≥ 門檻 → 視窗太短，量不到就說量不到。

    這正是無箝位那組可能真實發生的事（積分洩不完）。回「軌跡長度」
    之類的數字會**低估** windup 的代價，而且方向剛好偏袒它。
    """
    t = [float(i) for i in range(10)]
    df = trace(t, t_sense_c=[60.0] * 10, pwm=[100.0] * 10)
    assert pd.isna(metrics.recover_s(df, setpoint=65.0))


def test_recover_s_uses_positions_not_index_labels():
    """★★ 防：計畫給的實作（拿 index 標籤當 iloc 位置用）。

    exp07 的呼叫方式一定是「從 power_down_at 起裁切」——裁切後的
    DataFrame 標籤不從 0 開始。計畫的偽碼把 `df.index[...]` 的標籤
    餵給 `iloc`（位置），輕則 IndexError，重則默默回一個看起來合理的
    錯秒數。這一條與 mutation P17 一起，回答「為什麼不照抄計畫」。
    """
    t = [float(i) for i in range(12)]
    temp = [80.0, 75.0, 72.0, 70.0, 69.0, 68.0,
            65.0, 64.0, 63.0, 62.0, 61.0, 60.0]
    pwm = [100.0, 85.0, 100.0, 100.0, 100.0, 100.0,
           100.0, 100.0, 100.0, 89.0, 60.0, 40.0]
    df = trace(t, t_sense_c=temp, pwm=pwm).iloc[5:]   # 標籤 5..11，刻意不 reset
    assert metrics.recover_s(df, setpoint=65.0) == pytest.approx(3.0)


def test_recover_s_threshold_must_be_positive():
    """門檻 ≤ 0 沒有物理意義（PWM 不會低於 0），要大聲拒絕不要默默回 NaN。"""
    df = trace([0.0, 1.0], t_sense_c=[60.0, 60.0], pwm=[100.0, 50.0])
    with pytest.raises(ValueError, match="pwm_threshold"):
        metrics.recover_s(df, 65.0, pwm_threshold=0.0)


# ═══════════════════════════════════════════════════════════════════════
#  integral_max（W7）
# ═══════════════════════════════════════════════════════════════════════


def test_integral_max_is_the_absolute_extreme_not_the_signed_maximum():
    """防：忘了絕對值。負向最深 −120、正向最高 80 → 答案是 120。

    反向 windup（積分往負向累深）時忘了 abs 會回 80，
    把「反向 windup 很嚴重」讀成「沒事」。
    """
    df = trace([0.0, 1.0, 2.0, 3.0], integral=[10.0, -120.0, 80.0, 0.0])
    assert metrics.integral_max(df) == pytest.approx(120.0)


def test_integral_max_is_nan_for_traces_without_an_integral_column():
    """開環 CSV（exp01）沒有 integral 欄 → NaN（無定義），CLI 不該炸。

    防：回 0.0 —— 「積分從未累積」與「根本沒有積分」是兩件事，
    前者是量測結果、後者是無定義，混在一起會讓開環資料看起來像
    「驗證過沒有 windup」。
    """
    df = trace([0.0, 1.0], t_sense_c=[1.0, 2.0])
    assert pd.isna(metrics.integral_max(df))


# ═══════════════════════════════════════════════════════════════════════
#  summarise
# ═══════════════════════════════════════════════════════════════════════


def test_summarise_returns_every_metric_the_figure_table_needs():
    """Fig 2 的指標表直接吃這個 dict —— 少一個鍵圖就少一欄。

    ⚠️ 這裡寫死那六個鍵是刻意的。用 `set(metrics.summarise(...))` 去比對
       自己的輸出等於什麼都沒驗。
    """
    t = [i * 0.1 for i in range(3000)]
    df = trace(t,
               t_sense_c=[65.0] * 3000,
               pwm=[50.0] * 3000,
               fan_power_rel=[0.3] * 3000)
    got = metrics.summarise(df, setpoint=65.0)
    assert list(got) == ["overshoot_c", "settle_s", "pwm_pp",
                         "reversals_per_min", "fan_power_rel", "t_peak_c"]
    assert all(isinstance(v, float) for v in got.values())


# ═══════════════════════════════════════════════════════════════════════
#  邊界與錯誤訊息
# ═══════════════════════════════════════════════════════════════════════


def test_single_row_trace_works_instead_of_raising_indexerror():
    """★ 原本只有一列會丟 `IndexError`（`iloc[1]` 不存在）。

    訊息是「index out of bounds」，**看不出真正的原因**。
    改成用時間框視窗之後，一列是完全合法的輸入。
    """
    df = trace([7.0], fan_power_rel=[0.8], t_sense_c=[55.0])
    assert metrics.fan_power_rel(df) == pytest.approx(0.8)
    assert metrics.t_peak_c(df) == pytest.approx(55.0)


def test_empty_trace_says_what_is_wrong():
    """空軌跡要有**看得懂的**錯誤，不是一個索引例外。

    這條防的不是算錯，是**除錯時間**：實驗腳本半夜跑出一份空 CSV 時，
    錯誤訊息決定你是三秒還是三十分鐘看出問題。
    """
    df = trace([], fan_power_rel=[])
    with pytest.raises(ValueError, match="空的軌跡"):
        metrics.fan_power_rel(df)


def test_missing_time_column_says_what_is_wrong():
    """缺 `t_s` 欄時要點名是哪一欄，不要丟一個 KeyError('t_s') 讓人猜。"""
    df = pd.DataFrame({"fan_power_rel": [1.0, 2.0]})
    with pytest.raises(KeyError, match="t_s"):
        metrics.fan_power_rel(df)


def test_implemented_registry_matches_what_actually_works():
    """兩張 registry 要與現況一致。

    它們是 `python bench/metrics.py <csv>` 印出來的東西，也是「哪些指標
    可以用」的單一事實來源。表裡列了但其實會爆的話，CLI 會在使用者面前炸開。
    """
    df = trace([0.0, 1.0],
               t_sense_c=[10.0, 20.0],
               pwm=[30.0, 40.0],
               fan_power_rel=[0.1, 0.3])
    for name, fn in metrics.IMPLEMENTED.items():
        assert isinstance(fn(df), float), f"{name} 沒有回傳 float"
    for name, fn in metrics.IMPLEMENTED_WITH_SETPOINT.items():
        assert isinstance(fn(df, 65.0), float), f"{name} 沒有回傳 float"


def test_every_implemented_metric_is_registered_somewhere():
    """★ 防：實作了指標卻忘了註冊。

    忘了註冊的症狀是 `python bench/metrics.py <csv>` **少印一行** ——
    沒有錯誤、沒有警告，而且那支 CLI 正是「我手上有哪些數字」的入口。
    W6 一次加了四個指標，這正是最容易漏掉一個的時候。

    ⚠️ 這裡寫死清單是刻意的：拿 registry 去比對 registry 等於沒驗。
       下一次新增指標（W9 的 e2e_latency_ms）時，這一行要跟著改 ——
       那也是刻意的。
    """
    expected = {"t_peak_c", "fan_power_rel", "pwm_pp", "reversals_per_min",
                "overshoot_c", "settle_s", "recover_s", "integral_max"}
    registered = set(metrics.IMPLEMENTED) | set(metrics.IMPLEMENTED_WITH_SETPOINT)
    assert registered == expected

    overlap = set(metrics.IMPLEMENTED) & set(metrics.IMPLEMENTED_WITH_SETPOINT)
    assert not overlap, f"同一個指標出現在兩張表：{overlap}"
