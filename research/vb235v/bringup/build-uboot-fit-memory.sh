#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Apply 955, 956 and 957 to the pristine pinned source before running.
set -eu
if [ "$#" -ne 2 ]; then echo "usage: $0 SOURCE NEW_OUTPUT" >&2; exit 2; fi
: "${CROSS_COMPILE:?Set the native AArch64 compiler prefix}"
src=$(realpath "$1")
out=$(realpath -m "$2")
research=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ -e "$out" ]; then echo "Output must not exist: $out" >&2; exit 2; fi
python3 -B - "$src" "$research" <<'PY'
import json,sys
from pathlib import Path
src,research=map(Path,sys.argv[1:])
sys.path.insert(0,str(research/'tools'))
from check_uboot_ram import verify_source
verify_source(src,json.loads((research/'findings/uboot-fit-memory-source.json').read_text()))
PY
export SOURCE_DATE_EPOCH=1794787200
mkdir -p "$out/build"
make -C "$src" O="$out/build" an7583_vb235v_recovery_defconfig >"$out/config.log" 2>&1
make -C "$src" O="$out/build" olddefconfig >>"$out/config.log" 2>&1
if grep -q '^CONFIG_ENV_IS_IN_.*=y$\|^CONFIG_VB235V_NAND_SELFTEST=y$' "$out/build/.config"; then exit 1; fi
if ! make -C "$src" O="$out/build" -j"${JOBS:-8}" >"$out/build.log" 2>&1; then
 tail -n 50 "$out/build.log" >&2; exit 1
fi
python3 -B "$research/tools/check_uboot_stock_load_memory.py" --dtb "$out/build/u-boot.dtb" --output "$out/memory-checks.json"
python3 -B "$research/tools/check_uboot_nand_selftest.py" --source "$src" --build "$out/build" --output "$out/storage-checks.txt"
python3 -B "$research/tools/check_uboot_full_web.py" --source "$src" --output "$out/web-checks.txt"
python3 -B "$research/tools/check_uboot_full_dhcp.py" --source "$src" >"$out/dhcp-checks.txt"
python3 -B "$research/tools/pack_uboot_full_recovery.py" --build "$out/build" --output "$out/package"
echo "Recovery RAM candidate and memory checks: $out; no router access"
