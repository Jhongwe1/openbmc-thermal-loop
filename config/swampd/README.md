# `config.baseline.json` —— 每一個欄位為什麼那樣填

> **本週(W2)所有 PID 係數都是 0。** 這不是還沒填完 ——
> **係數要等 W4 做完系統識別、W6 做完 λ 整定才有意義。**
> 現在填任何數字都是猜的,而「試出來的」是面試最差的答案。
> 本週要驗的是**通路**:值進得去、swampd 看得到、log 出得來。

依據:`phosphor-pid-control` @ `f6d4cb9e5ddaeb14fbd14f9d5730fd71afe8efe2`(2026-07-31),
親自讀 `sensors/buildjson.cpp`、`sensors/builder.cpp`、`sensors/build_utils.cpp`、
`pid/buildjson.cpp`、`pid/fancontroller.cpp`、`sysfs/sysfs{read,write}.cpp`。

---

## 1. `sensors[]` —— 感測器怎麼被建立

`readPath` 的**前綴決定它走哪一條實作**。判斷邏輯在 `sensors/build_utils.cpp`:

| `readPath` | `IOInterfaceType` | 建出什麼 |
|---|---|---|
| 空字串或 `"None"` | `NONE` → `default:` | `WriteOnly`,**`read()` 會 throw** |
| 含 `/xyz/openbmc_project/extsensors/` | `EXTERNAL` | `HostSensor`(swampd 自己 own,走 host bus) |
| 含 `/xyz/openbmc_project/` | `DBUSPASSIVE` | `DbusPassive`,監聽 `PropertiesChanged` |
| 含 `/sys/` | `SYSFS` | `SysFsRead` |

> **★ 它用的是 `path.find(x) != npos`,也就是「字串裡任何位置含有」,不是「開頭是」。**
> 這一點決定了下面 `fan0` 的做法。而且**順序有意義** —— `extsensors` 先檢查,
> 所以 external 的路徑不會被誤判成 passive dbus。

### `die0`(溫感,**route (b′):hwmon 被動 D-Bus 感測器**)

```json
{ "name": "die0", "type": "temp",
  "readPath": "/xyz/openbmc_project/sensors/temperature/die0",
  "timeout": 0,
  "ignoreDbusMinMax": true }
```

> **2026-08-06 改動:** 原本走 route (a)(`/xyz/openbmc_project/extsensors/...`,
> swampd 自己 own 的 `HostSensor`)。改成讀 `dbus-sensors` 的 `hwmontempsensor`
> 建的那顆,因為**只有它有 association,Redfish 才看得到**。
> 舊版設定保留在 git 歷史 commit `52f84c8`。
> 為什麼不是計畫寫的 route (b),見
> [`config/entity-manager/README.md`](../entity-manager/README.md) §0。

- `type: "temp"` → 在 `builder.cpp` 走 read-only 分支。
- 路徑含 `/xyz/openbmc_project/` 但**不含** `extsensors` → `DBUSPASSIVE`,
  建成 `DbusPassive`,訂閱 `PropertiesChanged`。
- **`timeout: 0` 不是偷懶,是正解。** `pid/zone.hpp` 的 stale 判定是
  `now - r.updated >= timeout`,而 `_updated` **只在收到 `PropertiesChanged`
  時才更新**;dbus-sensors 端又是**值有變才發訊號**。
  結果是「溫度穩定不動」＝「感測器死了」。實測 `timeout: 5` 時 `failsafe=1`、
  `pwm0=255`,journal 印 `die0: The sensor has timed out`。
  上游走 entity-manager 設定那條路時會**自動**設 0(`dbus/dbusconfiguration.cpp`
  註解:*"D-Bus passive sensor updates are pushed in, not pulled by timer poll"*),
  但走 `--conf` JSON 這條路不會。
- **`ignoreDbusMinMax: true` 也不是可有可無。** 沒有它,`dbuspassive.cpp` 會用
  感測器的 `MinValue`/`MaxValue`(−128 / 127)把讀值正規化到 [0,1],
  於是 PID 拿 `0.8154` 去跟 `setpoint 65` 相減。
  **不會報錯,只有 `pidcore.*` 看得見。** 上游註解:
  *"which would mess up the PID loop math"*。
- **沒有寫 `min`/`max`。** `sensors/buildjson.cpp` 明文:非 fan 型別會忽略 min/max,
  而且會印 `Non-fan types ignore min value specified`。

### `fan0`(風扇)

```json
{ "name": "fan0", "type": "fan",
  "readPath": "/tmp/sys/fan0_input",
  "writePath": "/tmp/sys/pwm0",
  "min": 0, "max": 255, "timeout": 0 }
```

**⚠️ 這台 QEMU 上沒有任何風扇硬體。** 實測:
`/sys/class/pwm/` 是空的、`/sys/class/hwmon/*/pwm*` 不存在、
D-Bus 的 `/xyz/openbmc_project/sensors/` 底下**一顆 `fan_tach` 都沒有**。
但 swampd 的地雷是「**每個 zone 至少要有一顆風扇 ＋ 一顆溫感,否則起不來**」。

**解法:利用 `find("/sys/")` 是子字串比對這件事**,把路徑指到 `/tmp/sys/...`。
它含有 `/sys/`,所以被判定成 `SYSFS`,而 `SysFsRead` / `SysFsWrite` 的實作
就是單純的 `ifstream` / `ofstream` —— **對普通檔案完全適用**。

- `readPath` **不可以留空**:留空會走 `default:` 建出 `WriteOnly`,
  而 `WriteOnly::read()` 是 `throw std::runtime_error("Not supported.")`。
- `min: 0, max: 255` → 因為 `max > 0`,`builder.cpp` 選 `SysFsWritePercent`,
  寫入值 = `min + (max-min) × value`。而 `pid/fancontroller.cpp` 在寫之前做
  `percent /= 100.0`,所以 fan PID 的 `outLim` 單位是**百分比 0~100**。
  **實測印證:** failsafe 100% → 檔案內容 `255`;正常 30% → `76`(= 255×0.3)。
  0~255 就是 hwmon pwm 的慣例值域。
- `timeout: 0` → 永不 stale。假的 tach 值不會自己更新,設 0 才不會一直拖進 failsafe。

> **誠實標註(README 與圖說都要寫):** 這顆風扇是**檔案背板的替身**,
> 不是真實硬體。它證明的是「swampd 的寫出路徑有被執行、值是多少」,
> **不是**「風扇真的轉了」。

---

## 2. `zones[]`

依據 `pid/buildjson.cpp`。必填:`id`、`minThermalOutput`、`failsafePercent`、`pids`。

| 欄位 | 值 | 為什麼 |
|---|---|---|
| `id` | `0` | log 檔名會用它:`zone_0.log` |
| `minThermalOutput` | `3000.0` | zone 輸出的下限(RPM)。`zone.cpp` 會把 `_maximumSetPoint` 至少拉到這個值,requester 標成 `Minimum` —— **實測 log 第一欄之後就是 `3000,Minimum`** |
| `failsafePercent` | `100.0` | 任一感測器 stale 時風扇的 PWM 百分比。**實測 die0 逾時後 `pwm0` 變 255** |

**沒有寫的兩個欄位(刻意):** `cycleIntervalTimeMS`、`updateThermalsTimeMS`。
不寫的話 swampd 會印:
```
Zone 0: cycleIntervalTimeMS cannot find setting. Use default 100 ms
Zone 0: updateThermalsTimeMS cannot find setting. Use default 1000 ms
```
**這兩行本身就是「swampd 是串級控制器」的證據** —— 內圈風扇迴路 100 ms(10 Hz),
外圈熱迴路 1000 ms(1 Hz)。先讓它印預設值,W6 要調的時候再顯式寫進來。

---

## 3. `pids[]` —— 為什麼有兩個

**這不是巧合,swampd 是串級(cascade)控制器,不是單迴路。**

```
   die0 溫度 (1 Hz 更新)
        │
        ▼
   ┌──────────────┐   RPM setpoint   ┌──────────────┐   PWM
   │  熱 PID       │ ───────────────▶ │  風扇 PID     │ ──────▶ /tmp/sys/pwm0
   │  type: temp   │  (zone 內取 max) │  type: fan    │
   │  ts = 1.0 s   │                  │  ts = 0.1 s   │
   └──────────────┘                   └──────▲───────┘
                                             │ tach 讀回 (/tmp/sys/fan0_input)
                                             └──────────────
```

| PID | `setpoint` | `outLim` | 單位 | 說明 |
|---|---|---|---|---|
| `die0`(外圈) | `65.0` | 3000 ~ 15000 | **RPM** | 目標溫度 65 °C,輸出是「我要多少轉速」 |
| `fan0`(內圈) | `0.0` | 30 ~ 100 | **百分比** | setpoint 由 zone 在執行時餵(外圈的輸出),設定檔這格不生效 |

**係數全 0 的後果(而且是預期的):** 熱 PID 輸出被箝到 `outLim_min = 3000`,
zone 取 `max(3000, minThermalOutput)` = 3000;風扇 PID 輸出被箝到
`outLim_min = 30`(%),寫出 `255 × 0.30 = 76`。
**PWM 不會隨溫度變化 —— 這正是本週要的:先證明路是通的,再來談控制行為。**

---

## 4. 部署方式(唯讀 rootfs 的正解)

OpenBMC 的 `/` 是唯讀 squashfs,`/usr/share` 改不動。**不要 `chmod` 硬幹。**
正解是 systemd drop-in:`config/systemd/phosphor-pid-control-override.conf`。

⚠️ **`ExecStartPre` 不是可有可無的。** `--log` 的目錄與風扇的假 sysfs 檔都在
`/tmp`(tmpfs),**重開機就消失**;drop-in 在 `/etc` 卻是持久的。
兩者壽命不一致的結果是「重開機後 swampd 永遠起不來」,而且因為上游是
`Restart=always` + `StartLimitInterval=0`,它會變成無窮重啟風暴。
**踩過了,見 `LOG.md` 2026-08-05。**
