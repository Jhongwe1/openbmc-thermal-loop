# 官方 Robot 測試套件(QEMU_CI)執行紀錄

日期:2026-08-12
映像:`obmc-phosphor-image-bletchley-20260728025045.static.mtd`(`VERSION_ID 3.1.0-dev-739-gba9070d60b`,見 `images/bletchley/*.manifest`)
QEMU machine:`bletchley-bmc`(QEMU 11.0.1,官方 Jenkins 版)
openbmc-test-automation:`b4a1d031`(master,2026-08-11)
Robot Framework:7.2.2(Python 3.12.3,獨立 venv `~/.venvs/robot`)
執行腳本:`harness/qemu/run_robot_qemu_ci.sh`(報告含 `meta.txt` 版本紀錄)

## 為什麼用官方測試而不是自己 curl

1. **驗證**:通過的是官方測試,不是我自己寫的檢查。
2. **證據**:`log.html` / `report.html` 是 Robot 的標準報告,任何人都讀得懂。
3. **T0**:`openbmc-test-automation` 是我的 upstream patch 目標之一 ——
   跑它的過程直接生出了 patch 候選(見下面的觀察 1)。

## ⚠️ 環境的誠實宣告

這顆 flash 映像的 `/etc` overlay 帶著本專案部署的設定
(entity-manager 的 `Thermal_Loop_Demo` 板 + swampd 設定與 drop-in,
見 `config/`)。**這不是一顆 pristine 映像。** Redfish 巡檢因此看得到
兩個 chassis(`Bletchley_Front_Panel_Board` 與 `Thermal_Loop_Demo`)。
逐案追根因時,每個失敗都先問過「是不是我的設定造成的」——
結論寫在下表「類別」欄(本次 20 案例中,沒有任何失敗與本專案設定相關)。

## 執行方式

```bash
# 先驗環境(3 案例:Redfish 登入 / SSH / out-of-band IPMI)
./harness/qemu/run_robot_qemu_ci.sh setup
# QEMU 專用清單(-A = argument file,20 個 --include)
./harness/qemu/run_robot_qemu_ci.sh qemu_ci
```

`-A` 是 argument file、`-v` 是變數。⚠️ 兩個實測補充:

- 週計畫寫的 `OPENBMC_HOST=... robot ...`(純環境變數)**根本傳不進 Robot**:
  `lib/resource.robot` 把 `OPENBMC_HOST` 預設成空字串,Robot 不會自動吃
  環境變數 —— 一定要用 `-v`。
- `OPENBMC_PASSWORD` 上游預設也是**空字串**,必須顯式給 `-v OPENBMC_PASSWORD:0penBmc`。

## setup suite 結果(3 案例)

| 案例 | 結果 | 說明 |
|---|:---:|---|
| Test Redfish Setup | ✅ PASS | 登入/GET/登出 |
| Test SSH Setup | ✅ PASS | `uname -a` 回 `6.18.40-c2b9fc3 armv7l` |
| Test IPMI Setup | ❌ FAIL | out-of-band IPMI,根因見下 |

**IPMI 失敗的根因鏈(兩層,各自有證據):**

1. **映像層(真正的根因):bletchley 映像沒有 `phosphor-ipmi-net`(netipmid)**——
   聽 UDP 623 的 RMCP+ daemon。manifest 裡 IPMI 相關套件只有
   `phosphor-ipmi-host`(inband)、`fb-ipmi-oem`、`phosphor-ipmi-fru`、
   `phosphor-ipmi-ipmb`;BMC 上 `systemctl list-units` 也只有
   `phosphor-ipmi-host` 在跑。ipmitool 的 `lanplus` 介面沒有對端可談。
2. **主機層(就算映像有也連不到):`run_bmc.sh` 只轉發 TCP 2222/2443,
   沒有轉發 UDP 623。**

所以「這個失敗是因為該映像沒編那個功能」——Gate 5 DoD 明文的合格答案。
bletchley 是 sled 型機箱,Meta 的設計走 inband + IPMB + OEM handler,
不開網路 IPMI;這與 W3 發現的 `FACEBOOK_REMOVED_DBUS_SENSORS`
是同一種 vendor layer 裁剪。

## QEMU_CI 結果總覽

跑了**兩輪**,兩輪都留檔 —— 第一輪暴露的是**我的調用參數缺口**,
修正後的第二輪才是正式證據:

| 輪 | 調用 | 結果(執行 19 案) | 差異 |
|---|---|---|---|
| 1(2026-08-12 上午) | 缺 `CHASSIS_ID`、缺 `REDFISH_SUPPORT_TRANS_STATE` | 8 P / 11 F | `GET_Redfish_Resources` 因 `/Chassis/chassis` 404 而紅 |
| **2(正式,`docs/robot/20260812_032837/`)** | `run_robot_qemu_ci.sh`(含修正) | **10 P / 9 F** | 剩餘失敗**零項是本側調用問題** |

清單有 20 個生效 include,**兩輪都只執行 19 個測試** —— 見觀察 3(死 include)。

## 逐個失敗案例的根因(第二輪,9 案)

| # | 案例 | 根因 | 類別 | 我怎麼驗證的 |
|:---:|---|---|:---:|---|
| 1 | `Check_For_Application_Failures` | journal 有 `motor-init-calibration@1~6` 與 `bletchley-sys-init` 失敗:bletchley 是 sled 機箱,開機要校正**實體步進馬達**,QEMU 沒有這個硬體 | b | journal 原文;查 unit 名(`motor-init-calibration@`)對應 sled 馬達初始化 |
| 2 | `Test_SSH_And_IPMI_Connections` | SSH 半邊通過;IPMI 半邊 `Unable to establish RMCP+ session`:**映像沒有 `phosphor-ipmi-net`(netipmid)**,UDP 623 無人聽 | a | manifest 只有 `phosphor-ipmi-host`(inband)/`fb-ipmi-oem`/`-fru`/`-ipmb`;BMC `systemctl` 無 netipmid unit;另 host 側 QEMU 也沒轉發 UDP 623(就算有 daemon 也到不了) |
| 3~7 | 5 個 IPMI 案例(`Enable_IPMI_User`、`User_Deletion`、`SEL_Version`、`Self_Test`、`Device_GUID`) | 同上 —— 全部走 `ipmitool -I lanplus`(out-of-band) | a | 同上;每案失敗訊息一致 |
| 8~9 | `Verify_Redfish_Software_Inventory_Collection`、`Redfish_Software_Inventory_Status_Check` | **Test Setup 就死**:`Plug-in setup failed.`(`lib/obmc_boot_test.py:517`)——這套 suite 的 per-test setup 走 boot-test 框架的 plug-in 前置(`rprocess_plug_in_packages(call_point="setup")` 回非零)。與被測的 Redfish 路徑無關;`REDFISH_SUPPORT_TRANS_STATE=1` 不影響它(第二輪已驗) | d | 兩輪皆同;單獨跑同 suite 的另一個測試(見觀察 3)重現同一 setup 失敗;訊息出處用 `grep -rn 'Plug-in setup failed' lib/` 定位 |

其餘 10 案 PASS:Redfish 認證/Session 全套(7)、
`GET_Redfish_Resources_With_Login`、`Verify_AccountService_Available`、
`Verify_No_BMC_Dump_And_Application_Failures_In_BMC`。

⚠️ **不穩定案例注記:** `Verify_No_BMC_Dump_...` 第一輪紅(journal 的
motor-init 訊息)、第二輪綠。兩輪間差異只有兩個 `-v` 變數與 ~1 小時
uptime —— 該案的 journal 檢查窗口疑似與開機距離有關,未再深究,
兩輪報告都留檔。**選擇性只報綠的那輪 = 造假**,所以兩輪都在
`docs/robot/` 與本文件裡。

追根因的方法(每個失敗都走一遍):

```
1. 開 log.html 找失敗那一步的完整輸出(keyword 的參數與回傳都在)
2. 手動重現:把那一步的 curl / ssh / ipmitool 自己打一次
3. 分類:
   a) 映像沒編那個功能  → 指出 build option / manifest 證據
   b) QEMU 沒有那個硬體 → 指出該服務在真機上碰的硬體
   c) 我的環境/設定問題 → 修掉重跑
   d) 測試對 QEMU 的假設過時 → patch 候選
```

## ★ 兩個關鍵觀察

### 觀察 1:`QEMU_CI` 清單裡一個熱控/感測器案例都沒有 —— 而且現有套件補不上

```bash
$ grep -c -- '--include' test_lists/QEMU_CI   # 21(含 1 行註解掉的 Verify_Redfish_BMC_Time,掛 bmcweb#264)
$ grep -ic 'thermal\|sensor' test_lists/QEMU_CI
0
```

(⚠️ 第一個 grep 連註解行都算 —— 生效的 include 是 **20** 個。)

20 個案例涵蓋:SSH/IPMI 連線、應用程式失敗檢查、Redfish 認證與 Session、
UpdateService/SoftwareInventory、IPMI 使用者/SEL/self-test/GUID、
AccountService、BMC dump。**沒有任何熱控或感測器路徑的驗證。**

而且 repo 裡現有的兩份相關套件都進不了這份清單:

- `redfish/systems/test_sensor_monitoring.robot`:需要 host OS 的
  SSH(`OS_HOST`)與每機型的 `redfish_sensor_info_map` 變數檔,
  且驗的是**舊版** `/Thermal`、`/Power` schema —— 本映像上 404
  (見 docs/redfish-notes.md)。
- `redfish/systems/test_thermal_ambient_temperatures.robot`:同樣走舊
  `/Thermal`,還包含重開機流程。

**要補只能是新案例**:走現代 `ThermalSubsystem`/`Sensors` 路徑、
容忍空集合(stock QEMU 映像的 Sensors collection 是 0 成員 ——
本 rig 看得到 `die0` 是因為部署了自己的 entity-manager 設定)。
草稿:`docs/upstream-drafts/test_thermal_subsystem.robot`,
候選登記:`docs/upstream.md`。

### 觀察 2:清單裡有 5 個 IPMI 案例

所以跑完 QEMU_CI 我有真實的 IPMI **測試**接觸(在本映像上它們因
沒有 netipmid 而失敗,失敗本身也是接觸)。
⚠️ **誠實說明:我是「跑過官方 IPMI 測試」,不是「開發過 IPMI 命令」。**
履歷的 JD 對照表上,IPMI 標「中」不標「強」。

### 觀察 3:清單裡有一行掛了四年的死 include(→ 候選 3)

發現方式是**對帳**:清單 20 個生效 include,兩輪都只執行 19 個測試。

- 缺席者:`--include Verify_Update_Service_Enabled`。這個 tag 全 repo
  不存在 —— `5236ec54`(2022-01-31)把該測試的 tag 改名為
  `Verify_Redfish_Update_Service_Enabled`,而清單那行是 2022-04-28
  (`e4d77d2a8`)寫入的:**寫入當天引用的就是已改名的 tag,從未生效**。
  Robot 對不存在的 tag 安靜地跑零個測試,不報錯。
- **不能用「改成新 tag」修**:單獨跑改名後的 tag
  (`docs/robot/20260812_renamed_tag_probe/`),同樣死在
  `Setup failed: Plug-in setup failed.` —— 該 suite 的 Test Setup 是
  `Redfish.Login` + `Redfish Power Off`,後者走 boot-test 框架、
  需要 host 電源堆疊,而 BMC-only 的 QEMU 沒有(`obmcutil state`
  輸出為空)。整個 firmware-inventory suite 天生進不了 QEMU_CI。
- 正確修法:**刪掉那一行**。證據三件套(改名 commit、blame、
  探針報告)與 patch 規劃見 `docs/upstream.md` 候選 3。

## 我沒有做的

- 我跑的是 `QEMU_CI` 清單(20 個生效 include),**不是完整的硬體 CI 清單**。
- 我沒有把 Robot 測試接進本 repo 的 CI(它需要開 QEMU,跑太久)。
- 我沒有為了全綠去改測試或改環境 —— 失敗案例的價值在根因,不在顏色。
