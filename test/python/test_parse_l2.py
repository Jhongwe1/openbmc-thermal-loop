"""bench/parse_l2.py 的 L0 測試 —— 樣本行取自**真實抓回來的 log**。

★ 為什麼固定樣本要用真實行（exp06 與 W7 smoke 的原文），不自己編：
    這些 loader 的全部工作就是「把上游的格式翻譯對」。用自己編的樣本
    測翻譯，等於拿自己的想像驗自己的想像 —— 欄位順序記錯時兩邊會
    一起錯，測試照樣綠。取真實行，格式的事實才在測試裡。
    （唯一的例外是 pidcore 的箝位差異列 —— 真實 log 裡 integralTerm1
    與 integralTerm 恰好相等，分不出抓錯欄，所以那一列是**構造**的，
    構造規則寫在該測試的 docstring。）
"""

import io
import textwrap

import pandas as pd
import pytest

import parse_l2
from tune import RPM_PER_PCT

#: exp06 從 BMC 抓回的 zone_0.log 原文前三行（含第一行 fan0_pwm 為 nan）。
ZONE_SAMPLE = textwrap.dedent("""\
    epoch_ms,setpt,requester,fan0,fan0_raw,fan0_pwm,fan0_pwm_raw,die0,die0_raw,failsafe
    1786386117853,4491.8,die0,3000,3000,nan,nan,84.938,84.938,0
    1786386117960,4491.8,die0,3000,3000,0.3,-1,84.938,84.938,0
    """)

#: pidcore.die0 的標頭是真實的；第二列把 integralTerm1（箝位前）改成 250、
#: integralTerm（最終箝位後）維持 100 —— 兩欄不同，抓錯欄位就會現形。
PIDCORE_SAMPLE = textwrap.dedent("""\
    epoch_ms,input,setpoint,error,proportionalTerm,integralTerm1,integralTerm2,derivativeTerm,feedFwdTerm,output1,output2,minOut,maxOut,integralTerm3,output3,integralTerm,output
    1786386117744,84.938,65,-19.938,4391.92,99.8798,99.8798,-0,0,4491.8,4491.8,0,0,99.8798,4491.8,99.8798,4491.8
    1786386118856,84.938,65,-19.938,4391.92,250,250,0,0,4591.67,4591.67,0,0,100,4591.67,100,4591.67
    """)

EPOCH0 = 1786386117744.0


def zone_df(tmp_path):
    p = tmp_path / "zone_0.log"
    p.write_text(ZONE_SAMPLE)
    return parse_l2.zone_frame(p, EPOCH0)


def test_zone_pwm_is_scaled_from_fraction_to_percent(tmp_path):
    """★ 防：把 0~1 的 `fan0_pwm` 直接當百分比餵指標。

    後果不是報錯，是**假好看**：PWM 永遠 < 90，recover_s 的門檻
    在第一筆就滿足，windup 最嚴重的那組也會得到「恢復 0 秒」。
    實測 30% 在 log 裡記成 0.3 —— 這一條就是把那個事實釘住。
    """
    df = zone_df(tmp_path)
    assert df["pwm"].iloc[1] == pytest.approx(30.0)


def test_zone_time_is_anchored_to_the_bridge_epoch(tmp_path):
    """防：忘了對時（或 ms/s 弄錯 1000 倍）。

    zone log 記牆上時鐘、bridge CSV 記相對秒；錨點就是 bridge 的
    epoch0。第二列與錨點差 216 ms → t_s 必須是 0.216。
    """
    df = zone_df(tmp_path)
    assert df["t_s"].iloc[0] == pytest.approx((1786386117853 - EPOCH0) / 1000.0)
    assert df["t_s"].iloc[1] == pytest.approx(0.216)


def test_zone_setpt_converts_to_pwm_equiv_with_the_shared_constant(tmp_path):
    """防：150 這個量綱常數被就地重寫（或寫成 100）。

    換算常數的唯一定義在 bench/tune.py 的 RPM_PER_PCT ——
    這裡直接拿它來驗，常數改了兩邊會一起動，抄一份就不會。
    """
    df = zone_df(tmp_path)
    assert df["pwm_equiv"].iloc[0] == pytest.approx(4491.8 / RPM_PER_PCT)


def test_pidcore_integral_takes_the_final_clamped_column(tmp_path):
    """★ 防：抓成 `integralTerm1`（箝位**前**）。

    上游一輪會寫三個 integralTerm*：1 = 第一次箝位後、3 = 無條件
    箝位後、最後的 `integralTerm` 是**真正帶進下一輪的狀態**。
    構造列讓 term1=250、term=100：抓錯欄，Fig 3 第三面板的
    clamp arm 就會畫出一條「穿過箝位線」的曲線 —— 機制圖直接說謊。
    """
    p = tmp_path / "pidcore.die0"
    p.write_text(PIDCORE_SAMPLE)
    df = parse_l2.pidcore_frame(p, EPOCH0)
    assert df["integral_rpm"].iloc[1] == pytest.approx(100.0)
    assert df["integral"].iloc[1] == pytest.approx(100.0 / RPM_PER_PCT)


def test_zone_frame_feeds_metrics_time_windows_despite_jitter(tmp_path):
    """整合煙霧：zone frame 的欄位可以直接餵 metrics 的時間視窗。

    這裡不驗新數學（那是 test_metrics 的工作），只驗**欄位契約**：
    t_s / t_sense_c / pwm 三欄齊、pandas 能吃、開頭的 nan 不炸。
    樣本裡溫度 84.9 ≤ 90（i0 = 第 0 列）、pwm 第 0 列是 nan（nan < 90
    比較為 False，被跳過）、第 1 列 30 < 90 → recover_s = t[1] − t[0]
    = 0.216 − 0.109 = 0.107 s。nan 有被正確跳過，答案才是這個。
    """
    df = zone_df(tmp_path)
    import metrics
    assert metrics.t_peak_c(df) == pytest.approx(84.938)
    assert metrics.recover_s(df, setpoint=90.0) == pytest.approx(0.107)


def test_bridge_epoch0_is_read_from_the_sidecar_meta(tmp_path):
    """防：錨點從 CSV 第一列推（bridge 起動 ≠ 第一筆樣本）。"""
    csv = tmp_path / "exp07_L2_clamp_plant.csv"
    csv.write_text("t_s,pwm\n0.0,30.0\n")
    (tmp_path / "exp07_L2_clamp_plant_meta.json").write_text(
        '{"epoch0_ms": 123456.0, "args": {}}\n')
    assert parse_l2.bridge_epoch0_ms(csv) == pytest.approx(123456.0)


def test_zone_sample_roundtrips_through_pandas(tmp_path):
    """守住「樣本是合法 CSV」這個前提 —— 樣本壞了，上面全部變假綠。"""
    df = pd.read_csv(io.StringIO(ZONE_SAMPLE))
    assert list(df.columns)[:3] == ["epoch_ms", "setpt", "requester"]
    assert len(df) == 2
