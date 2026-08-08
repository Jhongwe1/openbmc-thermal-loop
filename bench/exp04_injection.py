#!/usr/bin/env python3
"""exp04：注入路徑的傳遞特性 —— 我量了我的量測儀器。

實驗協定（七欄，定義見 docs/measurement.md）
--------------------------------------------------
假設     : 從 QMP 寫進 QEMU tmp421 的溫度，到 BMC 的 `temp1_input` 之間
           **不是恆等映射**。預期會看到兩件事：
           ① 量化 —— 讀值只落在間距約 62.5 m°C 的離散階上（LSB = 1/16 °C）；
           ② **系統性偏壓** —— 正好落在格點上的要求值，讀回來會低整整一格。
              ★ ② 是**寫這個實驗之前先寫下來的假設**，理由是讀了 QEMU setter 的
                `(temp*256 - 128)/1000`：那個 `-128` 加上 C 的往 0 截斷，
                會把值壓到自己那一格的正下方。純量化器不會有這個行為。
           另外預期讀值有**快取**：注入後立刻讀會拿到上一個值
           （Linux tmp421 driver 是 `time_after(jiffies, last_updated + HZ/2)`）。
自變因   : 注入的溫度（唯一）
控制變因 : 同一顆晶片（i2c-0 0x4f、通道 0）、同一份映像、同一版 QEMU、
           同一個 repo commit、BMC 不重開、期間不跑其他實驗。全部記進 meta.txt。
應變因   : BMC `temp1_input` 的讀值（m°C）、QMP 讀回值（m°C）、
           以及「注入後多久讀得到新值」
重複     : grid 掃描重複 5 次（協定要求 ≥ 5），報「五次完全相同」
           —— 這條路徑是數位、決定性的，**重複的意義是證明它決定性**，
           不是求平均。
原始資料 : bench/data/exp04_injection/{sweep,grid,cache}.csv + meta.txt
產圖     : （這個實驗不產圖，結論寫進 docs/plant-model.md §2.1）

用法
----
    python bench/exp04_injection.py            # 跑實驗（需要 QEMU + BMC）
    python bench/exp04_injection.py --check    # 只驗證 repo 裡的 CSV（不需要 BMC）

★★ 這個實驗的方法學重點（面試會問，而且這是我踩到才想清楚的）
    `tools/set_die_temp.py --verify` 是「**輪詢到讀值等於我的預測值為止**」。
    那個機制拿來當**閘門**很好，拿來**產生這裡的資料就會變成同義反覆** ——
    我等到它等於我的預測，然後宣稱「看，它等於我的預測」。

    所以這支腳本的等待邏輯是**穩定性判定**：連續數次讀到同一個值、
    而且橫跨超過兩個快取窗口，才採計。**那條判定與預測值完全無關。**
    預測值只在事後當成一欄放進 CSV，讓「預測 vs 實測」變成一個可以被檢查的
    比較，而不是一個被保證的結果。

★ 為什麼 `--check` 不需要 BMC
    它讀的是**已經進 git 的 CSV**。任何人 clone 下來就能重驗這三條結論，
    不必先架起一台 QEMU。這與 bench/plot.py「圖從 repo 裡的資料產生」同一個原則。
"""

from __future__ import annotations

import argparse
import csv
import datetime
import pathlib
import subprocess
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))

import set_die_temp as sdt  # noqa: E402

OUT = pathlib.Path("bench/data/exp04_injection")
ENV = pathlib.Path("docs/env-baseline.md")

BUS, ADDR, CHANNEL = sdt.DEFAULT_BUS, sdt.DEFAULT_ADDR, sdt.DEFAULT_CHANNEL

# 正好落在 1/16 °C 格點上的要求值（40000/62.5 = 640，整數）。
# 選這些是因為**純量化器對它們應該是恆等映射** —— 任何偏差都不可能是量化造成的。
GRID_POINTS_mC = [40000, 41000, 42000, 42500, 45000, 55000, 60000]
GRID_REPEATS = 5

# 細掃：跨越好幾個格點，用來**數出**階的間距。
# 一個點量不出解析度（40.000 那個點就是這樣騙過我的），要看到階梯本身。
SWEEP_START_mC, SWEEP_STOP_mC, SWEEP_STEP_mC = 42000, 42320, 10

# 快取：來回跳大距離，立刻讀 vs 等穩定後讀。
LATENCY_SEQUENCE_mC = [50000, 30000, 50000, 30000, 50000, 30000]
LATENCY_SAMPLE_S = 0.025    # 取樣間隔：要遠小於 500 ms 的快取窗口才量得出它
LATENCY_WINDOW_S = 3.0      # 每次轉換最多追蹤幾秒


class BmcSampler:
    """一條**持久**的 ssh 連線，用來高速取樣 hwmon。

    ★ 為什麼非要持久連線不可（這是我踩到才想清楚的）
      第一版每讀一次就開一條新的 ssh，單次來回約 **0.4 s**。
      而 Linux tmp421 driver 的快取窗口是 `HZ/2` = **0.5 s** ——
      **量測工具比要量的現象還慢**，於是「注入後立刻讀會拿到舊值」
      永遠觀察不到，看起來像「快取不存在」。

      這是一個很典型的錯誤結論：**量不到不等於不存在，可能只是取樣太慢。**
      改成一條連線上跑迴圈之後，單次讀取降到毫秒等級，
      才有辦法把可見延遲**畫出來**而不是猜它在不在。

    ⚠️ ssh 的 `-n` 旗標和這個做法互斥：`-n` 把 stdin 接到 /dev/null，
       迴圈會讀到 EOF 立刻結束，而且**安靜地什麼都不做**。
    """

    def __init__(self, path: str):
        self.path = path
        self.proc = subprocess.Popen(
            ["sshpass", "-p", sdt.BMC_PASS, "ssh",
             "-o", "StrictHostKeyChecking=no",
             "-o", "UserKnownHostsFile=/dev/null",
             "-o", "LogLevel=ERROR", "-o", "ConnectTimeout=10",
             "-p", sdt.BMC_SSH_PORT, f"{sdt.BMC_USER}@{sdt.BMC_HOST}",
             f"while read -r _; do cat {path}; done"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1)

    def read(self) -> int:
        self.proc.stdin.write("\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise SystemExit("BMC 取樣連線斷了")
        return int(line.strip())

    def close(self) -> None:
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


# ═══════════════════════════════════════════════════════════════════════
#  量測
# ═══════════════════════════════════════════════════════════════════════


def resolve_hwmon_path() -> str:
    """把 hwmon 的 glob 解成一條具體路徑（取樣迴圈裡不要每次重新展開 glob）。"""
    import shutil
    if shutil.which("sshpass") is None:
        raise SystemExit("這個實驗需要 sshpass（sudo apt install sshpass）")
    proc = subprocess.run(
        ["sshpass", "-p", sdt.BMC_PASS, "ssh", "-n",
         "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
         "-o", "LogLevel=ERROR", "-o", "ConnectTimeout=10",
         "-p", sdt.BMC_SSH_PORT, f"{sdt.BMC_USER}@{sdt.BMC_HOST}",
         f"ls {sdt.hwmon_input_path(BUS, ADDR, CHANNEL)}"],
        capture_output=True, text=True)
    lines = proc.stdout.strip().splitlines()
    if proc.returncode != 0 or not lines:
        raise SystemExit(f"找不到 BMC 上的 hwmon 檔：{proc.stderr.strip()}")
    return lines[0]


def settle_read(sampler: BmcSampler, *, quiet_reads: int = 4,
                interval_s: float = 0.35,
                timeout_s: float = 10.0) -> tuple[int, float]:
    """等到 hwmon 讀值穩定，回傳 (讀值, 等了幾秒)。

    ★ 判定條件：連續 `quiet_reads` 次讀到同一個值。
      4 次 × 0.35 s 橫跨 1.05 s，超過兩個 500 ms 的 driver 快取窗口。

    ★ **這條判定裡沒有出現預測值。** 那是刻意的 —— 見模組 docstring 的
      「方法學重點」。用預測值當停止條件的話，這份資料就不再是獨立的觀測。
    """
    started = time.monotonic()
    history: list[int] = []
    while True:
        history.append(sampler.read())
        if len(history) >= quiet_reads and len(set(history[-quiet_reads:])) == 1:
            return history[-1], time.monotonic() - started
        if time.monotonic() - started > timeout_s:
            raise SystemExit(
                f"hwmon 讀值在 {timeout_s}s 內沒有穩定下來：最後幾次是 "
                f"{history[-quiet_reads:]}。BMC 上是不是有別的東西在寫這顆晶片？"
            )
        time.sleep(interval_s)


def inject(qmp, path: str, requested_mC: int) -> int:
    """寫一個值進去，回傳 QMP 讀回來的值（注入端的自我確認）。"""
    prop = f"temperature{CHANNEL}"
    qmp.cmd("qom-set", path=path, property=prop, value=requested_mC)
    return qmp.cmd("qom-get", path=path, property=prop)


def open_chip():
    qmp = sdt.Qmp(sdt.DEFAULT_SOCK)
    devices = sdt.find_tmp421(qmp)
    match = [p for bus, addr, p in devices if bus == BUS and addr == ADDR]
    if not match:
        raise SystemExit(f"找不到 i2c-{BUS} 0x{ADDR:02x} 上的 tmp421")
    return qmp, match[0]


def run_grid(qmp, path, sampler) -> list[dict]:
    rows = []
    for repeat in range(GRID_REPEATS):
        for requested in GRID_POINTS_mC:
            qom = inject(qmp, path, requested)
            hwmon, waited = settle_read(sampler)
            rows.append({
                "repeat": repeat,
                "requested_mC": requested,
                "qom_readback_mC": qom,
                "hwmon_mC": hwmon,
                "expected_mC": sdt.expected_hwmon_mC(requested),
                "bias_mC": hwmon - requested,
                "settle_s": f"{waited:.2f}",
            })
            print(f"  grid r{repeat} {requested:>6} -> qom {qom:>6} "
                  f"hwmon {hwmon:>6}  bias {hwmon - requested:+d}")
    return rows


def run_sweep(qmp, path, sampler) -> list[dict]:
    rows = []
    for requested in range(SWEEP_START_mC, SWEEP_STOP_mC + 1, SWEEP_STEP_mC):
        qom = inject(qmp, path, requested)
        hwmon, waited = settle_read(sampler)
        rows.append({
            "requested_mC": requested,
            "qom_readback_mC": qom,
            "hwmon_mC": hwmon,
            "expected_mC": sdt.expected_hwmon_mC(requested),
            "settle_s": f"{waited:.2f}",
        })
        print(f"  sweep {requested:>6} -> qom {qom:>6} hwmon {hwmon:>6}")
    return rows


def run_latency(qmp, path, sampler) -> list[dict]:
    """量**可見延遲**：注入之後，新值要多久才在 BMC 的 sysfs 上出現。

    ★ 為什麼量的是延遲曲線，不是「有沒有快取」
      「有快取」是一個是非題，而且答案取決於**我讀得多快** ——
      第一版每次開新 ssh（0.4 s）就得到「沒有快取」的錯誤結論。
      延遲是一個**數字**，它不隨我的取樣速度改變（只要取樣夠快），
      而且它正好是 W6/W7 需要的那個數字：
      **host 驅動的閉環，注入之後至少要等這麼久才能讀。**

    輸出的是**每一個取樣點**，不是一個結論 —— 結論由 --check 從這些點算出來。
    """
    rows = []
    # 先帶到序列的最後一個值並等穩，否則第一次轉換的「舊值」是未定義的。
    inject(qmp, path, LATENCY_SEQUENCE_mC[-1])
    settle_read(sampler)

    for i, requested in enumerate(LATENCY_SEQUENCE_mC):
        before = sampler.read()
        t0 = time.monotonic()
        inject(qmp, path, requested)
        target = sdt.expected_hwmon_mC(requested)
        first_seen_ms = None
        while True:
            elapsed_ms = (time.monotonic() - t0) * 1000.0
            value = sampler.read()
            rows.append({
                "transition": i,
                "from_mC": before,
                "requested_mC": requested,
                "expected_mC": target,
                "elapsed_ms": f"{elapsed_ms:.1f}",
                "value_mC": value,
            })
            if first_seen_ms is None and value == target and target != before:
                first_seen_ms = elapsed_ms
            if elapsed_ms > LATENCY_WINDOW_S * 1000.0:
                break
            if first_seen_ms is not None and elapsed_ms > first_seen_ms + 200.0:
                break  # 已經看到新值並多追 200 ms，夠了
            time.sleep(LATENCY_SAMPLE_S)
        seen = f"{first_seen_ms:.0f} ms" if first_seen_ms is not None else "沒看到"
        print(f"  latency {before} -> {target}：首次看到新值 {seen}")
    return rows


# ═══════════════════════════════════════════════════════════════════════
#  中繼資料
# ═══════════════════════════════════════════════════════════════════════


def _image_name() -> str:
    """從 docs/env-baseline.md 撈釘選的映像檔名（與 bench/plot.py 同一套規則）。"""
    if not ENV.exists():
        return "(docs/env-baseline.md not found)"
    for line in ENV.read_text(encoding="utf-8").splitlines():
        if "主線映像" in line and "`" in line:
            return line.split("`")[1]
    return "(image name not found)"


def _qemu_version(qmp) -> str:
    v = qmp.cmd("query-version")["qemu"]
    return f"{v['major']}.{v['minor']}.{v['micro']}"


def _bmc(command: str) -> str:
    import shutil
    if shutil.which("sshpass") is None:
        return "(sshpass 不在，取不到)"
    proc = subprocess.run(
        ["sshpass", "-p", sdt.BMC_PASS, "ssh", "-n",
         "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
         "-o", "LogLevel=ERROR", "-o", "ConnectTimeout=10",
         "-p", sdt.BMC_SSH_PORT, f"{sdt.BMC_USER}@{sdt.BMC_HOST}", command],
        capture_output=True, text=True)
    return proc.stdout.strip() or f"(取不到：{proc.stderr.strip()})"


def write_meta(qmp, hwmon_path: str) -> None:
    """★ 沒有這個檔案，這批 CSV 三個月後就指不回任何一個版本。

    exp02/exp03 一開始就是缺這個 —— 159 bytes 的純數字，說不出是在什麼上面量的。
    """
    lines = [
        "# exp04 — 注入路徑的傳遞特性。欄位定義見 docs/measurement.md。",
        "# repo_dirty=yes 是正常的：資料一定在收錄它的那個 commit **之前**產生，",
        "# 就跟圖的 caption 只能記到父 commit 一樣。repo_commit 記的是產生當下的 HEAD。",
        f"captured_at={datetime.date.today().isoformat()}",
        f"repo_commit={subprocess.getoutput('git rev-parse --short HEAD')}",
        f"repo_dirty={'yes' if subprocess.getoutput('git status --porcelain') else 'no'}",
        f"image={_image_name()}",
        f"qemu_version={_qemu_version(qmp)}",
        f"bmc_os_version_id={_bmc('. /etc/os-release && echo $VERSION_ID')}",
        f"bmc_build_id={_bmc('. /etc/os-release && echo $BUILD_ID')}",
        f"bmc_kernel={_bmc('uname -r')}",
        f"swampd_service={_bmc('systemctl is-active phosphor-pid-control')}",
        f"chip=i2c-{BUS} 0x{ADDR:02x} channel {CHANNEL}",
        f"hwmon_path={hwmon_path}",
        f"driver={_bmc(f'readlink -f /sys/bus/i2c/devices/{BUS}-{ADDR:04x}/driver')}",
        f"ext_range_assumed={sdt.EXT_RANGE}",
        f"grid_repeats={GRID_REPEATS}",
        f"sweep={SWEEP_START_mC}..{SWEEP_STOP_mC} step {SWEEP_STEP_mC}",
        f"latency_sample_interval_s={LATENCY_SAMPLE_S}",
        f"latency_transitions={len(LATENCY_SEQUENCE_mC)}",
    ]
    (OUT / "meta.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"寫出 {OUT / 'meta.txt'}")


def write_csv(name: str, rows: list[dict]) -> None:
    path = OUT / name
    # ⚠️ lineterminator 一定要顯式指定。csv 模組**預設是 CRLF**（RFC 4180），
    #    而這個 repo 的 .gitattributes 是 `* text=auto eol=lf` ——
    #    兩者打架的結果是工作目錄與 index 永遠差一個換行符，
    #    `git status` 乾淨但 `git diff` 一片紅。C++ 那側產的 CSV 本來就是 LF。
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"寫出 {path}（{len(rows)} 列）")


# ═══════════════════════════════════════════════════════════════════════
#  自我檢查（--check）—— 讀 repo 裡的 CSV，不需要 BMC
# ═══════════════════════════════════════════════════════════════════════


def _load(name: str) -> list[dict]:
    path = OUT / name
    if not path.exists():
        raise SystemExit(f"找不到 {path} —— 先跑一次 python bench/exp04_injection.py")
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def check_lsb_from_sweep() -> tuple[bool, str]:
    """① LSB = 0.0625 °C —— 從**階梯本身**量，不是從一個點推。"""
    rows = _load("sweep.csv")
    levels: list[int] = []
    for row in rows:
        value = int(row["hwmon_mC"])
        if not levels or value != levels[-1]:
            levels.append(value)
    gaps = [b - a for a, b in zip(levels, levels[1:], strict=False)]
    if len(levels) < 5:
        return False, f"只看到 {len(levels)} 個不同的階，掃描範圍太窄，量不出解析度"
    bad = [g for g in gaps if g not in (62, 63)]
    if bad:
        return False, f"階距出現 {sorted(set(bad))}，不是 62/63 —— LSB 不是 1/16 °C"
    return True, (f"{len(levels)} 個相異階，階距 {sorted(set(gaps))} m°C "
                  f"→ LSB = 62.5 m°C = 0.0625 °C")


def check_grid_bias() -> tuple[bool, str]:
    """② 落在格點上的要求值一律低整整一格 —— 系統性偏壓，不是量化。"""
    rows = _load("grid.csv")
    biases = {int(row["bias_mC"]) for row in rows}
    if biases != {-62}:
        return False, f"偏壓不是一致的 −62：看到 {sorted(biases)}"
    return True, (f"{len(rows)} 個格點觀測（{GRID_REPEATS} 次重複）全部 −62 m°C "
                  f"= 整整一個 LSB，零例外")


def check_predictor() -> tuple[bool, str]:
    """③ 三段轉換的預測式命中每一個實測點。

    這一條才是把「我讀懂了那條路徑」變成可查證的東西。
    ①② 只說明「有量化、有偏壓」；③ 說明「我算得出來是多少」。
    """
    problems = []
    total = 0
    for name, actual_key in (("sweep.csv", "hwmon_mC"),
                             ("grid.csv", "hwmon_mC")):
        for row in _load(name):
            total += 1
            predicted = sdt.expected_hwmon_mC(int(row["requested_mC"]))
            if predicted != int(row[actual_key]):
                problems.append(
                    f"{name} requested={row['requested_mC']} "
                    f"predicted={predicted} actual={row[actual_key]}")
    if problems:
        return False, f"{len(problems)}/{total} 個點對不上：" + "; ".join(problems[:5])
    return True, f"{total} 個實測點全部命中，零誤差"


def latency_summary() -> tuple[list[float], list[dict]]:
    """把 latency.csv 的取樣點整理成「每次轉換的首次可見延遲」。"""
    rows = _load("latency.csv")
    by_transition: dict[str, list[dict]] = {}
    for row in rows:
        by_transition.setdefault(row["transition"], []).append(row)

    first_seen: list[float] = []
    stale_rows: list[dict] = []
    for _, samples in sorted(by_transition.items(), key=lambda kv: int(kv[0])):
        target = int(samples[0]["expected_mC"])
        old = int(samples[0]["from_mC"])
        if target == old:
            continue  # 沒有真的換值，這次轉換量不到延遲
        hit = next((s for s in samples if int(s["value_mC"]) == target), None)
        if hit is None:
            continue
        first_seen.append(float(hit["elapsed_ms"]))
        stale_rows += [s for s in samples
                       if float(s["elapsed_ms"]) < float(hit["elapsed_ms"])]
    return first_seen, stale_rows


def check_latency() -> tuple[bool, str]:
    """④ 注入之後新值不是立刻可見 —— 量出可見延遲。

    ★ 這一條是給 W6/W7 的護欄，而且它給的是**數字**不是是非題：
      host 驅動的閉環如果注入後立刻讀，整條迴路會慢一拍，
      而那會被誤判成額外的死區 θ —— 剛好就是 W4 花一天量出來的那個量。

    ⚠️ 這條結論**取決於取樣速度**。用「每次開一條新 ssh」（約 400 ms 一次）
       去量，會得到「沒有延遲」的錯誤結論。取樣間隔必須遠小於 driver 的
       500 ms 快取窗口 —— 見 BmcSampler 的註解。
    """
    first_seen, stale_rows = latency_summary()
    if len(first_seen) < 5:
        return False, f"只有 {len(first_seen)} 次有效轉換，協定要求至少 5 次"
    if not stale_rows:
        return False, ("每一次注入都立刻可見 —— 取樣可能太慢（每個點都晚於快取窗口），"
                       "或 driver 換了行為。這條結論要重量")
    lo, hi = min(first_seen), max(first_seen)
    ordered = sorted(first_seen)
    median = ordered[len(ordered) // 2]
    return True, (f"{len(first_seen)} 次轉換，首次可見延遲中位數 {median:.0f} ms "
                  f"（範圍 {lo:.0f}~{hi:.0f} ms）；"
                  f"這段期間共有 {len(stale_rows)} 個取樣點讀到的仍是舊值")


def check_determinism() -> tuple[bool, str]:
    """⑤ 重複 5 次完全相同 —— 這條路徑是決定性的。

    協定要求「至少 5 次重複」。對類比量測那是為了報中位數與範圍；
    對這條**數位**路徑，重複的意義是證明它沒有隨機性 ——
    所以報的是「五次逐點相同」，那比一個中位數更強。
    """
    rows = _load("grid.csv")
    by_repeat: dict[str, dict[str, str]] = {}
    for row in rows:
        by_repeat.setdefault(row["repeat"], {})[row["requested_mC"]] = row["hwmon_mC"]
    repeats = sorted(by_repeat)
    if len(repeats) < 5:
        return False, f"只有 {len(repeats)} 次重複，協定要求至少 5 次"
    first = by_repeat[repeats[0]]
    for r in repeats[1:]:
        if by_repeat[r] != first:
            return False, f"第 {r} 次重複與第 {repeats[0]} 次不同 —— 這條路徑不是決定性的"
    return True, f"{len(repeats)} 次重複逐點完全相同"


CHECKS = [
    ("① 解析度來自階梯，不是單點", check_lsb_from_sweep),
    ("② 格點上的偏壓是系統性的", check_grid_bias),
    ("③ 三段轉換預測式命中實測", check_predictor),
    ("④ 注入到可見有量得到的延遲", check_latency),
    ("⑤ 重複 5 次完全相同", check_determinism),
]


def run_checks() -> int:
    failed = 0
    print("exp04 自我檢查（讀 bench/data/exp04_injection/，不需要 BMC）")
    print("-" * 72)
    for label, fn in CHECKS:
        ok, detail = fn()
        print(f"{'✅' if ok else '❌'} {label}\n     {detail}")
        failed += 0 if ok else 1
    print("-" * 72)
    if failed:
        print(f"⚠️ {failed} 條自我檢查沒過。")
        return 1
    print("全部通過。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="只驗證 repo 裡已有的 CSV（不需要 BMC）")
    args = ap.parse_args()

    if args.check:
        return run_checks()

    OUT.mkdir(parents=True, exist_ok=True)
    qmp, path = open_chip()
    hwmon_path = resolve_hwmon_path()
    print(f"BMC hwmon: {hwmon_path}")

    with BmcSampler(hwmon_path) as sampler:
        print("== grid：正好落在 1/16 格點上的要求值 ==")
        write_csv("grid.csv", run_grid(qmp, path, sampler))
        print("== sweep：細掃，數出階梯 ==")
        write_csv("sweep.csv", run_sweep(qmp, path, sampler))
        print("== latency：注入到可見要多久 ==")
        write_csv("latency.csv", run_latency(qmp, path, sampler))
    write_meta(qmp, hwmon_path)

    print()
    return run_checks()


if __name__ == "__main__":
    sys.exit(main())
