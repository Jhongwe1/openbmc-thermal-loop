# `ThermalLoopDemo.json` —— 每一個欄位為什麼那樣填

> **這份設定做的事:** 讓上游的 `entity-manager` 在 D-Bus 上宣告一塊「板子」,
> 板子上掛一顆 TMP421 溫度晶片。這樣上游的 `hwmontempsensor` 才會去建立感測器,
> 而且**自動幫感測器掛上 association** —— 那是 Redfish 看得見它的唯一條件。

依據:`entity-manager` @ `8c72d191bd`、`dbus-sensors` @ `fc2953c5fa`
(＝ `images/bletchley/image.manifest` 釘的版本),親自讀
`entity_manager/main.cpp`、`entity_manager/configuration.cpp`、`utils.cpp`、
`dbus-sensors/src/Utils.cpp`、`src/hwmon-temp/HwmonTempMain.cpp`。

---

## 0. ★ 為什麼不是計畫寫的 route (b)

計畫要走 `dbus-sensors` 的 **`ExternalSensor`**(設定 `"Type": "ExternalSensor"`,
值由外部 `busctl set-property` 寫入)。**這個映像裡沒有那支程式。**

```
/usr/libexec/dbus-sensors/  →  adcsensor  fansensor  hwmontempsensor  psusensor
```

根因不是建置失誤,是上游 vendor layer 的明文決定:

```bitbake
# openbmc/openbmc: meta-facebook/recipes-phosphor/sensors/dbus-sensors_%.bbappend
FACEBOOK_REMOVED_DBUS_SENSORS = " \
    exitairtempsensor \
    external \        ← ★
    intelcpusensor \
    intrusionsensor \
    ipmbsensor \
    mcutempsensor \
"
PACKAGECONFIG:remove = "${FACEBOOK_REMOVED_DBUS_SENSORS}"
```

而上游 `meta-phosphor/.../dbus-sensors_git.bb` 的預設**是有** `external` 的
(已核對映像建置當天 2026-07-27 的版本)。所以這是 Meta 這一層特意拿掉的。

**推論:換映像沒用、換備援平台也沒用。** 這是 layer 層級的長期決定;而依
[`platform-matrix.md`](../../docs/platform-matrix.md),QEMU 開得起來 ∩ 有 swampd
的平台只有 `bletchley` 與 `catalina`,**兩台都是 meta-facebook**。

**所以改走 route (b′):用這台機器上真的存在的 TMP421 晶片。**

---

## 1. `Probe`

```json
"Probe": "TRUE"
```

`Probe` 是「什麼條件成立時,這份設定才生效」。上游 bletchley 自己的設定寫的是
`xyz.openbmc_project.Inventory.Decorator.Asset({'Model': 'Bletchley_FPB_SI7021'})`
—— 要先有一顆 FRU EEPROM 被讀出來、型號對得上,設定才會套用。

`"TRUE"` 是特例:**永遠套用,不比對任何硬體**。這正是 QEMU 上沒有真實 FRU
EEPROM 時的解法。

## 2. `Type` 與 `Name`

```json
"Type": "Board",
"Name": "Thermal Loop Demo"
```

- `Type` 決定物件掛在哪:`/xyz/openbmc_project/inventory/system/**board**/…`
  可選值由 schema 限死(`Board` / `Chassis` / `Cpu` / `NVMe` / …)。
- `Name` 的空白會被換成底線 → `…/board/Thermal_Loop_Demo`。

**★ 副作用(而且是我們要的副作用):** bmcweb 把帶有
`xyz.openbmc_project.Inventory.Item.Board` 介面的 inventory 物件列成 Redfish
的 Chassis。所以這份設定同時產生了 **`/redfish/v1/Chassis/Thermal_Loop_Demo`**。
感測器就掛在這個 chassis 底下。

## 3. `Exposes[0]` —— 那顆 TMP421

```json
{ "Type": "TMP421", "Bus": 0, "Address": "0x4f", "Name": "die0", "Thresholds": [...] }
```

| 欄位 | 值 | 為什麼 |
|---|---|---|
| `Type` | `TMP421` | 必須是 `hwmontempsensor` 支援清單裡的字串。清單在 `HwmonTempMain.cpp` 的 `sensorTypes`,共 37 種 |
| `Bus` / `Address` | `0`、`0x4f` | **這是比對鍵。** `hwmontempsensor` 掃 `/sys/class/hwmon/*`,從裝置目錄名(如 `0-004f`)解出 bus 與位址,再回頭找有沒有哪份 EM 設定的 `Bus`+`Address` 對得上。對得上才建感測器 |
| `Name` | `die0` | 綁 **`temp1_input`**(本地通道)。若要再開 `temp2_input`,加 `Name1` |
| `Thresholds` | 80 / 95 | 只設上限。**不要設下限** —— 這台 QEMU 的 tmp421 開機讀值是 0 °C,設了下限會一開機就告警 |

> **⚠️ 這顆是真的存在的晶片,不是我捏造的。** `bletchley-bmc` 這個 QEMU machine
> 建了 10 顆 tmp421(i2c-0~5、9、10 的 0x4f,i2c-12 的 0x4c/0x4d),
> guest 裡的 Linux `tmp421` driver 已經綁上去了。
> 裝置樹路徑:`/ahb/apb/bus@1e78a000/i2c@80/tmp421@4f`。
>
> **誠實標註:** 它叫 `die0` 是我的**建模選擇**(拿它當 die 溫度的代理),
> 物理上它是板上的一顆溫度晶片。這件事在 README 與圖說都要寫。

## 4. ★ 部署到哪 —— 計畫寫錯了

計畫說 `/usr/share/entity-manager/configurations/` 是唯讀,要用 **bind mount 或
systemd drop-in**。**兩個都不必。**

讀 `entity_manager/main.cpp` 第 13~15 行:

```cpp
const std::vector<std::filesystem::path> configurationDirectories = {
    PACKAGE_DIR "configurations", SYSCONF_DIR "configurations"};
```

`entity-manager` 掃**兩個**目錄。第二個 `SYSCONF_DIR` 由 meson 定義為
`${prefix}/${sysconfdir}/${project_name}` = **`/etc/entity-manager/`**,
而 `/etc` 在 OpenBMC 上是可寫的 overlay。

```bash
ssh -p 2222 root@127.0.0.1 'mkdir -p /etc/entity-manager/configurations'
scp -P 2222 config/entity-manager/ThermalLoopDemo.json \
    root@127.0.0.1:/etc/entity-manager/configurations/
ssh -p 2222 root@127.0.0.1 'systemctl restart xyz.openbmc_project.EntityManager'
```

**實測:重開機之後設定還在,感測器自己回來。**

> **★ 額外收穫:`utils.cpp` 的 `findFiles()` 用 `std::map` 以「檔名」為鍵。**
> 後掃到的目錄會覆蓋先掃到的。所以在 `/etc/entity-manager/configurations/` 放一個
> **同名**檔案,就能覆蓋 `/usr/share` 裡原廠的那一份 —— 這是唯讀 rootfs 上
> 「改廠商設定」的正解。

## 5. 怎麼確認它真的生效(三段分割法)

```bash
# 第一段:D-Bus 上有沒有這個物件
busctl call xyz.openbmc_project.ObjectMapper /xyz/openbmc_project/object_mapper \
  xyz.openbmc_project.ObjectMapper GetSubTreePaths sias \
  /xyz/openbmc_project/sensors 0 1 xyz.openbmc_project.Sensor.Value

# 第二段:誰 own 它、有哪些介面
busctl call xyz.openbmc_project.ObjectMapper /xyz/openbmc_project/object_mapper \
  xyz.openbmc_project.ObjectMapper GetObject sas \
  /xyz/openbmc_project/sensors/temperature/die0 0

# ★ 第三段:association(最常見的根因)
busctl get-property xyz.openbmc_project.HwmonTempSensor \
  /xyz/openbmc_project/sensors/temperature/die0 \
  xyz.openbmc_project.Association.Definitions Associations
```

實測第三段回:

```
a(sss) 1 "chassis" "all_sensors" "/xyz/openbmc_project/inventory/system/board/Thermal_Loop_Demo"
```

這一串是 `dbus-sensors/src/Utils.cpp` 的 `createInventoryAssoc()` 建的:
它拿設定物件的**父路徑**當 inventory,再用 `findContainingChassis()` 找 chassis。
我們的設定物件是 `…/board/Thermal_Loop_Demo/die0`,父路徑就是那塊 board 本身,
而 board 有 `Inventory.Item.Board` 介面 → chassis 就是它自己。

ObjectMapper 收到之後產生反向物件:

```
/xyz/openbmc_project/inventory/system/board/Thermal_Loop_Demo/all_sensors
  endpoints = ["/xyz/openbmc_project/sensors/temperature/die0"]
```

**bmcweb 查的就是這個 `all_sensors`。** 缺了它,感測器在 `busctl` 看得到、
在 Redfish 就是孤兒 —— 這正是 W2 那顆 route (a) `die0` 的下場。
