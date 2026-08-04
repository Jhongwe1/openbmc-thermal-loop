#!/usr/bin/env bash
# 參數化的 QEMU 啟動器。
#
#   ./harness/qemu/run_bmc.sh bletchley
#   SSH_PORT=2223 HTTPS_PORT=2444 ./harness/qemu/run_bmc.sh gb200nvl-obmc
#   QEMU_MACHINE=ast2600-evb ./harness/qemu/run_bmc.sh bletchley   # 換 machine 重試
#   QEMU_SERIAL=file:/tmp/boot.log ./harness/qemu/run_bmc.sh bletchley  # 無終端機(CI)
#
# 離開:-nographic 下按 Ctrl-a 放開再按 x。(Ctrl-c 會被送進 guest)
set -euo pipefail
TARGET="${1:-bletchley}"

# MACHINE  = QEMU 的板子模型
# FLASH_MB = 該板子上 SPI flash 晶片的容量。QEMU 模擬的是實體晶片，映像必須
#            補零到晶片大小，否則 QEMU 在開機前就拒絕啟動：
#              w25q01jvq device requires 134217728 bytes,
#              mtd0 block backend provides 58610688 bytes
#            這等同於真實燒錄時，燒錄器把剩餘空間留空。
#
#            每塊板子的晶片型號不同，容量也不同：
#              bletchley-bmc  w25q01jv     128 MiB
#              gb200nvl-bmc   mx66u51235f   64 MiB
#              romulus-bmc    (AST2500)     32 MiB
#            填錯的話 QEMU 一樣會拒絕啟動，而且錯誤訊息裡的
#            "requires N bytes" 就是正確答案 —— 照著填即可。
case "${TARGET}" in
  bletchley|bletchley15) MACHINE="${QEMU_MACHINE:-bletchley-bmc}" ; FLASH_MB="${FLASH_MB:-128}" ;;
  catalina)              MACHINE="${QEMU_MACHINE:-catalina-bmc}"  ; FLASH_MB="${FLASH_MB:-128}" ;;
  gb200nvl-obmc)         MACHINE="${QEMU_MACHINE:-gb200nvl-bmc}"  ; FLASH_MB="${FLASH_MB:-64}"  ;;
  romulus)               MACHINE="${QEMU_MACHINE:-romulus-bmc}"   ; FLASH_MB="${FLASH_MB:-32}"  ;;
  *)                     MACHINE="${QEMU_MACHINE:-ast2600-evb}"   ; FLASH_MB="${FLASH_MB:-128}" ;;
esac

RAW="images/${TARGET}/image.mtd"
FLASH="images/${TARGET}/flash-${FLASH_MB}M.mtd"

[[ -e "${RAW}" ]] || { echo "找不到映像 ${RAW}，先跑 fetch_image.sh ${TARGET}" >&2; exit 1; }

# 只在缺檔或原始映像較新時重建，避免每次開機都複製 128 MB
if [[ ! -f "${FLASH}" || "${RAW}" -nt "${FLASH}" ]]; then
  RAW_BYTES=$(stat -Lc %s "${RAW}")
  WANT_BYTES=$(( FLASH_MB * 1024 * 1024 ))
  (( RAW_BYTES <= WANT_BYTES )) || {
    echo "映像 ${RAW_BYTES} bytes 比 flash ${WANT_BYTES} bytes 大，補零會截斷。停。" >&2
    exit 1
  }
  echo "==> 補齊映像到 ${FLASH_MB} MiB: ${FLASH}"
  cp --dereference "${RAW}" "${FLASH}"
  truncate -s "${FLASH_MB}M" "${FLASH}"
fi

SSH_PORT="${SSH_PORT:-2222}"; HTTPS_PORT="${HTTPS_PORT:-2443}"
SERIAL="${QEMU_SERIAL:-mon:stdio}"
echo "==> ${TARGET} on ${MACHINE}  flash=${FLASH_MB}MiB  (ssh:${SSH_PORT} https:${HTTPS_PORT})"

# UI 旗標的選擇取決於 console 送去哪裡。
#
#   互動模式（預設 QEMU_SERIAL=mon:stdio）：-nographic 把 serial 與 monitor
#   都接到終端機，Ctrl-a 放開再按 x 可以離開。
#
#   無終端機模式（QEMU_SERIAL=file:... 或 CI）：serial 已經導去檔案，此時
#   -nographic 會把 **monitor** 單獨留在 stdio。背景執行時 stdin 一旦 EOF，
#   monitor 收到 EOF 就讓整個 QEMU 正常結束 —— 現象是「開機開到一半自己消失」，
#   而且不留任何錯誤訊息、離開碼是 0。改用 -display none + -monitor none，
#   QEMU 就不再有任何東西掛在 stdin 上。
QEMU_UI=( -nographic )
case "${SERIAL}" in
  mon:stdio|stdio) ;;
  *) QEMU_UI=( -display none -monitor none ) ;;
esac

exec qemu-system-arm \
  -M "${MACHINE}" -m 1G "${QEMU_UI[@]}" \
  -drive "file=${FLASH},format=raw,if=mtd" \
  -netdev "user,id=net0,hostfwd=tcp:127.0.0.1:${SSH_PORT}-:22,hostfwd=tcp:127.0.0.1:${HTTPS_PORT}-:443" \
  -net nic,netdev=net0 \
  -serial "${SERIAL}" -serial null
