# Upstream contributions

本檔記錄本專案對 OpenBMC 上游的貢獻前置作業與實際提交紀錄。
證據層級 T0(第三方公證)的所有材料都收在這裡。

## 前置作業

| 項目 | 狀態 | 完成日期 | 備註 |
|---|---|---|---|
| Individual CLA 簽署並寄至 `manager@lfprojects.org` | 待寄出 | — | 簽名須為 `Chung-Wei Lan`,與 git `user.name`、Gerrit Full name 三者一致 |
| OpenBMC Discord 加入 | 待加入 | — | 邀請連結取自 `openbmc/docs` 的 README |
| Gerrit 帳號建立 | 待建立 | — | username: 待填 |
| SSH 金鑰(ed25519)產生 | 已完成 | 2026-08-04 | fingerprint `SHA256:+vMt3DBvhBz+bm/QKIJiV79IXnxZJQHhY4S4TKcyDL0` |
| `~/.ssh/config` 設定 `openbmc.gerrit` | 待設定 | — | Gerrit 的 SSH 走 **port 29418**,不是 22 |
| `commit-msg` hook 安裝(三個 repo) | 待安裝 | — | 沒有 hook = 沒有 Change-Id = Gerrit 拒收 |
| 推一次 `%private,wip` change 驗證流程 | 待驗證 | — | 驗證後立即 Abandon |

> 上表的日期欄一律等該項**實際完成後**才填。
> 理由:本專案〈誠實準則〉第 1 條 ——「沒做到的不要寫」。
> 這份檔案是 T0 證據的索引,只要有一格是假的,整份的可信度就沒了。

## CLA 與 DCO:兩件事,兩個都要

| | CLA | DCO |
|---|---|---|
| 全稱 | Contributor License Agreement | Developer Certificate of Origin |
| 是什麼 | 授權協議,處理**著作權**:你允許專案在其授權條款下散布你的程式碼 | 原創聲明,你**自我聲明**有權提交這份程式碼 |
| 做幾次 | **一次性**,簽了就好 | **每個 commit 都要** |
| 怎麼做 | 簽 PDF 寄 `manager@lfprojects.org` | commit message 加 `Signed-off-by:`(`git commit -s`) |
| 誰檢查 | 人工(Linux Foundation Projects) | Gerrit 自動擋 |

## 【查】2026-08-04 親自確認的上游原文

來源:<https://github.com/openbmc/docs/blob/master/CONTRIBUTING.md>

- Individual CLA:<https://drive.google.com/file/d/1k3fc7JPgzKdItEfyIoLxMCVbPUhTwooY>
- Corporate CLA:<https://drive.google.com/file/d/1d-2M8ng_Dl2j1odsvZ8o1QHAdHB-pNSH>
- *"After signing a CLA, send it to `manager@lfprojects.org`."*
- **CLA 不是在 Gerrit 的 Settings → Agreements 裡簽。** 在那裡按同意,對方不會收到任何東西。
- `Signed-off-by` 要用全名(given name 與 family name 都要)。
- commit message:主旨 ≤ 50 字元且要含元件名;正文每行 ≤ 72 字元;**`Tested:` 欄位為必填**。連結不受行長限制。
- 新功能送 Gerrit 前:*"introduce the change via the OpenBMC Discord server or email list to start the discussion."*

## 溝通管道(【查】同一份 CONTRIBUTING.md 與 docs README)

| 管道 | 位址 |
|---|---|
| Discord | <https://discord.gg/69Km47zH98> |
| Mailing list | `openbmc@lists.ozlabs.org`(<https://lists.ozlabs.org/listinfo/openbmc>) |

## 目標 repo 投資組合

待 D2 讀完各 repo 的 `OWNERS` 後填寫。

## 1. (尚未提交任何 change)