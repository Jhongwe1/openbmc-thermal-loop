#!/usr/bin/env bash
# 從 OpenBMC Jenkins 抓最新 static.mtd，並自動比對套件清單。
#
# 用法:
#   ./harness/qemu/fetch_image.sh bletchley              # 抓映像 + manifest
#   ./harness/qemu/fetch_image.sh romulus --manifest-only # 只抓 manifest(不下載幾十 MB 映像)
set -euo pipefail

MACHINE="${1:-bletchley}"
MANIFEST_ONLY=0
[[ "${2:-}" == "--manifest-only" ]] && MANIFEST_ONLY=1

BASE="https://jenkins.openbmc.org/job/latest-master/label=docker-builder,target=${MACHINE}"
DIR="${BASE}/lastSuccessfulBuild/artifact/openbmc/build/tmp/deploy/images/${MACHINE}"
OUT="images/${MACHINE}"
mkdir -p "${OUT}"

LISTING=$(curl -fsSL --max-time 60 "${DIR}/")

NAME=$(grep -oE "obmc-phosphor-image-${MACHINE}-[0-9]+\.static\.mtd" <<<"${LISTING}" | sort -u | tail -1)
MANIFEST=$(grep -oE "obmc-phosphor-image-${MACHINE}-[0-9]+\.manifest" <<<"${LISTING}" | sort -u | tail -1)

[[ -n "${MANIFEST}" ]] || { echo "找不到 manifest，手動開: ${DIR}/" >&2; exit 1; }

echo "==> manifest: ${MANIFEST}"
curl -fsSL --max-time 120 -o "${OUT}/${MANIFEST}" "${DIR}/${MANIFEST}"
ln -sf "${MANIFEST}" "${OUT}/image.manifest"

if [[ "${MANIFEST_ONLY}" -eq 0 ]]; then
  [[ -n "${NAME}" ]] || { echo "找不到 static.mtd，手動開: ${DIR}/" >&2; exit 1; }
  echo "==> image: ${NAME}"
  curl -fL -# --max-time 1800 -o "${OUT}/${NAME}" "${DIR}/${NAME}"
  ln -sf "${NAME}" "${OUT}/image.mtd"
fi

echo "==> 套件清單體檢(★ 這一步就是平台選擇的教訓):"
for pkg in phosphor-pid-control dbus-sensors entity-manager bmcweb \
           phosphor-hwmon phosphor-virtual-sensor phosphor-fan-control; do
  if grep -qE "^${pkg} " "${OUT}/${MANIFEST}" 2>/dev/null; then
    printf '  ✅ %-28s %s\n' "${pkg}" "$(grep -E "^${pkg} " "${OUT}/${MANIFEST}" | awk '{print $NF}')"
  else
    printf '  ❌ %-28s ← 不在這個映像裡\n' "${pkg}"
  fi
done
