#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
set -eu
test "$#" -ge 3 && test "$#" -le 4
tree=$(realpath "$1"); npu=$(realpath "$2"); eeprom=$(realpath "$3"); jobs=${4:-4}
case "$jobs" in ''|*[!0-9]*|0) exit 2 ;; esac
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PATH=$(python3 -c "import os; print(':'.join(p for p in os.environ['PATH'].split(':') if p.startswith('/') and not any(c.isspace() for c in p)))")
export PATH
exec 9>"$tree/.m55-build.lock"
flock -n 9
python3 "$here/prepare.py" "$tree" --npu-inputs "$npu" --wifi-eeprom "$eeprom"
cd "$tree"
mkdir -p m70-logs
make defconfig >m70-logs/defconfig.log 2>&1
make -j"$jobs" >m70-logs/build.log 2>&1
python3 "$here/../../tools/audit_ponwrt_accel.py" \
 --fit bin/targets/airoha/vb235v/ponwrt-airoha-vb235v-tplink_vb235v-ram-accel-initramfs-ram.itb \
 --kernel-config build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60/.config \
 --initramfs build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60/usr/initramfs_data.cpio \
 --output m70-artifact-audit.json
