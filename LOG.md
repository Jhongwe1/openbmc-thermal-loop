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

## 2026-07-28(W1 D5 續)我自己踩了一次同樣的坑,方向相反

- **現象**:開 `gb200nvl-obmc` 時 QEMU 又拒絕啟動,但數字反過來:
  ```
  mx66u51235f device requires 67108864 bytes,
  mtd0 block backend provides 134217728 bytes
  ```
- **根因**:我在 `run_bmc.sh` 的 `case` 裡把 `gb200nvl-obmc` 的 `FLASH_MB` 預設
  成 128,**是照 bletchley 抄的**。但 `gb200nvl-bmc` 用的是 `mx66u51235f`
  (512 Mbit = **64 MiB**),不是 `w25q01jv`(1 Gbit = 128 MiB)。補過頭了。
- **教訓(兩層)**:
  1. 表面教訓:每塊板子的 flash 型號不同,容量要一顆一顆查。
     現在 `run_bmc.sh` 的註解裡列了三顆的容量,並寫明「錯誤訊息裡的
     `requires N bytes` 就是正確答案」。
  2. **真正的教訓:我把「一個平台的觀察」當成「所有平台的通則」了。**
     這跟我在 D2 批評參考資料的錯誤是**同一種錯誤**——它把 anacapa 的映像狀態
     當成 QEMU 的機型狀態。**指出別人的推理錯誤,不代表自己不會犯同一種錯。**
- **附帶收穫**:設計本身是對的。因為 `FLASH_MB` 一開始就跟 `MACHINE` 放在同一個
  `case` 分支裡,修正只需要改一個數字;如果當初寫成全域常數,就要重構。
  **把「會因平台而異」的東西放在一起,是這次唯一做對的決定。**

## 2026-07-28(W1 D5 續)現場確認 gb200nvl-obmc 沒有 swampd

- 從 manifest 推論(D4)→ 實際開機驗證(D5),證據鏈接上:
  ```
  OPENBMC_TARGET_MACHINE="gb200nvl-obmc"
  ls: /usr/bin/swampd: No such file or directory
  Unit phosphor-pid-control.service could not be found.
  bmcweb: active        ← 機器本身開得起來,單純就是沒有這個套件
  ```
- **為什麼要多做這一步**:manifest 是**間接證據**(套件清單),開機是**直接證據**
  (檔案系統)。兩者一致才能說「我確認過」;如果不一致,那本身就是更值得追的事。
- 保留 `bmcweb: active` 這一行是刻意的——它排除了「機器根本開不起來」這個
  混淆因素,證明缺的就只是 `phosphor-pid-control`。

---

## 2026-08-04(W2 D1)Gerrit 的 Full name 被 GitHub 資料帶成暱稱

- **現象**:用 GitHub 帳號登入 gerrit.openbmc.org 之後,`ssh openbmc.gerrit`
  的歡迎訊息回的是 `Hi wei, you have successfully connected over SSH.`
  —— 但我的本名是 `Chung-Wei Lan`,git 的 `user.name` 也是。
- **為什麼這是問題(不是美觀問題)**:Gerrit 在 push 時會比對 commit 的
  `Signed-off-by:` 與帳號的 Full name。不一致會被拒收,錯誤訊息是
  `invalid author/committer`,**而且要到第一次真的送 patch 才會爆**。
- **假設**:(1) Gerrit 只是顯示暱稱,不影響驗證　(2) Full name 這一格是
  從 GitHub 個人檔案的 Name 欄自動帶進來的,而且就是 push 檢查用的那一格
- **先驗哪個、為什麼**:先驗 (2),因為**驗證成本幾乎為零** ——
  打開 Settings → Profile 看一眼就知道那格的值是不是 `wei`。
  而 (1) 要驗必須真的推一次 change 才能確定,成本高好幾個數量級。
  **「一個假設可以用兩秒的觀察排除,另一個要跑完整條流程」時,先驗前者。**
- **根因**:Gerrit 的 GitHub OAuth 登入會把 GitHub 個人檔案的 Name 欄
  預填進 Full name。我的 GitHub Name 是縮寫,所以帶進來就是 `wei`。
- **修正**:Settings → Profile → Full name 改成 `Chung-Wei Lan` → Save。
  重跑 `ssh openbmc.gerrit`,歡迎訊息變成 `Hi Chung-Wei Lan`。
- **教訓**:**`ssh openbmc.gerrit` 的歡迎訊息是一個免費的驗證點** ——
  它會把伺服器端認定的身分念出來。與其去翻設定頁,不如讓對方告訴你它以為你是誰。
  更一般的說法:**驗證身分類的設定,要用「對方回報的值」,不要用「我填了什麼」。**
- **這一題的證據價值**:GitHub 個人檔案不需要改成本名 —— 那一格沒人檢查。
  真正要一致的是四個地方:CLA 簽名 / git `user.name` / commit 的 `Signed-off-by`
  / Gerrit Full name。這四個以外的都不影響。

## 2026-08-04(W2 D1)腳本執行到一半整段消失:ssh 把 stdin 上的腳本吃掉了

- **現象**:一段有 7 個步驟的 shell 腳本,以
  `echo <base64> | base64 -d | bash -l` 的方式執行。輸出只印到第 2 步
  (那一步是 `ssh openbmc.gerrit` 的連線測試),**第 3 步之後完全沒有輸出,
  也沒有任何錯誤訊息**。之後檢查檔案系統,第 3 步要 clone 的 repo 一個都不存在。
- **假設**:(1) `set -e` 遇到非零回傳碼而中止 —— 但 Gerrit 的 SSH 本來就回非零
  (2) clone 因為網路/權限失敗,錯誤訊息被吞掉
  (3) **`ssh` 讀走了 stdin**,而 stdin 正好是「還沒被 bash 讀完的腳本本身」
- **先驗哪個、為什麼**:先驗 (2),因為**它能一刀切一半** ——
  單獨跑一次 `git clone` 就知道是「clone 本身有問題」還是「clone 根本沒被執行」。
  結果單獨跑**完全正常、5 秒就好**,直接把 (1)(2) 一起排除,只剩 (3)。
- **根因**:`bash` 從**管線(stdin)**讀腳本時,是**邊讀邊執行**的。
  `ssh` 預設會把自己的 stdin 轉發給遠端,於是它把「剩下還沒執行的腳本文字」
  當成輸入讀光。bash 回頭要讀下一行時,已經沒有東西可讀 → 正常結束。
  **所以不是失敗,是後半段根本沒有被執行。** 這也是為什麼連錯誤訊息都沒有。
- **修正(兩種)**:
  1. `ssh -n ...` —— `-n` 的意思是「把 stdin 接到 /dev/null」,不要去讀。
  2. **把腳本先落地成檔案再執行**(`... > /tmp/x.sh; bash -l /tmp/x.sh`)。
     這樣 bash 讀的是檔案不是 stdin,誰去讀 stdin 都不影響。我採用這個。
- **教訓**:**「沒有錯誤訊息」不等於「沒有錯誤」,也可能是「根本沒執行」。**
  遇到「輸出斷在某一行」時,第一個要問的不是「那一行為什麼失敗」,
  而是**「後面那些行到底有沒有被執行過」** —— 這兩者的排查方向完全相反。
- **同一類的坑(之後一定會遇到)**:
  ```bash
  while read -r host; do ssh "$host" uptime; done < hosts.txt
  ```
  只會處理第一台,因為 `ssh` 把 `hosts.txt` 剩下的行吃光了。
  解法一樣:`ssh -n`。**W9 寫多台 QEMU 的測試腳本時要記得。**

## 2026-08-04(W2 D1)`gcc ... | head` 之後執行檔沒有產生

- **現象**:`gcc -Wall -Wextra -std=c11 -o bits bits.c 2>&1 | head -n 20`
  跑完,畫面上看得到警告訊息,看起來有在編譯;但接著 `./bits` 說
  `No such file or directory`。
- **假設**:(1) 編譯真的失敗了,只是錯誤訊息被 `head` 截掉沒看到
  (2) 輸出到了別的目錄　(3) `head` 提早結束把 `gcc` 殺掉了
- **先驗哪個、為什麼**:先驗 (1),因為**排除成本最低** —— 把 `| head` 拿掉
  重跑一次就知道。結果拿掉之後**編譯完全成功,執行檔也生出來了**,
  (1)(2) 同時被排除,只剩 (3)。
- **根因**:`head -n 20` 印完 20 行就**主動關閉管線並結束**。此時 `gcc` 還在寫
  警告訊息到一個沒有讀取端的管線,核心送出 **SIGPIPE**,預設行為是**終止該行程**。
  gcc 在寫完 20 行警告、還沒連結出執行檔之前就被殺掉了。
- **修正**:不要用管線包住有副作用的指令。要看輸出就**先落地成檔案再看**:
  ```bash
  gcc -Wall -Wextra -std=c11 -o bits bits.c > /tmp/build.log 2>&1
  head -n 20 /tmp/build.log
  ```
- **教訓**:**管線右邊的程式提早結束,會殺掉左邊的程式。**
  所以 `| head`、`| grep -q`、`| less` **不可以**用來包住編譯、下載、寫檔
  這類有副作用的指令 —— 它們會被中途砍斷,而且**看起來像成功**。
  這個設計本身是對的(`yes | head -n 5` 才不會無限跑),但它跟「我只是想少看幾行」
  的直覺相反。
- **這一題什麼時候會再咬我**:W10 寫 CI 的時候。CI 腳本最愛寫
  `make 2>&1 | tail -n 50`,然後 build 莫名其妙失敗、日誌卻看不出原因。

> ⚠️ **待辦(§10 第 7 項):以上三則是指導老師整理的措辭,面試前要用自己的話重寫一次。**
> 面試官問的是「你當時怎麼想」,那不能是別人的句子。
## 2026-08-05(W2 D3)Gerrit 擋的是 email 不是名字 —— 推翻我自己 08-04 的紀錄

- **待驗假設(08-04 立,08-05 驗)**:我 08-04 在 `docs/upstream.md` 與
  `runbook.md` 都寫了「`Signed-off-by` 的名字與 Gerrit Profile 的 Full name
  不一致,**會被 Gerrit 擋下來**」。**那句話沒有實測,是從計畫抄來的。**
- **為什麼要驗**:兩種結果的意義完全不同。
  若**會擋** → 上游文件缺這一句是真的會害人,值得送 patch。
  若**不會擋** → 名字要一致的理由是「T0 證據要讓主管看到我的本名」,
  **仍然要一致,但理由完全不同**,面試講錯理由會被抓。
- **實驗設計(單一變因,同一個 Change-Id)**:
  | | patchset 1(對照組) | patchset 2(實驗組) | patchset 3 |
  |---|---|---|---|
  | diff | 一行 | **完全相同** | 完全相同 |
  | `Signed-off-by` 名字 | `Chung-Wei Lan` | **`wei`** | `Chung-Wei Lan` |
  | committer email | `zwwe1f@gmail.com` | 相同 | **`not-registered@example.com`** |
  | 結果 | ✅ 收 | **✅ 收** | **❌ 拒** |
- **實測輸出(patchset 3)**:
  ```
  ERROR: commit 53054b9: email address not-registered@example.com is not
  registered in your account, and you lack 'forge committer' permission.
  The following addresses are currently registered:
     zwwe1f@gmail.com
  ! [remote rejected] HEAD -> refs/for/master%private,wip (invalid committer)
  ```
- **根因**:Gerrit 的 receive 檢查驗的是 **committer / author 的 email 是否在
  帳號的註冊清單裡**(對應 `forge committer` 權限),**不驗 `Signed-off-by`
  這個 trailer 的名字**。名字要不要一致取決於各 server 的設定,
  OpenBMC 這台**沒有**開這項檢查。
- **修正**:`docs/upstream.md` 與 `runbook.md` 的那句話已改掉。
- **教訓**:**我把「兩件都要做的事」的其中一件的理由,錯記成另一件的理由。**
  「名字四處一致」與「email 要註冊」都要做,但一個是**證據價值**的要求
  (主管要在 Gerrit 上看到我的本名),另一個是**技術**的要求(不然推不上去)。
  抄來的文件把兩者混成一句,我就跟著混了。
  **以後凡是「因為 X 所以會被擋」這種因果句,在寫進交付文件之前要先實測 ——
  它的成本是一次 push,而講錯的成本是面試當場被追問到答不出來。**

---

## 2026-08-05(W2 D4)QEMU 背景執行時「開機開到一半自己消失」

- **現象**:`QEMU_SERIAL=file:/tmp/boot.log nohup ./harness/qemu/run_bmc.sh bletchley &`
  丟到背景。三秒後 `ps` 看得到 QEMU 在跑、`qemu-run.log` 也有正常的啟動訊息。
  但幾分鐘後回來看,**QEMU 行程不見了,`/tmp/boot.log` 與 `/tmp/qemu-run.log`
  兩個檔案也一起不見了,而且沒有任何錯誤訊息**。
- **假設**:(1) QEMU 自己 crash (2) WSL distro idle 關機把它帶走
  (3) QEMU 讀到 stdin 的 EOF 就正常結束
- **先驗哪個、為什麼**:先驗 (2),因為**它能一刀切一半** ——
  `/tmp` 裡的檔案一起消失,只有「整個 distro 重開、systemd-tmpfiles 清掉 /tmp」
  能解釋。crash 不會刪檔案。這一個觀察就把問題分成「環境層」與「QEMU 層」兩半。
  結果 (2) 成立,但它**不能解釋為什麼 distro 會 idle** —— 有 QEMU 在跑的話
  distro 不該閒置。所以 (2) 是**結果**不是根因,真正的根因在 (3)。
- **根因**:`run_bmc.sh` 用 `-nographic`。**這個旗標同時把 serial 與 QEMU
  monitor 接到終端機。** 當 `QEMU_SERIAL=file:...` 把 serial 導去檔案時,
  **monitor 仍然單獨留在 stdio**。背景執行時 stdin 一 EOF,monitor 收到 EOF
  就讓 QEMU **正常結束(離開碼 0)**。QEMU 一死,distro 沒有行程了 → WSL 關掉
  VM → 下次啟動 systemd 清空 /tmp → 連證據都沒了。
- **修正**:`run_bmc.sh` 依 console 去向選 UI 旗標 ——
  互動模式維持 `-nographic`,無終端機模式改用 `-display none -monitor none`,
  讓 QEMU 完全不掛任何東西在 stdin 上。
- **教訓**:**「離開碼是 0」不等於「我要它做的事做完了」。**
  這一則跟 08-04 那則「ssh 吃掉 stdin」是**同一族的坑**:
  都是「某個我沒注意到的東西掛在 stdin 上」。
  **凡是要丟到背景長跑的行程,先問一句:它跟 stdin 還有沒有關係?**
- **附帶結論**:「檔案跟著行程一起消失」是一個很強的訊號,
  它幾乎必然代表**整個環境重建過**,而不是程式出錯。下次看到要先往這個方向想。

---

## 2026-08-05(W2 D5)swampd 起不來,而且把整台 BMC 拖到重開機

- **現象**:照計畫做完 `mkdir -p /tmp/pidlog` → 傳設定 → 建 systemd drop-in →
  `systemctl daemon-reload && systemctl restart`。指令逾時。之後 SSH 連不進去,
  錯誤是 `Connection timed out during banner exchange`(TCP 通,但 SSH 的
  banner 送不出來)。再過幾分鐘 BMC **自己重開機了**。
- **假設**:(1) drop-in 寫錯,systemd 卡住 (2) 設定檔有問題讓 swampd 崩潰
  (3) 整台機器負載過高
- **先驗哪個、為什麼**:先驗 (3),因為 **banner exchange 逾時這個症狀本身就
  指向負載,不指向設定** —— TCP 三次握手成功代表 kernel 網路堆疊是活的,
  送不出 banner 代表 CPU 排不到 sshd。而且驗它只要看 `boot.log` 與宿主機的
  `ps` 的 CPU 欄,不必進得去 BMC。實測 QEMU 佔 143% CPU、guest load average 7.58。
- **根因(兩層,缺一不可)**:
  1. **`/tmp` 是 tmpfs,重開機就清空**,但 drop-in 在 `/etc` 是**持久的**。
     所以重開機之後 `--log /tmp/pidlog` 指向一個不存在的目錄,
     swampd 立刻 `exit 105`,journal 寫著 `--log: Directory does not exist: /tmp/pidlog`。
  2. 上游的 unit 是 **`Restart=always` + `RestartSec=5` + `StartLimitInterval=0`**
     —— **不限次數地無窮重啟**。於是每 5 秒起一次、每次失敗,把 QEMU 的 CPU 吃光。
- **修正(兩條都要)**:
  1. 把執行前提放進 unit 本身:
     `ExecStartPre=/bin/mkdir -p /tmp/pidlog /tmp/sys` 以及兩行建假 sysfs 檔的
     `ExecStartPre`。**這樣前提跟 unit 同生共死,不依賴任何人記得手動 mkdir。**
  2. 在測試床上把 `StartLimitIntervalSec=60` / `StartLimitBurst=3` 加回來。
- **★ 這一則最值得講的地方 —— 為什麼上游的設定沒有錯**:
  `StartLimitInterval=0`(永不放棄)在**真實伺服器**上是正確的:
  風扇控制停掉會燒硬體,寧可一直重試。但在**測試床**上,同一個設定會讓一個
  起不來的服務把整台機器拖垮。**同一份設定在不同環境下的正確答案不一樣 ——
  這不是上游的 bug,是我要判斷我在哪個環境。**
- **教訓**:**「持久的設定」搭「非持久的執行前提」= 重開機後必炸,
  而且炸在你不會聯想到的地方。** 症狀(SSH 連不上、機器重開)離根因
  (少了一個 /tmp 目錄)非常遠,中間隔著 systemd 的重啟策略。
  以後寫任何 unit,都要問:**它依賴的每一樣東西,壽命跟它一樣長嗎?**

---

## 2026-08-05(W2 D4/D6)這台 QEMU 上沒有風扇硬體 —— zone 怎麼建起來

- **現象**:swampd 的地雷是「每個 zone 至少要一顆風扇 ＋ 一顆溫感,否則
  `No fan zones` 起來就退出」。但實測這台 bletchley:
  `/sys/class/pwm/` 是空的、`/sys/class/hwmon/*/pwm*` 不存在、
  D-Bus 的 `/xyz/openbmc_project/sensors/` 底下**一顆 `fan_tach` 都沒有**
  (只有六顆 nvme 溫感與一顆 Virtual_Inlet_Temp)。計畫給的設定範本
  (`writePath` 指向 sysfs pwm)在這台機器上不可能成立。
- **我沒有用猜的,我去讀了原始碼**(`phosphor-pid-control` @ `f6d4cb9e5`)。
  `sensors/build_utils.cpp` 決定 `readPath`/`writePath` 走哪一條實作:
  ```cpp
  static constexpr auto sysfs = "/sys/";
  if (path.find(sysfs) != std::string::npos) { return IOInterfaceType::SYSFS; }
  ```
- **關鍵發現**:它用的是 **`find(...) != npos`(子字串比對)**,不是「開頭是」。
  所以 **`/tmp/sys/pwm0` 也會被判定成 SYSFS**。再看 `sysfs/sysfsread.cpp` 與
  `sysfs/sysfswrite.cpp`,實作就是單純的 `std::ifstream` / `std::ofstream` ——
  **對普通檔案完全適用**。
- **解法**:fan0 的 `readPath` 指向 `/tmp/sys/fan0_input`(內容是假的 tach 值),
  `writePath` 指向 `/tmp/sys/pwm0`。zone 於是有了「一顆風扇」,起得來。
- **另外兩個從原始碼讀出來、範本沒寫對的地方**:
  1. **`readPath` 不可以留空。** 留空會走 `default:` 建出 `WriteOnly`,
     而 `WriteOnly::read()` 是 `throw std::runtime_error("Not supported.")`。
  2. **`min`/`max` 只對 `type: "fan"` 有效。** `sensors/buildjson.cpp` 對非 fan
     型別會忽略並印 `Non-fan types ignore min value specified`。
     計畫範本在溫感 `die0` 上填了 `min/max`,那是噪音。
- **量化印證(這一段證明我讀對了)**:`builder.cpp` 在 `max > 0` 時選
  `SysFsWritePercent`,寫入值 = `min + (max-min) × value`;而
  `pid/fancontroller.cpp` 在寫之前做 `percent /= 100.0`。
  所以 `min:0 / max:255` 配 fan PID 的 `outLim 30~100`(百分比)應該得到:
  failsafe 100% → 255,正常 30% → 76。**實測 `/tmp/sys/pwm0` 就是 255 與 76。**
- **教訓**:**「範本在我的環境上跑不起來」的第一個動作,是去讀那個範本對應的
  解析程式碼,不是去改範本試。** 讀了三個檔案(約 20 分鐘)換到的是
  「我說得出每一欄為什麼那樣填」,而不是「我試到它會動」。
  後者在面試裡是負分。
- **誠實標註**:這顆風扇是**檔案背板的替身**,不是真實硬體。
  它證明的是「swampd 的寫出路徑被執行了、值是多少」,**不是「風扇真的轉了」**。
  README 與所有圖說都要這樣寫。

---

## 2026-08-05(W2 D6)`zone_0.log` 看起來停住了 —— 其實是緩衝

- **現象**:推完溫度後立刻 `grep` `zone_0.log`,**找不到剛推的值**;
  `tail -n 1` 拿到的是**半行**(`1785868892361,3000,Minimum,` 就斷了)。
  但 `pidcore.die0` 裡明明已經有 `input=40` 的紀錄。
  隔 5 秒再 `ls -l`,檔案大小**一個 byte 都沒變**,而 `systemctl is-active` 是 active。
- **假設**:(1) zone 停止運作了 (2) log 檔輪替 (3) **std::ofstream 的緩衝還沒 flush**
- **先驗哪個、為什麼**:先驗 (3),因為**「半行」這個細節幾乎只有緩衝能解釋** ——
  行寫到一半就沒了,代表資料是以固定大小的區塊落地的,而不是以行為單位。
  而且驗它只要「等久一點再看一次」,成本趨近於零。
- **根因**:swampd 用 `std::ofstream` 寫 CSV,預設是**全緩衝**(通常 4096 bytes)。
  以 10 Hz × 約 45 bytes/行 計算,大約 **每 9 秒才 flush 一次**。
  所以「5 秒內檔案大小沒變」是完全正常的。
- **驗證後拿到的真數字**:等 flush 之後回頭比對兩份 log 的 `epoch_ms`:
  | 事件 | epoch_ms | 差 |
  |---|---|---|
  | `pidcore.die0` 看到 `input=40` | 1785868902363 | — |
  | `zone_0.log` 記錄 `die0=40` | 1785868902461 | **98 ms** |
  | `pidcore.die0` 看到 `input=80` | 1785868904362 | — |
  | `zone_0.log` 記錄 `die0=80` | 1785868904461 | **99 ms** |

  **正好一個 zone 迴圈週期**(`cycleIntervalTimeMS` 預設 100 ms)。
- **教訓(這一則直接影響 W9)**:**`tail -f zone_0.log` 不能用來量時序。**
  你看到某一行的時間,不是那一行被產生的時間,而是緩衝滿了的時間 ——
  誤差可以到好幾秒,而且是**不固定**的。
  **要量延遲,必須用檔案裡自帶的 `epoch_ms` 欄位互相比對,不能用觀察者的時鐘。**
  W9 的端到端延遲量測如果用錯方法,量到的會是緩衝區大小,不是系統延遲。
