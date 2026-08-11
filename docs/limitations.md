# 限制與未完成

> 這一份是刻意寫的。作品集最容易被戳破的地方不是「做得少」,
> 而是「宣稱得比做的多」。這裡把邊界寫清楚;W11 補完整版。

## 驗證層面

- 官方 Robot 測試我跑的是 **`QEMU_CI` 清單(20 個生效 include)**,
  不是完整的硬體 CI 清單;失敗案例的數量、根因與判定寫在
  `docs/robot-qemu-ci.md`。**我沒有為了全綠去改測試或環境。**
- 跑 Robot 用的映像**不是 pristine**:`/etc` overlay 帶著本專案的
  entity-manager/swampd 設定(逐案檢查過,沒有失敗與此相關;
  宣告見 `docs/robot-qemu-ci.md`)。
- **端到端延遲(exp10)是在 QEMU 上量的,而且 guest 時鐘本身是量測
  對象級的干擾源**:實測 TCG guest 時鐘以 ~0.81× 速率行走、每 ~39.7 s
  被拉回牆鐘(+7.59 s,7 次跳步全記錄)。因此 ①(注入→D-Bus)與
  ④(D-Bus→Redfish)**不可分離、不單獨宣稱**;只宣稱單一時鐘域的量
  (全程 = host 錶、②③ = guest 錶)。數字用來比較**相對量級**與
  **組成結構**,不能當真實硬體的絕對值。(W6 的弱版教訓:平均值被
  排程抖動污染 19% → 只報中位數;這次是強版。)
- 我沒有把 Robot 測試接進本 repo 的 CI —— 它需要開 QEMU,單輪十幾分鐘,
  超出 CI 的合理預算;取捨是「報告 + 可重跑腳本進 repo」。

## 環境層面

- 全部在 QEMU 與本機模擬完成,**我沒有真實的 AST2600 板子**。
  溫度來自 QEMU 的 tmp421 行為模型(`hw/sensor/tmp421.c`),
  注入點在「晶片」層,下游(kernel driver → hwmon → dbus-sensors →
  swampd/bmcweb)是真的軟體路徑 —— 證明的是路徑,不是熱物理。
- **IPMI:我是「跑過官方 IPMI 測試」,不是「開發過 IPMI 命令」。**
  而且本映像沒有 netipmid,out-of-band 案例的失敗根因是映像裁剪
  (見 `docs/robot-qemu-ci.md`)。
- 風扇不存在:PWM 的 writePath 是普通檔案(`/tmp/sys/pwm0`),
  轉速回授由熱模型/橋接器合成 —— 「風扇物理」不在本專案的宣稱範圍。

(其餘 W11 補齊:每張圖的適用邊界、每個 claim 的容差理由。)
