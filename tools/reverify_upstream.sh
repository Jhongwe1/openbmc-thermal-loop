#!/usr/bin/env bash
# 重新確認「本 repo 引用的上游事實」還成不成立。輸出是 docs/verification-log.md 的原料。
#
#   ./tools/reverify_upstream.sh                 # 結果印到 stdout,原始檔存 /tmp/reverify-<日期>/
#   OUT=/path ./tools/reverify_upstream.sh       # 換輸出目錄
#
# 只讀不寫:不碰 images/(fetch_image.sh --manifest-only 會改 image.manifest 的
# symlink —— 2026-08-18 踩過),不碰 subprojects/,不需要 ~/work 底下的任何 clone。
# 需要:curl、jq、python3、git、qemu-system-arm(第 8 項;沒有就跳過並說明)。
#
# 八項各回答一個「這個宣稱還成立嗎」的問題,對應 docs/verification-log.md 的表:
#   1 映像:Jenkins latest-master 的 bletchley 映像與套件清單,和量測時用的那份差在哪
#   2 ec::pid():釘住的 c5e59550d3 之後,pid/ec/pid.cpp / conf.hpp 有沒有被改(parity 測試的前提)
#   3 configure.md:七個未文件化欄位在 master 上補了沒(change 93470 的前提)
#   4 OWNERS:兩個 repo 的 owner / reviewer 換人了沒
#   5 QEMU_CI:清單有沒有熱控/感測器案例、死 include 還在不在(change 93469 的前提)
#   6 bmcweb:GitHub 公開的 security advisory 清單
#   7 Gerrit:我們三筆 change 的狀態(匿名 REST;private 的那筆會 404,這是預期)
#   8 平台矩陣:19 個 target 的 manifest 五欄 + QEMU machine 是否存在 + 三條件交集
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO"
OUT="${OUT:-/tmp/reverify-$(date +%Y%m%d)}"
mkdir -p "$OUT"
PIN=c5e59550d3
LOCAL_MANIFEST=images/bletchley/obmc-phosphor-image-bletchley-20260728025045.manifest
GH=https://api.github.com/repos/openbmc
RAW=https://raw.githubusercontent.com/openbmc
CURL=(curl -fsSL --max-time 60 -A 'openbmc-thermal-loop reverify')

hdr() { printf '\n===== %s =====\n' "$1"; }
echo "reverify_upstream  $(date -u +%Y-%m-%dT%H:%M:%SZ)  repo HEAD=$(git rev-parse --short HEAD)  out=$OUT"

hdr "1. bletchley 映像:Jenkins latest-master vs 量測用的 20260728"
BASE="https://jenkins.openbmc.org/job/latest-master/label=docker-builder,target=bletchley"
DIR="${BASE}/lastSuccessfulBuild/artifact/openbmc/build/tmp/deploy/images/bletchley"
LISTING=$("${CURL[@]}" "${DIR}/" 2>/dev/null) || LISTING=""
MANIFEST=$(grep -oE "obmc-phosphor-image-bletchley-[0-9]+\.manifest" <<<"${LISTING}" | sort -u | tail -1)
echo "Jenkins 最新 manifest : ${MANIFEST:-<listing 失敗>}"
echo "本 repo 量測用的      : $(basename "$LOCAL_MANIFEST")"
if [[ -n "${MANIFEST}" ]] && "${CURL[@]}" -o "$OUT/latest.manifest" "${DIR}/${MANIFEST}"; then
  printf '  %-24s %-30s %s\n' "套件" "量測時(本 repo)" "Jenkins 最新"
  for pkg in phosphor-pid-control dbus-sensors entity-manager bmcweb phosphor-hwmon phosphor-virtual-sensor phosphor-fan-control phosphor-ipmi-net; do
    L=$(awk -v p="$pkg" '$1==p{print $NF}' "$LOCAL_MANIFEST"); N=$(awk -v p="$pkg" '$1==p{print $NF}' "$OUT/latest.manifest")
    printf '  %-24s %-30s %s\n' "$pkg" "${L:-<無>}" "${N:-<無>}"
  done
  diff <(awk '{print $1}' "$LOCAL_MANIFEST" | sort) <(awk '{print $1}' "$OUT/latest.manifest" | sort) > "$OUT/manifest_pkgset.diff"
  echo "  套件集合差異(只看名字,不看版本):$(grep -c '^[<>]' "$OUT/manifest_pkgset.diff") 行 → $OUT/manifest_pkgset.diff"
fi

hdr "2. phosphor-pid-control:釘點 ${PIN} 之後,控制律相關檔案動了沒(GitHub commits API)"
PIN_DATE=$("${CURL[@]}" "$GH/phosphor-pid-control/commits/$PIN" | jq -r '.commit.committer.date' 2>/dev/null)
echo "釘點 commit 日期:${PIN_DATE:-?}"
for f in pid/ec/pid.cpp conf.hpp configure.md pid/ec/logging.cpp; do
  n=$("${CURL[@]}" "$GH/phosphor-pid-control/commits?path=$f&since=${PIN_DATE:-2026-07-27T00:00:00Z}&per_page=50" \
      | jq -r --arg pin "$PIN" '[.[] | select(.sha | startswith($pin) | not)] | length' 2>/dev/null)
  printf '  %-22s 釘點之後的 commit 數:%s\n' "$f" "${n:-?}"
done
echo "  master 上釘點之後的所有 commit(最多 20):"
"${CURL[@]}" "$GH/phosphor-pid-control/commits?since=${PIN_DATE:-2026-07-27T00:00:00Z}&per_page=20" \
  | jq -r --arg pin "$PIN" '.[] | select(.sha | startswith($pin) | not) | "    \(.sha[0:7])  \(.commit.committer.date[0:10])  \(.commit.message | split("\n")[0])"' 2>/dev/null

hdr "3. configure.md(master):七個欄位各出現幾次(0 = 仍未文件化,93470 仍有意義)"
"${CURL[@]}" -o "$OUT/configure.md" "$RAW/phosphor-pid-control/master/configure.md" || echo "  抓不到 configure.md"
for f in cycleIntervalTimeMS updateThermalsTimeMS accumulateSetPoint derivativeCoeff convertTempToMargin convertMarginZero missingIsAcceptable; do
  c=$(grep -ci "$f" "$OUT/configure.md" 2>/dev/null)   # grep 數到 0 會以 exit 1 收場,所以不用 || 兜
  printf '  %-22s %s\n' "$f" "${c:-?}"
done

hdr "4. OWNERS(master)"
for r in phosphor-pid-control openbmc-test-automation; do
  echo "  --- $r ---"
  "${CURL[@]}" "$RAW/$r/master/OWNERS" | grep -vE '^\s*#' | grep -v '^\s*$' | sed 's/^/    /'
done

hdr "5. test_lists/QEMU_CI(master)"
"${CURL[@]}" -o "$OUT/QEMU_CI" "$RAW/openbmc-test-automation/master/test_lists/QEMU_CI" || echo "  抓不到 QEMU_CI"
echo "  生效 include 行數           :$(grep -c '^--include' "$OUT/QEMU_CI")"
echo "  thermal|sensor 案例         :$(grep -ic 'thermal\|sensor' "$OUT/QEMU_CI")"
echo "  死 include(改名前的 tag)    :$(grep -n 'Verify_Update_Service_Enabled' "$OUT/QEMU_CI" || echo '不在了')"

hdr "6. bmcweb:GitHub 公開的 security advisories"
if "${CURL[@]}" -H 'Accept: application/vnd.github+json' -o "$OUT/bmcweb_advisories.json" "$GH/bmcweb/security-advisories?per_page=20"; then
  jq -r 'if type=="array" then (length|tostring) + " 則已公開" , (.[] | "  \(.published_at[0:10])  \(.ghsa_id)  \(.severity)  \(.state)  \(.summary[0:70])") else "unexpected: \(.)" end' "$OUT/bmcweb_advisories.json"
fi

hdr "7. Gerrit:三筆 change 的狀態(匿名 REST)"
python3 - 93469 93470 93397 <<'EOF'
import json, sys, urllib.request
for c in sys.argv[1:]:
    url = f"https://gerrit.openbmc.org/changes/{c}?o=CURRENT_REVISION&o=MESSAGES&o=DETAILED_LABELS"
    try:
        raw = urllib.request.urlopen(url, timeout=60).read().decode()
    except Exception as e:
        print(f"  {c}  {e}  (93397 帶 private 旗標,匿名 404 是預期)"); continue
    d = json.loads(raw.split("\n", 1)[1] if raw.startswith(")]}'") else raw)
    ps = d["revisions"][d["current_revision"]]["_number"]
    msgs = d.get("messages", [])
    votes = [str(v.get("value")) for v in d.get("labels", {}).get("Code-Review", {}).get("all", []) if v.get("value")]
    last = msgs[-1]["date"][:16] if msgs else "?"
    print(f"  {d['_number']}  {d['status']:<9} ps={ps}  messages={len(msgs)}  最後一則={last}  Code-Review={votes or '無'}  {d['subject']}")
EOF

hdr "8. 平台矩陣:manifest 五欄(腳本)+ QEMU machine(腳本)+ 三條件交集"
./harness/qemu/platform_matrix.sh > "$OUT/platform_matrix.md" 2>&1 && echo "  manifest 五欄 → $OUT/platform_matrix.md"
if command -v qemu-system-arm >/dev/null; then
  echo "  $(command -v qemu-system-arm): $(qemu-system-arm --version | head -n 1)"
  qemu-system-arm -M help > "$OUT/qemu_machines.txt"
  # Jenkins target → QEMU machine 名稱不是機械對應,能對上的列在這裡;其餘試 <target>-bmc
  declare -A MAP=([p10bmc]=rainier-bmc [gb200nvl-obmc]=gb200nvl-bmc [gbs]=quanta-gbs-bmc [evb-npcm845]=npcm845-evb)
  printf '  %-16s %-8s %-20s %s\n' target swampd "QEMU machine" "三條件交集"
  grep -E '^\| `' "$OUT/platform_matrix.md" | while IFS='|' read -r _ t s _; do
    t=$(tr -d ' `' <<<"$t"); s=$(tr -d ' ' <<<"$s")
    m="${MAP[$t]:-$t-bmc}"
    if grep -qE "^${m}\b" "$OUT/qemu_machines.txt"; then have="$m"; else have="—"; fi
    ok="—"; [[ "$s" == "✅" && "$have" != "—" ]] && ok="✅"
    printf '  %-16s %-8s %-20s %s\n' "$t" "$s" "$have" "$ok"
  done
  echo "  (交集 = Jenkins 有映像 ∩ QEMU 有 machine ∩ 映像含 phosphor-pid-control;machine 對應表在本腳本 MAP,對不上的 target 以「—」列出,需人工確認)"
else
  echo "  qemu-system-arm 不在 PATH,第三條件跳過(Jenkins 版在 ~/bin,要用 login shell)"
fi
echo
echo "原始檔在 $OUT/。把上面的結果填進 docs/verification-log.md 時,日期用本次執行日期。"
