"""exp10 分析器的單元測試 —— 合成串流測邏輯;真樣本測 contract(W8 教訓:
兩種都要有)。真資料收完後 test_real_* 會自動生效。

合成模型刻意重現真實 rig 的兩種病:
  * 到達時戳是**批次**的(ssh 鏈 ~8 KB 塊緩衝)—— 事件時刻必須來自
    payload 的源頭時戳;
  * 配對必須走**序列索引**,不走時鐘閘門(guest 時鐘鋸齒會把跨域
    閘門騙去 16 s 後的下一個同電平 rep)。
每條測試都標了它守的 mutation(tools/mutation_check.sh 的 T 家族)。
"""

import pathlib
import sys
from datetime import datetime, timezone

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bench"))
sys.path.insert(0, str(REPO / "tools"))

from exp10_latency import (  # noqa: E402
    align_sequence,
    build_sequences,
    characterize_sawtooth,
    dbus_value_events,
    detect_rep_events,
    parse_busctl_ts,
    parse_zone_line,
    summarize,
    validate_sequences,
)

from set_die_temp import expected_hwmon_mC  # noqa: E402

#: 量化後的預測值 —— 不寫死數字,直接用注入模型算(它有自己的回歸測試)。
EXP90 = expected_hwmon_mC(90_000) / 1000.0
EXP55 = expected_hwmon_mC(55_000) / 1000.0
EXP70 = expected_hwmon_mC(70_000) / 1000.0   # 中性預位,不屬於任何電平

#: 合成時鐘:host ≈ bmc + OFFSET(僅用於造「到達」;分析不依賴它)。
OFFSET = 5.0
B0 = 1_786_480_000.0
H0 = B0 + 100.0 + OFFSET          # rep 的 t_inject(host 域)


def fmt_busctl(bmc_ts: float) -> str:
    return datetime.fromtimestamp(bmc_ts, tz=timezone.utc).strftime(
        "%a %Y-%m-%d %H:%M:%S.%f")


def dbus_msg(bmc_ts: float, value: float, arrival: float):
    """一則 busctl 訊息的兩行:頭(帶 Timestamp)+ DOUBLE 值行。"""
    return [
        (arrival, f'‣ Type=signal  Endian=l  Flags=1  Version=1 '
                  f'Cookie=7  Timestamp="{fmt_busctl(bmc_ts)} UTC"'),
        (arrival, f"                                  DOUBLE {value:.3f};"),
    ]


def zone_line(epoch_ms: float, setpt: float, pwm: float, die0: float) -> str:
    return (f"{int(epoch_ms)},{setpt},Minimum,3000,3000,"
            f"{pwm},-1,{die0},{die0},0")


def make_rep(level: float, expected: float) -> dict:
    return {"rep": 2, "level_c": level, "expected_c": expected,
            "t_qmp_before": H0 - 0.001, "t_inject": H0,
            "warmup": False}


def happy_streams():
    """一個乾淨 rep:70(中性)→ 90,BMC 域注入時刻 = B0+100。

    * dbus 有**兩則**連續同值訊號(真實 dbus-sensors 每次變化發兩則)
      —— 序列建構必須去重(mutation T5)。
    * 所有到達時戳晚源頭 12~16 s(批次)—— 用到到達就會爆。
    """
    dbus_raw = []
    dbus_raw += dbus_msg(B0 + 100.8, EXP90, H0 + 12.0)   # 真事件
    dbus_raw += dbus_msg(B0 + 100.85, EXP90, H0 + 12.0)  # 第二則(同值)

    zrows = []
    t = B0 + 99.0
    while t < B0 + 104.0:
        die0 = EXP90 if t >= B0 + 101.3 else EXP70
        setpt = 5500.0 if t >= B0 + 102.1 else 3000.0
        pwm = 0.3667 if t >= B0 + 102.2 else 0.3
        zrows.append((t + OFFSET + 16.0,
                      parse_zone_line(zone_line(t * 1000.0, setpt, pwm, die0))))
        t += 0.1

    redfish = [
        (H0 - 1.0, H0 - 0.9, EXP70),
        (H0 - 0.4, H0 - 0.3, EXP70),                     # t0 前的錨
        (H0 + 0.4, H0 + 0.5, EXP70),
        (H0 + 1.2, H0 + 1.3, EXP70),
        (H0 + 2.0, H0 + 2.1, EXP70),
        (H0 + 2.8, H0 + 2.9, EXP90),                     # 真事件
        (H0 + 3.6, H0 + 3.7, EXP90),
    ]
    return dbus_raw, zrows, redfish


def detect(dbus_raw, zrows, redfish):
    rep = make_rep(90.0, EXP90)
    seqs = build_sequences(dbus_value_events(dbus_raw), zrows, redfish)
    aligns = validate_sequences([rep], *seqs)
    return detect_rep_events(rep, 0, seqs, aligns, zrows, redfish)


def test_segments_from_synthetic_streams():
    """守 T1(②偷改基準)與序列配對的整條路。批次到達下仍要對。"""
    ev = detect(*happy_streams())
    # ②:zone 第一列 die0=新值(B0+101.3 之後最近的 0.1 格)− dbus 源頭
    assert ev["seg2_s"] == pytest.approx(
        ev["t_zone_bmc"] - (B0 + 100.8), abs=1e-6)
    assert B0 + 101.3 <= ev["t_zone_bmc"] < B0 + 101.5
    # ③:純 BMC 域(setpt 變 → pwm 變,合成資料裡差 0.1)
    assert ev["seg3_s"] == pytest.approx(0.1, abs=0.02)
    # total:純 host 域
    assert ev["total_redfish_s"] == pytest.approx(2.9, abs=1e-6)


def test_detection_matches_quantized_value_not_requested():
    """守 T4:序列比對用 expected_hwmon_mC 的量化預測(89.938…),
    不是注入的 90.0 —— 差一整個 −1 LSB 偏壓,拿錯邊序列會是空的。"""
    assert abs(90.0 - EXP90) > 0.02, "量化偏壓應大於比對容差,前提自檢"
    ev = detect(*happy_streams())
    assert ev["total_redfish_s"] == pytest.approx(2.9, abs=1e-6)


def test_legacy_head_is_aligned_past():
    """legacy 頭(上次中止 run 留在 zone log 的舊高原)必須被對齊跳過,
    段差不受影響 —— swampd 的 ofstream 緩衝讓舊資料流進本次捕捉是
    實測現象,不是假想。"""
    dbus_raw, zrows, redfish = happy_streams()
    legacy = dbus_msg(B0 + 90.0, EXP55, H0 - 20.0)       # 舊高原的殘影
    ev = detect(legacy + dbus_raw, zrows, redfish)
    assert ev["total_redfish_s"] == pytest.approx(2.9, abs=1e-6)
    assert ev["seg2_s"] == pytest.approx(
        ev["t_zone_bmc"] - (B0 + 100.8), abs=1e-6)


def test_align_sequence_contract():
    """對齊的四種邊界:乾淨、legacy 頭、截斷尾、中段錯位。"""
    want = [EXP90, EXP55, EXP90]
    seq = [(EXP90, 0), (EXP55, 1), (EXP90, 2)]
    assert align_sequence("x", seq, want, 2) == (0, 3)
    assert align_sequence("x", [(EXP55, 9), *seq], want, 2) == (1, 3)
    assert align_sequence("x", seq[:2], want, 2) == (0, 2)   # 截斷尾
    with pytest.raises(SystemExit, match="多餘"):
        align_sequence("x", [*seq, (EXP55, 9), (EXP90, 10)], want[:2], 2)
    with pytest.raises(SystemExit, match="對不上"):
        align_sequence("x", [(EXP55, 0)], want, 2)


def test_truncated_tail_marks_rep_invalid():
    """尾端缺失的 rep 要 RepInvalid,不是硬湊或默默少一個。"""
    dbus_raw, zrows, redfish = happy_streams()
    rep = make_rep(90.0, EXP90)
    seqs = build_sequences(dbus_value_events(dbus_raw), zrows, redfish)
    aligns = validate_sequences([rep], *seqs)
    aligns["zone"] = (aligns["zone"][0], 0)   # 模擬 zone 尾端全缺
    with pytest.raises(SystemExit, match="尾端缺失"):
        detect_rep_events(rep, 0, seqs, aligns, zrows, redfish)


def test_duplicate_signals_are_deduped():
    """守 T5:dbus-sensors 每次變化發兩則 PropertiesChanged,序列建構
    必須把連續同電平去重 —— happy_streams 本身就帶兩則。"""
    dbus_raw, zrows, redfish = happy_streams()
    seqs = build_sequences(dbus_value_events(dbus_raw), zrows, redfish)
    assert len(seqs[0]) == 1, "兩則同值訊號應合併成一個轉換"


def test_setpt_event_ignores_pre_arrival_ramp():
    """守「跟前一列比」:t_zone 之前的 setpt 斜坡(上一 rep 的積分殘餘)
    不得被當成 ③ 的起點。"""
    dbus_raw, zrows, redfish = happy_streams()
    ramped = []
    for arr, r in zrows:
        if r["epoch_ms"] / 1000.0 < B0 + 101.0:
            r = {**r, "setpt": 5000.0 + (r["epoch_ms"] / 1000.0 - B0) * 12.5}
        ramped.append((arr, r))
    ev = detect(dbus_raw, ramped, redfish)
    assert ev["t_setpt_bmc"] >= B0 + 102.0, "抓到斜坡殘餘而不是回應 tick"


def test_clock_jump_in_window_rejected():
    """守 T2:rep 窗內 guest epoch 出現跳步(+7.6 s)→ RepInvalid。"""
    dbus_raw, zrows, redfish = happy_streams()
    jumped = []
    for arr, r in zrows:
        ep = r["epoch_ms"] / 1000.0
        if ep >= B0 + 101.8:   # 在 zone 事件(101.3)與 pwm(102.2)之間跳步
            r = {**r, "epoch_ms": r["epoch_ms"] + 7600.0}
        jumped.append((arr, r))
    with pytest.raises(SystemExit, match="行距"):
        detect(dbus_raw, jumped, redfish)


def test_host_freeze_rejected():
    """守健康 (b):rep 窗內 Redfish 的 host 節奏斷檔 = host 凍結。"""
    dbus_raw, zrows, redfish = happy_streams()
    frozen = [(a, b, v) for a, b, v in redfish
              if not (H0 + 0.4 < b < H0 + 2.85)]
    with pytest.raises(SystemExit, match="host"):
        detect(dbus_raw, zrows, frozen)


def test_sawtooth_characterization():
    """鋸齒量化:兩次 +7.6 s 跳步要被數出來。"""
    _, zrows, _ = happy_streams()
    jumped = []
    for arr, r in zrows:
        ep = r["epoch_ms"] / 1000.0
        bump = 7600.0 * ((ep >= B0 + 100.0) + (ep >= B0 + 103.0))
        jumped.append((arr, {**r, "epoch_ms": r["epoch_ms"] + bump}))
    st = characterize_sawtooth(jumped)
    assert st["count"] == 2
    assert st["amplitude_median_s"] == pytest.approx(7.6, abs=0.1)


def _rows(values, warmup=False):
    keys = ("seg2_s", "seg3_s", "total_redfish_s")
    return [{"warmup": warmup, **{k: float(v) for k in keys}}
            for v in values]


def test_summary_median_and_p95():
    """守 T3:p95 是 quantiles(inclusive) 的第 19 格,不是 max。"""
    rows = _rows(range(1, 31))
    s = summarize(rows)
    assert s["n"] == 30
    assert s["seg2_s"]["median"] == pytest.approx(15.5)
    assert s["seg2_s"]["p95"] == pytest.approx(28.55)
    assert s["seg2_s"]["max"] == pytest.approx(30.0)


def test_summary_excludes_warmup():
    """守 T6:暖身 rep 事前宣告排除 —— 塞兩筆 999 的暖身,統計不得動。"""
    rows = _rows(range(1, 31)) + _rows([999, 999], warmup=True)
    s = summarize(rows)
    assert s["n"] == 30
    assert s["seg2_s"]["median"] == pytest.approx(15.5)
    assert s["seg2_s"]["max"] == pytest.approx(30.0)


def test_parse_busctl_ts_contract():
    """守 busctl 時戳解析:取樣自真實輸出格式。"""
    ts = parse_busctl_ts("Tue 2026-08-11 20:34:33.322285")
    expect = datetime(2026, 8, 11, 20, 34, 33, 322285,
                      tzinfo=timezone.utc).timestamp()
    assert ts == pytest.approx(expect, abs=1e-6)


def test_parse_zone_line_contract():
    line = zone_line(1786476075189, 3000.0, 0.3, 0.0)
    row = parse_zone_line(line)
    assert row == {"epoch_ms": 1786476075189.0, "setpt": 3000.0,
                   "fan0_pwm": 0.3, "die0": 0.0}
    assert parse_zone_line("not,a,zone,row") is None
    assert parse_zone_line("") is None


REAL_ZONE = REPO / "bench/data/exp10_latency/streams/zone.log"


@pytest.mark.skipif(not REAL_ZONE.exists(), reason="真資料還沒收")
def test_real_zone_rows_parse():
    """真樣本 contract 測試(W8:合成資料測不出「我對格式的想像是錯的」)。"""
    lines = REAL_ZONE.read_text().splitlines()[:200]
    parsed = [parse_zone_line(ln.partition("\t")[2]) for ln in lines]
    ok = [p for p in parsed if p is not None]
    assert len(ok) >= 10, "真 zone 串流前 200 行應該解析得出至少 10 列"


REAL_DBUS = REPO / "bench/data/exp10_latency/streams/dbus.log"


@pytest.mark.skipif(not REAL_DBUS.exists(), reason="真資料還沒收")
def test_real_dbus_rows_parse():
    """真樣本:busctl 串流要解析得出帶 BMC 時戳的值事件。"""
    rows = []
    for line in REAL_DBUS.read_text().splitlines()[:400]:
        t, _, payload = line.partition("\t")
        rows.append((float(t), payload))
    events = dbus_value_events(rows)
    assert len(events) >= 2, "前 400 行應該至少有 2 筆值事件"
