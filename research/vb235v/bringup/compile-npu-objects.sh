#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Input must be a separately prepared and development-patched kernel tree.
# Builds three objects only. No module loading, linking an Image or device I/O.
set -eu
if [ "$#" -ne 3 ]; then
    echo "usage: $0 PREPARED_PATCHED_KERNEL NEW_OUTPUT CROSS_COMPILE_PREFIX" >&2
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
cp "$script_dir/npu-compile.config" "$output/npu-compile.fragment"
"$source_dir/scripts/kconfig/merge_config.sh" -m -O "$output" \
    "$output/.config" "$output/npu-compile.fragment"
make -C "$source_dir" O="$output" ARCH=arm64 CROSS_COMPILE="$cross" olddefconfig
for symbol in NET_AIROHA NET_AIROHA_NPU FW_LOADER; do
    grep -qx "CONFIG_$symbol=y" "$output/.config"
done
make -C "$source_dir" O="$output" ARCH=arm64 CROSS_COMPILE="$cross" -j4 \
    drivers/net/ethernet/airoha/airoha_npu.o \
    drivers/net/ethernet/airoha/airoha_eth.o \
    drivers/net/ethernet/airoha/airoha_ppe.o
echo "NPU/ETHERNET OBJECT COMPILATION COMPLETE. No boot image was built or loaded."
