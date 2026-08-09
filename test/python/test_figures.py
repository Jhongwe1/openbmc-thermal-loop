"""交付的圖,是不是**現在這份程式碼與資料**畫得出來的那一張。

★ 這一組測試守的是一句宣稱:
    「任何人 clone 下來執行同一行指令,得到的是**同一張圖**。」

  這句話寫在 `bench/plot.py` 的 docstring 裡,而在 2026-08-09 之前它是**假的** ——
  caption 記的是**產圖當下的 HEAD**,所以同一份資料在不同 commit 上畫出來
  逐 byte 不同。**差的就是那一串 hash。**

  發現的方式:真的去 clone 一份下來跑。那件事我做了很久才做,
  而它是這個專案唯一一個「別人會怎麼看到它」的檢查。

★ 為什麼「逐 byte 相同」這種強斷言在這裡是可行的(而不是脆弱)
  實測過三件事:
    · matplotlib 在同一份輸入上是**決定性**的(連畫兩次逐 byte 相同)
    · 產出的 PNG 裡**沒有時間戳**(只有一個 `Software` 標籤)
    · 所以唯一的變數是 caption 的內容
  這三件事都成立,「逐 byte 相同」才是一個公平的要求。
  任何一件不成立時,這個測試會紅,而那本身就是要知道的事。

⚠️ 這個測試會**重畫**圖,所以要花幾秒。它畫到 pytest 的暫存目錄,
   不碰工作目錄裡的交付物 —— 測試中途掛掉不會留下爛攤子。
"""

import os
import pathlib
import subprocess
import sys

import pytest

import provenance

ROOT = pathlib.Path(__file__).resolve().parents[2]
FIGURES = ROOT / "figures"

# (檔名, 產圖指令, 它的資料輸入)
CASES = [
    ("fig1_sysid.png", ["bench/plot.py", "--fig", "1"], provenance.FIG1_INPUTS),
    ("fig6_dts_to_redfish.png", ["bench/plot_fig6.py"], provenance.FIG6_INPUTS),
]


def render(script_args: list[str], out_dir: pathlib.Path) -> None:
    env = dict(os.environ, FIGURES_DIR=str(out_dir))
    proc = subprocess.run([sys.executable, *script_args], cwd=ROOT, env=env,
                          capture_output=True, text=True)
    assert proc.returncode == 0, f"產圖失敗：\n{proc.stdout}\n{proc.stderr}"


@pytest.mark.parametrize(("name", "args", "inputs"), CASES,
                         ids=[c[0] for c in CASES])
def test_committed_figure_is_what_the_code_produces(name, args, inputs, tmp_path):
    """★★ repo 裡那張圖 == 現在重畫出來的那張圖(逐 byte)。

    這一條同時擋掉兩種事:
      · **改了產圖程式碼卻忘了重畫** —— 交付的圖與程式碼不一致,
        而且**看起來完全正常**,因為兩張圖都很像
      · **改了資料卻忘了重畫** —— 更嚴重:圖上的曲線不是那份 CSV 畫的

    ⚠️ 它紅的時候,正確的處理是**重畫並一起 commit**,不是放寬這個測試。
    """
    committed = FIGURES / name
    assert committed.exists(), f"{committed} 不在"

    render(args, tmp_path)
    fresh = tmp_path / name
    assert fresh.exists(), f"重畫沒有產生 {name}"

    assert fresh.read_bytes() == committed.read_bytes(), (
        f"{name} 與現在的程式碼＋資料畫出來的不一樣。\n"
        f"  repo 裡: {committed.stat().st_size} bytes\n"
        f"  重畫的 : {fresh.stat().st_size} bytes\n"
        f"  處理方式：重畫一次並跟著 commit 進去，不要放寬這個測試。"
    )


@pytest.mark.parametrize(("name", "args", "inputs"), CASES,
                         ids=[c[0] for c in CASES])
def test_rendering_is_deterministic(name, args, inputs, tmp_path):
    """同一份輸入畫兩次要逐 byte 相同 —— 上一條斷言成立的前提。

    ★ 前提斷言要自己有測試。 沒有這一條的話,上面那個測試哪天紅了,
      我分不出是「圖過期了」還是「matplotlib 本來就不決定性」。
    """
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    render(args, a)
    render(args, b)
    assert (a / name).read_bytes() == (b / name).read_bytes(), (
        "同一份輸入畫兩次得到不同的檔案 —— matplotlib 這個版本不是決定性的，"
        "上一個測試的「逐 byte 相同」就不再是公平的要求。"
    )


# caption 記的是「資料的 commit」而不是 HEAD 這件事，由
# test_provenance.py::test_version_line_says_data_commit_not_repo_commit 守。
# 這裡刻意不重複斷言 —— 同一條規則有兩個測試，改的時候只會改到一個。
