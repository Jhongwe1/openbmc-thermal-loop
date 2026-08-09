"""git 記的執行位元,要與檔案有沒有 shebang 一致。

★ 為什麼需要一個測試守這種事
    這個專案在 Windows + WSL 上開發,而用 `\\\\wsl.localhost\\...` 這條路徑
    編輯檔案**會把執行位元洗掉**(`755` → `644`)。

    危險的地方在於它**很安靜**:
      · 本機還是跑得動,因為平常都是 `python x.py` / `bash x.sh` 這樣叫
      · `git status` 在你 commit 之後就乾淨了 —— 因為錯的模式已經進去了
      · 別人 clone 下來 `./tools/xxx.sh` 才會噴 `Permission denied`

    2026-08-09 這一天它咬了兩次。第二次是**已經 commit 進去**才發現的,
    而發現的方式是最後那次總驗收剛好跑了 `chmod +x`,讓 `git status` 變髒。
    **靠「剛好」發現的東西,要補一個不靠運氣的檢查。**

⚠️ 檢查的是 **git index 裡的模式**,不是工作目錄的。
   工作目錄的模式在 Windows 那一側本來就不可靠;
   真正會被別人 clone 下去的是 index 裡那個。
"""

import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]


def tracked_files() -> list[tuple[str, str]]:
    """回傳 [(git 模式, 路徑), ...]。不在 git 工作樹裡就跳過整組測試。"""
    proc = subprocess.run(["git", "ls-files", "-s"], cwd=ROOT,
                          capture_output=True, text=True)
    if proc.returncode != 0:
        pytest.skip("不在 git 工作樹裡")
    out = []
    for line in proc.stdout.splitlines():
        meta, path = line.split("\t", 1)
        mode = meta.split()[0]
        out.append((mode, path))
    return out


def has_shebang(path: str) -> bool:
    full = ROOT / path
    if not full.is_file():
        return False
    try:
        with full.open("rb") as fh:
            return fh.read(2) == b"#!"
    except OSError:
        return False


def test_shebang_files_are_executable_in_git():
    """有 shebang 的檔案,在 git 裡必須是 100755。

    ⚠️ 修法是 `chmod +x <檔案>` 之後重新 commit ——
       **不要**把 shebang 拿掉來讓測試變綠。
    """
    offenders = [
        path for mode, path in tracked_files()
        if has_shebang(path) and mode != "100755"
    ]
    assert not offenders, (
        "這些檔案有 shebang 但 git 記的不是 100755"
        "（別人 clone 下來 ./ 執行會 Permission denied）：\n  "
        + "\n  ".join(offenders)
        + "\n修法：chmod +x 上面那些檔案，然後重新 commit。"
    )


def test_executable_files_have_a_shebang():
    """反過來:標了可執行的檔案要真的可以被執行(有 shebang)。

    防的是「順手 `chmod +x *.py`」——那會讓一堆只能被 import 的模組
    看起來像可以直接跑的工具。符號連結與二進位檔不在此限。
    """
    offenders = [
        path for mode, path in tracked_files()
        if mode == "100755" and not has_shebang(path)
    ]
    assert not offenders, (
        "這些檔案標了可執行但沒有 shebang：\n  " + "\n  ".join(offenders)
    )
