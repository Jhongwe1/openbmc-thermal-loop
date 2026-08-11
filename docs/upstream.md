# Upstream contributions

本檔記錄本專案對 OpenBMC 上游的貢獻前置作業與實際提交紀錄。
證據層級 T0(第三方公證)的所有材料都收在這裡。

## 前置作業

| 項目 | 狀態 | 完成日期 | 備註 |
|---|---|---|---|
| Individual CLA v1.0 簽署並寄至 `manager@lfprojects.org` | **已寄出** | 2026-08-04 | 簽名 `Chung-Wei Lan`;等待人工審核,【判】數天到數週 |
| OpenBMC Discord 加入 | **已加入** | 2026-08-04 | 潛水期兩週,期間不發言 |
| Gerrit 帳號建立(GitHub OAuth 登入) | **已完成** | 2026-08-04 | username `Jhongwe1` |
| Gerrit Profile Full name 設為本名 | **已完成** | 2026-08-04 | 初始被 GitHub 資料帶成 `wei`,已改為 `Chung-Wei Lan` |
| SSH 金鑰(ed25519)產生並註冊到 Gerrit | **已完成** | 2026-08-04 | fingerprint `SHA256:+vMt3DBvhBz+bm/QKIJiV79IXnxZJQHhY4S4TKcyDL0` |
| `~/.ssh/config` 設定 `openbmc.gerrit` | **已完成** | 2026-08-04 | Port 29418;`ssh openbmc.gerrit` 回 `Hi Chung-Wei Lan` |
| 三個 repo clone ＋ `commit-msg` hook 安裝 | **已完成** | 2026-08-04 | hook 來自 Gerrit 3.11.7;三個 repo 預設分支皆為 `master` |
| 推一次 `%private,wip` change 驗證流程 | **已完成** | 2026-08-05 | change [93169](https://gerrit.openbmc.org/c/openbmc/openbmc-test-automation/+/93169),3 個 patchset(含一組單一變因 A/B),驗完立即 Abandon |
| 目標 repo 的本地檢查綠燈 | **已完成** | 2026-08-11 | `docs` 無單元測試;以 repo 的 `.prettierrc.yaml` 跑 prettier(綠) |
| 推送流程完整走通(hook、refs/for、reviewer) | **已完成** | 2026-08-11 | change [93397](https://gerrit.openbmc.org/c/openbmc/docs/+/93397) —— 推出後**我決定收回(Abandoned)**,過程見下方紀錄 |
| 至少一筆 change 掛在 Gerrit 上(open) | **重新歸零** | — | 預計 **W10**(`phosphor-pid-control`);⚠️ 前置:CI 白名單(Discord 找管理員)、網頁顯示名 `wei` 要修 |
| 至少收到一次 reviewer 回覆 | 未開始 | — | 預計 W10~W11 |

> 上表的日期欄一律等該項**實際完成後**才填。
> 理由:本專案〈誠實準則〉第 1 條 ——「沒做到的不要寫」。
> 這份檔案是 T0 證據的索引,只要有一格是假的,整份的可信度就沒了。

## 身分一致性(★ 四處必須相同)

| 在哪 | 值 | 狀態 |
|---|---|---|
| CLA 上的簽名 | `Chung-Wei Lan` | ✅ |
| git `user.name` | `Chung-Wei Lan` | ✅ |
| commit 的 `Signed-off-by:` | `Chung-Wei Lan <zwwe1f@gmail.com>` | ✅ |
| Gerrit → Profile → Full name | `Chung-Wei Lan` | ✅(2026-08-04 修正) |

**踩到的坑:** 用 GitHub 帳號登入 Gerrit 時,Gerrit 會拿 GitHub 個人檔案的 Name
去預填 Full name,結果被填成 `wei`。驗證方式是 `ssh openbmc.gerrit` ——
歡迎訊息會直接把 Gerrit 認定的名字念出來(`Hi <Full name>`)。

> ⚠️ **2026-08-05 更正:** 這裡原本寫「不一致的話 Gerrit 會在 push 時擋下來」。
> **那句話是錯的,而且是從二手計畫抄來、沒有實測的。**
> D3 用同一個 Change-Id 做了單一變因 A/B(見 `LOG.md` 2026-08-05):
>
> | 變因 | 結果 |
> |---|---|
> | `Signed-off-by` 的**名字**與 Profile Full name 不一致(`wei`) | **✅ Gerrit 收下** |
> | **committer email** 不在帳號註冊清單裡 | **❌ 拒絕:`invalid committer`** |
>
> **Gerrit 驗的是 email,不是名字。** 名字四處一致仍然要做,
> 但理由是**證據價值**(主管要在 Gerrit 上看到本名),不是技術上會被擋。
> 這兩個理由不能混,面試講錯會被追問到答不出來。

## 【查】2026-08-04 親自確認的上游原文

來源:<https://github.com/openbmc/docs/blob/master/CONTRIBUTING.md>
      <https://github.com/openbmc/docs/blob/master/development/gerrit-setup.md>

- Individual CLA:<https://drive.google.com/file/d/1k3fc7JPgzKdItEfyIoLxMCVbPUhTwooY>
- *"After signing a CLA, send it to `manager@lfprojects.org`."*
- **CLA 不是在 Gerrit 的 Settings → Agreements 裡簽。** 在那裡按同意,對方不會收到任何東西。
- **Gerrit 用 GitHub 帳號登入**,並提供 `plugins/github-plugin/static/account.html` 帶入資料。
- `Signed-off-by` 要用全名(given name 與 family name 都要)。
- commit message:主旨 ≤ 50 字元且要含元件名;正文每行 ≤ 72 字元;
  **`Tested:` 欄位為必填**。連結不受行長限制。
- 新功能送 Gerrit 前:*"introduce the change via the OpenBMC Discord server or
  email list to start the discussion."*

## CLA 與 DCO:兩件事,兩個都要

| | CLA | DCO |
|---|---|---|
| 全稱 | Contributor License Agreement | Developer Certificate of Origin |
| 回答的問題 | 專案有沒有權利**散布**你的程式碼(授權) | 你有沒有權利**提交**這份程式碼(來源) |
| 做幾次 | **一次性** | **每個 commit** |
| 怎麼做 | 簽 PDF 寄 `manager@lfprojects.org` | `git commit -s` 加 `Signed-off-by:` |
| 誰檢查 | **人工**,要等 | **Gerrit 自動擋** |

## 溝通管道

| 管道 | 位址 |
|---|---|
| Discord | <https://discord.gg/69Km47zH98> |
| Mailing list | `openbmc@lists.ozlabs.org`(<https://lists.ozlabs.org/listinfo/openbmc>) |

上游對回應時間的明文期待:patch 沒人看可以 email 維護者或在 Discord ping,
**但合理的時間尺度是「一週」,不是「幾小時」**。

## 目標 repo 投資組合(【查】2026-08-04 親自讀 OWNERS)

同時佈局三個回應性不同的 repo,把「至少收到一次 review」的機率最大化。

| 優先 | Repo | owners | reviewers | 候選改動 | 【判】回應速度 |
|:--:|---|---|---|---|---|
| **1** | `openbmc-test-automation` | George Keishing | **2 位**(Sridevi Ramesh / IBM、Nandakumar Babu / AMI) | `test_lists/QEMU_CI` 沒有熱控／感測器案例;或補 QEMU 前置條件文件 | 最快 |
| **2** | `docs` | **Patrick Williams** | **3 位**(Andrew Jeffery、Gunnar Mills、Lei Yu)＋ 依路徑分流的 matchers | 照 `development/dev-environment.md`、`gerrit-setup.md` 做時沒跑通的步驟 | 快 |
| **3** | `phosphor-pid-control` | **Ed Tanous、Patrick Williams** | **空** | `configure.md` 補齊 7 個未文件化欄位;`ec::pid()` 的 slew ＋ 前饋回算單元測試 | 慢 |

### 讀完 OWNERS 之後修正的判斷

1. **`phosphor-pid-control` 的 `reviewers` 是空的** —— 計畫的說法成立。
   沒有第二層可以先幫你看,而兩位 owner 是 OpenBMC 最頂層也最忙的維護者。
2. **★ `docs` 與 `phosphor-pid-control` 的 owner 是同一個人:Patrick Williams。**
   所以「先推 `docs`」的價值不只是「在低門檻的 repo 上把格式錯誤犯完」,
   而是**在同一位守門人面前先建立一次良性往返紀錄**,再去推他守的那個難的。
   這是計畫沒有指出的一層。
3. **`docs` 的 reviewer 名單最厚(3 位)且有 path-based matchers**,
   代表它有成熟的分流機制 —— 對「拿到第一次 review 往返」的目標最有利。

**執行順序:W8 先推 1 或 2,W9~W10 再推 3。**
理由:第一個 patch 一定會在格式、commit message、CI 上出問題。
**在門檻低的 repo 上把這些錯犯完**,再去碰維護者最忙的那個。

> ⚠️ **【驗】`OWNERS` 在送 patch 前要重讀一次** —— 名單會變。

---

## 未提交的候選(同樣有訊號值)

### 候選 1:`ec::pid()` 在 slew 生效時的積分回算

- **觀察**(commit `c5e59550d3`,`pid/ec/pid.cpp`):slew rate limit 那一段結束時,
  程式把積分回算成 `integralTerm = output - proportionalTerm` ——
  **沒有扣掉 `derivativeTerm` 與 `feedFwdTerm`**。
- **而且觸發條件是「`slewNeg` 或 `slewPos` 有設定」,不是「slew 真的限制住了輸出」。**
  這一點計畫的虛擬碼寫錯了,我照著寫的第一版 parity 測試直接紅,回去讀原始碼才發現。
- **影響:** `feedFwdGain != 0`(fan PID 很常見,因為 PWM→RPM 近似線性)
  且 slew 有設定時,回算出的積分會把前饋那一份吸收進去,下一輪前饋又再加一次。
- **我的驗證:** `test/test_parity_upstream.cpp` 的
  `DivergesWhenSlewAndFeedForwardCoexist`。
  參數 `slewPos=2`、`slewNeg=-3`、`ffGain=0.4`、`setpoint=65`、`outLim=[30,100]` 時:

  | 量測 | 值 |
  |---|---|
  | 第一個分岔的時間步 | **13** |
  | 輸出最大差 | **4.75**(輸出範圍寬 70,約 6.8%) |
  | 積分最大差 | **62.5** |

  同一組參數把 `ffGain` 設成 0,兩者逐步一致到 `1e-12`
  (`NoDivergenceWhenFeedForwardIsZero`)—— 這條控制組證明分歧確實來自前饋項,
  不是我實作裡的其他差異。
- **我打算怎麼做:** **先在 Discord 問,不直接送 patch。** 我不確定這是刻意的
  設計還是我理解錯。如果對方認為值得,我送的會是一個**把現行行為釘住的單元測試**
  (不改行為)—— 這符合上游「可被測試的變更要附測試」的要求,而且不管結論是
  「這是對的」還是「這要改」,測試本身都有價值。
- **狀態:** 待 W10 提問。

> ⚠️ **絕對不要說「OpenBMC 有 bug」。** 正確講法:
> 「我讀 `ec::pid()` 時注意到,slew 生效時的積分回算是 `output − proportionalTerm`,
> 沒扣前饋跟微分。我不確定是刻意還是我理解錯,所以我寫了一個單元測試把行為釘住,
> 然後推去問。」

### 候選 2:`configure.md` 沒有記錄的欄位

計畫列了 7 個(`cycleIntervalTimeMS`、`updateThermalsTimeMS`、`accumulateSetPoint`、
`derivativeCoeff`、`convertTempToMargin`、`convertMarginZero`、`missingIsAcceptable`)。
**送出前必須逐一重驗**,不能照抄 —— 上游隨時可能已經補上了。

其中 `derivativeCoeff` 這次順手確認過:程式碼支援(`pid/ec/pid.cpp` **每一輪無條件**
計算 D 項),但 `configure.md` 的 PID 範例沒有列它。

- **狀態:** ★ 2026-08-12 已逐項重驗:7 個欄位全部「程式碼有、`configure.md`
  0 次」,且上游自 `f6d4cb9`(2026-07-31)之後無新 commit —— 候選完好。
  送幾個、怎麼分批,W10 推送前決定。

### 候選 3:`test_lists/QEMU_CI` 的死 include(2026-08-12 發現)

- **觀察:** 清單裡 `--include Verify_Update_Service_Enabled`,但這個 tag
  在整個 repo 已不存在 —— `5236ec54`(2022-01-31)把該測試的 tag 改名為
  `Verify_Redfish_Update_Service_Enabled`,而清單這一行是 2022-04-28
  (`e4d77d2a8`)寫入的:**寫入當天起就引用著一個已改名的 tag。**
- **證據:** 兩輪 QEMU_CI 實跑(2026-08-12,見 `docs/robot/`)都只執行
  19 個測試(清單有 20 個生效 include);`git log -S` + `git blame` 考古
  如上;修正後單獨實跑該 tag 驗證它在 QEMU 上的行為(結果見
  `docs/robot-qemu-ci.md`)。
- **修法:** 一行 —— 把 include 改成現行 tag。
- **【判】三個候選裡最小、證據最硬,適合當 `openbmc-test-automation`
  的第一筆。** W10 推(CI 白名單核准後),commit message 引用 5236ec54。
- **狀態:** 已驗證、已起草、待推。

### 候選 4:`QEMU_CI` 補一個 ThermalSubsystem/Sensors 案例(2026-08-12 起草)

- **依據(三段論):** ① 清單 `grep -ic 'thermal\|sensor'` = 0;
  ② repo 現有兩份 sensor 套件都進不了這份清單 ——
  `test_sensor_monitoring.robot` 需要 host OS 的 SSH 與每機型的
  `redfish_sensor_info_map` 變數檔;`test_thermal_ambient_temperatures.robot`
  走的是現代 bmcweb 已不提供的舊 `/Thermal` schema(本映像 404,
  見 `docs/redfish-notes.md`);③ 現代 `ThermalSubsystem`/`Sensors`
  路徑我在 QEMU 上手動驗證過。
- **草稿:** `docs/upstream-drafts/test_thermal_subsystem.robot`
  (兩個案例;**容忍空 Sensors collection** —— stock QEMU 映像是
  0 成員,這一點不寫進去的話,案例會在官方 CI 的 pristine 映像上假紅)。
- **上游規矩:** 介於「文件修正」與「新功能」之間 → 先 Discord 徵詢,
  有共識才推(訊息已擬;發出時間與回應回填於此)。
- **狀態:** 已起草;Discord 徵詢待發。

---

## W8 patch 候選 #1:`openbmc/docs` 的 `development/gerrit-setup.md`

【查】2026-08-05 讀原文找到三個缺口。**合併成一個 patch 送**
(同一份文件、同一個主題「怎麼確認你的 Gerrit 設定是對的」= 一個邏輯變更)。

| # | 缺口 | 依據 |
|:--:|---|---|
| **A** | 有〈Add full name to Gerrit〉但只有一行「填 Full name」,**沒說要跟 `Signed-off-by` 一致**,也沒提用 GitHub 登入時 Full name 會被 GitHub profile 的 Name 預填 | 我本人被填成 `wei`,見上 |
| **B** | 〈Confirm Setup Success〉只叫你 **clone 一個 repo**,**沒提 `ssh openbmc.gerrit`** | clone 是重驗證(要下載整個 repo,失敗時分不清是 SSH、權限還是網路);`ssh openbmc.gerrit` 是輕驗證,而且歡迎訊息的 `Hi <Full name>` **一行同時驗了 SSH 通、認證過、Gerrit 認為你是誰** |
| **C** | `Ensure proper permissions **for for** your .ssh directory: chmod 600 ~/.ssh/*` —— typo,且句子說 directory 指令卻改檔案 | ssh 實際嚴格檢查的是 `~/.ssh/` 目錄 700 與私鑰 600;`.pub`/`known_hosts` 644 即可。屬**不精確**而非錯 |

**⚠️ 措辭注意:** 缺口 A 不可以寫成「不一致會被擋」——**實測不會被擋**。
正確的寫法是「Full name 會出現在你所有 change 的作者欄,建議與 `Signed-off-by`
使用相同的全名」,並補上「Gerrit 拒絕的是未註冊的 committer email」。

> ⚠️ **【驗】W8 送出前要重讀一次這份文件** —— 上游隨時可能已經改掉,
> 改掉的話這個候選作廢,要另外找。

## 1. gerrit-setup: add SSH check and name caveats

- **Gerrit: <https://gerrit.openbmc.org/c/openbmc/docs/+/93397>**
- Repo: `openbmc/docs`
- 狀態: **Abandoned(2026-08-11,我自己的決定)**
- 起因: W2 照這份文件設 Gerrit 帳號時踩到三個缺口(Full name 被 GitHub
  預填成 `wei`、確認步驟只有重量級的 clone、`for for` typo)。
  W5 的單一變因 A/B 實測釐清了「Gerrit 驗 email 不驗名字」,
  這個事實成為缺口 A 的正確措辭依據。
- 事前討論: 無 —— 文件修正,依 CONTRIBUTING 不需事先討論。
- 內容: 一個 patch 修同一份文件的三個缺口(一個邏輯變更):
  Full name 補 GitHub 預填與 Signed-off-by 一致的理由、
  Confirm Setup 先 `ssh openbmc.gerrit` 再 clone、typo 與權限指令修正。
- Reviewers: Gunnar Mills、Andrew Jeffery(從 OWNERS 挑,`gerrit
  set-reviewers` 加入);Patrick Williams(owner,系統自動)、
  OpenBMC CI(自動)。
- Review 往返:
  - Patchset 1 推出(13:30)→ 我 Set private + Abandon(13:38)→
    Restore 並留言(17:37)→ 兩次 Abandon/Restore 拉鋸 →
    **最終 Abandon(18:11)**。沒有等到人工 review。
  - 收回的理由(我的判斷,如實記錄):我認為一個 +19/−2 的文件
    patch 不足以代表我想呈現的技術水準,寧可讓第一筆掛名的 change
    是 W10 的 `phosphor-pid-control` 主線 patch。
  - 指導方的不同意見(也如實記錄):docs 的 merge 歷史顯示同尺寸
    patch 是常態;第一個 patch 的功能是把流程錯誤在便宜處犯完,
    並在同一位 owner 面前建立首次往返;abandoned 紀錄仍公開可見。
    兩個論點我都聽過之後做了決定 —— 這一段留著,因為
    「知道所有代價之後做選擇」與「不知道就選」是兩回事。
- **這次推送真實學到的三件事(只有推了才會知道):**
  1. **OpenBMC CI 對新貢獻者有白名單**:change 一推,CI 帳號回
     `User not approved, see admin, no CI` —— 第一次要請管理員核准
     才會跑 Jenkins。**W10 推 patch 前要先在 Discord 解決**,
     否則主線 patch 同樣拿不到 Verified。
  2. **Gerrit 網頁的 change log 顯示我為 `wei`**:W2 修過 Profile 的
     Full name(ssh 歡迎訊息也確認過),但網頁另有顯示名的來源 ——
     **W10 前要查清楚並修正**(身分一致性表加一列,見上方)。
  3. push → private → abandon → restore 的每一步都留在公開的
     change log 上,含時間戳。Gerrit 沒有「刪除」,只有「狀態」。

### 送出前檢查(全過才推)

| 送出前檢查 | 結果 |
|---|---|
| 重讀上游 master(當日 `git pull`) | 三個缺口 **全部還在**(A: L52-54、B: L73-79、C: L71) |
| Gerrit 搜同類 open change(`gerrit query project:openbmc/docs status:open`) | **沒有人**在改 gerrit-setup |
| OWNERS 重讀 | 沒變:owner Patrick Williams;reviewers Andrew Jeffery / Gunnar Mills / Lei Yu |
| 格式 | prettier(repo 的 `.prettierrc.yaml`)綠;diff +19/−2 全在三處改動內 |
| commit | 主旨 `gerrit-setup: add SSH check and name caveats`(45 字元)、正文每行 ≤72、`Tested:` 寫實際做過的、Change-Id `I31efbb72…`、Signed-off-by 與 Gerrit Profile 一致 |
| 措辭紅線 | 守住:寫的是「Gerrit verifies the committer e-mail …, but it does not check the name」,**沒有**寫「不一致會被擋」 |
