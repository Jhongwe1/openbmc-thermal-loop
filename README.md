# OpenBMC Closed-Loop Thermal Control Testbed

在 QEMU ASPEED AST2600 上，用上游 `phosphor-pid-control` 建立一條可量測、
可重現的熱控閉環，並**量化上游既有抗飽和機制（anti-windup）的實際效果**。

> 🚧 進行中(2026-07 起)。目前進度:**Gate 0 完成、Gate 1 完成**——
> 一行指令從**模擬硬體層**(QEMU 的 tmp421 晶片模型)改溫度,
> 經 kernel driver → hwmon sysfs → `dbus-sensors` → D-Bus,
> **`busctl`、`swampd` 的 PID 軌跡、Redfish 三個地方同時變**。
> 每一段的行程數與 IPC 次數都量過,見
> [`docs/architecture.md`](docs/architecture.md) 的〈一個溫度值的旅程〉。

## 為什麼做這個

（W10 補完。）

## 目標平台

主線 **`bletchley`**（QEMU `bletchley-bmc`），備援 **`catalina`**（QEMU `catalina-bmc`）。
兩台都是 AST2600 / Cortex-A7。

此選擇來自 `harness/qemu/platform_matrix.sh` 對 19 個 Jenkins target 的實測掃描
（見 [`docs/platform-matrix.md`](docs/platform-matrix.md)）——依據是三個條件的交集：

```
{ Jenkins 有出映像 } ∩ { QEMU 有 machine model } ∩ { 映像含 phosphor-pid-control }
```

`romulus` 與 `gb200nvl-obmc` 明確排除：manifest 顯示它們**沒有**
`phosphor-pid-control`。這一步是查證，不是試錯。

## 架構

見 `docs/architecture.md`。

## 現況

- [x] Gate 0　環境就緒　　　　　　　← [env-baseline.md](docs/env-baseline.md)
- [x] Gate 1　端到端可觀測
  - [x] 一行指令把溫度從 40 改成 80　　← `tools/set_die_temp.py`(QMP → tmp421)
  - [x] `busctl` 看得到 `Value` 變了,且 `swampd` 收得到
        (`pidcore.die0` 的 `input` 欄跟著變,`error = setpoint − input`)
  - [x] Redfish 看到同一變化
        ← `/redfish/v1/Chassis/Thermal_Loop_Demo/Sensors/temperature_die0`
  - [x] 畫得出從指令到 Redfish JSON 經過哪幾個行程、幾次 IPC
        ← [architecture.md](docs/architecture.md)。**實測:一次 Redfish GET =
        3 個 method call(認證 / ObjectMapper / GetAll)+ 3 個回覆,牽涉 5 個行程**
  - [x] 知道**為什麼**有些感測器出現在 Redfish、有些沒有
        ← [redfish-notes.md](docs/redfish-notes.md)。**同機對照組:**
        我這顆有 `chassis`/`all_sensors` association → 看得到;
        上游的 `nvme1`~`nvme6` 沒有 → 看不到

  > ⚠️ **誠實標註(兩件事):**
  > 1. **溫度來自 QEMU 的 tmp421 裝置模型,不是真實硬體。** 它證明的是
  >    「從 i2c 晶片到 Redfish 的整條軟體路徑是通的、每一層讀到什麼值」。
  >    這顆晶片物理上是板上溫感,叫它 `die0` 是我的建模選擇。
  > 2. **這台 QEMU 沒有任何風扇硬體**(`/sys/class/pwm/` 是空的,
  >    D-Bus 上沒有 `fan_tach`)。設定裡的 `fan0` 讀寫的是 `/tmp/sys/` 底下的
  >    **普通檔案**,證明的是「swampd 的寫出路徑被執行了、值是多少」,
  >    **不是「風扇真的轉了」**。理由與做法見
  >    [`config/swampd/README.md`](config/swampd/README.md)。
  >
  > 📌 **計畫原訂的 route (b)(`dbus-sensors` 的 `ExternalSensor`)在這個映像上
  > 不存在** —— `meta-facebook` 的 bbappend 明文 `PACKAGECONFIG:remove`。
  > 根因與替代路線見 [`config/entity-manager/README.md`](config/entity-manager/README.md)。

- [ ] Gate 2　被控對象 + 跨層追蹤
- [ ] Gate 3　控制器與量測
- [ ] Gate 4　失效安全
- [ ] Gate 5　官方測試套件
- [ ] Gate 6　Upstream
- [ ] Gate 7　交付與敘事

## 授權

Apache-2.0（與 OpenBMC 上游一致）。
