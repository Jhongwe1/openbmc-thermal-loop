# 串級架構的實測(exp06)

**日期:** 2026-08-11
**映像:** `obmc-phosphor-image-bletchley-20260728025045.static.mtd`
**上游:** `phosphor-pid-control` @ `f6d4cb9`(`pid-control: Make IPMI support optional`)
**設定:** `config/swampd/config.tuned.json`(λ = 2τ 的係數)
**原始資料:** `bench/data/exp06_cascade/`

> **一句話:** swampd 不是一個 PID,是**兩個**。
> 內圈 **100 ms**、外圈 **1000 ms**,兩個數字都是我自己量的。

---

## 1. 上游怎麼說

**【查】上游 README:**
> *"The EC PID loop is designed to hit the fans 10 times per second to drive them
> to the desired value and read the sensors once per second."*

**【查】`pid/conf.hpp`:** `cycleIntervalTimeMS = 100`、`updateThermalsTimeMS = 1000`。

**【查】實測旁證:** 設定檔不寫這兩個欄位時,swampd 自己會印出預設值:
```
Zone 0: cycleIntervalTimeMS cannot find setting. Use default 100 ms
Zone 0: updateThermalsTimeMS cannot find setting. Use default 1000 ms
```

⚠️ 這兩個欄位 `configure.md` **沒有記錄** —— 見 `docs/upstream.md` 的 patch 候選清單。

```
   die0 溫度感測器(D-Bus,被動推送)
        │
        ▼
   ┌────────────────┐   RPM setpoint   ┌────────────────┐   PWM
   │  熱 PID(外圈) │ ───────────────▶ │ 風扇 PID(內圈)│ ──────▶ /tmp/sys/pwm0
   │  type: temp     │  (zone 內取 max) │  type: fan      │
   │  ts = 1.0 s     │                  │  ts = 0.1 s     │
   │  輸出單位 RPM   │                  │  輸出單位 %     │
   └────────────────┘                   └───────▲────────┘
                                                │ tach 讀回
                                                └──────────
```

---

## 2. ★★ 量之前:先確認量測儀器本身

**計畫寫的量法是「`pidcore.*` 裡 setpoint 變化的間隔」。那個方法是錯的。**

上游 `pid/ec/logging.cpp`:

```cpp
static constexpr int logThrottle = 60 * 1000;          // ← 60 秒

void LogContext(PidCoreLog& pidLog, ...)
{
    bool shouldLog = false;
    if (pidLog.lastLog == zero)                 shouldLog = true;  // 第一次
    else if (since.count() >= logThrottle)      shouldLog = true;  // 節流到期
    if (pidLog.lastContext != coreContext)      shouldLog = true;  // 內容變了
    if (!shouldLog) return;
    ...
}
```

`pidcore.*` 是**「內容變了 **或** 距上次 60 秒」**才寫一筆的 log,**不是等間隔取樣**。

**實測(迴路靜態時,係數全 0、溫度恆為 0):**

| 相鄰間隔 | 值 |
|---|---|
| `pidcore.die0` | **60013 ~ 67569 ms**,36 筆裡沒有一筆接近 1000 |
| `zone_0.log` | 中位數 **100 ms** |

**同一個 daemon 的兩份 log,同一台機器,差 600 倍。**
不是機器慢,是**兩種寫入策略**:`zone_0.log` 由 `DbusPidZone::writeLog()`
直接寫,**沒有節流**。

> ★ **所以週期要從 `zone_0.log` 量。**
> 而且要量的是它的 **`setpt` 欄變化的間隔**(那是熱 PID 的輸出),
> 不是 `die0` 欄(那是 D-Bus 感測器的更新率,**第三個**時間尺度)。

⚠️ **這對 W7 有直接後果:Fig 3 第三面板(積分軌跡)吃的就是 `pidcore.*`。**
畫之前要先確認每個週期都有點 —— 否則「值不再變化」的那一段
(**正是 anti-windup 生效之後的那一段**)會被壓縮成幾個點。

---

## 3. 我量到什麼

**方法:** 注入固定 85 °C(高於 setpoint 65,誤差為負、積分往正累積),
部署 `config.tuned.json`,重啟 swampd,取樣 90 s,把 log 抓回開發機分析。

**為什麼要注入一個「會讓輸出持續變化」的溫度:** 見上一節 —— 內容不變就只剩節流在寫。

| 量測 | 方法 | **我量到的(中位數)** | p05 ~ p95 | n | 上游常數 |
|---|---|---|---|---|---|
| **內圈:風扇迴路週期** | `zone_0.log` 相鄰行時間戳差 | **100.0 ms** | 95 ~ 105 | 819 | `cycleIntervalTimeMS = 100` |
| **外圈:熱迴路週期** | `zone_0.log` 的 `setpt` 欄變化間隔 | **1000.0 ms** | 994 ~ 1008 | 81 | `updateThermalsTimeMS = 1000` |

**兩個都與上游常數一致。**

### ⚠️ 為什麼報中位數不報平均

| | 中位數 | 平均 | 最大 |
|---|---|---|---|
| 內圈 | **100.0 ms** | 118.8 ms | 7805 ms |
| 外圈 | **1000.0 ms** | 1191.2 ms | 8705 ms |

**平均都被拉高約 19%。** 長尾來自 QEMU 的排程抖動(整台虛擬機被 host 暫停),
不是 swampd 的行為。**只報平均會得到一個錯 19% 的數字,而且錯的方向是「看起來比較慢」。**

---

## 4. ★ 交叉驗證:係數從 Fig 1 一路算到 BMC 上的積分累積速率

`pidcoeffs.die0`(swampd 自己回報的、**實際生效**的係數):

```
proportionalCoeff = -220.279
integralCoeff     = -5.00952
integralLimit.min = 0        integralLimit.max = 15000
outLim.min        = 3000     outLim.max        = 15000
ts                = 1
```

這兩個係數的來歷是**一條完整可查的鏈**:

```
開環階躍 CSV (exp01, W4)
  → exp01_fit.txt:  K = -0.314708 °C/%PWM,  tau = 43.972 s,  theta = 7.2013 s
  → bench/tune.py:  Kc = tau / (|K|(lambda+theta)) = 1.4685 %PWM/°C   (lambda = 2 tau)
                    Ki = Kc / Ti                   = 0.033397 %PWM/(°C·s)
  → × 150 RPM/%PWM(plant 的 rpmMax/100,串級外圈的量綱)
  → 取負(temp 型別,error = setpoint − input)
  → config.tuned.json:  -220.27862,  -5.00952
```

**手算與實測對得上小數點後三位:**

| 項 | 手算 | `pidcore.die0` 實測 |
|---|---|---|
| P 項 | `−220.279 × (−19.938)` = **4391.92** | **4391.92** |
| 每步積分增量 | `−5.00952 × (−19.938) × 1.0` = **99.880** | **99.8798** |

> ★ 這條鏈證明的不是「我算得對」,是
> **「BMC 上跑的那個數字,指得回我自己量的那張圖」。**

---

## 5. `integralLimit` 的修復驗收(W6 開工第一件事)

修之前 `integralLimit = [0, 0]`,而上游 `ec::pid()` 對積分項有一次**無條件**箝位,
`clamp(x, 0, 0)` 恆為 0 —— **設了 `integralCoeff` 也不會有積分作用,而且不報錯。**

**實測驗收(`bench/data/exp06_cascade/pidcore.die0`):**

```
t=...117744  input=84.938  error=-19.938  P=4391.92  I=  99.8798  out= 4491.8
t=...118856  input=84.938  error=-19.938  P=4391.92  I= 199.76    out= 4591.67
...
t=...235893  input=84.938  error=-19.938  P=4391.92  I=9588.46    out=13980.4
```

**`integralTerm` 從 99.88 走到 9588.46,96 筆,單調上升。它真的會動了。**

同時 `zone_0.log` 的 `requester` 欄從 `Minimum` 變成 **`die0`** ——
zone 的輸出不再是被 `minThermalOutput` 撐著,而是**熱 PID 在駕駛**。

⚠️ 這一段同時是 **W7 的預演**:這裡是**開環**(注入的溫度不會因為風扇轉而下降),
所以積分一路累積 —— 那正是 windup。積分上限 15000 還沒被碰到(最高 9588),
再跑久一點就會頂上去。**W7 要量的就是「頂上去之後,溫度降下來時它要花多久放完」。**

---

## 6. 這一節的限制

1. **我的 L1 是單迴路。** `bench/sim` 的控制器直接輸出 PWM,只是把控制器取樣週期
   設成 1 Hz 來對齊外圈。**我沒有在 L1 完整實作內圈風扇 PID。**
   兩層的量綱差 150 倍(`%PWM` vs `RPM`),換算靠 `bench/tune.py` 的
   `to_swampd_rpm()`,而那個換算**把內圈當成一個靜態增益** ——
   也就是假設「內圈快到外圈看不見它的動態」。
   內圈 10 Hz、外圈 1 Hz 相差 10 倍,這個假設大致成立,**但不是完全成立**。

2. **內圈風扇 PID 的係數刻意留 0,沒有整定。**
   理由:內圈的整定目標與外圈不同(它要準確追 RPM setpoint),
   而**我的 plant 沒有建模個別風扇的轉速誤差** —— 沒有量測就不要填數字。
   **後果要知道:內圈係數為 0 時 PWM 被箝在 `outLim_min = 30%` 不動。**
   所以 L1/L2 疊圖要比對**外圈的輸出(RPM setpoint)**,不是 PWM。
   由 `test/python/test_swampd_config.py::test_inner_fan_pid_is_left_untuned_on_purpose`
   守著,讓「PWM 不會動」是預期而不是意外。

3. **這台 QEMU 沒有真的風扇。** `fan0` 是 `/tmp/sys/` 底下的檔案替身
   (見 `config/swampd/README.md` §1)。它證明的是「swampd 的寫出路徑有被執行、
   值是多少」,**不是**「風扇真的轉了」。

4. **QEMU 的排程抖動是真的。** 內圈最大間隔 7805 ms、外圈 8705 ms。
   真實 BMC 上不會這樣。所以本頁的**中位數**可以拿來談 swampd 的設計,
   **分位數與最大值只能拿來談這個測試床**。

5. **L1 與 L2 的疊圖**(寫下這條時還沒做;**2026-08-14 更新:W7 已做**)。
   未修改的上游 swampd 二進位經 `harness/dbus_bridge.py` 控制同一份
   plant,anti-windup 恢復時間比單趟 **12.9×**,落在 L1 的 5-seed 範圍
   [12.83, 13.89] 內(`figures/fig3_antiwindup.png`)。
   當時的提醒仍然成立所以留著:先把**時間尺度**對齊 ——
   `bench/sim` 的 `--ctrl-ts` 預設 1.0 s,理由就是這一頁量到的 1000 ms;
   L1/L2 對不上時,先懷疑時間尺度,再懷疑參數。

---

## 7. 前饋在串級內圈的角色(2026-08-14 補)

**【查】`pid/ec/pid.cpp:101`:** `feedFwdTerm = (setpoint + feedFwdOffset) × feedFwdGain`

這不是抽象知識,**本 repo 的內圈設定就是它的極端實例**:
`config.baseline.json` 的 fan0 PID 係數 P=0、I=0、
`feedFwdGainCoeff = 1/150` —— 內圈輸出 = RPM setpoint × (100 %PWM / 15000 RPM)。
外圈要 4500 RPM,內圈**這一步**就給 30 %PWM,不等任何積分累積。

| 前饋給內圈買到什麼 | 說明 |
|---|---|
| 響應快 | 不用等積分爬;setpoint 一變,輸出同步跟 |
| **積分工作範圍小 → windup 風險降** | 積分只需要修「前饋沒算準的殘差」,不用扛整個工作點 —— **前饋是 anti-windup 的上游解法**(箝位是下游解法) |
| 係數有物理意義 | 1/150 = 100 %PWM / 15000 RPM,直接從風扇規格(`rpmMax`)算出來,不用試誤 |

**【判】誠實邊界:** 第二列「windup 風險降」在本測試床**沒有實驗證據**。
我的內圈 P=I=0,積分路徑整條沒開,「前饋 baseline + 回授修殘差」的
組合我沒有跑過 —— 這個論點是從 `ec::pid()` 的結構推論的。
要驗證它需要一個有個別風扇轉速誤差的 plant(未做,見
[limitations.md](limitations.md) 控制層面)。

---

## 8. 為什麼這件事重要

| 層面 | 影響 |
|---|---|
| **對我的實驗** | Fig 2 的 `--ctrl-ts 1.0` 不是隨手填的,是對齊這裡量到的外圈週期。L1/L2 對不上時,**先懷疑時間尺度,再懷疑參數**(地雷 #12) |
| **對前饋的理解** | `feedFwdGain` 是**內圈**用的:PWM→RPM 近似線性,前饋直接給 baseline,PI 只修殘差。**在單迴路的心智模型下這件事講不通** |
| **對面試** | 「為什麼要串級?」的答案:**內圈快、外圈慢,內圈把執行器的非線性(PWM→RPM 不線性、風扇機械慣性、個體差異)吃掉,讓外圈只需要面對熱動態。** 而我可以指著兩個自己量到的數字說這句話 |
| **對量測方法論** | ★ **量一個系統的週期之前,先確認記錄這件事的東西本身是不是等間隔的。** `pidcore.*` 教了我這件事,代價是 60 倍的誤差 |
