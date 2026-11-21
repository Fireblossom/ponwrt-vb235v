#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
set -eu
test "$#" -eq 2
tree=$(realpath "$1"); out=$(realpath -m "$2")
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
sh "$here/../m70-integrated-accel/build_probes.sh" "$tree" "$out"
cp "$here/vb235v_phy_status.c" "$out/"
printf '%s\n' 'obj-m += vb235v_phy_status.o' >>"$out/Makefile"
export STAGING_DIR="$tree/staging_dir"
export PATH="$tree/staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin:/usr/bin:/bin"
make -C "$tree/build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60" \
 M="$out" ARCH=arm64 CROSS_COMPILE=aarch64-openwrt-linux-musl- modules
sha256sum "$out/"*.ko >"$out/all-module-hashes.txt"
