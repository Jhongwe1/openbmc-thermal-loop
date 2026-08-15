"""全專案共用的指標定義。

規則：**一個指標只在這裡定義一次。**
README、docs/、圖的標註、CI 斷言全部引用同一個來源，才不會出現
「README 說降了 40%、圖上看起來是 30%」這種對不起來的情況。

指標總表（打勾的是已實作）
--------------------------
| 指標 | 定義 | 為什麼要它 | 何時 |
|---|---|---|---|
| `t_peak_c`          | 全程最高感測溫度 | 安全裕度 | ✅ W4 |
| `fan_power_rel`     | 穩態 (rpm/rpm_max)³ 的時間平均 | 功耗／TCO 代理 | ✅ W4 |
| `overshoot_c`       | 溫度超過 setpoint 的最大值 − setpoint | 熱裕度 | ✅ W6 |
| `settle_s`          | 進入 setpoint ±1 °C 並維持 60 s 的起點 | 收斂速度 | ✅ W6 |
| `pwm_pp`            | 穩態最後 120 s 內 PWM 峰對峰值 | 震盪幅度 | ✅ W6 |
| `reversals_per_min` | PWM 一階差分的符號改變次數／分鐘 | ★ 聲學代理 | ✅ W6 |
| `recover_s`         | 溫度回落到 setpoint 以下 → PWM 首次 < 90% | ★ anti-windup 主指標 | ✅ W7 |
| `integral_max`      | 積分項最大絕對值 | 直接顯示 windup 有沒有發生 | ✅ W7 |
| `e2e_latency_ms`    | 溫度寫入 D-Bus → Redfish 讀到新值 | 系統量測 | W9 |

用法
----
    python bench/metrics.py bench/data/exp01_sysid_seed0.csv
"""

import argparse
import pathlib
import sys

import numpy as np
import pandas as pd


def _require_trace(df: pd.DataFrame) -> None:
    """所有指標的共同前提：有時間欄、而且不是空的。

    ⚠️ 抽成一個函式是因為 W6 之後有六個指標要做同一件檢查。
       複製六份的話，只要有一份忘了改，那個指標就會在空 CSV 上
       丟出一個看不懂的例外 —— 而實驗腳本半夜跑出空 CSV 是會發生的事。
    """
    if "t_s" not in df.columns:
        raise KeyError("軌跡缺少 t_s 欄 —— 指標全部以時間定義，沒有它算不了")
    if len(df) == 0:
        raise ValueError("空的軌跡：沒有資料可以算指標")


def _require_columns(df: pd.DataFrame, *names: str) -> None:
    """點名缺了哪一欄，不要讓 pandas 丟一個裸的 KeyError 讓人猜。"""
    missing = [n for n in names if n not in df.columns]
    if missing:
        raise KeyError(
            f"軌跡缺少欄位 {missing} —— 這個指標算不了。"
            "CSV 標頭的定義在 bench/sim.cpp"
        )


def tail_window(df: pd.DataFrame, tail_s: float) -> pd.DataFrame:
    """取這份軌跡**最後 tail_s 秒**的那一段。

    ★★ 為什麼用「時間」選，不是用「列數」選（2026-08-09 改）

    原本的寫法是::

        dt = float(df["t_s"].iloc[1] - df["t_s"].iloc[0])   # 從前兩列推取樣週期
        n = max(1, int(tail_s / dt))
        df["fan_power_rel"].tail(n)

    它有兩個問題，都是寫測試的時候才逼出來的：

    1. **取樣週期是從前兩列推出來的。** 只要軌跡不是等間隔取樣
       （例如 L2 從 BMC 收資料 —— 那一側的間隔本來就會抖），
       視窗長度就會算錯，而且**不會有任何錯誤訊息**：
       你會拿到一個看起來很正常、但涵蓋時間根本不是 120 秒的平均值。
    2. **只有一列的 DataFrame 會丟 `IndexError`**（`iloc[1]` 不存在），
       訊息是「index out of bounds」，看不出真正的原因是什麼。

    用時間篩選同時解掉這兩個 —— 而且**它才是這個指標的定義**：
    「最後 120 秒的平均」講的是時間，不是列數。

    ⚠️ 這一段之後 W6 的 `settle_s`、`pwm_pp` 與 W7 的 `recover_s` 都會用到。
       現在把陷阱留著，等於留給那三個指標。
    """
    _require_trace(df)
    if tail_s <= 0.0:
        raise ValueError(f"tail_s 必須為正，收到 {tail_s}")

    t_end = float(df["t_s"].iloc[-1])
    return df[df["t_s"] >= t_end - tail_s]


def t_peak_c(df: pd.DataFrame) -> float:
    """全程最高感測溫度 (°C)。

    ⚠️ 看的是 `t_sense_c`（**感測器讀到的**），不是 `t_die_c`（模型內部真值）。
       真實系統上量不到後者，用它會讓這個指標變成「模擬才算得出來的東西」。
    """
    return float(df["t_sense_c"].max())


def fan_power_rel(df: pd.DataFrame, tail_s: float = 120.0) -> float:
    """穩態相對風扇功耗：(rpm/rpm_max)³ 的時間平均，滿速為 1.0。

    ★ 為什麼是三次方 —— 風扇親和定律（fan affinity laws）：
      系統阻抗不變時，風量 ∝ 轉速 N、靜壓 ∝ N²、**功率 ∝ N³**。
      所以**轉速降 10%，功耗降約 27%**（1 − 0.9³ = 0.271）。
      這是資料中心風扇控制的全部經濟動機，也是 W6/W8 講「λ 放大的代價」
      時要換算成錢的那個係數。

    ⚠️ **這個函式沒有在算三次方。** 三次方是 `plant/thermal_plant.cpp` 的
       `fanPowerRel()` 做的，`bench/sim` 把它寫成 CSV 的一欄。
       這裡做的只是「取最後一段的平均」。搞混的話會寫出測三次方的測試，
       然後以為自己驗過了這個函式。

    ⚠️【判】這是**模型算出來的相對值，不是量到的瓦數**。
       講的時候要說「相對風扇功耗」，不要說「省了多少瓦」。
    """
    return float(tail_window(df, tail_s)["fan_power_rel"].mean())


def overshoot_c(df: pd.DataFrame, setpoint: float) -> float:
    """溫度超過 setpoint 的最大值 − setpoint。沒超過就是 0。

    ⚠️ 刻意複用 `t_peak_c()`，不自己再寫一次 `df["t_sense_c"].max()`。
       「峰值要看哪一欄」只能有一個地方決定 —— 寫第二次的那天，
       就有機會一個看 `t_sense_c`、一個看 `t_die_c`，
       而它們會同時出現在同一張圖的指標表上，兩個都長得很正常。

    ⚠️ 下限是 0：「超調 −3 °C」不叫超調，叫沒到。那件事由 settle_s 講。
    """
    return max(0.0, t_peak_c(df) - setpoint)


def settle_s(df: pd.DataFrame, setpoint: float,
             band: float = 1.0, hold_s: float = 60.0) -> float:
    """**進入** setpoint ±band、並從那一刻起連續維持 hold_s 秒的時刻 (s)。

    回傳的是「進入的時刻」，不是「滿足維持條件的時刻」——
    後者永遠比前者晚 hold_s 秒，兩者差一個常數，但意義不同：
    使用者關心的是溫度什麼時候到位，不是我什麼時候才敢確定它到位。

    ★ 為什麼要「維持」而不只是「進入」
      震盪的系統會反覆穿越那條帶。只要求瞬間進入的話，**震盪越厲害的
      系統反而拿到越漂亮的數字** —— 而那正是這個指標本來要抓的壞行為。

    ★ 為什麼用時間框而不是列數（與 tail_window 同一個理由，2026-08-11）
      計畫給的實作是 `n_hold = int(hold_s / dt)`，`dt` 從**前兩列**推。
      L2 那側（從 BMC 收資料）的取樣間隔本來就會抖，列數會算錯，
      而且不會有任何錯誤訊息。這個坑 2026-08-09 已經在 `tail_window`
      踩過一次 —— **同一個念頭寫出來的錯不會只有一處。**

    ⚠️ 限制：只看得到樣本點。取樣間隔遠大於震盪週期時，這個指標會
       漏掉震盪而回一個好看的數字。那是取樣定理，不是實作缺陷，
       但下結論之前要先確認自己的取樣速度（W5 的教訓）。

    ⚠️ 從未穩定時回 **NaN**，不回一個假數字。NaN 會一路傳到圖上與
       claims.json —— 那是刻意的：「沒穩定」這件事必須看得見。
    """
    _require_trace(df)
    _require_columns(df, "t_sense_c")
    if band <= 0.0:
        raise ValueError(f"band 必須為正，收到 {band}")
    if hold_s < 0.0:
        raise ValueError(f"hold_s 不可為負，收到 {hold_s}")

    t = df["t_s"].to_numpy(dtype=float)
    inside = np.abs(df["t_sense_c"].to_numpy(dtype=float) - setpoint) <= band

    entered = None
    for i in range(t.size):
        if not inside[i]:
            entered = None
            continue
        if entered is None:
            entered = t[i]
        if t[i] - entered >= hold_s:
            return float(entered)
    return float("nan")


def pwm_pp(df: pd.DataFrame, tail_s: float = 120.0) -> float:
    """穩態最後 tail_s 秒的 PWM 峰對峰值（max − min）。

    ⚠️ 它與 `reversals_per_min` 是一對，報告時要一起出現：
       **峰對峰講「抖多大」，反轉次數講「抖多快」。**
       一個緩慢的大漂移 pwm_pp 很大但 reversals 很小（聽不到）；
       一個高頻的小抖動剛好相反（聽得到）。只報其中一個會誤導。
    """
    _require_columns(df, "pwm")
    w = tail_window(df, tail_s)
    return float(w["pwm"].max() - w["pwm"].min())


def reversals_per_min(df: pd.DataFrame, tail_s: float = 120.0,
                      deadband: float = 0.05) -> float:
    """PWM 一階差分的符號改變次數 ÷ 分鐘 —— **聲學代理**。

    使用者聽到的是**變化**，不是絕對轉速。一顆穩定在 70% 的風扇不吵；
    一顆在 68~72% 之間每秒來回三次的風扇很吵。這個指標量的是後者。

    ★ deadband 在做什麼，以及它**不只**在濾雜訊
      只有 |Δpwm| > deadband 的那些步才算數。它擋掉兩種東西：
        ① CSV 的數值精度（sim 印 `%.4f`）造成的正負跳動 —— 純假象
        ② **真實但幅度很小的變化** —— 那不是假象，是刻意忽略
      ②
      的理由是「低於某個幅度使用者聽不到」，而那個門檻**我沒有量過**。

      ⚠️【判】用 PWM 方向反轉當聲學代理、以及 deadband = 0.05 這個值，
         都是我的工程判斷，**沒有做過聲壓量測驗證**（見 docs/limitations.md）。

      ⚠️★ 而且它與 Kp 有交互作用，比較三組 λ 時要記得：
         溫度量化階 LSB 經過 Kp 放大之後就是 PWM 的抖動幅度，
         **Kp 越大（λ 越小）抖動越大**。同一個 deadband 對三組不等價 ——
         高增益那組被濾掉的比例比較低。三組用**同一個 deadband** 是為了
         讓定義一致（不然數字不可比），代價寫在 docs/measurement.md exp05。

    ★ 分母用「實際視窗跨度」而不是 tail_s（偏離計畫）
      計畫寫 `sign_changes / (tail_s / 60.0)`。軌跡比 tail_s 短的時候
      那個分母是錯的 —— 它會**低估**反轉率，而且不會報錯。
      這與 `tail_window` 改用時間框是同一件事：**視窗的真實長度要問資料，
      不要問參數。**
    """
    _require_columns(df, "pwm")
    if deadband < 0.0:
        raise ValueError(f"deadband 不可為負，收到 {deadband}")

    w = tail_window(df, tail_s)
    t = w["t_s"].to_numpy(dtype=float)
    if t.size < 2:
        return 0.0

    span_s = float(t[-1] - t[0])
    if span_s <= 0.0:
        return 0.0

    d = np.diff(w["pwm"].to_numpy(dtype=float))
    d = d[np.abs(d) > deadband]
    if d.size < 2:
        return 0.0

    reversals = int(np.count_nonzero(np.diff(np.sign(d)) != 0))
    return reversals * 60.0 / span_s


def recover_s(df: pd.DataFrame, setpoint: float,
              pwm_threshold: float = 90.0) -> float:
    """飽和解除後的恢復時間 (s) —— anti-windup 的主指標（W7）。

    定義：從「溫度**首次**回落到 setpoint 以下」那一刻起，
          到「PWM **首次**低於 pwm_threshold」為止，經過幾秒。

    為什麼這樣定義：windup 的症狀是「溫度已經降下來了，風扇卻還在全速」。
    前者是條件、後者是後果，兩者的時間差就是 windup 的代價 ——
    也是 Fig 3 的 A/B 兩組唯一該分開的數字。

    ⚠️ 呼叫者要傳「飽和解除之後」的視窗（exp07 從 power_down_at 起裁）。
       軌跡從冷機（25 °C）開始，整段傳進來的話「首次低於 setpoint」
       會命中 t=0 的暖機段 —— 量到的是開機行為，不是恢復。

    ⚠️ 兩個 NaN 出口都是刻意的（與 settle_s 同一條紀律）：
       · 溫度從未回落 → 飽和沒有解除，實驗設計錯了，回 NaN 不回 0
       · PWM 從未低於門檻 → 視窗太短或箝位形同虛設，同樣不能假裝量到了

    ★ 位置 vs 標籤（這裡是計畫給的實作寫錯的地方）：
      計畫的偽碼拿 `df.index[...]` 的**標籤**去餵 `iloc` 的**位置**。
      exp07 傳進來的一定是裁切過的 DataFrame，標籤不從 0 開始，
      兩者就對不上 —— 輕則 IndexError，重則默默回一個看起來合理的錯秒數。
      所以這裡全程用 numpy 位置索引；mutation P17 種的就是計畫那版。
    """
    _require_trace(df)
    _require_columns(df, "t_sense_c", "pwm")
    if pwm_threshold <= 0.0:
        raise ValueError(f"pwm_threshold 必須為正，收到 {pwm_threshold}")

    t = df["t_s"].to_numpy(dtype=float)
    sensed = df["t_sense_c"].to_numpy(dtype=float)
    pwm = df["pwm"].to_numpy(dtype=float)

    below = np.nonzero(sensed <= setpoint)[0]
    if below.size == 0:
        return float("nan")
    i0 = int(below[0])

    released = np.nonzero(pwm[i0:] < pwm_threshold)[0]
    if released.size == 0:
        return float("nan")
    return float(t[i0 + int(released[0])] - t[i0])


def integral_max(df: pd.DataFrame, col: str = "integral") -> float:
    """積分項的最大**絕對值** —— windup 有沒有發生的直接證據（W7）。

    ⚠️ 欄位不存在時回 NaN，不是 raise：開環軌跡（exp01）本來就沒有
       積分項，對它們這個指標是「無定義」，不是「算失敗」——
       模組 docstring 的用法範例就是拿 exp01 的 CSV 跑 CLI，它不該炸。
       NaN 的下游行為與 settle_s 相同：流進表裡看得見，不會變成假數字。

    ⚠️ 取的是 |·| 的最大：下界為負的箝位（或反向 windup）時積分是負的，
       忘了絕對值會回一個小的正數，把「反向 windup 很嚴重」讀成「沒事」。
    """
    _require_trace(df)
    if col not in df.columns:
        return float("nan")
    return float(df[col].abs().max())


def summarise(df: pd.DataFrame, setpoint: float) -> dict:
    """一次算完 Fig 2 / Fig 5 指標表要的那幾個。

    ⚠️ 這裡的順序就是圖上表格的欄位順序。改這裡等於改圖，
       而 `test/python/test_figures.py` 會逐 byte 比對重畫的結果 ——
       所以改了會變紅，那是刻意的。
    """
    return {
        "overshoot_c": overshoot_c(df, setpoint),
        "settle_s": settle_s(df, setpoint),
        "pwm_pp": pwm_pp(df),
        "reversals_per_min": reversals_per_min(df),
        "fan_power_rel": fan_power_rel(df),
        "t_peak_c": t_peak_c(df),
    }


#: 只吃 `df` 的指標。CLI 不給 --setpoint 時就只印這些。
IMPLEMENTED = {
    "t_peak_c": t_peak_c,
    "fan_power_rel": fan_power_rel,
    "pwm_pp": pwm_pp,
    "reversals_per_min": reversals_per_min,
    "integral_max": integral_max,
}

#: 需要 setpoint 才算得出來的指標。**setpoint 是實驗設定，不是資料的一部分** ——
#: 從 CSV 猜不出來，所以只能從外面傳進來。猜它（例如「取最後 60 秒平均」）
#: 會讓指標在系統根本沒收斂時給出一個看起來很成功的數字。
IMPLEMENTED_WITH_SETPOINT = {
    "overshoot_c": overshoot_c,
    "settle_s": settle_s,
    "recover_s": recover_s,
}


def main() -> int:
    ap = argparse.ArgumentParser(description="印出一份 CSV 的所有已實作指標")
    ap.add_argument("csv", type=pathlib.Path)
    ap.add_argument("--setpoint", type=float, default=None,
                    help="目標溫度 (°C)。不給的話跳過需要它的指標。")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    for name, fn in IMPLEMENTED.items():
        print(f"{name}={fn(df):.6f}")
    if args.setpoint is None:
        print("# 沒給 --setpoint，略過 overshoot_c / settle_s", file=sys.stderr)
        return 0
    for name, fn in IMPLEMENTED_WITH_SETPOINT.items():
        print(f"{name}={fn(df, args.setpoint):.6f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
