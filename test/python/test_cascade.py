"""bench/exp06_cascade.py 的分析函式測試。

★ 為什麼分析要從採集裡拆出來
    採集需要 QEMU 跑著、需要 sshpass、需要 90 秒。分析不需要 ——
    所以分析是**純函式**，測得到、也進得了 CI（W10）。
    合在一起的話，`docs/cascade.md` 上那兩個數字就永遠只能靠
    「我在我機器上跑過」來背書。

★ 每一條測試都對應一個**真的會發生**的資料缺陷，不是湊出來的邊界。
"""

import pytest

import exp06_cascade as cascade

HEADER = ("epoch_ms,setpt,requester,fan0,fan0_raw,fan0_pwm,fan0_pwm_raw,"
          "die0,die0_raw,failsafe")


def line(epoch_ms: int, setpt: float, requester: str = "die0") -> str:
    return f"{epoch_ms},{setpt},{requester},3000,3000,0.3,-1,84.938,84938,0"


def log(*rows: str) -> str:
    return "\n".join([HEADER, *rows])


# ═══════════════════════════════════════════════════════════════════════
#  解析
# ═══════════════════════════════════════════════════════════════════════


def test_truncated_last_line_is_dropped():
    """★★ 最後一行常常是截斷的 —— log 還在寫。

    這是 2026-08-11 從 BMC 抓回來的檔案裡**真的長這樣**：
    `_log << std::endl` 之前已經有部分內容進了檔案。

    不濾掉的話，`int(fields[0])` 會拿到一個看起來正常的時間戳、
    但那一列其他欄位全缺 —— 而它剛好會製造出一個假的「最大間隔」，
    落在報告的 max 那一格上。
    """
    text = log(line(1000, 3000.0), line(1100, 3000.0)) + "\n1786385346427"
    rows = cascade.parse_zone_log(text)
    assert len(rows) == 2
    assert [r["epoch_ms"] for r in rows] == [1000, 1100]


def test_unexpected_header_is_rejected_loudly():
    """欄位順序變了要當場停，不要照著算。

    上游哪天在 `initializeLog()` 前面插一欄，這份分析會安靜地
    把別的東西當成時間戳 —— 而算出來的數字仍然「像個週期」。
    """
    with pytest.raises(ValueError, match="epoch_ms"):
        cascade.parse_zone_log("t,setpt\n1,2")


# ═══════════════════════════════════════════════════════════════════════
#  內圈：相鄰行的間隔
# ═══════════════════════════════════════════════════════════════════════


def test_fan_cycle_reports_the_median_not_the_mean():
    """★★ 一筆離群值就足以讓平均失真 —— 而 QEMU 每分鐘都在製造離群值。

    九筆 100 ms 加一筆 7805 ms：
      · 中位數 = **100**（正確描述這個迴路）
      · 平均   = **870.5**（錯 8.7 倍）

    實測資料的平均是 118.8 ms、中位數 100 ms。報平均會讓
    「swampd 內圈 10 Hz」這句話變成「約 8.4 Hz」。
    """
    times = [0, 100, 200, 300, 400, 500, 600, 700, 800, 8605]
    rows = cascade.parse_zone_log(log(*(line(t, 3000.0) for t in times)))
    stats = cascade.fan_cycle_ms(rows)
    assert stats["median"] == pytest.approx(100.0)
    assert stats["mean_for_contrast"] > 800.0
    assert stats["max"] == 7805


def test_fan_cycle_ignores_non_positive_gaps():
    """時間戳沒有前進的列不算一次 cycle。

    重啟 swampd 時新舊 log 可能接在一起，時間戳會倒退。
    負的間隔混進去會把中位數往下拉，而且**不會有任何警告**。
    """
    rows = cascade.parse_zone_log(
        log(line(1000, 3000.0), line(1100, 3000.0), line(900, 3000.0),
            line(1000, 3000.0)))
    stats = cascade.fan_cycle_ms(rows)
    assert stats["n"] == 2
    assert stats["median"] == pytest.approx(100.0)


# ═══════════════════════════════════════════════════════════════════════
#  外圈：setpt 變化的間隔
# ═══════════════════════════════════════════════════════════════════════


def test_thermal_update_measures_gaps_between_setpoint_changes():
    """外圈週期 = `setpt` 欄變化的間隔，不是行的間隔。

    這裡每 10 行（1000 ms）setpt 才變一次，其餘 9 行原封不動 ——
    正是實機的樣子（內圈 100 ms、外圈 1000 ms）。
    """
    rows = []
    setpt = 3000.0
    for i in range(31):
        if i % 10 == 0 and i > 0:
            setpt += 99.88
        rows.append(line(i * 100, setpt))
    stats = cascade.thermal_update_ms(cascade.parse_zone_log(log(*rows)))
    assert stats["median"] == pytest.approx(1000.0)
    assert stats["n"] == 3


def test_a_frozen_setpoint_raises_instead_of_returning_a_number():
    """★ setpt 一動也不動時要**報錯**，不要回一個像樣的數字。

    這種情況真的會發生：輸出被箝在 `outLim` 上、或溫度根本沒注入。
    回 0、回 NaN、或回「唯一那次變化的間隔」都會變成一個
    看起來合理、但量的是別的東西的數字 —— 而那正是這整個實驗
    要防的失敗模式（見 docs/cascade.md §2）。

    訊息裡要指出下一步該看哪裡，不是只說「失敗」。
    """
    rows = [line(i * 100, 3000.0) for i in range(20)]
    with pytest.raises(ValueError, match="outLim|pidcore"):
        cascade.thermal_update_ms(cascade.parse_zone_log(log(*rows)))


# ═══════════════════════════════════════════════════════════════════════
#  repo 裡那份真的資料
# ═══════════════════════════════════════════════════════════════════════


def test_the_committed_capture_still_gives_the_documented_constants():
    """★★ `docs/cascade.md` 與 `claims.json` 上那兩個數字，要能從
    repo 裡那份原始 log **重算出來**。

    這一條是「別人 clone 下來能不能自己驗一次」的最小版本：
    不需要 QEMU、不需要 BMC、不需要 90 秒，只需要那個檔案。
    """
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[2]
    zone = root / "bench/data/exp06_cascade/zone_0.log"
    if not zone.exists():
        pytest.skip("還沒採集 exp06 的資料（python bench/exp06_cascade.py --collect）")

    result = cascade.analyse(zone.read_text())
    assert result["fan_cycle_ms"]["median"] == pytest.approx(100.0, abs=5.0)
    assert result["thermal_update_ms"]["median"] == pytest.approx(1000.0, abs=10.0)
    # 而且平均**確實**被離群值污染 —— 這是報中位數的理由，不是藉口
    assert result["fan_cycle_ms"]["mean_for_contrast"] > \
        result["fan_cycle_ms"]["median"]
