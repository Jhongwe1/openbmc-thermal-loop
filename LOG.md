# LOG

每一則都要有「**先驗哪個、為什麼**」。格式：現象 → 假設 → 驗證順序與理由 → 根因 → 教訓。

---

## 2026-08-03 之前的空白

（本檔由 W1 D1 起記錄。）

---

## 2026-07-28（W1 D1）repo 為什麼不放在 Windows 檔案系統上

- **情境**：開發機是 Windows 11 + WSL2 / Ubuntu 24.04。專案資料夾原本開在
  `C:\Users\...\Desktop\`，在 WSL 裡看到的路徑是 `/mnt/c/...`。要決定 git repo
  放哪一邊。
- **假設**：(1) 放 `/mnt/c` 只是「比較慢」，可接受　(2) 跨檔案系統邊界會丟掉
  POSIX 語意（權限位元、換行符號），那是功能問題不是效能問題
- **先驗哪個、為什麼**：先驗 (2) 裡的「權限位元」。理由是**排除成本最低**——
  複製一個目錄過去再 `ls -l` 就知道，兩秒；而「慢多少」要做基準測試，成本高
  十倍以上。而且就算 (1) 成立，慢只是讓我等；(2) 成立的話是我的 `.sh` 交付物
  直接不能執行。期望成本差很多。
- **驗證方式**：`cp -r /mnt/c/.../plan ~/work/...` 之後 `ls -l`。
- **結果**：所有 `.md` 檔的權限是 `-rwxr-xr-x`（755）。
- **根因**：WSL 用 `drvfs` 掛載 Windows 磁碟，drvfs 沒有 POSIX 權限模型，
  一律回報 755，`chmod` 在該掛載點上不生效。另外 Windows 版 git 預設
  `core.autocrlf=true`，shell script 會被存成 CRLF，在 Linux 執行時會出現
  `bad interpreter: /bin/bash^M`——而這個錯誤訊息完全指不到真正的原因。
- **決策**：repo 建在 `~/work/openbmc-thermal-loop`（ext4）。`plan/` 與
  `archive/` 複製一份進來並 gitignore。
- **教訓**：跨檔案系統／跨作業系統邊界時，第一個問題不是「快不快」，而是
  **「這個邊界會丟掉什麼語意」**。效能問題會讓我等，語意問題會讓我查半天
  還查不到原因。

## 2026-07-28（W1 D1）環境事實記錄

- WSL2 的 PID 1 預設**不是** systemd，是微軟的 `/init`。必須在 `/etc/wsl.conf`
  寫 `[boot] systemd=true` 並 `wsl --shutdown` 後才生效。
  驗證：`ps -p 1 -o comm=` → `systemd`；`systemctl is-system-running` → `running`。
  這件事對本專案是必要條件，因為 `phosphor-pid-control`（swampd）是 systemd
  service，而整條控制鏈走 D-Bus。
- 發行版 QEMU 版本：**8.2.2**（`qemu-system-arm --version`，Ubuntu 24.04 內建）。
  **待驗假設（D2 驗證）**：`bletchley-bmc` 應該在，但 `anacapa-bmc` 與
  `gb200nvl-bmc` 是較晚進上游的 machine，8.2.2 可能沒有。若不在，改抓
  OpenBMC Jenkins 的預編譯 `qemu-system-arm`。
- Docker：本機已有 Docker Desktop，採用其 WSL integration，**不另裝 `docker.io`**
  （兩者並存會搶 socket）。整合開關待啟用；docker 在 W9 前用不到。

## 2026-07-28(W1 D2 提前)發行版 QEMU 的機種不足,以及一個與參考資料矛盾的發現

> 進度說明:計畫把 QEMU 驗機排在 D2、平台掃描排在 D3。本日一併完成,
> 日期以**實際執行日**為準。

- **情境**:要決定在哪個 QEMU machine 上跑 OpenBMC。參考資料指定主線
  `bletchley`、備援 `anacapa`。
- **假設(前一日提出)**:Ubuntu 24.04 內建的 QEMU 是 8.2.2(2024 年初),
  而 `anacapa` / `gb200nvl` 是較晚進上游的機種,**很可能不在**;`bletchley`
  較早進上游,應該在。
- **驗證方式**:`qemu-system-arm -M help | grep -Ei 'bletchley|anacapa|gb200|romulus'`
- **結果**:假設成立。8.2.2 只有 `bletchley-bmc` 與 `romulus-bmc`。
- **處置**:抓 OpenBMC Jenkins 每日建置的預編譯 `qemu-system-arm`(11.0.1),
  放 `~/bin` 並提高 PATH 優先序。
- **★ 但換上 11.0.1 之後出現一件參考資料沒說的事**:
  `gb200nvl-bmc` 出現了,**`anacapa-bmc` 依然不存在**——而參考資料把
  `anacapa` 列為備援平台。反過來,參考資料標記「無 machine、QEMU 跑不起來」
  的 `catalina`,在 11.0.1 裡**是存在的**(`catalina-bmc`,Cortex-A7)。
- **根因**:「Jenkins 有出映像」與「QEMU 有 machine model」是**兩條獨立的
  上游時間線**。`anacapa` 的映像五個套件全齊,但 QEMU 那邊還沒有它的
  machine model。參考資料把這兩件事混成一欄,所以錯了。
- **決策**:備援平台由 `anacapa` 改為 `catalina`。
- **教訓**:文件會過期,而且**過期的方式常常是「兩個獨立變動的事實被寫成
  同一個結論」**。所以驗證時要拆開驗:先問「映像有沒有」,再問「機器跑不跑
  得起來」,不要合起來問「這台能不能用」。

## 2026-07-28(W1 D3 提前)先掃平台,再決定在哪台機器上做

- **現象**:參考資料對「用哪台 QEMU machine」給過不同答案(`gb200nvl` /
  `romulus`),而這兩台我都還沒驗過。
- **假設**:(1) 兩個答案都對,只是側重不同　(2) 其中一份過期
  (3) **兩份都沒有實際查過映像的套件清單**
- **先驗哪個、為什麼**:先驗 (3)。理由是**排除成本最低**——Jenkins 對每個
  target 都有 `*.manifest`,一支 `curl` 就知道,不必開機。而且如果 (3) 成立,
  (1)(2) 自動失效,一次砍掉整棵樹。
- **驗證方式**:寫 `harness/qemu/platform_matrix.sh`,對 19 個 target 各拉一次
  目錄列表 + 一次 manifest(共 38 次 HTTP),比對 5 個套件是否存在。
  耗時 44 秒。
- **根因**:Jenkins 的每個 target 是不同的 Yocto 設定,套件清單差很多。
  `romulus` 連 `dbus-sensors`、`entity-manager` 都沒有;`gb200nvl-obmc` 有
  `dbus-sensors`、`entity-manager` 但**沒有** `phosphor-pid-control`。
  兩份參考資料指定的平台,**都不含本專案的主體套件**。
- **結論**:三個條件的交集
  ({有映像} ∩ {QEMU 有 machine} ∩ {含 phosphor-pid-control})
  只剩 `bletchley` 與 `catalina`。
- **教訓**:「換一台試試」是試錯,「拉 manifest 比對」是查證。同樣是換平台,
  後者說得出為什麼,前者說不出。在 BMC 這一行,先確認目標平台的套件清單
  比先寫程式重要——量產團隊每天都在對 image manifest。
- **副產物**:這張矩陣本身變成交付物(`docs/platform-matrix.md`),
  腳本可重跑(上游每天變,隨時可以重新驗一次)。

## 2026-07-28(W1 D4 提前)四份 manifest 對照:兩套風扇堆疊

- **現象**:參考資料建議過的兩個平台(`gb200nvl-obmc`、`romulus`),manifest
  裡都沒有 `phosphor-pid-control`(swampd)。
- **我做了什麼**:沒有一台一台試開機。寫 `harness/qemu/fetch_image.sh` 直接拉
  Jenkins 的 image manifest 比對,`--manifest-only` 模式連映像都不用下載
  (manifest 約 10 KB,映像 56 MB)。
- **根因**:Jenkins 的每個 target 是不同的 Yocto 設定,套件清單差很多。
- **★ 一個參考資料沒寫、但更重要的觀察**:`romulus` **沒有**
  `phosphor-pid-control`,卻**有** `phosphor-fan-control`;`p10bmc` 也是同樣的
  模式。這代表 OpenBMC 有**兩套互不相同的風扇控制堆疊**:

  | | `phosphor-pid-control`(swampd) | `phosphor-fan-control` |
  |---|---|---|
  | 出身 | Intel 系 | IBM / OpenPOWER 系 |
  | 設定來源 | JSON / entity-manager | YAML 產生的 C++ |

  所以「這台有沒有風扇控制」**不是一個是非題**——要問的是「**哪一套**」。
  參考資料把 `romulus` 描述成「只有 bmcweb + hwmon」,漏掉了這件事。
- **教訓**:「換一台試試」是試錯,「拉 manifest 比對」是查證。同樣是換平台,
  後者說得出為什麼,前者說不出。
  而且比對時要看的不只是「有沒有」,還要看「**沒有 A 的那台,是不是有 B**」
  ——缺席本身也是資訊。
- **副產物**:`docs/env-baseline.md` 記下 `phosphor-pid-control` 的 git hash
  `c5e59550d3`。W5 的 meson wrap 要釘死它,W7 的圖說明要引用它。

## 2026-07-28(W1 D5 提前)QEMU 拒絕開機:映像大小與模擬晶片容量不符

- **現象**:`./harness/qemu/run_bmc.sh bletchley` 一啟動就死,連 U-Boot 都沒到:
  ```
  qemu-system-arm: w25q01jvq device '/machine/unattached/device[17]'
                   requires 134217728 bytes, mtd0 block backend provides 58610688 bytes
  ```
- **假設**:(1) machine 選錯了(該用 `ast2600-evb` 而非 `bletchley-bmc`)
  (2) 映像下載不完整　(3) 映像大小與模擬的 flash 晶片容量不符
- **先驗哪個、為什麼**:先驗 (3)。**理由是錯誤訊息本身已經給了兩個數字**——
  134217728 = 128 MiB,58610688 ≈ 56 MiB,而 `w25q01jv` 是一顆 **1 Gbit = 128 MiB**
  的 SPI NOR flash。**驗證成本接近零**(查一下型號就知道)。
  相較之下 (1) 要重跑一輪、(2) 要重新下載並比對雜湊,成本高一個數量級。
- **驗證方式**:把映像複製一份並 `truncate -s 128M` 補零,再開一次。
- **根因**:QEMU 模擬的是**一顆實體 SPI flash 晶片**,block backend 的大小必須等於
  晶片容量。Yocto 產出的 `.static.mtd` 只包含實際用到的部分(56 MiB),
  尾端未使用的區域沒有寫進檔案。真實燒錄時,燒錄器會把剩餘空間留空——
  補零就是在做同一件事。
- **處置**:把補零寫進 `run_bmc.sh`,並讓 `FLASH_MB` 跟著 `MACHINE` 一起放在
  `case` 裡——**因為晶片容量是「板子」的屬性,不是「映像」的屬性**
  (AST2500 的 `romulus` 只有 32 MiB)。只在缺檔或原始映像較新時才重建,
  避免每次開機都複製 128 MB。
- **教訓**:**錯誤訊息裡的數字要當成線索讀,不要只讀文字。** 這則訊息把答案直接
  寫在兩個數字的比值裡。另外——模擬器模擬的是**硬體約束**,它會拒絕物理上不可能
  的組態;這跟軟體錯誤不同,不能靠改參數繞過。

## 2026-07-28(W1 D6 提前)十分鐘體檢:三個腳本 bug,與整個專案的起點

- **現象**:照參考資料寫的 `healthcheck.sh` 有多項輸出是錯誤訊息而非資料。
- **逐項排查**:
  1. `head: invalid option -- '3'` → BMC 上的 coreutils 是 **BusyBox v1.38.0**,
     不是 GNU。BusyBox 的 `head` 不接受 `head -5` 簡寫,必須 `head -n 5`。
     **跑在 BMC 端的指令全部要檢查一遍。**
  2. Redfish 的 `Thermal` / `ThermalSubsystem` / `Sensors` 全回 `ResourceNotFound`
     → 因為腳本把 chassis id 寫死成 `chassis`,但這台的實際 id 是
     **`Bletchley_Front_Panel_Board`**。改成先 `GET /redfish/v1/Chassis` 取
     `Members[0]` 再組路徑。**改完之後 `ThermalSubsystem` 就出現了**——
     原本會誤判成「這個映像沒有新 schema」。
  3. `systemd-analyze: command not found` → 這個映像沒裝。改用
     `systemctl show -p FinishTimestampMonotonic`(單位微秒)。
- **★ 最重要的發現**:
  ```
  swampd[1729]: No fan zones, application pausing until new configuration
  ```
  `swampd` 有在跑(`systemctl is-active` = active),但它**沒有拿到任何風扇 zone
  設定**,印完這行就停著等。
- **這一行同時解釋了另外兩個觀察**:`busctl tree xyz.openbmc_project.State.FanCtrl`
  底下沒有任何 zone 物件;Redfish 的 Sensors collection 存在但 Members 是空的。
  **三者是同一件事的三個面向。**
- **教訓**:「服務有沒有在跑」跟「服務有沒有在工作」是兩個問題。
  `systemctl is-active` 回 active 只代表行程還活著。
  **要看它的 journal,才知道它到底在做什麼。**
  → 所以 Gate 1 的任務不是「讓 swampd 跑起來」,而是**給它一份設定**。
- **其他影響後續設計的量測**:`/` 是唯讀(`rootfs ro`),`/etc` 與 `/var` 是
  overlay 可寫,`/usr/share` 唯讀 → 設定必須放 `/etc` 並用 systemd drop-in 指過去。
  開機耗時 **149.7 秒**(QEMU 上,非真實硬體)。
