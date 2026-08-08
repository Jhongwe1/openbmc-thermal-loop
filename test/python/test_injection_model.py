"""注入路徑預測式（`tools/set_die_temp.py`）的回歸測試。

★ 這份測試的形態跟其他測試不一樣，值得說明
    它不是拿我算的答案去比我算的答案 —— 那什麼都證明不了。
    它拿的是 **exp04 在真的 QEMU + 真的 kernel driver 上量到、
    而且已經進 git 的原始 CSV**，逐點比對預測式。

    也就是說：這是一份**用實測資料當黃金樣本**的回歸測試。
    QEMU 或 kernel 哪天改了轉換行為，`--verify` 會在測試床上大聲失敗；
    而如果是**我**改壞了預測式，這裡會在 CI 上先失敗 —— 不需要 BMC。

    兩個方向都有守到，才叫「把理解變成會執行的斷言」。

⚠️ 這些 CSV 是**證據**，不是可以隨手重產的中間檔。
   要更新它們必須重跑 `python bench/exp04_injection.py`（需要 BMC），
   而且要在 commit message 裡說明為什麼。
"""

import csv
import pathlib

import pytest

import set_die_temp as sdt

DATA = pathlib.Path(__file__).resolve().parents[2] / "bench/data/exp04_injection"


def rows(name: str) -> list[dict]:
    path = DATA / name
    if not path.exists():
        pytest.skip(f"{path} 不在 —— 先跑 python bench/exp04_injection.py")
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


# ═══════════════════════════════════════════════════════════════════════
#  對照實測資料
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("name", ["grid.csv", "sweep.csv"])
def test_predictor_reproduces_every_measured_point(name):
    """預測式要命中**每一個**實測點，零誤差。

    防的是「我調整了預測式，順手把某一段改壞了」——
    例如把 C 的往 0 截斷改成 Python 的 `//`，或把 DIV_ROUND_CLOSEST
    寫成 `(x + d // 2) // d`。那兩種在正溫度區間看不出差別，
    所以只靠手算幾個點是驗不到的。
    """
    data = rows(name)
    assert data, f"{name} 是空的"
    mismatches = [
        (r["requested_mC"], sdt.expected_hwmon_mC(int(r["requested_mC"])),
         int(r["hwmon_mC"]))
        for r in data
        if sdt.expected_hwmon_mC(int(r["requested_mC"])) != int(r["hwmon_mC"])
    ]
    assert not mismatches, f"{len(mismatches)}/{len(data)} 個點對不上：{mismatches[:5]}"


def test_grid_points_all_come_back_one_full_step_low():
    """落在 1/16 格點上的要求值一律低整整一格 —— 而且是**系統性**的。

    這一條釘住的是一個結論，不是一個實作細節：
    如果哪天量到的偏壓不再是一致的 −62，那代表注入路徑變了，
    `docs/plant-model.md` §2.1 的推導要重做。
    """
    data = rows("grid.csv")
    biases = {int(r["hwmon_mC"]) - int(r["requested_mC"]) for r in data}
    assert biases == {-62}, f"偏壓不再是一致的 −62：{sorted(biases)}"


def test_sweep_shows_a_staircase_with_one_lsb_treads():
    """解析度的證據是**階梯**，不是單一個點。

    ⚠️ 一格是 62.5 m°C，不是整數，所以相鄰階距會在 62 與 63 之間交替。
       斷言寫成「等於 63」會在換一段掃描範圍時假性失敗。
    """
    data = rows("sweep.csv")
    levels: list[int] = []
    for r in data:
        value = int(r["hwmon_mC"])
        if not levels or value != levels[-1]:
            levels.append(value)
    assert len(levels) >= 5, f"只有 {len(levels)} 個相異階，掃描範圍太窄"
    # strict=False：levels[1:] 本來就短一個，這裡要的就是相鄰配對。
    gaps = {b - a for a, b in zip(levels, levels[1:], strict=False)}
    assert gaps <= {62, 63}, f"階距出現 {sorted(gaps)}，LSB 不再是 1/16 °C"


# ═══════════════════════════════════════════════════════════════════════
#  C 語言語意（這些是預測式最容易寫錯的地方）
# ═══════════════════════════════════════════════════════════════════════


def test_c_division_truncates_toward_zero_not_down():
    """C 的整數除法往 0 截，Python 的 `//` 往下取整 —— 負值時差一。

    QEMU setter 裡就是一個 C 的整數除法。用 `//` 寫的話，
    正溫度全部正確、負溫度全部差一格，而這個專案平常只用正溫度 ——
    **一個永遠不會在日常使用中暴露的錯**。
    """
    assert sdt._c_div(-7, 2) == -3      # Python 的 -7 // 2 是 -4
    assert sdt._c_div(7, 2) == 3
    assert sdt._c_div(-7, -2) == 3
    assert sdt._c_div(7, -2) == -3


def test_div_round_closest_rounds_half_away_from_zero():
    """Linux 的 DIV_ROUND_CLOSEST 對負值是「減半個除數再截」。

    寫成 `(x + d // 2) // d` 的話，負值會往錯的方向捨入。
    """
    assert sdt._div_round_closest(5, 2) == 3        # 2.5 -> 3
    assert sdt._div_round_closest(-5, 2) == -3      # -2.5 -> -3（不是 -2）
    assert sdt._div_round_closest(4, 2) == 2
    assert sdt._div_round_closest(0, 256) == 0


def test_prediction_is_insensitive_to_the_extended_range_bit():
    """★ 擴充量程的 offset 是 64*256 = 16384，**是 16 的倍數**。

    所以它在 `reg & ~0xf` 這個遮罩下進出自如，兩種量程對正溫度給出同一個預測。
    這一條把「我不知道 CONFIG 的 range 位元是什麼」從一個風險
    變成一個**已證明不重要**的細節 —— 那是兩件不同的事。
    """
    for requested in (0, 25000, 40000, 42500, 100000, 126999):
        assert (sdt.expected_hwmon_mC(requested, ext_range=False)
                == sdt.expected_hwmon_mC(requested, ext_range=True)), requested


def test_worked_example_from_the_documentation():
    """docs/plant-model.md §2.1 逐步算的那個例子，釘住它。

    文件裡的算式與程式碼分家，是文件過期最常見的方式。
    """
    assert sdt.expected_hwmon_mC(42500) == 42438
    assert sdt.expected_hwmon_mC(40000) == 39938
