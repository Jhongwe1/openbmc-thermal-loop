# Upstream contributions

本檔記錄本專案對 OpenBMC 上游的貢獻前置作業與實際提交紀錄。
證據層級 T0(第三方公證)的所有材料都收在這裡。

## 前置作業

| 項目 | 狀態 | 完成日期 | 備註 |
|---|---|---|---|
| Individual CLA v1.0 簽署並寄至 `manager@lfprojects.org` | **已核准 —— 2026-09-02 12:33Z 帳號進 CI approved list**;release maintainer 同時以 email 確認「uploaded your ICLA and added you to the approved CI list」(見往返 5) | 2026-09-02 | 簽名 `Chung-Wei Lan`;8/4 寄出;人工審核,【判】數天到數週。**至 2026-08-31 無回音(27 天)**;2026-08-31 owner 人工核 CLA 資料夾找不到本名 → 93469 改投 −1;同日 forward 8/4 原信給 LF、Discord 追 CC 名單(見〈候選 3〉往返 3)。**2026-09-01:改走 maintainer 直審通道** —— release maintainer 於 93469 指路(讀 [93905](https://gerrit.openbmc.org/c/openbmc/docs/+/93905) 後若仍符資格,ICLA 直寄他本人並附可查證背景),同日已寄(8/4 原件、CC 學校信箱、附 GitHub/Gerrit/本 repo 為查證管道)並在 93469 回覆確認(見往返 4);LF 線擱置,**下次追蹤點 2026-09-08**(`CONTRIBUTING.md`:合理等待 "on the order of a week")。(8/13 Discord 上已獲「可 CC 社群成員推一把」的指引,8/31 才開始執行 —— 見 LOG 2026-08-31) |
| OpenBMC Discord 加入 | **已加入** | 2026-08-04 | 潛水期兩週,期間不發言 |
| Gerrit 帳號建立(GitHub OAuth 登入) | **已完成** | 2026-08-04 | username `Jhongwe1` |
| Gerrit Profile Full name 設為本名 | **已完成** | 2026-08-04 | 初始被 GitHub 資料帶成 `wei`,已改為 `Chung-Wei Lan` |
| SSH 金鑰(ed25519)產生並註冊到 Gerrit | **已完成** | 2026-08-04 | fingerprint `SHA256:+vMt3DBvhBz+bm/QKIJiV79IXnxZJQHhY4S4TKcyDL0` |
| `~/.ssh/config` 設定 `openbmc.gerrit` | **已完成** | 2026-08-04 | Port 29418;`ssh openbmc.gerrit` 回 `Hi Chung-Wei Lan` |
| 三個 repo clone ＋ `commit-msg` hook 安裝 | **已完成** | 2026-08-04 | hook 來自 Gerrit 3.11.7;三個 repo 預設分支皆為 `master` |
| 推一次 `%private,wip` change 驗證流程 | **已完成** | 2026-08-05 | change [93169](https://gerrit.openbmc.org/c/openbmc/openbmc-test-automation/+/93169),3 個 patchset(含一組單一變因 A/B),驗完立即 Abandon |
| 目標 repo 的本地檢查綠燈 | **已完成** | 2026-08-11 | `docs` 無單元測試;以 repo 的 `.prettierrc.yaml` 跑 prettier(綠) |
| 推送流程完整走通(hook、refs/for、reviewer) | **已完成** | 2026-08-11 | change [93397](https://gerrit.openbmc.org/c/openbmc/docs/+/93397) —— 推出後**我決定收回(Abandoned)**,過程見下方紀錄。★ 2026-08-13 查證:此 change 帶 `private` 旗標,**匿名不可見**(REST 回 Not found,ssh authed 查得到)——決策:維持 private;此連結僅本人登入可見,對外敘事以本檔文字為準 |
| 至少一筆 change 掛在 Gerrit 上(open) | **已完成 ×2** | 2026-08-13 | [93469](https://gerrit.openbmc.org/c/openbmc/openbmc-test-automation/+/93469)(QEMU_CI 死 include)+ [93470](https://gerrit.openbmc.org/c/openbmc/phosphor-pid-control/+/93470)(configure.md 七欄)。CI 白名單 **2026-09-02 隨 ICLA 核准一併生效**(不需另外請核;原本的想法是 **順序刻意反轉**:先推、拿著 change URL 去 Discord 請核,比抽象請核更好開口)。顯示名 `wei` 經 ssh 查證(`gerrit query` 回 owner.name = `Chung-Wei Lan`)確認**不需修** —— W9 的這條待辦其實不存在 |
| 至少收到一次 reviewer 回覆 | **已完成** | 2026-08-13 | 93469 收到 owner George Keishing 的 **−1** 與 inline comment(要求改指新 tag 而非刪行)。實測他的改法後以量測數據回覆,兩次往返全文見下方〈候選 3〉 |
| 至少一位 reviewer 投 +1 | **已完成** | 2026-08-31 | 93469:owner George Keishing **+1**(08:48Z),reviewer Sridevi Ramesh **+1**(08:50Z);owner 隨後在技術 thread 回「sure got it..」(「刪行」被接受,不需 PS2),再因 ICLA 未入列改投 **−1**(09:05Z,「Verified No votes → 不在 approved list」)—— **行政閘門,不是技術異議**。**2026-09-02:帳號核准 → CI 首跑失敗(commit message 英式 `behaviour` 被 codespell 擋)→ PS2 只改一字 → Verified +1;兩張 Code-Review 票被複製到 PS2(含 owner 的 CLA −1),等 owner 改票。** 未合併。往返見〈候選 3〉往返 5 |

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
> 這兩個理由不能混:混了之後,遇到 `invalid committer` 會跑去改名字,
> 改半天還是推不上去。

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

## 已提交的 change(索引;本表更新於 2026-09-01,權威來源是 Gerrit —— `tools/reverify_upstream.sh` 第 7 項會印出現況)

| Change | Repo | 提交日 | 內容一句話 | 狀態 |
|---|---|---|---|---|
| [93469](https://gerrit.openbmc.org/c/openbmc/openbmc-test-automation/+/93469) | `openbmc-test-automation` | 2026-08-13 | `QEMU_CI` 清單刪除一行掛了四年的死 include | **Open**(PS2)。8/13 owner George Keishing −1(要求改指新 tag)→ 我方兩輪帶量測回覆(8/13、8/14)。**2026-08-31:owner +1、reviewer Sridevi Ramesh +1,owner 在技術 thread 回「sure got it..」(「刪行」被接受,不推 PS2);同日 owner 因 ICLA 未入列改投 −1(行政閘門,非技術)。** 我方同日回覆(ICLA 8/4 已寄、正在追件)並把技術 thread 標 Resolved。**2026-08-31 15:55Z:release maintainer 指路 ICLA 直審通道(93905);2026-09-01 已直寄並在 change 回覆 —— 見〈候選 3〉往返 4。** **2026-09-02:CLA 核准;CI 首跑因 commit message 拼字 −1 → PS2(只改一字)Verified +1;等 owner 改掉複製到 PS2 的 CLA −1 —— 往返 5。** 死 include 仍在 master 第 13 行 |
| [93470](https://gerrit.openbmc.org/c/openbmc/phosphor-pid-control/+/93470) | `phosphor-pid-control` | 2026-08-13 | `configure.md` 補七個未文件化欄位 | **Open**(PS4)。**2026-09-02 CI Verified +1**(帳號核准後首跑,Jenkins 147271);尚無人工回覆(reviewer Ed Tanous、Patrick Williams 在列)。**2026-08-30 查核:master 的 `configure.md` 七欄仍 0 次、釘點後 0 commit**,前提未變 |
| [93397](https://gerrit.openbmc.org/c/openbmc/docs/+/93397) | `docs` | 2026-08-11 | `gerrit-setup.md` 三個缺口 | **Abandoned(我自己收回)**,完整過程與收回理由見文末 —— 帶 `private` 旗標,僅本人登入可見 |

兩筆 open change 的 CI 皆為 `User not approved`:新貢獻者要先請管理員
加入 CI 白名單,而白名單卡在 CLA 人工處理(2026-08-04 寄出,至
2026-08-31 無回音 —— 見 LOG 2026-08-13「對外依賴要自帶 timer」與
LOG 2026-08-31「沒放在每天會看的地方的 timer 不是 timer」;8/31 已
forward 原信追件;**2026-09-01 起改走 maintainer 直審通道,見〈候選
3〉往返 4 與 LOG 2026-09-01,下次追蹤點 2026-09-08**)。

93469 的完整往返紀錄在下方〈候選 3〉,93470 在〈候選 2〉——
兩段保留在候選清單原位,因為本 repo 其他文件以「候選 N」為錨點引用它們。

## 候選清單(候選 2、3 已提交,見上表;1、4 未提交)

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
- **狀態(2026-08-18 更新):** 尚未徵詢。W10 的提交給了證據更硬的
  候選 2、3;本條的現行行為已由 `test/test_parity_upstream.cpp` 釘住,
  不會因為等待而流失。徵詢排在 93470 的往返收斂之後 —— 它與 93470
  是同一個 repo、同兩位 owner(Ed Tanous / Patrick Williams),
  同時開兩條提問線對雙方都不利。

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

- **狀態:** ★★ **已推:change [93470](https://gerrit.openbmc.org/c/openbmc/phosphor-pid-control/+/93470)(2026-08-13,reviewer = OWNERS 兩位)。**
  推送當日第三次查證:七欄在 tip 的 configure.md **不分大小寫**皆 0 次;
  Gerrit open/merged 皆無人先占。★ 查證抓到一根刺:merged 清單裡 47606
  (「UNA sensors」,2022-01)動過 configure.md —— 細看它文件化的是
  sensor 層的 `unavailableAsFailed`(存在但自報 unavailable),與
  controller 層的 `missingIsAcceptable`(整顆缺席)是兩個機制;
  這個區分直接寫進了 patch 的 margin 表(reviewer 最可能問的問題,
  先答在文件裡)。上游官方 docker CI 當日在本機跑了三次:
  ① 3 秒死於 `sh` 模組缺失;② boost 中繼映像建置 flake;
  ③ **跑通到 format-code,而它改了 configure.md** —— 我在 ② 之後
  寫下的判斷「該 pipeline 對 .md 沒有任何檢查(repo 僅
  `.clang-format`)」被第三次執行**推翻**:format-code 的 prettier
  全域檢查會重排 markdown 表格(新增的長列撐寬欄位,整張表重新
  padding,40+/40−、內容零變)。已以 **patchset 2** 推上格式化後的
  版本;第四次執行又抓到 `commit_spelling`(codespell):
  `behaviour ==> behavior`(訊息 ×2 + 檔內 ×1,英式拼寫)——
  修正後 **patchset 3**(amend 時以 `git log --format=%B` 保留
  Change-Id);第五輪 codespell 綠、換 markdownlint MD060(手改一個
  字母沒重排表格,pipe 對不齊),prettier 同輪修好 → **patchset 4**。
  錯誤判斷與整串 patchset 都保留不塗銷,理由見 LOG 2026-08-13
  (「會不會碰到我的變更」是實證問題,不是推理問題;檢查表的每一項
  都要真的執行,而且要執行到綠為止)。第六輪本機 format 階段
  **全綠**(codespell/markdownlint/prettier —— 會碰到 .md 的檢查
  全數通過),build 階段死於 OOM(與 66 案 mutation 併發,cc1plus
  被殺);同刻本 repo CI 的 `upstream-build`(pristine master、
  乾淨 runner、同一支腳本)**端到端綠** —— pipeline 的權威證據
  以該 run 為準。

### 候選 3:`test_lists/QEMU_CI` 的死 include(2026-08-12 發現)

- **觀察:** 清單裡 `--include Verify_Update_Service_Enabled`,但這個 tag
  在整個 repo 已不存在 —— `5236ec54`(2022-01-31)把該測試的 tag 改名為
  `Verify_Redfish_Update_Service_Enabled`,而清單這一行是 2022-04-28
  (`e4d77d2a8`)寫入的:**寫入當天起就引用著一個已改名的 tag。**
- **證據:** 兩輪 QEMU_CI 實跑(2026-08-12,見 `docs/robot/`)都只執行
  19 個測試(清單有 20 個生效 include);`git log -S` + `git blame` 考古
  如上;修正後單獨實跑該 tag 驗證它在 QEMU 上的行為(結果見
  `docs/robot-qemu-ci.md`)。
- **修法:** 一行 —— **刪掉那行 include**。不是改指新 tag:改名後的測試
  隸屬 firmware-inventory suite,其 Test Setup 走 boot-test 框架的
  `Redfish Power Off`,需要 host 電源堆疊,BMC-only 的 QEMU 天生沒有
  (探針 `docs/robot/20260812_renamed_tag_probe/`;詳見
  `docs/robot-qemu-ci.md` 觀察 3)。
  ⚠️ 2026-08-13 稽核:本行原寫「把 include 改成現行 tag」——那是探針
  **之前**的舊結論,與 robot-qemu-ci.md 自相矛盾;W9 收工時漏改,今修正。
  另:上游 `HW_CI`/`HW_CI_DEV` 也有同一行死 include,patch 刻意不動它們
  (硬體上該 suite 可能跑得動,正確修法可能是改指新 tag,無硬體無法驗證
  —— 這個範圍取捨寫進了 commit message)。
- **【判】三個候選裡最小、證據最硬,適合當 `openbmc-test-automation`
  的第一筆。** 2026-08-13 已推(白名單刻意後補 —— 帶 URL 請核),
  commit message 引用 5236ec54。
- **狀態:** ★★ **已推:change [93469](https://gerrit.openbmc.org/c/openbmc/openbmc-test-automation/+/93469)(2026-08-13,reviewer = OWNERS 的 gkeishin)。**
  推送當日重驗:死行仍在 tip(`QEMU_CI:13`)、舊 tag 全 repo 0 個 .robot
  引用、Gerrit 無人先占;`HW_CI`/`HW_CI_DEV` 的同病行**刻意不動**
  (真硬體上該 suite 可能跑得動,正確修法可能是改指新 tag,無硬體無法
  驗證 —— 範圍取捨寫進 commit message)。
- **往返 1(2026-08-13):** George Keishing 投 **−1**,inline comment
  要求改成**重指新 tag**(「please update with this commit」)。處理:
  先審自己 —— 發現 commit message 第二段「a BMC-only QEMU target」是把
  bletchley 單平台量測寫成全稱命題(外推);再 fresh boot 重跑探針:
  **FAIL 復現**,且 console 流把根因釘到具體呼叫 ——
  `Auto_reboot/cp_setup` plug-in PATCH `/redfish/v1/Systems/system`
  (AutomaticRetryConfig)→ HTTP 500×3 → `Plug-in setup failed`
  (證據:`docs/robot/20260813_renamed_tag_probe_rerun/`,含
  console.log.gz;機制詳見 `docs/robot-qemu-ci.md` 觀察 3)。
  回覆(已發)= 證據 + 明說「bletchley 是我唯一能測的 target」+
  問「CI 跑這份清單用哪台 QEMU」。兩種答案都有既定下一步:
  跑得動 → 照改重指(同 commit `--amend` 推 PS2);跑不動 →
  維持刪行。comment 留 unresolved、未投票,等他回。
- **往返 2(2026-08-14):** 貼出根因補充(messages 第 5 則,已查核
  送出)。內容 = 8/13 深夜紅隊把 500 從「症狀」釘到「地址」:
  ① 純 curl(無 Robot)復現 500 ×2;② bmcweb journal 承認
  D-Bus 寫入失敗(`Invalid request descriptor`);③ Settings 樹
  只有 host1~host6、**無 host0**,對 host1 同寫入成功(rc 0)——
  機制無罪,地址不存在;④ bmcweb `systems.hpp` 單主機路由
  string-build host<index>、index 恆 0。bletchley 一殼六主機 →
  **任何 stock bletchley 都會在此 suite 的 Test Setup 掛掉,與本地
  環境無關**。先排除的三重嫌疑(基底落後 2 commits 但 mergeable、
  CLA 只擋 Jenkins/merge 不擋 review、WSL 偽造不出格式完好的
  Redfish 500)也留檔。證據包:
  `docs/robot/20260813_curl500_dbus_probe/`(commit `313aded`);
  LOG 2026-08-13 紅隊一則。CI target 的問題維持開放,球在 George。
- **往返 3(2026-08-31):** owner 投 **+1**(08:48Z),reviewer Sridevi Ramesh
  **+1**(08:50Z);owner 在技術 thread 回「sure got it..」—— 「刪行」被接受,
  不推 PS2。同日 owner 貼出 CLA 清單資料夾、找不到本名,改投 **−1**(09:05Z,
  「Verified No votes → 不在 approved list,請找公司的 CLA manager」)。這個
  −1 與 8/13 的 −1 性質不同:**行政閘門,不是技術異議**。處理(同日):
  ① Gerrit 回覆(09:38Z)—— 個人貢獻者走 ICLA、8/4 已寄 `manager@lfprojects.org`、
  資料夾的 `individuals` 子目錄確認無本名、今日 forward 追件;技術 thread
  回一句「維持刪行」並標 Resolved;不投票。② forward 8/4 原信給 LF(主旨
  不改、附件原封,讓對方搜信箱落在同一串)。③ Discord 回 Milton 8/13 那則,
  先自報 Gerrit 本名(Discord 顯示名不是本名,對方無從對照)再問 CC 名單。
  (原定 9/4 用 CC 名單寄第二封 —— 已被往返 4 的 maintainer 直審通道取代。)
  **正確的狀態描述(至 9/1 止;9/2 起見往返 5):兩位 reviewer +1、owner 因 CLA −1、未合併、CI 未跑。**
  記錄:LOG 2026-08-31;API 原文見 `docs/verification-log.md`〈2026-08-31〉。
- **往返 4(2026-08-31 15:55Z → 2026-09-01):** release maintainer Andrew
  Geissler(docs change [93905](https://gerrit.openbmc.org/c/openbmc/docs/+/93905)
  的 owner)在 93469 直接留言:ICLA 受理正在收緊(93905 把 CCLA 對受僱於
  晶片/韌體/伺服器廠與 CSP 者改為**必要**;ICLA 保留給不屬於這些類別的
  個人),讀後若仍符資格,可將 ICLA 直寄其信箱審核,需附「盡可能多的
  背景與可查證方式(I will need mechanisms to verify you)」。我方讀
  93905 全文後判定 ICLA 仍適用(無雇主個人),2026-09-01 寄出:8/4
  簽署的原件(不重簽,保留時間戳)、與 Gerrit/ICLA 相同的寄件信箱、
  CC 學校信箱(第三方核發)、以 GitHub / Gerrit 兩筆 change / 本 repo
  為查證管道,並主動聲明未來若受僱於 93905 所列類別公司,屆時改走該
  雇主的 CCLA。同日在 93469 回覆確認(18:25Z,messages=14)。
  **下次追蹤點 2026-09-08**(`CONTRIBUTING.md`:"on the order of a
  week")。記錄:LOG 2026-09-01。
- **往返 5(2026-09-02):** 12:33:25Z Gerrit CI 在 93469 與 93470 同秒留言
  `User approved, CI ok to start` —— 帳號進 approved list(距 9/1 直寄
  約一天)。同時 12:34Z 收到 Andrew Geissler 的 email(回在 9/1 那串,
  CC 一位 Patrick):「Thanks for the detailed info. I've uploaded your
  ICLA and added you to the approved CI list.」—— 核准者與時間都對上。93470 首跑 **Verified +1**
  (Jenkins 147271);93469 首跑 **Verified −1**(Jenkins 147270):
  `openbmc-build-scripts/scripts/format-code.sh` 的 `commit_spelling` 對
  commit message 跑 codespell `--builtin clear,rare,en-GB_to_en-US`,
  第 25 行的英式 `behaviour` 被判錯;檔案層 linter 全 unchanged。這條
  「commit message 一律美式英語」的規則,test-automation 的 `CONTRIBUTING.md`、
  它的 `docs/code_standards_check.md`、`openbmc/docs` 的 `CONTRIBUTING.md`
  都沒寫,只存在於 CI 腳本。本機以同版 codespell 2.4.3 重現後,14:04Z 推
  **PS2**(只改一字,Change-Id 不變;Gerrit 標 `NO_CODE_CHANGE`),14:05Z
  **Verified +1**(Jenkins 147287);兩張 Code-Review 票**被複製到 PS2**
  (OpenBMC 的 copy condition 含 NO_CODE_CHANGE),owner 的 CLA −1 因此
  還掛著。14:17Z 我方回覆(messages=22):PS2 只改訊息、diff 與 PS1 相同、
  CI 綠,請 owner 重看。**現在的狀態描述:CLA 已核准、CI 綠(PS2)、一位
  reviewer +1、owner 的 CLA −1 待其本人改票、未合併。** 一週內不催。
  記錄:LOG 2026-09-02;`docs/verification-log.md`〈2026-09-02〉。

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
- **狀態(2026-08-18 更新):** 已起草;Discord 徵詢未發。排序理由同
  候選 1:它與 93469 是同一個 repo、同一位 owner(George Keishing),
  93469 的往返還開著,先把一條線走完。

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
