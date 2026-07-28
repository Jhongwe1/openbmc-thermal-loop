# OpenBMC Closed-Loop Thermal Control Testbed

在 QEMU ASPEED AST2600 上，用上游 `phosphor-pid-control` 建立一條可量測、
可重現的熱控閉環，並**量化上游既有抗飽和機制（anti-windup）的實際效果**。

> 🚧 進行中（2026-07 起）。目前進度：開發環境落地，Gate 0 進行中。

## 為什麼做這個

（W10 補完。）

## 目標平台

主線 `bletchley`，備援 `anacapa`。
**此選擇待 `harness/qemu/platform_matrix.sh` 掃描 Jenkins target 後確認**
（見 `docs/platform-matrix.md`）——選平台的依據是該 target 的映像裡是否
實際含有 `phosphor-pid-control`，不是猜的。

## 架構

見 `docs/architecture.md`。

## 現況

- [ ] Gate 0　環境就緒　　　　　　　← 進行中
- [ ] Gate 1　端到端可觀測
- [ ] Gate 2　被控對象 + 跨層追蹤
- [ ] Gate 3　控制器與量測
- [ ] Gate 4　失效安全
- [ ] Gate 5　官方測試套件
- [ ] Gate 6　Upstream
- [ ] Gate 7　交付與敘事

## 授權

Apache-2.0（與 OpenBMC 上游一致）。
