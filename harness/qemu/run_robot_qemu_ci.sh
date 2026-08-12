#!/usr/bin/env bash
# Run the official OpenBMC Robot suites against a QEMU BMC that is already up.
#
# Usage:
#   ./harness/qemu/run_robot_qemu_ci.sh [setup|qemu_ci|both]   (default: both)
#
# Prerequisites:
#   * QEMU is running: ./harness/qemu/run_bmc.sh bletchley (ports 2222/2443)
#   * openbmc-test-automation cloned at $OBMC_TA, deps installed in $ROBOT_VENV
#     (a dedicated venv: its requirements.txt must not dirty ~/.venvs/thermal,
#     which pins what bench/ and CI depend on)
#
# Notes:
#   * Robot exits non-zero when any case fails. That is data, not a script
#     error — failures on QEMU are expected and analysed one by one in
#     docs/robot-qemu-ci.md — so both runs end with "|| true" and the
#     reports are always kept.
#   * The weekly plan's env-var-only invocation (OPENBMC_HOST=... robot ...)
#     never reaches Robot: lib/resource.robot defaults OPENBMC_HOST to EMPTY
#     and Robot does not import environment variables. -v flags are the
#     working route (verified against the setup suite on 2026-08-12).
#   * Console output is tee'd next to the reports: the boot-test framework
#     runs its plug-ins as child processes whose output never reaches
#     Robot's log.html — the Auto_reboot 500 behind "Plug-in setup failed."
#     (2026-08-13) was visible only on the console.
set -uo pipefail

MODE="${1:-both}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
OBMC_TA="${OBMC_TA:-$HOME/work/openbmc-test-automation}"
ROBOT_VENV="${ROBOT_VENV:-$HOME/.venvs/robot}"
HOST="${OPENBMC_HOST:-127.0.0.1}"
SSH_PORT="${SSH_PORT:-2222}"
HTTPS_PORT="${HTTPS_PORT:-2443}"
OUT="${OUT:-$REPO/docs/robot/$(date +%Y%m%d_%H%M%S)}"

# shellcheck disable=SC1091
source "$ROBOT_VENV/bin/activate"
mkdir -p "$OUT"
cd "$OBMC_TA"

# REDFISH_SUPPORT_TRANS_STATE=1: without it several lib helpers fall back to
#   the legacy phosphor REST /login, which modern bmcweb no longer serves
#   (400) — the firmware-inventory suites then die in Suite Setup before
#   testing anything (observed on the 2026-08-12 first run).
# CHASSIS_ID: lib/resource.robot defaults to the literal id "chassis";
#   bletchley names its chassis Bletchley_Front_Panel_Board and
#   Thermal_Loop_Demo, so /redfish/v1/Chassis/chassis 404s without this.
VFLAGS=(-v OPENBMC_HOST:"$HOST"
        -v SSH_PORT:"$SSH_PORT" -v HTTPS_PORT:"$HTTPS_PORT"
        -v OPENBMC_USERNAME:root -v OPENBMC_PASSWORD:0penBmc
        -v REDFISH_SUPPORT_TRANS_STATE:1
        -v CHASSIS_ID:Bletchley_Front_Panel_Board)

run_setup() {
  echo "==> templates/test_openbmc_setup.robot"
  robot -d "$OUT/setup" "${VFLAGS[@]}" templates/test_openbmc_setup.robot 2>&1 | tee "$OUT/setup_console.log" || true
}

run_qemu_ci() {
  echo "==> test_lists/QEMU_CI (redfish/ + ipmi/)"
  robot -d "$OUT/qemu_ci" "${VFLAGS[@]}" -A test_lists/QEMU_CI redfish/ ipmi/ 2>&1 | tee "$OUT/qemu_ci_console.log" || true
}

case "$MODE" in
  setup)   run_setup ;;
  qemu_ci) run_qemu_ci ;;
  both)    run_setup; run_qemu_ci ;;
  *) echo "usage: $0 [setup|qemu_ci|both]" >&2; exit 2 ;;
esac

# Provenance — without it a report cannot be tied back to what produced it.
{
  echo "date=$(date -Is)"
  echo "obmc_test_automation_commit=$(git rev-parse --short HEAD)"
  echo "robot_version=$(robot --version 2>&1)"
  echo "repo_commit=$(git -C "$REPO" rev-parse --short HEAD)"
  echo "qemu_version=$(qemu-system-arm --version | head -n 1)"
  echo "image_manifest=$(basename "$(ls "$REPO"/images/bletchley/obmc-phosphor-image-*.manifest 2>/dev/null | head -n 1)")"
} > "$OUT/meta.txt"

echo "==> reports in $OUT"
