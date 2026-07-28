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
