# Redfish schema 實測筆記

- 日期:**2026-08-05**
- 映像:`obmc-phosphor-image-bletchley-20260728025045.static.mtd`
- QEMU:11.0.1(Jenkins 版),machine `bletchley-bmc`
- Redfish 版本:`1.17.0`

---

## 1. 我這台支援哪一套

**Chassis id 不是 `chassis`。** 這台是 `Bletchley_Front_Panel_Board`,
而且 `Members@odata.count` 只有 1。**每個平台都不一樣,腳本不可寫死。**

| 路徑 | 結果 |
|---|---|
| `/redfish/v1/Chassis/Bletchley_Front_Panel_Board/Thermal`(舊) | ❌ `Base.1.19.ResourceNotFound` |
| `…/ThermalSubsystem`(新) | ✅ `#ThermalSubsystem.v1_0_0.ThermalSubsystem` |
| `…/Power`(舊) | ❌ `Base.1.19.ResourceNotFound` |
| `…/PowerSubsystem`(新) | ✅ `#PowerSubsystem.v1_1_0.PowerSubsystem` |
| `…/Sensors` | ✅ `#SensorCollection.SensorCollection`,但 **`Members@odata.count` = 0** |
| `…/ThermalSubsystem/Fans` | ✅ `#FanCollection.FanCollection`,**count = 0** |

**結論:這個映像只編了新 schema,舊的 `Thermal`/`Power` 沒有編進去。**

---

## 2. 為什麼要驗兩套

【查】DMTF 在 **Redfish 2020.4** 釋出中,於 **`Chassis` schema v1.15** 新增
`ThermalSubsystem` 與 `PowerSubsystem`,同時把 `Thermal` 與 `Power` 標為
**Deprecated**,讀值統一收到 `Sensors` collection。

| 舊(已棄用) | 新 |
|---|---|
| `Thermal` | `ThermalSubsystem` + `Fan` + `EnvironmentMetrics` |
| `Power` | `PowerSubsystem` + `PowerSupply` + `PowerSupplyMetrics` + `EnvironmentMetrics` |
| (讀值散在各處) | 統一到 `Sensors` collection |

bmcweb **兩套都實作**,用 meson build option 控制是否編入 ——
所以「這台支援哪一套」是**建置期決定的**,不是規格決定的。

> ⚠️ **「舊版即將於 2026 年底全面移除」這句話沒有依據,不要引用。**
> **Deprecated 沒有公布移除時程**,DMTF 的 schema 相容性政策也不輕易移除。

**現場的機器世代是混的,所以工具要同時支援兩套。這是真實的相容性問題。**

---

## 3. ★ 我的 external sensor 出現在 Redfish 了嗎

> 📌 **這一節是 W2 的紀錄,講的是 route (a)。**
> **W3 之後 `die0` 走的是 route (b′)**(真的 tmp421 → hwmon → `dbus-sensors`),
> 而且**在 Redfish 上看得到了** —— 因為 `hwmontempsensor` 會建 association。
> 這一節的結論(**bmcweb 靠 association 決定感測器屬於哪個 Chassis**)
> 正是那次改動的依據,所以留著。現行路徑見
> [`devicetree-to-dbus.md`](devicetree-to-dbus.md)。
>
> ⚠️ 底下那幾條 `busctl ... /xyz/openbmc_project/extsensors/...` 指令
> **在現在的設定上會回 `Unknown object`** —— 那個物件只有走 route (a) 時才存在
> (swampd 依設定檔自己建的)。現在要注入溫度用
> `./tools/set_die_temp.py <溫度> --verify`。

**沒有。而且比預期更徹底 —— 整個 `Sensors` collection 是空的。**

我用 route (a) 建的 `die0`:

- ✅ D-Bus 上**存在**:`busctl get-property xyz.openbmc_project.Hwmon.external
  /xyz/openbmc_project/extsensors/temperature/die0 xyz.openbmc_project.Sensor.Value Value`
  回 `d 80`
- ✅ **ObjectMapper 找得到**:`GetSubTreePaths /xyz/openbmc_project/extsensors 0 1
  xyz.openbmc_project.Sensor.Value` → `as 1 "/xyz/openbmc_project/extsensors/temperature/die0"`
- ❌ **Redfish 看不到**

**但更值得注意的是:D-Bus 上另外有六顆 `nvme1`~`nvme6` 與一顆
`Virtual_Inlet_Temp`,它們是上游 daemon 建的,一樣沒有出現在 Redfish。**

### 根因

【查】bmcweb **不掃描**所有 `/xyz/openbmc_project/sensors/**`。
它靠 **ObjectMapper association** 決定「這顆感測器屬於哪個 Chassis」。
`openbmc/docs` 的 `architecture/sensor-architecture.md` 定義兩組:

| 正向 | 反向 | 意義 |
|---|---|---|
| `chassis` | `all_sensors` | 感測器 ↔ Chassis |
| `inventory` | `sensors` | 感測器 ↔ 硬體 inventory item |

`dbus-sensors` 用 `createInventoryAssoc()` 建立這些關聯。
**自己的服務要出現在 Redfish,必須實作
`xyz.openbmc_project.Association.Definitions`,`Associations` 屬性型別 `a(sss)`。**

**在這台 QEMU 上,連上游的感測器都沒有掛上唯一那個 Chassis
(`Bletchley_Front_Panel_Board`)** —— 因為那顆 chassis 是前面板,而
entity-manager 在 QEMU 上沒有真的 FRU EEPROM 可以 probe,inventory 是不完整的。

**這就是 W3 要做 route (b) 的理由:走 entity-manager + `"Probe": "TRUE"`,
才會有完整的 association 鏈,感測器才會真的出現在 Redfish。**

### 除錯流程:感測器 `busctl` 看得到、Redfish 看不到

**三段分割法**,每一段各有一條兩秒跑得完的指令:

| 段 | 要回答的問題 | 怎麼查 |
|:--:|---|---|
| 1 | D-Bus 上有沒有這個物件與 `Sensor.Value` 介面? | `busctl introspect` |
| 2 | ObjectMapper 找不找得到? | `GetSubTreePaths` |
| 3 | 有沒有 `chassis` / `all_sensors` association? | `busctl get-property … Associations` |

**先驗第 3 段。** 前兩段各花兩秒但幾乎不會錯;第 3 段才是最常見的根因 ——
bmcweb 靠 association 把感測器掛到 Chassis 底下,缺了它感測器就是孤兒。

★ **而且要連上游的感測器一起查,不要只查自己那一顆。**
本次實測:不只自建的那顆不見,`nvme1`~`nvme6` 與 `Virtual_Inlet_Temp` 也不見 ——
那一下就把問題從「我的服務寫錯了」改判成「這台機器的 inventory 本來就不完整」
(QEMU 沒有真的 FRU EEPROM 給 entity-manager probe)。
**只驗自己那一顆,會往錯的方向查兩天。**

---

## 4. 本次實測用的指令

```bash
C="curl -sk -u root:0penBmc https://127.0.0.1:2443"
CH=$($C/redfish/v1/Chassis | jq -r '.Members[0]."@odata.id"')   # ← 不要寫死
$C$CH/Thermal            | jq
$C$CH/ThermalSubsystem   | jq
$C$CH/Power              | jq
$C$CH/PowerSubsystem     | jq
$C$CH/Sensors            | jq
$C$CH/ThermalSubsystem/Fans | jq
```

---

## 5. ★ 2026-08-06 更新:感測器出現在 Redfish 了(route b′)

`Sensors` collection 不再是空的。做法**不是**計畫寫的 route (b)
(那支 daemon 不在這個映像裡,根因見 `config/entity-manager/README.md` §0),
而是用 entity-manager 宣告一塊 board + 一顆**真的存在**的 TMP421,
交給上游 `hwmontempsensor` 建立感測器。

### 實測結果

```bash
$ C="curl -sk -u root:0penBmc https://127.0.0.1:2443"
$ $C/redfish/v1/Chassis | jq -r '.Members[]."@odata.id"'
/redfish/v1/Chassis/Bletchley_Front_Panel_Board
/redfish/v1/Chassis/Thermal_Loop_Demo          ← ★ 新的,由我的 EM 設定產生
```

```json
{
  "@odata.id": "/redfish/v1/Chassis/Thermal_Loop_Demo/Sensors/temperature_die0",
  "@odata.type": "#Sensor.v1_11_1.Sensor",
  "Id": "temperature_die0",
  "Name": "die0",
  "Reading": 79.938,
  "ReadingRangeMax": 127.0,
  "ReadingRangeMin": -128.0,
  "ReadingType": "Temperature",
  "ReadingUnits": "Cel",
  "Status": { "Health": "OK", "State": "Enabled" },
  "Thresholds": {
    "UpperCaution":  { "Reading": 80.0 },
    "UpperCritical": { "Reading": 95.0 },
    "LowerCaution":  { "Reading": null },
    "LowerCritical": { "Reading": null }
  }
}
```

### ★ 三個計畫沒講、實測才知道的細節

| # | 細節 | 為什麼重要 |
|---|---|---|
| 1 | **Redfish 的 `Id` 是 `temperature_die0`,不是 `die0`** | bmcweb 用 `<型別>_<名字>` 當 id。計畫寫的 `/Sensors/die0` 會 404。**腳本不可寫死,要從 `Sensors` collection 讀回來** |
| 2 | **多了一個 Chassis** | 我的 EM 設定 `"Type": "Board"` 產生 `Inventory.Item.Board` 物件,bmcweb 就把它列成一個 Chassis。感測器掛在**我的** chassis 底下,不是原本那顆前面板 |
| 3 | **`ReadingRangeMin/Max` 是 −128/127** | 那是 tmp421 的量程,由 `hwmontempsensor` 填。**這兩個數字在 swampd 那邊會被拿去做 [0,1] 正規化** —— 見 `LOG.md` 2026-08-06 第三則 |

### 上游那七顆感測器仍然看不到 —— 而這正好印證了 §3 的根因

`nvme1`~`nvme6`(`xyz.openbmc_project.nvme.manager`)與 `Virtual_Inlet_Temp`
(`xyz.openbmc_project.VirtualSensor`)**到今天還是不在任何 Chassis 的
`Sensors` 底下**。`busctl introspect` 顯示它們**沒有
`xyz.openbmc_project.Association.Definitions` 介面**。

**同一台機器上,有 association 的出現在 Redfish、沒有的沒出現 —— 這是對照組。**
§3 那句「缺了 association 感測器就是孤兒」在 2026-08-05 還只是「讀文件得到的推論」,
2026-08-06 變成**同機對照的實測結論**。
