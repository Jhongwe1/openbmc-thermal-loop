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
