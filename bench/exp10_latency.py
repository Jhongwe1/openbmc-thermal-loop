"""exp10:端到端延遲 —— 一個溫度值從 QMP 注入到各層生效要多久(route (b′), L3)。

⚠️ 編號:計畫叫它 exp06_latency,但 exp06 已被串級實測佔用(W6);
   實驗一律按**執行順序**取號(§4.0)。exp09 docstring 曾寫「L1/L2 對照
   順延 exp10」—— 該對照尚未執行,依同一規則輪到時取 exp11。

實驗協定(七欄,定義見 docs/measurement.md)
--------------------------------------------------
假設     : 計畫預測「④ D-Bus→Redfish 最慢(ObjectMapper + 組 JSON)」;
           我的預測相反:「①(注入→D-Bus)最慢,因為疊了 hwmon 快取
           (HZ/2 = 500 ms)與 dbus-sensors 輪詢兩層取樣」。
           ★ 結果:**兩個預測都無法在本 rig 判定** —— guest 時鐘每
           ~40 s 跳步 +7.6 s(見下),跨時鐘域的 ①④ 無法以小於跳步
           幅度的精度分離。能精確量的是:全程(host 域)、②、③
           (皆單一時鐘域)。誠實記錄勝於硬給數字。
自變因   : 無(觀測性實驗)。注入電平 90 ↔ 55 °C 交替只是為了讓每段
           都有可觀測的跳變:90 °C 時外圈 P 項 = −220.28×(65−90) =
           +5507 RPM,單獨越過 outLim_min=3000 的箝制 → setpt/PWM
           立刻動;55 °C 收回箝制。**先算作用窗再選電平** ——
           70 °C 只有 P=1101,爬出箝制要等積分堆 ~76 s,什麼都量不到
           (W5「成功地什麼都沒測到」+ W8 死旋鈕,同一個教訓)。
控制變因 : config = config/swampd/config.tuned.json **原樣部署**
           (本腳本 md5 驗證後才跑)、swampd 未修改二進位 @ c5e5955、
           QEMU bletchley-bmc(11.0.1)、量測期間 host 淨空
           (Robot / meson 都不得跑 —— 上一輪就是被自己的編譯風暴
           污染,健康檢查當場抓包)。
應變因   : total  t_redfish − t_inject   注入 → host 從 Redfish 讀到
                                          (純 host 域,**最可靠**)
           ②     t_zone − t_dbus        D-Bus 訊號 → swampd zone log
                                          吃到(純 BMC 域)
           ③     t_pwm − t_setpt        外圈新輸出 → PWM 欄變
                                          (純 BMC 域)
           ①+④ 合計 = total − (②+③)/rate(rate = guest 時鐘速率,
           見 meta),只報合計與組成,不硬拆。
重複     : 32 次(90/55 交替);**前 2 次是暖身,事前宣告排除統計**;
           guest 時鐘跳步命中的 rep 逐個拒收(理由入 meta),
           有效 rep < MIN_VALID(25)才整 run 作廢 —— 門檻寫在
           採資料之前,不是看完數字才挑。
原始資料 : bench/data/exp10_latency/{events.csv, streams/*, exp10_meta.json}
產圖     : 無(表格型結果 → docs/measurement.md)

★ 時鐘紀律 v3(v1/v2 的地雷見 LOG 2026-08-12 三則)
--------------------------------------------------
v1:四事件全蓋 host 時鐘(串流到 host 打時戳)→ 被 ssh 鏈的 ~8 KB
    塊緩衝推翻(zone 行 15~18 s 一批到,-tt/stdbuf/免密都治不動)。
v2:時鐘搬回源頭(zone 自帶 epoch_ms、busctl 自帶 µs Timestamp),
    以「到達−源頭」低分位數橋接兩域 → 被 guest 時鐘的**鋸齒**推翻:
    TCG guest 錶以 ~0.8× 速率行走,每 ~40 s 被拉回牆鐘(+7.6 s)。
    以單一 offset 閘門跨域配對,會把事件錯配到 16 s 後的下一個
    同電平 rep(實測 seg1 = +12.5 s、seg2 < 0 的病理數字)。
v3(本版):**配對不用時鐘,用序列索引** —— 電平 90/55 嚴格交替,
    D-Bus / zone / Redfish 三條轉換序列各自時間單調,第 i 個 rep
    恰對第 i 個轉換,零歧義;三序列長度與電平模式都強制驗證。
    時鐘只決定「段差的單位」:total 是 host 秒(牆鐘真值);
    ② ③ 是 guest 秒(swampd 的週期、timeout 都定義在這個錶上,
    這正是機制的原生單位);①④ 不再單獨宣稱。
    host 到達時戳只剩傳輸診斷用途;鋸齒特徵(次數/幅度/間隔)與
    guest 時鐘速率量化進 meta。

量具健康(rep 有效性,exp09 家族):
  (a) rep 窗內 zone 的 BMC epoch 連續性 ≤ 0.5 s —— 時鐘跳步/停擺;
  (b) rep 窗內 Redfish 輪詢的 host 節奏 ≤ 2.5 s(錨定 t0 前最後一筆,
      防「窗頭的洞」盲區)—— host/WSL 凍結;
  (c) 注入節奏 ≤ 週期 + 2 s —— 注入迴圈自身凍結。

★ 事件偵測 = expected_hwmon_mC() 預測值的精確比對(±0.02 °C)
------------------------------------------------------------
不是「值有變就算」:量的是**何時**,預測的是**什麼值**,兩者正交,
不構成同義反覆;比對值錯了會大聲失敗而不是給出偏掉的延遲。
±0.02 °C < 半個 LSB(0.03125),所以「拿注入值而不是量化預測值來比」
這種錯一定會被抓到(mutation T4)。
"""

import argparse
import base64
import hashlib
import http.client
import json
import pathlib
import re
import ssl
import statistics
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone

REPO = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
from set_die_temp import Qmp, expected_hwmon_mC, find_tmp421  # noqa: E402

OUT_DIR = REPO / "bench/data/exp10_latency"
CONF_SRC = REPO / "config/swampd/config.tuned.json"
CONF_DST = "/etc/thermal-loop/config.json"

BMC = dict(host="127.0.0.1", ssh_port="2222", https_port="2443",
           user="root", password="0penBmc")

REPS = 32
WARMUP_REPS = 2          # 事前宣告:前 2 次(90 與 55 各一)不進統計
MIN_VALID = 25           # 事前宣告:有效 rep(暖身除外)少於此數 → run 無效
PERIOD_S = 8.0           # 全鏈 ~3 s 內收斂,8 s 給模擬器留裕度
LEVELS_C = (90.0, 55.0)  # 偶數 rep 打 90、奇數打 55(理由見 docstring)
#: 兩個電平經注入路徑量化後在 BMC 上的實際值 —— 序列比對用它,不用 90/55。
EXPECTED_C = tuple(expected_hwmon_mC(int(round(c * 1000))) / 1000.0
                   for c in LEVELS_C)
MATCH_EPS_C = 0.02       # < LSB/2 = 0.03125,見 docstring
MAX_GAP_S = 0.5          # zone 的 BMC epoch 行距上限(跳步/停擺偵測)
REDFISH_GAP_S = 2.5      # rep 窗內 Redfish host 節奏上限(host 凍結偵測)

DIE0_DBUS_PATH = "/xyz/openbmc_project/sensors/temperature/die0"
REDFISH_DIE0 = "/redfish/v1/Chassis/Thermal_Loop_Demo/Sensors/temperature_die0"

SSH_BASE = ["sshpass", "-p", BMC["password"], "ssh",
            "-o", "StrictHostKeyChecking=no",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=ERROR",
            "-p", BMC["ssh_port"], f"{BMC['user']}@{BMC['host']}"]


def ssh_run(cmd: str) -> str:
    proc = subprocess.run(SSH_BASE + [cmd], capture_output=True, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"ssh 失敗({proc.returncode}):{cmd}\n{proc.stderr}")
    return proc.stdout


def deploy_tuned_config() -> str:
    """把 repo 的 tuned config 原樣部署到 BMC,md5 驗證,必要時重啟 swampd。

    「量的是哪份設定」必須是機器驗證的事實:live config 少了 W7 的
    fan0 feedFwdGainCoeff(1/150)的話,PWM 永遠貼在 30% 不動,
    ③ 段會「成功地什麼都量不到」。
    """
    want = hashlib.md5(CONF_SRC.read_bytes()).hexdigest()
    have = ssh_run(f"md5sum {CONF_DST} 2>/dev/null || true").split()
    if have and have[0] == want:
        print(f"config 已是 tuned 版(md5 {want[:8]}…),不動")
        return want
    print(f"部署 {CONF_SRC.name} → BMC {CONF_DST}(md5 {want[:8]}…)")
    scp = ["sshpass", "-p", BMC["password"], "scp",
           "-o", "StrictHostKeyChecking=no",
           "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR",
           "-P", BMC["ssh_port"], str(CONF_SRC),
           f"{BMC['user']}@{BMC['host']}:{CONF_DST}"]
    subprocess.run(scp, check=True)
    got = ssh_run(f"md5sum {CONF_DST}").split()[0]
    if got != want:
        raise SystemExit(f"部署後 md5 不符:{got} != {want}")
    ssh_run("systemctl restart phosphor-pid-control")
    deadline = time.time() + 30
    while time.time() < deadline:
        if "active" == ssh_run(
                "systemctl is-active phosphor-pid-control || true").strip():
            print("swampd 重啟完成")
            return want
        time.sleep(1)
    raise SystemExit("swampd 重啟後 30 s 內沒有回到 active")


#: pty(-tt)讓 systemd 系工具開彩色輸出,跳脫碼會插在「DOUBLE 」與數字
#: 之間害 regex 撲空 —— 第一次收集就是這樣整組空手而回(LOG 2026-08-12)。
#: 遠端已加 SYSTEMD_COLORS=0 治本;這裡再剝一層是防別的工具同款行為。
_ANSI = re.compile(r"\x1b\[[0-9;]*m")


class Stream:
    """一條持久 ssh 串流。到達時戳只當**傳輸診斷**用 —— ssh 鏈對低流量
    串流做 ~8 KB 塊緩衝(批次 15~18 s,LOG 2026-08-12),事件時刻一律
    取 payload 自帶的源頭時戳。"""

    def __init__(self, name: str, remote_cmd: str):
        self.name = name
        self.rows: list[tuple[float, str]] = []
        self._lock = threading.Lock()
        # -tt:BusyBox tail / busctl 對非 tty stdout 整塊緩衝,沒有 pty
        # 的話低流量串流會**整段沉默**(變體 C/D 實測 0 行)。
        self.proc = subprocess.Popen(
            SSH_BASE[:-1] + ["-tt", SSH_BASE[-1], remote_cmd],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        self.thread = threading.Thread(target=self._pump, daemon=True)
        self.thread.start()

    def _pump(self):
        for line in self.proc.stdout:
            now = time.time()
            with self._lock:
                self.rows.append((now, _ANSI.sub("", line).rstrip("\r\n")))

    def snapshot(self):
        with self._lock:
            return list(self.rows)

    def close(self):
        self.proc.terminate()


class RedfishPoller:
    """host 端 keep-alive 輪詢:每筆記 (t_before, t_after, reading)。

    單支 curl 每次冷握手 ~1 s;http.client 重用連線後單次快得多,
    輪詢解析度才追得上事件的尺度。事件時刻取 t_after(讀到回應的
    時刻),解析度 = 相鄰 t_after 間距,寫進 meta 供判讀。它同時是
    host 凍結的偵測器 —— 整條在 host 行程內,ssh 批次污染不到它。"""

    def __init__(self):
        self.rows: list[tuple[float, float, float]] = []
        self._lock = threading.Lock()
        self._stop = threading.Event()
        auth = base64.b64encode(
            f"{BMC['user']}:{BMC['password']}".encode()).decode()
        self._headers = {"Authorization": f"Basic {auth}"}
        self._ctx = ssl.create_default_context()
        self._ctx.check_hostname = False
        self._ctx.verify_mode = ssl.CERT_NONE
        self.thread = threading.Thread(target=self._pump, daemon=True)
        self.thread.start()

    def _pump(self):
        conn = None
        while not self._stop.is_set():
            try:
                if conn is None:
                    conn = http.client.HTTPSConnection(
                        BMC["host"], int(BMC["https_port"]),
                        timeout=5, context=self._ctx)
                t0 = time.time()
                conn.request("GET", REDFISH_DIE0, headers=self._headers)
                body = conn.getresponse().read()
                t1 = time.time()
                reading = json.loads(body).get("Reading")
                if reading is not None:
                    with self._lock:
                        self.rows.append((t0, t1, float(reading)))
            except (OSError, http.client.HTTPException,
                    json.JSONDecodeError, ValueError):
                if conn is not None:
                    conn.close()
                conn = None
                time.sleep(0.2)
            time.sleep(0.05)

    def snapshot(self):
        with self._lock:
            return list(self.rows)

    def close(self):
        self._stop.set()


# ── 分析(純函式,不碰網路;mutation T1~T6 的守備範圍)────────────────

_FLOAT = re.compile(r"DOUBLE (-?\d+(?:\.\d+)?)")
_TS = re.compile(r'Timestamp="([^"]+) UTC"')

#: zone_0.log 欄位(W2 D3 實測,test_exp09 亦用):
ZONE_COLS = ("epoch_ms", "setpt", "requester", "fan0", "fan0_raw",
             "fan0_pwm", "fan0_pwm_raw", "die0", "die0_raw", "failsafe")


def parse_busctl_ts(text: str) -> float:
    """busctl 訊息頭的 `Timestamp="Tue 2026-08-11 20:34:33.322285 UTC"`
    → epoch 秒(BMC 時鐘,µs 解析度)。"""
    return datetime.strptime(text, "%a %Y-%m-%d %H:%M:%S.%f").replace(
        tzinfo=timezone.utc).timestamp()


def parse_zone_line(line: str) -> dict | None:
    parts = line.split(",")
    if len(parts) != len(ZONE_COLS) or not parts[0].isdigit():
        return None
    row = dict(zip(ZONE_COLS, parts, strict=True))
    try:
        return {"epoch_ms": float(row["epoch_ms"]),
                "setpt": float(row["setpt"]),
                "fan0_pwm": float(row["fan0_pwm"]),
                "die0": float(row["die0"])}
    except ValueError:
        return None


def dbus_value_events(dbus_rows) -> list[tuple[float, float, float]]:
    """busctl monitor 串流 → [(bmc_ts, host_arrival, value), …]。

    訊息頭行帶 Timestamp、值在後續的 DOUBLE 行 —— 以「最後看到的頭」
    配對同一則訊息內的值。"""
    events = []
    cur_ts = None
    for arr, ln in dbus_rows:
        m = _TS.search(ln)
        if m:
            cur_ts = parse_busctl_ts(m.group(1))
            continue
        if cur_ts is None:
            continue
        for v in _FLOAT.findall(ln):
            events.append((cur_ts, arr, float(v)))
    return events


def level_of(value: float) -> float | None:
    """值屬於哪個量化電平(EXPECTED_C 之一),都不是回 None。"""
    for exp_c in EXPECTED_C:
        if abs(value - exp_c) <= MATCH_EPS_C:
            return exp_c
    return None


def build_sequences(dbus_events, zrows, redfish):
    """三條「電平轉換」序列 —— 配對靠**索引**,不靠時鐘。

    guest 時鐘的鋸齒(每 ~40 s 跳步 +7.6 s)讓任何「跨時鐘域的
    大於/小於閘門」都不可靠(v2 把事件錯配到 16 s 後的下一個同電平
    rep)。但電平 90/55 嚴格交替 → 三條序列各自時間單調 → 第 i 個
    rep 恰對第 i 個轉換,零歧義。長度與電平模式由 validate_sequences
    強制檢查。回傳:
      dbus_seq: [(exp_c, bmc_ts)]      zone_seq: [(exp_c, row_index)]
      rf_seq:   [(exp_c, t_after)]
    """
    dbus_seq = []
    last = None
    for ts, _arr, v in dbus_events:
        lev = level_of(v)
        if lev is None:
            continue
        if lev != last:
            dbus_seq.append((lev, ts))
            last = lev

    zone_seq = []
    last = None
    for k, (_arr, r) in enumerate(zrows):
        lev = level_of(r["die0"])
        if lev is None:
            last = None
            continue
        if lev != last:
            zone_seq.append((lev, k))
            last = lev

    rf_seq = []
    last = None
    for _t0, t1, v in redfish:
        lev = level_of(v)
        if lev is None:
            last = None
            continue
        if lev != last:
            rf_seq.append((lev, t1))
            last = lev

    return dbus_seq, zone_seq, rf_seq


def align_sequence(name: str, seq, want, min_match: int) -> tuple[int, int]:
    """在 seq 的電平序列裡找 want 的**連續前綴對齊**,回傳 (起點 j, 對齊長度 k)。

    容忍兩種真實現象、拒絕其它一切:
      * **legacy 頭**(j > 0):上一次中止的 run 留在 zone log 的舊高原
        —— swampd 的 ofstream 也有 ~8 KB 緩衝,tail 掛上時檔案 EOF
        落後真實 ~16 s,舊資料會流進本次捕捉。
      * **截斷尾**(k < len(want)):關通道時最後一批還在緩衝裡 ——
        尾端缺的 rep 由呼叫端逐個判 invalid,不硬湊。
    中段錯位(k 停在中間但 seq 後面還有東西)= 配對失敗,大聲死。
    """
    got = [lev for lev, _ in seq]
    best_j, best_k = -1, -1
    for j in range(len(got)):
        k = 0
        while (k < len(want) and j + k < len(got)
               and got[j + k] == want[k]):
            k += 1
        if k > best_k:
            best_j, best_k = j, k
    if best_k < min_match:
        raise SystemExit(
            f"{name} 序列對不上注入序列(最長對齊只有 {best_k},"
            f"需要 ≥ {min_match};序列長 {len(got)},前 6 個:{got[:6]} "
            f"vs {want[:6]})—— 配對失敗,不硬湊")
    if best_j + best_k != len(got):
        raise SystemExit(
            f"{name} 序列在對齊區之後還有 {len(got) - best_j - best_k} 個"
            f"多餘轉換 —— 中段錯位,不硬湊")
    return best_j, best_k


def validate_sequences(reps, dbus_seq, zone_seq, rf_seq) -> dict:
    """對齊三條序列;回傳每條的 (j, k)。"""
    want = [level_of(r["expected_c"]) for r in reps]
    if None in want:
        raise SystemExit("rep 的 expected_c 不在 EXPECTED_C 裡 —— 資料壞了")
    min_match = min(MIN_VALID + WARMUP_REPS, len(want))
    return {
        "dbus": align_sequence("dbus", dbus_seq, want, min_match),
        "zone": align_sequence("zone", zone_seq, want, min_match),
        "redfish": align_sequence("redfish", rf_seq, want, min_match),
    }


def detect_rep_events(rep: dict, idx: int, seqs, aligns, zrows,
                      redfish) -> dict:
    """第 idx 個 rep 的事件(索引配對 + 對齊位移)+ 量具健康。
    無效就 RepInvalid。"""
    dbus_seq, zone_seq, rf_seq = seqs
    t0 = rep["t_inject"]

    for name in ("dbus", "zone", "redfish"):
        _j, k = aligns[name]
        if idx >= k:
            raise RepInvalid(
                f"rep {rep['rep']}: {name} 序列尾端缺失(串流提早關閉,"
                f"只對齊到 {k} 個)—— rep 無效")

    t_dbus_bmc = dbus_seq[aligns["dbus"][0] + idx][1]
    k_zone = zone_seq[aligns["zone"][0] + idx][1]
    t_zone_bmc = zrows[k_zone][1]["epoch_ms"] / 1000.0
    t_redfish = rf_seq[aligns["redfish"][0] + idx][1]

    # setpt / pwm 事件 = 「與前一列不同」且在 t_zone 之後 —— 不能拿
    # rep 開頭當基準:90 °C 期間積分在爬,setpt 每個外圈 tick 都在動,
    # 55 °C rep 的「基準」會被上一個 rep 的殘餘斜坡污染。外圈是同一個
    # 1 Hz 排程(updateSensors 與 PID 計算同一輪),吃到新 die0 的那個
    # tick 就是回應 tick,純斜坡 tick 插不進 t_zone 與它之間。
    k_setpt = next((k for k in range(max(k_zone, 1), len(zrows))
                    if zrows[k][1]["setpt"] != zrows[k - 1][1]["setpt"]),
                   None)
    if k_setpt is None:
        raise RepInvalid(f"rep {rep['rep']}: setpt 沒動 —— 電平選錯或箝住了")
    t_setpt_bmc = zrows[k_setpt][1]["epoch_ms"] / 1000.0

    k_pwm = next((k for k in range(max(k_setpt, 1), len(zrows))
                  if zrows[k][1]["fan0_pwm"] != zrows[k - 1][1]["fan0_pwm"]),
                 None)
    if k_pwm is None:
        raise RepInvalid(f"rep {rep['rep']}: PWM 沒動 —— 內圈前饋失效?")
    t_pwm_bmc = zrows[k_pwm][1]["epoch_ms"] / 1000.0

    # 健康 (a):rep 窗內 zone 的 BMC epoch 連續性(跳步/停擺偵測)。
    # 窗在 BMC 域,**涵蓋被量的整段**:從 ② 的起點(t_dbus 與 t_zone
    # 較早者)前 1 s 到 pwm 事件後 2 s —— 第一版從 t_zone−1.5 起算,
    # 跳步落在 t_dbus 與 t_zone 之間時漏抓,seg2 出現 8.47 s 的
    # 髒 outlier(= 0.87 + 一次 7.6 s 跳步)。
    lo = min(t_dbus_bmc, t_zone_bmc) - 1.0
    window = [r["epoch_ms"] / 1000.0 for _, r in zrows
              if lo <= r["epoch_ms"] / 1000.0 <= t_pwm_bmc + 2.0]
    gaps = [b - a for a, b in zip(window, window[1:], strict=False)]
    max_gap = max(gaps) if gaps else float("inf")
    if max_gap > MAX_GAP_S:
        raise RepInvalid(
            f"rep {rep['rep']}: zone 的 BMC epoch 行距 {max_gap:.2f} s"
            f" > {MAX_GAP_S} s —— guest 時鐘跳步/停擺,rep 無效")

    # 健康 (b):rep 窗內 Redfish 輪詢的 host 節奏(host/WSL 凍結偵測)。
    # ★ 錨定「t0 前最後一筆」:凍結若發生在窗的開頭,窗內樣本對之間
    #   看不到那個洞(沒有樣本對就沒有 gap)—— 合成測試抓過這個盲區。
    before_rf = [t1 for _, t1, _ in redfish if t1 <= t0]
    rf_ts = ([max(before_rf)] if before_rf else []) + \
        [t1 for _, t1, _ in redfish if t0 < t1 <= t_redfish + 1.0]
    rf_gaps = [b - a for a, b in zip(rf_ts, rf_ts[1:], strict=False)]
    rf_max = max(rf_gaps) if rf_gaps else float("inf")
    if rf_max > REDFISH_GAP_S:
        raise RepInvalid(
            f"rep {rep['rep']}: Redfish host 節奏斷了 {rf_max:.2f} s"
            f" > {REDFISH_GAP_S} s —— host/WSL 凍結,rep 無效"
            f"(exp09 的 17.3 s 教訓,host 側版本)")

    return {"t_dbus_bmc": t_dbus_bmc, "t_zone_bmc": t_zone_bmc,
            "t_setpt_bmc": t_setpt_bmc, "t_pwm_bmc": t_pwm_bmc,
            "t_redfish": t_redfish,
            "max_gap_s": max_gap, "redfish_gap_s": rf_max,
            "seg2_s": t_zone_bmc - t_dbus_bmc,
            "seg3_s": t_pwm_bmc - t_setpt_bmc,
            "total_redfish_s": t_redfish - t0}


class RepInvalid(SystemExit):
    """單一 rep 無效(量具健康或事件缺失)。

    32 個 rep 互相獨立,guest 時鐘每 ~40 s 跳步一次本來就會命中其中
    幾個 —— 逐 rep 拒收、記錄理由,有效數低於 MIN_VALID 才整 run
    作廢。門檻寫在採資料之前。(繼承 SystemExit:單獨呼叫
    detect_rep_events 時行為不變。)"""


def characterize_sawtooth(zrows) -> dict:
    """從 zone epoch 序列量化 guest 時鐘的跳步:次數、幅度、間隔。"""
    jumps = []
    prev = None
    for _arr, r in zrows:
        ep = r["epoch_ms"] / 1000.0
        if prev is not None and ep - prev > 1.0:
            jumps.append({"epoch_s": ep, "amplitude_s": ep - prev})
        prev = ep
    periods = [b["epoch_s"] - a["epoch_s"]
               for a, b in zip(jumps, jumps[1:], strict=False)]
    return {
        "count": len(jumps),
        "amplitude_median_s": statistics.median(
            [j["amplitude_s"] for j in jumps]) if jumps else 0.0,
        "period_median_s": statistics.median(periods) if periods else None,
        "jumps": jumps,
    }


def summarize(rows: list[dict]) -> dict:
    """暖身以外的 rep → 每段 median 與 p95(inclusive)。"""
    kept = [r for r in rows if not r["warmup"]]
    out = {"n": len(kept)}
    for key in ("seg2_s", "seg3_s", "total_redfish_s"):
        vals = sorted(r[key] for r in kept)
        out[key] = {
            "median": statistics.median(vals),
            "p95": statistics.quantiles(vals, n=20, method="inclusive")[18],
            "min": vals[0], "max": vals[-1],
        }
    return out


# ── 收集 ──────────────────────────────────────────────────────────────

def collect() -> None:
    import shutil

    if shutil.which("sshpass") is None:
        raise SystemExit("需要 sshpass")
    conf_md5 = deploy_tuned_config()

    qmp = Qmp("/tmp/qmp-bletchley.sock")
    devs = [p for bus, addr, p in find_tmp421(qmp) if bus == 0 and addr == 0x4F]
    if len(devs) != 1:
        raise SystemExit(f"預期恰好一顆 die0 tmp421,找到 {len(devs)}")
    die0_qom = devs[0]

    # 中性預位:上一輪(或上一次中止)可能把感測器留在某個電平上。
    # 若 rep00 注入的值恰等於現值,dbus-sensors **不會發 PropertiesChanged**
    # (值沒變就沒訊號 —— W3 的 timeout=0 教訓的同一機制),活體檢查會
    # 冤枉整條通道;序列配對也要求開場不在任何電平上。先壓到 70 °C。
    qmp.cmd("qom-set", path=die0_qom, property="temperature0", value=70000)

    streams_dir = OUT_DIR / "streams"
    streams_dir.mkdir(parents=True, exist_ok=True)

    print("開三條量測通道(dbus monitor / zone tail / redfish poll)…")
    dbus = Stream("dbus", (
        "SYSTEMD_COLORS=0 busctl monitor --match \"type='signal',"
        "member='PropertiesChanged',"
        f"path='{DIE0_DBUS_PATH}'\""))
    zone = Stream("zone", "tail -n 0 -F /tmp/pidlog/zone_0.log")
    redfish = RedfishPoller()

    # 就緒屏障:固定 sleep 會輸給偶發的慢握手 —— 第二次收集就是注入
    # 跑在 busctl 掛上之前,訊號發給了還沒出生的聽眾(LOG 2026-08-12)。
    # busctl 掛上會先印 banner;zone tail 每 0.1 s 有心跳(批次傳輸下
    # 屏障可能要等一個 flush);redfish 至少一筆成功讀值。
    deadline = time.time() + 25.0
    while True:
        dbus_ok = any("Monitoring bus message stream" in ln
                      for _, ln in dbus.snapshot())
        zone_ok = len(zone.snapshot()) >= 3
        rf_ok = len(redfish.snapshot()) >= 1
        if dbus_ok and zone_ok and rf_ok:
            break
        if time.time() > deadline:
            raise SystemExit(f"量測通道 25 s 內沒就緒:dbus={dbus_ok} "
                             f"zone={zone_ok} redfish={rf_ok}")
        time.sleep(0.2)
    time.sleep(0.5)

    reps = []
    try:
        for i in range(REPS):
            level = LEVELS_C[i % 2]
            expected_c = expected_hwmon_mC(int(round(level * 1000))) / 1000.0
            t_before = time.time()
            qmp.cmd("qom-set", path=die0_qom, property="temperature0",
                    value=int(round(level * 1000)))
            t_inject = time.time()
            reps.append({"rep": i, "level_c": level,
                         "expected_c": expected_c,
                         "t_qmp_before": t_before, "t_inject": t_inject,
                         "warmup": i < WARMUP_REPS})
            print(f"rep {i:02d}: {level:.0f} °C @ {t_inject:.3f}"
                  f"(預測 hwmon {expected_c:.3f})", flush=True)
            # 暖身第一發做一次活體檢查:D-Bus 4 s 內要看到,否則整組
            # 都會是垃圾 —— 早死早超生。(批次傳輸下訊號行可能晚到:
            # busctl 每則訊息 ~1 KB,注入觸發的兩則訊息量足以逼出 flush。)
            if i == 0:
                time.sleep(4.0)
                seen = any(any(abs(float(m) - expected_c) <= MATCH_EPS_C
                               for m in _FLOAT.findall(ln))
                           for _, ln in dbus.snapshot())
                if not seen:
                    tail = [ln for _, ln in dbus.snapshot()][-8:]
                    raise SystemExit(
                        "暖身注入 4 s 內沒出現在 D-Bus 串流 —— 檢查 "
                        "busctl match / hwmontempsensor / 通道時序。"
                        "串流尾 8 行:\n" + "\n".join(tail))
                time.sleep(PERIOD_S - 4.0)
            else:
                time.sleep(PERIOD_S)
        # 收尾寬限:swampd 的 ofstream 與 ssh 鏈各有 ~8 KB 緩衝
        # (各 ≈16 s 的 zone 行),立刻關通道會把最後一批留在緩衝裡
        # —— 第一次乾淨收集就這樣丟了 rep31 的 zone 事件。
        print("收尾寬限 40 s(等兩層 ~8 KB 緩衝把尾巴吐完)…", flush=True)
        time.sleep(40.0)
    finally:
        dbus.close()
        zone.close()
        redfish.close()

    print("寫原始串流(證據)…")
    (streams_dir / "dbus.log").write_text(
        "".join(f"{t:.6f}\t{ln}\n" for t, ln in dbus.snapshot()))
    (streams_dir / "zone.log").write_text(
        "".join(f"{t:.6f}\t{ln}\n" for t, ln in zone.snapshot()))
    (streams_dir / "redfish.csv").write_text(
        "t_before,t_after,reading\n" + "".join(
            f"{a:.6f},{b:.6f},{v}\n" for a, b, v in redfish.snapshot()))
    (streams_dir / "inject.csv").write_text(
        "rep,level_c,expected_c,t_qmp_before,t_inject,warmup\n" + "".join(
            f"{r['rep']},{r['level_c']},{r['expected_c']},"
            f"{r['t_qmp_before']:.6f},{r['t_inject']:.6f},"
            f"{int(r['warmup'])}\n" for r in reps))
    (OUT_DIR / "collect_meta.json").write_text(json.dumps({
        "config_md5": conf_md5,
        "reps": REPS, "warmup_reps": WARMUP_REPS,
        "period_s": PERIOD_S, "levels_c": LEVELS_C,
        "redfish_uri": REDFISH_DIE0,
    }, indent=2) + "\n")
    print(f"收集完成 → {streams_dir}")


def analyze() -> int:
    streams_dir = OUT_DIR / "streams"

    def load_stream(name):
        rows = []
        for line in (streams_dir / name).read_text().splitlines():
            t, _, payload = line.partition("\t")
            rows.append((float(t), payload))
        return rows

    dbus_events = dbus_value_events(load_stream("dbus.log"))
    zrows = [(t, parse_zone_line(ln)) for t, ln in load_stream("zone.log")]
    zrows = [(t, r) for t, r in zrows if r is not None]
    redfish = []
    for line in (streams_dir / "redfish.csv").read_text().splitlines()[1:]:
        a, b, v = line.split(",")
        redfish.append((float(a), float(b), float(v)))

    reps = []
    inject = (streams_dir / "inject.csv").read_text().splitlines()[1:]
    for line in inject:
        rep, level, exp_c, t_b, t_i, warm = line.split(",")
        reps.append({"rep": int(rep), "level_c": float(level),
                     "expected_c": float(exp_c),
                     "t_qmp_before": float(t_b), "t_inject": float(t_i),
                     "warmup": bool(int(warm))})

    # 健康 (c):注入節奏(注入迴圈自身的凍結偵測)
    inj_ts = [r["t_inject"] for r in reps]
    inj_gaps = [b - a for a, b in zip(inj_ts, inj_ts[1:], strict=False)]
    if inj_gaps and max(inj_gaps) > PERIOD_S + 2.0:
        raise SystemExit(f"注入節奏斷了 {max(inj_gaps):.2f} s —— run 無效")

    seqs = build_sequences(dbus_events, zrows, redfish)
    aligns = validate_sequences(reps, *seqs)
    for name, (j, k) in aligns.items():
        if j or k < len(reps):
            print(f"  {name} 對齊:略過 {j} 個 legacy 轉換、"
                  f"尾端缺 {len(reps) - k} 個")

    sawtooth = characterize_sawtooth(zrows)
    print(f"guest 時鐘鋸齒:{sawtooth['count']} 次跳步,"
          f"中位幅度 {sawtooth['amplitude_median_s']:.2f} s,"
          f"中位間隔 {sawtooth['period_median_s']} s")

    rows = []
    rejects = []
    for i, rep in enumerate(reps):
        try:
            ev = detect_rep_events(rep, i, seqs, aligns, zrows, redfish)
        except RepInvalid as why:
            rejects.append({"rep": rep["rep"], "why": str(why)})
            print(f"  拒收 {why}")
            continue
        rows.append({**rep, **ev})

    n_valid = sum(1 for r in rows if not r["warmup"])
    if n_valid < MIN_VALID:
        raise SystemExit(
            f"有效 rep 只剩 {n_valid} < {MIN_VALID} —— run 無效"
            f"(拒收 {len(rejects)} 個,理由見上)")

    hdr = list(rows[0].keys())
    (OUT_DIR / "events.csv").write_text(
        ",".join(hdr) + "\n" + "".join(
            ",".join(str(r[k]) for k in hdr) + "\n" for r in rows))

    summary = summarize(rows)

    # Redfish 輪詢解析度(相鄰 t_after 間距)—— total 的讀值粒度,進 meta。
    poll_gaps = sorted(b1 - b0 for (_, b0, _), (_, b1, _)
                       in zip(redfish, redfish[1:], strict=False))
    poll_med = statistics.median(poll_gaps) if poll_gaps else float("nan")

    # guest 時鐘速率(診斷):同 rep 的 zone 事件間隔(guest)對注入
    # 間隔(host)。跳步落在事件間的 rep 已被拒收,這裡用有效 rep。
    valid_pairs = [(r["t_inject"], r["t_zone_bmc"]) for r in rows]
    rate = None
    if len(valid_pairs) >= 3:
        dh = valid_pairs[-1][0] - valid_pairs[0][0]
        dg_raw = valid_pairs[-1][1] - valid_pairs[0][1]
        span_jumps = sum(
            j["amplitude_s"] for j in sawtooth["jumps"]
            if valid_pairs[0][1] < j["epoch_s"] <= valid_pairs[-1][1])
        rate = (dg_raw - span_jumps) / dh if dh > 0 else None

    meta = {
        "experiment": "exp10_latency",
        "collect": json.loads((OUT_DIR / "collect_meta.json").read_text()),
        "summary": summary,
        "rejected_reps": rejects,
        "sawtooth": {k: v for k, v in sawtooth.items() if k != "jumps"},
        "sawtooth_jumps": sawtooth["jumps"],
        "guest_clock_rate_between_corrections": rate,
        "redfish_poll_median_s": poll_med,
        "swampd": "unmodified upstream @ c5e5955 (docs/env-baseline.md)",
        "repo_commit": subprocess.getoutput("git rev-parse --short HEAD"),
    }
    (OUT_DIR / "exp10_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n")

    print(f"\n{'':>22} {'median':>8} {'p95':>8} {'min':>8} {'max':>8}")
    for key, label in (
            ("total_redfish_s", "inject→redfish(host)"),
            ("seg2_s", "2 dbus→zone(guest)"),
            ("seg3_s", "3 setpt→pwm(guest)")):
        s = summary[key]
        print(f"{label:>22} {s['median']:>8.3f} {s['p95']:>8.3f}"
              f" {s['min']:>8.3f} {s['max']:>8.3f}")
    print(f"\nRedfish 輪詢解析度(中位):{poll_med:.3f} s;"
          f"guest 時鐘速率(校正間):{rate if rate is None else round(rate, 4)};"
          f"n = {summary['n']}(拒收 {len(rejects)},暖身 {WARMUP_REPS})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="exp10 end-to-end latency")
    ap.add_argument("--collect-only", action="store_true")
    ap.add_argument("--analyze-only", action="store_true")
    args = ap.parse_args()
    if not args.analyze_only:
        collect()
    if not args.collect_only:
        return analyze()
    return 0


if __name__ == "__main__":
    sys.exit(main())
