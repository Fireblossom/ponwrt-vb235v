#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Build host only; no network connection to the board and no flash operations.
set -eu
# WSL inherits Windows PATH entries. OpenWrt's make recipes and find -execdir
# require absolute, whitespace-free components even when the worktree is clean.
PATH=$(python3 -c "import os; print(':'.join(p for p in os.environ['PATH'].split(':') if p.startswith('/') and not any(c.isspace() for c in p)))")
export PATH
if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
 echo 'usage: build.sh PINNED_PONWRT_WORKTREE [JOBS]' >&2
 exit 2
fi
tree=$(realpath "$1")
jobs=${2:-4}
case "$jobs" in ''|*[!0-9]*|0) exit 2 ;; esac
case "$tree" in *[[:space:]]*) echo 'Use a Linux build directory without spaces' >&2; exit 2 ;; esac
resources=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
test "$(git -C "$tree" rev-parse HEAD)" = dcf140cb1d5d2c15c1d7c353c95c4c2a56629820
command -v flock >/dev/null
exec 9>"$tree/.m55-build.lock"
flock -n 9 || { echo 'Another M55 build owns this directory' >&2; exit 1; }
if [ ! -f "$tree/.config" ]; then
 python3 "$resources/prepare.py" "$tree"
fi
cd "$tree"
mkdir -p m55-logs
export CURL_OPTIONS=${CURL_OPTIONS:---max-time 180 --speed-time 15 --speed-limit 1024}
make defconfig >m55-logs/defconfig.log 2>&1
grep -qx 'CONFIG_TARGET_airoha_vb235v_DEVICE_tplink_vb235v-ram=y' .config
grep -qx 'CONFIG_TARGET_ROOTFS_INITRAMFS=y' .config
make -j"$jobs" download >m55-logs/download.log 2>&1
make -j"$jobs" >m55-logs/build.log 2>&1
set -- bin/targets/airoha/vb235v/*tplink_vb235v-ram*ram.itb
test "$#" = 1 && test -f "$1"
fit=$1
set -- build_dir/target-*/linux-airoha_vb235v/linux-6.18.60/.config
test "$#" = 1 && test -f "$1"
kconfig=$1
initramfs=$(dirname "$kconfig")/usr/initramfs_data.cpio
test -f "$initramfs"
python3 "$resources/../../tools/audit_ponwrt_ram.py" --fit "$fit" \
 --kernel-config "$kconfig" --initramfs "$initramfs" --output m55-artifact-audit.json
echo 'RAM image compiled and checked offline; hardware boot remains a separate result.'
