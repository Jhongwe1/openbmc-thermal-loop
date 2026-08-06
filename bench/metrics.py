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


def t_peak_c(df: pd.DataFrame) -> float:
    """全程最高感測溫度 (°C)。"""
    return float(df["t_sense_c"].max())


def fan_power_rel(df: pd.DataFrame, tail_s: float = 120.0) -> float:
    """穩態相對風扇功耗：(rpm/rpm_max)³ 的時間平均，滿速為 1.0。

    ★ 為什麼是三次方 —— 風扇親和定律（fan affinity laws）：
      系統阻抗不變時，風量 ∝ 轉速 N、靜壓 ∝ N²、**功率 ∝ N³**。
      所以**轉速降 10%，功耗降約 27%**（1 − 0.9³ = 0.271）。
      這是資料中心風扇控制的全部經濟動機，也是 W6/W8 講「λ 放大的代價」
      時要換算成錢的那個係數。

    ⚠️【判】這是**模型算出來的相對值，不是量到的瓦數**。
       講的時候要說「相對風扇功耗」，不要說「省了多少瓦」。
    """
    dt = float(df["t_s"].iloc[1] - df["t_s"].iloc[0])
    n = max(1, int(tail_s / dt))
    return float(df["fan_power_rel"].tail(n).mean())


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
