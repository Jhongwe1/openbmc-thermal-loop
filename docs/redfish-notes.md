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

> ⚠️ **不要說「舊版即將於 2026 年底全面移除」。**
> **Deprecated 沒有公布移除時程**,DMTF 的 schema 相容性政策也不輕易移除。
> 這句話是編的,講出來會被抓。

**現場的機器世代是混的,所以工具要同時支援兩套。這是真實的相容性問題。**

---

## 3. ★ 我的 external sensor 出現在 Redfish 了嗎

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

### 面試題(§13 Q14):「你的感測器 `busctl` 看得到、Redfish 看不到,怎麼查?」

> 「先分段。第一段是 D-Bus 上有沒有這個物件跟 `Sensor.Value` 介面 ——
> `busctl introspect` 兩秒就知道。第二段是 ObjectMapper 找不找得到 ——
> `GetSubTreePaths` 查。第三段是有沒有 `chassis`/`all_sensors` association ——
> bmcweb 靠這個把感測器掛到 Chassis 底下,缺了它感測器就是孤兒。
> **我先驗第三段,因為前兩段各花兩秒但幾乎不會錯,第三段是最常見的根因。**
>
> 我實際查的時候還多發現一件事:**不只我的感測器不見,上游的也不見。**
> 那一下就把問題從「我的服務寫錯了」改判成「這台機器的 inventory 本來就不完整」——
> 因為 QEMU 沒有真的 FRU EEPROM 給 entity-manager probe。
> **如果只驗自己那一顆,我會往錯的方向查兩天。**」

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
