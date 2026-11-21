#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
set -eu
test "$#" = 2
tree=$(realpath "$1"); out=$2
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
lib="$tree/build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60/scripts/dtc/libfdt"
cross="$tree/staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin/aarch64-openwrt-linux-musl-"
export STAGING_DIR="$tree/staging_dir"
"${cross}gcc" -O2 -std=c11 -D_GNU_SOURCE -Wall -Wextra -Werror \
 -I"$lib" -I"$here" "$here/image-check.c" \
 "$lib/fdt.c" "$lib/fdt_ro.c" "$lib/fdt_strerror.c" \
 -o "$out"
