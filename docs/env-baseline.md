# 環境基線(env-baseline)

> 這份文件記錄「我在什麼東西上面量的」。所有數字與圖都要能對回這裡的版本。
> 產生日期:2026-07-28

## 開發環境

| 項目 | 值 | 怎麼查 |
|---|---|---|
| 主機 OS | Windows 11 (10.0.26200) | `winver` |
| 開發環境 | WSL2 / Ubuntu 24.04 | `wsl -l -v` |
| WSL 版本 | 2.6.3.0 | `wsl --version` |
| PID 1 | `systemd`(已在 /etc/wsl.conf 開啟 systemd) | `ps -p 1 -o comm=` |
| systemd 狀態 | `running` | `systemctl is-system-running` |
| 核心 | `6.6.87.2-microsoft-standard-WSL2` | `uname -r` |

## 工具鏈

| 工具 | 版本 |
|---|---|
| gcc | gcc (Ubuntu 13.3.0-6ubuntu2~24.04.1) 13.3.0 |
| meson | 1.3.2 |
| ninja | 1.11.1 |
| dtc | Version: DTC 1.7.0 |
| Python | Python 3.12.3 |
| numpy / scipy / matplotlib | 2.5.1 1.18.0 3.11.1 |
| Robot Framework | Robot Framework 7.4.2 (Python 3.12.3 on linux) |

## QEMU

| | 版本 | 用途 |
|---|---|---|
| Ubuntu 24.04 內建 | `QEMU emulator version 8.2.2 (Debian 1:8.2.2+ds-0ubuntu1.17)` | **不使用**(缺 catalina-bmc / gb200nvl-bmc) |
| **實際採用** | `QEMU emulator version 11.0.1 (v11.0.1-3179-g9c2fa9d4b4)` | OpenBMC Jenkins 每日建置,放在 `~/bin` |

Jenkins 版下載位址:
<https://jenkins.openbmc.org/job/latest-qemu-x86/lastSuccessfulBuild/artifact/qemu/build/qemu-system-arm>

## ★ 映像版本釘選(W5 meson wrap 與 W7 圖說明要引用)

主線映像:`obmc-phosphor-image-bletchley-20260728025045.static.mtd`
映像大小:56M

| 套件 | 版本字串 | git hash |
|---|---|---|
| `phosphor-pid-control` | `0.1+git0+c5e59550d3-r1` | `c5e59550d3` |
| `dbus-sensors` | `0.1+git0+fc2953c5fa-r0` | `fc2953c5fa` |
| `entity-manager` | `0.1+git0+8c72d191bd-r0` | `8c72d191bd` |
| `bmcweb` | `1.0+git0+e05fbc0500-r0` | `e05fbc0500` |
| `phosphor-hwmon` | `1.0+git0+100f95a32b-r1` | `100f95a32b` |
| `phosphor-virtual-sensor` | `0.1+git0+0dd6fc7866-r1` | `0dd6fc7866` |
| `phosphor-fan-control` | `1.0+git0+3fb6d9f474-r1` | `3fb6d9f474` |

**★ `phosphor-pid-control` 的 git hash 是本專案最重要的一個版本號。**
W5 建立 `subprojects/phosphor-pid-control.wrap` 時要釘死它,
W7 的 anti-windup A/B 圖說明要寫它——否則「我跟上游 `ec::pid()` 逐步比對過」
這句話沒有可查證的對象。

## 平台選擇

見 [`platform-matrix.md`](platform-matrix.md)。結論:主線 `bletchley`,備援 `catalina`。

## 四個 target 的套件對照(實測)

| 套件 | `bletchley` | `catalina` | `gb200nvl-obmc` | `romulus` |
|---|:---:|:---:|:---:|:---:|
| `phosphor-pid-control`(swampd) | ✅ | ✅ | ❌ | ❌ |
| `dbus-sensors` | ✅ | ✅ | ✅ | ❌ |
| `entity-manager` | ✅ | ✅ | ✅ | ❌ |
| `bmcweb` | ✅ | ✅ | ✅ | ✅ |
| `phosphor-hwmon` | ✅ | ✅ | ✅ | ✅ |
| `phosphor-virtual-sensor` | ✅ | ✅ | ❌ | ❌ |
| `phosphor-fan-control` | ✅ | ✅ | ❌ | **✅** |

### ★ 值得注意的一格:`romulus` 有 `phosphor-fan-control` 卻沒有 `phosphor-pid-control`

OpenBMC 有**兩套互不相同的風扇控制堆疊**:

| | `phosphor-pid-control`(swampd) | `phosphor-fan-control` |
|---|---|---|
| 出身 | Intel 系 | IBM / OpenPOWER 系 |
| 設定 | JSON(`/usr/share/swampd/config.json`)或 entity-manager | YAML 產生的 C++ |
| 本專案 | **這一套是主體** | 不使用 |

所以「這台有沒有風扇控制」不是一個是非題——**要問的是「哪一套」**。
`romulus` 與 `p10bmc` 走的是後者,因此即使它們能開機,也不能拿來做本專案。

---

# 十分鐘體檢:判讀結論

執行日期:2026-07-28　執行指令:`SSH_PORT=2222 ./harness/qemu/healthcheck.sh`
映像:`obmc-phosphor-image-bletchley-20260728025045.static.mtd`
OS:`Phosphor OpenBMC 3.1.0-dev-739-gba9070d60b`(BUILD_ID `20260728025045`)
Kernel:`6.18.40-c2b9fc3 armv7l`　QEMU:`11.0.1` / machine `bletchley-bmc`

| # | 項目 | 結果 | 對本專案的意義 |
|:--:|---|---|---|
| 1 | 熱控 daemon | `swampd` **存在且 active**;`phosphor-fan-control@0` **也 active** | ✅ 兩套堆疊都裝了。本專案用 `phosphor-pid-control` |
| 2 | swampd 設定來源 | `/usr/share/swampd/config.json` **不存在**;`/usr/share/entity-manager/configurations/` 有大量廠商目錄 | **設定走 entity-manager(D-Bus),不是檔案**。這決定 W2/W3 怎麼注入設定 |
| 3 | 感測器 D-Bus 服務 | `HwmonTempSensor` / `FanSensor` / `ADCSensor` / `PSUSensor` / `VirtualSensor` / `EntityManager` 全在 | ✅ Gate 1 的觀測鏈完整 |
| 4 | 現有溫度感測器 | 9 個,含 `Virtual_Inlet_Temp`、`nvme1`~`nvme6` | 都是 virtual sensor;實體溫度要靠 `extsensors` 或 EM 設定注入 |
| 5 | 風扇控制 zone | `/xyz/openbmc_project/settings/fanctrl` 底下**沒有任何 zone** | ⚠️ **見第 13 項** |
| 6 | hwmon 實體 | 17 個:`tmp421` ×8、`tcpm_source_psy_*` ×6、`iio_hwmon` ×1 | Fig 6(W5)要從這裡往上追到 D-Bus |
| 7 | Redfish Chassis | `/redfish/v1/Chassis/**Bletchley_Front_Panel_Board**` | ⚠️ **id 不是 `chassis`**,腳本不可寫死 |
| 8 | Redfish `Thermal`(舊) | ❌ `Base.1.19.ResourceNotFound` | 這個映像**沒有**編舊 schema |
| 9 | Redfish `ThermalSubsystem`(新) | ✅ `#ThermalSubsystem.v1_0_0` | **本專案走新 schema**,README 要標註 |
| 10 | Redfish Sensors collection | 存在但 **Members 是空的** | 與第 5 項同源:還沒有東西被關聯上去 |
| 11 | 檔案系統 | `/` **唯讀**(`rootfs ro`);`/etc`、`/var` 是 **overlay 可寫**;`/usr/share` 唯讀 | **設定必須放 `/etc`,並用 systemd drop-in 指過去**(W2 會用到) |
| 12 | 開機耗時 | **149.7 秒**(kernel 22.3s + userspace 127.4s) | `systemd-analyze` **不在此映像**,改用 `systemctl show` 的 `FinishTimestampMonotonic`(微秒) |
| 13 | **★ swampd 實際狀態** | **`No fan zones, application pausing until new configuration`** | **★★ 這是整個專案的起點** |

## ★ 最重要的一行

```
Jul 28 09:53:12 bletchley swampd[1729]: No fan zones, application pausing until new configuration
```

`swampd` 有在跑,但它**沒有拿到任何風扇 zone 設定**,所以它印完這行就停在那裡等。

所以 Gate 1 的任務不是「讓 swampd 跑起來」——它已經跑起來了——而是**給它一份設定**。
這也解釋了第 5 項(沒有 zone 物件)與第 10 項(Sensors collection 是空的):
三者是同一件事的三個面向。

## 幾個會影響後續設計的決定

| 觀察 | 後續怎麼做 |
|---|---|
| 設定走 entity-manager 而非 `config.json` | W3 要寫 `config/entity-manager/ThermalLoopDemo.json`;W2 的 route (a) 先用 `extsensors` 走捷徑 |
| `/usr/share` 唯讀 | 設定放 `/etc`,用 `systemd drop-in`(`config/systemd/phosphor-pid-control.service.d/override.conf`)指過去 |
| 只有 `ThermalSubsystem`,沒有 `Thermal` | README 與 `docs/redfish-notes.md` 只描述新 schema,**不要**寫「舊 schema 將被移除」(它只是 deprecated,沒有移除時程) |
| 開機 149.7 秒 | 這是 **QEMU 上的數字**,不是真實硬體。任何引用都要標明是模擬環境 |

---

# 原始體檢輸出(未經編輯)

```

=== 0. 身分與版本 ===
Linux bletchley 6.18.40-c2b9fc3 #1 SMP Mon Jul 27 02:33:15 UTC 2026 armv7l GNU/Linux

ID=openbmc-phosphor
NAME="Phosphor OpenBMC (Phosphor OpenBMC Project Reference Distro)"
VERSION="3.1.0-dev"
VERSION_ID=3.1.0-dev-739-gba9070d60b
VERSION_CODENAME="styhead"
PRETTY_NAME="Phosphor OpenBMC (Phosphor OpenBMC Project Reference Distro) 3.1.0-dev"
CPE_NAME="cpe:/o:openembedded:openbmc-phosphor:3.1.0-dev-739-gba9070d60b"
BUILD_ID="20260728025045"
OPENBMC_TARGET_MACHINE="bletchley"
EXTENDED_VERSION="3.1.0-dev-739-gba9070d60b"

=== 1. 熱控 daemon(兩套堆疊都看) ===
-rwxr-xr-x    1 root     root        952992 Mar  9  2018 /usr/bin/swampd
● phosphor-pid-control.service - Phosphor-Pid-Control Margin-based Fan Control Daemon
     Loaded: loaded (/usr/lib/systemd/system/phosphor-pid-control.service; enabled; preset: enabled)
    Drop-In: /usr/lib/systemd/system/phosphor-pid-control.service.d
             └─10-bletchley.conf
     Active: active (running) since Tue 2026-07-28 09:53:04 PDT; 4min 19s ago
 Invocation: a1107811c520446da8aa68d797483bb5
● phosphor-fan-control@0.service - Phosphor Fan Control Daemon
     Loaded: loaded (/usr/lib/systemd/system/phosphor-fan-control@.service; static)
     Active: active (running) since Fri 2026-03-13 08:35:54 PDT; 4 months 15 days ago
 Invocation: 1ba37ffd8c9840e5bf99ff6435139bfa
   Main PID: 684 (phosphor-fan-co)
        CPU: 184ms

=== 2. swampd 設定來源(檔案 or entity-manager D-Bus) ===
ls: /usr/share/swampd/config.json: No such file or directory
3y-power
acbel
amd
ampere
aspower
asrock
axiado
broadcomm
compuware
delta
flextronics
foxconn-industrial-internet
gigabyte
gospower
hpe
ibm
ieisystem
intel
mbx_systems
mellanox

=== 3. 感測器相關 D-Bus 服務 ===
:1.147                                                 1329 virtual-sensor  root             :1.147        phosphor-virtual-sensor.service                   -       -
:1.162                                                 1493 entity-manager  root             :1.162        xyz.openbmc_project.EntityManager.service         -       -
:1.169                                                 1627 adcsensor       root             :1.169        xyz.openbmc_project.adcsensor.service             -       -
:1.170                                                 1632 fansensor       root             :1.170        xyz.openbmc_project.fansensor.service             -       -
:1.171                                                 1635 hwmontempsensor root             :1.171        xyz.openbmc_project.hwmontempsensor.service       -       -
:1.172                                                 1638 psusensor       root             :1.172        xyz.openbmc_project.psusensor.service             -       -
:1.36                                                   845 sensor-monitor  root             :1.36         sensor-monitor.service                            -       -
xyz.openbmc_project.ADCSensor                          1627 adcsensor       root             :1.169        xyz.openbmc_project.adcsensor.service             -       -
xyz.openbmc_project.EntityManager                      1493 entity-manager  root             :1.162        xyz.openbmc_project.EntityManager.service         -       -
xyz.openbmc_project.FanSensor                          1632 fansensor       root             :1.170        xyz.openbmc_project.fansensor.service             -       -
xyz.openbmc_project.Hwmon.external                     1729 swampd          root             :1.189        phosphor-pid-control.service                      -       -
xyz.openbmc_project.HwmonTempSensor                    1635 hwmontempsensor root             :1.171        xyz.openbmc_project.hwmontempsensor.service       -       -
xyz.openbmc_project.PSUSensor                          1638 psusensor       root             :1.172        xyz.openbmc_project.psusensor.service             -       -
xyz.openbmc_project.State.FanCtrl                      1729 swampd          root             :1.187        phosphor-pid-control.service                      -       -
xyz.openbmc_project.VirtualSensor                      1329 virtual-sensor  root             :1.147        phosphor-virtual-sensor.service                   -       -

=== 4. 現有溫度感測器 ===
as
9
"/xyz/openbmc_project/sensors/airflow/Virtual_CFM_Sensor"
"/xyz/openbmc_project/sensors/power/Virtual_P12V_AUX_HSC_Input_Power"
"/xyz/openbmc_project/sensors/temperature/Virtual_Inlet_Temp"
"/xyz/openbmc_project/sensors/temperature/nvme1"
"/xyz/openbmc_project/sensors/temperature/nvme2"
"/xyz/openbmc_project/sensors/temperature/nvme3"
"/xyz/openbmc_project/sensors/temperature/nvme4"
"/xyz/openbmc_project/sensors/temperature/nvme5"
"/xyz/openbmc_project/sensors/temperature/nvme6"

=== 5. 風扇控制 zone(Manual / FailSafe) ===
└─ /xyz
  └─ /xyz/openbmc_project
    └─ /xyz/openbmc_project/settings
      └─ /xyz/openbmc_project/settings/fanctrl

=== 6. hwmon 實體(Fig 6 要對照) ===
hwmon0
hwmon1
hwmon10
hwmon11
hwmon12
hwmon13
hwmon14
hwmon15
hwmon16
hwmon2
hwmon3
hwmon4
hwmon5
hwmon6
hwmon7
hwmon8
hwmon9
/sys/class/hwmon/hwmon0 -> tmp421
/sys/class/hwmon/hwmon1 -> tmp421
/sys/class/hwmon/hwmon10 -> tcpm_source_psy_0_0022
/sys/class/hwmon/hwmon11 -> tcpm_source_psy_1_0022
/sys/class/hwmon/hwmon12 -> tcpm_source_psy_2_0022
/sys/class/hwmon/hwmon13 -> tcpm_source_psy_3_0022
/sys/class/hwmon/hwmon14 -> tcpm_source_psy_4_0022
/sys/class/hwmon/hwmon15 -> tcpm_source_psy_5_0022
/sys/class/hwmon/hwmon16 -> iio_hwmon
/sys/class/hwmon/hwmon2 -> tmp421
/sys/class/hwmon/hwmon3 -> tmp421
/sys/class/hwmon/hwmon4 -> tmp421
/sys/class/hwmon/hwmon5 -> tmp421
/sys/class/hwmon/hwmon6 -> tmp421
/sys/class/hwmon/hwmon7 -> tmp421
/sys/class/hwmon/hwmon8 -> tmp421
/sys/class/hwmon/hwmon9 -> tmp421

=== 7. Redfish:Chassis 清單 ===
/redfish/v1/Chassis/Bletchley_Front_Panel_Board

=== 8. Redfish:Thermal(已棄用,可能不存在) ===
Base.1.19.ResourceNotFound

=== 9. Redfish:ThermalSubsystem(新) ===
#ThermalSubsystem.v1_0_0.ThermalSubsystem

=== 10. Redfish:Sensors collection ===

=== 11. 檔案系統可寫性(先看掛載旗標，再實際試寫) ===
rootfs / rootfs ro 0 0
tmpfs /run tmpfs rw,nosuid,nodev,mode=755 0 0
overlay /var overlay rw,relatime,lowerdir=/var,upperdir=/run/mnt-persist/var-data,workdir=/run/mnt-persist/var-work,uuid=on 0 0
overlay /etc overlay rw,relatime,lowerdir=/etc,upperdir=/run/mnt-persist/etc-data,workdir=/run/mnt-persist/etc-work,uuid=on 0 0
---
/etc 可寫
/usr/share 唯讀 ← 設定放 /etc，用 systemd drop-in 指過去

=== 12. 開機耗時 ===
KernelTimestampMonotonic=0
UserspaceTimestampMonotonic=22289983
FinishTimestampMonotonic=149666213

=== 13. ★ swampd 目前的實際狀態(本專案的起點) ===
Jul 28 09:53:04 bletchley systemd[1]: Started Phosphor-Pid-Control Margin-based Fan Control Daemon.
Jul 28 09:53:12 bletchley swampd[1729]: No fan zones, application pausing until new configuration
```
