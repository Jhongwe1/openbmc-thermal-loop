"""swampd 設定檔的守門員。

★ 這份測試守的是**證據鏈上最容易斷的一節**：
    「填進 swampd 的係數，真的是從 Fig 1 的量測算出來的嗎？」

  那條鏈是：
      開環階躍 CSV -> exp01_fit.txt (K/tau/theta)
                   -> bench/tune.py (IMC-PI，%PWM 量綱)
                   -> × 150 RPM/%PWM (串級外圈的量綱)
                   -> config/swampd/config.tuned.json

  中間任何一節手打錯，**BMC 上照樣跑得起來、log 照樣寫、圖照樣畫得出來**。
  症狀是「數字有點怪」，而不是錯誤訊息。對「這個 -220 是哪來的」這個問題，
  答不出來與答錯是同一件事 —— 所以這條鏈要有測試守著，不能靠記憶。

⚠️ 這裡刻意**重算一次**再比對，而不是把答案抄進來當常數。
   抄常數只能證明「這個檔案沒被人改過」，不能證明「它是算出來的」。
"""

import json
import pathlib

import pytest

import tune

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASELINE = ROOT / "config/swampd/config.baseline.json"
TUNED = ROOT / "config/swampd/config.tuned.json"
NOWINDUP = ROOT / "config/swampd/config.nowindup.json"
FIT = ROOT / "bench/data/exp01_fit.txt"

#: config.tuned.json 採用的 λ。改這裡就要改那個檔案，反之亦然。
ADOPTED_LAMBDA_MULT = 2.0


def load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text())


def pid_of(config: dict, name: str) -> dict:
    for pid in config["zones"][0]["pids"]:
        if pid["name"] == name:
            return pid["pid"]
    raise AssertionError(f"設定檔裡沒有名為 {name} 的 PID")


# ═══════════════════════════════════════════════════════════════════════
#  係數的來源
# ═══════════════════════════════════════════════════════════════════════


def test_tuned_gains_are_what_the_identified_plant_implies():
    """★★ 重算一次 IMC-PI，比對設定檔裡的兩個係數。

    容差 1e-9（相對）：這是同一組浮點運算，不是兩次量測，
    所以要求它們一致是合理的。差得比這多，代表數字是手打的或過期了。
    """
    k, tau, theta = tune.load_fit(FIT)
    gains = tune.imc_pi(k, tau, theta, ADOPTED_LAMBDA_MULT * tau)
    swampd = tune.to_swampd_rpm(gains)

    die0 = pid_of(load(TUNED), "die0")
    assert die0["proportionalCoeff"] == pytest.approx(
        -swampd["Kc_rpm_per_c"], rel=1e-9), (
        "proportionalCoeff 不等於重算出來的 -Kc(RPM/°C)。"
        "重跑 `python bench/tune.py --lambda-mult 2.0` 對一次。")
    assert die0["integralCoeff"] == pytest.approx(
        -swampd["Ki_rpm_per_c_s"], rel=1e-9)


def test_temp_pid_gains_are_negative():
    """★ 符號：`temp` 型別必須用負係數。

    上游 `ec::pid()` 的誤差定義是 `error = setpoint − input`，而風扇迴路的
    製程增益 K 是負的。正係數 = 正回饋，症狀不是「發散」而是
    **「鎖在起始誤差的那一邊」** —— 看起來像收斂（W5 實測：風扇衝 100%、
    溫度停在 43 °C，比目標低 22 度，而且穩得很）。

    這一條擋的就是「有一天有人覺得負號很怪，把它拿掉」。
    """
    die0 = pid_of(load(TUNED), "die0")
    assert die0["proportionalCoeff"] < 0.0
    assert die0["integralCoeff"] < 0.0


# ═══════════════════════════════════════════════════════════════════════
#  integralLimit —— 2026-08-11 修掉的那顆地雷
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("path", [BASELINE, TUNED, NOWINDUP],
                         ids=["baseline", "tuned", "nowindup"])
def test_integral_limit_is_not_a_zero_width_clamp(path):
    """★★ `integralLimit = [0, 0]` 會讓積分項**恆為 0**，而且完全不報錯。

    上游 `pid/ec/pid.cpp` 對 integralTerm 做兩次箝位，**第二次是無條件的**：

        integralTerm = clamp(integralTerm, integralLimit.min, integralLimit.max);

    `clamp(任何值, 0, 0) === 0`。所以設了 integralCoeff 也不會有積分作用，
    journal 乾淨、pidcore 照常寫、P 項照常運作 ——
    症狀只有「穩態誤差消不掉」，而你會去查係數、查取樣週期、查感測器，
    **唯獨不會查一個自己沒動過的欄位**。

    對 W7 更致命：anti-windup 的前提是積分會累積到飽和。
    積分恆為 0 的話 Fig 3 的 A/B 會是兩條一模一樣的線。
    """
    for name in ("die0", "fan0"):
        pid = pid_of(load(path), name)
        lo = pid["integralLimit_min"]
        hi = pid["integralLimit_max"]
        assert hi > lo, (
            f"{path.name} 的 {name}：integralLimit = [{lo}, {hi}] 是零寬度箝位，"
            "積分項會恆為 0 而且不會有任何錯誤訊息")


@pytest.mark.parametrize("path", [BASELINE, TUNED, NOWINDUP],
                         ids=["baseline", "tuned", "nowindup"])
def test_integral_limit_covers_the_absolute_output_range(path):
    """★★ 積分上限要涵蓋 `outLim_max` 的**絕對值**，不是輸出區間的**寬度**。

    穩態時 error → 0，所以 P 項 → 0，而 feedFwdOffsetCoeff 也是 0：

        output ≈ integralTerm

    也就是說「輸出最高能到多少」＝「積分最高能累到多少」。
    要讓 die0 PID 真的能命令到 `outLim_max = 15000 RPM`，
    積分本身就必須能到 15000。

    ⚠️ 這一條防的是一個**我自己犯過**的錯：`config/swampd/README.md` 原本
       建議 `±12000`，理由寫「涵蓋 outLim 的寬度（15000−3000）」。
       12000 是寬度不是絕對值，設它會把輸出鎖在 ~12000 RPM 上不去，
       而症狀看起來像「控制律收斂在這裡」。

    ★ 這個 bug 在 L1 看不見（bench/sim 的 outMin 剛好是 0，寬度＝絕對值），
      只有在 outMin ≠ 0 的 swampd 這一側才會現形。
      **同一個概念錯誤，換個環境才咬人。**
    """
    for name in ("die0", "fan0"):
        pid = pid_of(load(path), name)
        assert pid["integralLimit_max"] >= pid["outLim_max"], (
            f"{path.name} 的 {name}：integralLimit_max="
            f"{pid['integralLimit_max']} 小於 outLim_max={pid['outLim_max']}，"
            "穩態輸出會被積分箝位擋在 outLim_max 之下")


# ═══════════════════════════════════════════════════════════════════════
#  兩個設定檔的關係
# ═══════════════════════════════════════════════════════════════════════


def test_tuned_differs_from_baseline_only_in_the_outer_pid_gains():
    """★ 單變因：tuned 與 baseline 的差別只能是外圈的兩個係數。

    W7 的 Fig 3 是 A/B 對照，而 A/B 的前提是「兩個設定檔 diff 只差一個欄位」。
    這裡先把 W6 這一組守住 —— 如果連 baseline → tuned 都不只差係數，
    那 W7 的 diff 截圖就證明不了任何事。
    """
    base, tuned = load(BASELINE), load(TUNED)
    assert base["sensors"] == tuned["sensors"], "感測器區塊不該有差異"

    allowed = {"proportionalCoeff", "integralCoeff"}
    for name in ("die0", "fan0"):
        b, t = pid_of(base, name), pid_of(tuned, name)
        assert set(b) == set(t), f"{name} 的 PID 欄位集合不同"
        differing = {key for key in b if b[key] != t[key]}
        assert differing <= allowed, (
            f"{name} 除了係數之外還差了 {differing - allowed} —— "
            "這會讓 baseline/tuned 的對照不是單變因")

    zone_keys = {"id", "minThermalOutput", "failsafePercent"}
    for key in zone_keys:
        assert base["zones"][0][key] == tuned["zones"][0][key]


def test_inner_fan_pid_is_feedforward_only_by_design():
    """內圈 fan0：回授係數留 0（W6 的決定）＋ 唯一的前饋增益 1/150（W7）。

    W6 的理由不變：plant 沒有建模個別風扇的轉速誤差，**沒有量測就不整定
    回授**。W7 加的 `feedFwdGainCoeff` 不是整定出來的增益，是量綱換算：
    上游 `pid/ec/pid.cpp:101` 是 `feedFwdTerm = (setpoint + off) × gain`，
    而 fan PID 的 setpoint 就是外圈的 RPM 輸出（`fancontroller.cpp` 的
    `setptProc()` → `getMaxSetPointRequest()`）。gain = 1/150 = 100%/15000 RPM，
    與 `bench/tune.py` 的 `to_swampd_rpm()` 是同一個常數 ——
    PWM 純前饋地追隨外圈輸出，不引入任何內圈動態。

    ⚠️ W6 時內圈全 0，PWM 箝死在 `outLim_min = 30%` —— 那時 L2 的迴路
       其實沒有閉起來（runbook §4.8 記過這件事）。W7 要讓真 swampd 對
       plant 閉環，「把外圈輸出傳遞出去」是達成它的最小改動。
       三份設定檔一致：**這不是 A/B 的變因。**
    """
    for path in (BASELINE, TUNED, NOWINDUP):
        fan0 = pid_of(load(path), "fan0")
        assert fan0["proportionalCoeff"] == 0.0
        assert fan0["integralCoeff"] == 0.0
        assert fan0["feedFwdGainCoeff"] == pytest.approx(1.0 / 150.0)
        assert fan0["feedFwdOffsetCoeff"] == 0.0


# ═══════════════════════════════════════════════════════════════════════
#  W7 的 A/B 配對 —— Fig 3 的單變因宣言，機器版
# ═══════════════════════════════════════════════════════════════════════


def test_nowindup_differs_from_tuned_only_in_the_outer_integral_limit():
    """★★ README 貼的 diff 說「只差兩行」—— 這裡讓它不是修辭。

    A/B 的可信度整個掛在這上面：如果 nowindup 順手動了別的欄位
    （哪怕是 fan0 的一個小數點），Fig 3 的差異就再也不能歸因給
    integralLimit 這一個機制。守到欄位級；連 `_comment` 都要逐字相同 ——
    兩檔共用同一段說明，`diff` 的輸出才乾淨到只剩那兩行。
    """
    tuned, nw = load(TUNED), load(NOWINDUP)
    assert tuned["_comment"] == nw["_comment"], "_comment 必須逐字相同"
    assert tuned["sensors"] == nw["sensors"], "感測器區塊不准有差異"

    for key in ("id", "minThermalOutput", "failsafePercent"):
        assert tuned["zones"][0][key] == nw["zones"][0][key]

    fan_t, fan_n = pid_of(tuned, "fan0"), pid_of(nw, "fan0")
    assert fan_t == fan_n, "內圈 fan0 不准有任何差異"

    die_t, die_n = pid_of(tuned, "die0"), pid_of(nw, "die0")
    assert set(die_t) == set(die_n)
    differing = {key for key in die_t if die_t[key] != die_n[key]}
    assert differing == {"integralLimit_min", "integralLimit_max"}, (
        f"die0 的差異是 {differing}，"
        "但 A/B 的自變因只允許 integralLimit 兩行")


def test_nowindup_limit_is_wide_enough_to_never_bind():
    """「等同關閉」要是真的 —— 上下界都要離可能的積分值夠遠。

    ±1e6 對 outLim_max = 15000 有 66 倍餘裕。這一條防的是哪天有人把它
    「改合理一點」改到會夾到的量級：那樣 open arm 就不再是對照組，
    A/B 變成「兩種箝位強度」的比較 —— 一個完全不同的實驗。
    """
    die0 = pid_of(load(NOWINDUP), "die0")
    assert die0["integralLimit_max"] >= 10 * die0["outLim_max"]
    assert die0["integralLimit_min"] <= -10 * die0["outLim_max"]
