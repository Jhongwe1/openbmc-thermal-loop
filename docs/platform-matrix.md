# 平台決策矩陣

> 這份文件的用途:證明「用哪台機器」是**查出來的**,不是猜的。
> 產生方式:`./harness/qemu/platform_matrix.sh | tee docs/platform-matrix.md`

## 執行環境

- 執行日期:2026-07-28
- 掃描耗時:44 秒(19 個 target,38 次 HTTP 請求)
- 發行版 QEMU(Ubuntu 24.04 內建):`QEMU emulator version 8.2.2 (Debian 1:8.2.2+ds-0ubuntu1.17)`
- **實際採用**:OpenBMC Jenkins 預編譯版 `QEMU emulator version 11.0.1 (v11.0.1-3179-g9c2fa9d4b4)`
  - 來源:<https://jenkins.openbmc.org/job/latest-qemu-x86/lastSuccessfulBuild/artifact/qemu/build/qemu-system-arm>
  - 換版本的理由見下方〈為什麼不用發行版的 QEMU〉

`qemu-system-arm -M help` 中與本專案相關的 machine(Jenkins 11.0.1):

```
ast2600-evb          Aspeed AST2600 EVB (Cortex-A7)
bletchley-bmc        Facebook Bletchley BMC (Cortex-A7)
catalina-bmc         Facebook Catalina BMC (Cortex-A7)
gb200nvl-bmc         Nvidia GB200NVL BMC (Cortex-A7)
rainier-bmc          IBM Rainier BMC (Cortex-A7)
romulus-bmc          OpenPOWER Romulus BMC (ARM1176)
```

## 三個條件的交集才是可用平台

```
{ Jenkins latest-master 有出映像 } ∩ { QEMU 有 machine model } ∩ { 映像含 phosphor-pid-control }
```

三個條件缺一不可,理由:

| 條件 | 缺了會怎樣 |
|---|---|
| Jenkins 有出映像 | 沒有現成映像就要自己跑 Yocto build,那是好幾小時到一整天 |
| QEMU 有 machine model | 映像抓下來也開不起來,`qemu-system-arm -M xxx` 直接報錯 |
| 映像含 `phosphor-pid-control` | **這是本專案的主體**。沒有它,`systemctl status phosphor-pid-control` 會是 not found,整個 Gate 3 歸零 |

## 結論

- **主線:`bletchley`**(QEMU machine `bletchley-bmc`,AST2600 / Cortex-A7)
- **備援:`catalina`**(QEMU machine `catalina-bmc`,AST2600 / Cortex-A7)

**明確排除:**

| target | 為什麼排除 |
|---|---|
| `romulus` | manifest 顯示**沒有** `phosphor-pid-control`、`dbus-sensors`、`entity-manager`。而且 SoC 是 AST2500 / ARM1176,與本專案的 AST2600 目標不同。**做不了本專案。** |
| `gb200nvl-obmc` | QEMU 有 machine,但 manifest **沒有** `phosphor-pid-control`。保留作 Redfish / entity-manager / device tree 探索用。 |
| `p10bmc`(`rainier-bmc`) | 沒有 `phosphor-pid-control`,用的是另一套風扇堆疊。 |
| `anacapa`、`harma`、`minerva`、`ventura`、`ventura2`、`yosemite4`、`yosemite5`、`santabarbara`、`clemente`、`bletchley15` | 映像齊全,但 **QEMU 沒有對應的 machine model**,開不起來。 |
| `evb-npcm845`、`gbs` | 有 `phosphor-pid-control` 但缺 `dbus-sensors` / `entity-manager`,且 QEMU 無對應 machine。 |

## ⚠️ 與參考資料的兩處差異(以本次實測為準)

參考資料寫於 2026-07-27,本次掃描為 2026-07-28,**兩處對不上**:

| 項目 | 參考資料 | 本次實測 | 影響 |
|---|---|---|---|
| `anacapa-bmc` | 標示 ✅ 存在,列為**備援平台** | ❌ **QEMU 11.0.1 中不存在**(搜尋 `anacapa` 無結果) | **備援平台必須改掉**,否則 D5 止損計畫是空的 |
| `catalina-bmc` | 標示 ❌ 無 machine,🔴「QEMU 跑不起來」 | ✅ **存在**,Cortex-A7 | 它成為新的備援 |

`anacapa` 的映像本身是齊全的(五個套件全 ✅),問題純粹在 QEMU 沒有它的 machine model
——這正好說明為什麼「有映像」跟「跑得起來」是**兩個獨立的條件**,必須分開驗。

## 為什麼不用發行版的 QEMU

Ubuntu 24.04 內建的是 QEMU 8.2.2(2024 年初)。實測它**只有** `bletchley-bmc`
與 `romulus-bmc`,沒有 `catalina-bmc` 也沒有 `gb200nvl-bmc`。

主線 `bletchley` 用 8.2.2 是跑得動的,但**備援平台會消失**——而 D5 的止損條件正是
「主線開不起來就換備援」。所以改用 OpenBMC Jenkins 每日建置的 11.0.1。

## ★ OpenBMC 有兩套風扇控制堆疊,不是一套

**「BMC 就是用 PID 控風扇」是錯的。** 上游同時存在兩套彼此獨立的風扇控制實作,
一個平台裝哪一套(或兩套)取決於它的**血統**,不是取決於技術優劣。

| | `phosphor-pid-control`(swampd) | `phosphor-fan-presence` 底下的 control |
|---|---|---|
| 控制範式 | **PID 回授**(串級:熱迴路 1 Hz → 風扇迴路 10 Hz) | **事件驅動**:D-Bus 物件群組 ＋ trigger → action |
| 設定 | `config.json` 或 entity-manager 的 D-Bus | JSON(YAML 已棄用):fans / zones / events / zone_conditions |
| 血統 | Google / Intel 路線 | IBM 路線 |
| 執行檔 | `swampd` | `phosphor-fan-control` |

### 這張矩陣本身就是證據

上表(下一節的掃描結果)提供了三種平台的對照:

| 平台 | `phosphor-pid-control` | `phosphor-fan-control` | 代表什麼 |
|---|:---:|:---:|---|
| **`p10bmc`**(IBM Power10) | **—** | ✅ | **只有事件驅動那套,根本沒裝 swampd** |
| **`romulus`** | **—** | ✅ | 同上(這也是它不能當本專案備援的原因之一) |
| `gbs`、`evb-npcm845` | ✅ | **—** | 反過來:只有 PID 那套 |
| **`bletchley`**(本專案主線) | ✅ | ✅ | **兩套都裝** |

**所以選 `bletchley` 不只是「它有 swampd」,而是「它兩套都有,而我要驗的是 PID 那條」。**

### 【驗】執行時期的確認(2026-08-05,不只看 manifest)

manifest 只證明「**裝了**」。開機之後用 `busctl list` 確認**兩套真的都在跑**:

```bash
ssh -p 2222 root@127.0.0.1 'busctl list --no-pager | grep -iE "fan|thermal"'
```

實測輸出(節錄,服務名與 D-Bus name 都是穩定的;PID 每次開機會變):

| D-Bus name | systemd unit | 屬於哪一套 |
|---|---|---|
| `xyz.openbmc_project.State.FanCtrl` | `phosphor-pid-control.service`(`swampd`) | **PID 回授** |
| `xyz.openbmc_project.Control.Thermal` | `phosphor-fan-control@0.service` | **事件驅動** |
| `xyz.openbmc_project.Thermal.Alert` | `phosphor-fan-monitor@0.service` | 事件驅動(風扇故障監測) |
| — | `phosphor-fan-presence-tach@0.service` | 事件驅動(風扇在位偵測) |

**兩套在同一台機器上同時執行,各自擁有不同的 D-Bus 名稱。**

對應的套件版本(`images/bletchley/image.manifest`):

```
phosphor-pid-control        armv7ahf-vfpv4d16  0.1+git0+c5e59550d3-r1
phosphor-fan-control        bletchley          1.0+git0+3fb6d9f474-r1
phosphor-fan-monitor        bletchley          1.0+git0+3fb6d9f474-r1
phosphor-fan-presence-tach  bletchley          1.0+git0+3fb6d9f474-r1
```

> ⚠️ **`phosphor-pid-control` 的 hash `c5e59550d3` 要記住** —— W5 的 meson wrap 要釘它,
> 否則本機建置的版本與映像裡跑的版本不一致,量到的東西無法宣稱是同一份程式碼。

### 面試講法

> 「OpenBMC 其實有**兩套**風扇控制。`phosphor-pid-control` 是 PID 回授,
> `phosphor-fan-presence` 底下的 control 是事件驅動的 —— 一組 D-Bus 物件配一組
> trigger 跟 action。**IBM 的 p10bmc 用後者,我比對 19 個平台的 manifest 時發現
> 它根本沒裝 swampd**;反過來 `gbs` 只有 swampd 沒有另一套。
> **所以「BMC 怎麼控風扇」沒有唯一答案,要看平台的血統。**
> 我選 `bletchley` 是因為它兩套都裝,而我要驗的是 PID 那條 ——
> 我開機後用 `busctl list` 確認過兩個 daemon 真的都在跑,不只是 manifest 上有。」

---

## 掃描結果(腳本原始輸出)

| target | phosphor-pid-control | dbus-sensors | entity-manager | phosphor-virtual-sensor | phosphor-fan-control |
|---|:---:|:---:|:---:|:---:|:---:|
| `anacapa` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `bletchley` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `bletchley15` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `catalina` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `clemente` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `e3c246d4i` | — | ✅ | ✅ | — | ✅ |
| `evb-npcm845` | ✅ | — | — | — | — |
| `gb200nvl-obmc` | — | ✅ | ✅ | — | — |
| `gbs` | ✅ | — | — | ✅ | — |
| `harma` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `minerva` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `p10bmc` | — | ✅ | ✅ | ✅ | ✅ |
| `romulus` | — | — | — | — | ✅ |
| `sanmiguel` | — | ✅ | ✅ | ✅ | — |
| `santabarbara` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `ventura` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `ventura2` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `yosemite4` | ✅ | ✅ | ✅ | ✅ | ✅ |
| `yosemite5` | ✅ | ✅ | ✅ | ✅ | ✅ |
