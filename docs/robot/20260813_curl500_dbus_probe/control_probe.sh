#!/bin/bash
# Control experiment: the same D-Bus write that fails for host0 must SUCCEED
# for host1 (write-back of the current value, so no state actually changes).
# If so, the mechanism works and only the host0 object is missing.
C="curl -sk -u root:0penBmc --max-time 30"
B=https://127.0.0.1:2443
S="sshpass -p 0penBmc ssh -n -p 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR root@127.0.0.1"

echo '=== Redfish Systems collection: what members does bmcweb expose? ==='
$C $B/redfish/v1/Systems -o /home/key/scratch/systems_col.json -w 'GET HTTP %{http_code}\n'
python3 -c "import json; d=json.load(open('/home/key/scratch/systems_col.json')); print(json.dumps(d.get('Members'), indent=1)); print('Members@odata.count:', d.get('Members@odata.count'))"

echo
echo '=== control: read host1 AutoReboot (should work) ==='
$S 'busctl get-property xyz.openbmc_project.Settings /xyz/openbmc_project/control/host1/auto_reboot xyz.openbmc_project.Control.Boot.RebootPolicy AutoReboot; echo read_rc=$?'

echo
echo '=== control: write host1 AutoReboot back to its current value (no state change) ==='
$S "v=\$(busctl get-property xyz.openbmc_project.Settings /xyz/openbmc_project/control/host1/auto_reboot xyz.openbmc_project.Control.Boot.RebootPolicy AutoReboot | awk '{print \$2}'); echo current=\$v; busctl set-property xyz.openbmc_project.Settings /xyz/openbmc_project/control/host1/auto_reboot xyz.openbmc_project.Control.Boot.RebootPolicy AutoReboot b \$v; echo write_rc=\$?"

echo
echo '=== same read for host0 (for the record) ==='
$S 'busctl get-property xyz.openbmc_project.Settings /xyz/openbmc_project/control/host0/auto_reboot xyz.openbmc_project.Control.Boot.RebootPolicy AutoReboot; echo read_rc=$?'

echo
echo '=== provenance: BMC build id ==='
$S 'cat /etc/os-release | head -n 6'
echo DONE
