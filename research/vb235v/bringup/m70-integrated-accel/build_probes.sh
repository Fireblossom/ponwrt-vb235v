#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
set -eu
test "$#" -eq 2
tree=$(realpath "$1"); out=$(realpath -m "$2")
test ! -e "$out"
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
kernel="$tree/build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60"
mkdir -p "$out"
python3 "$here/crypto_vectors.py" "$out"
cp "$here/vb235v_crypto_probe.c" "$here/vb235v_mdio_probe.c" "$out/"
cp "$here/../../tools/vb235v_npu_probe.c" "$out/"
printf '%s\n' 'obj-m += vb235v_crypto_probe.o vb235v_mdio_probe.o vb235v_npu_probe.o' >"$out/Makefile"
export STAGING_DIR="$tree/staging_dir"
PATH="$tree/staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin:/usr/bin:/bin"
export PATH
make -C "$kernel" M="$out" ARCH=arm64 CROSS_COMPILE=aarch64-openwrt-linux-musl- modules
sha256sum "$kernel/.config" "$out/"*.ko >"$out/build-hashes.txt"
