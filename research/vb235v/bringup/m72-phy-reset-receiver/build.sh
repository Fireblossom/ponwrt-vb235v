#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
set -eu
test "$#" -ge 1 && test "$#" -le 2
tree=$(realpath "$1"); jobs=${2:-4}
case "$jobs" in ''|*[!0-9]*|0) exit 2 ;; esac
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PATH=$(python3 -c "import os; print(':'.join(p for p in os.environ['PATH'].split(':') if p.startswith('/') and not any(c.isspace() for c in p)))")
export PATH
exec 9>"$tree/.m55-build.lock"
flock -n 9
python3 "$here/prepare.py" "$tree"
cd "$tree"; mkdir -p m72-logs
make -j"$jobs" >m72-logs/build.log 2>&1
python3 "$here/verify_sources.py" "$tree" --output m72-source-audit.json
python3 "$here/../../tools/audit_ponwrt_multigig.py" \
 --fit bin/targets/airoha/vb235v/ponwrt-airoha-vb235v-tplink_vb235v-ram-multigig-initramfs-ram.itb \
 --kernel-config build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60/.config \
 --initramfs build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60/usr/initramfs_data.cpio \
 --output m72-artifact-audit.json
