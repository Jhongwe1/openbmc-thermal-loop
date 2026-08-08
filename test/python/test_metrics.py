"""bench/metrics.py 的 L0 測試。

★ 為什麼這份檔案存在
    `metrics.py` 是**全專案每一個應變因的唯一定義來源**
    （docs/measurement.md §2 自己這樣寫），而在 2026-08-09 之前它**一個測試都沒有**。
    對照組：C++ 那一側有 26 個 gtest case 加上 21 個被證明會咬人的 mutation；
    Python 這一側只有 `ruff`，而 ruff 只查風格，不查算得對不對。

    這很重要是因為 W7 的招牌宣稱 `recover_s_ratio` 就是這裡的函式算出來的。
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


def test_unimplemented_metrics_are_explicit_about_which_week():
    """★ 還沒實作的指標要**大聲**沒實作。

    這一條防的是「W6 忘了實作，但某個地方已經在呼叫它」——
    `NotImplementedError` 會炸，回一個 0.0 或 NaN 不會，
    而 NaN 一路流進 claims.json 與圖上是最難查的一種錯。
    """
    df = trace([0.0, 1.0], t_sense_c=[1.0, 2.0])
    for fn in (metrics.overshoot_c, metrics.settle_s, metrics.recover_s):
        with pytest.raises(NotImplementedError):
            fn(df, 65.0)
    for fn in (metrics.pwm_pp, metrics.reversals_per_min):
        with pytest.raises(NotImplementedError):
            fn(df)


def test_implemented_registry_matches_what_actually_works():
    """`IMPLEMENTED` 那張表要與現況一致。

    它是 `python bench/metrics.py <csv>` 印出來的東西，也是「哪些指標可以用」
    的單一事實來源。表裡列了但其實會爆的話，CLI 會在使用者面前炸開。
    """
    df = trace([0.0, 1.0], t_sense_c=[10.0, 20.0], fan_power_rel=[0.1, 0.3])
    for name, fn in metrics.IMPLEMENTED.items():
        assert isinstance(fn(df), float), f"{name} 沒有回傳 float"
