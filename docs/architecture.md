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
