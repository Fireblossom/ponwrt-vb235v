#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
set -eu
test "$#" -ge 1 && test "$#" -le 3
tree=$(realpath "$1"); jobs=${2:-4}; revision=${3:-M73-install-v1}
case "$jobs" in ''|*[!0-9]*|0) exit 2 ;; esac
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PATH=$(python3 -c "import os; print(':'.join(p for p in os.environ['PATH'].split(':') if p.startswith('/') and not any(c.isspace() for c in p)))")
export PATH
exec 9>"$tree/.m55-build.lock"; flock -n 9
python3 "$here/prepare.py" "$tree" --revision "$revision"
mkdir -p "$tree/files/usr/libexec" "$tree/m73-logs"
sh "$here/build-checker.sh" "$tree" "$tree/files/usr/libexec/vb235v-image-check.new"
chmod 755 "$tree/files/usr/libexec/vb235v-image-check.new"
mv "$tree/files/usr/libexec/vb235v-image-check.new" "$tree/files/usr/libexec/vb235v-image-check"
cd "$tree"
make defconfig >m73-logs/defconfig.log 2>&1
make -j"$jobs" >m73-logs/build.log 2>&1
