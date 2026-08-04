# OpenBMC Closed-Loop Thermal Control Testbed

在 QEMU ASPEED AST2600 上，用上游 `phosphor-pid-control` 建立一條可量測、
可重現的熱控閉環，並**量化上游既有抗飽和機制（anti-windup）的實際效果**。

> 🚧 進行中（2026-07 起）。目前進度：**Gate 0 完成、Gate 1 前半達成**——
> `swampd` 已用本 repo 的設定跑起來，一行 `busctl set-property` 就能把
> `die0` 的溫度從 40 改成 80，`zone_0.log` 與 PID 內部軌跡都出得來。
> **Redfish 那一段還沒通**（見下方 Gate 1 的未打勾項），原因已查明並記錄在
> [`docs/redfish-notes.md`](docs/redfish-notes.md)。

## 為什麼做這個

（W10 補完。）

## 目標平台

主線 **`bletchley`**（QEMU `bletchley-bmc`），備援 **`catalina`**（QEMU `catalina-bmc`）。
兩台都是 AST2600 / Cortex-A7。

此選擇來自 `harness/qemu/platform_matrix.sh` 對 19 個 Jenkins target 的實測掃描
（見 [`docs/platform-matrix.md`](docs/platform-matrix.md)）——依據是三個條件的交集：

```
{ Jenkins 有出映像 } ∩ { QEMU 有 machine model } ∩ { 映像含 phosphor-pid-control }
```

`romulus` 與 `gb200nvl-obmc` 明確排除：manifest 顯示它們**沒有**
`phosphor-pid-control`。這一步是查證，不是試錯。

## 架構

見 `docs/architecture.md`。

## 現況

- [x] Gate 0　環境就緒　　　　　　　← [env-baseline.md](docs/env-baseline.md)
- [ ] Gate 1　端到端可觀測　　　　　← **前兩條達成，Redfish 那段待 W3**
  - [x] 一行指令把溫度從 40 改成 80　　← `tools/push_temp.sh`
  - [x] `busctl` 看得到 `Value` 變了，且 `swampd` 收得到
        （`pidcore.die0` 的 `input` 欄從 40 變 80）
  - [ ] Redfish 看到同一變化　　　　　← W3（route (b)：entity-manager）
  - [ ] 畫得出從指令到 Redfish JSON 經過哪幾個行程、幾次 IPC
  - [x] 知道**為什麼**有些感測器出現在 Redfish、有些沒有
        ← [redfish-notes.md](docs/redfish-notes.md)

  > ⚠️ **誠實標註：** 這台 QEMU 沒有任何風扇硬體（`/sys/class/pwm/` 是空的，
  > D-Bus 上沒有 `fan_tach`）。設定裡的 `fan0` 讀寫的是 `/tmp/sys/` 底下的
  > **普通檔案**，它證明的是「swampd 的寫出路徑被執行了、值是多少」，
  > **不是「風扇真的轉了」**。理由與做法見
  > [`config/swampd/README.md`](config/swampd/README.md)。
- [ ] Gate 2　被控對象 + 跨層追蹤
- [ ] Gate 3　控制器與量測
- [ ] Gate 4　失效安全
- [ ] Gate 5　官方測試套件
- [ ] Gate 6　Upstream
- [ ] Gate 7　交付與敘事

## 授權

Apache-2.0（與 OpenBMC 上游一致）。
