# 架構

這裡有**兩張不同的圖**。混為一談是外行訊號。

| | 圖 A:系統三層時間尺度 | 圖 B:驗證四層金字塔 |
|---|---|---|
| 描述的是 | **產品在跑的時候長什麼樣** | **我怎麼驗證我的東西** |
| 分層依據 | **時間尺度**(µs → ms → s) | 迭代成本與被測物 |

> 圖中的服務名稱、hwmon 裝置、感測器路徑**都是 2026-07-28 在 `bletchley` 上實際量到的**
> (見 [`env-baseline.md`](env-baseline.md)),不是通用範例。

---

## 圖 A:系統三層時間尺度解耦

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  L3  管理層 —— 秒級                                                            │
│      bmcweb  (Redfish over HTTPS/JSON)                                       │
│      實測:GET /redfish/v1/Chassis/Bletchley_Front_Panel_Board/ThermalSubsystem │
│            → #ThermalSubsystem.v1_0_0        (舊的 /Thermal 在此映像不存在)    │
│      用途:遙測、策略覆寫。★ 絕不是控制迴路的一部分                              │
└──────────────────────────────────────────────────────────────────────────────┘
        ▲ JSON / HTTPS(非同步遙測)              │ PATCH / POST(策略覆寫)
        │                                        ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  IPC  D-Bus 系統匯流排 (sdbusplus / libsystemd)                                │
│       xyz.openbmc_project.Sensor.Value                                       │
│       xyz.openbmc_project.Control.FanPwm   (Target)                          │
│       xyz.openbmc_project.State.FanCtrl    (Manual / FailSafe) ← swampd 持有  │
│       xyz.openbmc_project.Hwmon.external   (extsensors 注入)   ← swampd 持有  │
│       xyz.openbmc_project.Association.Definitions ← 沒有它 Redfish 看不到      │
└──────────────────────────────────────────────────────────────────────────────┘
        ▲ PropertiesChanged 訊號                  │ Method call / Set
        │                                        ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  L2  韌體控制層 —— 100 ms ~ 1 s   ★ 控制閉環在這裡,只在這裡                     │
│      entity-manager   : probe FRU → 發布 Configuration                       │
│                         (實測:swampd 的設定來源是這個,不是 config.json)      │
│      dbus-sensors     : HwmonTempSensor / FanSensor / ADCSensor / PSUSensor   │
│      phosphor-virtual-sensor : Virtual_Inlet_Temp、nvme1~6 …                  │
│      phosphor-pid-control (swampd):                                          │
│          熱 PID  ~1 Hz ──RPM setpoint──▶ 風扇 PID ~10 Hz ──PWM──▶            │
│          【查】cycleIntervalTimeMS / updateThermalsTimeMS(W6 要實測)          │
│      ⚠️ 目前狀態:「No fan zones, application pausing until new configuration」 │
│          ← Gate 1 的任務就是給它設定,不是讓它跑起來                            │
└──────────────────────────────────────────────────────────────────────────────┘
        ▲ /sys/class/hwmon/hwmonX/temp1_input     │ /sys/.../pwm1
        │                                        ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  L1  硬體抽象與物理層 —— µs ~ ms                                               │
│      ASPEED AST2600-A3 (ARM Cortex-A7), Linux 6.18.40 armv7l                 │
│      實測 hwmon:tmp421 ×8、tcpm_source_psy_* ×6、iio_hwmon ×1                 │
│      i2c-aspeed / pwm-tacho driver、I2C/SMBus、NTC / diode、tach (FG)         │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 靶心題:「為什麼 Redfish 遙測不能直接當 PID 閉環的輸入?」

因為**時間尺度差了兩到三個數量級**。

L2 的控制迴路,上游設計是風扇每秒跑十次、感測器每秒讀一次。
L3 的 Redfish 每次請求要走 TLS、透過 ObjectMapper 查 association、再組 JSON,**秒級起跳**。

把 L3 的值餵進 L2 的迴路會同時得到兩個問題:**相位延遲**讓迴路的相位裕度被吃掉、
容易震盪;**取樣率不足**讓你抓不到熱瞬變。

所以 Redfish 的定位是**非即時遙測與策略覆寫**——它可以告訴你現在幾度、可以叫你切到
Acoustic mode,但它不能是誤差訊號的來源。
**這是分層設計的通則:控制迴路要閉在最靠近執行器的那一層。**

> ⚠️ **不要講「違反奈奎斯特取樣定理」。** 那是訊號重建的定理,不是控制迴路穩定性的
> 判準。要講的是**相位裕度**與**死區時間佔比**。講錯定理比不講更糟。

---

## 圖 B:驗證四層金字塔

只在 QEMU 裡做,會遇到三件事:改一個參數要重開機(實測開機 **149.7 秒**),迭代太慢;
QEMU 時間不精確,量到的延遲摻雜模擬器抖動;CI 跑不動,別人重現不了。

只在本機模擬,則會被問死:「那你有跑過真的 OpenBMC 嗎?」

**所以要分層。這正是真實韌體團隊的做法。**

```
        ┌────────────────────────────────────────────────────────────┐
  L3    │  QEMU 全系統:bletchley + swampd + bmcweb + systemd          │  分鐘級
        │  ★ 官方 Robot 測試套件 QEMU_CI 在這一層跑                    │  少量、決定性
        ├────────────────────────────────────────────────────────────┤
  L2    │  Host + 私有 D-Bus:真 swampd 二進位 + 我的 plant             │  秒級
        │  驗證:真實 daemon 行為、failsafe、CSV log                    │  中量
        ├────────────────────────────────────────────────────────────┤
  L1    │  Host 純模擬:我的 PI(C++) + 我的 plant(C++),無 D-Bus        │  毫秒級
        │  驗證:控制律、參數掃描、所有的圖                             │  大量、CI 內
        ├────────────────────────────────────────────────────────────┤
  L0    │  gtest:plant 方程、PI 步進、FOPDT 擬合、★ 與上游 parity       │  微秒級
        └────────────────────────────────────────────────────────────┘
```

| 層 | 跑在哪 | 被測物 | 產出 | 迭代成本 | 目前狀態 |
|:--:|---|---|---|:--:|:--:|
| **L0** | `meson test`(gtest) | 我的 plant 方程、我的 PI、**上游 `ec::pid()`** | 通過的測試 | ms | ⬚ 未開始(W4~W5) |
| **L1** | `./build/sim` | 我的 PI ＋ 我的 plant | **Fig 1/2/3/5 ＋ 所有 CSV** | 秒 | ⬚ 未開始(W4) |
| **L2** | 本機私有 D-Bus ＋ 真 swampd | **上游 swampd** ＋ 我的 plant | **Fig 3(上游版)、Fig 4** | 秒~分 | ⬚ 未開始(W7) |
| **L3** | QEMU `bletchley-bmc` | 完整 OpenBMC 映像 | **Fig 6、Robot 報告、demo 影片** | 分 | ▣ **開機成功、SSH/Redfish 通** |

**圖例:** ▣ = 已完成且有證據　▢ = 進行中　⬚ = 理解但未實作

### 關鍵設計:同一份 plant model 貫穿 L1~L3

```
                    ┌──────────────────────────┐
                    │  plant/thermal_plant.cpp │  ← 一份 C++ 程式碼
                    │  純函式、無 IO、可測試     │
                    └───────────┬──────────────┘
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
        bench/sim          harness/dbus_bridge   (QEMU 內同一支
      (L1: 我的 PI)         (L2: 真 swampd)       透過 SSH 推值)
```

一份模型服務三層,才能宣稱「L1 的結論在 L2 也成立」。
如果每一層各寫一份模型,那三層之間的比較就沒有意義。

---

## 待補:手繪版本

上面兩張是 ASCII 版。**手繪版(紙筆)尚未完成** —— 面試白板題要的是能徒手畫出來,
不是能貼出 ASCII。手繪稿完成後放進 `docs/` 並在此連結。

---

# 資料流:一個溫度值的旅程(2026-08-05 實測)

> **Gate 1 DoD 第 4 條要求的就是這一節:「我畫得出從指令到 Redfish JSON 經過
> 哪幾個行程、幾次 IPC。」下面每一個數字都是量出來的,不是估的。**

## 完整路徑

```
  ① 我的指令(開發機,WSL)
     ./tools/set_die_temp.py 80
         │  QMP over unix socket  (/tmp/qmp-bletchley.sock)
         │  {"execute":"qom-set","arguments":{
         │     "path":"/machine/unattached/device[19]",
         │     "property":"temperature0","value":80000}}
         ▼
╔═════════════════════════ QEMU 行程(開發機上) ═════════════════════════╗
║  ② tmp421 裝置模型  (hw/sensor/tmp421.c)                              ║
║     temperature[0] = (80000*256 - 128)/1000 = 20479   ← 8.8 定點數      ║
║         │  模擬的 i2c 匯流排 (aspeed.i2c.bus.0)                        ║
║         ▼                                                             ║
║ ┌───────────────────── guest:OpenBMC(ARM) ────────────────────────┐  ║
║ │  ③ Linux tmp421 driver  ← 真的 kernel driver                     │  ║
║ │     暫存器只回傳高 12 bit(4 個小數位元 = 1/16 °C 的刻度):        │  ║
║ │     20479 & ~0xf = 20464 → 20464×1000/256 四捨五入 → 79938 m°C    │  ║
║ │         │                                                        │  ║
║ │         ▼  /sys/class/hwmon/hwmon0/temp1_input = 79938  (m°C)    │  ║
║ │  ④ hwmontempsensor (dbus-sensors)  ← 行程 1                       │  ║
║ │     每秒輪詢 sysfs;值有變才發訊號                                  │  ║
║ │         │                                                        │  ║
║ │         ▼  D-Bus                                                 │  ║
║ │  ⑤ dbus-broker  ← 行程 2(所有訊息都經過它,常被漏掉)               │  ║
║ │      ├── PropertiesChanged (broadcast)  ──▶ ⑥ swampd    ← 行程 3  │  ║
║ │      │                                        熱 PID → 風扇 PID   │  ║
║ │      │                                        → /tmp/sys/pwm0    │  ║
║ │      └── ThresholdAsserted (broadcast)  ──▶ ⑦ sel-logger ← 行程 4 │  ║
║ │                                                                  │  ║
║ │  ⑧ bmcweb  ← 行程 5(只有在有人來要的時候才動)                      │  ║
║ │      HTTPS GET /redfish/v1/Chassis/Thermal_Loop_Demo/            │  ║
║ │                Sensors/temperature_die0                          │  ║
║ └──────────────────────────────────────────────────────────────────┘  ║
╚═══════════════════════════════════════════════════════════════════════╝
```

## 【驗】行程數與 IPC 次數 —— 自己數的

量法:在 BMC 上 `timeout 8 busctl monitor > /tmp/x.txt`,期間**只做一件事**,
把輸出抓回開發機用 Python 依 `Sender` / `Destination` / `Path` 分類。
(直接比「訊息總數」會被雜訊淹沒 —— 每一次 `ssh` 進去都會產生一批
`NameOwnerChanged`。**要按物件路徑或連線名過濾。**)

### 注入一次溫度(88 °C,跨過 80 °C 的 warning 門檻)

| # | 訊息 | 發送者 → 接收者 | 說明 |
|:-:|---|---|---|
| 1 | `PropertiesChanged` | hwmontempsensor → **broadcast** | `Value` 變了 |
| 2 | `PropertiesChanged` | hwmontempsensor → **broadcast** | `WarningAlarmHigh` 變了 |
| 3 | `ThresholdAsserted` | hwmontempsensor → **broadcast** | 越過門檻的事件 |
| 4 | `Properties.GetAll` | sel-logger → hwmontempsensor | 記事件前先把感測器讀齊 |
| 5 | `Properties.Get` | sel-logger → hwmontempsensor | 同上 |

**swampd 收到第 1 則就更新了,它送出 0 則訊息。**
因為 D-Bus 訊號是**推**的 —— 訂閱者不需要回問。這就是為什麼 L2 控制迴路可以
用 D-Bus 而不會被拖慢。

**不跨門檻時只有第 1 則**;而且**值沒變就一則都沒有**(見下面的坑)。

### 讀一次 Redfish(單一感測器)

| # | method call | bmcweb → 誰 | 為什麼需要 |
|:-:|---|---|---|
| 1 | `Manager.GetUserInfo` | `xyz.openbmc_project.User.Manager` | **認證授權** —— 這一次幾乎沒人猜得到 |
| 2 | `ObjectMapper.GetObject` | `xyz.openbmc_project.ObjectMapper` | 問「這個路徑歸誰管」 |
| 3 | `Properties.GetAll` | `xyz.openbmc_project.HwmonTempSensor` | 一次把所有屬性讀回來 |

**合計 3 個 method call + 3 個回覆 = 6 則訊息,牽涉 5 個行程**
(bmcweb、user-manager、ObjectMapper、hwmontempsensor,加上 dbus-broker 本身)。

> **這張表就是〈為什麼 Redfish 不能當 PID 輸入〉的量化依據。**
> 一次讀值要 TLS 握手 + 3 次跨行程往返 + JSON 序列化;
> 而 swampd 的內圈迴路是 **100 ms 一輪**。W9 會實際去量這條鏈路的延遲。

## 圖例與現況

**實線(上面全部)＝ 已完成、有實測證據。** 2026-08-05 起,從 ① 到 ⑧ 全部是實線。

尚未實作(虛線,之後補):
- `harness/dbus_bridge.py` —— L2 用,W7
- 閉環:PWM 讀回開發機 → 餵進 plant model → 算出新溫度 → 再注入 ①,W7

## 兩條注入路線的對照

| | route (a) `extsensors` | **route (b′) hwmon(現行)** |
|---|---|---|
| 注入點 | BMC 內部(`busctl set-property`) | **模擬硬體層(QMP → tmp421)** |
| 誰擁有感測器 | swampd 自己(`HostSensor`) | `hwmontempsensor`(上游 daemon) |
| 經過 kernel driver | ❌ | **✅** |
| 經過 hwmon sysfs | ❌ | **✅** |
| 有 association | ❌ | **✅** |
| Redfish 看得到 | ❌ | **✅** |
| swampd 的介面 | `HostSensor`(推) | `DbusPassive`(訂閱) |
| 量化 | 無 | **LSB = 0.0625 °C**(晶片暫存器只有 4 個小數位元) |
| **注入偏壓** | 無 | ⚠️ **−0.0625 °C(整整一格),而且是系統性的** —— 見下方 |
| **注入到可見延遲** | 幾乎沒有(直接寫 D-Bus) | ⚠️ **中位數 351 ms**(driver 快取 `HZ/2`) |

route (a) 的設定仍留在 git 歷史裡(commit `52f84c8`),**它證明的是我兩條都做過**。

> ### ⚠️ 2026-08-09 更正:那一格差**不是量化**
>
> 上面那張圖原本標著「暫存器只回傳 12 bit → **0.0625 °C 量化** → 79.9375」。
> **那個歸因是錯的。**
>
> `80.000` 剛好落在 1/16 的格點上(80 = 1280/16),
> **一個純粹的量化器應該原封不動回 80.000**。
> 真正把它壓下去的是圖上**前一行**就寫著的 QEMU setter:
>
> ```
> temperature[0] = (int16_t)((80000 * 256 - 128) / 1000) = 20479
>                                          ^^^^^ 半個 LSB 的預先扣除,
>                                                加上 C 的整數除法往 0 截
> ```
>
> **量化(刻度多細)與偏壓(整體偏多少)是兩件不同的事**,這條路徑兩者都有:
> 刻度是 62.5 m°C,偏壓是固定的 −62 m°C(35 個觀測,零例外)。
>
> ⚠️ **偏壓是注入路徑的產物,真實硬體上不會有。** W9 的 L1/L2 疊圖要扣掉它。
> 完整推導與實測見 [`plant-model.md` §2.1](plant-model.md)
> 與 `bench/data/exp04_injection/`;離線驗證:`python bench/exp04_injection.py --check`。
