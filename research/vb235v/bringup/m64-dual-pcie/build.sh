#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
set -eu
PATH=$(python3 -c "import os; print(':'.join(p for p in os.environ['PATH'].split(':') if p.startswith('/') and not any(c.isspace() for c in p)))")
export PATH
test "$#" -ge 1 && test "$#" -le 2
tree=$(realpath "$1")
jobs=${2:-4}
case "$jobs" in ''|*[!0-9]*|0) exit 2 ;; esac
resources=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec 9>"$tree/.m55-build.lock"
flock -n 9
python3 "$resources/prepare.py" "$tree"
cd "$tree"
mkdir -p m64-logs
make defconfig >m64-logs/defconfig.log 2>&1
grep -qx 'CONFIG_TARGET_airoha_vb235v_DEVICE_tplink_vb235v-ram-dual-pcie=y' .config
make -j"$jobs" >m64-logs/build.log 2>&1
python3 "$resources/../../tools/audit_ponwrt_dual_pcie.py" \
 --fit bin/targets/airoha/vb235v/ponwrt-airoha-vb235v-tplink_vb235v-ram-dual-pcie-initramfs-ram.itb \
 --kernel-config build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60/.config \
 --initramfs build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60/usr/initramfs_data.cpio \
 --output m64-artifact-audit.json
