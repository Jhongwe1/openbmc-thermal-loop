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


def _fopdt(t: np.ndarray, y0: float, k: float, du: float, tau: float,
           theta: float, step_at: float) -> np.ndarray:
    """FOPDT 階躍響應。**只在 t >= step_at 有定義。**"""
    dtau = np.maximum(t - step_at - theta, 0.0)
    return np.where(t < step_at + theta, y0,
                    y0 + k * du * (1.0 - np.exp(-dtau / tau)))


def fig1() -> None:
    """Fig 1 — 開環系統識別：階躍 + 5 個 seed 的原始響應 + FOPDT 擬合 + 殘差。

    ★ 版面上的四個決定，每一個都有理由（見 LOG.md 2026-08-07）：

    1. **x 軸從階躍前 60 s 開始**，不畫 0~240 s 的冷機暖機段。
       那段是「把系統帶到工作點」，不是實驗的一部分，卻會把 y 軸拉大五倍，
       結果就是**雜訊與量化階梯完全看不見** —— 而「看得到雜訊」正是
       這張圖的反造假要求。原始 CSV 仍然是完整的 0~900 s。
    2. **多一個殘差面板。** 殘差 RMS 是一個數字，數字看不出「有沒有系統性偏差」。
       畫出來才看得到它是不是圍著 0 隨機分布。
    3. **多一個死區放大鏡。** theta 只有 7 s，在 660 s 寬的圖上是一條線。
       放大之後，死區變成一段看得見的平台，量化階梯也看得見。
    4. **擬合曲線只畫階躍之後。** 畫過整段會暗示這個模型也預測了暖機過程 ——
       它沒有，它只描述階躍響應。
    """
    meta = _read_kv(DATA / "exp01_sysid_meta.txt")
    fit = _read_kv(DATA / "exp01_fit.txt")

    step_at = float(meta["step_at_s"])
    du = float(meta["du"])
    k, tau, theta = float(fit["k"]), float(fit["tau"]), float(fit["theta"])
    rms = float(fit["residual_rms"])

    frames = [pd.read_csv(p) for p in sorted(DATA.glob("exp01_sysid_seed*.csv"))]
    if not frames:
        raise SystemExit("bench/data/ 裡沒有 exp01 的 CSV，先跑 bench/exp01_sysid.py")

    t = frames[0]["t_s"].to_numpy()
    y0 = float(np.mean([_baseline_mean(df, step_at) for df in frames]))
    model = _fopdt(t, y0, k, du, tau, theta, step_at)

    view_lo, view_hi = step_at - 60.0, float(t[-1])
    inset_lo, inset_hi = step_at - 5.0, step_at + 45.0

    fig, (ax_u, ax_y, ax_r) = plt.subplots(
        3, 1, sharex=True, figsize=(11, 9.5),
        gridspec_kw={"height_ratios": [1, 3.4, 1.1], "hspace": 0.10},
    )
    fig.patch.set_facecolor(C_SURFACE)

    # ── 上：輸入（我下的命令）────────────────────────────────────────
    ax_u.plot(t, frames[0]["pwm"], lw=2.0, color=C_COMMANDED, solid_joinstyle="round")
    ax_u.axvline(step_at, ls="--", lw=1.0, color=C_MUTED)
    ax_u.set_ylabel("PWM command\n(%)", fontsize=10, color=C_MUTED)
    ax_u.set_ylim(0, 100)
    ax_u.set_title("Fig 1 - Open-loop system identification (FOPDT)",
                   fontsize=14, color="#0b0b0b", loc="left", pad=10)
    _style(ax_u)
    ax_u.annotate(
        f"step at t = {step_at:g} s:  {meta['pwm_base']}% -> {meta['pwm_step']}%",
        xy=(step_at, float(meta["pwm_step"])), xytext=(step_at + 45, 22),
        fontsize=9, color=C_MUTED,
        arrowprops=dict(arrowstyle="->", color=C_MUTED, lw=0.8),
    )

    # ── 中：響應（量到的東西）──────────────────────────────────────
    # ★ 五條原始曲線全畫、不平滑、不取平均 —— 反造假設計。
    #   平滑過的曲線看不出是不是編的；看得到雜訊才知道那是量出來的。
    for i, df in enumerate(frames):
        ax_y.plot(t, df["t_sense_c"], lw=0.7, alpha=0.8, color=C_MEASURED, zorder=2,
                  label=f"sensed temperature, raw ({len(frames)} seeds)" if i == 0 else None)

    ax_y.axvspan(step_at, step_at + theta, color=C_ANNOTATE, alpha=0.13, zorder=1,
                 label=r"dead time $\theta$")
    ax_y.axvline(step_at, ls="--", lw=1.0, color=C_MUTED, zorder=3)

    post = t >= step_at
    ax_y.plot(t[post], model[post], lw=2.2, color=C_MODEL, ls="--", zorder=4,
              label="FOPDT fit (median of 5 seeds)")
    # 基準值 y0 是怎麼來的：階躍前 10 s 的平均
    ax_y.plot([step_at - 10, step_at], [y0, y0], lw=1.8, color=C_MODEL, ls=":",
              zorder=4, label="baseline $y_0$ (mean of 10 s before step)")

    ax_y.set_ylabel("sensed temperature (°C)", fontsize=10, color=C_MUTED)
    _style(ax_y)
    ax_y.set_xlim(view_lo, view_hi)
    win = (t >= view_lo)
    lo = min(float(df["t_sense_c"][win].min()) for df in frames)
    hi = max(float(df["t_sense_c"][win].max()) for df in frames)
    pad = 0.12 * (hi - lo)
    ax_y.set_ylim(lo - pad, hi + pad)

    # 圖例放到面板外面：面板裡沒有一塊夠大的空白不會壓到資料，
    # 而「為了塞圖例而把資料遮掉一角」是最沒必要的一種資訊損失。
    handles, labels = ax_y.get_legend_handles_labels()

    # ── 死區放大鏡 ──────────────────────────────────────────────────
    axin = ax_y.inset_axes([0.47, 0.45, 0.50, 0.52])
    for df in frames:
        axin.plot(t, df["t_sense_c"], lw=0.9, alpha=0.85, color=C_MEASURED, zorder=2)
    axin.axvspan(step_at, step_at + theta, color=C_ANNOTATE, alpha=0.13, zorder=1)
    axin.axvline(step_at, ls="--", lw=1.0, color=C_MUTED, zorder=3)
    axin.plot(t[post], model[post], lw=1.6, color=C_MODEL, ls="--", zorder=4)
    axin.set_xlim(inset_lo, inset_hi)
    zoom = (t >= inset_lo) & (t <= inset_hi)
    zlo = min(float(df["t_sense_c"][zoom].min()) for df in frames)
    zhi = max(float(df["t_sense_c"][zoom].max()) for df in frames)
    zpad = 0.15 * (zhi - zlo)
    axin.set_ylim(zlo - zpad, zhi + zpad)
    _style(axin)
    axin.tick_params(labelsize=8)
    axin.set_title(
        f"zoom on the step: dead time, noise and quantisation "
        f"(LSB = {float(meta['lsb']):g} °C)",
        fontsize=8.5, color=C_MUTED, loc="left", pad=4)
    ax_y.indicate_inset_zoom(axin, edgecolor=C_MUTED, alpha=0.6, lw=0.8)

    # ── 下：殘差（資料 − 模型）──────────────────────────────────────
    # 殘差 RMS 是一個數字，看不出「有沒有系統性偏差」。畫出來才看得到。
    for df in frames:
        resid = df["t_sense_c"].to_numpy() - model
        ax_r.plot(t[post], resid[post], lw=0.7, alpha=0.8, color=C_MEASURED, zorder=2)
    ax_r.axhline(0.0, lw=1.0, color=C_MODEL, zorder=3)
    ax_r.axhspan(-rms, rms, color=C_ANNOTATE, alpha=0.13, zorder=1)
    ax_r.axvline(step_at, ls="--", lw=1.0, color=C_MUTED, zorder=3)
    ax_r.set_ylabel("residual\n(°C)", fontsize=10, color=C_MUTED)
    ax_r.set_xlabel("time (s)", fontsize=10, color=C_MUTED)
    _style(ax_r)

    # ── 參數區塊：放在面板外面，避免壓到資料 ────────────────────────
    tau_plus = float(fit["tau_plus_theta"])
    # 雜訊底：量測雜訊與量化誤差是獨立的，所以平方相加開根號。
    # 量化的 RMS 是 LSB/sqrt(12)（均勻分布在正負半個 LSB 之間的標準差）。
    noise_floor = float(np.hypot(float(meta["noise_sigma"]),
                                 float(meta["lsb"]) / np.sqrt(12)))
    model_sum = (float(meta["tau_die"]) + float(meta["tau_sense"])
                 + float(meta["dead_time"]))
    params = (
        f"K = {k:+.4f} °C/%PWM      [{float(fit['k_min']):+.4f}, {float(fit['k_max']):+.4f}]\n"
        f"tau = {tau:6.2f} s            [{float(fit['tau_min']):.2f}, "
        f"{float(fit['tau_max']):.2f}]\n"
        f"theta = {theta:6.2f} s          [{float(fit['theta_min']):.2f}, "
        f"{float(fit['theta_max']):.2f}]\n"
        f"fit residual RMS = {rms:.3f} °C   [{float(fit['residual_rms_min']):.3f}, "
        f"{float(fit['residual_rms_max']):.3f}]\n"
        f"tau + theta = {tau_plus:.2f} s  vs  model tau_die + tau_sense + theta "
        f"= {model_sum:.1f} s\n"
        f"median of 5 seeds; [min, max] across seeds in brackets\n"
        f"residual band = +/-RMS;  noise floor from sigma and LSB/sqrt(12) "
        f"= {noise_floor:.3f} °C"
    )
    fig.text(0.012, 0.115, params, fontsize=9, va="bottom", color="#0b0b0b",
             family="monospace",
             bbox=dict(boxstyle="round,pad=0.55", fc=C_SURFACE, ec=C_GRID))

    leg = fig.legend(handles, labels, loc="lower right",
                     bbox_to_anchor=(0.99, 0.115), fontsize=9, ncol=1,
                     framealpha=1.0, facecolor=C_SURFACE, edgecolor=C_GRID)
    for text in leg.get_texts():
        text.set_color("#52514e")

    what = (
        f"Fig 1 - Open-loop PWM step {meta['pwm_base']}% -> {meta['pwm_step']}% at "
        f"t = {step_at:g} s, power held at {meta['power_w']} W, dt = {meta['dt']} s, "
        f"{len(frames)} seeds. K/tau/theta by the two-point method "
        f"(plant/identify.cpp, verified by test/test_identify.cpp).\n"
        f"View starts at t = {view_lo:g} s; the first {view_lo:g} s are the plant "
        f"settling to its operating point from cold and are not part of the "
        f"experiment. Full traces are in bench/data/exp01_sysid_seed*.csv."
    )
    fig.text(0.012, 0.005, _caption(what), fontsize=7.5, va="bottom", color=C_MUTED)

    fig.subplots_adjust(bottom=0.30)
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
