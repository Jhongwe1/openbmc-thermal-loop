"""統一產圖。**實驗腳本不畫圖，這裡不跑實驗。**

分離的理由：改樣式不用重跑實驗，重跑實驗不動樣式。
這裡讀的全部是 bench/data/ 底下**已經進 git 的**檔案 ——
所以任何人 clone 下來執行同一行指令，得到的是同一張圖。

    python bench/plot.py --fig 1
    python bench/plot.py --all

★ 圖上的文字一律英文。
  不是崇洋：這台機器沒有 CJK 字型，而就算裝了，
  「別人 clone 下來跑一次得到同一張圖」就會依賴他們的字型設定。
  圖是交付物，交付物不能依賴我本機的環境。中文留在 docs/ 與 LOG.md。
"""

import argparse
import pathlib
import subprocess
import sys

import matplotlib

matplotlib.use("Agg")  # noqa: E402  必須在 import pyplot 之前

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

DATA = pathlib.Path("bench/data")
FIGS = pathlib.Path("figures")
ENV = pathlib.Path("docs/env-baseline.md")

# ── 顏色（見 dataviz 的色彩規則，已跑過驗證器）─────────────────────────
#   量到的東西 -> 系列色；我下的命令與模型 -> ink；註解區塊 -> 淡底色。
#   五個 seed 是**同一個實體的重複**，所以是一個顏色不是五個。
C_MEASURED = "#2a78d6"  # 系列 1 藍：感測溫度（量測值）
C_COMMANDED = "#52514e"  # 次要 ink：PWM（我下的命令，不是量測值）
C_MODEL = "#0b0b0b"      # 主要 ink：FOPDT 擬合（模型參考線，不是第三筆資料）
C_ANNOTATE = "#eb6834"   # 註解用橘（只用在很淡的底色與輔助線）
C_GRID = "#e1e0d9"
C_AXIS = "#c3c2b7"
C_MUTED = "#898781"
C_SURFACE = "#fcfcfb"


def _read_kv(path: pathlib.Path) -> dict[str, str]:
    """讀 key=value 檔（略過 # 開頭的註解行）。"""
    out = {}
    for line in path.read_text().splitlines():
        if line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k] = v
    return out


def _image_name() -> str:
    """從 docs/env-baseline.md 撈釘選的映像檔名。

    ⚠️ 計畫範本是「讀第 4 行」——那一行其實是產生日期，不是映像名。
       改成找「主線映像」那一行，文件多加一段也不會壞掉。
    """
    if not ENV.exists():
        return "image: n/a"
    for line in ENV.read_text().splitlines():
        if "主線映像" in line and "`" in line:
            return "image: " + line.split("`")[1]
    return "image: n/a"


def _caption(what: str) -> str:
    """每張圖的 caption 必須有三樣東西。

    1. 實驗說明   —— 圖要能單獨看懂，不用回去翻 README
    2. 模擬聲明   —— 誠實準則第 5 條：限制寫在圖旁邊，不是只寫在 README 最後
    3. 版本       —— 誠實準則第 6 條：映像檔名 + repo commit
    """
    commit = subprocess.getoutput("git rev-parse --short HEAD")
    return (
        f"{what}\n"
        f"[Simulation on my own thermal plant - see docs/plant-model.md. "
        f"Not measured on server hardware.]\n"
        f"{_image_name()}  |  repo commit: {commit}"
    )


def _style(ax) -> None:
    """統一的座標軸外觀：格線與軸線都要退到背景去。"""
    ax.set_facecolor(C_SURFACE)
    ax.grid(True, color=C_GRID, lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(C_AXIS)
    ax.tick_params(colors=C_MUTED, labelsize=9)


def _baseline_mean(df: pd.DataFrame, step_at: float, window_s: float = 10.0) -> float:
    """階躍前 window_s 秒的平均感測溫度。

    ★ 必須與 plant/identify.cpp 的 baselineMean() 用同一個定義，
      否則畫在圖上的擬合曲線起點會跟報出來的 K 對不起來。
    """
    pre = df[(df["t_s"] >= step_at - window_s) & (df["t_s"] < step_at)]
    return float(pre["t_sense_c"].mean())


def fig1() -> None:
    """Fig 1 — 開環系統識別：階躍 + 5 個 seed 的原始響應 + FOPDT 擬合。"""
    meta = _read_kv(DATA / "exp01_sysid_meta.txt")
    fit = _read_kv(DATA / "exp01_fit.txt")

    step_at = float(meta["step_at_s"])
    du = float(meta["du"])
    k, tau, theta = float(fit["k"]), float(fit["tau"]), float(fit["theta"])
    rms = float(fit["residual_rms"])

    frames = [pd.read_csv(p) for p in sorted(DATA.glob("exp01_sysid_seed*.csv"))]
    if not frames:
        raise SystemExit("bench/data/ 裡沒有 exp01 的 CSV，先跑 bench/exp01_sysid.py")

    fig, (ax_u, ax_y) = plt.subplots(
        2, 1, sharex=True, figsize=(10, 7.5),
        gridspec_kw={"height_ratios": [1, 3], "hspace": 0.12},
    )
    fig.patch.set_facecolor(C_SURFACE)

    # ── 上：輸入（我下的命令）────────────────────────────────────────
    ax_u.plot(frames[0]["t_s"], frames[0]["pwm"], lw=2.0, color=C_COMMANDED,
              solid_joinstyle="round")
    ax_u.axvline(step_at, ls="--", lw=1.0, color=C_MUTED)
    ax_u.set_ylabel("PWM command (%)", fontsize=10, color=C_MUTED)
    ax_u.set_ylim(0, 100)
    ax_u.set_title("Fig 1 - Open-loop system identification (FOPDT)",
                   fontsize=13, color="#0b0b0b", loc="left", pad=10)
    _style(ax_u)
    ax_u.annotate(
        f"step at t = {step_at:g} s\n{meta['pwm_base']}% -> {meta['pwm_step']}%",
        xy=(step_at, float(meta["pwm_step"])), xytext=(step_at + 25, 82),
        fontsize=9, color=C_MUTED,
        arrowprops=dict(arrowstyle="->", color=C_MUTED, lw=0.8),
    )

    # ── 下：響應（量到的東西）──────────────────────────────────────
    # ★ 五條原始曲線全畫、不平滑 —— 反造假設計。
    #   平滑過的曲線看不出是不是編的；看得到雜訊才知道那是量出來的。
    for i, df in enumerate(frames):
        ax_y.plot(df["t_s"], df["t_sense_c"], lw=0.7, alpha=0.75,
                  color=C_MEASURED,
                  label=f"sensed temperature, raw ({len(frames)} seeds)" if i == 0 else None,
                  zorder=2)

    # 死區區間：讓 theta 從一個數字變成一段看得見的區域
    ax_y.axvspan(step_at, step_at + theta, color=C_ANNOTATE, alpha=0.10, zorder=1,
                 label=r"dead time $\theta$")
    ax_y.axvline(step_at, ls="--", lw=1.0, color=C_MUTED, zorder=3)

    # FOPDT 擬合（用五個 seed 的中位數參數）
    t = frames[0]["t_s"].to_numpy()
    y0 = float(np.mean([_baseline_mean(df, step_at) for df in frames]))
    dtau = np.maximum(t - step_at - theta, 0.0)
    model = np.where(t < step_at + theta, y0,
                     y0 + k * du * (1.0 - np.exp(-dtau / tau)))
    ax_y.plot(t, model, lw=2.0, color=C_MODEL, ls="--", zorder=4,
              label="FOPDT fit (median of 5 seeds)")

    ax_y.set_xlabel("time (s)", fontsize=10, color=C_MUTED)
    ax_y.set_ylabel("sensed temperature (°C)", fontsize=10, color=C_MUTED)
    _style(ax_y)

    leg = ax_y.legend(loc="upper right", fontsize=9, framealpha=0.92,
                      facecolor=C_SURFACE, edgecolor=C_GRID)
    for text in leg.get_texts():
        text.set_color("#52514e")

    # 參數標註：中位數 + 範圍。**不報最好看的那一次。**
    ax_y.text(
        0.015, 0.05,
        f"K = {k:.4f} °C/%PWM   [{float(fit['k_min']):.4f}, {float(fit['k_max']):.4f}]\n"
        f"$\\tau$ = {tau:.2f} s   [{float(fit['tau_min']):.2f}, {float(fit['tau_max']):.2f}]\n"
        f"$\\theta$ = {theta:.2f} s   [{float(fit['theta_min']):.2f}, "
        f"{float(fit['theta_max']):.2f}]\n"
        f"fit residual RMS = {rms:.3f} °C\n"
        f"$\\tau+\\theta$ = {float(fit['tau_plus_theta']):.2f} s   "
        f"(model: $\\tau_{{die}}+\\tau_{{sense}}+\\theta$ = "
        f"{float(meta['tau_die']) + float(meta['tau_sense']) + float(meta['dead_time']):.1f} s)\n"
        f"median of 5 seeds, [min, max] in brackets",
        transform=ax_y.transAxes, va="bottom", fontsize=9, color="#0b0b0b",
        family="monospace",
        bbox=dict(boxstyle="round,pad=0.5", fc=C_SURFACE, ec=C_GRID, alpha=0.95),
    )

    what = (
        f"Fig 1 - Open-loop PWM step {meta['pwm_base']}% -> {meta['pwm_step']}% at "
        f"t = {step_at:g} s, power held at {meta['power_w']} W, dt = {meta['dt']} s, "
        f"5 seeds. K/tau/theta by the two-point method (plant/identify.cpp)."
    )
    fig.text(0.01, 0.005, _caption(what), fontsize=7, va="bottom", color=C_MUTED)

    FIGS.mkdir(exist_ok=True)
    out = FIGS / "fig1_sysid.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=C_SURFACE)
    plt.close(fig)
    print(f"wrote {out}")


FIGURES = {1: fig1}


def main() -> int:
    ap = argparse.ArgumentParser(description="產生 figures/ 底下的圖")
    ap.add_argument("--fig", type=int, help="只產生某一張")
    ap.add_argument("--all", action="store_true", help="全部產生")
    a = ap.parse_args()

    if not a.all and a.fig is None:
        ap.error("要給 --fig N 或 --all")

    wanted = sorted(FIGURES) if a.all else [a.fig]
    for n in wanted:
        if n not in FIGURES:
            raise SystemExit(f"Fig {n} 還沒實作")
        FIGURES[n]()
    return 0


if __name__ == "__main__":
    sys.exit(main())
