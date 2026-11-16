#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Build from the pinned source after applying 954-vb235v-uboot-ram-recovery.patch.
set -eu
if [ "$#" -ne 2 ]; then
 echo "usage: CROSS_COMPILE=/native/path/aarch64-linux-gnu- $0 SOURCE NEW_OUTPUT" >&2
 exit 2
fi
: "${CROSS_COMPILE:?Set the AArch64 compiler prefix (use a path without spaces)}"
src=$(realpath "$1")
out=$(realpath -m "$2")
research=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ -e "$out" ]; then
 echo "Output must not exist: $out" >&2
 exit 2
fi
if [ "$(git -C "$src" rev-parse HEAD)" != 4b91e112c345b8a4ad4f954775f3f4955f2cafb2 ]; then
 echo "Unexpected U-Boot source revision" >&2
 exit 2
fi
python3 - "$src" "$research" <<'PY'
import json,sys
from pathlib import Path
research=Path(sys.argv[2])
sys.path.insert(0,str(research/'tools'))
from check_uboot_ram import verify_source
verify_source(Path(sys.argv[1]),json.loads((research/'findings/uboot-ram-source.json').read_text()))
PY
export SOURCE_DATE_EPOCH=1794787200
mkdir -p "$out"
for mode in serial net; do
 case "$mode" in
  serial) config=an7583_vb235v_ram_defconfig ;;
  net) config=an7583_vb235v_ram_net_defconfig ;;
 esac
 mkdir "$out/$mode"
 make -C "$src" O="$out/$mode" "$config" >"$out/$mode/config.log" 2>&1
 if ! make -C "$src" O="$out/$mode" -j"${JOBS:-8}" >"$out/$mode/build.log" 2>&1; then
  tail -n 60 "$out/$mode/build.log" >&2
  exit 1
 fi
done
python3 -B "$research/tools/check_uboot_ram.py" --source "$src" \
 --serial-build "$out/serial" --net-build "$out/net" --output "$out/checks.json"
for mode in serial net; do
 python3 -B "$research/tools/pack_uboot_ram.py" --mode "$mode" \
  --build "$out/$mode" --checks "$out/checks.json" \
  --mkimage "$out/serial/tools/mkimage" --output "$out/packages/$mode"
done
echo "RAM development packages: $out/packages (not flash images)"
