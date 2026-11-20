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
cd "$tree"
grep -qx 'CONFIG_TARGET_airoha_vb235v_DEVICE_tplink_vb235v-ram-lan=y' .config
mkdir -p m60-logs
cp -p .config m60-logs/config-before
./scripts/kconfig.pl + .config "$resources/wifi-compile.config" >.config.m60
mv .config.m60 .config
make defconfig >m60-logs/defconfig.log 2>&1
cp -p .config m60-logs/config-selected
export CURL_OPTIONS=${CURL_OPTIONS:---max-time 180 --speed-time 15 --speed-limit 1024}
make -j"$jobs" package/kernel/mt76/download >m60-logs/download.log 2>&1
# Wi-Fi adds kernel crypto dependencies: build those before packaging modules.
make -j"$jobs" target/linux/compile >m60-logs/kernel-rebuild.log 2>&1
make -j"$jobs" package/kernel/mt76/compile >m60-logs/compile.log 2>&1
python3 "$resources/../../tools/audit_mt7990_build.py" "$tree" --output m60-artifact-audit.json
