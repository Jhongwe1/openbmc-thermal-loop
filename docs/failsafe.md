# Failsafe 的語意與實測

> 讀碼版本:`phosphor-pid-control @ c5e5955`(與 BMC 映像同版,見
> `docs/env-baseline.md`)。行號以該版為準。
> 實測數據見 §5(exp09);我沒有驗證的部分誠實列在 §6。

## 0. 一句話

**Fail to safe,不是 fail to last-known-good。**
讀不到值可能代表 I2C 掛了、感測器燒了、或系統正在起火 ——
保持上一個低速值,等於在最需要保護的時候把保護關掉。
OpenBMC 的實作:zone 進 failsafe,PWM 拉到 `failsafePercent`
(本專案 config 設 100%)。

## 1. 觸發條件(讀 `pid/zone.hpp:145-220` 的 `processSensorInputs`)

每一輪感測器更新,對每顆 sensor 依序檢查三件事:

| # | 條件 | 程式碼 | 說明 |
|---|---|---|---|
| ① | `sensor->getFailed()` | `dbus/dbuspassive.cpp:194-270` | 匯總六種失效(見下) |
| ② | `timeout != 0 && (now − r.updated) ≥ timeout` | `zone.hpp:192` | **感測器逾時**:`r.updated` 是**最後一次 PropertiesChanged 的時刻**,不是最後一次讀取 |
| ③ | 都沒有 → 從 `_failSafeSensors` 移除 | `zone.hpp:204-219` | **恢復是自動的**,新值一到就退出 |

`getFailed()`(①)匯總的失效來源,依檢查順序:

1. redundancy 物件宣告的失效清單
2. `_badReading` —— 讀到 **NaN**
3. `_marginHot` —— margin 型感測器過熱
4. `_failed` —— D-Bus `OperationalStatus.Functional == false`
5. `!_available` —— D-Bus `Availability.Available == false`
   ★ 受 `unavailableAsFailed` 調節:設 false 時「不可用」不算失敗
   (某些感測器在特定電源狀態下本來就不該有值);
   注意 fan 型別**不受**這個豁免(`!_typeFan` 條件)
6. `!_functional`

★★ **還有第四個入口,計畫沒寫:開機即 failsafe。**
`initializeCache()`(`pid/zone.cpp:503-521`)把**每一顆** sensor 先
`markSensorMissing` —— swampd 啟動的第一刻整個 zone 就在 failsafe,
直到每顆 sensor 都送來第一筆有效讀值才逐顆退出。
這是「fail to safe」哲學的一致延伸:**沒讀過值 = 不可信**,
而不是「還沒讀到 = 假設正常」。

`getFailSafeMode()` 的定義是 `!_failSafeSensors.empty()`
(`pid/zone.cpp:86-89`)—— **任何一顆**輸入失效,整個 zone 進 failsafe。

## 2. 四個 build option 的語意差異(讀 `meson.options`)

| Build option | 預設 | 它處理的故障模式 |
|---|:---:|---|
| `strict-failsafe-pwm` | false | failsafe 時 PWM **嚴格等於** `failsafePercent`。預設(不開)是 `max(計算值, failsafePercent)` —— 計算值可以更高,不能更低(`pid/fancontroller.cpp:140-161`) |
| `offline-failsafe-pwm` | false | **swampd 自己要下線了**(reload / terminate)時把風扇設到 failsafe PWM。⚠️ 它不是 CLI 參數、與感測器逾時無關 —— 這是「控制器不在了」的故障模式,不是「感測器壞了」 |
| `unc-failsafe` | false | 溫感超過 **upper non-critical 閾值**時進 failsafe —— 感測器**還活著而且值可信**,只是值太高 |
| `handle-missing-object-paths` | false | 感測器物件**根本沒出現在 D-Bus 上**時的額外處理 —— 連「它應該存在」都要從設定推斷(entity-manager 的設定與實際硬體對不上) |

> 這四個是四種**不同的故障模式**:值太高 / 控制器消失 / 物件缺席 /
> 嚴格度。偵測路徑與合理的退化行為都不一樣,所以是四個開關不是一個。

**本映像編了哪幾個?** 從行為驗證(§5 的 exp09):failsafe 期間
PWM 恰為 `failsafePercent` 且解除後回到計算值 —— 但因為本 config 的
`failsafePercent = 100` 恰好也是 `outLim_max`,「strict」與「max」在
100% 這一點**不可分辨**。要分辨得把 failsafePercent 設到計算值之下
(例如 50%)再觸發 failsafe:PWM 若跳到 50 → strict;若停在計算值
(> 50)→ 預設 max 行為。這個驗證列在 §6(未做)。

## 3. 兩個不同的逾時 —— 關注點分離

| 誰的逾時 | 設定在哪 | 逾時後 |
|---|---|---|
| `dbus-sensors` 的 `ExternalSensor.Timeout` | entity-manager JSON | 值變 **NaN**(設計文件原話:*"NaN is literally not a number, and thus can not be misparsed as a valid sensor reading."*) |
| `phosphor-pid-control` 的 sensor `timeout` | swampd config | **zone 進 failsafe**(§1 的入口 ②) |

感測器層只把值標成 NaN —— 它不知道誰在用這個值,也不該替使用者
決定怎麼辦。控制層才決定進不進 failsafe,因為**只有控制器知道
「沒有這顆值我還能不能安全運作」**。這是關注點分離,不是重複設計。

兩層在 swampd 端**匯流**:NaN 走 `_badReading`(§1 入口 ①-2),
「值不再更新」走 timeout(入口 ②)—— 一個是「收到壞值」,
一個是「什麼都沒收到」,swampd 分開偵測、殊途同歸進 failsafe。

⚠️ 本映像的 dbus-sensors 被 meta-facebook 的 bbappend 拿掉了
`external`(W3 的發現,`PACKAGECONFIG:remove`),所以第一列的
`ExternalSensor.Timeout` 在這台上**沒有實例** —— 表格描述的是上游
兩層設計;本專案實測的是第二列。

## 4. 與 W3 那顆地雷的關係(timeout = 0 的由來)

W3 把 `die0` 的 `timeout` 設成 0(= 永不逾時),因為:passive D-Bus
感測器的 `r.updated` **只在 `PropertiesChanged` 時推進**,而
dbus-sensors 值沒變就不發訊號 → 溫度穩定 = `_updated` 凍結 =
被誤判成感測器死掉(當時實測 failsafe=1、PWM 100%)。

**exp09 正是把這顆地雷倒過來用**:要觸發 timeout,溫度來源必須先
「持續變化」(每秒都有 PropertiesChanged,`_updated` 跟著走)——
然後**停止變化**,`now − updated` 開始累積,timeout 秒後入 failsafe。
「停止推值」在 D-Bus 語意上等於「感測器凍結」,不需要殺任何行程。

同一個機制,W3 是坑(穩定溫度被當成死掉)、W8 是量具(凍結時刻
可以由實驗精確控制)—— 差別只在 timeout 是 0 還是 5。

## 5. 我量到的延遲(exp09,2026-08-11)

L2 rig(私有匯流排、**未修改** swampd @ c5e5955、同一份 C++ plant),
config = `config.tuned.json` 唯一改 `die0` 的 `timeout` 0 → 5(腳本生成
並逐欄驗證)。t₀ = bridge 停止推值(絕對節拍錨定);t₁/t₂ 從
`zone_0.log` 讀(每輪一行、無節流、自帶 epoch)。**5 次獨立 run**:

| 段 | 從 → 到 | 中位數 | 範圍 | 組成 |
|---|---|---|---|---|
| ① | 停止推值 → failsafe 旗標 | **4.981 s** | 4.910~5.055 | timeout(config 5 s,從**最後一次 push** 起算 = t₀−0.1 s)+ 逾時檢查節奏(隨外圈 1 Hz)+ D-Bus/寫出(ms) |
| ② | failsafe → PWM 拉滿 | **100 ms** | 100~100(5/5 恰好一輪) | 內圈風扇迴路(實測 100 ms)+ 檔案寫出 |
| 總 | 停止推值 → PWM 拉滿 | **5.081 s** | 5.010~5.155 | |

- **② 的決定性**是數位路徑該有的樣子:failsafe 旗標變 1 之後,
  下一輪內圈就把 PWM 蓋成 `failsafePercent` —— 5 次都是恰好一行之差。
- ⚠️ **run 間散布(145 ms)遠小於機制的抖動上界(~1 s),
  這是採樣偏差不是精度**:逾時檢查騎在外圈 1 Hz 上,停止推值的時刻
  與檢查的相位差理論上均勻分布;但本 rig 的啟動序列固定
  (bridge 起 2 s 後才起 swampd),每 run 的相位幾乎相同。
  正確的宣稱是「**N ≈ timeout + [0, 1) s 的檢查相位 + ms 級傳遞**,
  本 rig 的相位恰落在 ~0 附近」,不是「延遲總是 5.0 s」。
- ⚠️ 環境健康是 run 有效性的一部分:事件窗內 log 行距 > 0.5 s
  (量測環境凍結)的 run 會被自動作廢 —— 第一批資料就是這樣死的
  (session 中斷期間宿主節流 WSL,t₁−t₀ 被撐到 17.3 s),見 LOG.md。
- Gate 4 的 D-Bus 驗證:每個 run 結束前 `busctl get-property … FailSafe`
  讀到 `b true`(`run*_failsafe_property.txt`)。**這是驗證不是量測**:
  `FailSafe` 是純 getter、從不發 PropertiesChanged(§1),
  所以計畫寫的「busctl monitor 打時戳」量不到任何東西。

## 6. 我沒有驗證的部分(誠實)

- 感測器逾時是**停止推值**模擬的,不是真的把 I2C 拔掉。
- 四個 build option 的實際行為差異需要重編映像,我沒有做。
  我讀了 `meson.options` 與 `fancontroller.cpp` 知道語意,
  但除了預設組合外沒有實驗證據。特別是 §2 說明的
  「strict 與 max 在 failsafePercent = 100 時不可分辨」——
  分辨實驗(failsafePercent < 計算值)列入待做,未排程。
- `unavailableAsFailed` / `missingIsAcceptable` 兩個豁免旋鈕只讀了碼,
  沒有做行為驗證。
- I2C bus 死鎖復原(SCL 送最多 9 個 clock pulse 逼 slave 吐完剩餘
  bit,再補 STOP;9 = 一個 byte + ACK 的 bit 數)只能講原理:
  QEMU 模擬不出 SDA 被實體拉低,我沒有真板子能製造這個故障。
  **我驗證的是「感測器讀不到值之後的行為」,不是「感測器為什麼
  讀不到」。**
