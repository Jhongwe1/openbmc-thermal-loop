# LOG

每一則都要有「**先驗哪個、為什麼**」。格式：現象 → 假設 → 驗證順序與理由 → 根因 → 教訓。

> **這是實驗日誌,不是交付文件。** 每一則逐字保留寫下當天的認知與措辭,
> 包含後來被自己推翻的判斷、當時的用詞、以及當時還沒想清楚的地方。
> **舊則一律不回頭修飾** —— 被推翻的結論會由後面日期的新則更正並互相連結,
> 而不是把舊則改掉。要看「現在成立的結論」請讀 `README.md` 與 `docs/`;
> 這一份的用途是「這些結論是怎麼一步步被逼出來的」。

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

> ⚠️ **待辦:以上三則的措辭是別人幫忙整理的,要用自己的話重寫一次。**
> 這份日誌記的是「當時怎麼想」,那不能是別人的句子。
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
| gtest case | 26 | **32**（closed_loop 4、pi 的 ts/Tt 4、identify 的非等間隔 1） |
| pytest case | **0** | **32** |
| mutation | 15 | **33**（含 8 個 Python） |
| 有 meta 檔的實驗 | 1 / 3 | **4 / 4** |
| 七欄登記 | exp01 | **exp01 ~ exp04** |
| 圖的 caption 有 repo commit | Fig 1 | **Fig 1 + Fig 6**（共用同一份實作，並有測試守著） |
| `Tested:` | 21 / 67 | 從此每一個 |

---

## 2026-08-09（稽核 10）★ 同一個缺陷,在三個地方

- **現象**：修 `bench/metrics.py` 的時候發現「最後 120 秒」是用**列數**框的，
  取樣週期從**前兩列**推。修完之後順手去看 `plant/identify.cpp` ——
  **一模一樣的寫法，而且有兩處**：

  | 位置 | 原本怎麼寫 | 非等間隔時會怎樣 |
  |---|---|---|
  | `bench/metrics.py` `fan_power_rel` | `n = int(tail_s / dt)`，`dt` 從前兩列推 | 平均到錯誤的時間長度 |
  | `plant/identify.cpp` `baselineMean` | `n = baselineS / dt`，同上 | **基準值 y0 錯 → K、t₁、t₂ 全錯** |
  | `plant/identify.cpp` `tailMean` | 最後 `y.size() / 10` **列** | 穩態值 y∞ 錯 → K 錯 |

- **為什麼三個地方都一樣**：因為它們是**同一個念頭**寫出來的 ——
  「我知道取樣間隔是 0.1 秒，所以 N 秒就是 10N 列」。
  那個念頭在寫的當下是對的（`bench/sim` 產生的資料就是等間隔），
  **錯的是把一個當下成立的前提編進了介面**。
- **什麼時候會咬到**：**W9 的 L1 vs L2 對照**。
  那時候要把**從 BMC 收回來的軌跡**餵進同一批函式，
  而那一側的取樣間隔本來就會抖（見稽核 2 的可見延遲量測）。
  症狀會是「L2 的 K 跟 L1 對不上」，然後我會去懷疑熱模型 —— 又是改錯地方。
- **怎麼修的**：三處全部改成**用時間框**。而且這不只是修 bug，
  **那本來就是這些量的定義**：「最後 120 秒」講的是時間，不是列數。
- **★ 怎麼證明改動沒有動到已經量到的數字**：等間隔資料上兩種框法逐點相同，
  所以重跑 exp01 應該逐 byte 一樣 —— 實測確認：
  `exp01_fit.txt` 逐字相同、五份 CSV 全部 `cmp` 通過。
  **重構要能證明自己沒有改變結果，不能只是「應該不會吧」。**
- **教訓兩條**：
  1. **找到一個 bug 之後，要去找它的兄弟。** 同一個念頭寫出來的程式碼會犯同一個錯，
     而它們通常不在同一個檔案裡 —— 所以只修眼前那一個，等於留兩個。
  2. **「等間隔」這種前提要嘛寫進斷言，要嘛不要依賴它。**
     最糟的是**默默依賴**：程式在滿足前提時完全正常，前提消失時也完全正常，
     只是答案錯了。

**還沒做的**：基本功那一軌（W2~W5 共 17 項）—— 那是我自己的時間，
沒有人能代做，而且它仍然是全案最大的風險：
第一關的 C 語言測驗擋掉的人，根本沒有機會講這個專案。

---

## 2026-08-09（稽核 11）★★ 我到最後才做那個「別人會怎麼看到它」的檢查

- **現象**：修完全部之後，我做了一件從頭到尾都沒做過的事 ——
  **真的從 GitHub clone 一份下來,照 README 的指令跑一次。**
  結果大部分都好：檔案沒被 `.gitignore` 誤殺、執行位元對、
  `meson subprojects download` 抓得到上游、六個測試全綠、
  `exp04 --check` 離線通過、`exp01` 的擬合逐字重現。

  **只有一項不對：重畫出來的 Fig 1 與 repo 裡那張逐 byte 不同。**

- **為什麼這一項嚴重**：`bench/plot.py` 的 docstring 寫著
  「任何人 clone 下來執行同一行指令，**得到的是同一張圖**」。
  那是這個專案「可重現」這個賣點的具體承諾，而**它是假的**。

- **假設**：(1) matplotlib 本身不決定性　(2) PNG 裡有時間戳
  (3) caption 內容不一樣

- **先驗哪個、為什麼**：先驗 (1)，因為**它一句指令就驗得完**
  —— 同一份輸入連畫兩次然後 `cmp`。而且如果 (1) 成立，
  後面兩個都不必查了：不決定性的話這個承諾根本沒救。

- **結果**：
  - (1) ❌ 連畫兩次**逐 byte 相同** → matplotlib 是決定性的
  - (2) ❌ 掃 PNG 的 chunk，只有一個 `Software` 標籤，**沒有時間戳**
  - (3) ✅ **唯一的變數是 caption 裡那串 commit hash**

- **根因**：caption 記的是**產圖當下的 HEAD**。
  HEAD 每個 commit 都在動，所以同一份資料在不同時間畫出來就是不同的檔案。
  而且更糟的是 **HEAD 常常與那張圖無關** ——
  修一個文件的 typo 也會讓一張它從來沒碰過的圖「改版」。

- **怎麼修的**：把 caption 從「HEAD」改成
  「**這張圖的資料**最後一次變動的 commit」（未 commit 就標 `-dirty`）。

  | | 記 HEAD | 記資料的 commit |
  |---|---|---|
  | 資料沒動、隔 10 個 commit 再畫 | ❌ 不同的檔案 | ✅ 逐 byte 相同 |
  | hash 指向什麼 | 一個可能無關的 commit | 產生這張圖的那一版資料 |

  **產圖程式碼刻意不算進那個 hash** —— 會有自我參照問題：
  「改 `plot.py` 的那個 commit」在圖被畫出來的當下還不存在。
  程式碼那一側改由測試守：`test_figures.py` **重畫一次並逐 byte 比對**，
  所以「改了產圖程式卻忘了重畫」會讓測試變紅。

- **★ 順手做對的一件事**：那個「逐 byte 相同」的斷言很強，
  強斷言的前提要自己有測試 —— 所以 `test_rendering_is_deterministic` 存在。
  **沒有它的話，主測試哪天紅了，我分不出是「圖過期了」還是
  「matplotlib 換版本之後不決定性了」。**

- **教訓三條**：
  1. **★ 最重要的一條：「別人 clone 下來會看到什麼」是一個獨立的檢查，
     而我把它留到最後。** 我在自己的工作目錄裡驗了幾十次，
     每一次都帶著我本機的狀態（venv 開著、subproject 抓好了、圖是我剛畫的）。
     **在自己的機器上跑得過，跟「交付得出去」是兩件事。**
     這個檢查應該在 W1 就寫成腳本，而不是在 W5 之後才想到。
  2. **承諾要寫成可執行的斷言。** 「別人跑一次得到同一張圖」寫在 docstring 裡
     十幾天，沒有任何東西在驗它。現在它是一個測試。
  3. **一句話裡的量詞要精確。** 「同一張圖」我心裡想的是「看起來一樣」，
     寫出來卻是一個可以用 `cmp` 檢驗的強宣稱。
     既然寫了強的，就要嘛做到、要嘛改寫成弱的 —— **不能兩邊都不做**。

## 2026-08-11(W6 D1)我自己寫的建議值也錯了:把「區間寬度」當成「絕對值」

**現象:** 稽核(2026-08-09)時我在 `config/swampd/README.md` 寫下
「`integralLimit` 合理的起點是涵蓋 `outLim` 的**寬度**(3000~15000 → 例如 ±12000)」。
今天要照著設,重讀一次,發現那句話是錯的。

**推導:** 穩態時 `error → 0`,所以 P 項 → 0;`feedFwdOffsetCoeff` 也是 0,於是

```
output ≈ integralTerm
```

**「輸出最高能到多少」就等於「積分最高能累到多少」。**
要讓 die0 PID 真的命令得到 `outLim_max = 15000 RPM`,積分本身就必須能到 15000。
`12000 = 15000 − 3000` 是**區間寬度**,不是絕對值。

**根因:** 寫那句話的時候,我腦子裡想的是「積分要能涵蓋輸出的**變化範圍**」。
那個念頭對於「輸出從哪裡變到哪裡」是對的,但積分項不是變化量 ——
在 P 項歸零之後,**它就是輸出本身**。

**★ 這個錯誤有一個很陰的性質:它在 L1 看不見。**
`bench/sim` 的 `outMin = 0`,所以「寬度」與「絕對值」是同一個數字(100)。
只有在 `outMin = 3000` 的 swampd 那一側才會現形,而症狀是
**「風扇最高只轉到 12000 RPM」,看起來像控制律收斂在那裡**,不像一個箝位。

**教訓:**
- ★ **同一個概念錯誤,在一個環境看不出來,在另一個環境會咬人。**
  兩側的預設值不同(L1 `±1e9`、L2 `[0,0]`)本來就該讓我警覺:
  **一個參數在兩個地方有兩種預設,通常代表我沒想清楚它到底是什麼。**
- ★ 這是**同一個念頭犯的第三次錯**(前兩次見 2026-08-09 稽核 10):
  量綱對了,但把**相對量**當成**絕對量**。
- ★ 處理方式不是改註解,是**寫成兩條測試**
  (`test/python/test_swampd_config.py` 的 `..._is_not_a_zero_width_clamp`
  與 `..._covers_the_absolute_output_range`)。
  註解會被讀過就忘,測試不會。

---

## 2026-08-11(W6 D3)λ 越大峰值偏差越大 —— 計畫的驗收標準寫的是另一個實驗

**現象:** 三組 λ 的閉環掃描跑完,`overshoot_c` 是 **9.94 / 12.75 / 17.00 °C**
(λ = 0.5τ / 1.0τ / 2.0τ),**λ 越大越差**。
計畫 §4 的眼睛驗收寫的是「λ 越大 → `overshoot_c` 越小」,
止損表則寫「趨勢跟預期相反 → 先檢查係數符號,再檢查 λ 的換算」。

**假設:**
1. 係數符號錯(計畫指定先驗的那個)
2. λ → Kc 的換算寫反了
3. **計畫的驗收標準本身錯了**

**先驗哪個、為什麼:★ 先驗 (3),不是計畫叫我先驗的 (1)。**

- **(1) 的症狀不對。** 符號錯是正回饋,W5 實測過那個症狀:
  **鎖在起始誤差的那一邊**(風扇衝 100%、溫度停在 43 °C,而且穩得很)。
  我現在看到的是三組全部乾淨收斂到 65 °C。**症狀不符,先放一邊。**
- **(2) 會連帶動到別的指標。** 換算反了的話「λ 大」會對應「Kc 大」,
  那 `settle_s` 也該反過來 —— 但實測是 130 / 172 / 250 s,
  **λ 越大越慢,與「增益越低」完全一致**。
- 也就是說:**六個指標裡有五個的方向都指向「λ 大 = 增益低 = 慢而平順」,
  只有 `overshoot_c` 一個相反。** 一個系統性的錯誤不會只錯一個指標。

**根因:** 計畫把 **setpoint 追蹤**的直覺套到了**擾動抑制**上。這是兩件相反的事:

| | setpoint 階躍 | 負載擾動(本實驗) |
|---|---|---|
| 誰在動 | 目標值跳 | 目標值不動,擾動把溫度推高 |
| 高增益的效果 | 追得猛 → **衝過頭 → 超調大** | 壓得快 → **峰值偏差小** |

我做的是後者(功耗 150 → 300 W,setpoint 一直是 65 °C)。

**⚠️ 順帶:那個指標的名字也誤導。** `overshoot_c` 在這個場景量的是
**擾動造成的峰值偏差**,不是傳統意義的超調。函式名沒改(定義「超過 setpoint 的
最大值」本身沒錯,而且 W7 是同一個場景),但圖上與文件一律寫 "peak deviation"。

**教訓:**
- ★★ **「趨勢與預期相反」時,先問「這個預期是從哪個實驗來的」,
  再問「我的系統是不是錯了」。**
  一份寫得很細的計畫,最危險的不是它漏寫什麼,
  是它**寫對了一句話,但那句話屬於另一個場景**。
- ★ **當多數指標方向一致、只有一個相反,先懷疑那一個的期望值。**
  系統性的錯誤(符號、換算、量綱)會讓**一整組**指標一起歪,不會只歪一個。
- ⚠️ 如果照止損表走,我會花半天去查一個完全正確的符號。
  **止損表本身也需要止損條件。**

---

## 2026-08-11(W6 D5)`pidcore.*` 的時間戳量到的是 log 的節流,不是迴路週期

**現象:** 計畫叫我用 `pidcore.die0` 相鄰時間戳的差來量熱迴路週期,
預期 ≈ 1000 ms(`updateThermalsTimeMS`)。
實測 **60013 ~ 67569 ms**,36 筆裡沒有一筆接近 1000 ms。

**假設:**
1. 這台 QEMU 慢了 60 倍
2. 熱迴路真的是 60 秒一輪(設定被什麼東西覆寫了)
3. **那份 log 不是每個週期都寫一筆**

**先驗哪個、為什麼:★ 先驗 (3) —— 排除成本最低,而且它有前科。**

- **(1) 一眼就排除。** 同一個 daemon 的 `zone_0.log` 相鄰間隔中位數是
  **100 ms**。**同一台機器上的兩份 log,不可能只有一份被拖慢 60 倍。**
- **(3) 有前科:** 2026-08-05 已經踩過一次
  「`zone_0.log` 看起來停住了 —— 其實是緩衝」。
  **同一類問題的兄弟:log 的寫入時機不是我以為的那樣。**

**驗證(讀上游原始碼,`pid/ec/logging.cpp`):**

```cpp
static constexpr int logThrottle = 60 * 1000;      // ← 60 秒

void LogContext(...)
{
    bool shouldLog = false;
    if (pidLog.lastLog == zero)                 shouldLog = true;  // 第一次
    else if (since.count() >= logThrottle)      shouldLog = true;  // 節流到期
    if (pidLog.lastContext != coreContext)      shouldLog = true;  // 內容變了
    if (!shouldLog) return;
    ...
}
```

**根因:** `pidcore.*` 是**「內容變了 **或** 距上次超過 60 秒」**才寫一筆的 log,
**不是等間隔取樣**。當時我的迴路是靜態的(die0 讀值恆為 0、輸出恆被箝在 3000),
每一筆的內容完全相同 → 只剩節流在寫 → 量到的就是 `logThrottle`。

**對照組:** `zone_0.log` 由 `DbusPidZone::writeLog()` 直接寫,**沒有任何節流**,
所以它的行間隔就是內圈的真實週期(中位數 **100 ms**,p05~p95 = 96~104 ms,
n = 18366,與 `cycleIntervalTimeMS = 100` 一致)。
**同一個 daemon 的兩份 log,兩種完全不同的寫入策略。**

⚠️ 順帶一個統計上的提醒:同一批資料的**平均**是 **122.8 ms**、最大值 7832 ms
(QEMU 的排程抖動)。**只報平均會得到一個錯 23% 的數字。** 報中位數與分位數。

**教訓:**
- ★★ **量一個系統的週期之前,先確認「記錄這件事的東西」本身是不是等間隔的。**
  量測儀器有自己的取樣邏輯,而它不會告訴你。
- ★ 這是 W5「**我量不到 ≠ 它不存在**」的下一層:
  **我量到了一個數字,但那個數字量的是另一件事。**
  前者會讓你少一個結論,後者會讓你多一個錯的結論 —— 後者危險得多。
- ★★ **而且它有後果:W7 的 Fig 3 第三面板(積分軌跡)吃的就是這份 log。**
  不知道這件事就畫,會得到一條看起來等間隔、其實是變化觸發的曲線;
  而「值不再變化」的那一段**正是 anti-windup 生效之後的那一段** ——
  最該看清楚的地方會被壓縮成幾個點。
- ⚠️ 因此 D5 的量測程序要改:**要量熱迴路週期,必須先讓每個週期的內容都不同**
  (注入持續變化的溫度),否則量到的永遠是節流。

---

## 2026-08-11(W6 D5)驗收 `integralLimit` 的修復 —— 順便得到一條完整的證據鏈

**這一則不是 debug,是驗證。** 記下來是因為它把今天所有東西串起來了。

**做法:** 部署 `config.tuned.json`(λ=2τ 的係數 + `integralLimit = [0, 15000]`),
注入固定 85 °C(高於 setpoint 65,誤差為負、積分往正累積),取樣 90 秒。

**驗收 ①:`integralTerm` 真的會動了。**

```
t=...117744  input=84.938  error=-19.938  P=4391.92  I=  99.8798  out= 4491.8
t=...118856  input=84.938  error=-19.938  P=4391.92  I= 199.76    out= 4591.67
...
t=...235893  input=84.938  error=-19.938  P=4391.92  I=9588.46    out=13980.4
```

96 筆、單調上升。修之前它恆為 0,而且**不會有任何錯誤訊息**。

**驗收 ②:`zone_0.log` 的 `requester` 欄從 `Minimum` 變成 `die0`。**
zone 的輸出不再是被 `minThermalOutput = 3000` 撐著,是**熱 PID 在駕駛**。
這一欄比任何數字都直接:它說的是「誰在做決定」。

**★★ 驗收 ③(意外收穫):手算與實測對得上小數點後三位。**

| 項 | 手算 | `pidcore.die0` 實測 |
|---|---|---|
| P 項 | `−220.279 × (−19.938)` = **4391.92** | **4391.92** |
| 每步積分增量 | `−5.00952 × (−19.938) × 1.0` = **99.880** | **99.8798** |

而那兩個係數的來歷是一條完整可查的鏈:

```
開環階躍 CSV (exp01, W4)
  → exp01_fit.txt:  K = −0.314708,  tau = 43.972,  theta = 7.2013
  → bench/tune.py:  Kc = tau / (|K|(lambda+theta)),  Ki = Kc / Ti
  → × 150 RPM/%PWM(串級外圈的量綱)
  → 取負(temp 型別)
  → config.tuned.json → BMC 上的 pidcoeffs.die0
```

**教訓:**
- ★ **一條證據鏈的價值不在於每一節都對,而在於它「可以被外人一節一節走一遍」。**
  面試官問「這個 −220 是哪來的」時,我可以從一張圖走到 BMC 上的一行 log。
  這件事 AI 生不出來,因為中間每一節都指得到一份我機器上真的存在的檔案。
- ★ 「積分每秒增加 99.88」這種**可以手算驗證的中間量**,比「圖看起來對」強得多。
  下次設計實驗時要刻意留一個這樣的檢查點。
- ⚠️ 順帶記錄:這一段是**開環**(注入的溫度不會因為風扇轉而下降),
  所以積分一路累積 —— **那正是 windup**。積分上限 15000 還沒碰到(最高 9588)。
  **W7 要量的就是「頂上去之後,溫度降下來時它要花多久放完」。**
  也就是說:今天無意間跑了一次 Fig 3 的前半段。

## 2026-08-11(W7)L2 一閉環就露餡:內圈全 0 的設定,PWM 永遠釘在 30%

**現象** 把真 swampd 接上 plant 之前先盤點設定,發現 W6 那份
`config.tuned.json` 的內圈 fan0 係數全 0 —— runbook §4.8 自己就記過後果:
「PWM 被箝在 30% 不動」。也就是說**計畫的 L2 從第一天起就閉不了環**:
外圈算出再漂亮的 RPM 目標,沒有人把它變成 PWM,plant 看到的永遠是 30%。

**假設** ① fan PID 必須整定回授係數(違反 W6「沒有量測就不整定」的決定);
② 上游有某條不經回授係數的傳遞路徑;③ zone 層自己會把 RPM setpoint 翻成 PWM。

**先驗哪個、為什麼** ②。讀碼成本最低(一個函式),而且 W6 的紀律就是
「不知道欄位怎麼填,先看上游的計算圖」。

**根因** `pid/ec/pid.cpp:101`:`feedFwdTerm = (setpoint + feedFwdOffset) × feedFwdGain`,
而 fan PID 的 setpoint 就是外圈的 RPM 輸出(`fancontroller.cpp` 的
`setptProc()` → `getMaxSetPointRequest()`)。所以 `feedFwdGainCoeff = 1/150`
(= 100% ÷ 15000 RPM,與 `bench/tune.py` 的 `RPM_PER_PCT` 是同一個常數)
就讓 PWM 純前饋地追隨外圈 —— 迴路閉起來,而回授係數維持 0。
A/B 兩個 arm 同改,不碰自變因;`test_swampd_config.py` 三份設定一起守。

**教訓(方法論)** 「不整定」與「不傳遞」是兩件事。W6 的原則守的是前者
(沒有量測就不給回授增益),但把後者也一起關掉了。**檢查一條控制鏈,
要沿著訊號問「這一步誰把它變成下一個量綱」**,而不是只看每個方塊的
參數有沒有值 —— 全 0 的方塊在方塊圖上看起來也是一個方塊。

## 2026-08-11(W7)私有匯流排上 swampd 找不到感測器 —— mapper 是計畫沒寫的隱形相依

**現象** 計畫的 L2 步驟是「起私有 dbus-daemon → 跑 swampd」。動手前讀
`dbus/dbuspassive.cpp`,第 87 行:建 sensor 的第一步是 `helper->getService()`
—— 去問 **ObjectMapper** 這個物件在哪個服務上。私有匯流排上沒有 mapper,
照計畫走,swampd 會在建 sensor 時就倒地,而錯誤訊息只會說 sensor missing。

**假設** ① die0 的 readPath 改走 /tmp 檔(繞開 D-Bus,但也繞開了
「與 BMC 同一條資料路徑」的意義);② 裝真的 phosphor-objmgr(重,又多
一個要管的服務);③ bridge 順便冒充一個只會 `GetObject` 的迷你 mapper。

**先驗哪個、為什麼** ③,因為上游自己的單元測試就是這樣做的
(`test/dbushelper_mock.hpp` mock 掉 getService)—— 有上游背書的測試
手法,三十行程式。**先查上游怎麼測自己,再決定自己怎麼測它。**

**根因(規格全部讀碼取得,不猜)** `GetObject(s path, as interfaces) → a{sas}`
—— 注意是 `s` 不是 `o`(`dbushelper.cpp` 用 `mapper.append(std::string)`);
`GetAll(Sensor.Value)` 只有 `Value` 必在(`Unit` 給 DegreesC);
Availability 與 threshold 介面缺席都被上游 catch 成無害預設
(`UNC_FAILSAFE` 預設關)。實跑 45 秒煙霧測試一次通,
swampd(**釘在 BMC 映像同版 c5e5955 的未修改二進位**)正常進出 failsafe。

**教訓(方法論)** 隱形相依要用**原始碼**找,不是等錯誤訊息猜。
而**上游的 mock 就是它對自己相依的規格書**:它 mock 什麼,
你就知道什麼是可以假的、什麼必須是真的。

## 2026-08-11(W7)A/B 在「不該分家的地方」分家了 —— 反向 windup 的意外現身

**現象** exp07 的預期:飽和期間兩組輸出同頂 100%,溫度曲線應重合。
實測 `t_peak` 差 1.9 °C(92.0 vs 90.1),而且差異在**進飽和之前**就存在。

**假設** ① 單變因破功(某個參數跟著 integralLimit 一起變了);
② 機制真實:open arm 的**下界** −1e6 在暖機段就生效;③ seed 沒對齊的假象。

**先驗哪個、為什麼** ①,因為它最致命 —— 單變因破功整個實驗作廢。
但它已被 `check_single_variable` 機器排除(兩層逐欄比對,組間只差
integral_min/max),seed 又是配對共用(排除③)。剩 ② → 直接看積分面板。

**根因** 冷開機段 T < setpoint、誤差為正、ki 為負 → 積分往**負向**累積。
clamp arm 的下界 0 把它擋住;open arm 挖到約 −45 %PWM,要先「爬出坑」
風扇才開始加速 → 暖機超調更高、帶著略不同的狀態進入 400 W 階躍。
`config/swampd/README.md` 在 W6 寫「下界為什麼是 0 不是負值」時
就預言過這個機制 —— 今天它自己走進圖裡,Fig 3 從 t=0 整段畫、
把它標成 LIMIT 而不是裁掉。

**教訓(方法論)** **對照變因會在你沒設計的區段也生效。** A/B 的差異
不會乖乖等到你想觀察的視窗才出現;把「不該分家處的分家」標出來,
比裁掉開頭讓圖乾淨誠實得多 —— 而且這次它是**同一機制的下界版展品**,
免費的第二個證據。

## 2026-08-11(W7)同一顆地雷一天踩四次:755 被洗掉,而管線把失敗遮成綠的

**現象** ① `./tools/mutation_check.sh 2>&1 | tail` 回 exit 0,以為在跑,
其實唯一輸出是 `Permission denied` —— **管線的離開碼是 tail 的**。
② 稍後 `l2_ab.sh` 以 126 掛掉,煙霧測試「什麼都沒發生」,第一輪還誤判
成 dbus-daemon 壞掉。③④ 每 chmod 一次,只要再用 UNC 路徑編輯同一支
`.sh`,755 就又被洗回 644。一天之內同一根稻草壓了四次 ——
而 W6 才剛為這件事寫過 `test_file_modes.py`。

**假設** ① dbus-daemon 起不來;② 腳本本身有 bug;③ 執行位又被洗掉。

**先驗哪個、為什麼** 應該先驗 ③:3 秒可驗(`ls -la`),而且**這個專案
有它的前科檔案**(CLAUDE.md 第一節、2026-08-09 兩次)。有前科的假設
永遠先驗 —— 實際上卻先花了一輪去查 dbus-daemon,學費。

**根因(三層)** ⑴ `\\wsl.localhost` 寫檔把 mode 洗成 644,git index 仍記
100755,`git status` 乾淨 → **看不見**。⑵ `test_file_modes.py` 驗的是
**index**,工作樹的 644 要等下一次 `git add` 才進 index —— 守門員守的門
與這次的破口差一層。⑶ `cmd | tail` 沒有 pipefail,失敗碼被最後一節覆蓋。

**教訓(方法論)** ⑴ **重複發生的坑,對策不能是「記得小心」,要把觸發
條件整個拿掉**:執行一律 `bash 檔案`(對 mode 免疫),chmod + 重新
`git add` 收斂成 commit 前的固定一步。⑵ 背景與管線指令的「成功」要驗
**產物**(log 有沒有長出來),不是離開碼。⑶ 同場加映:**負向驗證跑的
時候,測試集要凍結** —— 今天在 mutation 執行中新增了一條預期寫錯的
測試,紅測試會讓所有 mutation 被「誤抓」成假綠,整輪作廢重跑。
假綠不會自己現形,這正是它比紅可怕的地方。

**後記(同一天,更深一層)** 上面那句「被 kill 就還原」也是沒驗過的話:
bash 對**未攔截的** SIGTERM 直接死,`trap restore EXIT` 根本不會執行。
被 pkill 的那輪把 P4 突變體留在 `bench/metrics.py` 裡,九個測試從此
恆紅,而下一輪 mutation 的**每一個案例**都被那九個紅「誤抓」——
報表上全是 ✅,全是假的。發現的線索有兩條,都不是「測試紅了」:
P3/P4 回報「過期(找不到字串)」(因為原字串已被改走),以及每一列的
「抓到它的測試」都是同一組(真的抓到應該各有各的守門員)。
修法:`trap 'exit 143' INT TERM` 把訊號轉成 exit,EXIT trap 才會接手。
★ **安全網要嘛被測過,要嘛當它不存在** —— 這支腳本的 trap 注釋寫了
「Ctrl-C 也會還原」,寫的當下沒有人按過 Ctrl-C。

## 2026-08-11(W7)L2 重現:12.9×,落在 L1 的 seed 範圍內

一句話結果:**未修改的 swampd(`c5e5955`,與 BMC 映像同版)+ 同一份
plant,單趟 `recover_s` 181.0 / 14.0 s = 12.9×**,落在 L1 五個 seed
配對比值的範圍 [12.83, 13.89] 之內;積分在 clamp 組貼死 15000 RPM
上限、open 組爬到 33308 RPM(222.1 %PWM 等效)。
**「程式碼完全沒動,只改設定兩行」的宣稱,從模擬走進了真 daemon。**

兩個值得單獨記的工程量:

- bridge 的**絕對節拍**(deadline,不是 `sleep(dt)`)在 1500 s 後的
  累積誤差約 **1 ms** —— 相對節拍的誤差是會累積的,量測即時系統前,
  節拍器自己要先站得住。
- pidcore 節流下,**積分峰值仍然可信**:極值必然出現在「值有變」的
  那一筆,而「值有變」必寫。這是把 W6「節流量不了週期」的教訓翻成
  「什麼仍然量得了」的正面清單 —— 一份量測工具的限制清單,
  要同時寫「不能用它做什麼」與「仍能用它做什麼」。

## 2026-08-11(W7)乾淨 clone 又立功:本機永遠綠的六個測試,clone 全倒

**現象** push 完照例從 GitHub 乾淨 clone 一份跑 `meson setup && meson test`:
Ok: 5 / Fail: 1 —— `test_sim_cli` 六個 case 全倒在「`build/sim` 不存在」。
本機同一套指令從來沒紅過。

**假設** ① clone 不完整(缺檔);② 測試對路徑的假設在 clone 裡不成立;
③ **`meson test` 根本沒把 sim 建出來**。

**先驗哪個、為什麼** ③:錯誤訊息就是「執行檔不存在」,先去 clone 的
build/ 裡 `ls` 一眼,3 秒。

**根因** `meson test` 只建**測試宣告過的依賴**,不是整個專案。
`sim` 是 `executable()` 目標但沒有任何 `test()` 宣告依賴它 ——
本機的 build/ 總有跑過 `meson compile` 的殘留,所以永遠是綠的;
乾淨 clone 走「setup → test」的最短路,sim 從來沒被建出來。
修法:pytest 目標加 `depends: sim_exe`。

**教訓(方法論)** 「本機綠」隱含著一堆**沒寫下來的建置順序假設**,
而殘留的 build 目錄會把它們全部藏起來。乾淨 clone 是唯一會把
「你以為宣告過、其實沒有」的依賴逼出來的檢查 —— 它今天第二次
抓到本機永遠抓不到的東西(第一次是 2026-08-09 的 caption HEAD)。

## 2026-08-11(W8)slew 掃描第一版:八組聲學代理**完全相同** —— 死旋鈕

**現象** exp08 照計畫跑(整定 = 部署採用的 λ=2.0τ、方波週期 120 s):
八組 `reversals_per_min` 全部是 1.0 次/分(W6 穩態量到 31.5,差 30 倍);
slew ≥ 1 的五組連 `t_peak_c` 都**逐位相同**。40 份 CSV,一條取捨曲線
都畫不出來。

**假設** ① 程式錯(slew 旗標沒接上);② 指標壞(deadband 把一切
濾掉);③ 實驗設計錯 —— 機制在這個工作點**沒有作用空間**。

**先驗哪個、為什麼** ①,排除成本最低:stderr dump 的單變因檢查已逐欄
比對過八組的 slewNeg/slewPos 確實不同,而且 slew=0.25 的 t_peak 明顯
不同(81.6 vs 77.3)—— 旗標有生效,① 3 秒出局。再驗 ②:手算 tail
視窗裡 PWM 的每步變化 —— 追方波的每步 ≈ 0.33 %,遠大於 deadband
0.05,不是被濾掉,是**全部同號** → 反轉根本沒發生 → ③。

**根因** 兩層。表層:λ=2.0τ 的閉環時間常數 ≈ 88 s > 半週期 60 s,
tail 整段都在追蹤 —— 雜訊步(±0.10 %)被大信號斜率(0.33 %/步)淹沒,
方向從不反轉,指標量到的是**軌跡形狀**不是聲學。
底層:slew 咬得到的對象由「被限訊號的斜率」決定 —— 這個工作點的
兩個特徵斜率(雜訊 0.10 %/步、追蹤 0.33 %/s)都在掃描範圍
(0.25~16)之下,整條掃描落在機制的作用窗外。
**slew 治的是高增益的病;部署整定已經用 λ 把病治掉了。**
處置:掃描基準改 λ=0.5τ(高增益側,雜訊步 0.34 %)、週期改 240 s
(半週期 > 3× 閉環時間常數,每段電平都有「追蹤+穩態」兩種行為)。
改完梯度立刻出現:23 → 1.5 次/分,配對比 3.4×~15.3×。

**教訓(方法論)** 「掃了 7 個值」不自動等於「掃描」—— 7 個值全落在
機制的作用窗外就是 7 個相同的點。把掃描範圍定下去**之前**,先算
被掃系統的特徵斜率/特徵尺度,確認範圍跨在作用窗的兩側。
這是 W7 教訓 #1 的定量版:對照的差異只在機制有機會生效的區段顯形,
而「區段」是可以事先算出來的,不必等 40 份 CSV 告訴你。

## 2026-08-11(W8)同一個旋鈕,負載節奏不同,答案的**符號**相反

**現象** 先導試探裡,slew 收緊對相對風扇功耗的影響:週期 120 s 時
**下降**(0.249 → 0.185,省 26%);週期 240 s 時**上升**
(0.102 → 0.192,費 87%)。同一個 plant、同一組增益、同一個旋鈕。

**假設** ① 指標 bug;② 兩個機制在搶,週期決定誰贏:
削 N³ 尖峰(省)vs 落後拖高平均轉速(費)。

**先驗哪個、為什麼** ②,因為 ① 與「其他指標在兩個週期下都合理」
矛盾 —— 指標壞掉不會只壞一半。看 PWM 軌跡:半週期 60 s(< 3λ)時
基準組**從不穩定**,全程大擺,slew 主要在削 N³ 的尖峰;半週期 120 s
(> 3λ)時基準組大部分時間坐在穩態低功耗,slew 組長時間落後在
高 PWM 高原上 —— 平均整段上移。

**根因** `fan_power_rel` 是 PWM 軌跡的 N³ 泛函,而 slew 同時做兩件事
(削峰、拖平均),兩者對積分的貢獻方向相反,權重由負載的時間結構
決定。沒有「slew 對功耗的影響」這種與負載無關的結論。

**教訓(方法論)** 任何「X 對 Y 的影響」的結論都隱含一個負載時間
結構,而且**符號**都可能跟著翻。這就是為什麼 Fig 5 的 caption 必須把
方波週期寫進去、measurement.md 要明寫「單一週期的掃描不能外推」——
不是謙虛,是這個量真的會變號。

## 2026-08-11(W8)計畫偽碼把 slew=0 畫在數值軸上 —— 0 在這裡是「關」不是「小」

**現象** 計畫的 Fig 5 偽碼直接 `ax.plot(slews, ...)`,slews[0] = 0
(不限制)。照畫的話 0 落在 x 軸最左 —— 但 0 的語意是「無限鬆」,
而它左邊的鄰居 0.25 是**最緊**的一組:曲線在最左端會先跳到基準值,
整條「越左越緊」的讀法直接反掉。

**假設**(設計判斷,無需排錯)

**根因** slew=0 是上游的哨兵值(`slewNeg != 0.0` 才啟用),它不在
「緊 ↔ 鬆」的連續量尺上。畫法改成:x 軸 log₂(0.25~16,越左越緊,
單調成立),slew=0 抽出來畫成每個面板的**水平基準帶**(中位數虛線
+ 5-seed 範圍 —— 基準也有不確定度,不是一條理想線)。

**教訓(方法論)** 把變數編碼到視覺軸之前,先問「這個值在物理上是
什麼」—— 哨兵值(0 = 關、−1 = 不階躍)混進數值軸,圖的單調性就是
假的。同族的前例:sim 的 `--power-at` 用負數表示「不階躍」,它也
從來不該被畫在時間軸上。

## 2026-08-11(W8)mutation E2 活下來 —— 抓到的不是程式的洞,是**測試自己的洞**

**現象** 55 個植入錯誤跑完,54 個被抓;活下來的 E2(exp09 的
「t0 前狀態檢查失效」)**恰好有一個專門為它寫的測試**
(`test_still_in_failsafe_at_t0_is_rejected_loudly`),而那個測試是綠的。

**假設** ① 測試沒被收進這輪執行;② 測試斷言太弱;③ 突變其實沒植入
(字串沒匹配到,被判「過期」)。

**先驗哪個、為什麼** 先排除 ③:mutation 表上 E2 印的是「沒有任何測試
變紅」不是「過期」,植入成功。再驗 ②,成本最低 —— 重讀測試資料
30 秒就夠。

**根因** 測試餵的反例資料 `(failsafe=1, pwm=255)` **同時違反兩個前提**
(還在 failsafe、PWM 已在頂)。E2 把第一個檢查廢掉之後,第二個檢查
照樣 raise SystemExit,而 `pytest.raises(SystemExit)` 分不出是誰
raise 的 —— 兩個守門員互相頂替,廢掉一個看不出來。
修法:反例資料改成**恰好只違反一個前提**(`pwm=120`),
植入 E2 立刻紅、還原立刻綠(單獨重驗過)。

**教訓(方法論)** 「為 X 寫了測試」≠「測試守著 X」。當一個函數有
多個依序檢查的前提,每個前提的反例資料必須**正交**(只違反它自己),
否則守門員互相頂替,少一個都看不出來。這正是 mutation 流程存在理由的
自我示範:測試在、綠著、而它守的門不是你以為的那扇 ——
沒有 E2,這個洞會一路埋到有人真的把前提檢查改壞的那天。

## 2026-08-11(W8)exp09 首戰:8 個單元測試全綠,真資料第一筆就爆

**現象** `detect_events` 的單元測試全綠;拿 run1 的真 zone_0.log 一跑,
「t0 之後 PWM 從未到 255」—— t2 永遠找不到。

**假設** ① failsafePercent 沒生效(swampd 側);② 解析的欄位語意錯;
③ run 本身壞掉。

**先驗哪個、為什麼** ① 的反證最便宜:`run1_failsafe_property.txt` 是
`b true`、log 的 failsafe 欄 0→1、`fan0_pwm` 從 0.3 跳到 1.0 ——
**機制全對**。→ ②:印出真資料的欄位,`fan0_pwm_raw` **全程是 −1**。

**根因** 本 rig 的 writePath 是 write-only 的普通檔案,swampd 讀不回
raw,那一欄恆為 −1;真正的 PWM 在 `fan0_pwm`,**0~1 的比例**
(W7 的 mutation P22 就在守「×100 才是 %」—— 同一個欄位語意,
同一天學第二次)。而我的單元測試全綠,因為**假資料是照我想像的格式
(raw 0~255)造的** —— 合成資料只能測邏輯,測不出「我對格式的想像
本身就是錯的」。修:改用 `fan0_pwm >= 1.0`,並加一個**逐字複製真實
log 行**的測試(`test_real_zone_log_rows_parse_and_detect`)——
test_parse_l2 從第一天就是這樣做的,這次真的照抄。

**教訓(方法論)** 合成資料測邏輯、真樣本測 contract,**兩種都要有**。
只有前者時,測試驗證的是「程式碼與我的想像一致」,而 bug 常常就住在
想像裡。順帶:真樣本還揭露了兩個合成資料想不到的細節 ——
拉滿時印的是整數 `1` 不是 `1.0`、requester 是字串欄。

## 2026-08-11(W8)t1−t0 = 17.3 s(預期 ~5.5):量測環境自己在凍結

**現象** run1 的 failsafe 延遲 17.31 s,比 timeout(5 s)+ 檢查節奏
(≤1 s)多出 ~11 s。這一 run 恰好橫跨 session 中斷的時段。

**假設** ① swampd 的 staleness 檢查有額外延遲;② `_updated` 的語意
與我理解的不同;③ **量測環境(WSL)本身被凍結,wall-clock 時刻失真**。

**先驗哪個、為什麼** ② 讀碼最快:`updateValue()` 對**每個**
PropertiesChanged 都無條件 `_updated = now`(值沒變也更新)—— ② 出局。
再驗 ③:掃 zone log 的相鄰行距(主迴圈 0.1 s 應該等距)——
**每 ~33.5 s 出現一次 1.4~1.55 s 的凍結,共 10 次 ≈ 13 s**,
全程 span 341.4 s(應為 ~330)。宿主在 session 中斷時段對 WSL 的
CPU 節流。t0→t1 區間正好吃到凍結,17.3 s 是污染值。

**根因** wall-clock 量測隱含「時間軸連續」的假設,而 VM/容器環境裡
這個假設**會被宿主打破**。單元層與統計層都抓不到它 ——
它不是程式錯,是**量測儀器(時鐘)壞了**。
修:把環境健康變成 run 有效性檢查 —— `detect_events` 拒收事件窗內
行距 > 0.5 s 的 run(對照:主迴圈節奏 0.1 s,5 倍裕度),run1 作廢重跑。

**教訓(方法論)** 量測腳本要驗的不只資料,還有**量具自己的健康**:
時序量測至少附一條「時間軸連續性」檢查。W6 已經見過弱版
(QEMU 排程抖動污染平均值 → 只能報中位數);這次是強版 ——
中位數也救不了被凍結撐開的單一區間,只能整 run 拒收。
這條檢查現在是程式(mutation 家族的鄰居),不是「記得看一眼」。

## 2026-08-12(W9)開工就中招:runbook 門面說 W8 沒做,其實做完了

**現象** 使用者讀 runbook 開工,門面(§0/§3.2/§4.1)全都說「下一份是
W08」,以為 W8 沒做;實際上 W8 於 08-11 完成、§4.11 詳細段也寫了。

**假設** ① 上次收工忘了跑六項;② 六項有跑,但 runbook 更新只更新了
一部分;③ 檔案衝突/還原事故。

**先驗哪個、為什麼** git log 最便宜:08-11 有完整的收工 commit 與 push
(`bddd3be..5007c82`),LOG/README 都有 W8 → ① ③ 出局,是 ②。

**根因** 同一個「目前進度」狀態寫在 runbook 的**五個位置**(最後更新
日期、§0 表、§3.2、§4.1、§4.x)。一天收三週(W6+W7+W8)的那個晚上,
§4.11 寫了、門面四處全漏 —— 多副本狀態沒有機器檢查,漂移只是時間問題。

**教訓(方法論)** 狀態要嘛單一來源、要嘛有同步檢查清單。修法不是
「下次記得」:在 runbook 檔案第一行加了 HTML 註解列出「收工五個必改
位置」,讓下一個更新的人(就是未來的自己)撞到清單。CLAUDE.md 的
收工六項同日也把「進度有變就更新」寫進第 5 項。

## 2026-08-12(W9)官方 Robot 首輪 11 紅:先分「它的假設」還是「我的調用」

**現象** QEMU_CI 首輪 19 案 8 綠 11 紅。其中 `GET_Redfish_Resources_
With_Login` 對 `/redfish/v1/Chassis/chassis` 拿 404;SoftwareInventory
兩案 `Setup failed: Plug-in setup failed.`。

**假設** ① bmcweb 缺資源(映像裁剪);② 測試假設過時;③ 我的調用
參數不完整。

**先驗哪個、為什麼** ③ 最便宜也最常見:先讀 `lib/resource.robot` 的
變數預設值再說。結果 `CHASSIS_ID` 預設是字面值 `chassis`(bletchley 的
兩個 chassis 都不叫這名),`OPENBMC_PASSWORD` 預設空字串;而幾個 lib
沒設 `REDFISH_SUPPORT_TRANS_STATE:1` 時會走 **legacy phosphor REST 的
`POST /login`** —— 現代 bmcweb 回 400,後面整串 NoneType 雪崩都是它的
屍體。修正調用後第二輪 10 綠 9 紅,`GET_Redfish_Resources` 轉綠,
**剩餘失敗零項是我的調用問題**(5+1 IPMI=映像無 netipmid、2=journal 的
sled 馬達校正、2=suite setup 要 host 電源,見下則)。兩輪報告都留檔
(`docs/robot/`),第一輪是「調用缺口」的證據不是垃圾。

**根因** 官方套件的變數契約是隱性的:模板 `test_openbmc_setup.robot`
內部自帶 `REDFISH_SUPPORT_TRANS_STATE=1` 所以 setup 不踩雷,直接跑
QEMU_CI 就踩。計畫的示範指令(純環境變數)更是完全傳不進 Robot
(`resource.robot` 預設空、Robot 不吃環境變數)—— 已寫進
`run_robot_qemu_ci.sh` 的註解。

**教訓(方法論)** 跑別人的測試套件,紅的第一分類不是「它錯還是
環境錯」,是「**它的假設**還是**我的調用**」—— 而驗「我的調用」永遠
最便宜,先讀它的 `resource`/變數預設,再談根因。第一輪的紅不是失敗,
是把隱性契約顯性化的量測。

## 2026-08-12(W9)清單 20 個 include、只執行 19 個:四年的死引用

**現象** `test_lists/QEMU_CI` 有 20 個生效 `--include`,兩輪都只執行
19 個測試。`Verify_Update_Service_Enabled` 這個 tag 全 repo 找不到。

**假設** ① tag 改名了;② 套件不在我跑的 `redfish/ ipmi/` 路徑下;
③ 清單本來就是錯的。

**先驗哪個、為什麼** ① 用 `git log -S` 一次到位:`5236ec54`
(2022-01-31)把 tag 改成 `Verify_Redfish_Update_Service_Enabled`;
`git blame` 顯示清單那行是 2022-04-28(`e4d77d2a8`)寫入 ——
**寫入當天引用的就是三個月前已改名的 tag**,從未生效,四年沒人發現。

**根因** Robot 的 `--include` 對不存在的 tag 安靜地跑零個測試,
清單型設定沒有引用完整性檢查。而且不能用「改成新 tag」修:單獨跑
改名後的測試,它死在 suite 的 Test Setup(`Redfish Power Off`)——
BMC-only 的 QEMU 沒有 host 電源堆疊,整個 firmware-inventory suite
天生進不了 QEMU_CI。正確修法是**刪行**,證據三件套:改名 commit、
blame、探針 run(`docs/robot/20260812_renamed_tag_probe/`)。
→ 登記為 upstream 候選 3(`docs/upstream.md`),W10 第一發。

**教訓(方法論)** 「安靜地少跑」比「大聲地失敗」危險 —— 對照表:
我自己的 mutation 腳本開頭就有「該有的測試真的在嗎」的檢查(坑 27),
上游清單缺的正是同一件事。發現流程 = 數字對帳(20 vs 19):
**任何兩個應該相等的計數,對一次帳都可能挖出屍體**。

## 2026-08-12(W9)「Plug-in setup failed」:錯誤訊息與根因隔兩層

**現象** SoftwareInventory 兩案在兩輪都是 `Setup failed: Plug-in setup
failed.`,與 `REDFISH_SUPPORT_TRANS_STATE` 無關(第二輪已排除)。

**假設** ① 測試框架的 plug-in 基建在我的 host 上壞了;② 這訊息是
別的失敗的包裝;③ 缺某個變數。

**先驗哪個、為什麼** 先 `grep -rn 'Plug-in setup failed'` 找訊息出處
(`lib/obmc_boot_test.py:517`,boot-test 框架),再讀 suite 檔案的
`Test Setup Execution` —— 兩行:`Redfish.Login` + **`Redfish Power
Off`**。到此根因清楚:每個測試的 setup 要先把「主機」關機,而
QEMU bletchley 是 BMC-only(`obmcutil state` 輸出為空,無 host 電源
堆疊),關機流程走進 boot-test 框架的 plug-in 前置就死在那裡。

**根因** 測試想驗的是 Redfish 的 SoftwareInventory(純讀),但 suite
的 setup 綁了 host 電源控制 —— **測試的前置比測試本身要求更多環境**。
分類:QEMU 缺硬體(host)× 測試假設(所有環境都有 host)。

**教訓(方法論)** 追根因不能停在錯誤訊息的字面:「Plug-in setup
failed」與真根因(host 電源假設)隔了兩層(訊息出處 → setup 內容 →
環境能力)。方法是固定的:先找**訊息的出處**,再找**誰呼叫它**,
最後問**它假設了什麼**。

## 2026-08-12(W9)exp10 電平不是挑的,是算的:70 °C 什麼都量不到

**現象** exp10 要量「PID 決策 → PWM 生效」段,注入電平初想用
setpoint ± 5(60/70 °C)。

**假設** 任何高於 setpoint 的電平都會讓 PWM 動。

**先驗哪個、為什麼** 不跑,先用部署 config 的係數算作用窗:
70 °C 時外圈 P 項 = −220.28 × (65−70) = **+1101 RPM**,遠低於
`outLim_min = 3000` —— 要等積分以 +25 RPM/s 爬 ~76 s 才出箝制,
8 s 的 rep 窗內 PWM 一格都不會動,實驗會「成功地什麼都沒測到」
(W5 符號檢查那次的翻版)。90 °C 時 P 項 = +5507,單獨越過箝制,
一個外圈週期內 setpt/PWM 就動。電平定為 55↔90 交替。

**根因** 箝制(outLim/integralLimit)把「可觀測」變成有門檻的事:
訊號要大到讓機制離開箝制,量測才有東西。這與 W8 的 slew 死旋鈕
(作用窗之外的掃描)、W5 的 3000 箝平(兩點同值分不出符號)是
同一族 —— 三次都是「先算作用窗,再定實驗參數」。

**教訓(方法論)** 觀測性實驗的參數也要推導,不是「找個合理值」。
判準:動手前先回答「這個參數下,機制的每一段會不會離開飽和/箝制/
死區?」答不出來就先算,算不動才做先導 run。

## 2026-08-12(W9)同一個症狀、三層根因:安靜的量測通道

**現象** exp10 的活體檢查連續兩次死在同一句:「暖身注入 4 s 內沒出現在
D-Bus 串流」。而手動探針每次都證明 busctl monitor 本身是通的。

**假設** ① busctl match 寫錯;② `-tt` 的 pty 有問題;③ 解析壞了;
④ 通道時序競態。

**先驗哪個、為什麼** 先把 stderr 撿回來重現一次 —— 第一版把量測通道的
stderr 丟進 DEVNULL,通道死得無聲無息,這本身就是第一個要修的錯。
重現輸出裡看到 `DOUBLE [0;1;39m41.938[0m;`:**pty 讓 systemd 系工具
開了彩色輸出**,跳脫碼插在「DOUBLE 」與數字之間,regex 撲空(③,
第一層 —— 而 `-tt` 正是為了治塊緩衝加的:一個修正引來下一個症狀)。
修掉(`SYSTEMD_COLORS=0` + host 端剝碼)再跑,同一句又死;儀器化重現
(單獨拉起同一個 Stream 類別)卻一切正常 → 差異只剩「三條通道同時
握手 vs 單條」:**固定 `sleep(3)` 輸給偶發的慢握手,注入訊號發出時
聽眾還沒掛上**(④,第二層)。順這條再推演出第三層:上一次中止把
感測器留在 90 °C,下一輪 rep00 再注 90 = **值沒變 = dbus-sensors
不發 PropertiesChanged** —— 通道再健康也會被冤枉(機制上就是 W3
「穩定溫度被當成感測器死掉」的那顆地雷,換個方向再咬一次)。

**根因** 三層獨立疊加:pty 彩色碼毀解析、固定延遲賭輸競態、
同值注入無訊號。修:`SYSTEMD_COLORS=0` + 剝碼(雙保險);
「就緒屏障」(busctl banner + zone 心跳 ≥3 行 + Redfish 首讀到齊
才開打)取代固定 sleep;開場中性預位 70 °C 保證每次注入都是真邊沿。

**教訓(方法論)** ① 量測通道的 stderr 永遠要留 —— 安靜失敗的儀器比
壞掉的儀器更危險(push_temp.sh 那則的儀器版);② 「等它就緒」要等
**就緒的證據**,不是等固定秒數 —— 秒數是對時序的猜測,證據才是同步;
③ 邊沿觸發的觀測鏈,實驗設計要保證每次刺激都是真邊沿;
④ 同一個症狀底下可以疊多個獨立根因 —— 修一層就靠「症狀消失」驗收
會把運氣當成修好,要修到「儀器化重現的行為也解釋得通」為止。

## 2026-08-12(W9)量測方法 v1→v3:被同一份資料推翻兩次

**現象** exp10 分析結果病理化:seg1 = +12.5 s、seg2 是**負的**;
更早一版整個 rep 被「行距 16.85 s」拒收 —— 但注入迴圈自己的節奏
全程 8.0 s 無縫,「環境凍結」說不通。

**假設** ① 環境真的在凍結;② 傳輸鏈在批次;③ 時鐘本身有問題。

**先驗哪個、為什麼** 驗屍**已存檔的原始串流**(原始資料進 git 的價值
在這一刻兌現):zone 行以 ~16 s 一批到達、同批 host 時戳全部相同 →
② 實錘:ssh 鏈對低流量串流做 ~8 KB 塊緩衝;三個傳輸變體
(-tt / stdbuf -o0 / 免密金鑰)實測都治不動,拿掉 pty 更慘(0 行,
BusyBox tail 對非 tty 整塊緩衝)。→ 方法 v2:時鐘搬回源頭(zone 行
自帶 epoch_ms、busctl 訊息自帶 µs Timestamp),單一 offset 橋接。
再驗屍:epoch 每 40 s 整**跳 +7.6 s**、列值連續、host 側無洞 →
③ 也實錘:guest 時鐘(TCG)以 **0.81×** 速率行走、週期性被拉回牆鐘。
v2 的「橋接後 ≥ t0」閘門在鋸齒下把事件錯配到 16 s 後**下一個同電平
rep**,seg1=+12.5 / seg2<0 全是它的屍斑。→ 方法 v3:**配對不用時鐘,
用序列索引** —— 電平 90/55 嚴格交替,D-Bus/zone/Redfish 三條轉換序列
各自時間單調,第 i 個 rep 恰對第 i 個轉換,零歧義;時鐘只決定段差的
**單位**(全程 = host 錶,②③ = guest 純域,offset 完全消去)。
對齊器還吃下兩個真實毛邊:swampd 自己的 ofstream 也有 ~8 KB 緩衝 →
legacy 舊高原會流進捕捉(容忍頭)、關通道會丟掉緩衝裡的尾巴
(容忍尾、缺的 rep 逐個判無效),中段錯位一律大聲死。

**根因** 三層,每層都是在資料上驗出來的:傳輸批次毀「到達時戳」;
guest 時鐘鋸齒毀「跨域比較」;兩層 8 KB 緩衝毀「串流完整性」。

**教訓(方法論)** ① 原始串流進 git 的意義不只重現 —— 方法可以重寫
三次,資料一次都不用重收;② 跨時鐘域的任何「大於/小於」都是隱性
假設,能用**結構**(交替、單調、序列)配對就不要用時鐘;③ 「量不到」
也要量化:①④ 不可分離的結論帶著鋸齒的次數/幅度/週期三個數字,
比硬拆一個錯的數字值錢;④ 修一層就靠「症狀消失」驗收會把運氣當成
修好 —— 三層根因就是三次「修完再驗屍」挖出來的。


## 2026-08-13(W10)CI 首紅 3 秒:No module named 'sh'

**現象** ci.yml 首推,cpp/experiments 一次綠,`upstream-build` 3 秒紅。

**假設** ① runner 上 docker 不可用;② 上游腳本缺 Python 相依;
③ WORKSPACE 佈局不符合腳本預期。

**先驗哪個、為什麼** 直接抓 job log(最便宜、而且是**一手證據**;
三個假設用同一份 log 一次分辨)。traceback 指到
`build-unit-test-docker:38` 的 `from sh import git`。

**根因** 兩層:表層是 runner 的 python 沒有 `sh` 模組;底層是
**記憶與事實不符** —— 記憶說「W8 跑過 run-unit-test-docker 綠」,
實查 docs/upstream.md 前置表,W8 做的是 docs repo 的 prettier;
這支腳本今天才第一次在任何一台我的機器上真的執行。
本機以裸 python3 重現同錯,`pip install sh` 後過關 → ci.yml 補一步。

**教訓(方法論)** 「跑過沒」以 log 與文件為準,不以印象為準 ——
印象會把「相鄰的事」合併成「同一件事」。CI 對第三方腳本的相依要
顯式安裝,不賭 runner 映像剛好有。

## 2026-08-13(W10)93397 匿名看是 Not found —— private 旗標

**現象** 用匿名 REST 查 change 93397(W8 的第一筆,已 Abandon)回
`Not found`;查詢式搜尋回空陣列。

**假設** ① change 被刪除;② 編號記錯;③ 可見性問題(private/wip)。

**先驗哪個、為什麼** 用自己的 ssh 身分 `gerrit query`(一條指令、
authed,三個假設一次分辨:查得到=沒刪+編號對,剩可見性)。

**根因** `"private": true` —— 當時推送帶了 private 選項。順帶把另一件
W9 待辦一起驗掉:owner.name = `Chung-Wei Lan`,顯示名根本不用修。

**教訓(方法論)** T0 證據的「對外可見性」是獨立於「存在性」的性質,
要用**別人的身分**(匿名)驗過才算數;文件裡的連結,自己點得開
不代表別人點得開。決策(使用者):維持 private,文件註明。

## 2026-08-13(W10)候選 B 差點被大小寫騙過

**現象** 推 93470 前查 Gerrit merged 紀錄,發現 47606
(2022-01「Make specific UNA sensors not trigger failsafe」)動過
configure.md —— 而那正是 missingIsAcceptable 機制的功能 commit,
「七欄未文件化」的前提瞬間可疑。

**假設** ① 已被文件化(EM 拼法 MissingIsAcceptable,我的 grep 區分
大小寫所以漏抓);② 它文件化的是別的欄位;③ 文件化過又被刪。

**先驗哪個、為什麼** 直接看該 commit 對 configure.md 的 diff
(`git show <sha> -- configure.md`,一條指令直接分辨三者,
比任何 grep 都便宜且權威)。

**根因** ② —— 它加的是 sensor 層的 `unavailableAsFailed`(存在但
自報 unavailable),與 controller 層的 `missingIsAcceptable`
(整顆缺席)是兩個機制。再以不分大小寫 grep 重驗七欄:0 次,前提成立。
把這個區分寫進 patch 的 margin 表 —— reviewer 最可能問的問題,
先答在文件裡。

**教訓(方法論)** 「grep 0 次」的證據強度取決於 pattern(大小寫、
同義詞、EM/JSON 拼法差);查「有沒有人做過」要沿**功能史**
(commit 歷史、路徑過濾)查,不能只沿字串。查證流程本身要能
推翻自己的結論,否則只是儀式。

## 2026-08-13(W10)紅燈證明 R1 的兩個發現

**現象** rthMin +20% 推上分支:experiments 紅(預期),
**cpp 32 個 case 全綠(預期外)**;且 assert_metrics 在第五個 claim
處 ZeroDivisionError,整支 traceback。

**假設(對 cpp 全綠)** ① 測試沒編到新碼;② 性質型測試對參數改壞
天生盲;③ 容差太鬆。

**先驗哪個、為什麼** 看 run 裡 cpp job 的測試數(有跑=①排除),
再對照本機 mutation 表:M6(rthMin 調**小**)是被「飽和條件」測試
抓的 —— 調大讓飽和更容易,該守門自然不叫 → ②。

**根因** 性質型測試驗「關係」(守恆/單調/飽和條件),不驗「數值」;
數值的守門在 claims 斷言層 —— 這正是 assert_metrics 存在的理由,
一次紅燈證明把「測試綠 ≠ 數字對」變成可指認的實測。
第二個發現:檢查器自己會倒 —— 單一 claim 崩潰讓其餘九個沒被檢查。
修正 = 逐 claim 攔截、記 FAIL 繼續查(commit 805ab36,pytest +
mutation AM5 守著;AM5 用 `except ()` 植回「接不到任何東西」)。

**教訓(方法論)** ① 紅燈證明的價值不只「會紅」,在於**紅的形狀**
與預測的差 —— R2 我預測 parity 全綠,實際
`NoDivergenceWhenFeedForwardIsZero` 也紅(它交叉比對我的一般路徑與
上游,等價一破就叫):預測落空要照實記,那是測試網密度的實測。
② 檢查器要被檢查;倒地的檢查器比沒有檢查器更危險,因為它上半場
印的 PASS 會被當成全卷。

## 2026-08-13(W10)Gerrit push 斷線:小查詢通、大串流死

**現象** `git push` 到 Gerrit(ssh:29418)兩次 `Broken pipe`,
斷點在 `git-receive-pack` exec 被接受、伺服器要回大量 ref 廣告的
瞬間;同時 `gerrit query`(小回應)正常、`gerrit ls-projects`
(大串流)回 0 行。

**假設** ① Gerrit 端限制;② 本機到 Gerrit 的路徑問題(MTU 級);
③ 同時在跑的 docker image build(--network=host,狂載套件)
把 WSL NAT 打飽。

**先驗哪個、為什麼** 用 ls-projects 當探針(不用 push 就能重現
「大串流」條件);等 docker build 結束後重試 —— 一次成功,③ 實錘。

**根因** 併發的大量下載讓長連線的大流量階段活不過去;兩天前
(93397)同一條路徑推送成功,環境變因就是今天的 docker build。

**教訓(方法論)** 「同一台機器、同一條指令、昨天可以今天不行」
先問**現在還有誰在用這條路** —— 併發負載是環境變因的第一嫌疑;
探針要挑「能重現故障條件的最小指令」,不要拿主作業本身試錯。

## 2026-08-13(W10)本機 docker CI:兩次失敗,兩個根因

**現象** run-unit-test-docker 在本機第一次 3 秒死(缺 sh 模組,
與 GitHub runner 同病),裝了 sh 後第二次跑 40 分鐘死在
phosphor-objmgr 的 COPY --from 找不到 boost 中繼映像、
轉去 docker.io 拉被拒。

**假設(第二次)** ① docker hub 授權問題;② boost 映像根本沒建成,
下游才會去遠端找;③ buildx 驅動看不到本地映像。

**先驗哪個、為什麼** 在 log 裡往前找 boost 自己的建置紀錄
(「下游找不到」的最常見原因是「上游沒產出」,先驗因果鏈上游)。
找到:`boost: #5 ERROR ... ./b2 ... exit code: 2` —— ② 實錘,
docker.io 拒絕是正常的(那個 tag 本來就只存在於本地)。

**根因** boost 從源碼建置在高併發下 flake(當時 mutation 66 案 +
多映像並行搶 CPU/RAM);對**純 .md 的 93470** 而言,該 pipeline
本來就沒有任何檢查會碰到文件(repo 只有 .clang-format)——
【判】不擋推送,重試與 CI 乾淨環境驗證並行。

**教訓(方法論)** 錯誤訊息指到哪裡,不等於錯誤發生在哪裡 ——
「pull access denied」是第 12120 行,病灶在第 6918 行;
在建置圖(DAG)上永遠先驗**上游節點**。資源競爭下的 flake,
重試前先把競爭者清場,否則重試只是擲骰子。

**★ 第三次執行的後記(同日稍晚)** 重試跑通了整條 pipeline,
這次死在 format-code —— 而且它**改了 configure.md**(prettier
全域檢查會重排 markdown 表格:新增的長列撐寬欄位,整張表重新
padding,40+/40−、內容零變)。我在第二次失敗後寫下的「該
pipeline 對 .md 沒有任何檢查」,是**用 repo 裡有沒有設定檔推理
出來的**,被真正的執行推翻。格式化後 amend 成 patchset 2 推回
93470。追加教訓:「這條 pipeline 會不會碰到我的變更」是實證問題
不是推理問題 —— 推理只該決定「值不值得等」,不該替代「跑過一次」。

**★★ 第四、五輪:檢查表的階梯繼續往上。** 第四輪 codespell 紅在
commit message:`behaviour ==> behavior` ×2(檔內另有一處)——
英式拼寫,上游字典是美式;修正時用 `git log -1 --format=%B` 撈出
現有訊息再改,**直接拿原稿覆蓋會弄丟 hook 加的 Change-Id**。
第五輪 codespell 綠了,換 markdownlint MD060:我手改一個字母
(behaviour→behavior,短一格)沒重排表格,pipe 對不齊 —— 同輪的
prettier 已當場把樹修好,amend 即 patchset 4。三輪三個 patchset,
每個問題(表格 padding、拼寫、pipe 對齊)都是「推理想不到、
執行一次就冒出來」的那種 —— 檢查表的每一項都要真的執行,
而且**要執行到綠為止**,不是執行到「我覺得剩下的都沒事」為止。

**收尾(第六輪 + 乾淨環境權威)** 第六輪 format 階段全綠
(codespell 0、markdownlint 無、prettier 零變更 —— 會碰到 .md 的
部分全部通過),build 階段死於 `c++: fatal error: Killed`:cc1plus
被 OOM killer 收走 —— `-flto` 的重編譯撞上同時在跑的 66 案
mutation,純資源競爭。同時刻,本 repo CI 的 `upstream-build` job
(pristine master、乾淨 runner、同一支腳本)**端到端綠**
(run #5)—— 那才是這條 pipeline 的權威證據;本機的角色只是
把 format 階段(唯一會碰到我的 .md 的部分)驗到綠。

## 2026-08-13(W10)體檢 W1~W9:三處「文件對不齊」

**現象** 開工體檢(使用者指定)發現:① docs/upstream.md 候選 3
寫「改成現行 tag」,同 repo 的 robot-qemu-ci.md 觀察 3 寫「刪行是
唯一解」——互相矛盾;② README 的 mutation 數停在 41(W9 已是 61);
③ 記憶說 W8 跑過上游 docker CI(見上則,實未跑過)。

**假設** 不適用(這是盤點,不是除錯)—— 但要回答「為什麼會發生」:
候選 3 那句寫於探針**之前**,探針推翻結論後只改了 robot-qemu-ci.md,
沒有回頭改 upstream.md;README 數字是 W9 收工六項裡「與當天產出
一致」檢查的漏網。

**根因** 同一結論寫在兩個檔案,更新時只改了一份 —— 結論沒有
single source of truth。

**教訓(方法論)** 會演化的結論(修法、數字)只該有一個權威位置,
其他地方用指標;做不到時,收工檢查要加一條「grep 這個結論的
所有出現點」。矛盾的兩份文件比錯的一份更傷 —— 讀者無從判斷
哪份是新的。

## 2026-08-13(W11)第一則上游 review:reviewer 的要求與自己的量測相撞

**現象** George Keishing(openbmc-test-automation 頭號 maintainer,
1796 commits)給 93469 投 −1,inline comment 要求把「刪行」改成
「重指 `Verify_Redfish_Update_Service_Enabled`」——正是 commit
message 第二段用實測否決過的選項;而他「告知」的 rename 就是
第一段引用的 5236ec54。

**假設** ① maintainer 說了算,照改;② 他只讀了 diff+開頭,
回覆說明即可;③ 我們的第二段本身有洞,被他的要求剛好逼出來。

**先驗哪個、為什麼** ③ 最便宜也最要命——回錯話的信用成本最高,
先審自己再回。審出兩件事:(a) 同 suite 的 SoftwareInventory 兩案
在清單裡活了四年、上游 CI 沒紅,而我們寫的是「suite 天生進不了
QEMU_CI」——單平台(bletchley)量測被寫成了全稱命題,是外推;
(b) 使用者要求 fresh boot 重驗探針,FAIL 復現(見下則)。
結論:②③ 並存——他大概真沒讀完,但我們的第二段也真有外推。

**根因** maintainer 一天 triage 幾十個 change,只讀 diff 與訊息
開頭;我們把關鍵證據埋在第二段中間,等於對這種閱讀模式不設防。

**教訓(方法論)** reviewer 要求與自己量測衝突時的順序:重審
自己 → 重驗 → 回覆 = 證據前置 + 明說量測邊界 + 一個能分勝負的
問題(這裡是「CI 的 QEMU target 是誰」)。不是說服,也不是服從。
設計回覆時假設對方沒讀完;措辭時假設對方都讀了。

## 2026-08-13(W11)重驗多挖出一層根因——因為這次留了 console

**現象** 重跑探針(fresh boot、同官方變數):FAIL 復現。但這次
console 流裡看到 8/12 沒記到的死點:boot-test 框架內建的
`Auto_reboot/cp_setup` plug-in 對 `/redfish/v1/Systems/system`
PATCH `{"Boot":{"AutomaticRetryConfig":"Disabled"}}`(host 開機
設定),bmcweb 回 **HTTP 500**、三試全敗,才吐出那句
「Plug-in setup failed」。

**假設** 8/12 為什麼沒看到這層?① 當天失敗路徑不同,沒有 500;
② 同病,但證據沒被打包——這層細節不在 Robot 三件套裡。

**先驗哪個、為什麼** zgrep 兩天的 log.html.gz:
`AutomaticRetryConfig` **兩天都是 0 筆**(連 8/13 自己的都是)——
plug-in 是子行程,輸出只上 console,不進 Robot 的 log.html。
8/12 沒存 console → ① 無法回溯驗證;② 被檔案結構直接證實:
這一層**只活在 console 流**。

**根因** 打包清單抄了 Robot 的三件套(log/output/report),但
boot-test 框架的 plug-in 輸出走 console —— 證據打包用了 Robot 的
視角,漏了框架的視角。追根因的深度被打包內容封頂:8/12 停在
「plug-in 前置死掉」不是不想深,是沒料。

**教訓(方法論)** 能追多深,取決於**存了什麼**:失敗 run 的
console stream 一律進打包。修在流程不是修在記憶:rerun 目錄補存
`console.log.gz`,`run_robot_qemu_ci.sh` 加 `tee`。順帶補齊對照組:
舊 tag 單獨跑,Robot 拒跑(rc 252,`no tests matching`)——
「無聲 no-op(舊 tag)vs 大聲紅燈(新 tag)」,這一對比就是
刪行 vs 重指的本質差異,也是回覆 George 的骨架。

## 2026-08-13(W11)CLA 寄出九天等於沒寄:對外依賴要自帶 timer

**現象** Discord 請核白名單,Milton 回「complete a cla first」;
但 ICLA 8/4 已寄 manager@lfprojects.org,九天無 ack —— 在對方的
流程裡,我們等於不存在。

**假設** ① 信沒送達;② 在處理但不發 ack;③ 寄錯地址。

**先驗哪個、為什麼** ③ 最便宜:比對 CONTRIBUTING.md(L50 就是
這個地址),排除。①② 無法自查 → 回 Milton 時直接問「怎麼查
狀態」,並設兩三天的追蹤點(forward 8/4 原信重寄,保留時間戳)。

**根因** 把「寄出」當「完成」,沒設回音期限。它卡的不只是禮貌:
Jenkins 白名單、93469/93470 的 CI、ec::pid() 測試貢獻全排在它
後面 —— 時程風險最大的不是自己手上的工作,是無 SLA 的外部佇列。

**教訓(方法論)** 任何交到別人手上的依賴,寄出當下就記
「N 天沒回音就做什麼」。等別人踢到才發現,已經晚了九天。

## 2026-08-13(W11)紅隊自查 93469:把 500 釘到 D-Bus 物件層

**現象** 使用者三重懷疑自己:①change 沒基於最新 master?
②CLA 沒過害的?③會不會是 WSL/環境問題,「其他人都可以」?
先擺正一個事實:兩個 change 上沒有任何紅色 CI(bot 只說
no CI,Jenkins 根本沒跑)——唯一的負訊號是 George 的人工 −1。

**假設** ①基底過舊;②CLA 擋了 review;③500 是我們環境的
假訊號(WSL 網路/Robot 框架/自建流程),別人的機器不會發生。

**先驗哪個、為什麼** ①②一次 Gerrit REST 查詢就能殺,最便宜:
落後 master 僅 2 commits、皆未碰 test_lists、死 tag 今天仍在
tip、mergeable=True(submit 策略 REBASE_IF_NECESSARY,單純
落後不需 rebase);CLA 只擋 Jenkins 白名單與最終 merge
(maintainer-workflow.md 寫明是 maintainer 人工核),不擋
review——George 的 −1 是純技術意見,與 CLA 無關。③要開
QEMU 才能驗,方法是**剝層**:把 Robot 整個拿掉,用純 curl
重打同一個 PATCH(payload 抄 lib/utils.robot:719)。

**根因** fresh boot 後純 curl PATCH ×2(RetryAttempts /
Disabled)皆 HTTP 500 → Robot 框架無罪;journal 抓到 bmcweb
自己的錯:dbus_utils.cpp:85 `ec=Invalid request descriptor
[generic:53]`(=EBADR)→ WSL 網路無罪,5xx 是 BMC 內部產生;
busctl:Settings 樹上 host1~host6 的 auto_reboot 都在,
**host0 不存在**(bletchley 一殼六主機);對照組:對 host1
同介面同屬性寫回原值 rc=0 → 寫入機制無罪。bmcweb
systems.hpp 的 setAutomaticRetry() 用
`"/xyz/openbmc_project/control/host" +
std::to_string(computerSystemIndex)` 拼路徑,而這個 image 的
Systems collection 只有一個 member(index=0)→ 每次都打向
不存在的 host0。四層收斂:不是版本、不是 CLA、不是 WSL——是
「單主機 Redfish 路由 × 多主機 settings 樹」的結構不相容,
stock bletchley QEMU 上任何人都復現。
證據:docs/robot/20260813_curl500_dbus_probe/(meta.txt 含
image sha256;bmcweb 引文為 2026-08-13 的 master,與 image
版 3.1.0-dev-739-gba9070d60b 行為一致,未逐 rev 比對)。

**「其他人怎麼都沒事」拆成兩個命題,都為真** (a) 大多數人在
單主機平台:host0 存在,PATCH 就成功——IBM 的 HW_CI 世界即
如此,George 的直覺沒錯,只是不適用 bletchley;(b) 這份清單
沒有活的守門 CI:in-tree 消化鏈(run-qemu-robot-test.sh,
DEFAULT_MACHINE=versatilepb → run-robot.sh --argumentfile
test_lists/QEMU_CI)檔頭自標 WIP,四年死 include 沒人發現,
本身就是「沒人在跑」的量測。我們大概是第一個把 bletchley ×
QEMU × boot-test 框架三件事同時跑起來的人。

**教訓(方法論)** 紅隊「環境嫌疑」的順序:便宜的先殺(REST
查詢),貴的剝層(拿掉框架用最原始工具復現),最後補對照組
(同一機制打一個存在的物件)。HTTP 5xx 本身就是「伺服器承認
是自己的錯」——4xx 才輪得到懷疑客戶端。「別人都沒問題」要拆成
「別人的環境踩不到」與「根本沒有別人在測」兩個可分別驗證的
命題,不能混成一團恐慌。

## 2026-08-13(W11)自己踩坑:背景化的最小單位是「整條鏈」

**現象** 照坑 26 的 setsid 模板經 `wsl -- bash -lc` 啟動
QEMU:回了 LAUNCHED,但 .out 檔根本沒生出來;等待探針第一圈
就宣判 QEMU_DEAD。

**假設** ①run_bmc.sh 自己死了;②setsid 沒保護到,鏈在
exec 前就被收走;③探針誤判。

**先驗哪個、為什麼** 看 .out:**檔案不存在**——連重定向都
沒執行過,①出局(它死也會留檔)。剩②:
`A && B && setsid C & D` 的 `&` 綁的是**整條** `A && B && C`,
setsid 只保護 exec 之後的 QEMU;`bash -lc` 一退出、session
拆掉,還沒走到 setsid 的前段子 shell 先被 SIGHUP 收走。
③也真:探針 loop 1 就 pgrep,沒給啟動器前置作業任何 grace。

**根因** 兩個獨立 bug 疊加:背景化保護的範圍畫錯(保護了
「將來的 QEMU」,沒保護「現在的鏈」)+ 探針比被測物先開槍。
症狀與坑 26 一模一樣,機轉是第三種(坑 14 是 stdin EOF、
坑 26 是 QEMU 蓋 SIGHUP handler、這次是鏈的前段不在新
session)。修法:`setsid -f` 包整個腳本檔 + 探針前三圈免死。

**教訓(方法論)** 背景化就用 `setsid -f` 包**整個腳本檔**,
不要掛在鏈尾;任何等待式探針,第一次判死之前要有 grace
period,否則探針的誤判會蓋掉真正的死因。「同症狀≠同根因」
這句 runbook 裡自己寫過的話,第三次應驗在自己身上。

## 2026-08-14(W11)計畫給的範文,三處被 tree 推翻

**現象** W11 計畫附了 limitations/design/cascade 的完整範文,細到可以
照抄。照抄會寫進三個錯:① design 文件「固定八節」;② Impacts 寫
L2「uses a compressed plant time scale」;③ 限制寫「內圈風扇 PID 用
上游預設值、沒有重新整定」。

**假設** ①計畫單純寫錯;②上游模板在計畫寫成之後改版;③計畫寫的是
「預測」,而 tree 在 W5~W7 的實作早已走出不同的解。

**先驗哪個、為什麼** 三處都用同一招最便宜:把引用鏈縮短到一跳 ——
不經計畫轉述,直接讀一手來源(上游 docs clone 的 design-template.md、
harness/dbus_bridge.py 的檔頭說明、config.baseline.json 的欄位)。
每處成本一分鐘;寫錯的成本是交付文件裡一句面試會被戳破的話。

**根因** 三處三個不同根因,但同一族:① 上游模板的 Organizational 是
Impacts 底下的 ###,計畫轉述時把它升級成獨立的第八節 —— 轉述漂移;
② 「壓縮時間尺度」是計畫動工前的預測,實作發現 swampd 的兩個迴路
週期掛在牆鐘上、快轉不可能,W7 用「即時執行 + 單 seed + 統計歸 L1」
解掉,計畫沒跟上;③ 「上游預設值」是佔位描述,實況是刻意
P=I=0 純前饋(「沒有量測就不整定」),語義比「沒調」強得多 ——
而弱的那句會把一個設計決定講成一個疏忽。

**教訓(方法論)** 範文是預測,tree 是事實;引用鏈每多一跳
(上游 → 計畫 → 我的文件)就多一次漂移機會,寫交付文件前先把鏈
縮到一跳。副產品:cascade.md §6.5 自己也過期了 ——「疊圖是 W7 的
工作」寫於 W6,W7 做完沒人回頭改,文件靜靜錯了五週。文件過期不是
恥辱,過期了不校準才是;本次順手立了規矩:凡「還沒做」的句子要嘛
帶日期、要嘛指向會過期時自動變紅的東西(測試/CI),不然就別寫。

## 2026-08-14(W11)乾淨 clone 抓到「Ok: 5 假全綠」——檢查器自己也在裝綠

**現象** 收工乾淨 clone 檢查:`meson test` 回 `Ok: 5`(本機是 6)、
`assert_metrics.py` 直接 `ModuleNotFoundError: pandas`——但整支檢查
腳本 exit 0,還印了 CLEAN CLONE CHECK DONE。

**假設** ① repo 壞了(少 commit 了什麼);② clone 環境沒 Python
相依,測試被跳過;③ 檢查腳本自己吞錯。

**先驗哪個、為什麼** 先 ②③——一次 grep 就能殺:`test/meson.build`
的注釋自己寫著這個坑(configure 沿 PATH 找 python,系統 python 沒
pandas/pytest → `python_tests_ok=false` → pytest 目標**不註冊**)。
① 最貴(要 diff 兩棵樹)排最後——結果不用走到。

**根因** 三層,一層比一層難看:
(1) 檢查腳本用非 login shell 跑,venv 沒啟用 → 意外撞進「陌生人
clone」的真實環境——這半是好事,它暴露了 (2)(3)。
(2) README「自己跑一次」的三行指令**沒有任何一步裝 Python 相依**;
meson 的 warning 又把修復指示寫成 `source ~/.venvs/thermal/...`——
一條只存在於我機器上的路徑。**對外,這個警告等於沒警告。**
(3) 檢查腳本 `set -e` 沒配 `set -o pipefail`:`python3 … | tail`
讓 pandas 的爆炸變成 tail 的 exit 0——**檢查器自己會裝綠**
(W10 R1 修 assert_metrics 除零守門的同族錯,這次輪到我的 shell)。

**修了什麼** README 補 `python3 -m venv` + `pip install -e '.[dev]'`
兩行與「**Ok: 6 才是全部**,Ok: 5 = 146 個 Python 測試沒在跑」的
警語;meson warning 文案改成對任何人可執行的指令;檢查腳本 v2 加
`set -euo pipefail` 並改成**逐字照 README 的指令**走(檢查的就是
README 教的那條路,不是我自己的捷徑)。

**教訓(方法論)** 「跳過而不是失敗」是測試基礎設施最危險的仁慈:
可以跳,但要大聲,而且修復指示要寫給**讀者**而不是寫給自己。
檢查器與被檢查物適用同一套紀律(shell 的 pipefail = Python 的
除零守門)。乾淨 clone 檢查再次抓到本機永遠抓不到的東西——這次
抓到的是「README 教的路走不通」,那正是它唯一的視角。

## 2026-08-14(W12)散文裡的測試數字:三處 146、一處 145,實測 153

**現象** README 第一屏改版(文體:評審視角→工程師視角,8cae59d)
時順手 grep,發現 pytest 案例數散文寫 146(×3,含今早 166cc24 才
寫進 meson 警語的那句)與 145(×1);`pytest --collect-only` 與
全綠 run 的 testlog 都說 **153**。

**假設** ① 153 是我這側環境造出來的(未 commit 的新測試、collect
範圍與 meson 調用不同);② 146/145 曾經對過,測試每週在長、散文
沒跟上;③ 從來沒對過(從別處抄來)。

**先驗哪個、為什麼** ① 最便宜先殺:`git status` 乾淨(只有本次
.md 改動)、`pyproject.toml` 的 testpaths 與 meson 的調用同指
`test/python`、剛跑完的 testlog 寫著 `153 passed`——三方一致,
153 就是 HEAD 的事實。②③ 之分對修法無差;週紀錄(82→107→128
→146)支持 ②:計數每週都在長,146 大概率是某週實況,被抄進
警語那天已經長到 153。

**根因** 這個 repo 對「量測數字」有 assert_metrics 守 14 條
claim,對「repo 自述自己的數字」(測試數量)卻沒有任何守門——
散文數字每加一個測試就過期一次,而且不會有任何東西變紅。最好的
樣本就是今早那句警語:「判別式」的一半(Ok: 6 才是全部/Ok: 5 =
Python 沒跑)上線半天就抓到第一個受害者——我,非 login shell 重
配 meson,系統 python 讓測試整包 SKIP、Ok: 5 假全綠當場現形;
「計數」的一半(146)則在 commit 當下就已經死了。同一行字,
不變量活著、計數已死,對照組天然形成。

**修了什麼** README/design.md 統一為實測 153(4f3d48d);meson
警語**把數字拿掉**——它的本體是判別式,在任何數量下都為真;
LOG 舊則不改(日誌記的是當時的認知)。

**教訓(方法論)** 散文裡的數字只有兩種活法:被斷言守著,或者
不寫。寫文案時把內容拆成「會過期的」與「不會過期的」:計數會長,
判別式不變;會過期的只放天天被重讀的地方(README 第一屏),沒人
重讀的地方(程式裡的警語)只放不變量。同場另一件:第一屏文體
改寫的檢驗句——「任一句拿掉『讀者=面試官』前提要仍說得通」——
理由與取捨記在 deviations 表與 8cae59d 的 commit message。


---

## 2026-08-16(W12)「把履歷兩個字換掉」是問錯的問題

**現象** 要求是「公開 repo 裡的『履歷』都改成『專案題目』,我不要它讀起來
像履歷」。grep 出 6 處 `履歷`,而**沒有一處填得進「專案題目」**:那 6 處的
語法角色是「引用這些數字的地方」(`README、履歷、圖的標註、CI 斷言全部引用
同一個來源`),不是「這個專案叫什麼」。要求本身指向的東西,跟關鍵字所在的
位置不是同一個東西。

**假設** ① 純用詞:換掉那幾個詞就結束;② 框架:「讀者=面試官」這個預設散在
句子的**謂語選擇**裡,`履歷` 只是它露出來的一角;③ 結構:有些整節文件的存在
理由就是給人評分,換詞救不回來、只能重寫或刪。

**先驗哪個、為什麼** 先驗 ①——一支 grep 就驗得完,而且 ① 若成立就不必讀
50 份文件,成本差兩個數量級。① 當場被推翻(上一段)。於是擴大關鍵字集合
(面試/作品集/賣點/招牌/展品/靶心)再 grep → 26 處,② 有支撐。但 grep 只能
證明「有」不能證明「沒有」,所以最後**逐字讀完 README + docs/ 全 13 份**,
又抓到 **11 處完全沒有關鍵字**的殘留。③ 只成立一處:`architecture.md` 的
〈待補:手繪版本〉整節,它唯一的存在理由是「面試白板題」——改寫成
「不看圖能不能重畫一次才是理解的檢驗」之後才站得住。

**根因** 「讀者=面試官」不是一個詞,是一個**謂語選擇**。它會逼出兩種句型,
兩種 grep 都抓不到:

- (a) 拿「面試會問 X」當作「這裡值得寫」的**理由**。
  例:`docs/upstream.md`「這兩個理由不能混,面試講錯會被追問到答不出來」。
- (b) 拿「我說得出 / 我能指著 Y」當作**交付標準**。
  例:README Gate 2 的兩條勾選項。

(b) 嚴重得多,因為**它把不可驗證的東西寫進了驗收清單**。README 第一屏才
剛用一張「宣稱 → 怎麼驗 → 花多久」的表宣告「這裡每一條你都查得到」,
往下捲兩百行,勾選項卻是「我說得出每個參數的物理意義」——讀者驗不到。

**修了什麼** 26 個檔案。`履歷` 6→0(全部換成 repo 內查得到的引用點,
那反而讓「單一真相來源」這個宣稱變成可查的);`面試` 24→8(8 個全在
LOG.md,見下);`作品集`/`portfolio` 2→0;`賣點` 3→1;`招牌` 12→0(→核心,
與 README 既有的「核心證據」對齊);`展品` 3→0。
`redfish-notes.md` 的「面試題」整節改寫成一張三段分割法的除錯表——
同樣的內容,從「我背好的答案」變成「別人照著做的步驟」。

**LOG.md 刻意不改**,只在檔頭加一段說明它是實驗日誌、逐則保留當日措辭。
理由是 08-14 自己立的規則「LOG 舊則不改(日誌記的是當時的認知)」——
兩天前立的規則,不能為了語氣一致就推翻。唯一的例外是 302 行那則:
它是**待辦**不是紀錄,待辦是朝前看的。

**教訓(方法論)**

1. **關鍵字掃描能證明「有」,不能證明「沒有」。** 要驗「沒有某一種語氣」,
   只能逐字讀 + 對每一句套一個**可判定的檢驗式**。這次用的是 08-14 自己
   發明的那句:「拿掉『讀者=面試官』這個前提,這句話還說得通嗎?」
   有檢驗式,逐字讀才不會變成憑感覺。
2. **更一般的版本:每一條驗收項目都要能被讀者自己證偽。**
   「我說得出 X」讀者驗不到;「X 寫在這個檔案裡」點連結就驗得到。
   差別不在語氣,在**誰有資格判定它是不是真的**。
3. **「面試會問」是很弱的理由,拿掉它反而讓文件變強。** 因為
   「可能有人會問」換成「不這樣做會出什麼事」的時候,被迫要寫出真實的
   失效模式——upstream.md 那句改成「混了之後遇到 `invalid committer`
   會跑去改名字,改半天還是推不上去」,對任何一個要推 Gerrit 的人都有用。

---

## 2026-08-16(W12)README 說做完了、docs/ 說未開始——同一個 repo 兩種事實

**現象** 上面那輪逐字讀,順手撞到七處**文件與現實不符**,其中三處是
**同一份文件自己矛盾**:

| 位置 | 文件寫的 | 實際 |
|---|---|---|
| `architecture.md` 圖 B 狀態欄 | L0/L1/L2 **`⬚ 未開始`** | README Gate 0~5 全打勾 |
| `architecture.md` 圖例與現況 | 「尚未實作:`dbus_bridge.py` W7、閉環 W7」 | Fig 3 的虛線就是它畫的 |
| `plant-model.md` §3.1 | 「32 個 pytest case」 | **153**(`--collect-only` 實測) |
| `plant-model.md` §3.3 | 「33 個植入的錯誤」 | **66**(`run_case` 計數) |
| `upstream.md` L21 | 「收到一次 reviewer 回覆 \| **未開始**」 | **同檔 L217** 是 08-13 George −1 的兩次往返全文 |
| `measurement.md` §4.0 | `exp09 = L1 vs L2 對照` | **同檔** §狀態表 `exp09 = failsafe,W8 完成` |

**假設** ① 單純忘了改;② 08-14 那輪計數稽核的**作用域太窄**;
③ 這類欄位天生會腐,沒有守門機制就一定會再腐。

**先驗哪個、為什麼** 先驗 ②,因為它一條 `git show` 就驗得完,而且**如果
② 成立,①③ 的討論才有意義**(否則只是「這次忘了」)。查 `4f3d48d`:
那輪 grep 的範圍是 README 與 design.md。② 成立。而 ①③ 也同時成立——
三者不互斥,② 只是解釋了「為什麼兩天前掃過還會留下」。

**根因** **修補打在「發現 bug 的那個檔案」,不是打在「這一類 bug」上。**
08-14 當天寫下的教訓是「散文裡的數字只有兩種活法:被斷言守著,或者不寫」,
那條教訓的作用域是**全 repo 的散文**;當天只套用到 README 與 design.md。
同一支 grep 多打一個 `docs/` 參數要三秒。

`upstream.md` 那一格最尖銳:同一份文件第 23~25 行自己寫著
「這份檔案是 T0 證據的索引,只要有一格是假的,整份的可信度就沒了」——
而第 21 行就是那一格,已經假了三天。

**修了什麼** 七處全部更新為實測值(數字來源:`pytest --collect-only` =
153、`run_case` 計數 = 66、`--gtest_list_tests` = 32,全部是這台機器當下
跑出來的)。三張會腐的表各加一行「本欄更新於 2026-08-16,權威來源是 X」。
`measurement.md` §4.0 那張表**不改內容**,改成在下面加補註——因為那張表
記的是「08-09 當天怎麼決定的」,跟 LOG 舊則同一個性質。

**教訓(方法論)**

1. **會腐的欄位要指定權威來源與更新日期。** 修法不是「這次改對」——
   那只是把時鐘歸零。修法是在表格旁邊寫「本欄更新於 YYYY-MM-DD,
   權威來源是 X」,讓下一個讀者知道**該相信誰**,以及**這份有多舊**。
2. **對公開 repo,自相矛盾比措辭差嚴重一個等級。** 措辭差只讓人覺得
   不夠專業;自相矛盾讓人開始懷疑**所有沒查的部分**。這個 repo 的主張是
   「每個數字都指得回證據」,而讀者只要抓到一處對不上,那條主張就整條倒。
   而且他抓到的機率不低——README 第一屏就在邀請他去查。
3. **⚠️ 這筆債沒有清乾淨,記在這裡不記在心裡。** 當時有第三個選項是
   「順便寫一條 pytest,掃 README + docs/ 的『N 個 pytest case / N 個
   mutation』型宣稱,對不上就紅」,沒有選。所以下一次計數變動(加測試、
   加 mutation)**仍然要靠人記得 grep 全 repo**——這正是這一則的根因。
   把修補打在檔案上而不是打在那一類 bug 上,今天做了第二次。

---

## 2026-08-16(W12)守門員抓到了,但晚一個 commit

**現象** 語氣改寫那個 commit 落下去,輸出裡跑出兩行:

```
mode change 100755 => 100644 bench/exp04_injection.py
mode change 100755 => 100644 tools/set_die_temp.py
```

這是 `CLAUDE.md` 明文警告、2026-08-09 咬過兩次的同一個陷阱:透過
`\\wsl.localhost\...` 這條路徑寫檔會洗掉執行位元。**第三次。**
而 `test/python/test_file_modes.py` 正是 08-09 為它寫的守門員 ——
**它沒有在 commit 之前紅。**

**假設** ① 測試沒涵蓋 `.py`(只看 `.sh`);② 測試沒被 `meson test` 收進去;
③ 涵蓋到了也跑了,但**檢查的時機**不對。

**先驗哪個、為什麼** 先驗 ③。因為 ①② 讀一次測試檔就排除得掉(成本三十秒):
它用 `git ls-files -s` 掃**全部** tracked 檔,判準是「有 shebang 就必須 100755」,
與副檔名無關;而且它確實在 `meson test` 的六項裡。③ 一驗就中:

- 測試讀的是 **git index** 的 mode —— 而且是**刻意**的,docstring 寫著
  「工作目錄的模式在 Windows 那一側本來就不可靠;真正會被別人 clone 下去的
  是 index 裡那個」。
- 但 index 要到 **`git add` 那一刻**才會拿到壞掉的 mode。
- 所以:我改完檔案 → `meson test` 綠(index 還是 100755)→
  `mutation_check.sh` 跑 66 輪、每輪跑全套 → 全綠 →
  一直到 `git add -A` 才把 644 寫進 index,**而那和 commit 在同一支腳本裡**。

工作目錄已經是 644 一個小時,期間所有的綠燈都是真的綠,也都是無效的。

**根因** **守門員「看哪裡」對、「看什麼」對,「什麼時候看」錯。**
「檢查 index 的 mode」這個判準,本身就保證了它必須等到 `git add` 之後才有東西可看
—— 它是一個 post-hoc 偵測器,不是 pre-commit 閘門。
08-09 當天發現這個 bug 的方式就是「commit 進去之後才發現」,
寫測試的時候把那個**發現的時機**一起繼承了下來。
**修補複製了「症狀被發現的時機」,而不是「症狀發生的時機」。**

**修了什麼** `chmod +x` **並重新 `git add`**(只 chmod 不夠 —— index 不會自己更新,
這一條 `CLAUDE.md` 特別標星號),新開 commit `2364fcc`,
**不 amend `b6f35fc`**:壞掉的 mode 與它的修復留在歷史裡比乾淨的歷史有價值。
順手全 repo 掃一次 shebang × mode,其餘乾淨。

**教訓(方法論)**

1. **一個檢查有三個獨立的屬性:看哪裡、看什麼、什麼時候看。**
   這次是第三個錯。而**時機錯的檢查最危險**,因為它會給你「有在守」的錯覺:
   它保護的東西照樣會壞,只是壞完才通知你。設計檢查的時候要明確回答
   「它會在事件的**之前**還是**之後**叫」,寫進 docstring。

2. **這一則跟今天另外兩則是同一個病的第三個變體。**
   - 第一則:修補打在「發現 bug 的那個檔案」,不是「這一類 bug」。
   - 第二則:同上,08-14 的 grep 只掃 README。
   - 這一則:修補複製了「症狀被發現的方式」,而不是「症狀發生的方式」。

   共同點是 **修補的作用域直接從症狀那裡照抄,沒有回頭問
   「這一類問題真正的邊界在哪裡」。** 三次都是同一天撞到的,
   所以這不是巧合,是一個我固定會犯的錯。

3. ⚠️ **已知修法,未做,記在這裡不記在心裡:** 判準加上工作目錄那一側。
   這個 repo 在 WSL 的 ext4 上,worktree 的 mode 是可靠的
   —— docstring 那句「Windows 那一側不可靠」講的是 repo 放在 `/mnt/c` 的情況,
   本 repo 不是(見 LOG 2026-07-28 第一則)。加上去之後 `meson test` 在
   `git add` **之前**就會紅。要動的話得同時補一個對應的 mutation。

## 2026-08-18(W12)tail 到的「最後一行」不是資料,是 buffer 的切口

**背景** 寫 `tools/failsafe_demo.sh`(exp09 rig 的單次縮時演示)。
live view 第一版用 `tail -1 zone_0.log` 每秒撈一行印摘要。

**現象** 預跑時 live 印出 `failsafe=51.625`(該欄應為 0/1),
t0 之後整行位移成 `die0=0.00、failsafe=<13 位 epoch>`;顯示值每
4~7 秒才跳一次。但收尾段的 python 從**同一份檔案**算出的 t1−t0 =
6.636 s、t2−t1 = 100 ms,完全正常;`awk -F, '{print NF}'` 統計
791 行**全部 10 欄**。

**假設** ① zone log 的欄序與 W2 記錄的不同;② 行尾 CRLF 或欄內逗號
讓 NF 偏移;③ `tail` 撈到的「最後一行」不是完整行 —— 讀的**時刻**
不同,看到的東西不同。

**先驗哪個、為什麼** ③。因為它是唯一能同時解釋三件事的:落地後
全 10 欄(排除①②的永久性錯位)、live 撈到 9 欄與 1 欄兩種殘骸、
顯示值 4~7 秒才動一次。驗法不用寫程式:行長 ~60 B、顯示更新週期
換算出來 ≈ 4 KB —— 正是 stdio 的塊大小。

**根因** swampd 的 zone log 是 `ofstream`(塊緩衝):每滿 4 KB 才
flush 一次,所以檔案的最後一行**幾乎永遠是被塊邊界切斷的半行**,
而且內容落後真實狀態數秒。`tail -1` 在串流中的檔案上,取樣到的是
buffer 的切口,不是任何一筆紀錄。

**修了什麼** live 顯示改用即時來源:`/tmp/sys/pwm0`(swampd 每個
內圈直寫)與 `busctl get-property` 輪詢 `FailSafe` / bridge 的
`Sensor.Value`;精確時序維持由收尾段從**落地後**的完整 log 計算。
坑寫進腳本註解。

**教訓(方法論)** 同一份檔案有兩種可靠性:**串流中**與**落地後**。
事後分析器(exp09)只碰落地後的檔案,所以它從來沒教過我這件事;
第一個碰串流中檔案的消費者(live view)立刻中招。這與 08-09 稽核 2
「量測工具比現象慢」同族 —— **顯示層自己的取樣機制,要先於被顯示
的資料被驗證**。凡是「邊寫邊讀」的設計,第一個要問的是誰在緩衝、
緩衝多大、切口落在哪。

## 2026-08-18(W12)set -e 與「預期會失敗的查詢」:demo 在最後一秒無聲死掉

**現象** `failsafe_demo.sh` 第二輪預跑:`bridge: done` 之後腳本
無聲消失 —— 沒有 cp、沒有 summary,而外層 `… | tail -45` 回 exit 0。
第一輪(改 live view 之前)同樣的收尾段是好的。

**假設** ① 收尾的 python 崩了;② `cp` 失敗;③ `set -e` 在 live
迴圈內被某個查詢命令觸發,EXIT trap 把一切收走。

**先驗哪個、為什麼** 先看時序證據再猜:`ls -la` 顯示 `zone_0.log`
的 mtime 是**第一輪**的,`demo_plant_meta.json` 是第二輪的 ——
死點在 `cp` 之前,①②出局,剩③。迴圈裡唯一沒兜 `|| true` 的是
兩條 `$(busctl … | awk …)`;而死亡時刻恰好是 bridge 剛退出、
`ThermalLoopBridge` 的 bus name 剛釋放的那一秒。

**根因** TOCTOU:`while kill -0 $BRIDGE_PID` 檢查時 bridge 還活著,
一秒後查它的屬性時已經死了。`busctl` 非零 + `set -o pipefail` →
`$()` 賦值非零 → `set -e` 終止 → EXIT trap 殺掉 swampd →
外層管道的 exit code 被 `tail` 的 0 蓋掉,屍體連聲音都沒有。

**修了什麼** 兩條查詢兜 `|| true`,查不到印 `?`(第三輪實測:
bridge 死後那秒印 `die0=?`,腳本繼續走完 summary)。診斷時的
第一動作是把 `| tail` 拆掉拿真實 exit code。

**教訓(方法論)**
1. **live 輪詢的對象會在輪詢窗口內死亡** —— 這不是異常,是收尾的
   常態。對「預期會失敗的查詢」,`set -e` 不是安全網,是啞彈:
   它把可預期的失敗升級成無聲的整體死亡。降級路徑(`|| true` +
   佔位輸出)是設計的一部分,不是妥協。
2. **`script | tail` 會吃掉 script 的 exit code。** 包管道的那一刻,
   就要想好之後怎麼拿到真實的退出狀態(`PIPESTATUS`、重導向到檔案、
   或乾脆別包)。這與 08-14「檢查腳本 set -e 沒配 pipefail 自己裝綠」
   是一體兩面:那次是管道讓失敗變成綠,這次是管道讓失敗變成靜音。

## 2026-08-18(W12)bmcweb 會回答 ≠ inventory 就緒:readiness 是三層的

**背景** 預演 demo 段 4(QEMU 上的 Redfish 指令),開機後
sleep 165 s 再 curl。

**現象** 第一輪:`/Chassis/chassis/ThermalSubsystem` 回空物件(其實
是 404 —— id 寫錯,`chassis` 是文件範例的字面值,W9 Robot 的
`CHASSIS_ID` 同一顆雷)。改用正確 id `Bletchley_Front_Panel_Board`
再開一輪:**還是 404,而且 `/redfish/v1/Chassis` collection 是空的**
—— 但 W2 實測過 `ThermalSubsystem.v1_0_0` ✅、W9 Robot 也用這個 id
過了測試。

**假設** ① id 又錯(被第二輪的正確 id + 完整格式的 404 排除);
② **部署丟失**(EM 設定不在 flash 的持久層了);③ **inventory 還沒
就緒** —— 165 秒只夠 bmcweb 起來,不夠 entity-manager 把板子掛上。

**先驗哪個、為什麼** ③。成本最低:再開一次機、每 30 秒輪詢一次
collection 就能分辨,不用 ssh 進去翻檔案;而且已有反證線索壓低 ②
的機率 —— 同一輪開機的 healthcheck 顯示 swampd 讀到了 zone 設定,
表示 `/etc` 持久層是活的,EM 設定沒理由單獨消失。若 ③ 成立,② 不用查。

**根因(輪詢實測)** t=150/180/210 s collection 皆空,**t=240 s 出現
2 個成員**(原生前面板 + 我們 EM 設定產生的 `Thermal_Loop_Demo`,
部署完好),ThermalSubsystem 回 `v1_0_0` + Status OK。
而 bmcweb 早在 t=165 s 就能回**格式完整的** 404 ——
服務可答與資料就緒,中間隔了約 75 秒。

**教訓(方法論)** readiness 至少三層:**程序活著**(systemd
active)→ **介面可答**(HTTP 有回應,哪怕是 404)→ **資料就緒**
(inventory 非空)。W1 坑 6 的「Redfish 要等 60~120 秒」只保證第二層;
拿第二層的訊號當第三層的門,得到的是格式完美的空答案。凡是
「等它好」的腳本,要明確寫出等的是哪一層、用哪個訊號判定 ——
demo 錄影 checklist 現在用「collection 非空」當第三層的門。

## 2026-08-30(W14)把「QEMU 有 machine」交給腳本算,第一次跑就抓到一格手寫錯誤

**背景** W14 的第一件事是重新確認所有會過期的上游事實(映像、
`ec::pid()`、`configure.md`、OWNERS、`QEMU_CI`、bmcweb 公告、Gerrit、
平台矩陣)。平台矩陣那一項,`docs/platform-matrix.md` 檔頭寫著
「產生方式:`platform_matrix.sh | tee`」。

**現象** 重跑 `platform_matrix.sh`:19 列五欄逐格與 07-28 相同。但這支
腳本只掃 manifest —— 三條件裡「QEMU 有 machine model」那一欄它從頭到尾
沒算過,文件裡那一段是手打的。第一次重跑還跑在非登入 shell 上,
`qemu-system-arm` 解析到系統版 8.2.2 而不是 `~/bin` 的 Jenkins 11.0.1,
而腳本輸出裡完全看不出來 —— 因為它根本沒碰 QEMU。

**假設** 手打的那一欄 ① 全對;② 有錯但不影響結論;③ 有錯且影響結論。

**先驗哪個、為什麼** 不挑 —— 把第三欄寫進腳本
(`tools/reverify_upstream.sh` 第 8 項:target → machine 對應表 +
`qemu-system-arm -M help`),讓機器把三欄一起印,三個假設一次分辨。
成本 20 行 shell,比逐格人工核對便宜,而且下個月重跑還能再用。

**根因** ②。`gbs` 那一列:文件寫「且 QEMU 無對應 machine」,腳本印出
`quanta-gbs-bmc`;再抓 Jenkins `gbs` 的 deploy 目錄,裡面是
`nuvoton-npcm730-gbs.dtb` —— 同一塊板子。嚴格照三條件算,交集是
`{bletchley, catalina, gbs}`;把 `gbs` 剔掉的其實是**第四個條件**
(映像要同時含 `dbus-sensors` 與 `entity-manager`,route (b′) 才建得起
感測器)。這個條件從 W3 起就一直在用,只是沒被寫成條件。
結論(主線 bletchley、備援 catalina)不變;舊文不改,加 08-30 補註。

**教訓(方法論)**
1. 「產生方式:腳本」這句話只對腳本真的產生的那幾欄成立。宣稱由腳本
   產生的表,腳本輸出要能**整張**貼回去;手補的欄位要標「手填」,否則
   下一次重跑的人(這次是我)會以為「逐格相同」等於「全部確認」。
2. 這是 08-16「散文裡的數字只有兩種活法:被斷言守著,或者不寫」的另一個
   切面:**判斷也只有兩種活法 —— 被腳本重算,或者標成人工判斷。**
   修法不是改對那一格,是讓那一欄從此由腳本印。
3. 依賴 PATH 的工具,腳本要把自己用到的版本印出來(`reverify_upstream.sh`
   現在印 `command -v` 與 `--version`)。同一支腳本在兩種 shell 下看到
   兩個世界、輸出卻長得一樣,是最難察覺的那種錯。

## 2026-08-30(W14)重跑 `make figures`,四張 PNG 變了 —— 變的是 caption,不是圖

**現象** 環境重跑第 6 項:`make figures` 之後 `git status` 列出 4 個 meta 檔
與 `fig1/2/3/5` 四張 PNG;同時 CSV 逐 byte 相同、`assert_metrics` 14/14 PASS。

**假設** ① PNG 只是跟著 meta 檔變(caption 記的 data commit 被改寫成 HEAD);
② 本機 matplotlib/numpy 版本與產圖時不同(CI 釘了四個版本);
③ 產圖不是決定性的。

**先驗哪個、為什麼** ①:成本最低(從備份還原 4 個 meta 檔、只重畫、30 秒),
它成立時 ②③ 就不必查;它不成立時 `git status` 會直接把問題交給 ② 或 ③
(版本 `pip show` 可查,決定性連畫兩次可比)。

**根因** ①。meta 還原後 `plot.py --all`,四張 PNG 回到與 git 逐 byte 相同;
四個套件版本也與 `.github/ci-constraints.txt` 逐一相同。CI 的決定性檢查
(`ci.yml`)刻意把 meta 排除在 byte-diff 之外、PNG 走 `test_figures.py` 用
釘住的版本比 —— 所以 CI 上這件事不會發生,只有「本機重跑再看 `git status`」
這條人工流程會撞到。

**教訓(方法論)** 規劃文件(W14 D6)給的自檢指令是
`git diff --exit-code bench/data/`,那條在本機重跑後**永遠紅**(meta 必變),
等於教人把「預期的紅」當訊號;CI 用的是帶排除清單的 pathspec。自檢指令要抄
CI 那一條,不要抄它的簡化版 —— 一條會因為正確行為而紅的檢查,跟一條永遠綠的
檢查一樣沒有資訊。`docs/verification-log.md`〈環境重跑〉寫的是 CI 的原句。

## 2026-08-30(W14)failsafe demo 單趟 6.456 s,高於 Fig 4 五趟範圍 —— 能排除的都排除了,根因未定

**現象** 環境重跑第 5 項,`tools/failsafe_demo.sh`(exp09 的單趟縮時版)算出
t1−t0 = 6.456 s、t2−t0 = 6.556 s。Fig 4 的五趟是中位 5.081 s、範圍
[5.010, 5.155];`claims.json` 的允收區間(±25%)是 [3.81, 6.35] ——
這一趟若是量測,會落在允收區間**外**。同一時段主機正在跑 18 個讀檔代理、
meson 建置與 QEMU。

**假設** ① swampd 被主機負載餓到(它寫 zone log 的節奏會出現空洞);
② bridge 的推送落後名目節拍(CSV 的 `t_s` 是名目值,真實推送時間晚);
③ 訊息路徑(私有 dbus-daemon)延遲了最後幾筆 PropertiesChanged;
④ 單趟落在分佈尾端 —— 五趟的 range 本來就不是上界。

**先驗哪個、為什麼** ① 與 ②,因為兩者都有現成證據可讀、各 10 秒:
① 讀 `zone_0.log` 行距(exp09 的 run 有效性三前提之一就是「事件窗行距
≤ 0.5 s」);② bridge 收尾自己印 schedule lag。

**結果** ① 排除:事件窗(t0−2 s ~ t0+9 s)內 **0** 個 >0.5 s 的空洞,整趟
1485 列最大 0.739 s 且不在窗內。② 排除:`schedule lag at end: +1 ms`。
t2−t1 = 100 ms 與五趟一致(恰一個內圈週期),差的全在 t1−t0。③④ 用這趟
留下的東西分不出來:demo 沒有接收側的每筆時間戳(exp09 也沒有 —— 它靠
三前提把環境健康擋在**前面**,不靠事後定位)。

**根因** 未定。這趟不進 `bench/data`,`claims.json` 不動;要定位就是在安靜的
主機上重跑 exp09 五趟(28 分鐘),看它是尾端還是系統性。

**教訓(方法論)**
1. 「能排除什麼」也是結果。兩個最便宜的假設各 10 秒排除掉,剩下的兩個要
   新的量測工具(接收側時間戳)才分得開 —— 寫下來,比硬湊一個根因誠實。
2. demo 與量測的差別不只是次數:量測腳本把「環境健康」寫成**事前門檻**
   (exp09 的三前提),demo 腳本沒有 —— 所以 demo 跑出怪數字時只能事後翻
   證據,而證據不一定留了。錄影要當眾播的那一趟,前一分鐘先跑一次確認落在
   範圍內;落外就不要用那一趟,也不要拿它講數字。
3. 同一天的開機 readiness 三層分別在 +288 / +289 / +290 s(08-18 量到
   bmcweb +165 s、inventory +240 s);guest 自報 FinishTimestampMonotonic
   202.7 s。沒有同條件對照,不下「負載」的結論 —— 只記數字。

## 2026-08-30(W14)README 校對:一個人眼讀不出來的連結

**現象** 用腳本抽 README 所有 `[文字](目標)`、逐個檢查目標存在 —— 回報一個
MISSING,目標是 `5 次獨立 run`。

**根因** Fig 4 那段原文是 `**中位數 5.081 s [5.010, 5.155](5 次獨立 run)**`:
方括號緊接小括號,對 Markdown 就是連結語法。GitHub 會把 `5.010, 5.155`
渲染成指向 `5 次獨立 run` 的壞連結。讀 `.md` 原文的人看了幾十次都沒發現,
因為**原文讀起來是對的**。

**教訓** 校對「別人會看到什麼」要用別人的渲染器,不是讀原文;能寫成腳本的
檢查就寫成腳本 —— 這支 link 檢查暫時留在本機 scratch,下次再抓到同類問題
就進 `tools/`。修法:方括號與小括號之間用全形括號斷開。

## 2026-08-31(W14)93469 十七分鐘內 +1、+1、−1:卡的不是技術,是 27 天前寄出的 ICLA

**現象** Gerrit 通知:93469 在同一個下午先後收到 owner George Keishing
**+1**(08:48Z)、reviewer Sridevi Ramesh **+1**(08:50Z),十七分鐘後 owner
改投 **−1**(09:05Z)。8/13 那個 −1 之後,這條線已經 18 天沒動靜。

**假設** ① 技術異議重開(他不接受「刪行」,要 PS2);② 行政閘門
(CLA / CI 白名單);③ 別人先修了同一行,change 失去意義。

**先驗哪個、為什麼** 先讀 −1 旁邊的留言 —— 零成本,而且三個假設在留言裡
各有不同的字眼。結果:① 不成立 —— 他在技術 thread 回「sure got it..」,
+1 在前、留言在後,「刪行」被接受;③ 不成立 —— `reverify_upstream.sh` #5
今天仍印出第 13 行那個 include;② 成立:他貼出 CLA 清單資料夾,寫
「Verified No votes → 你不在 approved list,請找公司的 CLA manager」。
Verified 欄沒票是因為 Jenkins 從來沒跑(8/13 那句 `User not approved,
see admin, no CI`),他拿這個反推 CLA 沒入列 —— 推得對。

**根因** ICLA 8/4 寄 `manager@lfprojects.org`,至今 27 天無回音;清單資料夾的
`individuals` 子目錄確認無本名;寄件備份有附件、無退信、無 LF 來信 —— 所以是
LF 端沒處理(或漏了),不是沒寄。**但真正的根因在我這邊:** 8/13 就寫下
「對外依賴要自帶 timer」並擬好催件兩步(Discord 問 CC 名單 → forward 原信),
然後 18 天一步都沒執行 —— timer 寫在 LOG 與草稿裡,沒有放在任何一個每天會跑、
會跳出來的地方;`reverify_upstream.sh` #7 每天看 Gerrit,看不到「ICLA 已寄
N 天」這個數字。

**處理(同日)** ① Gerrit(09:38Z):回覆 owner —— 個人貢獻者走 ICLA、8/4
已寄、資料夾查無、今日追件;技術 thread 回「維持刪行」並標 Resolved;不投票。
② forward 8/4 原信給 LF(主旨與附件不動,讓對方搜信箱落在同一串)。③ Discord
回 Milton 8/13 那則,先自報 Gerrit 本名(Discord 顯示名不是本名,對方無從
對照),再問 CC 名單。下次追蹤點 2026-09-04。

**教訓** 沒有放在每天會看的地方的 timer,就不是 timer。「對外依賴自帶 timer」
寫在日誌裡是一句話,寫進每天跑的腳本裡才是機制 —— 待辦:`reverify_upstream.sh`
加一行印「ICLA 寄出至今 N 天、上次追件日」,超過一週標 OVERDUE。另一個切面:
**技術上收斂與流程上放行是兩件事**,狀態要分開講 —— 「兩位 reviewer +1、owner
因 CLA −1、未合併、CI 未跑」四個都要說,少說一個就是灌水。

## 2026-08-31(W14)把每個帶來源的句子對回來源:一次通盤重讀抓到 docs 三處錯

**現象** 用 repo 外的工具把 `docs/` 裡每一句「帶數字、帶來源」的話逐條對回
它宣稱的來源(設定檔、測試檔、原始輸出),回報三處「句子與來源不符」:
① `measurement.md:486`「PWM 下限 30%(3000 RPM ÷ 150)」—— 3000 ÷ 150 = 20;
② `cascade.md:190` 引用的守門測試名 `test_inner_fan_pid_is_left_untuned_on_purpose`
在 `test/python/test_swampd_config.py` 裡不存在;③ `verification-log.md` 環境重跑
第 3 列寫「Sensors collection 含 `temperature_die0`」。

**假設(各自)** ① 數字錯(下限其實 20%)/ 推導錯(30% 另有來源);
② 測試被刪 / 測試改名;③ 原始輸出真的有列 / 我把「資源抓得到」寫成「集合有列」。

**先驗哪個、為什麼** 三題都先開**產生那句話的 artifact**,不開文件:
① 開 `config.baseline.json` —— fan0 PID `outLim_min = 30.0`(%PWM),
`config/swampd/README.md:222` 也寫 `255 × 0.30 = 76` 實測印證 → **數字對、括號裡的
推導錯**:30% 來自內圈的 `outLim_min`;3000 RPM 是外圈 setpoint 下限,經前饋 1/150
只對應 20%,被內圈箝位蓋過。② `grep '^def test_'` —— 第 177 行叫
`test_inner_fan_pid_is_feedforward_only_by_design`,是改名不是刪除。③ 開
`demo_rerun.out` —— 列 `Bletchley_Front_Panel_Board/Sensors` 成員那一步**一行都沒印**
(集合為空);`temperature_die0` 是第 4b 步用資源路徑直接 GET 到的。三處都是**文件
漂離了它描述的 artifact**,不是 artifact 錯。

**根因** 三種漂移各有一個共同點:句子裡有一個「可以被機器對回去」的東西
(算式、測試名、原始輸出的某一行),但寫的時候是用腦子想的,不是對著 artifact 抄的。
① 是把「結果 30%」與「順手想到的一個算式」黏在一起;② 是改測試名時沒 grep docs;
③ 是 8/30 我看到 4b 的 Redfish 讀值成功,就往回寫「集合含它」。

**處理** ① 改推導、註明更正;② 改名;③ 帶日期區塊不改原文,格內加指標、表下加
2026-08-31 更正註。LOG 計數 → 96。

**教訓** 「散文裡的數字只有兩種活法」(08-16)要再加一條:**散文裡的算式、測試名、
「輸出裡有 X」也一樣** —— 要嘛能被腳本對回 artifact,要嘛標成人工判斷。可腳本化的
兩個:docs 裡出現的 `test_xxx` 名稱是否存在於 `test/`;帶「÷」「×」的算式是否算得出
右邊的數 —— 先記在這裡,下次再抓到同類問題就進 `tools/`。
