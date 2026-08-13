#!/bin/bash
# Poll until bmcweb answers on 2443, or fail with diagnostics.
for i in $(seq 1 36); do
  if [ "$i" -gt 3 ] && ! pgrep -x qemu-system-arm >/dev/null; then
    echo "QEMU_DEAD at loop $i -- launcher stderr:"
    tail -n 15 /home/key/scratch/run_bmc-0813red.out 2>/dev/null
    exit 2
  fi
  code=$(curl -sk -o /dev/null -w '%{http_code}' --max-time 5 -u root:0penBmc https://127.0.0.1:2443/redfish/v1/ 2>/dev/null)
  if [ "$code" = "200" ]; then
    echo "BMCWEB_UP after ~$((i * 10))s"
    exit 0
  fi
  sleep 10
done
echo "TIMEOUT_360s -- last serial lines:"
tail -n 20 /home/key/scratch/boot-0813red.log 2>/dev/null
exit 1
