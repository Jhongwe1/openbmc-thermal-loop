"""每張圖的「這是在什麼東西上、用哪一版產生的」——**只定義一次**。

★ 為什麼要獨立成一個模組
    〈誠實準則〉第 6 條:「每張圖的 caption 要有映像檔完整檔名與 repo commit。」
    這條規則原本有**兩份實作** —— `bench/plot.py` 一份、`bench/plot_fig6.py`
    一份,而且兩份長得不一樣:Fig 1 有 commit,**Fig 6 沒有**。

    「六張圖不同標準」不是排版問題,是**證據等級不一致**:
    看得到 commit 的那張圖指得回一份原始碼,看不到的那張指不回去。

    一條規則只能有一份實作,否則它遲早會分岔 —— 而且分岔的時候不會有人發現,
    因為兩張圖各自看起來都很正常。

★★ caption 記的是「**這張圖的資料**最後一次變動的 commit」，不是產圖當下的 HEAD
    （2026-08-09 改）。

    原本記 HEAD。那樣有兩個問題：

    1. **它讓「別人 clone 下來跑一次得到同一張圖」變成一句假話。**
       HEAD 每個 commit 都在變，所以同一份資料在不同時間畫出來的 PNG
       **逐 byte 不同** —— 差的就是 caption 裡那串 hash。
       實測過：matplotlib 本身是決定性的（同一個 commit 連畫兩次逐 byte 相同），
       PNG 裡也沒有時間戳，**唯一的變數就是這串 hash**。
    2. HEAD 常常與這張圖**無關**。修一個文件的 typo 也會讓 caption 變，
       但那個 commit 沒有動到任何一筆資料。

    改成記「資料的 commit」之後：
      · 資料沒動 → 任何人在任何時間畫出來都是**同一個檔案**（可以 `cmp` 驗）
      · 資料動了 → hash 跟著動，指得回**真正產生這張圖的那一版資料**

    ⚠️ **產圖程式碼刻意不算在裡面**，否則會有自我參照問題：
       「改 plot.py 的那個 commit」在圖被畫出來的當下還不存在。
       程式碼那一側改由測試守：`test_figures_reproduce_byte_for_byte`
       會重畫一次並與 repo 裡那張逐 byte 比對 ——
       任何會改變圖的程式碼變動都會讓它紅。

⚠️ 資料有未 commit 的改動時，hash 後面會加 `-dirty`（借 `git describe` 的慣例）。
   沒有這個標記的話，一張用「還沒進 git 的資料」畫出來的圖，
   caption 會指向一個**不含那些資料**的 commit —— 那比沒有標記更糟。
"""

from __future__ import annotations

import pathlib
import subprocess

ENV = pathlib.Path("docs/env-baseline.md")

#: Fig 1 的輸入。`docs/env-baseline.md` 也算 —— caption 上的映像名從它來。
FIG1_INPUTS = [
    "bench/data/exp01_sysid_seed*.csv",
    "bench/data/exp01_fit.txt",
    "bench/data/exp01_sysid_meta.txt",
    "docs/env-baseline.md",
]

#: Fig 6 的輸入。
FIG6_INPUTS = [
    "bench/data/exp03_trace/layers.json",
    "docs/env-baseline.md",
]


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


def _git(*args: str) -> str | None:
    """跑一個 git 指令;不在 git 工作樹裡（或沒有 git）時回 None。"""
    try:
        proc = subprocess.run(["git", *args], capture_output=True, text=True,
                              check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return proc.stdout.strip()


def repo_commit() -> str:
    """目前的 short HEAD。**不要拿它當 caption 用** —— 見模組 docstring。

    留著是因為 `meta.txt` 那一類「這次執行的環境」紀錄要的正是 HEAD。
    """
    return _git("rev-parse", "--short", "HEAD") or "(not a git checkout)"


def data_commit(paths: list[str]) -> str:
    """這批輸入檔**最後一次被改動**的 commit，未 commit 的改動標 `-dirty`。"""
    head = _git("log", "-1", "--format=%h", "--", *paths)
    if head is None:
        return "(not a git checkout)"
    if not head:
        return "(uncommitted)"
    dirty = _git("status", "--porcelain", "--", *paths)
    return f"{head}-dirty" if dirty else head


def version_line(inputs: list[str]) -> str:
    """caption 的第三行:映像 + 資料的 commit。**每張圖共用同一個字串格式。**

    寫 `data commit` 而不是 `repo commit`，是因為它記的**就是**資料的版本 ——
    名字要說實話，不然讀者會以為那是 HEAD。
    """
    return f"image: {image_name()}  |  data commit: {data_commit(inputs)}"
