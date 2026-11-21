#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Usage: check.sh PREPARED_M75_TREE OWN_EMPTY_OR_PRIOR_M78_CHECK_DIRECTORY
# All build output stays in the second directory. Never installs a module.
set -eu
src=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
tree=$(realpath "$1")
work=$(realpath -m "$2")
kernel="$tree/build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60"
case "$work" in "$tree"|"$tree"/*|/|"$src") echo 'Need a separate M78 work directory' >&2; exit 1;; esac
mkdir -p "$work"
cp "$src/vb235v-cpufreq.c" "$src/vb235v-cpufreq-contract.h" "$src/test-contract.c" "$work/"
cc -std=c11 -O2 -Wall -Wextra -Werror -fsanitize=undefined "$work/test-contract.c" -o "$work/test-contract"
"$work/test-contract"
printf '%s\n' 'obj-m += vb235v-cpufreq.o' > "$work/Makefile"
export STAGING_DIR="$tree/staging_dir"
make -C "$kernel" M="$work" ARCH=arm64 \
 CROSS_COMPILE="$tree/staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin/aarch64-openwrt-linux-musl-" \
 modules
python3 -c 'import pathlib,sys; compile(pathlib.Path(sys.argv[1]).read_text(), sys.argv[1], "exec")' "$src/prepare.py"
python3 "$src/test-prepare.py" "$tree"
printf '%s\n' 'M78 host contract and exact-kernel external module build passed; no device accessed.'
