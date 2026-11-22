#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Parent must grant a shared-tree lease before invoking this script.
set -eu
test "$#" = 3 || { echo 'usage: build.sh TREE NEW_OUTPUT JOBS' >&2; exit 2; }
tree=$(realpath "$1");out=$2;jobs=$3
case "$jobs" in ''|*[!0-9]*|0) exit 2 ;; esac
test ! -e "$out"
mkdir -p "$out"
out=$(realpath "$out")
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PATH=$(python3 -c "import os; print(':'.join(p for p in os.environ['PATH'].split(':') if p.startswith('/') and not any(c.isspace() for c in p)))")
export PATH
exec 9>"$tree/.m55-build.lock"
flock -n 9
python3 "$here/prepare.py" "$tree" --check-only > "$out/preflight.json"
python3 "$here/prepare.py" "$tree" > "$out/prepare.log" 2>&1
cd "$tree"
make defconfig > "$out/defconfig.log" 2>&1
# These local package sources changed; fresh preparation must copy the locked C
# inputs and fresh package metadata must include the corrected dropbear init.
make -j1 package/ponwrt/diagnostics/clean package/ponwrt/dsl-runtime/clean package/network/services/dropbear/clean > "$out/package-clean.log" 2>&1
make -j"$jobs" > "$out/build.log" 2>&1
python3 "$here/audit.py" "$tree" "$out"
printf 'M83 build and artifact audit completed; no installation dispatched\n'
