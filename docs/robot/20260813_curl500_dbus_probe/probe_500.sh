#!/bin/bash
# Red-team probe: reproduce the AutomaticRetryConfig 500 with plain curl
# (no Robot framework involved), then collect BMC-side evidence.
C="curl -sk -u root:0penBmc --max-time 30"
B=https://127.0.0.1:2443

echo '=== GET Systems/system: what does the Boot block advertise? ==='
$C $B/redfish/v1/Systems/system -o /home/key/scratch/sys.json -w 'GET HTTP %{http_code}\n'
python3 - <<'EOF'
import json
try:
    d = json.load(open('/home/key/scratch/sys.json'))
    print('Boot block:', json.dumps(d.get('Boot', {}), indent=1)[:700])
except Exception as e:
    print('parse failed:', e)
EOF

echo
echo '=== PATCH Boot.AutomaticRetryConfig = RetryAttempts (cp_setup, AUTO_REBOOT=1) ==='
$C -X PATCH -H 'Content-Type: application/json' \
  -d '{"Boot":{"AutomaticRetryConfig":"RetryAttempts"}}' \
  $B/redfish/v1/Systems/system -o /home/key/scratch/p1.json -w 'PATCH HTTP %{http_code}\n'
head -c 600 /home/key/scratch/p1.json; echo

echo
echo '=== PATCH Boot.AutomaticRetryConfig = Disabled (cp_setup, AUTO_REBOOT=0) ==='
$C -X PATCH -H 'Content-Type: application/json' \
  -d '{"Boot":{"AutomaticRetryConfig":"Disabled"}}' \
  $B/redfish/v1/Systems/system -o /home/key/scratch/p2.json -w 'PATCH HTTP %{http_code}\n'
head -c 600 /home/key/scratch/p2.json; echo

S="sshpass -p 0penBmc ssh -n -p 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@127.0.0.1"
echo
echo '=== bmcweb journal, last 20 lines (should show the D-Bus error behind the 500) ==='
$S 'journalctl -u bmcweb --no-pager -n 20'
echo
echo '=== mapper: who owns the auto_reboot settings object? ==='
$S 'mapper get-service /xyz/openbmc_project/control/host0/auto_reboot; echo mapper_rc=$?'
echo
echo '=== Settings tree, reboot-related objects ==='
$S 'busctl tree xyz.openbmc_project.Settings --no-pager | grep -i -B1 -A1 reboot'
echo
echo '=== direct D-Bus read of AutoReboot property ==='
$S 'busctl get-property xyz.openbmc_project.Settings /xyz/openbmc_project/control/host0/auto_reboot xyz.openbmc_project.Control.Boot.RebootPolicy AutoReboot; echo rc=$?'
echo DONE
