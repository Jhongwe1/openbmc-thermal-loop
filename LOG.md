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

---

## 2026-08-06(W3 D1,計畫排 08/11)計畫要走的那條路,這個映像裡根本沒有

- **現象**:W3 D1 的任務是走 route (b) —— 用 entity-manager 設定一顆
  `"Type": "ExternalSensor"`,由 `dbus-sensors` 建立、由外部 `busctl set-property`
  寫值。設定寫好之前我先看了一眼服務清單:
  ```
  /usr/lib/systemd/system/ 只有 adcsensor / fansensor / hwmontempsensor / psusensor
  /usr/libexec/dbus-sensors/ 也只有那四支
  find / -xdev -iname '*external*'  →  只有 rsyslog 跟 tpm2 的無關檔案
  ```
  **`externalsensor` 這支程式在這個映像裡不存在。**
- **假設**:(1) 我看錯地方,它在別的路徑 (2) 這個 build 壞了/漏包
  (3) **上游預設沒開這個 PACKAGECONFIG** (4) 這是平台特定的決定
- **先驗哪個、為什麼**:先驗 (3)。因為 (1) 已經被 `find /` 排除;
  而 (2) 與 (4) 都要下載別的映像才能驗(每次 56 MB + 2.5 分鐘開機),
  (3) 只要抓一個 4 KB 的 recipe 檔就能看。**先做最便宜且能一次排除最多可能的那個。**
- **查到什麼(推翻了假設 3)**:上游
  `meta-phosphor/recipes-phosphor/sensors/dbus-sensors_git.bb` 的預設**有** `external`。
  而且我特地抓了**映像建置當天(2026-07-27)那個 commit 的版本**核對,不是抓今天的
  master —— 因為「今天的預設」不等於「我這顆映像建的時候的預設」。
- **根因(在 vendor layer)**:
  ```bitbake
  # meta-facebook/recipes-phosphor/sensors/dbus-sensors_%.bbappend
  FACEBOOK_REMOVED_DBUS_SENSORS = " exitairtempsensor  external  intelcpusensor \
                                    intrusionsensor  ipmbsensor  mcutempsensor "
  PACKAGECONFIG:remove = "${FACEBOOK_REMOVED_DBUS_SENSORS}"
  ```
  **Meta 在他們自己的 layer 裡把 `external` 明文移除。** 這是長期決定,不是壞掉。
- **這個根因同時殺掉三個「再試試看」的方向**(所以值得多花 20 分鐘查):
  1. **換新映像沒用** —— 它不是某天的 build flake。
  2. **換備援平台沒用** —— `catalina` 也是 meta-facebook,吃同一個 bbappend。
  3. **沒有第三個平台可換** —— 依 `platform-matrix.md`,
     {Jenkins 有映像} ∩ {QEMU 有 machine} ∩ {有 swampd} 的交集就只有
     `bletchley` 與 `catalina`。
- **解法(route b′)**:改用這台機器上**真的存在**的硬體。
  `bletchley-bmc` 這個 QEMU machine 建了 **10 顆 tmp421 溫度晶片**,
  guest 裡的 Linux driver 已經綁上去、hwmon 節點都在(讀值 0 °C)。
  而 `hwmontempsensor` **在映像裡**,它的支援清單裡**有 `TMP421`**,
  而且它建感測器時會呼叫 `createInventoryAssoc()` —— **association 是免費送的**。
  溫度怎麼改?QEMU 的 tmp421 模型有可寫的 QOM property
  (`hw/sensor/tmp421.c` 的 `object_class_property_add("temperature0", ...)`),
  用 QMP `qom-set` 從外面寫。
- **換到的東西比原本的計畫更好**:注入點從「BMC 內部的假感測器」下移到
  **模擬硬體層**,下游多經過 **kernel driver** 與 **hwmon sysfs** 兩層真實程式碼。
  Gate 2 要的跨層追蹤與 Fig 6 直接到手。
- **教訓**:**「文件說要做 X」的第一個動作,是確認 X 在我的環境裡存在。**
  我如果直接寫設定、部署、重啟、看不到東西,再回頭查,會多花半天在
  「是不是我 JSON 寫錯」上。**先花兩分鐘 `ls` 一下,省下半天。**
  另外:**查上游 recipe 要查「我這顆映像建置當天」的版本**,不是 master。

---

## 2026-08-06(W3 D2)同一個 `timeout: 5`,在兩條路上意思不一樣

- **現象**:把 swampd 的 `die0` 從 route (a) 的 `extsensors` 換成 route (b′) 的
  passive D-Bus 感測器之後,溫度明明讀得到(`zone_0.log` 的 `die0_raw = 44.938`),
  但 `failsafe` 欄一直是 `1`、`/tmp/sys/pwm0` 卡在 `255`。
  journal 直接指名:`Zone 0 is in failsafe mode. With update at die0: The sensor has timed out.`
- **假設**:(1) 感測器真的沒在更新 (2) `timeout: 5` 的語意在 passive 上不一樣
- **先驗哪個、為什麼**:先驗 (2)。因為 (1) 已經被 `die0_raw = 44.938` 這個
  **有效的讀值**推翻了 —— 值進得來,卻被判定逾時,**那就不是「有沒有值」的問題,
  是「怎麼算逾時」的問題**。
- **去讀原始碼**(`phosphor-pid-control` @ `f6d4cb9e5`,`pid/zone.hpp`):
  ```cpp
  ReadReturn r = sensor->read();
  auto duration = duration_cast<seconds>(now - r.updated).count();
  auto period   = seconds(timeout).count();
  ```
  而 `r.updated`(`dbus/dbuspassive.cpp` 的 `_updated`)**只在收到
  `PropertiesChanged` 時才更新**。dbus-sensors 端則是**值有變才發訊號**。
  → **溫度穩定不動 = 沒有訊號 = 被當成感測器死掉。**
- **單一變因 A/B(唯一改動:`die0` 的 `timeout`)**:

  | | `timeout: 5` | `timeout: 0` |
  |---|---|---|
  | `failsafe` 欄 | **1** | **0** |
  | `/tmp/sys/pwm0` | **255** | **76** |
  | journal | `die0: The sensor has timed out.` | `Zone 0 fans, returning to normal mode, output pwm: 30` |

- **上游自己怎麼說**:`dbus/dbusconfiguration.cpp`(entity-manager 那條設定路徑)
  的註解白紙黑字:
  > *"Setting timeout to 0 is intentional, as D-Bus passive sensor updates are
  > **pushed in, not pulled by timer poll**."*

  也就是說**上游知道這件事,而且走 entity-manager 設定時會自動幫你設 0**。
  但我們走的是 `--conf` JSON 檔那條路(`sensors/buildjson.cpp`),
  **那條路照著 JSON 填什麼就是什麼,不會幫你改。**
- **教訓**:**同一個設定欄位,在不同的資料來源路徑下有不同的預設與語意。**
  route (a) 的 `HostSensor` 是「推進來」的,每次寫入都更新時間戳,
  所以 `timeout: 5` 是有意義的 stale 偵測;
  passive 感測器的時間戳綁在**值的變化**上,`timeout` 就變成了
  「多久沒變化就當它死了」—— 那對一顆穩定的溫感是錯的判準。
  **passive 感測器的存活狀態應該看 `OperationalStatus.Functional` 與
  `Availability.Available`(swampd 本來就有訂閱),不是看值變不變。**
- **W8 patch 候選**:`phosphor-pid-control` 的文件沒有寫這件事。
  JSON 設定那條路的使用者踩到的機率是 100%,而錯誤訊息
  (`The sensor has timed out`)會把人引導到完全錯誤的方向。

---

## 2026-08-06(W3 D2)PID 拿 0.8154 去跟 65 比 —— 換了感測器,單位悄悄變了

- **現象**:failsafe 解掉之後,`zone_0.log` 看起來正常,但打開
  `pidcore.die0`(PID 內部軌跡)發現:
  ```
  epoch_ms,input,setpoint,error,...
  1785947785628,0.815443,65,64.1846,...
  ```
  **`input = 0.8154`,`setpoint = 65`,`error = 64.18`。** 溫度是 79.938 °C。
- **假設**:(1) log 欄位對錯位 (2) **輸入被正規化到 0~1 了**
- **先驗哪個、為什麼**:先驗 (2),因為 0.815443 這個數字**看起來就像一個比例**。
  兩秒的心算就驗掉了:
  `(79.938 - (-128)) / (127 - (-128)) = 0.81544` —— **完全吻合**。
  而 `-128` / `127` 正是這顆 tmp421 在 D-Bus 上的 `MinValue` / `MaxValue`。
- **根因**:`dbus/dbuspassive.cpp` 對 passive 感測器會呼叫
  `scaleSensorReading(_min, _max, value)`,把讀值正規化成 `[0,1]`,
  而 `_min`/`_max` 是**從 D-Bus 感測器的 `MinValue`/`MaxValue` 屬性抓來的**。
  route (a) 的 `HostSensor` 沒有這兩個屬性,所以之前不會發生。
- **解法**:`sensors/buildjson.cpp` 有一個每顆感測器的旗標
  `"ignoreDbusMinMax": true`。加上去之後:
  ```
  zone_0.log :  ... ,die0=59.938, die0_raw=59.938, failsafe=0
  pidcore    :  input=59.938, setpoint=65, error=5.062      ← 對了
  ```
- **上游自己怎麼說**(同一段註解,就在 `timeout = 0` 的下一行):
  > *"Setting ignoreDbusMinMax is intentional, as this prevents normalization of
  > values to [0.0, 1.0] range, **which would mess up the PID loop math**.
  > All non-fan PID classes should be initialized this way."*
- **這一則最可怕的地方:它不會報錯。** 沒有警告、沒有 journal 訊息,
  服務是 `active (running)`,`zone_0.log` 的 `die0_raw` 也是對的。
  **只有打開 `pidcore.*` 才看得見。** 如果我沒有在 W2 就加上 `-g`(corelogging),
  這個錯會一路帶到 W6 調參 —— 那時候我會以為是我的 λ 算錯了。
- **教訓**:**換掉一個元件之後,不要只驗「有沒有東西出來」,要驗「單位對不對」。**
  而且**要驗最裡面那一層**:`zone_0.log` 三個欄位全對,錯的在 `pidcore.*`。
  外層正常不代表內層正常。

---

## 2026-08-06(W3 D5/D6)量化要做幾次?—— 一個差點讓 L1 與 L2 沒辦法比較的設計

- **現象(還沒發生,是先想到的)**:熱模型的 `step()` 依計畫要回傳
  「感測器讀到的溫度」,也就是含雜訊與**量化**的值。
  但 W5 之後 L2 的做法是:**把模型算出的溫度寫進 QEMU 的 tmp421,
  由真的晶片與真的 kernel driver 去讀。** 那顆晶片自己就會量化。
  → **同一個量化會發生兩次。**
- **量兩次的後果**:L2 量到的解析度誤差是實際的兩倍。
  而這個專案的核心宣稱之一是「**同一份 plant model 貫穿 L1~L3,
  所以 L1 的圖與 L2 的圖可以直接疊**」。
  疊起來差一個量化步階的話,那個差**看起來會像是「模擬與實機的差異」**,
  但其實是我自己造成的。**這種 bug 會被當成研究結果報出去。**
- **解法**:`ThermalPlant` 開兩個出口。

  | 方法 | 回傳什麼 | 給誰 |
  |---|---|---|
  | `step(pwm, P)` | 死區 + 遲滯 + **雜訊 + 量化** | L1(模型自己模擬整條量測鏈) |
  | `sensedAnalog()` | 死區 + 遲滯,**不含雜訊與量化** | L2(交給真的晶片去量化) |

- **順帶決定了 `lsb` 的值**:計畫範本填 0.5 °C(一般溫感的量級),
  **但我 08-06 實際量到這顆 tmp421 是 0.0625 °C**(設 40.000 讀回 39.938,
  暫存器只給 4 個小數位元 → 1/16)。
  用實測值不只是「比較準」,而是**讓 L1 與 L2 的量化行為一致** ——
  兩層要能直接疊,量化步階就不能是兩個不同的數字。
- **教訓**:**「同一份程式碼服務多層」不是把它 include 進去就成立的。**
  要逐項檢查每一層各自負責哪一段:哪一段是模型該模擬的、
  哪一段是那一層的真實元件會做的。**重疊的部分要拿掉,不是留著比較保險。**

---

## 2026-08-06(W3 D6)我對 QEMU 溫度上限的假設是錯的,而且是測出來才知道

- **背景**:熱模型在 0 RPM + 400 W 的開環穩態是 **165 °C**。
  W5 之後模型會自動餵值進 tmp421,所以我先加了一段量程夾制。
- **我當時寫的註解(錯的)**:「超出去 QEMU 會 `(int16_t)` 截斷,
  例如 165 °C 會**繞回負數**,而且不會有任何錯誤訊息。」
  推理依據是我看到 setter 最後一行有 `(int16_t)` 轉型。
- **實測打臉**:寫 165 °C,QEMU 直接回錯誤:
  ```
  qom-set 失敗:{'class': 'GenericError', 'desc': 'value 127.000 C is out of range'}
  ```
  **它有檢查,不是安靜截斷。** 而且連我夾制後的 127.0 也被拒絕。
- **回去把整個 setter 讀完(不是只讀最後一行)**:
  ```c
  static const int32_t mins[2] = { -40000, -55000 };
  static const int32_t maxs[2] = { 127000, 150000 };
  if (temp >= maxs[ext_range] || temp < mins[ext_range]) { error_setg(...); return; }
  ```
  範圍檢查在轉型**之前**。而且**用哪一組取決於晶片 CONFIG 暫存器的 range 位元** ——
  那個位元從 QOM 讀不到。上界是 `>=`,所以 127.000 剛好被排除。
- **改成的做法**:不硬猜是哪一組。**先照使用者給的值寫,被拒絕才夾制到
  保守的那一組(−40 ~ 126.999)再試一次**,並在 stderr 印「感測器飽和了」。
- **為什麼要印警告而不是安靜夾制**:夾制發生的那一段,**模型的值與 BMC 讀到的值
  不一致**,那段數據不能拿去擬合。安靜夾制會產生看起來很正常的假數據。
- **教訓兩條**:
  1. **只讀函式的最後一行就下結論,跟沒讀一樣。** 我看到 `(int16_t)` 就推論
     「會截斷」,但檢查在前面十行。
  2. **寫進註解的因果句要先測。** 這跟 08-05 那則(Gerrit 擋的是 email 不是名字)
     是同一種錯:**我把推論當成事實寫進交付物**。這次只花了兩分鐘就抓到,
     因為我剛好順手跑了一次超量程的值。

---

## 2026-08-06(W3 D7)測試綠了,但它抓得到 bug 嗎?

- **問題**:`meson test` 顯示 `1/1 plant OK`。但那是**一個執行檔**通過,
  不是「兩個斷言成立」。而且**一個永遠會過的測試也是綠的**。
- **做法(負向驗證)**:故意把熱阻內插的符號寫反 ——
  `(1.0 - pow(q, n))` 改成 `(pow(q, n))`,也就是讓「風越大熱阻越大」。
  重編、跑測試:
  ```
  [  FAILED  ] Plant.SteadyStateMatchesAnalytic
  [  FAILED  ] Plant.MonotonicInPwm
  ```
  **兩個都掛。** 改回來,兩個都綠。
- **順手修掉的一個報告問題**:`meson test` 預設把一個執行檔算成一個測試,
  所以兩個 case 全掛也只會顯示「1 個失敗」。加上 `protocol: 'gtest'`
  讓 meson 去解析 gtest 的 XML,報告才有意義。
- **`analytic()` 的已知弱點(寫在測試的註解裡)**:那個函式**複製了**
  `step()` 裡的熱阻公式。兩邊同時寫錯同一個地方的話,測試會過。
  **所以第二個測試 `MonotonicInPwm` 刻意不用它** ——
  它只斷言「方向對不對」,是完全獨立的一道防線。
- **教訓**:**「測試是綠的」跟「測試有在保護我」是兩件事。**
  新寫一個測試之後,花兩分鐘故意把被測物弄壞一次,確認它會紅。
  沒做過這一步的測試,只是一個會消耗 CI 時間的裝飾品。

---

## 2026-08-07（W4 D1）死區測試紅了，但錯的是容差不是死區

- **現象**：補完七個 L0 測試後跑 `meson test`，六綠一紅。
  ```
  Plant.DeadTimeDelaysResponse
  Expected: (maxDeviation) < (2.0 * p.lsb), actual: 0.1875 vs 0.125
  ```
  `0.1875` 剛好是 `3 × 0.0625`，也就是三個量化格。
- **三個假設**：
  1. **H1** 死區真的沒生效（`delay_` 佇列壞了）→ 若成立，`docs/plant-model.md`
     那張「前 3 秒 sensed 不動」的驗收表也是假的，W3 要重驗。
  2. **H2** 死區是好的，那 0.1875 是**雜訊**造成的。
  3. **H3** `before` 那一個基準點本身是離群值。
- **先驗哪個、為什麼**：驗 H2 —— 把 `noiseSigma` 設 0 重跑。
  一行改動、兩秒有結果，而且**一次切三刀**：
  偏移若掉到 0，H1/H3 同時被排除；若還是大，H1 就直接成立。
- **量到什麼**（同一段實驗跑四種設定，`~/scratch/deadtime_probe.cpp`）：

  | 設定 | `step()` 的最大偏移 | `sensedAnalog()` 的最大偏移 |
  |---|---:|---:|
  | 雜訊 ON + 量化 ON（原況） | **0.1875** | 3.18e-06 |
  | 雜訊 OFF + 量化 ON | **0.0000** | 3.18e-06 |
  | 雜訊 OFF + 量化 OFF | 0.0000 | 3.18e-06 |
  | **對照組：`deadTime = 0`** | **1.0625** | — |

- **根因**：**死區完全正常，是容差算漏了一項。**
  類比值在那 2.8 秒內只變 3.18e-06 °C（那是 `T_die` 還在漸近收斂的殘餘）。
  `2 × lsb` 這個容差只算了量化，**沒算雜訊**：
  σ = 0.05 的兩個讀值相減，σ√2 ≈ 0.0707；28 個樣本取最大約 2.6σ ≈ 0.185；
  量化到 0.0625 的格點就是 **0.1875** —— 與實測分毫不差。
  而量化本身貢獻 0，因為類比值不動就永遠落在同一格。
- **改成的做法**：拆成兩個斷言，容差都有物理來歷，而且**不綁 seed**。
  1. 類比值的變動 < **半個 LSB** —— 意思是「這點變動連量化器都看不見」。
  2. 多跑一台 `deadTime = 0` 的 plant 當**對照組**（其餘參數與視窗長度完全相同，
     單變因），斷言「有死區的偏移 < 對照組的一半」。實測 0.19 vs 1.06。
- **教訓兩條**：
  1. **絕對容差要把每一個誤差來源都算進去；算漏一項，測試就會冤枉被測物。**
     我差一點就去改 `delay_` 的程式碼 —— 那會把一個好的實作改壞。
  2. **能用對照組就不要用絕對容差。** 第二個斷言不需要我猜任何數字，
     換 seed、改 σ、改 τ 都不會假性失敗，因為兩邊一起變。
     這跟整個專案的實驗協定是同一件事：**單變因 A/B 比絕對門檻可信。**

---

## 2026-08-07（W4 D1）我的驗證腳本自己是綠的，但它什麼都沒在驗

- **背景**：W3 D7 我手動做過一次負向驗證（故意把符號寫反，確認測試會紅）。
  這次想把它變成可重跑的腳本，一次植入六種錯誤。
- **現象**：第一版腳本跑完，六個 mutation **全部**回報「❌ 沒有任何測試變紅」。
  照字面讀，意思是我七個測試全都是裝飾品。
- **三個假設**：
  1. 測試套件真的沒有鑑別力。
  2. 字串替換根本沒生效（植入失敗，跑的還是原始碼）。
  3. **失敗訊息抓取失敗**（測試有紅，但腳本沒看到）。
- **先驗哪個、為什麼**：驗 3。代價最低 —— 手動把腳本裡那一行指令貼出來跑一次
  就知道，不用改任何程式碼。而且假設 1 與 W3 D7 的手動結果直接矛盾，
  **與既有證據衝突的假設要排在後面驗**。
- **根因**：`meson test` **不加 `--print-errorlogs` 就不會印 gtest 的輸出**，
  只會印 `1/1 plant FAIL`。我 grep 的是 `[  FAILED  ] Plant.xxx`，
  那些行從來沒有出現過。
- **第二個根因（順手抓到的）**：M4 那一條回報的是「⚠ 找不到要替換的字串」。
  因為我為了 perl 的 `s///` 手動在字串裡加了 `\/`，結果 `grep -qF` 拿去做
  **字面**比對就找不到。**六個案例裡只有它誠實回報自己壞掉**，其他五個
  安靜地產生了假結果。改用 python 做字面替換之後這個問題整類消失。
- **修好之後的結果**（`./tools/mutation_check.sh`，六個全被抓到）：

  | 植入的錯誤 | 抓到的測試 |
  |---|---|
  | M1 熱阻內插符號反 | `MonotonicInPwm`、`SteadyState` |
  | M2 功耗項符號反 | 五個 |
  | **M3 死區佇列拿掉** | **只有 `DeadTimeDelaysResponse`** |
  | M4 一階離散化寫反 | 七個全部 |
  | **M5 rng 改成全域共用** | **只有 `Determinism`** |
  | **M6 `rthMin` 0.12 → 0.08** | **只有 `SaturationCaseHolds`** |

  M3 / M5 / M6 各自只有一個測試抓得到 —— 那三個測試是**唯一的防線**，
  而且它們守住了。
- **順手修掉的一個安全性問題**：第一版用 `git checkout --` 還原原始碼。
  那會連我**還沒 commit 的改動**一起洗掉。正式版改成「備份到暫存目錄 →
  `trap ... EXIT` 還原」，Ctrl-C 也還原得回來。
- **教訓**：**「驗證工具的綠」比「被驗證對象的綠」更危險，因為沒有人會去驗證驗證工具。**
  凡是會輸出「一切正常」的腳本，都要先讓它輸出一次「不正常」才能相信它。
  我原本要做的事是「確認測試會紅」，結果第一步是「確認我的『確認』會動」——
  這一層遞迴每加一層就少一個人做，所以錯誤最容易藏在最外層。

---

## 2026-08-07（W4 D3）擬合出來的 τ 比設定值小、θ 比設定值大，但總和是對的

- **背景**：兩點法寫完，在自己的 plant 上跑五個 seed 的開環階躍
  （PWM 40% → 60% @ 300 s，功耗固定 150 W，900 s，dt = 0.1 s）。
- **現象**：擬合結果與 `PlantParams` 裡填的數字對不上。

  | seed | K (°C/%PWM) | τ (s) | θ (s) | **τ + θ** | 殘差 RMS (°C) |
  |---|---:|---:|---:|---:|---:|
  | 0 | −0.3144 | 44.41 | 6.58 | 50.99 | 0.060 |
  | 1 | −0.3147 | 43.97 | 7.30 | 51.27 | 0.058 |
  | 2 | −0.3151 | 40.25 | 8.84 | 49.09 | 0.089 |
  | 3 | −0.3151 | 44.45 | 7.14 | 51.59 | 0.056 |
  | 4 | −0.3147 | 43.69 | 7.20 | 50.89 | 0.061 |

  模型設定的是 `τ_die = 45`、`τ_sense = 3`、`θ = 3`。
  照直覺，τ 應該量到 48 上下、θ 應該量到 3 —— 兩個都不對。
- **假設**：
  1. 兩點法實作有 bug（係數或百分比寫錯）。
  2. 基準值 y0 取錯，把整條曲線的門檻都算偏了。
  3. **不是 bug**：FOPDT 只有一個 τ，而模型有**兩個**一階環節串聯，
     多出來的那一段一定會被擠到某個參數裡。
- **先驗哪個、為什麼**：驗 3，因為它有一個**免費的判別式**：
  若假設 3 成立，`τ + θ` 應該守恆於 `τ_die + τ_sense + θ_true = 51.0`；
  若是實作有 bug，沒有理由剛好守恆。不用改一行程式碼就能判。
- **根因（假設 3 成立）**：五個 seed 的 `τ + θ` 中位數是 **50.99**，
  理論值 **51.0**，差 0.02%。
  **感測器那一段一階遲滯（τ_sense = 3 s）被兩點法算進了 θ 裡。**
  這與 `docs/plant-model.md` 早就寫下的那句話是同一件事的反面：
  「把死區用一階濾波器近似，FOPDT 擬合會把 θ 算進 τ 裡」——
  反過來，把一階遲滯餵給只有一個 τ 的模型，它會把遲滯算進 θ 裡。
- **第二個證據：殘差就是雜訊底。**
  量測雜訊 σ = 0.05，量化的 RMS 是 `lsb/√12 = 0.0625/3.464 = 0.018`，
  合成 **0.053 °C**。實測殘差 0.056~0.060。
  **殘差幾乎等於雜訊底，代表 FOPDT 這個形狀沒有系統性偏差**，
  剩下那 0.028 °C 的系統性成分對 6.35 °C 的變化量而言是 0.4%。
- **教訓**：**「量到的值跟設定的值不一樣」不等於「量錯了」。**
  先問「我的量測方法能不能表達我設定的東西」——
  FOPDT 只有一個 τ，我的模型有兩個，這是模型階數不匹配，不是 bug。
  而判斷它的方法是找一個**守恆量**：單看 τ 或單看 θ 都會誤判，
  看 τ + θ 一秒就清楚了。

---

## 2026-08-07（W4 D3）mutation 回報「編不過」的時候，其實什麼都沒驗到

- **背景**：我把 y0 從「階躍前那一個點」改成「階躍前 10 秒的平均」
  （計畫範本是單點）。這是工程判斷，所以照規矩要有測試守著，
  於是寫了 `Identify.BaselineAveragingReducesSeedSpread`：
  同一批 seed、只改 `baselineS` 這一個變因，斷言取平均後 K 的離散度
  小於單點的一半。
- **現象**：`tools/mutation_check.sh` 的 I4 回報 **「✅ 編不過」**。
  表格上是綠的，`exit=0`，看起來一切正常。
- **問題**：「編不過」代表**測試根本沒被執行**。我寫那個測試就是為了守 I4，
  結果 I4 是被編譯器擋下來的，那個斷言到底有沒有效**完全沒有被驗證**。
- **根因**：我的 mutation 把 `const double y0 = baselineMean(y, iStep, nBase);`
  整行換成 `y[iStep]`，於是 `nBase` 變成未使用變數，
  被 `-Werror`（`warning_level=3` + `werror=true`）擋在編譯期。
- **改成的做法**：把 mutation 改成**編得過**的版本 ——
  `std::max(1.0, baselineS / dt)` 改成 `std::min(...)`，
  讓 `nBase` 仍然被使用但值變成 1（等價於單點）。
  改完之後 I4 由 `Identify.BaselineAveragingReducesSeedSpread` 抓到，
  這才是我要的證據。
- **教訓**：**設計 mutation 的時候要避開編譯期。**
  「編不過」在 mutation testing 裡是弱證據：它證明的是編譯器有在工作，
  不是我的測試有在工作。這跟前一則（驗證工具自己是綠的）是同一個病 ——
  **一個綠色訊號如果可能來自兩個不同的原因，它就不構成證據。**

---

## 2026-08-07（W4 D5→D6）第一張圖畫出來了，然後我發現它證明不了任何事

- **背景**：Fig 1 的規格寫得很明確 ——「擬合曲線疊在原始資料上，**看得到雜訊**。
  平滑過的曲線看不出是不是編的。」這是反造假設計。
- **現象**：第一版圖產出來，九項檢查裡有八項都打勾了：階躍時刻有標、
  K/τ/θ 有標、殘差 RMS 有標、五個 seed 全畫、死區有陰影、caption 三要素齊全、
  座標軸有單位。**只有「看得到雜訊」那一項，看起來像過了但其實沒過。**
- **問題出在哪**：我畫了完整的 0~900 s。前 240 s 是 plant 從 25 °C 冷機
  暖到工作點 61 °C 的過程 —— 那 36 °C 的爬升把 y 軸整個撐開，
  而真正的實驗（61 → 54.6，只有 6.35 °C）被壓在圖的上緣 20% 裡。
  結果：
  - σ = 0.05 °C 的雜訊在那個尺度下是 **0.7 個像素**，看不見；
  - 0.0625 °C 的量化階梯同理，看不見；
  - θ = 7.2 s 在 900 s 寬的圖上是 **一條線**，不是一段區域；
  - 五條 seed 完全重疊，看起來像一條。
  **那張圖看起來就像一條畫上去的平滑曲線 —— 也就是規格明文要避免的那個樣子。**
- **另一個一開始沒注意到的問題**：擬合曲線我從 t = 0 一路畫到底，
  階躍前那一段是平的。那**暗示 FOPDT 模型也預測了暖機過程** ——
  它沒有，它只描述階躍之後。畫過頭本身就是一種輕微的誇大。
- **改成的做法（四項，全部是版面決定，不是加註解）**：
  1. x 軸從階躍前 60 s 開始。暖機段不是實驗的一部分。
     **並在 caption 明講「略過的是什麼、為什麼、完整資料在哪」**——
     裁切如果不說明，跟藏資料沒兩樣。
  2. 加一個**死區放大鏡**（階躍前後 50 s 的 inset）。
     θ 從一條線變成一段看得見的平台，量化階梯也在這裡現形。
  3. 加一個**殘差面板**。殘差 RMS 是一個數字，數字看不出「有沒有系統性偏差」；
     畫出來才看得到它是不是圍著 0 隨機分布。
     實際畫出來看到：階躍後 ±0.22 °C，之後收斂到 ±0.1 —— 那個結構就是
     「FOPDT 用一個 τ 去套兩個一階環節」留下的系統性偏差，**看得見比報一個數字誠實**。
  4. 擬合曲線只畫在 t ≥ 階躍時刻，另外用點線標出 y₀ 的取樣區間。
- **教訓兩條**：
  1. **反造假設計不是加註解，是版面決定。**
     一張把資料壓成一條線的圖，再誠實的 caption 也救不回來 ——
     因為讀者看的是線，不是字。
  2. **檢查表打勾 ≠ 通過檢查。** 那九項我第一版逐條看過，
     「看得到雜訊」我當時是打勾的，因為我知道雜訊在裡面。
     **但檢查表問的是「讀者看不看得到」，不是「我知不知道」。**
     這跟前面兩則（驗證工具自己是綠的、mutation 編不過）是同一個病：
     **我一直在檢查我已經知道答案的東西。**

---

## 2026-08-09（W5 D1）PID 係數的符號：兩分鐘的實驗，省掉兩天的除錯

> ⚠️ **這一則不是除錯紀錄，是預防性實驗。** 我沒有先遇到「風扇越熱轉越慢」
> 再回頭查 —— 我是在寫任何係數之前，先花兩分鐘把符號量出來。
> 格式仍然照〈假設 → 先驗哪個 → 根因〉走，但「現象」那一欄是我**製造**的，
> 不是撞到的。這個差別要講清楚，否則就是把一個順利的決定包裝成一次英勇的除錯。

- **待驗的命題**：`ec::pid()` 的誤差定義是 `error = setpoint - input`。
  `input` 是絕對溫度（`type: "temp"`）時，溫度上升會讓 `error` 變負，
  所以**比例係數必須是負的**，輸出（風扇轉速需求）才會隨溫度上升。
  **這句話是從原始碼推出來的，不是量出來的。** 地雷 #9（係數符號搞反）
  預估損失 1~2 天，而驗證成本是兩分鐘。
- **實驗設計，以及兩個計畫沒說、但會讓實驗失敗的細節**：
  1. **觀察的是溫度 PID 自己的輸出，不是 PWM。**
     swampd 是**串級**的：溫度 PID（1 Hz）算出 RPM setpoint，
     風扇 PID（10 Hz）才把 RPM 誤差轉成 PWM。本專案的風扇 PID 係數目前是 0，
     **PWM 根本不會動**，照計畫盯著 PWM 看會得到「兩組一模一樣」的結論。
     改看 `swampd -g` 寫的 `/tmp/pidlog/pidcore.die0`（欄位定義在上游
     `pid/ec/logging.cpp` 的 `DumpContextHeader()`）。
  2. **係數用 ±500，不是計畫寫的 ±100。**
     `die0` 的 `outLim_min` 是 3000（zone 的 `minThermalOutput`），誤差是 ±10 °C，
     `Kp=100` 時 `|輸出|` 只有 1000 —— **兩個溫度點都會被箝到 3000，
     實驗會「成功地什麼都沒測到」。**
- **量到什麼**（`./tools/sign_check.sh 500` 與 `./tools/sign_check.sh -500`，
  原始資料 `bench/data/exp02_signcheck/`；設定檔只有 `proportionalCoeff`
  一個欄位不同，而且是用程式改的，改完 `assert` 只動到一個 PID）：

  | `proportionalCoeff` | 55 °C 的輸出 | 75 °C 的輸出 | 判讀 |
  |---|---:|---:|---|
  | **+500**（正） | **5031** | **3000** | ❌ 越熱轉越慢 |
  | **−500**（負） | 3000 | **4969** | ✅ 越熱轉越快 |

- **根因（命題成立）**：`temp` 型別要用負係數。
  或者用 `convertTempToMargin` + `convertMarginZero` 在設定檔層級把它轉成 margin
  —— **那兩個欄位 `configure.md` 沒有記錄**（見 `docs/upstream.md` 候選 2）。
- **★ 一個計畫沒預期的觀察**：兩組在 3000 那一格是**完全一樣**的
  （都被 `outLim_min` 箝住）。也就是說：
  - **單點量測分不出符號對錯。** 這正是它叫「**兩點**檢查」的原因，
    不是文件寫爽的。
  - 而且符號錯的真正症狀不是「風扇越熱轉越慢」那麼明顯 —— 在誤差不夠大的
    工作區間裡，症狀是**風扇卡在最低速，而且一切看起來都正常**。
    **箝位把一半的資訊吃掉了。** 安靜的錯誤比大聲的錯誤難查。
- **教訓三條**：
  1. **不要假設「PID 就是那個 PID」。** 控制律的符號取決於誤差怎麼定義，
     而那是**實作決定的**，不是理論決定的。以後接手任何控制器，
     第一件事就是兩點符號檢查。
  2. **設計實驗時要先問「這個量測看得到我要驗的東西嗎」。**
     這次有兩個地方會讓實驗變成空的（看錯訊號、係數太小被箝位），
     兩個都不會報錯，都只會給我一組「看起來很正常」的數字。
  3. **箝位會吃掉資訊。** 這對之後的 anti-windup A/B（W7）是直接的提醒：
     實驗參數要先確認**待測的差異落在沒有被箝住的區間裡**。

---

## 2026-08-09（W5 D1）背景跑的 QEMU 在 U-Boot 倒數結束時消失，而 `nohup` 擋不住

- **現象**：把 QEMU 丟到背景開機（`nohup ./harness/qemu/run_bmc.sh bletchley &`），
  三分鐘後 `ssh` 回 `Connection refused`。開機 log 停在
  `Hit any key to stop autoboot:  2  1`，之後一個字都沒有，`pgrep qemu-system-arm`
  也是空的。**看起來跟 W2 D4 的坑 14 一模一樣。**
- **三個假設**：
  1. **H1** 就是坑 14：`-nographic` 把 monitor 留在 stdio，背景執行時 stdin EOF
     讓 QEMU 正常結束。
  2. **H2** U-Boot 在等鍵盤輸入，serial 導到檔案之後讀不到東西。
  3. **H3** QEMU 收到了某個訊號。
- **先驗哪個、為什麼**：先驗 **H1**，因為它有前例、而且**兩秒就驗得完**
  ——`run_bmc.sh` 裡已經有那段修正（`QEMU_SERIAL` 不是 stdio 時改用
  `-display none -monitor none`），只要確認那條分支有走到即可。
  結果：確實走到了，`ps` 的指令列印著 `-display none -monitor none`。**H1 排除。**
  接著看啟動器的 stderr（我本來只看開機 log，沒看啟動器自己的輸出）：
  ```
  qemu-system-arm: terminating on signal 1
  ```
- **根因**：**signal 1 = SIGHUP，而 `nohup` 對 QEMU 無效。**
  `nohup` 的做法是把 SIGHUP 設成 SIG_IGN 再 exec；`exec` 的確會保留「被忽略」
  這個狀態。但 **QEMU 自己註冊了 SIGHUP 的處理函式**，那一步把繼承來的 SIG_IGN
  蓋掉，於是 `wsl` 這一次呼叫結束、session 被拆掉時，SIGHUP 送進來就把它收掉了。
  改用 `setsid`（開一個新的 session，根本不會收到那個 SIGHUP）之後正常。
- **教訓兩條**：
  1. **同一個症狀可以有兩個完全不同的根因。** 坑 14 與這次的畫面幾乎一樣
     （開機開到一半安靜消失、離開碼看起來沒事），但一個是 stdin EOF、一個是 SIGHUP。
     分辨它們的**只有一行**：啟動器的 stderr 上那句 `terminating on signal 1`。
     **我第一次沒看那個檔案，因為我已經先認定是坑 14 了。**
  2. **`nohup` 只保證「訊號處理狀態被繼承」，不保證程式不去改它。**
     要真的讓一個程式脫離 session，用 `setsid`。

---

## 2026-08-09（W5 D2）我以為那顆 tmp421 是 entity-manager 建的 —— 錯了

- **背景**：W3 為了讓 swampd 有溫度可讀，我用 entity-manager 設定了一顆 TMP421
  （`/etc/entity-manager/configurations/ThermalLoopDemo.json`，bus 0、位址 `0x4f`）。
  所以做 Fig 6 之前，我的預設是「這顆裝置是 entity-manager 在執行時期
  用 `new_device` 建出來的」。**如果這是真的，Fig 6 的第一格（device tree）
  就不存在，整張圖的敘事要重寫。**
- **怎麼驗的**：讀 sysfs，兩個欄位就分得出來。
  ```
  $ readlink -f /sys/bus/i2c/devices/0-004f/of_node
  /sys/firmware/devicetree/base/ahb/apb/bus@1e78a000/i2c@80/tmp421@4f
  $ cat /sys/bus/i2c/devices/0-004f/modalias
  of:Ntmp421T(null)Cti,tmp421
  ```
- **根因**：**裝置本來就在 device tree 裡**（`bletchley` 的 dts 宣告了 **10 顆**
  tmp421），kernel 依 `compatible = "ti,tmp421"` 直接綁上。
  `of_node` 存在、`modalias` 以 `of:` 開頭，兩者都是「從 device tree 來的」的證據；
  執行時期建出來的會是 `i2c:tmp421`，而且沒有 `of_node`。
  **entity-manager 做的是另一件事**：它發布一個 Configuration 物件，
  讓 `dbus-sensors` 的 `hwmontempsensor` 知道「這顆要認領、名字叫 die0」。
- **順帶量到的東西（比原本要做的還值錢）**：一顆感測器要出現在 D-Bus 上，
  **「硬體在」與「設定在」是兩個獨立的必要條件**，而這台機器同時給了我兩種失敗：

  | | 硬體在 | 硬體不在 |
  |---|---|---|
  | 有 EM 設定 | ✅ `die0` | ❌ `FRONT_PANEL_TEMP`（SI7020 @ bus10 `0x40`，QEMU 沒模擬那顆） |
  | 沒有 EM 設定 | ❌ 另外 9 顆 tmp421 | — |

  證據在 `bench/data/exp03_trace/raw/42_counts.txt`、`44_config_without_hardware.txt`、
  `45_dts_tmp421_count.txt`。
- **教訓兩條**：
  1. **「我做了 X，所以 X 是原因」是最容易騙過自己的推論。** 我確實設定了
     entity-manager，感測器確實出現了，但那兩件事之間少了一環 ——
     裝置本來就在。**沒有去看 `of_node`，Fig 6 的第一格就是編的。**
  2. **這個誤會被抓到，是因為圖規定「每一格都要是我機器上的真實字串」。**
     如果我只是照計畫的範例圖畫，永遠不會發現。**反造假設計順便抓到了我的無知。**

---

## 2026-08-09（W5 D5）計畫抄的 `ec::pid()` 有三處與原始碼不符

- **背景**：D5 要寫自己的 PI，D6 要跟上游 `ec::pid()` 逐步比對。
  計畫在 D1 給了一段 `ec::pid()` 的虛擬碼。
- **現象**：我先讀了釘住那個 commit（`c5e59550d3`）的真正原始碼，
  發現與計畫給的虛擬碼有三處不同。三處**都會改變輸出**：

  | # | 計畫寫的 | 原始碼實際上 | 什麼時候會咬到 |
  |:--:|---|---|---|
  | 1 | `if (derivativeCoeff != 0) { 算 D }` | **沒有這個判斷**，每輪無條件計算 | `ts` 為 0 時會是 inf/NaN（上游註解自己寫了 "assumes the ts field is non-zero"） |
  | 2 | 最後那次 `clamp(integralTerm)` 只在 slew 生效時做 | **無條件執行**，每輪都做 | 回算把積分推出 `integralLimit` 時 |
  | 3 | 回算發生在「slew **限制住了**輸出」時 | **只要 `slewNeg` 或 `slewPos` 不是 0 就回算** | slew 有設定但沒咬到的每一輪 |

- **第 3 點為什麼最重要**：它把分歧的條件從「slew 咬到」放寬成「slew 有設定」。
  照計畫寫，`slewPos=2` 而輸出根本沒被限速的那些輪，我不會回算、上游會 ——
  兩邊的積分從那一刻起就分家，而且**輸出要好幾輪之後才看得出來**。
- **我怎麼處理**：`controller/pi.hpp` 多一個 `AntiWindup::UpstreamParity` 模式，
  逐行複製上游的順序，**刻意不與我自己的四種策略共用程式碼** ——
  那條路徑的規格不是「一個好的控制器」，是「上游此刻的行為」。
  共用的話，我哪天改進自己的實作，會把比對基準一起改掉，而那正是 parity 測試
  唯一要防的事。
- **教訓**：**二手的程式碼摘要不能當規格。**
  計畫那段虛擬碼看起來完全合理，三個差異都是「合理化」的方向
  （加上 `if` 判斷、把 clamp 收進條件式裡）——**它比原始碼「更像正確的程式碼」，
  所以更不容易起疑。** 逐行比對的成本是 20 分鐘，被它咬到的成本是整個 parity 測試
  的結論失效。

---

## 2026-08-09（W5 D6）meson 不准我碰 subproject 的檔案，而止損方案會弄壞我的宣稱

- **現象**：照計畫把 `subprojects/phosphor-pid-control/pid/ec/pid.cpp` 直接加進
  parity 測試的 target，`meson setup` 直接失敗：
  ```
  ERROR: Sandbox violation: Tried to grab file pid.cpp from a nested subproject.
  ```
- **計畫的止損方案**：把 `pid.cpp` / `pid.hpp` 兩個檔案 vendor 進 `third_party/`，
  README 註明來源 commit 與 Apache-2.0。
- **為什麼我不用它**：這個測試的價值整個押在一句話上 ——
  「**我的測試真的在編上游的程式碼**，不是重寫一版然後宣稱一樣」。
  複製進來之後，那句話就退化成「我的測試在編一份我自己維護的副本」。
  止損方案本身沒錯，但它損失的正好是我最想留的那樣東西。
- **改用的做法**：meson wrap 的 **`patch_directory`** ——
  我在 `subprojects/packagefiles/phosphor-pid-control-parity/meson.build` 寫一份
  只編三個編譯單元的 `meson.build`，wrap 下載後會用它蓋掉上游那份。
  commit 仍然釘死在 `.wrap` 裡、編的仍然是上游的原始碼、repo 裡沒有任何副本。
- **實際踩到的三件事**：
  1. `pid.cpp` 不只需要自己 —— 它呼叫 `LogInit/LogPeek/LogContext`（`pid/ec/logging.cpp`），
     那支又用到 `coreLoggingEnabled` 等全域旗標（`pid/tuning.cpp`）。
     **三個編譯單元，而且合起來只依賴標準函式庫**（不需要 sdbusplus / boost / systemd）。
  2. 上游那三個檔在我的 `warning_level=3 + werror=true` 底下編不過。
     解法是在 subproject 的 `meson.build` 裡設 `warning_level=0, werror=false` ——
     **不是去改上游的程式碼**。改了的話，比對的就不是上游那一份了。
  3. ★ **`dependency(..., required: false)` 不會去看 wrap。** 輸出是
     `Run-time dependency upstream-ec-pid found: NO (tried pkgconfig and cmake)`，
     然後 parity 測試**安靜地從測試清單裡消失**，`meson test` 依然全綠。
     要加 `allow_fallback: true`。
- **教訓兩條**：
  1. **止損方案要看它損失的是什麼。** 「退版也完全可以接受」這句話成立的前提是
     退掉的東西不是這件事的重點。這次退掉的正好就是重點。
  2. **「少建了一個測試」比「建置失敗」危險。** 建置失敗會叫，少一個測試不會 ——
     `Ok: 3 Fail: 0` 看起來跟 `Ok: 4 Fail: 0` 一樣令人放心。

---

## 2026-08-09（W5 D7）parity 一次就綠，所以我去證明它會紅

- **現象**：`test_parity_upstream` 第一次執行就全綠 —— 72 組參數組合、
  每組約 90 個時間步，逐步吻合到 `1e-12`。
- **為什麼這是可疑的訊號**：這一週前面才剛發生兩件事 ——
  我照計畫寫的兩個 PI 測試紅了（而且錯的是我的前提），
  以及計畫的虛擬碼有三處與原始碼不符。
  在那個背景下，「一次就完全吻合」比較像是**測試沒在測**，而不是我寫得好。
  這也是 W3 D7 就立下的規矩：**測試綠 ≠ 測試有在保護我。**
- **怎麼驗的**：把 `controller/pi.cpp` 加進 `tools/mutation_check.sh`，
  植入 5 個「我真的可能寫錯」的錯（C1~C5），其中 C1~C3 就是上面那三處
  計畫寫錯的地方。**如果 parity 測試抓不到那三個，它證明的就不是「我讀懂了上游」，
  只是「兩份實作今天剛好一致」。**
- **★ 設計 C2 的時候發現 parity 測試自己有洞**：
  C2 是「上游的回算多扣了前饋」。但我原本的主要比對**只掃 `ffGain = 0`**
  （我當時的理由是「ff != 0 時會分歧」）—— 那是把兩件事混在一起：
  分歧的是**我自己的標準回算**，而 `UpstreamParity` 這個模式的規格是
  「**不管參數是什麼**，都要跟上游一模一樣」。
  補上 `ffGain ∈ {0, 0.4}` 之後（組合數 36 → 72），C2 才抓得到。
  **補之前它會是 survivor。**
- **結果**：15 個植入的錯誤全部至少被一個測試抓到。
- **量到的分歧**（`DivergesWhenSlewAndFeedForwardCoexist`，
  `slewPos=2 slewNeg=-3 ffGain=0.4 setpoint=65 outLim=[30,100]`）：
  第一個分岔在第 **13** 步，輸出最大差 **4.75**（輸出範圍寬 70），積分最大差 **62.5**。
  把 `ffGain` 設成 0 則逐步一致到 `1e-12` —— 這條控制組證明分歧確實來自前饋項。
- **教訓兩條**：
  1. **設計負向驗證會逼你重讀正向測試的涵蓋範圍。**
     這個洞不是跑測試發現的（跑幾次都綠），是「我要植入哪一種錯」逼出來的。
  2. **「因為會分歧所以不掃」是錯的推論。** 該問的是「這個模式的規格是什麼」——
     規格是「複製上游」，那就沒有任何參數可以豁免。
     會分歧的是**另一個模式**，那該由另一個測試去管。

---
---

# 2026-08-09（W5 收工後的稽核與修復）

> 這一段是 W5 全部做完、push 完之後，**回頭不信任自己的結論**做的一次完整稽核。
> 方法：重讀 repo 的實際產物、用 WebFetch 讀四份一手上游原始碼核對、
> 跑三個新的實測把「我覺得有問題」變成「有證據有問題」。
> 找到 17 項。下面記的是其中最值錢的幾則。

---

## 2026-08-09（稽核 1）一個「數字對、但推導是錯的」量測

- **現象**：`docs/plant-model.md` 的參數表寫著
  「`lsb = 0.0625 °C`【驗】★ 實測：設 40.000 °C 進 QEMU 的 tmp421，
  BMC 讀回 **39.938**。那顆晶片的溫度暫存器只給 4 個小數位元 → 1/16 °C」。
  這條標了【驗】，也就是「我自己量到的」。
- **我為什麼回頭懷疑它**：不是因為數字看起來怪 —— `0.0625 = 1/16` 完全合理。
  是因為**它只用了一個點**。而這個專案自己的反造假清單第一條就是
  「原始資料不平滑、不取平均畫上去，**看得到雜訊才知道是量出來的**」。
  一個點畫不出雜訊，也畫不出階梯。
- **假設**：(1) 推導成立，只是證據薄　(2) **推導根本不成立**
- **先驗哪個、為什麼**：先驗 (2)，而且用**紙筆**驗，不用機器。
  理由是成本：`40.000 / 0.0625 = 640`，是整數 ——
  **40.000 剛好落在 1/16 的格點上**。一個純粹的 4 位元小數量化器
  對格點上的值應該是**恆等映射**，也就是應該回 40.000。
  這三十秒的心算就推翻了那條推導，不需要開 QEMU。
- **根因**：那 62 m°C 的差**不是量化**，是 QEMU setter 的截斷：

  ```c
  s->temperature[i] = (int16_t)((temp * 256 - 128) / 1000) + offset;
  //                                     ^^^^^ 半個 LSB 的預先扣除，
  //                                           配上 C 的往 0 截斷，
  //                                           把值壓到自己那一格的正下方
  ```

  **量化與偏壓是兩件事**，被我混成一件。而且更糟的是：
  **數字（0.0625）是對的。** 靠巧合對的結論最難發現，因為它不會出錯。
- **怎麼修的**：升級成一個正式實驗 `exp04`，證據換成**階梯本身**：
  細掃注入值，BMC 的讀值只落在 **7 個相異階**上，階距在 62 與 63 之間交替
  （一格 = 62.5 m°C，不是整數）。偏壓另外量：7 個格點 × 5 次重複
  = **35 個觀測，全部 −62 m°C，零例外** → 系統性，不是隨機。
- **教訓三條**：
  1. **【驗】這個標記是有重量的。** 它宣稱的不只是「數字是這個」，
     還包括「我知道它為什麼是這個」。後者錯了，前者對也沒用。
  2. **一個點量不出解析度。** 解析度是「階梯」的性質，要看到階梯本身。
     而我當初挑的那個點（40.000）**正好是最不可能暴露問題的那一個** ——
     格點上的值對純量化器是恆等映射。
  3. **這一條我沒有刪掉，我把它留在文件裡當成範例。**
     「我曾經寫過一條推導不成立的【驗】」比一份看起來從來沒錯過的文件有價值。

---

## 2026-08-09（稽核 2）★★ 量測工具比現象慢，於是我量出「現象不存在」

- **現象**：稽核時懷疑 hwmon 讀值有快取（注入後立刻讀會拿到舊值）。
  寫進 `bench/exp04_injection.py` 的自我檢查，跑起來 —— **完全觀察不到**。
  四次注入，四次「立刻讀」都拿到新值。看起來就是「這台機器沒有快取」。
- **我為什麼不接受這個結論**：因為它與一手原始碼衝突。
  `drivers/hwmon/tmp421.c` 白紙黑字寫著：

  ```c
  if (time_after(jiffies, data->last_updated + (HZ / 2)) || !data->valid) {
      ... 真的去 i2c 讀 ...
  }
  ```

  `HZ / 2` = **500 ms**。程式碼說有，我卻量不到 —— 一定有一邊錯。
- **假設**：(1) 這個 kernel 版本改掉了　(2) QEMU 的模型繞過了它
  (3) **我的取樣太慢，每次都晚於快取窗口**
- **先驗哪個、為什麼**：先驗 (3)。理由是**它是唯一我能立刻量的**：
  在讀取迴圈外面包一個計時就知道單次讀取要多久，五秒鐘的事。
  而 (1)(2) 都要去翻另一份原始碼或反組譯，成本高一個數量級。
  **而且 (3) 如果成立，(1)(2) 就不必查了。**
- **結果**：單次「讀取」是 **~0.4 s** —— 因為我每讀一次就**開一條新的 ssh**
  （TCP 連線 + 密碼認證 + 執行 `cat`）。而要量的窗口是 0.5 s。
  **量測工具與現象同一個量級。**
- **根因**：取樣週期沒有遠小於要觀察的時間尺度，所以「立刻讀」其實一點都不立刻。
  改成**一條持久的 ssh 連線上跑迴圈**（`while read -r _; do cat X; done`，
  單次降到毫秒等級）之後，量出來的注入到可見延遲是
  **中位數 351 ms，範圍 178~423 ms** —— 漂亮地落在 0~500 ms 之間，
  與「注入時刻相對快取窗口是均勻分布」完全一致。
- **★ 教訓（這是這次稽核最重要的一條）**：
  **「我量不到」和「它不存在」是兩件不同的事。**
  判斷方法很簡單：**先問自己的取樣速度，再下結論。**
  取樣週期沒有比要量的現象快一個數量級以上，任何「沒觀察到」都不算數。
  這其實就是取樣定理在工程現場的樣子，只是它平常不長這個名字。
- **附帶的教訓**：我第一版差一點就把「這台機器沒有快取」寫進文件。
  救我的不是更仔細，是**我先去讀了原始碼，所以有一個可以牴觸的預期**。
  沒有預期的量測，量到什麼都會被接受。
- **對後續的殺傷力（這才是為什麼要修）**：W6/W7 的 L2 閉環如果從 host 驅動
  「注入 → 讀 → 算 → 再注入」，整條迴路會慢一拍。那一拍會表現成
  **額外的死區 θ** —— 剛好是 W4 花一整天量出來、還用 `τ+θ` 守恆交叉驗證過的
  那個量。到 W9 做 L1 vs L2 對照時，症狀是「實機比模擬多一個取樣的死區」，
  而我會跑去改熱模型 —— **改錯地方，而且改完數字還會變好看**。

---

## 2026-08-09（稽核 3）★ 我的驗證機制會讓實驗變成同義反覆

- **現象**：修好上面那條之後，`tools/set_die_temp.py` 有了 `--verify`：
  注入後**輪詢到讀值等於我算出來的預測值**為止，否則失敗。
  很自然的下一步是「exp04 掃描時每一點都用這個等待邏輯」——
  修復計畫也是這樣寫的。
- **停下來的理由**：如果我「等到讀值等於預測值」才記錄，
  那 CSV 裡的 `hwmon_mC` **永遠不可能與 `expected_mC` 不同**。
  於是「預測式命中 68 個實測點」這句話就不是量測結果，是**我的停止條件**。
  這種錯不會讓任何測試變紅，也不會讓任何數字看起來怪 ——
  它只是讓整個實驗什麼都沒證明。
- **怎麼處理**：把兩件事拆開。
  - **閘門**用預測值：`--verify` 的工作是「確認注入到了」，用預測值比對很好，
    QEMU 或 kernel 換行為時會大聲失敗。
  - **量測**用穩定性：連續 4 次讀到同一個值、橫跨 1.05 s（超過兩個快取窗口）
    才採計。**那條判定裡沒有出現預測值。**
    預測只在事後當成 CSV 的一欄，讓「預測 vs 實測」變成一個可以被檢查的**比較**。
- **教訓**：**同一個機制，當閘門與當量測儀器，要求是相反的。**
  閘門要「符合預期才放行」，量測要「不管預期是什麼都照實記」。
  把兩者合而為一很省事，而且省完之後**看起來更嚴謹**（每一點都驗過！）——
  這是最危險的那種簡化。

---

## 2026-08-09（稽核 4）測試套件最大的盲區：每一個測試的 `ts` 都是 1.0

- **現象**：W5 D7 剛做完 mutation testing，15 個植入的錯誤全被抓到，
  自認測試套件夠硬。稽核時隨手多植了五個與**取樣週期 `ts`** 有關的錯 ——
  **四個活了下來，整套測試依然全綠。**

  | 植入的錯 | 結果 |
  |---|---|
  | 積分不乘 ts（我的 step） | ❌ 活下來 |
  | 積分不乘 ts（上游相容路徑） | ❌ 活下來 |
  | slew 不乘 ts | ❌ 活下來 |
  | 微分不除 ts | ❌ 活下來 |
  | 上游相容路徑的 D 項歸零 | ✅ 被抓到 |

- **根因**：**每一個測試的 `ts` 都是 `1.0`。乘 1 跟不乘看起來一模一樣。**
  parity 測試掃了 72 組參數組合、逐步吻合到 `1e-12`，聽起來很厚 ——
  但那 72 組全部在 `ts = 1.0` 這一個切面上。
- **而且這不是理論問題**：`config/swampd/config.baseline.json` 裡
  **風扇 PID 的 `samplePeriod` 就是 `0.1`**。
  也就是說，**我驗過的那個切面，正好是我實際上不會用到的那一個。**
- **怎麼修的**：parity 掃 `ts ∈ {1.0, 0.1}`（組合 72 → 144），
  前提斷言（序列真的會飽和）也跟著掃；`test_pi.cpp` 補三條手算期望值的
  `ts != 1` 測試；`mutation_check.sh` 加六條。
- **★ 補完之後又發現我補的測試自己只驗了一半**：只測 `slewPos`、沒測 `slewNeg`，
  於是「slewNeg 忘了乘 ts」**仍然活著**。
  **一個只驗一半的測試，看起來跟驗完整的一樣綠。**
- **教訓三條**：
  1. **「掃了 N 組參數」要問「掃的是哪 N 個維度」。** 沒被掃到的維度上，
     測試的解析度是零。72 組聽起來像涵蓋率，實際上是同一個切面切 72 次。
  2. **預設值是最容易被漏掉的參數。** `ts = 1.0` 是我在每個 fixture 裡
     手打的，打到後來就不覺得它是一個變數了。
  3. **mutation testing 不只驗程式碼，也驗我剛補的測試。**
     這一次它連續抓到我兩個洞：原本的 ts 盲區，以及我補洞時只補一半。

---

## 2026-08-09（稽核 5）Python 那一側零測試，而它產出 README 上每一個數字

- **現象**：

  | | C++ 側 | Python 側 |
  |---|---|---|
  | 測試 case | 26 | **0** |
  | mutation 驗證 | 15/15 被抓 | **無** |
  | 把關工具 | gtest + mutation_check | `ruff`（**只查風格**） |

  而 `bench/metrics.py` 是 `docs/measurement.md` §2 自己宣告的
  「**每一個應變因的唯一定義來源**」，W7 的招牌宣稱 `recover_s_ratio`
  就是它算的。
- **為什麼會變成這樣（誠實面對）**：因為 C++ 那一側有 meson + gtest，
  「加一個測試」的成本接近零；Python 這一側沒有跑測試的地方，
  於是「等有空再說」。**基礎設施的缺口會偽裝成紀律問題。**
- **怎麼修的**：pytest 接進 `meson test`（**不另外做一套跑法** ——
  兩套 test runner 的結果是大家只記得跑其中一套），
  加 7 個 Python mutation。
- **★ 寫測試順手抓到一個真的隱患**：`fan_power_rel` 的「最後 120 秒」
  原本是**用列數**框的，而取樣週期是從**前兩列**推出來的：

  ```python
  dt = float(df["t_s"].iloc[1] - df["t_s"].iloc[0])
  n = max(1, int(tail_s / dt))
  return float(df["fan_power_rel"].tail(n).mean())
  ```

  軌跡只要不是等間隔，視窗長度就錯，**而且不會有任何錯誤訊息**；
  只有一列的軌跡則會丟 `IndexError`，訊息看不出原因。
  改成**用時間框**兩個都消失了 —— 而且那本來就是這個指標的定義
  （「最後 120 秒」講的是時間，不是列數）。
  **L2 從 BMC 收資料時取樣間隔本來就會抖**，這個陷阱留著就是留給 W9。
- **★ 最值錢的一條 mutation**：「把 QEMU setter 的 `−128` 拿掉」，
  抓到它的是 **exp04 那批實測 CSV**。
  那條 mutation 同時證明了**那些 CSV 是有在承重的證據，不是擺著好看的附件** ——
  用我自己手寫的期望值去驗預測式，只能證明我前後一致；
  用機器上量到的資料去驗，才證明我對那條路徑的理解是對的。
- **教訓**：**「唯一定義來源」這個說法會製造風險。** 它讓那份程式碼變成
  單點故障，卻不會自動讓它變得更可靠。宣告某個東西是唯一來源的那一刻，
  就是它最需要測試的時候。

---

## 2026-08-09（稽核 6）★ 閉環測試抓到的第一件事，是我對「符號錯」的理解是錯的

- **背景**：`controller/` 一直只被證明了一件事 ——「它的算術跟上游 `ec::pid()`
  一樣」。**那不等於「它是一個能收斂的控制器」**：兩個實作可以逐位元一致地
  一起錯。`grep ThermalPlant test/` 在此之前完全不命中 controller，
  也就是說這個專案有一個 plant、有一個 controller，卻從來沒把它們接起來測過。
- **我寫的第一個斷言**：「正的係數 = 越熱輸出越低 = **風扇停掉** = 溫度飆高」。
  這是我從 exp02（在真的 BMC 上量的兩點符號檢查）帶過來的直覺。
- **實測**：測試紅了。**風扇衝到 100 % 並鎖死，溫度停在 43 °C ——
  比目標低 22 度。**
- **根因**：把誤差的符號弄反，等於把整條迴路從**負回饋**變成**正回饋**。
  正回饋會往**起始誤差的那一邊**鎖死，所以落到哪一個極限**取決於初始條件**：
  - 起點比 setpoint 冷（plant 從 `tAmb` = 25 °C 開機）→ error > 0
    → 輸出衝上限 → 更冷 → **鎖在 100 %**
  - 起點比 setpoint 熱 → error < 0 → 輸出撞下限 → 更熱 → **鎖在 0 %**

  兩個都是穩定的鎖死狀態。exp02 在 BMC 上量的是**兩個溫度點**，
  所以它同時看到了兩邊；我在腦中把它簡化成了一句話，簡化的時候丟掉了初始條件。
- **為什麼這個版本的症狀更難發現**：「風扇 100 %、溫度 43 °C」在監控畫面上
  **看起來完全健康** —— 沒有過溫告警、沒有 failsafe，只是永遠全速在燒電。
  而「風扇停掉、溫度 77 °C」至少會有人來看。
- **怎麼處理**：測試改成把**兩個分支都測出來**，並加一個「同樣的 |係數|、
  符號正確就收斂」的對照組 —— 沒有對照組的話，上面兩個失敗也可能是
  「這個 plant 根本控不動」造成的。
- **教訓**：**閉環測試的價值不是多抓幾個 mutation，是它會反駁我的敘事。**
  這一條在 `mutation_check.sh` 裡不是任何一個 mutation 的唯一捕手 ——
  單元測試都抓得到那些單行錯誤。它抓到的是**我講給面試官聽的那段話裡的錯**，
  而那種錯沒有任何單行 mutation 表達得出來。

---

## 2026-08-09（稽核 7）我的防護設定咬到我自己的自動化，而且還印了一行假的成功訊息

- **現象**：把 `sign_check.sh` 的重複次數從 1 提到 5（協定要求 ≥ 5）之後，
  第 2 輪就死掉：

  ```
  Job for phosphor-pid-control.service failed because start of the service
  was attempted too often.
  ```

- **根因**：**是這個專案自己加的設定。** W2 為了不讓測試床被重啟風暴拖垮，
  在 drop-in 裡加回了 `StartLimitBurst=3`（見 2026-08-05 那則）。
  我的迴圈每一輪都 `systemctl restart` 一次，第 4 次就撞上限。
- **兩層修法**：
  1. **重啟本來就不必放在迴圈裡。** 這組參數 `ki = kd = slew = 0`，
     輸出是 `clamp(kp × error)`，**沒有任何內部狀態** ——
     重複的是「注入 → 等 → 讀」這個量測序列，不是 daemon 的啟動。
  2. 還原時加 `systemctl reset-failed`，否則跑到那裡時 swampd 很可能
     已經在 start-limit-hit 狀態，`restart` 會被直接拒絕。
- **★ 更嚴重的是第二件事**：我的還原函式原本長這樣 ——

  ```bash
  "${S[@]}" 'systemctl restart phosphor-pid-control' || true
  echo "==> 已還原成 baseline"
  ```

  `|| true` 吃掉了失敗，然後**無條件印出「已還原成 baseline」**。
  實測那一次 swampd 根本沒起來，而畫面上寫著還原成功。
  **一個假的成功訊息比沒有訊息更糟，因為它會讓人停止檢查。**
  改成還原後 `systemctl is-active` 驗證，失敗就印 status 並回非零離開碼。
- **教訓兩條**：
  1. **防護性的設定會咬到自動化，而且那不代表設定寫錯。**
     `StartLimitBurst=3` 在測試床上是對的（真實硬體上「永不放棄」才是對的）。
     要改的是「別把重啟塞進迴圈」，不是把防護拿掉。
  2. **`|| true` 是在說「我不在乎這一步的結果」。**
     清暫存檔可以不在乎，**還原機器狀態不行**。
     每寫一個 `|| true` 都要問一次：如果它真的失敗了，我還想印那句話嗎？

---

## 2026-08-09（稽核 8）`Tested:` 從 W4 起全部消失 —— 以及為什麼我不回頭補

- **現象**：上游 `CONTRIBUTING.md` 明文要求 commit message 要有 `Tested:`
  欄位，`docs/upstream.md` 自己也抄了這一條並標「**必填**」。
  實測 67 個 commit 只有 21 個有，**最後一個是 W3 的 `f299554`；
  W4 的 12 個、W5 的 12 個，一個都沒有。**
- **為什麼會斷掉（誠實面對）**：W1~W3 的 commit 多半是「設定/腳本會不會動」，
  `Tested:` 很好寫。W4 之後改的是**測試與圖**，我下意識覺得
  「這個 commit 本身就是測試，還要寫 Tested 幹嘛」——
  **那個念頭是錯的**：`Tested:` 記的不是「有沒有測試」，
  是「**我實際上跑了什麼、看到什麼**」。
  「跑了 `meson test`，5 個測試 26 個 case 全綠」與
  「我加了一個測試」是兩個不同的宣稱。
- **要不要 rebase 回頭補**：**不補。** 三個理由：
  1. 那段歷史**已經 push 出去了**，改寫會讓 GitHub 上已有的紀錄對不起來。
  2. commit 歷史在這個專案的證據階梯裡是 **T3 證據**，
     而「失敗與修正留在歷史裡」比乾淨的歷史更有說服力。
     一份沒有斷過的紀律紀錄，看起來像是事後整理的。
  3. 改寫會毀掉時間戳，而時間戳正是那份證據的一部分。
- **改成怎麼做**：**從這一刻起每個 commit 都寫**，並且把這一則留在 `LOG.md`。
  面試被問到 commit 紀律時，正確答案不是「我一直都有做」，是
  「我做了 21 個之後斷掉 24 個，稽核時發現，決定不改寫歷史而是從此補上 ——
  這一則就是紀錄」。
- **教訓**：**紀律斷掉的時候通常沒有人會提醒你，因為斷掉不會讓任何東西變紅。**
  這一類的事只有靠**定期回頭稽核自己**才會發現 ——
  而稽核要能發現，前提是規則寫在文件裡（`docs/upstream.md` 那個「必填」）。
  **寫下來的規則不會自動被遵守，但沒寫下來的規則連檢查都無從檢查起。**

---

## 2026-08-09（稽核 9）修復之後的狀態

| | 稽核前 | 修復後 |
|---|---|---|
| gtest case | 26 | **31**（多了 closed_loop 4 + pi 的 ts/Tt 4，扣掉重算） |
| pytest case | **0** | **24** |
| mutation | 15 | **31**（含 7 個 Python） |
| 有 meta 檔的實驗 | 1 / 3 | **4 / 4** |
| 七欄登記 | exp01 | **exp01 ~ exp04** |
| 圖的 caption 有 repo commit | Fig 1 | **Fig 1 + Fig 6**（共用同一份實作，並有測試守著） |
| `Tested:` | 21 / 67 | 從此每一個 |

**還沒做的**：基本功那一軌（W2~W5 共 17 項）—— 那是我自己的時間，
沒有人能代做，而且它仍然是全案最大的風險：
第一關的 C 語言測驗擋掉的人，根本沒有機會講這個專案。
