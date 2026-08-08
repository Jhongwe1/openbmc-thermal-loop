"""每張圖的「這是在什麼東西上、用哪一版產生的」——**只定義一次**。

★ 為什麼要獨立成一個模組
    〈誠實準則〉第 6 條:「每張圖的 caption 要有映像檔完整檔名與 repo commit。」
    這條規則原本有**兩份實作** —— `bench/plot.py` 一份、`bench/plot_fig6.py`
    一份,而且兩份長得不一樣:Fig 1 有 commit,**Fig 6 沒有**。

    「六張圖不同標準」不是排版問題,是**證據等級不一致**:
    看得到 commit 的那張圖指得回一份原始碼,看不到的那張指不回去。

    一條規則只能有一份實作,否則它遲早會分岔 —— 而且分岔的時候不會有人發現,
    因為兩張圖各自看起來都很正常。

⚠️ commit 記的是**產圖當下的 HEAD**,也就是收錄這張圖那個 commit 的父節點。
   這不是 bug,是無法避免的:圖在被 commit 之前就已經產生了。
   意思是「這張圖是從**這一版**的程式碼與資料產生的」—— 正是要記錄的東西。
"""

from __future__ import annotations

import pathlib
import subprocess

ENV = pathlib.Path("docs/env-baseline.md")


def image_name() -> str:
    """從 docs/env-baseline.md 撈釘選的映像完整檔名。

    ⚠️ 計畫範本是「讀第 4 行」—— 那一行其實是產生日期,不是映像名。
       改成找「主線映像」那一行,文件多加一段也不會壞掉。
    """
    if not ENV.exists():
        return "(docs/env-baseline.md not found)"
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if "主線映像" in line and "`" in line:
            return line.split("`")[1]
    return "(image name not found)"


def repo_commit() -> str:
    """產圖當下的 short HEAD;不在 git 工作樹裡時回一個講得清楚的字串。"""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "(not a git checkout)"
    return out or "(unknown)"


def version_line() -> str:
    """caption 的第三行:映像 + commit。**六張圖共用同一個字串格式。**"""
    return f"image: {image_name()}  |  repo commit: {repo_commit()}"
