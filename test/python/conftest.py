"""讓 pytest 找得到 bench/ 與 tools/ 底下的模組。

這兩個目錄刻意**不是** Python package（沒有 `__init__.py`）——
它們是腳本目錄，不是函式庫；`pyproject.toml` 的 `py-modules = []` 也是同一個意思。
所以這裡用 sys.path 直接指過去，而不是把整個 repo 變成一個套件。

路徑從 `__file__` 推，不從工作目錄推 —— 這樣不管是
`meson test`（workdir = repo 根）還是 `pytest test/python`（workdir 隨你）
都找得到同一份程式碼。
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]

for sub in ("bench", "tools"):
    path = str(ROOT / sub)
    if path not in sys.path:
        sys.path.insert(0, path)
