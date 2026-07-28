#!/usr/bin/env bash
# 掃描所有 Jenkins target 的套件清單，產出 Markdown 表格。
# 這支腳本本身就是交付物：它證明平台選擇是查出來的，不是猜的。
#
# 用法: ./harness/qemu/platform_matrix.sh | tee docs/platform-matrix.md
set -uo pipefail

TARGETS="anacapa bletchley bletchley15 catalina clemente e3c246d4i evb-npcm845
         gb200nvl-obmc gbs harma minerva p10bmc romulus sanmiguel santabarbara
         ventura ventura2 yosemite4 yosemite5"
PKGS="phosphor-pid-control dbus-sensors entity-manager phosphor-virtual-sensor phosphor-fan-control"
NCOL=$(wc -w <<<"$PKGS")

printf '| target | %s |\n' "$(sed 's/ / | /g' <<<"$PKGS")"
printf '|---%s|\n' "$(for _ in $PKGS; do printf '|:---:'; done)"

for M in $TARGETS; do
  D="https://jenkins.openbmc.org/job/latest-master/label=docker-builder,target=${M}/lastSuccessfulBuild/artifact/openbmc/build/tmp/deploy/images/${M}"
  N=$(curl -fsSL --max-time 60 "${D}/" 2>/dev/null \
      | grep -oE "obmc-phosphor-image-${M}-[0-9]+\.manifest" | sort -u | tail -1)
  if [[ -z "$N" ]]; then
    # 補滿欄位數，否則 Markdown 表格會跑掉
    printf '| `%s` ' "$M"
    for _ in $(seq "$NCOL"); do printf '| (no manifest) '; done
    printf '|\n'
    continue
  fi
  MAN=$(curl -fsSL --max-time 60 "${D}/${N}" 2>/dev/null)
  printf '| `%s` ' "$M"
  for p in $PKGS; do
    grep -qE "^${p} " <<<"$MAN" && printf '| ✅ ' || printf '| — '
  done
  printf '|\n'
done
