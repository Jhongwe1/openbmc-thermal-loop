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


FIGURES = {1: fig1, 2: fig2}


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
