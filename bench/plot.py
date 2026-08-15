"""統一產圖。**實驗腳本不畫圖，這裡不跑實驗。**

分離的理由：改樣式不用重跑實驗，重跑實驗不動樣式。
這裡讀的全部是 bench/data/ 底下**已經進 git 的**檔案 ——
所以任何人 clone 下來執行同一行指令，得到的是**逐 byte 相同**的那一張圖。

★ 「逐 byte 相同」是認真的，不是形容詞：
  `test/python/test_figures.py` 會重畫一次並與 repo 裡那張比對。
  能這樣要求，是因為量過三件事：matplotlib 對同一份輸入是決定性的、
  PNG 裡沒有時間戳、而 caption 記的是**資料的 commit** 不是 HEAD
  （記 HEAD 的話每個 commit 都會讓圖變 —— 見 bench/provenance.py）。

    python bench/plot.py --fig 1
    python bench/plot.py --all

★ 圖上的文字一律英文。
  不是崇洋：這台機器沒有 CJK 字型，而就算裝了，
  「別人 clone 下來跑一次得到同一張圖」就會依賴他們的字型設定。
  圖是交付物，交付物不能依賴我本機的環境。中文留在 docs/ 與 LOG.md。
"""

import argparse
import json
import os
import pathlib
import sys

import matplotlib

matplotlib.use("Agg")  # noqa: E402  必須在 import pyplot 之前

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import parse_l2  # noqa: E402
import provenance  # noqa: E402

DATA = pathlib.Path("bench/data")
# 輸出目錄可以用環境變數覆寫 —— 給 test/python/test_figures.py 用：
# 那個測試要「重畫一次並與 repo 裡那張逐 byte 比對」，
# 不能為了測試就去覆蓋工作目錄裡的交付物（測試中途掛掉會留下爛攤子）。
FIGS = pathlib.Path(os.environ.get("FIGURES_DIR", "figures"))

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


def _caption(what: str, inputs: list[str]) -> str:
    """每張圖的 caption 必須有三樣東西。

    1. 實驗說明   —— 圖要能單獨看懂，不用回去翻 README
    2. 模擬聲明   —— 誠實準則第 5 條：限制寫在圖旁邊，不是只寫在 README 最後
    3. 版本       —— 誠實準則第 6 條：映像檔名 + 資料的 commit

    ⚠️ 第 3 行由 bench/provenance.py 產生，**每張圖共用同一份實作**。
       以前這裡與 plot_fig6.py 各有一份，結果 Fig 1 有 commit、Fig 6 沒有 ——
       同一條誠實準則，兩張圖兩個標準。

    ⚠️ 記的是**資料**的 commit，不是 HEAD。理由見 provenance.py：
       記 HEAD 的話，同一份資料在不同時間畫出來會是不同的檔案，
       「clone 下來跑一次得到同一張圖」就變成一句假話。
    """
    return (
        f"{what}\n"
        f"[Simulation on my own thermal plant - see docs/plant-model.md. "
        f"Not measured on server hardware.]\n"
        f"{provenance.version_line(inputs)}"
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
    fig.text(0.012, 0.005, _caption(what, provenance.FIG1_INPUTS), fontsize=7.5,
             va="bottom", color=C_MUTED)

    fig.subplots_adjust(bottom=0.30)
    FIGS.mkdir(exist_ok=True)
    out = FIGS / "fig1_sysid.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=C_SURFACE)
    plt.close(fig)
    print(f"wrote {out}")


#: 三組 λ 的顏色。**刻意用同一色相的三個明度，不是三個不同的顏色。**
#:
#: λ 是**有序**變數（0.5 < 1.0 < 2.0），不是三個並列的類別。
#: 用紅/橘/藍會暗示它們是三種不同的東西；用由淺到深的同一色相，
#: 圖上的順序本身就帶著「λ 變大」這個資訊，灰階印出來也還在。
#: 最深的那個給 2.0τ —— 本專案採用的那一組。
LAMBDA_COLOURS = {
    "0.5tau": "#8ab8e6",
    "1.0tau": "#2a78d6",
    "2.0tau": "#123f6d",
}
LAMBDA_LABELS = {
    "0.5tau": r"$\lambda$ = 0.5$\tau$",
    "1.0tau": r"$\lambda$ = 1.0$\tau$",
    "2.0tau": r"$\lambda$ = 2.0$\tau$  (adopted)",
}


def _med(entry: dict, key: str) -> str:
    """meta 裡某個指標的 `median [min, max]`。NaN 組別誠實印 NaN。"""
    stat = entry["metrics"][key]
    if stat["median"] is None:
        return "NaN"
    return f"{stat['median']:.3g} [{stat['min']:.3g}, {stat['max']:.3g}]"


def fig2() -> None:
    """Fig 2 — 三組 λ 的閉環負載擾動響應：溫度/PWM 雙面板 + 5 seed 帶狀範圍。

    ★ 版面上的四個決定：

    1. **x 軸從階躍前 60 s 開始**（與 Fig 1 同一個理由）。0~240 s 是 plant
       從冷機收斂到工作點，不是實驗的一部分，卻會把 y 軸拉大一倍。
       原始 CSV 仍然是完整的 0~1200 s。
    2. **帶狀範圍是 5 個 seed 的 min~max，中位數才是線。**
       畫一條「最好看的那次」是這張圖最容易造假的地方。
    3. **★ PWM 面板多一個穩態放大鏡。** 這張圖真正的發現是
       `pwm_pp` 三組差 3.3 倍 —— 但那是 0.4~1.2% 的尺度，
       在 0~100% 的面板上是一條線的厚度。不放大等於沒畫。
       （與 Fig 1 的死區放大鏡同一個道理：**發現在小尺度上就得放大**）
    4. **指標表的數字直接讀 meta.json，不在這裡重算。**
       重算一次就等於有第二份定義 —— 圖上的數字與 exp05 報的數字
       有機會不一致，而且不會有人發現。
    """
    meta = json.loads((DATA / "exp05_tuning_meta.json").read_text())
    setpoint = meta["setpoint_c"]
    power = meta["power_w"]
    step_at = power["at_s"]
    table = meta["lambda_table"]
    keys = list(LAMBDA_COLOURS)

    frames = {}
    for key in keys:
        mult = key.replace("tau", "")
        paths = sorted(DATA.glob(f"exp05_tuning_lam{mult}tau_seed*.csv"))
        if not paths:
            raise SystemExit(
                f"bench/data/ 裡沒有 λ={key} 的 CSV，先跑 bench/exp05_tuning.py")
        frames[key] = [pd.read_csv(p) for p in paths]

    t = frames[keys[0]][0]["t_s"].to_numpy()
    view_lo, view_hi = step_at - 60.0, float(t[-1])
    # 穩態放大鏡：與 pwm_pp / reversals 用的是**同一個尾段視窗**，
    # 這樣圖上看到的抖動就是表格裡那個數字量的東西。
    tail_s = meta["metric_settings"]["pwm_pp_tail_s"]
    zoom_lo, zoom_hi = view_hi - tail_s, view_hi

    fig, (ax_t, ax_p) = plt.subplots(
        2, 1, sharex=True, figsize=(11, 8.6),
        gridspec_kw={"height_ratios": [1.15, 1.0], "hspace": 0.12},
    )
    fig.patch.set_facecolor(C_SURFACE)

    for key in keys:
        colour = LAMBDA_COLOURS[key]
        temps = np.vstack([f["t_sense_c"].to_numpy() for f in frames[key]])
        pwms = np.vstack([f["pwm"].to_numpy() for f in frames[key]])

        ax_t.fill_between(t, temps.min(0), temps.max(0), color=colour,
                          alpha=0.22, lw=0, zorder=2)
        ax_t.plot(t, np.median(temps, 0), color=colour, lw=1.7, zorder=3,
                  label=LAMBDA_LABELS[key])
        ax_p.fill_between(t, pwms.min(0), pwms.max(0), color=colour,
                          alpha=0.22, lw=0, zorder=2)
        ax_p.plot(t, np.median(pwms, 0), color=colour, lw=1.7, zorder=3)

    # ── 上：溫度 ────────────────────────────────────────────────────────
    ax_t.axhline(setpoint, ls="--", lw=1.0, color=C_MODEL, zorder=4)
    ax_t.axvline(step_at, ls="--", lw=1.0, color=C_MUTED, zorder=4)
    ax_t.text(view_lo + 12, setpoint + 1.0, f"setpoint {setpoint:g} °C",
              fontsize=9, color=C_MODEL, va="bottom", zorder=5,
              bbox=dict(boxstyle="square,pad=0.25", fc=C_SURFACE, ec="none"))
    ax_t.annotate(
        f"load step {power['base']:g} W -> {power['step']:g} W",
        xy=(step_at, setpoint + 12), xytext=(step_at + 55, setpoint + 15),
        fontsize=9, color=C_MUTED,
        arrowprops=dict(arrowstyle="->", color=C_MUTED, lw=0.8),
    )
    ax_t.set_ylabel("sensed temperature (°C)", fontsize=10, color=C_MUTED)
    ax_t.set_title(
        "Fig 2 - Closed-loop load-disturbance response vs IMC lambda",
        fontsize=14, color="#0b0b0b", loc="left", pad=10)
    _style(ax_t)
    ax_t.set_xlim(view_lo, view_hi)
    win = t >= view_lo
    lo = min(float(np.min(np.vstack([f["t_sense_c"].to_numpy()[win]
                                     for f in frames[k]]))) for k in keys)
    hi = max(float(np.max(np.vstack([f["t_sense_c"].to_numpy()[win]
                                     for f in frames[k]]))) for k in keys)
    pad = 0.12 * (hi - lo)
    ax_t.set_ylim(lo - pad, hi + pad)

    # ── 下：PWM + 穩態放大鏡 ────────────────────────────────────────────
    ax_p.axvline(step_at, ls="--", lw=1.0, color=C_MUTED, zorder=4)
    ax_p.set_ylabel("PWM command (%)", fontsize=10, color=C_MUTED)
    ax_p.set_xlabel("time (s)", fontsize=10, color=C_MUTED)
    _style(ax_p)
    ax_p.set_ylim(0, 105)

    axin = ax_p.inset_axes([0.50, 0.13, 0.47, 0.52])
    zoom = (t >= zoom_lo) & (t <= zoom_hi)
    for key in keys:
        colour = LAMBDA_COLOURS[key]
        pwms = np.vstack([f["pwm"].to_numpy() for f in frames[key]])
        axin.fill_between(t[zoom], pwms.min(0)[zoom], pwms.max(0)[zoom],
                          color=colour, alpha=0.22, lw=0, zorder=2)
        axin.plot(t[zoom], np.median(pwms, 0)[zoom], color=colour, lw=1.0,
                  zorder=3)
    axin.set_xlim(zoom_lo, zoom_hi)
    _style(axin)
    axin.tick_params(labelsize=8)
    axin.set_title(
        f"zoom on the last {tail_s:g} s - this is the scale pwm p-p measures",
        fontsize=8.5, color=C_MUTED, loc="left", pad=4)
    ax_p.indicate_inset_zoom(axin, edgecolor=C_MUTED, alpha=0.6, lw=0.8)

    # 圖例放在溫度面板的右上角 —— 那一塊在 t > 600 s 之後是空的（三組都已
    # 收斂到 setpoint），不會壓到任何一條線，也不會像放在圖外那樣去擠表格。
    leg = ax_t.legend(loc="upper right", fontsize=9, framealpha=1.0,
                      facecolor=C_SURFACE, edgecolor=C_GRID)
    for text in leg.get_texts():
        text.set_color("#52514e")

    # ── 指標表：中位數 [min, max]，五個 seed ────────────────────────────
    rows = []
    for key in keys:
        e = table[key]
        adopted = " *" if key == "2.0tau" else ""
        rows.append([
            f"{key.replace('tau', ' tau')}{adopted}",
            f"{e['Kc']:.3f}",
            _med(e, "overshoot_c"),
            _med(e, "settle_after_step_s"),
            _med(e, "pwm_pp"),
            _med(e, "reversals_per_min"),
            _med(e, "fan_power_rel"),
            _med(e, "t_peak_c"),
        ])
    tbl = ax_p.table(
        cellText=rows,
        colLabels=["lambda", "Kc", "peak dev (°C)", "settle (s)",
                   "pwm p-p (%)", "reversals/min", "fan power (rel)",
                   "T peak (°C)"],
        loc="bottom", bbox=[0.0, -0.80, 1.0, 0.52],
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(7.5)
    for (row, _), cell in tbl.get_celld().items():
        cell.set_edgecolor(C_GRID)
        cell.set_facecolor(C_SURFACE)
        if row == 0:
            cell.get_text().set_color("#0b0b0b")
        else:
            cell.get_text().set_color("#52514e")

    # ── 參數區塊：包含這張圖最重要的那個限制 ────────────────────────────
    fopdt = meta["fopdt"]
    ms = meta["metric_settings"]
    ratio_pp = (table["0.5tau"]["metrics"]["pwm_pp"]["median"]
                / table["2.0tau"]["metrics"]["pwm_pp"]["median"])
    params = (
        f"IMC-PI from Fig 1: K = {fopdt['k']:+.4f} °C/%PWM, "
        f"tau = {fopdt['tau']:.2f} s, theta = {fopdt['theta']:.2f} s"
        f"   ->   Kc = tau / (|K|(lambda+theta)),  Ti = tau"
        f"       (* = the group this project adopts)\n"
        f"Only lambda changes between the three groups. Verified by the "
        f"experiment script, not by hand: same seed set, and every other sim "
        f"parameter compared field by field.\n"
        f"Load step {power['step']:g} W is below the controllable limit "
        f"(setpoint - t_amb) / rth_min = "
        f"{meta['controllable_power_limit_w']:.1f} W, so none of the three "
        f"groups saturates (peak PWM "
        f"{min(table[k]['metrics']['pwm_max']['median'] for k in keys):.0f}"
        f"-{max(table[k]['metrics']['pwm_max']['median'] for k in keys):.0f}%). "
        f"Saturation is Fig 3's experiment, not this one.\n"
        f"Metrics are computed from t = {meta['metrics_computed_from_s']:g} s "
        f"(the step) onward; the cold-start transient before it is not part of "
        f"this experiment. Band = min~max over "
        f"{len(meta['seeds'])} seeds, line = median.\n"
        f"LIMIT - larger lambda cuts the amplitude of the steady-state PWM "
        f"jitter by {ratio_pp:.1f}x, but NOT its rate: reversals/min are "
        f"within 2% of each other. At this noise level that metric is "
        f"dominated by sensor noise, not by the control law.\n"
        f"reversals deadband = {ms['reversals_deadband']:g} %PWM, tail = "
        f"{ms['reversals_tail_s']:g} s; settle band = +/-{ms['settle_band_c']:g} "
        f"°C held for {ms['settle_hold_s']:g} s. A larger deadband would "
        f"separate the three groups - it was not tuned to do so."
    )
    fig.text(0.012, 0.005, params, fontsize=8, va="bottom", color="#0b0b0b",
             family="monospace",
             bbox=dict(boxstyle="round,pad=0.55", fc=C_SURFACE, ec=C_GRID))

    what = (
        f"Fig 2 - Closed-loop response to a load step "
        f"{power['base']:g} W -> {power['step']:g} W at t = {step_at:g} s, "
        f"setpoint {setpoint:g} °C, controller sample period "
        f"{meta['ctrl_ts_s']:g} s (outer thermal loop rate), plant dt "
        f"{meta['dt_s']:g} s, anti-windup {meta['anti_windup']}, "
        f"integral limit {meta['integral_limit']}.\n"
        f"This is disturbance rejection, not setpoint tracking: peak deviation "
        f"grows with lambda here, which is the opposite of the familiar "
        f"setpoint-step behaviour. View starts at t = {view_lo:g} s. "
        f"Raw traces: bench/data/exp05_tuning_lam*.csv."
    )
    fig.text(0.012, -0.075, _caption(what, provenance.FIG2_INPUTS),
             fontsize=7.5, va="bottom", color=C_MUTED)

    fig.subplots_adjust(bottom=0.32)
    FIGS.mkdir(exist_ok=True)
    out = FIGS / "fig2_tuning.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=C_SURFACE)
    plt.close(fig)
    print(f"wrote {out}")


#: A/B 兩個 arm 的顏色。這是兩個**類別**（不是像 λ 那樣的有序量），
#: 所以用兩個色相：藍 = clamp（本專案採用的設定，與 Fig 1/2 的量測藍一致）、
#: 橘 = open（等同關閉的對照組）。橘在這張圖不兼任註解色 ——
#: 飽和區間的底色用灰，兩者不會撞。
AW_COLOURS = {"clamp": "#2a78d6", "open": "#eb6834"}
AW_LABELS = {
    "clamp": "integralLimit [0, 100] %PWM  (mirrors config.tuned.json)",
    "open": "integralLimit ±1e6  (equivalent to off - config.nowindup.json)",
}
#: L2 疊線：各 arm 的深色變體（同色相，更深 = 真的 daemon，虛線）。
AW_L2_COLOURS = {"clamp": "#123f6d", "open": "#a03d12"}


def fig3() -> None:
    """Fig 3 — anti-windup 單變因 A/B：溫度/PWM/積分項三面板 + 5 seed 帶狀。

    ★ 版面上的五個決定：

    1. **x 軸從 t = 0 畫整段**（Fig 1/2 都裁掉暖機段，這張刻意不裁）：
       open arm 在冷開機段就有故事 —— 下界 −1e6 讓積分往負向挖坑
       （**反向 windup**），風扇比 clamp 組晚開、暖機超調更高，
       兩組帶著略不同的狀態進入 400 W 階躍。裁掉暖機等於把
       「同一個機制在下界側的表現」裁掉。指標視窗仍從階躍起算（meta 記了）。
    2. **第三面板（積分項）是這張圖的核心**：windup 從名詞變成一條爬升的曲線。
       clamp 的上限畫成參考線 —— 藍線「頂」在它上面、橘線穿過它，
       機制一眼可見，不用讀任何文字。
    3. 飽和區間灰底，與 exp07 的 sat_frac 用同一個視窗定義。
    4. **recover_s 的兩個數字直接標在 PWM 面板** —— README 的結論引用的就是它們，
       順便把 90% 門檻畫成參考線，數字與圖形互相指認。
    5. 指標表直接讀 exp07 的 meta，不重算（與 Fig 2 同一條理由）。
    """
    meta = json.loads((DATA / "exp07_antiwindup_meta.json").read_text())
    setpoint = meta["setpoint_c"]
    power = meta["power_w"]
    up_at, down_at = power["up_at_s"], power["down_at_s"]
    table = meta["table"]
    arms = list(AW_COLOURS)

    frames = {}
    for arm in arms:
        paths = sorted(DATA.glob(f"exp07_aw{arm}_seed*.csv"))
        if not paths:
            raise SystemExit(
                f"bench/data/ 裡沒有 {arm} arm 的 CSV，"
                "先跑 bench/exp07_antiwindup.py")
        frames[arm] = [pd.read_csv(p) for p in paths]

    t = frames[arms[0]][0]["t_s"].to_numpy()

    fig, (ax_t, ax_p, ax_i) = plt.subplots(
        3, 1, sharex=True, figsize=(11, 10.8),
        gridspec_kw={"height_ratios": [1.2, 0.95, 1.0], "hspace": 0.10},
    )
    fig.patch.set_facecolor(C_SURFACE)

    for arm in arms:
        colour = AW_COLOURS[arm]
        for ax, col in ((ax_t, "t_sense_c"), (ax_p, "pwm"), (ax_i, "integral")):
            m = np.vstack([f[col].to_numpy() for f in frames[arm]])
            ax.fill_between(t, m.min(0), m.max(0), color=colour,
                            alpha=0.22, lw=0, zorder=2)
            ax.plot(t, np.median(m, 0), color=colour, lw=1.7, zorder=3,
                    label=AW_LABELS[arm] if ax is ax_t else None)

    # ── L2：未修改的上游 swampd 單趟即時執行，疊在 L1 帶狀上 ────────────
    #   溫度/PWM 來自 zone_0.log（每輪都寫）；積分來自 swampd 自己的 -g
    #   輸出（pidcore，有節流：內容變了 OR 60 s 才寫）。節流曲線**必須
    #   對時間軸畫** —— 兩筆之間值沒變，直線段就是事實；對 index 畫會把
    #   稀疏段壓扁而且看不出來。欄位對應與理由見 bench/parse_l2.py。
    l2_summary = json.loads((DATA / "exp07_L2_summary.json").read_text())
    l2 = {}
    for arm in arms:
        bridge_csv = DATA / f"exp07_L2_{arm}_plant.csv"
        if not bridge_csv.exists():
            raise SystemExit(
                f"L2 的 {arm} arm 資料不在 —— 先跑 bash harness/l2_ab.sh {arm}")
        epoch0 = parse_l2.bridge_epoch0_ms(bridge_csv)
        l2[arm] = {
            "zone": parse_l2.zone_frame(
                DATA / f"exp07_L2_{arm}_zone0.log", epoch0),
            "core": parse_l2.pidcore_frame(
                DATA / f"exp07_L2_{arm}_pidcore.die0", epoch0),
        }

    for arm in arms:
        zone, core = l2[arm]["zone"], l2[arm]["core"]
        style = {"color": AW_L2_COLOURS[arm], "lw": 1.25, "ls": (0, (5, 2)),
                 "zorder": 4}
        ax_t.plot(zone["t_s"], zone["t_sense_c"],
                  label=f"L2 {arm}: unmodified swampd, one real-time run",
                  **style)
        ax_p.plot(zone["t_s"], zone["pwm"], **style)
        ax_i.plot(core["t_s"], core["integral"], **style)

    # ── 飽和區間灰底 + 兩次階躍：三個面板同一份 ─────────────────────────
    for ax in (ax_t, ax_p, ax_i):
        ax.axvspan(up_at, down_at, color="#6b6a64", alpha=0.10, zorder=1)
        ax.axvline(up_at, ls="--", lw=0.9, color=C_MUTED, zorder=4)
        ax.axvline(down_at, ls="--", lw=0.9, color=C_MUTED, zorder=4)

    # ── 上：溫度 ────────────────────────────────────────────────────────
    ax_t.axhline(setpoint, ls="--", lw=1.0, color=C_MODEL, zorder=4)
    ax_t.text(10, setpoint + 1.5, f"setpoint {setpoint:g} °C", fontsize=9,
              color=C_MODEL, va="bottom", zorder=5,
              bbox=dict(boxstyle="square,pad=0.25", fc=C_SURFACE, ec="none"))
    ax_t.annotate(
        f"load {power['base']:g} -> {power['step']:g} W\n"
        f"(above the controllable limit: forces saturation)",
        xy=(up_at, 88.0), xytext=(up_at - 272, 86.0), fontsize=9, color=C_MUTED,
        arrowprops=dict(arrowstyle="->", color=C_MUTED, lw=0.8), zorder=5)
    ax_t.annotate(
        f"back to {power['base']:g} W\n(saturation releases - the arms diverge here)",
        xy=(down_at, 80.0), xytext=(down_at + 55, 84.5), fontsize=9,
        color=C_MUTED,
        arrowprops=dict(arrowstyle="->", color=C_MUTED, lw=0.8), zorder=5)
    ax_t.set_ylabel("sensed temperature (°C)", fontsize=10, color=C_MUTED)
    ax_t.set_title("Fig 3 - Anti-windup A/B (single variable: integralLimit)",
                   fontsize=14, color="#0b0b0b", loc="left", pad=10)
    _style(ax_t)
    ax_t.set_xlim(0.0, float(t[-1]))
    all_temps = np.vstack([f["t_sense_c"].to_numpy()
                           for arm in arms for f in frames[arm]])
    # ⚠️ y 軸範圍要把 L2 也算進去:L2 open 的暖機坑更深、進飽和更熱,
    #    尖峰(~112 °C)比 L1 高 —— 只用 L1 定範圍會把它裁掉。
    lo = min(float(all_temps.min()),
             *(float(l2[a]["zone"]["t_sense_c"].min()) for a in arms))
    hi = max(float(all_temps.max()),
             *(float(l2[a]["zone"]["t_sense_c"].max()) for a in arms))
    pad = 0.10 * (hi - lo)
    ax_t.set_ylim(lo - pad, hi + 1.6 * pad)

    leg = ax_t.legend(loc="lower right", fontsize=9, framealpha=1.0,
                      facecolor=C_SURFACE, edgecolor=C_GRID)
    for text in leg.get_texts():
        text.set_color("#52514e")

    # ── 中：PWM + recover_s 的兩個數字 ──────────────────────────────────
    threshold = meta["metric_settings"]["recover_pwm_threshold"]
    ax_p.axhline(threshold, ls=":", lw=0.9, color=C_MUTED, zorder=4)
    ax_p.text(float(t[-1]) - 10, threshold - 3.0,
              f"recover_s threshold ({threshold:g}%)", fontsize=8, ha="right",
              va="top", color=C_MUTED, zorder=5)
    ax_p.set_ylabel("PWM command (%)", fontsize=10, color=C_MUTED)
    _style(ax_p)
    ax_p.set_ylim(-4, 106)

    ro = table["open"]["metrics"]["recover_s"]
    rc = table["clamp"]["metrics"]["recover_s"]
    ratio = ro["median"] / rc["median"]
    l2m = l2_summary["arms"]
    l2_ratio = l2m["open"]["recover_s"] / l2m["clamp"]["recover_s"]
    box = (f"recover_s (open)  = {_med(table['open'], 'recover_s')} s\n"
           f"recover_s (clamp) = {_med(table['clamp'], 'recover_s')} s\n"
           f"ratio = {ratio:.1f}x        median [min, max], 5 seeds\n"
           f"L2, single runs:  {l2m['open']['recover_s']:.0f} s / "
           f"{l2m['clamp']['recover_s']:.1f} s = {l2_ratio:.1f}x")
    ax_p.text(0.015, 0.42, box, transform=ax_p.transAxes, va="bottom",
              fontsize=9, family="monospace", color="#0b0b0b", zorder=6,
              bbox=dict(boxstyle="round,pad=0.5", fc=C_SURFACE, ec=C_GRID))

    # ── 下：積分項（核心面板）───────────────────────────────────────────
    clamp_hi = table["clamp"]["integral_limit"][1]
    ax_i.axhline(clamp_hi, ls="--", lw=1.0, color=C_MODEL, zorder=4)
    ax_i.text(float(t[-1]) - 10, clamp_hi + 10,
              f"clamp arm's integralLimit_max = {clamp_hi:g}", fontsize=8.5,
              ha="right", color=C_MODEL, zorder=5)
    ax_i.axhline(0.0, lw=0.8, color=C_AXIS, zorder=1)

    med_open = np.median(
        np.vstack([f["integral"].to_numpy() for f in frames["open"]]), 0)
    dt_step = float(t[1] - t[0])
    i_pit = int(np.argmin(med_open[: int(up_at / dt_step)]))
    ax_i.annotate(
        "reverse windup at cold start: the -1e6 lower limit\n"
        "lets the integral dig a pit while T < setpoint",
        xy=(float(t[i_pit]), float(med_open[i_pit])),
        xytext=(float(t[i_pit]) + 130, float(med_open[i_pit]) + 30),
        fontsize=8.5, color=C_MUTED,
        arrowprops=dict(arrowstyle="->", color=C_MUTED, lw=0.8), zorder=5)

    ax_i.set_ylabel("integral term (%PWM)", fontsize=10, color=C_MUTED)
    ax_i.set_xlabel("time (s)", fontsize=10, color=C_MUTED)
    _style(ax_i)

    # ── 指標表：中位數 [min, max]，直接讀 meta ──────────────────────────
    rows = []
    for arm in arms:
        e = table[arm]
        lim = e["integral_limit"]
        lim_txt = (f"[{lim[0]:g}, {lim[1]:g}]"
                   if abs(lim[1]) <= 1000 else "±1e6")
        rows.append([
            arm, lim_txt,
            _med(e, "recover_s"), _med(e, "integral_max"),
            _med(e, "t_peak_c"), _med(e, "pwm_max"), _med(e, "sat_frac"),
        ])
    tbl = ax_i.table(
        cellText=rows,
        colLabels=["arm", "integralLimit (%PWM)", "recover_s (s)",
                   "integral max (%PWM)", "T peak (°C)", "PWM max (%)",
                   "saturated fraction"],
        loc="bottom", bbox=[0.0, -0.95, 1.0, 0.42],
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(7.5)
    for (row, _), cell in tbl.get_celld().items():
        cell.set_edgecolor(C_GRID)
        cell.set_facecolor(C_SURFACE)
        if row == 0:
            cell.get_text().set_color("#0b0b0b")
        else:
            cell.get_text().set_color("#52514e")

    # ── 參數區塊：單變因宣言 + 這張圖的誠實限制 ─────────────────────────
    sat_pct = 100.0 * table["open"]["metrics"]["sat_frac"]["median"]
    params = (
        f"Single variable, machine-checked: both arms share every sim "
        f"parameter and the same {len(meta['seeds'])} seeds; only "
        f"--integral-min/--integral-max differ. exp07_antiwindup.py compares\n"
        f"the full parameter dump of every run field by field and refuses to "
        f"write data otherwise. Both arms run --anti-windup clamp: the open "
        f"arm's limits are simply too wide\n"
        f"to ever bind - exactly how the swampd config pair differs "
        f"(config.tuned.json vs config.nowindup.json, a 2-line diff).\n"
        f"Gains: the lambda = 2 tau pair adopted in Fig 2, re-derived from "
        f"exp01's fit at run time (the script aborts on mismatch).\n"
        f"Load step {power['step']:g} W exceeds the controllable limit "
        f"(setpoint - t_amb) / rth_min = "
        f"{meta['controllable_power_limit_w']:.1f} W -> saturation is "
        f"guaranteed; PWM sits >= 99.99% for {sat_pct:.0f}% of the 400 W "
        f"window (both arms).\n"
        f"recover_s = first time the temperature falls back below the "
        f"setpoint -> first time PWM drops below {threshold:g}%. This is "
        f"windup's cost in one number: the open arm's fans keep\n"
        f"blowing at full speed for another ~{ro['median']:.0f} s (median) "
        f"after the temperature has already recovered - {ratio:.1f}x the "
        f"clamped arm - and overcool the die below the setpoint.\n"
        f"LIMIT - the arms already differ before the step: the open arm's "
        f"lower limit lets the integral go negative during cold start "
        f"(reverse windup), so they enter saturation with\n"
        f"slightly different states - T peak "
        f"{table['open']['metrics']['t_peak_c']['median']:.1f} vs "
        f"{table['clamp']['metrics']['t_peak_c']['median']:.1f} °C. Same "
        f"mechanism, other bound; kept in view on purpose.\n"
        f"L2 (dashed) - one 1500 s real-time run per arm against the "
        f"unmodified upstream swampd binary, rev "
        f"{l2_summary.get('swampd_rev', 'see exp07_L2_summary.json')}: "
        f"temperature/PWM from zone_0.log (written every cycle), integral "
        f"from swampd's own -g output (pidcore) / 150 RPM per %PWM.\n"
        f"Known differences, not tuned away: L2's effective PWM floor is "
        f"30% (zone minThermalOutput / fan outLim_min) vs L1's 0%, so its "
        f"cold start differs - the A/B claim lives after the release, far "
        f"from both floors."
    )
    fig.text(0.012, 0.005, params, fontsize=8, va="bottom", color="#0b0b0b",
             family="monospace",
             bbox=dict(boxstyle="round,pad=0.55", fc=C_SURFACE, ec=C_GRID))

    what = (
        f"Fig 3 - Anti-windup A/B on the L1 closed loop: load "
        f"{power['base']:g} -> {power['step']:g} W at t = {up_at:g} s, back "
        f"to {power['base']:g} W at t = {down_at:g} s; setpoint "
        f"{setpoint:g} °C, controller period {meta['ctrl_ts_s']:g} s, dt "
        f"{meta['dt_s']:g} s, {len(meta['seeds'])} seeds per arm (band = "
        f"min~max, line = median).\n"
        f"The integral panel is the point: while the output is pinned at "
        f"100%, the open arm's integral keeps climbing - state the plant "
        f"never sees - and must unwind after the release before the fans "
        f"can slow. Metric windows: t >= {up_at:g} s; recover_s from t >= "
        f"{down_at:g} s. Raw traces: bench/data/exp07_aw*_seed*.csv plus "
        f"exp07_L2_* (zone_0.log / pidcore from the real daemon)."
    )
    fig.text(0.012, -0.125, _caption(what, provenance.FIG3_INPUTS),
             fontsize=7.5, va="bottom", color=C_MUTED)

    # 0.36 而不是 Fig 2 的 0.32:這張的 params 區塊多了 L2 的三行,
    # 不加高的話它會蓋掉指標表的第二列(open 那列)。
    fig.subplots_adjust(bottom=0.36)
    FIGS.mkdir(exist_ok=True)
    out = FIGS / "fig3_antiwindup.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=C_SURFACE)
    plt.close(fig)
    print(f"wrote {out}")


def fig4() -> None:
    """Fig 4 — failsafe 偵測時序：t0 停止推值 → t1 failsafe → t2 PWM 拉頂。

    ★ 版面上的四個決定：

    1. **畫「中位數那一次」run，不是最好看的那次** —— 挑 t2−t0 最接近
       5 次中位數的 run；五次的完整數字都在表格裡。
    2. **x 軸從 t0 前 60 s 開始**（與 Fig 1/2 同慣例）：前 240 s 的
       冷機收斂不是實驗的一部分。
    3. **溫度面板畫兩條線**：plant 的真實溫度（bridge 還在記）與
       D-Bus 上凍結的最後推送值 —— 「感測器凍結」的視覺就是這兩條線
       在 t0 分家。
    4. **t1→t2 只有一個內圈週期（~0.1 s），在 90 s 寬的圖上是一條線的
       厚度** —— 與 Fig 1 的死區、Fig 2 的穩態同款：發現在小尺度上就
       得放大，PWM 面板配一個事件放大鏡。
    """
    meta = json.loads((DATA / "exp09_failsafe/exp09_meta.json").read_text())
    runs = meta["runs"]
    med_t2 = meta["summary"]["t2_minus_t0_s"]["median"]
    pick = min(runs, key=lambda r: abs(r["t2_minus_t0_s"] - med_t2))
    k = pick["run"]
    t0 = meta["stop_push_at_s"]
    t1_rel = t0 + pick["t1_minus_t0_s"]
    t2_rel = t0 + pick["t2_minus_t0_s"]

    plant = pd.read_csv(DATA / f"exp09_failsafe/run{k}_plant.csv")
    zone = pd.read_csv(DATA / f"exp09_failsafe/run{k}_zone0.log")
    pmeta = json.loads(
        (DATA / f"exp09_failsafe/run{k}_plant_meta.json").read_text())
    zt = (zone["epoch_ms"] - pmeta["epoch0_ms"]) / 1000.0
    # ★ `fan0_pwm`（0~1 比例）×100，**不是** `fan0_pwm_raw` —— 本 rig 的
    #   writePath 讀不回 raw，那一欄恆為 -1。同一個欄位語意錯在同一天
    #   出現第三次（P22 → detect_events → 這裡），這行註解就是墓碑。
    zpwm = zone["fan0_pwm"].astype(float) * 100.0
    zfs = zone["failsafe"].astype(int)

    frozen = float(plant.loc[plant["t_s"] < t0, "t_sense_c"].iloc[-1])
    view_lo, view_hi = t0 - 60.0, float(plant["t_s"].iloc[-1])

    fig, (ax_t, ax_p, ax_f) = plt.subplots(
        3, 1, sharex=True, figsize=(11, 9.2),
        gridspec_kw={"height_ratios": [1.2, 1.0, 0.45], "hspace": 0.13},
    )
    fig.patch.set_facecolor(C_SURFACE)

    for ax in (ax_t, ax_p, ax_f):
        ax.axvline(t0, ls="--", lw=1.1, color=C_MODEL, zorder=4)
        ax.axvline(t1_rel, ls="--", lw=1.1, color=C_ANNOTATE, zorder=4)
        ax.axvline(t2_rel, ls=":", lw=1.1, color="#a03d12", zorder=4)

    # ── 上：plant 真實溫度 vs D-Bus 凍結值 ─────────────────────────────
    ax_t.plot(plant["t_s"], plant["t_sense_c"], color=C_MEASURED, lw=1.6,
              zorder=3, label="plant temperature (bridge keeps recording)")
    ax_t.plot([t0, view_hi], [frozen, frozen], ls="--", lw=1.4,
              color=C_MUTED, zorder=3,
              label="last pushed value - frozen on D-Bus after t0")
    ax_t.set_ylabel("temperature (°C)", fontsize=10, color=C_MUTED)
    ax_t.set_title("Fig 4 - Failsafe detection timing "
                   "(sensor freeze -> failsafe -> PWM to failsafePercent)",
                   fontsize=14, color="#0b0b0b", loc="left", pad=10)
    leg = ax_t.legend(loc="center left", fontsize=8.5, framealpha=1.0,
                      facecolor=C_SURFACE, edgecolor=C_GRID)
    for text in leg.get_texts():
        text.set_color("#52514e")
    _style(ax_t)

    ax_t.annotate(
        "t0 = stop pushing\n(scripted, epoch-anchored)",
        xy=(t0, frozen - 1.0), xytext=(t0 - 50, frozen - 14), fontsize=8.5,
        color=C_MODEL,
        arrowprops=dict(arrowstyle="->", color=C_MODEL, lw=0.8))
    ax_t.annotate(
        f"t1 = failsafe flag  (+{pick['t1_minus_t0_s']:.2f} s:\n"
        f"timeout {meta['timeout_s']} s + staleness-check\n"
        f"phase, outer loop 1 Hz)",
        xy=(t1_rel, frozen - 2.0), xytext=(t1_rel + 5, frozen - 22),
        fontsize=8.5, color=C_ANNOTATE,
        arrowprops=dict(arrowstyle="->", color=C_ANNOTATE, lw=0.8))

    # ── 中：PWM(swampd 視角)+ 事件放大鏡 ────────────────────────────
    ax_p.plot(zt, zpwm, color=C_COMMANDED, lw=1.5, zorder=3)
    ax_p.set_ylabel("PWM command (%)", fontsize=10, color=C_MUTED)
    ax_p.set_ylim(0, 108)
    _style(ax_p)

    # inset 抬高到面板上半 —— 主線是 30% 的平線（y=30，面板下 1/3），
    # 放低會把它自己要放大的那條線遮住。
    axin = ax_p.inset_axes([0.055, 0.44, 0.40, 0.50])
    zlo, zhi = t1_rel - 1.5, t2_rel + 1.5
    zm = (zt >= zlo) & (zt <= zhi)
    axin.plot(zt[zm], zpwm[zm], color=C_COMMANDED, lw=1.2, zorder=3,
              drawstyle="steps-post")
    axin.axvline(t1_rel, ls="--", lw=1.0, color=C_ANNOTATE)
    axin.axvline(t2_rel, ls=":", lw=1.0, color="#a03d12")
    axin.set_xlim(zlo, zhi)
    _style(axin)
    axin.tick_params(labelsize=8)
    axin.set_title(
        f"zoom: t1 -> t2 = {pick['t2_minus_t1_s'] * 1000.0:.0f} ms "
        f"(one fan-loop cycle + file write)",
        fontsize=8.5, color=C_MUTED, loc="left", pad=4)
    ax_p.indicate_inset_zoom(axin, edgecolor=C_MUTED, alpha=0.6, lw=0.8)

    # ── 下:failsafe 布林(zone_0.log 的末欄,每輪直寫、無節流)──────────
    ax_f.plot(zt, zfs, color=C_ANNOTATE, lw=1.6, drawstyle="steps-post",
              zorder=3)
    ax_f.set_ylim(-0.15, 1.25)
    ax_f.set_yticks([0, 1])
    ax_f.set_yticklabels(["normal", "failsafe"])
    ax_f.set_ylabel("zone mode", fontsize=10, color=C_MUTED)
    ax_f.set_xlabel("time since run start (s)", fontsize=10, color=C_MUTED)
    _style(ax_f)
    ax_f.set_xlim(view_lo, view_hi)

    # ── 表格:五次 run 全列(不挑好看的)──────────────────────────────
    s1, s2 = meta["summary"]["t1_minus_t0_s"], meta["summary"]["t2_minus_t0_s"]
    rows = [[f"run {r['run']}{'  *' if r['run'] == k else ''}",
             f"{r['t1_minus_t0_s']:.3f}", f"{r['t2_minus_t0_s']:.3f}",
             f"{r['t2_minus_t1_s'] * 1000.0:.0f}"] for r in runs]
    rows.append(["median [min, max]",
                 f"{s1['median']:.3f} [{s1['min']:.3f}, {s1['max']:.3f}]",
                 f"{s2['median']:.3f} [{s2['min']:.3f}, {s2['max']:.3f}]",
                 "-"])
    tbl = ax_f.table(
        cellText=rows,
        colLabels=["run (* = plotted)", "t1 - t0 (s)", "t2 - t0 (s)",
                   "t2 - t1 (ms)"],
        loc="bottom", bbox=[0.10, -2.35, 0.80, 1.85],
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(7.5)
    for (row, _), cell in tbl.get_celld().items():
        cell.set_edgecolor(C_GRID)
        cell.set_facecolor(C_SURFACE)
        cell.get_text().set_color("#0b0b0b" if row == 0 else "#52514e")

    # ── 參數區塊 ─────────────────────────────────────────────────────
    params = (
        f"Single variable: whether temperature keeps being pushed - a one-shot "
        f"event at t0 = {t0:g} s, not a sweep. Load constant 150 W.\n"
        f"Config = config.tuned.json with exactly one field changed: die0 "
        f"timeout 0 -> {meta['timeout_s']} s (generated and field-checked by "
        f"bench/exp09_failsafe.py, not hand-edited).\n"
        f"Why timeout was 0 in deployment: a passive D-Bus sensor only "
        f"advances its staleness clock on PropertiesChanged, so a *stable* "
        f"temperature looks dead (W3). This experiment inverts that trap:\n"
        f"  the bridge pushes a fresh (noisy) value every 100 ms while "
        f"running, so stopping the push IS the sensor-freeze event, with a "
        f"script-controlled timestamp.\n"
        f"t1 is read from zone_0.log (written every fan cycle, no throttling, "
        f"wall-clock epoch per line). The FailSafe D-Bus property is a plain "
        f"getter and never emits PropertiesChanged\n"
        f"  (upstream zone.cpp @ c5e5955), so the plan's 'busctl monitor' "
        f"method cannot observe t1 at all; busctl get-property is kept as a "
        f"point check (run*_failsafe_property.txt = 'b true').\n"
        f"Composition of the delay: timeout ({meta['timeout_s']} s, config) + "
        f"staleness-check phase (checks ride the 1 Hz thermal loop -> up to "
        f"~1 s jitter, the dominant spread below) + D-Bus/log write (ms).\n"
        f"t2 - t1 is one 100 ms fan cycle + a plain-file write. "
        f"LIMIT - this is NOT '100 ms failsafe': the sensor timeout itself "
        f"is a seconds-scale config value; N here is ~{s2['median']:.1f} s.\n"
        f"LIMIT - the freeze is simulated by stopping value pushes, not by "
        f"unplugging I2C; swampd is the unmodified upstream binary at "
        f"c5e5955 on a private D-Bus (L2, same rig as Fig 3)."
    )
    fig.text(0.012, 0.005, params, fontsize=7.6, va="bottom", color="#0b0b0b",
             family="monospace",
             bbox=dict(boxstyle="round,pad=0.55", fc=C_SURFACE, ec=C_GRID))

    what = (
        f"Fig 4 - Failsafe detection timing on the L2 rig: unmodified "
        f"upstream swampd @ c5e5955 against the same C++ plant, private "
        f"D-Bus. t0 = stop pushing temperature (script-anchored epoch), "
        f"t1 = failsafe flag in zone_0.log, t2 = PWM reaches "
        f"failsafePercent (100% -> raw 255). {len(runs)} independent runs "
        f"(seeds 1-{len(runs)}); the plotted run is the one closest to the "
        f"median t2 - t0. Raw: bench/data/exp09_failsafe/."
    )
    fig.text(0.012, -0.155, _caption(what, provenance.FIG4_INPUTS),
             fontsize=7.5, va="bottom", color=C_MUTED)

    fig.subplots_adjust(bottom=0.40)
    FIGS.mkdir(exist_ok=True)
    out = FIGS / "fig4_failsafe.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=C_SURFACE)
    plt.close(fig)
    print(f"wrote {out}")


#: Fig 5 的三個指標：一個收益、兩個代價。**語意色，不是三個並列的類別色**：
#: 收益（reversals ↓）沿用量測藍；兩個代價（T peak ↑、fan power ↑）用
#: 橘色系的兩個深度 —— 同一個「代價」家族，深度只是讓相鄰面板分得開。
SLEW_PANELS = [
    ("reversals_per_min", "#2a78d6", "reversals / min\n(acoustic proxy)"),
    ("t_peak_c", "#eb6834", "peak temperature\n(°C)"),
    ("fan_power_rel", "#a03d12", "fan power\n(relative, N³ model)"),
]

#: 圖上標的「選定工作點」。claims.json 的 reversals_reduction_ratio 也指它。
#: 選它的理由（取捨語言，不是最佳解）寫在 docs/measurement.md exp08。
SLEW_CHOSEN = 0.5


def fig5() -> None:
    """Fig 5 — slew 掃描：聲學代理 / 峰值溫度 / 相對風扇功耗的三方取捨。

    ★ 版面上的四個決定：

    1. **三個 sharex 面板，不是計畫偽碼的三重 y 軸（twinx×2）。**
       三個量綱擠同一格時帶狀範圍互相蓋，第三條軸的刻度沒有人讀得懂；
       分面板後「同一個 slew 值往下對」就是取捨的讀法，
       轉折的垂直對應一眼可見。
    2. **x 軸是 log₂（0.25~16 %PWM/s），slew=0（不限制）不在軸上** ——
       0 在這個軸上的語意是「無限鬆」不是「最緊」，畫在原點會把
       整條曲線的方向讀反。它改畫成每個面板的水平基準帶
       （中位數虛線 + 5 seed 範圍）。
    3. 帶狀是 5 個 seed 的 min~max，線是中位數（與 Fig 2 同一慣例）。
    4. 指標數字直接讀 exp08_meta.json，不在這裡重算（同 Fig 2 理由）。
    """
    meta = json.loads((DATA / "exp08_meta.json").read_text())
    table = meta["slew_table"]
    slews = meta["slew_values"]
    swept = np.array([s for s in slews if s > 0], dtype=float)
    base_key = str(slews[0])  # "0.0" = unlimited 基準
    power = meta["power_w"]

    def stats(key: str, metric: str) -> tuple[float, float, float]:
        m = table[key]["metrics"][metric]
        return m["median"], m["min"], m["max"]

    fig, axes = plt.subplots(
        3, 1, sharex=True, figsize=(9.5, 10.2),
        gridspec_kw={"hspace": 0.16},
    )
    fig.patch.set_facecolor(C_SURFACE)

    for ax, (metric, colour, label) in zip(axes, SLEW_PANELS, strict=True):
        med = [stats(str(s), metric)[0] for s in swept]
        lo = [stats(str(s), metric)[1] for s in swept]
        hi = [stats(str(s), metric)[2] for s in swept]
        bmed, blo, bhi = stats(base_key, metric)

        # unlimited 基準：水平帶（它也有 5 個 seed 的不確定度，不是一條理想線）
        ax.axhspan(blo, bhi, color=colour, alpha=0.10, lw=0, zorder=1)
        ax.axhline(bmed, ls="--", lw=1.1, color=colour, alpha=0.8, zorder=2)

        ax.fill_between(swept, lo, hi, color=colour, alpha=0.22, lw=0, zorder=3)
        ax.plot(swept, med, "o-", color=colour, lw=1.7, ms=4.5, zorder=4)

        ax.axvline(SLEW_CHOSEN, ls=":", lw=1.2, color=C_MUTED, zorder=2)
        ax.set_xscale("log", base=2)
        ax.set_ylabel(label, fontsize=9.5, color=C_MUTED)
        _style(ax)

    # 基準帶與選定點只標一次（第一面板），三個面板共用同一套視覺語言
    ax0 = axes[0]
    bmed0 = stats(base_key, "reversals_per_min")[0]
    ax0.text(swept[-1], bmed0, "  unlimited (slew = 0):\n  median + seed range",
             fontsize=8, color="#2a78d6", va="center", ha="left", clip_on=False)
    ax0.text(SLEW_CHOSEN, ax0.get_ylim()[1], " chosen operating point\n"
             f" ({SLEW_CHOSEN:g} %PWM/s - a point on the curve,\n"
             " not an optimum)",
             fontsize=8, color=C_MUTED, va="top", ha="left")

    axes[0].set_title(
        "Fig 5 - Slew rate limit: acoustic proxy vs thermal margin vs fan power",
        fontsize=14, color="#0b0b0b", loc="left", pad=10)
    axes[-1].set_xticks(swept)
    axes[-1].set_xticklabels([f"{s:g}" for s in swept])
    axes[-1].minorticks_off()
    axes[-1].set_xlabel(
        "slew rate limit, symmetric ±S (%PWM per second) - "
        "log scale, tighter to the LEFT",
        fontsize=10, color=C_MUTED)

    # ── 指標表：3 指標 × 8 組的中位數（帶狀已在圖上，表格只放中位數）──────
    col_labels = ["unlimited"] + [f"{s:g}" for s in swept]
    row_labels = ["reversals/min", "T peak (°C)", "fan power (rel)"]
    cells = []
    for metric, _, _ in SLEW_PANELS:
        row = []
        for key in [base_key] + [str(s) for s in swept]:
            m = table[key]["metrics"][metric]["median"]
            row.append("NaN" if m is None else f"{m:.3g}")
        cells.append(row)
    tbl = axes[-1].table(cellText=cells, rowLabels=row_labels,
                         colLabels=col_labels,
                         loc="bottom", bbox=[0.06, -0.62, 0.94, 0.38])
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(7.5)
    for (row, _), cell in tbl.get_celld().items():
        cell.set_edgecolor(C_GRID)
        cell.set_facecolor(C_SURFACE)
        cell.get_text().set_color("#0b0b0b" if row == 0 else "#52514e")

    # ── 參數區塊：最重要的是「為什麼 λ=0.5τ」與兩個 LIMIT ────────────────
    fopdt = meta["fopdt"]
    ms = meta["metric_settings"]
    gains = meta["gains"]
    chosen = stats(str(SLEW_CHOSEN), "reversals_per_min")[0]
    base_rev = stats(base_key, "reversals_per_min")[0]
    # claims.json 的 reversals_reduction_ratio 就是這個數 —— 按 seed 配對的
    # 比值中位數（兩組共用同一組 seed），從 meta 讀，不在這裡重算。
    paired = meta["reversals_ratio_vs_unlimited"][str(SLEW_CHOSEN)]
    d_peak = (stats(str(SLEW_CHOSEN), "t_peak_c")[0]
              - stats(base_key, "t_peak_c")[0])
    d_pow = (stats(str(SLEW_CHOSEN), "fan_power_rel")[0]
             / stats(base_key, "fan_power_rel")[0] - 1.0)
    params = (
        f"Single variable: slewNeg/slewPos only - machine-checked field by "
        f"field across all {len(slews)} x {len(meta['seeds'])} runs "
        f"(bench/exp08_slew_sweep.py).\n"
        f"Tuning held at lambda = 0.5 tau (Kc = {gains['Kc']:.3f}, from Fig 1's "
        f"K = {fopdt['k']:+.4f}, tau = {fopdt['tau']:.2f} s) - deliberately NOT "
        f"the deployed lambda = 2.0 tau of Fig 2/Fig 3.\n"
        f"  Why: slew acts on high-rate output changes. At lambda = 2.0 tau the "
        f"noise-driven step is ~0.10 %PWM and tracking this load needs only "
        f"~0.33 %PWM/s,\n"
        f"  so every value in this range is a dead knob there (pilot run: all "
        f"eight groups returned identical reversals). This sweep asks the "
        f"complementary question:\n"
        f"  keep the high-gain tuning's disturbance peak and buy acoustics "
        f"with slew instead. Fig 2 buys amplitude with lambda; slew buys "
        f"*rate* - two different acoustic defects.\n"
        f"Square-wave load {power['base']:g} <-> {power['step']:g} W, full "
        f"period {power['period_s']:g} s, from t = {power['at_s']:g} s; "
        f"{power['step']:g} W < controllable limit "
        f"{meta['controllable_power_limit_w']:.1f} W, so no group saturates. "
        f"Metrics from t = {meta['metrics_computed_from_s']:g} s; reversals "
        f"tail = {ms['reversals_tail_s']:g} s = exactly the last half-period.\n"
        f"At the chosen {SLEW_CHOSEN:g} %PWM/s: reversals {base_rev:.3g} -> "
        f"{chosen:.3g} per min ({paired['paired_median']:.2f}x paired by seed, "
        f"range {paired['paired_min']:.2g}-{paired['paired_max']:.2g}), peak "
        f"temperature +{d_peak:.2g} °C, fan power {d_pow:+.0%} (relative).\n"
        f"LIMIT - fan power is the affinity-law N^3 proxy computed from fan "
        f"speed, a *relative model value*, not measured watts.\n"
        f"LIMIT - reversals use deadband = {ms['reversals_deadband']:g} %PWM "
        f"(untuned, W6 value): sub-deadband reversals are invisible to this "
        f"metric by definition."
    )
    fig.text(0.012, 0.005, params, fontsize=7.6, va="bottom", color="#0b0b0b",
             family="monospace",
             bbox=dict(boxstyle="round,pad=0.55", fc=C_SURFACE, ec=C_GRID))

    what = (
        f"Fig 5 - Symmetric slew rate limit sweep, {len(swept)} values + "
        f"unlimited baseline, x {len(meta['seeds'])} seeds. Square-wave load "
        f"{power['base']:g} <-> {power['step']:g} W (period "
        f"{power['period_s']:g} s), setpoint {meta['setpoint_c']:g} °C, "
        f"controller sample {meta['ctrl_ts_s']:g} s, anti-windup "
        f"{meta['anti_windup']} (upstream ec::pid() semantics, including its "
        f"integral back-calculation whenever slew is set).\n"
        f"Line = median, band = min~max over seeds; the dashed horizontal "
        f"line + tint is the unlimited baseline. Raw traces: "
        f"bench/data/exp08_slew*_seed*.csv."
    )
    fig.text(0.012, -0.062, _caption(what, provenance.FIG5_INPUTS),
             fontsize=7.5, va="bottom", color=C_MUTED)

    fig.subplots_adjust(bottom=0.30, top=0.955)
    FIGS.mkdir(exist_ok=True)
    out = FIGS / "fig5_slew_sweep.png"
    fig.savefig(out, dpi=150, bbox_inches="tight", facecolor=C_SURFACE)
    plt.close(fig)
    print(f"wrote {out}")


FIGURES = {1: fig1, 2: fig2, 3: fig3, 4: fig4, 5: fig5}


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
