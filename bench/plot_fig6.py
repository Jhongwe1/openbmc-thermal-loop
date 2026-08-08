#!/usr/bin/env python3
"""Fig 6 — device tree 到 Redfish 的跨層追蹤圖。

    python bench/plot_fig6.py

輸入：bench/data/exp03_trace/layers.json（由 tools/trace_sensor.sh 產生）
輸出：figures/fig6_dts_to_redfish.png

★ 為什麼這張圖不是手畫的
    Fig 6 的反造假設計只有一條：「每一格都是我機器上的真實字串」。手畫的圖無從
    查證那句話。這支程式只從 layers.json 讀字串，而 layers.json 的每一格都指得回
    bench/data/exp03_trace/raw/ 裡某一條指令的 stdout。

★ 為什麼圖上一個中文字都沒有
    這台機器的 matplotlib 沒有 CJK 字型。但真正的理由不是「沒裝」——是裝了也不該
    用：那會讓「別人 clone 下來跑一次得到同一張圖」依賴他們的字型設定。
"""

from __future__ import annotations

import json
import pathlib
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.patches as mpatches  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

TRACE = pathlib.Path("bench/data/exp03_trace/layers.json")
ENV = pathlib.Path("docs/env-baseline.md")
OUT = pathlib.Path("figures/fig6_dts_to_redfish.png")

# 每一層一個顏色。刻意用低飽和度：這張圖的主角是字串，不是配色。
BOX_FACE = "#f7f7f9"
BOX_EDGE = "#5b6472"
UNIT_FACE = "#fff4e0"
UNIT_EDGE = "#c8912a"


def _image_name() -> str:
    """從 docs/env-baseline.md 撈釘選的映像檔名（與 bench/plot.py 同一套規則）。"""
    if not ENV.exists():
        return "(docs/env-baseline.md not found)"
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if "主線映像" in line and "`" in line:
            return line.split("`")[1]
    return "(image name not found)"


def main() -> int:
    if not TRACE.exists():
        print(f"找不到 {TRACE}，先跑 ./tools/trace_sensor.sh", file=sys.stderr)
        return 1

    doc = json.loads(TRACE.read_text(encoding="utf-8"))
    layers = doc["layers"]
    edges = doc["edges"]

    # ── 版面 ────────────────────────────────────────────────────────
    # 每個盒子的高度依它有幾行文字決定，不要固定高度：dts 那格有 11 行，
    # driver 那格只有 3 行，固定高度會讓其中一格擠爆、另一格空一大片。
    line_h = 0.30
    pad = 0.34
    gap = 0.78  # 盒子之間留給箭頭與說明文字

    # 太長的行要折，不要讓字跑出框線。折行時保留一個懸掛縮排，讓人看得出
    # 「這是上一行的續行」而不是新的一項。
    def wrap(line: str, width: int = 92) -> list[str]:
        line = line.replace("\t", "  ")
        if len(line) <= width:
            return [line]
        out, rest = [], line
        indent = " " * (len(line) - len(line.lstrip()) + 4)
        while len(rest) > width:
            cut = rest.rfind(" ", 0, width)
            if cut <= 0:
                cut = width
            out.append(rest[:cut])
            rest = indent + rest[cut:].lstrip()
        out.append(rest)
        return out

    wrapped = [[w for line in ly["lines"] for w in wrap(line)] for ly in layers]

    heights = [pad * 2 + line_h * (len(w) + 1) for w in wrapped]
    total = sum(heights) + gap * (len(layers) - 1)

    fig_h = total * 0.52 + 2.0
    fig, ax = plt.subplots(figsize=(13.2, fig_h))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, total)
    ax.axis("off")

    y = total
    box_left, box_right = 0.15, 9.15

    for i, ly in enumerate(layers):
        h = heights[i]
        y_top, y_bot = y, y - h

        ax.add_patch(
            mpatches.FancyBboxPatch(
                (box_left, y_bot),
                box_right - box_left,
                h,
                boxstyle="round,pad=0.02,rounding_size=0.12",
                linewidth=1.3,
                edgecolor=BOX_EDGE,
                facecolor=BOX_FACE,
            )
        )

        ty = y_top - pad - line_h * 0.15
        ax.text(box_left + 0.22, ty, ly["title"], fontsize=11.5,
                fontweight="bold", va="top", ha="left", color="#1c2530")
        ax.text(box_left + 2.95, ty, ly["subtitle"], fontsize=8.4,
                family="monospace", va="top", ha="left", color="#3d4756")

        for j, line in enumerate(wrapped[i]):
            ax.text(box_left + 0.34, ty - line_h * (j + 1.05), line,
                    fontsize=8.0, family="monospace", va="top", ha="left",
                    color="#22282f")

        # 右側單位泡泡：這張圖的第二個重點是「單位換了幾次」
        if ly["value"] is not None:
            ax.add_patch(
                mpatches.FancyBboxPatch(
                    (9.55, y_bot + h / 2 - 0.28),
                    1.95,
                    0.56,
                    boxstyle="round,pad=0.02,rounding_size=0.1",
                    linewidth=1.1,
                    edgecolor=UNIT_EDGE,
                    facecolor=UNIT_FACE,
                )
            )
            ax.text(10.52, y_bot + h / 2, f'{ly["value"]}  {ly["unit"]}',
                    fontsize=9.5, family="monospace", ha="center", va="center",
                    color="#7a5410", fontweight="bold")

        # 證據檔名（讓每一格都指得回一條指令的 stdout）
        ax.text(box_right - 0.12, y_bot + 0.13, ly["evidence"], fontsize=6.6,
                family="monospace", ha="right", va="bottom", color="#8a93a0")

        # ── 箭頭 ────────────────────────────────────────────────────
        if i < len(layers) - 1:
            ax.annotate(
                "",
                xy=(1.5, y_bot - gap + 0.06),
                xytext=(1.5, y_bot - 0.06),
                arrowprops=dict(arrowstyle="-|>", linewidth=1.5, color=BOX_EDGE),
            )
            ax.text(1.75, y_bot - gap / 2, edges[i], fontsize=8.6,
                    va="center", ha="left", color="#39424f", style="italic")

        y = y_bot - gap

    # ── 標題與 caption ──────────────────────────────────────────────
    fig.suptitle(
        "Fig 6  One sensor traced from device tree to Redfish",
        fontsize=13.5, fontweight="bold", y=0.995,
    )

    caption = (
        f'Platform: {doc["platform"]}    Image: {_image_name()}    Captured: {doc["captured_at"]}\n'
        f'Sensor "{doc["sensor"]}" = the tmp421 at i2c {doc["i2c_device"]}. '
        f'{doc["injected_temp_c"]} C was injected into the emulated chip over QMP; '
        f"every box below is real output from that machine.\n"
        f'Device tree obtained by: {doc["how_dts_obtained"]}  (the blob the kernel actually loaded, not the one in the image).\n'
        "Two things change on the way up: the UNIT (millidegree -> degree -> Redfish 'Cel') and the NAME "
        "(tmp421@4f -> 0-004f -> hwmon0 -> die0 -> temperature_die0).\n"
        "Raw evidence for every string: bench/data/exp03_trace/raw/"
    )
    fig.text(0.012, 0.008, caption, fontsize=7.4, va="bottom", ha="left",
             color="#3d4756", family="monospace")

    fig.subplots_adjust(top=0.965, bottom=0.115, left=0.01, right=0.99)
    OUT.parent.mkdir(exist_ok=True)
    fig.savefig(OUT, dpi=170)
    print(f"寫出 {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
