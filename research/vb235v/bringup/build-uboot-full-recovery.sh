#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Apply cumulative patch 955 to the pinned pristine revision before running.
set -eu
if [ "$#" -ne 2 ]; then
 echo "usage: CROSS_COMPILE=/native/tools/aarch64-linux-gnu- $0 SOURCE NEW_OUTPUT" >&2
 exit 2
fi
: "${CROSS_COMPILE:?Set a native AArch64 compiler prefix without spaces}"
src=$(realpath "$1")
out=$(realpath -m "$2")
research=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ -e "$out" ]; then
 echo "Output must not exist: $out" >&2
 exit 2
fi
python3 -B - "$src" "$research" <<'PY'
import json,sys
from pathlib import Path
src,research=map(Path,sys.argv[1:])
sys.path.insert(0,str(research/'tools'))
from check_uboot_ram import verify_source
verify_source(src,json.loads((research/'findings/uboot-full-source.json').read_text()))
PY
export SOURCE_DATE_EPOCH=1794787200
mkdir -p "$out/build"
make -C "$src" O="$out/build" an7583_vb235v_recovery_defconfig >"$out/config.log" 2>&1
make -C "$src" O="$out/build" olddefconfig >>"$out/config.log" 2>&1
if grep -q '^CONFIG_ENV_IS_IN_.*=y$' "$out/build/.config"; then
 echo "Unexpected persistent environment backend" >&2
 exit 1
fi
if ! make -C "$src" O="$out/build" -j"${JOBS:-8}" >"$out/build.log" 2>&1; then
 tail -n 50 "$out/build.log" >&2
 exit 1
fi
python3 -B "$research/tools/check_uboot_full_storage.py" --source "$src" --build "$out/build" --output "$out/storage-checks.txt"
python3 -B "$research/tools/check_uboot_full_web.py" --source "$src" --output "$out/web-checks.txt"
python3 -B "$research/tools/check_uboot_full_dhcp.py" --source "$src" >"$out/dhcp-checks.txt"
cat "$out/dhcp-checks.txt"
python3 -B "$research/tools/pack_uboot_full_recovery.py" --build "$out/build" --output "$out/package"
echo "Full recovery development candidate: $out/package (RAM test image; not a FIP)"
