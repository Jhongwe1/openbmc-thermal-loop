"""exp06:swampd 的兩個時間常數 —— 把「串級」從讀來的知識變成量到的數字。

⚠️ 編號與計畫不同。計畫的 exp06 是「參數掃描(Kp/Ki)」,但那正是 exp05 做的事
   (三組 λ 就是三組 Kc/Ki)。exp06 改成串級時間常數的實測 ——
   那是 W6 真正缺的那塊,也是 W7 Fig 3「L2 那一半」的前提。

實驗協定(七欄,定義見 docs/measurement.md)
--------------------------------------------------
假設     : swampd 是串級控制器。內圈(風扇 PID)每 `cycleIntervalTimeMS = 100` ms
           跑一次,外圈(熱 PID)每 `updateThermalsTimeMS = 1000` ms 跑一次。
自變因   : 無 —— 這是**特性量測**,不是對照實驗。量的是這個 daemon 的固有節奏。
控制變因 : 同一次開機、同一份設定檔(config.tuned.json)、
           注入溫度固定不變(讓溫度本身不成為變因)
應變因   : ① zone_0.log 相鄰行的時間戳差(內圈週期)
           ② zone_0.log 的 `setpt` 欄變化的間隔(外圈週期)
重複     : 單次長取樣(數千筆),報**中位數與分位數**而不是平均 ——
           理由見下面「為什麼不報平均」
原始資料 : bench/data/exp06_cascade/zone_0.log、pidcore.die0、meta.txt
重跑     : python bench/exp06_cascade.py --collect   (需要 QEMU + BMC)
           python bench/exp06_cascade.py --check     (只讀 repo 裡的資料)

★★ 這個實驗最重要的一件事:量測方法本身要先驗證
------------------------------------------------
計畫寫的量法是「`pidcore.*` 裡 setpoint 變化的間隔」。**那個方法是錯的。**

上游 `pid/ec/logging.cpp` 的 `LogContext()`::

    static constexpr int logThrottle = 60 * 1000;
    ...
    if (pidLog.lastLog == zero)            shouldLog = true;   // 第一次
    else if (since >= logThrottle)         shouldLog = true;   // 節流到期
    if (pidLog.lastContext != coreContext) shouldLog = true;   // 內容變了
    if (!shouldLog) return;

也就是 `pidcore.*` 是**「內容變了 OR 距上次 60 秒」**才寫一筆,**不是等間隔取樣**。
靜態情況下量到的是 60 秒(實測 60013~67569 ms),與迴路週期無關。

對照:`zone_0.log` 由 `DbusPidZone::writeLog()` 直接寫,**沒有節流** ——
所以週期要從它量。**同一個 daemon 的兩份 log,兩種寫入策略。**

⚠️ 這件事對 W7 有直接後果:Fig 3 第三面板(積分軌跡)吃的就是 `pidcore.*`。
   畫之前要先確認每個週期都有點,否則「值不再變化」的那一段
   ——**正是 anti-windup 生效之後的那一段**—— 會被壓縮成幾個點。

為什麼不報平均
--------------
同一批資料:中位數 100 ms、平均 122.8 ms、最大值 7832 ms。
長尾來自 QEMU 的排程抖動(整台虛擬機被 host 暫停)。
**只報平均會得到一個錯 23% 的數字,而且錯的方向是「看起來比較慢」。**
"""

import argparse
import json
import pathlib
import statistics
import subprocess
import sys

DATA = pathlib.Path("bench/data/exp06_cascade")

#: 注入的溫度 (°C)。要**高於** setpoint,誤差才是負的、積分才會往正的累積
#: (temp 型別用負係數)。85 °C 讓 |error| = 20,積分累積得夠快,
#: 一分鐘就看得出趨勢,而且離 tmp421 的上限還很遠。
INJECT_C = 85.0

#: 取樣時間 (s)。內圈 100 ms → 約 6000 筆;外圈 1 s → 約 600 筆。
COLLECT_S = 90

SSH_OPTS = ["-p", "2222", "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR"]


# ═══════════════════════════════════════════════════════════════════
#  分析（純函式，不碰 BMC —— 所以測得到）
# ═══════════════════════════════════════════════════════════════════


def parse_zone_log(text: str) -> list[dict]:
    """把 zone_0.log 解析成一串 dict。

    實際格式(2026-08-11 從 BMC 上抓的,計畫沒有寫,要自己看)::

        epoch_ms,setpt,requester,fan0,fan0_raw,fan0_pwm,fan0_pwm_raw,die0,die0_raw,failsafe

    ⚠️ **最後一行常常是截斷的** —— log 還在寫,而 `_log << std::endl` 之前
       已經有部分內容進了檔案。不濾掉的話最後一筆的時間戳差會是一個假的巨大值,
       而它剛好會落在「最大值」那一格上。
    """
    lines = text.splitlines()
    if not lines:
        raise ValueError("空的 zone log")
    header = lines[0].split(",")
    if header[0] != "epoch_ms":
        raise ValueError(f"zone log 的第一欄應該是 epoch_ms,實際是 {header[0]!r}")

    rows = []
    for line in lines[1:]:
        fields = line.split(",")
        if len(fields) != len(header):        # 截斷的行
            continue
        try:
            row = {"epoch_ms": int(fields[0]), "setpt": float(fields[1])}
        except ValueError:
            continue
        row["requester"] = fields[2]
        rows.append(row)
    return rows


def _quantiles(values: list[float]) -> dict:
    """中位數與分位數。**不報平均** —— 理由見模組 docstring。"""
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        raise ValueError("沒有樣本可以統計")

    def at(fraction: float) -> float:
        return ordered[min(n - 1, max(0, int(round(fraction * (n - 1)))))]

    return {
        "n": n,
        "median": statistics.median(ordered),
        "p05": at(0.05),
        "p95": at(0.95),
        "min": ordered[0],
        "max": ordered[-1],
        # 平均也記下來，但只是為了**展示它有多誤導**，不拿它下結論
        "mean_for_contrast": statistics.fmean(ordered),
    }


def fan_cycle_ms(rows: list[dict]) -> dict:
    """內圈(風扇迴路)週期:zone_0.log 相鄰行的時間戳差。

    成立的前提是「這份 log 每個 cycle 都寫一筆」——
    `DbusPidZone::writeLog()` 沒有節流,所以成立。
    """
    diffs = [b["epoch_ms"] - a["epoch_ms"] for a, b in zip(rows, rows[1:],
                                                           strict=False)]
    return _quantiles([d for d in diffs if d > 0])


def thermal_update_ms(rows: list[dict]) -> dict:
    """外圈(熱迴路)週期:`setpt` 欄**變化**的時間間隔。

    ★ 為什麼看 `setpt` 而不是 `die0`
      `setpt` 是 zone 的 `_maximumSetPoint`,由**熱 PID 的輸出**決定,
      所以它變化的節奏就是熱 PID 被呼叫的節奏。
      `die0` 欄反映的是 D-Bus 感測器的更新率,那是**第三個**時間尺度。

    ⚠️ 這個量法要求 setpt **真的在變**。溫度靜止 + 輸出被箝在 outLim 上時,
       setpt 一動也不動,量出來會是「沒有樣本」而不是一個錯的數字 ——
       那是刻意的:寧可回報量不到,也不要回報一個像樣的錯數字。
    """
    changes = []
    last_value = rows[0]["setpt"]
    last_time = rows[0]["epoch_ms"]
    for row in rows[1:]:
        if row["setpt"] != last_value:
            changes.append(row["epoch_ms"] - last_time)
            last_value = row["setpt"]
            last_time = row["epoch_ms"]
    if len(changes) < 2:
        raise ValueError(
            f"setpt 只變了 {len(changes)} 次 —— 量不到外圈週期。"
            "多半是熱 PID 的輸出被箝在 outLim 上不動了(積分已飽和),"
            "或是溫度沒有注入。先看 pidcore.die0 的 output 欄。"
        )
    return _quantiles(changes)


def analyse(zone_text: str) -> dict:
    rows = parse_zone_log(zone_text)
    return {
        "rows": len(rows),
        "span_s": (rows[-1]["epoch_ms"] - rows[0]["epoch_ms"]) / 1000.0,
        "fan_cycle_ms": fan_cycle_ms(rows),
        "thermal_update_ms": thermal_update_ms(rows),
    }


# ═══════════════════════════════════════════════════════════════════
#  採集（需要 QEMU + BMC）
# ═══════════════════════════════════════════════════════════════════


def ssh(command: str) -> str:
    proc = subprocess.run(
        ["sshpass", "-p", "0penBmc", "ssh", *SSH_OPTS, "root@127.0.0.1",
         command],
        capture_output=True, text=True, check=True)
    return proc.stdout


def collect(out_dir: pathlib.Path) -> None:
    """部署整定過的設定、注入溫度、取樣、把原始 log 抓回來。"""
    out_dir.mkdir(parents=True, exist_ok=True)

    print("→ 部署 config.tuned.json")
    subprocess.run(
        ["sshpass", "-p", "0penBmc", "scp", "-P", "2222",
         "-o", "StrictHostKeyChecking=no",
         "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR",
         "config/swampd/config.tuned.json",
         "root@127.0.0.1:/etc/thermal-loop/config.json"], check=True)

    print(f"→ 注入 {INJECT_C} °C（--verify 會等到 BMC 真的看得到）")
    subprocess.run([sys.executable, "tools/set_die_temp.py", str(INJECT_C),
                    "--verify"], check=True)

    print("→ 重啟 swampd（log 會重新開檔）")
    ssh("systemctl restart phosphor-pid-control")

    print(f"→ 取樣 {COLLECT_S} s")
    ssh(f"sleep {COLLECT_S}")

    for name in ("zone_0.log", "pidcore.die0", "pidcoeffs.die0"):
        print(f"→ 取回 {name}")
        (out_dir / name).write_text(ssh(f"cat /tmp/pidlog/{name}"))

    meta = {
        "experiment": "exp06_cascade",
        "inject_c": INJECT_C,
        "collect_s": COLLECT_S,
        "config": "config/swampd/config.tuned.json",
        "swampd_version": ssh(
            "rpm -q phosphor-pid-control 2>/dev/null || "
            "opkg list-installed 2>/dev/null | grep -i phosphor-pid-control || "
            "echo unknown").strip(),
        "upstream_constants": {
            "cycleIntervalTimeMS": 100,
            "updateThermalsTimeMS": 1000,
            "logThrottle_ms": 60000,
            "source": "phosphor-pid-control @ f6d4cb9, pid/conf.hpp 與 "
                      "pid/ec/logging.cpp",
        },
        "repo_commit": subprocess.getoutput("git rev-parse --short HEAD"),
    }
    (out_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n")
    print(f"→ 寫入 {out_dir}/meta.json")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--collect", action="store_true",
                    help="重新採集（需要 QEMU 上的 BMC 跑著）")
    ap.add_argument("--check", action="store_true",
                    help="只分析 repo 裡已經有的資料（不需要 BMC，進得了 CI）")
    ap.add_argument("--data", default=str(DATA))
    a = ap.parse_args()

    if not a.collect and not a.check:
        ap.error("要給 --collect 或 --check")

    out_dir = pathlib.Path(a.data)
    if a.collect:
        collect(out_dir)

    zone = out_dir / "zone_0.log"
    if not zone.exists():
        raise SystemExit(f"找不到 {zone}，先跑 --collect")

    result = analyse(zone.read_text())
    print()
    print(f"樣本 {result['rows']} 筆，涵蓋 {result['span_s']:.1f} s")
    for label, key, expected in (
            ("內圈 fan cycle", "fan_cycle_ms", 100),
            ("外圈 thermal update", "thermal_update_ms", 1000)):
        s = result[key]
        print(f"{label:22s} median={s['median']:8.1f} ms  "
              f"p05={s['p05']:7.1f}  p95={s['p95']:7.1f}  "
              f"min={s['min']:6.0f}  max={s['max']:7.0f}  n={s['n']:5d}   "
              f"[上游常數 {expected} ms]")
        print(f"{'':22s} （平均 {s['mean_for_contrast']:.1f} ms —— "
              f"與中位數差 {abs(s['mean_for_contrast'] - s['median']):.1f} ms，"
              f"這就是不報平均的理由）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
