"""全專案共用的指標定義。

規則：**一個指標只在這裡定義一次。**
README、履歷、圖的標註、CI 斷言全部引用同一個來源，才不會出現
「README 說降了 40%、圖上看起來是 30%」這種對不起來的情況。

指標總表（打勾的是已實作）
--------------------------
| 指標 | 定義 | 為什麼要它 | 何時 |
|---|---|---|---|
| `t_peak_c`          | 全程最高感測溫度 | 安全裕度 | ✅ W4 |
| `fan_power_rel`     | 穩態 (rpm/rpm_max)³ 的時間平均 | 功耗／TCO 代理 | ✅ W4 |
| `overshoot_c`       | 溫度超過 setpoint 的最大值 − setpoint | 熱裕度 | W6 |
| `settle_s`          | 進入 setpoint ±1 °C 並維持 60 s 的起點 | 收斂速度 | W6 |
| `pwm_pp`            | 穩態最後 120 s 內 PWM 峰對峰值 | 震盪幅度 | W6 |
| `reversals_per_min` | PWM 一階差分的符號改變次數／分鐘 | ★ 聲學代理 | W6 |
| `recover_s`         | 溫度回落到 setpoint 以下 → PWM 首次 < 90% | ★ anti-windup 主指標 | W7 |
| `integral_max`      | 積分項最大絕對值 | 直接顯示 windup 有沒有發生 | W7 |
| `e2e_latency_ms`    | 溫度寫入 D-Bus → Redfish 讀到新值 | 系統量測 | W9 |

用法
----
    python bench/metrics.py bench/data/exp01_sysid_seed0.csv
"""

import argparse
import pathlib
import sys

import pandas as pd


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
    if "t_s" not in df.columns:
        raise KeyError("軌跡缺少 t_s 欄 —— 指標全部以時間定義，沒有它算不了")
    if len(df) == 0:
        raise ValueError("空的軌跡：沒有資料可以算指標")
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


def overshoot_c(df: pd.DataFrame, setpoint: float) -> float:  # W6 實作
    raise NotImplementedError("W6")


def settle_s(df: pd.DataFrame, setpoint: float) -> float:  # W6 實作
    raise NotImplementedError("W6")


def pwm_pp(df: pd.DataFrame, tail_s: float = 120.0) -> float:  # W6 實作
    raise NotImplementedError("W6")


def reversals_per_min(df: pd.DataFrame) -> float:  # W6 實作
    raise NotImplementedError("W6")


def recover_s(df: pd.DataFrame, setpoint: float) -> float:  # W7 實作
    raise NotImplementedError("W7")


IMPLEMENTED = {
    "t_peak_c": t_peak_c,
    "fan_power_rel": fan_power_rel,
}


def main() -> int:
    ap = argparse.ArgumentParser(description="印出一份 CSV 的所有已實作指標")
    ap.add_argument("csv", type=pathlib.Path)
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    for name, fn in IMPLEMENTED.items():
        print(f"{name}={fn(df):.6f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
