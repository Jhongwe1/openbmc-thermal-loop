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
| 推一次 `%private,wip` change 驗證流程 | 待驗證 | — | 預計 W2 D3;驗證後立即 Abandon |
| `run-unit-test-docker.sh` 對目標 repo 綠燈 | 未開始 | — | 預計 W8 |
| 至少一筆 change 已推上 Gerrit | 未開始 | — | 預計 W8 |
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
去預填 Full name,結果被填成 `wei`。**不一致的話 Gerrit 會在 push 時擋下來**,
而這個錯誤要到第一次送 patch 才會爆。驗證方式是 `ssh openbmc.gerrit` ——
歡迎訊息會直接把 Gerrit 認定的名字念出來(`Hi <Full name>`)。

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

## 1. (尚未提交任何 change)
