#!/bin/bash
cd /home/key/work/openbmc-thermal-loop || exit 1
export QEMU_SERIAL=file:/home/key/scratch/boot-0813red.log
exec ./harness/qemu/run_bmc.sh bletchley >/home/key/scratch/run_bmc-0813red.out 2>&1 </dev/null
