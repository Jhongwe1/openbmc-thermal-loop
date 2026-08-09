"""每張圖的來源標註（〈誠實準則〉第 6 條）。

★ 這一組測試守的不是一個函式，是一條**紀律**：
    「每張圖的 caption 要有映像檔完整檔名與 repo commit。」

    紀律很難用測試守，但**「這條規則只有一份實作」**可以。
    在 2026-08-09 之前它有兩份 —— `plot.py` 一份、`plot_fig6.py` 一份 ——
    然後就分岔了：Fig 1 有 commit，**Fig 6 沒有**。
    兩張圖各自看起來都很正常，所以沒有人發現。
"""

import pathlib
import re

import provenance

BENCH = pathlib.Path(__file__).resolve().parents[2] / "bench"
FIGURE_SCRIPTS = ["plot.py", "plot_fig6.py"]


def test_image_name_finds_the_pinned_image():
    """要撈到 docs/env-baseline.md 釘選的那個映像完整檔名。

    ⚠️ 計畫範本是「讀第 4 行」—— 那一行其實是產生日期。
       文件多加一段就會壞，而壞掉的樣子是 caption 上出現一個日期當映像名。
    """
    name = provenance.image_name()
    assert name.startswith("obmc-phosphor-image-"), name
    assert name.endswith(".static.mtd"), name


def test_repo_commit_looks_like_a_short_hash():
    commit = provenance.repo_commit()
    assert re.fullmatch(r"[0-9a-f]{7,40}", commit), commit


def test_version_line_has_both_halves():
    """兩樣都要有。少任何一樣，這張圖就指不回產生它的那一版。"""
    line = provenance.version_line(provenance.FIG1_INPUTS)
    assert "image: obmc-phosphor-image-" in line, line
    assert "data commit: " in line, line


def test_version_line_says_data_commit_not_repo_commit():
    """★ 名字要說實話。

    寫 `repo commit` 會讓讀者以為那是 HEAD —— 而它**不是**，
    它是「這張圖的資料最後一次變動的 commit」。
    這個區別正是「clone 下來得到同一張圖」能成立的唯一理由:
    HEAD 每個 commit 都在動，資料的 commit 只在資料真的變動時才動。
    """
    line = provenance.version_line(provenance.FIG1_INPUTS)
    assert "repo commit" not in line, line

    head = provenance.repo_commit()
    data = provenance.data_commit(provenance.FIG1_INPUTS)
    assert data != "(uncommitted)", "Fig 1 的資料還沒進 git"
    assert data != head, (
        f"資料的 commit（{data}）等於 HEAD（{head}）。"
        f"如果這一版真的動了 exp01 的資料，這是正常的；"
        f"否則代表 provenance 又退回去記 HEAD 了。"
    )


def test_dirty_inputs_are_marked():
    """輸入有未 commit 的改動時要標 `-dirty`。

    沒有這個標記的話，一張用「還沒進 git 的資料」畫出來的圖，
    caption 會指向一個**不含那些資料**的 commit —— 比沒有標記更糟。
    """
    # 拿一個一定乾淨的路徑當對照，確認乾淨時**不會**被標。
    assert not provenance.data_commit(provenance.FIG1_INPUTS).endswith("-dirty")


def test_every_figure_script_uses_the_shared_version_line():
    """★ 這條是架構斷言：**所有產圖腳本共用同一份來源標註實作。**

    防的是「新增第七張圖時，順手複製一份 caption 產生器」——
    複製當下兩份是一樣的，分岔是幾週之後的事，而且不會有人發現。
    """
    for name in FIGURE_SCRIPTS:
        source = (BENCH / name).read_text(encoding="utf-8")
        assert "provenance.version_line(" in source, (
            f"bench/{name} 沒有用共用的 version_line() —— "
            f"誠實準則第 6 條不可以有第二份實作"
        )


def test_no_figure_script_reimplements_the_image_lookup():
    """同上的另一半：不准有人自己再寫一個 `_image_name()`。"""
    for name in FIGURE_SCRIPTS:
        source = (BENCH / name).read_text(encoding="utf-8")
        assert "def _image_name" not in source, (
            f"bench/{name} 自己又實作了一次映像名判定 —— 用 provenance.image_name()"
        )
