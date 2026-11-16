#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Apply 955 then 956 to the pinned upstream source. No router access.
set -eu
if [ "$#" -ne 2 ]; then
 echo "usage: CROSS_COMPILE=/native/tools/aarch64-linux-gnu- $0 SOURCE NEW_OUTPUT" >&2
 exit 2
fi
: "${CROSS_COMPILE:?Set a native AArch64 compiler prefix without spaces}"
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
verify_source(src,json.loads((research/'findings/uboot-nand-selftest-source.json').read_text()))
PY
export SOURCE_DATE_EPOCH=1794787200
mkdir -p "$out"
for mode in standard selftest; do
 mkdir "$out/$mode"
 make -C "$src" O="$out/$mode" an7583_vb235v_recovery_defconfig >"$out/$mode-config.log" 2>&1
 if [ "$mode" = selftest ]; then
  "$src/scripts/config" --file "$out/$mode/.config" -e VB235V_NAND_SELFTEST
 fi
 make -C "$src" O="$out/$mode" olddefconfig >>"$out/$mode-config.log" 2>&1
 if grep -q '^CONFIG_ENV_IS_IN_.*=y$' "$out/$mode/.config"; then exit 1; fi
 if ! make -C "$src" O="$out/$mode" -j"${JOBS:-8}" >"$out/$mode-build.log" 2>&1; then
  tail -n 50 "$out/$mode-build.log" >&2
  exit 1
 fi
done
if grep -q '^CONFIG_VB235V_NAND_SELFTEST=y$' "$out/standard/.config"; then exit 1; fi
grep -q '^CONFIG_VB235V_NAND_SELFTEST=y$' "$out/selftest/.config"
if "${CROSS_COMPILE}nm" "$out/standard/u-boot" | grep -q 'vb_storage_nand_selftest'; then exit 1; fi
"${CROSS_COMPILE}nm" "$out/selftest/u-boot" | grep 'vb_storage_nand_selftest'
python3 -B "$research/tools/check_uboot_nand_selftest.py" --source "$src" --build "$out/standard" --output "$out/storage-selftest-checks.txt"
python3 -B "$research/tools/check_uboot_full_web.py" --source "$src" --output "$out/web-checks.txt"
python3 -B "$research/tools/check_uboot_full_dhcp.py" --source "$src" >"$out/dhcp-checks.txt"
for mode in standard selftest; do
 python3 -B "$research/tools/pack_uboot_full_recovery.py" --build "$out/$mode" --output "$out/package-$mode"
done
echo "RAM packages: $out/package-standard and $out/package-selftest; no flashing performed"
