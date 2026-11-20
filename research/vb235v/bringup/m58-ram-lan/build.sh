#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
set -eu
PATH=$(python3 -c "import os; print(':'.join(p for p in os.environ['PATH'].split(':') if p.startswith('/') and not any(c.isspace() for c in p)))")
export PATH
test "$#" -ge 1 && test "$#" -le 2
tree=$(realpath "$1")
jobs=${2:-4}
case "$jobs" in ''|*[!0-9]*|0) exit 2 ;; esac
case "$tree" in *[[:space:]]*) echo 'Use a Linux worktree without spaces' >&2; exit 2 ;; esac
resources=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
test "$(git -C "$tree" rev-parse HEAD)" = dcf140cb1d5d2c15c1d7c353c95c4c2a56629820
exec 9>"$tree/.m55-build.lock"
flock -n 9 || { echo 'Another development build owns this tree' >&2; exit 1; }
if ! grep -qx 'CONFIG_TARGET_airoha_vb235v_DEVICE_tplink_vb235v-ram-lan=y' "$tree/.config" 2>/dev/null; then
 python3 "$resources/prepare.py" "$tree"
fi
cd "$tree"
mkdir -p m58-logs
export CURL_OPTIONS=${CURL_OPTIONS:---max-time 180 --speed-time 15 --speed-limit 1024}
make defconfig >m58-logs/defconfig.log 2>&1
grep -qx 'CONFIG_TARGET_airoha_vb235v_DEVICE_tplink_vb235v-ram-lan=y' .config
make -j"$jobs" download >m58-logs/download.log 2>&1
make -j"$jobs" >m58-logs/build.log 2>&1
set -- bin/targets/airoha/vb235v/*tplink_vb235v-ram-lan*ram.itb
test "$#" = 1 && test -f "$1"
fit=$1
set -- build_dir/target-*/linux-airoha_vb235v/linux-6.18.60/.config
test "$#" = 1 && test -f "$1"
kconfig=$1
python3 "$resources/../../tools/audit_ponwrt_lan.py" --fit "$fit" \
 --kernel-config "$kconfig" --initramfs "$(dirname "$kconfig")/usr/initramfs_data.cpio" \
 --output m58-artifact-audit.json
echo 'Separate single-port RAM LAN image checked offline; hardware evidence is independent.'
