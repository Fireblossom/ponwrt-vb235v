#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
set -eu
test "$#" = 2
tree=$(realpath "$1"); out=$2
test ! -e "$out"; mkdir -p "$out"; out=$(realpath "$out")
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cp "$here/vb235v_phy_detail.c" "$here/vb235v_phy_hard_reset.c" "$out/"
printf 'obj-m += vb235v_phy_detail.o vb235v_phy_hard_reset.o\n' >"$out/Makefile"
export STAGING_DIR="$tree/staging_dir"
export PATH="$tree/staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin:$PATH"
make -C "$tree/build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60" \
 M="$out" ARCH=arm64 CROSS_COMPILE=aarch64-openwrt-linux-musl- modules
