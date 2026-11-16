#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Compile existing AN7583 PCS sources; no device I/O or boot image.
set -eu
if [ "$#" -ne 3 ]; then
    echo "usage: $0 PREPARED_KERNEL NEW_OUTPUT CROSS_COMPILE_PREFIX" >&2
    exit 2
fi
source_dir=$(realpath "$1")
output=$2
cross=$3
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
for path in "$source_dir" "$output" "$cross"; do
    case "$path" in
        *[[:space:]]*) echo "Kernel/output/tool paths must not contain whitespace" >&2; exit 2 ;;
    esac
done
test ! -e "$output"
mkdir -p "$output"
output=$(realpath "$output")
export KBUILD_BUILD_TIMESTAMP='2026-11-16 00:00:00 UTC'
export KBUILD_BUILD_USER=vb235v KBUILD_BUILD_HOST=research KBUILD_BUILD_VERSION=1
make -C "$source_dir" O="$output" ARCH=arm64 CROSS_COMPILE="$cross" allnoconfig
cp "$script_dir/pcs-compile.config" "$output/pcs-compile.fragment"
"$source_dir/scripts/kconfig/merge_config.sh" -m -O "$output" \
    "$output/.config" "$output/pcs-compile.fragment"
make -C "$source_dir" O="$output" ARCH=arm64 CROSS_COMPILE="$cross" olddefconfig
for symbol in PCS_AIROHA PCS_AIROHA_AN7583 PHYLINK NVMEM; do
    if ! grep -qx "CONFIG_$symbol=y" "$output/.config"; then
        echo "Resolved configuration lacks CONFIG_$symbol=y" >&2
        exit 1
    fi
done
make -C "$source_dir" O="$output" ARCH=arm64 CROSS_COMPILE="$cross" -j4 \
    drivers/net/pcs/airoha/pcs-airoha-common.o \
    drivers/net/pcs/airoha/pcs-an7583.o
echo "AN7583 PCS OBJECT COMPILATION COMPLETE. No image built or device accessed."
