# 查證紀錄(verification log)

> **用途:** 本 repo 引用了一批**會過期**的上游事實 —— 映像版本、上游程式碼、
> 文件缺口、OWNERS、官方測試清單、漏洞公告、Gerrit change 的狀態。
> 這份檔案記錄「每一項最後一次被重新確認是什麼時候、怎麼確認、結果是什麼」,
> 讓讀者不必相信 README 上的任何一句「目前仍……」。
>
> **怎麼重跑:** `./tools/reverify_upstream.sh`(唯讀、需網路、約 2 分鐘;
> 不碰 `images/` 與 `subprojects/`)。下表每一格都來自那支腳本的輸出,
> 手打的只有「影響」欄的判斷。
>
> **時間軸:** 原始查證 2026-07-27(規劃時)與 2026-07-28
> (`env-baseline.md`、`platform-matrix.md`);2026-08-18 跑過一次同樣的六項但
> 沒有留檔;**本檔從 2026-08-30 起是固定紀錄**,之後每次重跑往下加一節。

## 八項核心確認(本表更新於 2026-08-30,權威來源是每列「怎麼驗」那支指令的當下輸出)

| # | 項目 | 量測時的狀態(2026-07/08) | 2026-08-30 重新確認 | 對本 repo 的影響 |
|:-:|---|---|---|---|
| 1 | `bletchley` 映像與套件清單(Jenkins `latest-master`) | `obmc-phosphor-image-bletchley-20260728025045`;`phosphor-pid-control 0.1+git0+c5e59550d3-r1` | 最新是 `…-20260829025047`;swampd → `f6d4cb9e5d`、dbus-sensors/entity-manager/bmcweb/fan-control 皆換 hash;**套件集合只差 kernel `6.18.40` → `6.18.47`(4 個套件名)**;`phosphor-ipmi-net` 仍不在 | 所有圖與 `bench/data/` 綁的是 `c5e5955` 那份映像(其 manifest 進 git)。新映像的 swampd 只多 2 個 commit(見 #2),量測結論不受影響;**要在新映像上重現**,`subprojects/phosphor-pid-control.wrap` 要跟著重釘 |
| 2 | 上游 `ec::pid()`(parity 測試與候選 1 的前提) | 釘 `c5e59550d3`(2026-07-26) | 釘點之後 master 共 **2** 個 commit:`a337b68`(dbus helper 改 lg2 logging)、`f6d4cb9`(IPMI 支援改可選);`pid/ec/pid.cpp`、`conf.hpp`、`pid/ec/logging.cpp`、`configure.md` 各 **0** 個 commit | `test/test_parity_upstream.cpp` 的 144 組比對與「slew + 前饋回算」的分歧觀察,仍對著現行程式碼 |
| 3 | `configure.md` 的七個未文件化欄位(change 93470 的前提) | 七欄各 0 次 | **七欄仍各 0 次**(不分大小寫) | 93470 仍有意義 |
| 4 | `OWNERS` | ppc:`ed@tanous.net`、`patrick@stwcx.xyz`,reviewers 空;ota:owner `gkeishin@gmail.com` + 2 reviewers | **相同**;ota reviewers = Sridevi Ramesh(IBM)、Nandakumar Babu(AMI) | 兩筆 change 的 reviewer 名單不用改 |
| 5 | `test_lists/QEMU_CI`(change 93469 與候選 4 的前提) | 20 個生效 include;`thermal\|sensor` 0 案;死 include 在第 13 行 | **相同**:20 / 0 / 第 13 行 `--include Verify_Update_Service_Enabled` 仍在 | 93469 未被別人先修;候選 4 的缺口仍在 |
| 6 | bmcweb 漏洞公告 | 規劃文件寫「2026-05 揭露四項、一項未修」 | GitHub 公開的 security advisories 只有 **2** 則:`GHSA-p3gc-68x5-g9w3`(2026-04-21,high,100-continue 未強制 payload 上限)、`GHSA-g3qc-375m-h66j`(2022-10-19,high) | ★ **規劃文件那句在公開來源查不到,本 repo 不引用它**。要講 bmcweb 安全,只講查得到的這兩則 |
| 7 | Gerrit 三筆 change | 93469 NEW/PS1/−1;93470 NEW/PS4;93397 Abandoned(private) | **相同**。93469 最後一則訊息是 2026-08-13(我方),之後 **17 天無新回覆**;93470 仍無人工 review;93397 匿名 REST 404(private,預期) | `docs/upstream.md` 狀態表照實更新日期 |
| 8 | 平台決策矩陣(`platform_matrix.sh` + QEMU machine 清單) | 19 個 target;交集 = `bletchley` + `catalina`;`anacapa-bmc` 不存在 | manifest 五欄 19 列**逐格相同**;QEMU 11.0.1 的 machine 清單相同(`anacapa-bmc` 仍無、`catalina-bmc` 仍在)。★ **第三條件改由腳本計算後,抓到一格手寫錯誤**:`gbs` 有 QEMU machine(`quanta-gbs-bmc`;其 manifest 含 `nuvoton-npcm730-gbs.dtb`),`platform-matrix.md` 原寫「QEMU 無對應 machine」不成立 —— 排除它的真正理由是**缺 `dbus-sensors` 與 `entity-manager`** | 主線 / 備援結論不變;`platform-matrix.md` 已加 2026-08-30 補註(舊文不改) |

## 有變動或被修正的項目,以及怎麼處理

1. **映像有新版(#1):不換。** 本 repo 的每一個數字都指向 `c5e5955` 那份映像的
   manifest(在 `images/bletchley/`,進 git),換映像等於換被測物,所有 L2/L3 量測
   都要重做才能宣稱。釘點之後上游只動了 logging 與 build 選項(#2),沒有動控制律,
   所以「量測結論在新映像上仍成立」是**合理預期**,不是已驗證的事實 —— 本檔不寫成事實。
2. **`gbs` 那一格(#8):** 原文件把「有 machine 但缺兩個必要 daemon」寫成「無 machine」。
   嚴格照三條件算,交集是 `{bletchley, catalina, gbs}`;把 `gbs` 排除的是**第四個條件**
   ——route (b′)(entity-manager + dbus-sensors 建感測器,見 `config/entity-manager/README.md`)
   要求映像同時含 `dbus-sensors` 與 `entity-manager`。這個條件一直存在,只是沒被寫成條件。
   處理:`platform-matrix.md` 加補註;`tools/reverify_upstream.sh` 的第 8 項現在印出
   machine 欄與交集,讓這個判斷每次都由腳本重算。
3. **bmcweb 漏洞(#6):** 規劃文件的「2026-05 四項」不可引用。以後只引用
   `tools/reverify_upstream.sh` 第 6 項印出來的清單。
4. **Gerrit(#7):** 17 天無回覆是事實,不是問題 —— `docs/upstream.md`〈溝通管道〉引用
   上游對回應時間的期待是「一週」量級,而 8/13、8/14 兩則帶量測的回覆已經是
   合理的推進;下一步等 owner 回答「CI 用哪台 QEMU target」,兩種答案各有既定處理。

## 有效期表(哪些事實會腐、多久要重驗一次)

| 類型 | 重新確認頻率 | 怎麼確認 | 2026-08-30 |
|---|---|---|---|
| 映像檔套件清單 | 每次換映像 | `reverify_upstream.sh` #1(或 `fetch_image.sh <target>`;注意 `--manifest-only` 會改 `image.manifest` symlink) | 未換映像;差異已記錄 |
| 平台決策矩陣 | 每 1~2 個月 | `reverify_upstream.sh` #8(= `platform_matrix.sh` + `qemu-system-arm -M help`) | 重跑;結論不變,修正一格 |
| `OWNERS` | 送 patch 前 | `reverify_upstream.sh` #4 | 未變 |
| 上游程式碼行為(`ec::pid()`、`conf.hpp`) | 引用前 | `reverify_upstream.sh` #2(記 commit hash) | 釘點後 0 commit |
| `configure.md` 的缺口 | 送 patch 前 | `reverify_upstream.sh` #3 | 七欄仍 0 |
| `QEMU_CI` 清單內容 | 送 patch 前 | `reverify_upstream.sh` #5 | 未變 |
| Redfish schema 支援狀態 | 每次換映像 | `harness/qemu/healthcheck.sh` 第 8、9 項 | 見下方〈環境重跑〉 |
| CLA 流程與連結 | 簽之前 | `openbmc/docs` 的 `CONTRIBUTING.md` | 2026-08-04 已寄出;ICLA 至今無回音(見 `upstream.md`) |
| bmcweb 漏洞公告 | 引用前 | `reverify_upstream.sh` #6 | 2 則公開,最新 2026-04-21 |
| Gerrit change 狀態 | 每天(有 open change 時) | `reverify_upstream.sh` #7 | 見 #7 |

## 環境重跑(2026-08-30):量測用的環境還跑得起來嗎

> 目的:確認「別人照 README 與 runbook 做,今天仍能得到同樣的東西」。
> 這一節在每次長時間沒開 QEMU 之後重做一次。結果的原始檔不進 git(是重跑不是量測)。

主機當時同時在跑其他工作(讀檔代理、建置),**時間類數字只供參考,不是量測**。

| # | 項目 | 2026-08-30 結果 |
|:-:|---|---|
| 1 | 映像還在 | `images/bletchley/` 仍是 `…-20260728025045.static.mtd`(56 MB)+ manifest;`flash-128M.mtd` 由 `run_bmc.sh` 重建 |
| 2 | 開機 | QEMU 11.0.1 `bletchley-bmc`。三層 readiness:SSH 可連 **+288 s**、bmcweb 回格式完整的 JSON **+289 s**(`RedfishVersion 1.17.0`)、`/redfish/v1/Chassis` collection 非空 **+290 s**(2 個成員:`Bletchley_Front_Panel_Board`、`Thermal_Loop_Demo` —— 後者是本 repo 的 entity-manager 設定,證明部署仍在 flash 的持久層)。guest 自報 `FinishTimestampMonotonic` 202.7 s。2026-08-18 量到的是 bmcweb +165 s、inventory +240 s;本次主機負載不同,兩組數字**不能比**,只記錄 |
| 3 | SSH + Redfish | kernel `6.18.40`、OpenBMC `3.1.0-dev-739`;`ThermalSubsystem.v1_0_0` 回 OK;Sensors collection 含 `temperature_die0` |
| 4 | swampd 還在跑本 repo 的設定 | `phosphor-pid-control.service` active;drop-in `/etc/systemd/system/phosphor-pid-control.service.d/override.conf` 在(重開機後仍在);`/tmp/pidlog/zone_0.log` 在寫;`FailSafe = false`(**預期**:部署的 `die0` 是 passive、`timeout: 0`,見 `config/swampd/README.md`) |
| 4b | 一行指令改溫度、三處同時變 | `tools/set_die_temp.py 42.5 --verify`:BMC hwmon 收到 `42438` m°C(等了 2.84 s);`busctl` 讀 `42.438`;Redfish `Reading 42.438 Cel`、`Status OK` |
| 5 | failsafe demo(L2 rig,`tools/failsafe_demo.sh`) | 觀察到 `FailSafe = true`、PWM `255/255`;這一趟 t1−t0 = **6.456 s**、t2−t0 = **6.556 s**(單趟、不進 `bench/data`)。Fig 4 的五趟量測是中位 5.081 s、範圍 [5.010, 5.155] —— 這趟高出範圍 1.3 s,bridge 節拍(+1 ms)與 swampd 行距(事件窗內無 >0.5 s 空洞)都排除,根因未定;分析見 `LOG.md` 2026-08-30 |
| 6 | 本機 | `meson test` **Ok: 6 / Fail: 0**(32 gtest + 153 pytest);`make figures` 後,CI 同款的決定性檢查 `git diff --exit-code -- ':(glob)bench/data/*.csv' bench/data/exp01_fit.txt bench/data/exp10_latency/events.csv` **乾淨**;`bench/assert_metrics.py` **14/14 PASS**;四張 PNG 在 meta 檔還原後與 git 逐 byte 相同(變的只是 caption 裡的 data commit,見 `LOG.md` 2026-08-30);matplotlib/numpy/pandas/scipy = `3.11.1 / 2.5.1 / 3.0.5 / 1.18.0`,與 `.github/ci-constraints.txt` 逐一相同 |

> ⚠️ 第 6 項**不要**照規劃文件寫的 `git diff --exit-code bench/data/` 檢查 ——
> 那條在本機重跑後永遠紅(meta 檔記的 data commit 必變)。用上面 CI 的原句。
