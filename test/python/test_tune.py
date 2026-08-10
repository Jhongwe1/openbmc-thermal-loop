"""bench/tune.py 的 L0 測試。

★ 為什麼這份檔案存在
    `tune.py` 決定 Fig 2 上**每一條線的形狀**。它算錯的話，三組 λ 的
    對照圖依然畫得出來、依然好看、趨勢依然可能是對的 ——
    只是那些數字不再是「從我量到的 K/τ/θ 推出來的」。

    而 Fig 2 的整個賣點就是那句「不是試出來的」。
    **賣點在哪裡，測試就要在哪裡。**

★ 每一條測試都說得出「它防的是哪一種寫錯」，見各自的 docstring。
"""

import math
import pathlib

import pytest

import tune

# ═══════════════════════════════════════════════════════════════════════
#  IMC-PI 公式本身
# ═══════════════════════════════════════════════════════════════════════


def test_imc_pi_matches_the_closed_form_when_there_is_no_dead_time():
    """θ = 0 時公式退化成 `Kc = τ / (|K|·λ)` —— 可以手算的解析解。

    刻意挑出來的數字讓答案是整數：τ=20, K=−0.5, λ=10
    → Kc = 20 / (0.5 × 10) = 4.0
    """
    g = tune.imc_pi(k=-0.5, tau=20.0, theta=0.0, lam=10.0)
    assert g["Kc"] == pytest.approx(4.0)
    assert g["Ti"] == pytest.approx(20.0)
    assert g["Ki"] == pytest.approx(0.2)


def test_dead_time_goes_in_the_denominator_added_to_lambda():
    """★★ 防：`λ + θ` 被寫成 `λ − θ`（或 `λ · θ`）。

    τ=20, K=−0.5, λ=10, θ=5：
      · **`λ + θ`（正確）** → 20 / (0.5 × 15) = **2.6667**
      · `λ − θ`            → 20 / (0.5 ×  5) = **8.0**
      · `λ · θ`            → 20 / (0.5 × 50) = **0.8**

    三個都是「合理」的數字，圖上都畫得出來。
    ⚠️ 而且 θ = 0 的測試**分不出這三種**——所以那一條不能單獨存在。
    """
    g = tune.imc_pi(k=-0.5, tau=20.0, theta=5.0, lam=10.0)
    assert g["Kc"] == pytest.approx(20.0 / (0.5 * 15.0))


def test_ki_is_kc_divided_by_ti_not_multiplied():
    """防：`Ki = Kc / Ti` 寫成 `Kc * Ti`。

    τ = Ti = 20 時兩者差 400 倍。但輸出還是會被 outLim 箝住，
    所以圖上看起來只是「這組比較兇」，不像一個 bug。
    """
    g = tune.imc_pi(k=-0.5, tau=20.0, theta=0.0, lam=10.0)
    assert g["Ki"] == pytest.approx(g["Kc"] / g["Ti"])
    assert g["Ki"] != pytest.approx(g["Kc"] * g["Ti"])


def test_kc_is_positive_even_though_the_process_gain_is_negative():
    """★★ 防：忘了 `abs(k)`。

    風扇迴路的 K 必為負（轉越快溫度越低）。忘了取絕對值的話 Kc 變負，
    而呼叫端**還會再取一次負號**（temp 型別的符號慣例）——
    **負負得正，係數變成對的**，一路到圖上都正常。

    這種「錯兩次剛好對」是最難發現的一類：它沒有症狀。
    真正會咬人的是哪天有人改用 `convertTempToMargin`（誤差方向自然為正、
    不需要外面那個負號），這時第一個錯就會單獨現形。
    """
    negative = tune.imc_pi(k=-0.314708, tau=43.972, theta=7.2013, lam=87.944)
    positive = tune.imc_pi(k=+0.314708, tau=43.972, theta=7.2013, lam=87.944)
    assert negative["Kc"] > 0.0
    assert negative["Kc"] == pytest.approx(positive["Kc"])


def test_larger_lambda_gives_smaller_gain():
    """單調性：λ 是「期望的閉環時間常數」，要慢就得降增益。

    這一條防的是公式整個上下顛倒（`(λ+θ)/τ` 之類）。
    ★ 它也是 Fig 2 三組線能互相解釋的前提 —— 趨勢反了的話，
      圖上的結論會是「λ 越大越震盪」，而那與 λ 的定義矛盾。
    """
    gains = [tune.imc_pi(k=-0.3, tau=40.0, theta=7.0, lam=m * 40.0)["Kc"]
             for m in (0.5, 1.0, 2.0)]
    assert gains[0] > gains[1] > gains[2]


def test_larger_dead_time_forces_a_more_conservative_gain():
    """死區越大，增益越保守 —— 這是公式**自己**說的，不是調出來的。

    面試會問「你怎麼知道要多保守」：答案是 θ 在分母裡，
    而 θ 是我量到的（Fig 1），不是我選的。
    """
    small = tune.imc_pi(k=-0.3, tau=40.0, theta=1.0, lam=80.0)["Kc"]
    large = tune.imc_pi(k=-0.3, tau=40.0, theta=20.0, lam=80.0)["Kc"]
    assert small > large


def test_ti_equals_tau_and_does_not_depend_on_lambda():
    """IMC-PI 的 Ti 只由 τ 決定，λ 只動 Kc。

    防的是「把 λ 摻進 Ti」——那會讓「λ 是唯一旋鈕」這句話變成假的，
    而那句話是 §13 Q4 的答案主幹。
    """
    for m in (0.25, 1.0, 4.0):
        g = tune.imc_pi(k=-0.3, tau=40.0, theta=7.0, lam=m * 40.0)
        assert g["Ti"] == pytest.approx(40.0)


# ═══════════════════════════════════════════════════════════════════════
#  L1（%PWM）→ L2（RPM）的量綱換算
# ═══════════════════════════════════════════════════════════════════════


def test_swampd_conversion_multiplies_by_the_rpm_per_percent_slope():
    """★★ 防：換算寫成除法，或斜率取倒數。

    plant/thermal_plant.cpp 的映射是 `rpm = rpmMax × pwm/100`，
    rpmMax = 15000 → 斜率 **150 RPM/%PWM**。

    · **乘 150（正確）** → 1.4685 %PWM/°C 變成 220.3 RPM/°C
    · 除 150           → 0.0098 RPM/°C —— 外圈輸出永遠低於
      `outLim_min = 3000`，**看起來像「PID 沒作用」**
    · 忘了換算          → 1.47 RPM/°C，症狀一模一樣

    這兩種錯的症狀相同，而且都不像量綱問題 ——
    這正是 D6 疊圖最容易掉進去的坑。
    """
    g = tune.imc_pi(k=-0.314708, tau=43.972, theta=7.2013, lam=87.944)
    s = tune.to_swampd_rpm(g)
    assert s["Kc_rpm_per_c"] == pytest.approx(g["Kc"] * 150.0)
    assert s["Ki_rpm_per_c_s"] == pytest.approx(g["Ki"] * 150.0)
    assert s["Kc_rpm_per_c"] != pytest.approx(g["Kc"] / 150.0)


def test_swampd_conversion_records_the_slope_it_used():
    """換算結果要帶著它用的斜率一起走。

    ⚠️ 斜率是**模型參數**（rpmMax = 15000）。哪天 plant 改了 rpmMax
       而這裡沒跟上，輸出裡的 `rpm_per_pct` 是唯一看得出來的地方。
       不記的話，那組係數就變成「來歷不明的數字」。
    """
    g = tune.imc_pi(k=-0.3, tau=40.0, theta=7.0, lam=80.0)
    assert tune.to_swampd_rpm(g)["rpm_per_pct"] == pytest.approx(150.0)
    assert tune.to_swampd_rpm(g, rpm_per_pct=200.0)["rpm_per_pct"] == 200.0


def test_swampd_conversion_keeps_ti_unchanged():
    """★ Ti 是**時間**，不參與量綱換算。

    防的是「整個 dict 乘一遍」這種偷懶寫法 —— 那會讓 Ti 變成 6595 秒，
    積分幾乎不作用，而圖上只會看到「這組怎麼有穩態誤差」。
    """
    g = tune.imc_pi(k=-0.3, tau=40.0, theta=7.0, lam=80.0)
    assert tune.to_swampd_rpm(g)["Ti"] == pytest.approx(g["Ti"])


# ═══════════════════════════════════════════════════════════════════════
#  輸入驗證與來源
# ═══════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("bad", [
    {"k": -0.3, "tau": 0.0, "theta": 7.0, "lam": 80.0},
    {"k": -0.3, "tau": -40.0, "theta": 7.0, "lam": 80.0},
    {"k": -0.3, "tau": 40.0, "theta": -1.0, "lam": 80.0},
    {"k": -0.3, "tau": 40.0, "theta": 7.0, "lam": 0.0},
    {"k": 0.0, "tau": 40.0, "theta": 7.0, "lam": 80.0},
])
def test_impossible_inputs_raise_instead_of_returning_inf(bad):
    """壞輸入要當場報錯，不要回 inf / nan。

    τ=0 或 λ=0 會讓公式除以零。Python 的 float 除零會丟例外，
    但 `k=0` 不會 —— 它會回 `inf`，而 `inf` 一路傳進 CSV、
    再被 pandas 讀回來變成一條**畫不出來但也不報錯**的線。
    """
    with pytest.raises(ValueError):
        tune.imc_pi(**bad)


def test_the_real_fit_file_is_readable_and_gives_the_documented_gains():
    """★ 端到端：repo 裡那份真的 exp01_fit.txt 要算得出東西。

    這一條**不寫死係數的值**（那會變成「把答案抄兩遍」），
    只驗三件事：檔案讀得到、三組 Kc 單調遞減、而且都是正的。
    真正的數字由 exp05 的 meta 記錄，來源是這支程式跑出來的。
    """
    fit = pathlib.Path("bench/data/exp01_fit.txt")
    if not fit.exists():                       # 從別的工作目錄跑 pytest 時
        fit = pathlib.Path(__file__).resolve().parents[2] / fit
    k, tau, theta = tune.load_fit(fit)

    assert k < 0.0, "風扇迴路的製程增益必為負 —— 正的代表資料或擬合有問題"
    assert tau > 0.0 and theta > 0.0
    assert not math.isnan(k)

    kcs = [tune.imc_pi(k, tau, theta, m * tau)["Kc"] for m in (0.5, 1.0, 2.0)]
    assert kcs[0] > kcs[1] > kcs[2] > 0.0


def test_missing_fit_file_says_where_it_comes_from():
    """找不到擬合檔時，錯誤訊息要說它**是誰產生的**。

    防的不是算錯，是除錯時間：新 clone 的人跑 exp05 會先撞到這個，
    訊息裡有「bench/exp01_sysid.py」他就知道下一步做什麼。
    """
    with pytest.raises(SystemExit, match="exp01_sysid"):
        tune.load_fit(pathlib.Path("bench/data/does-not-exist.txt"))
