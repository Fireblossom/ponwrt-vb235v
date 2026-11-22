#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Offline RAM experiment only; no shared make/source mutation or device IO.
set -eu
test "$#" = 2
tree=$(realpath "$1")
out=$(realpath -m "$2")
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
workspace=$(realpath "$here/../../../../..")
test ! -e "$out"
mkdir -p "$out-tools"
cross="$tree/staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin/aarch64-openwrt-linux-musl-"
cp "$here/../m81-cpu-integration/cpu-observe.sh" "$out-tools/vb235v-cpu-observe"
cp "$here/../m81-cpu-integration/cpu-cycle.sh" "$out-tools/vb235v-cpu-cycle"
STAGING_DIR="$tree/staging_dir" "${cross}gcc" -O2 -std=c11 -Wall -Wextra -Werror -pthread \
    "$here/../../tools/vb235v_smp_probe.c" -o "$out-tools/vb235v-cpu-smp-probe"
kd="$tree/build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v"
PATH="$kd/linux-6.18.60/scripts/dtc:$PATH" python3 "$here/mini-fit.py" \
    --normal-fit "$workspace/VB235v-PonWrt-Persistent-M75-v1/kernel.itb" \
    --sha256 3c1528eeb4cb4ea2e8494d39a61873cf6ed605445dd803e1a138118b632e42cc \
    --normal-elf "$kd/vmlinux.debug" \
    --rootfs "$tree/staging_dir/target-aarch64_cortex-a53_musl/root-airoha" \
    --private-overlay "$tree/files" \
    --cpu-tools "$out-tools" --readelf "${cross}readelf" --strip "${cross}strip" \
    --mkimage "$tree/staging_dir/host/bin/mkimage" \
    --m75-module-experiment --cpu-module /home/duanx/m81-cpu-isolated/vb235v-cpufreq.ko \
    --cpu-module-sha256 e55f925a7664966b5741efd1d4c70f3db411c27e58114ee73a3825c11122cc9e \
    --output "$out"
