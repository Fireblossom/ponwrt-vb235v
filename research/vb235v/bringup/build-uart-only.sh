#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Local build only. This script does not contact or boot the router.
set -eu

if [ "$#" -ne 3 ]; then
    echo "usage: $0 VERIFIED_LINUX_SOURCE NEW_BUILD_DIRECTORY CROSS_COMPILE_PREFIX" >&2
    exit 2
fi
kernel_src=$(realpath "$1")
build_dir=$2
cross_prefix=$3
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
for make_path in "$kernel_src" "$build_dir" "$cross_prefix"; do
    case "$make_path" in
        *[[:space:]]*) echo "Kernel, build and tool-prefix paths must not contain whitespace" >&2; exit 2 ;;
    esac
done
test ! -e "$build_dir"
mkdir -p "$build_dir"
build_dir=$(realpath "$build_dir")
artifacts="$build_dir/artifacts"
mkdir "$artifacts"

export KBUILD_BUILD_TIMESTAMP='2026-11-16 00:00:00 UTC'
export KBUILD_BUILD_USER=vb235v
export KBUILD_BUILD_HOST=research
export KBUILD_BUILD_VERSION=1
export KCONFIG_NOTIMESTAMP=1

"${cross_prefix}gcc" -nostdlib -static -no-pie -Wl,--build-id=none \
    -o "$artifacts/init" "$script_dir/uart-init.S"
cat > "$artifacts/initramfs.list" <<EOF
dir /dev 755 0 0
nod /dev/console 600 0 0 c 5 1
file /init $artifacts/init 755 0 0
EOF

make -C "$kernel_src" O="$build_dir" ARCH=arm64 CROSS_COMPILE="$cross_prefix" allnoconfig
# Upstream merge_config.sh splits its fragment list on spaces internally.
cp "$script_dir/uart-only.config" "$artifacts/uart-only.fragment"
"$kernel_src/scripts/kconfig/merge_config.sh" -m -O "$build_dir" \
    "$build_dir/.config" "$artifacts/uart-only.fragment"
"$kernel_src/scripts/config" --file "$build_dir/.config" \
    --set-str INITRAMFS_SOURCE "$artifacts/initramfs.list"
make -C "$kernel_src" O="$build_dir" ARCH=arm64 CROSS_COMPILE="$cross_prefix" olddefconfig
python3 "$script_dir/../tools/audit_uart_bringup.py" --config "$build_dir/.config"
dtc -I dts -O dtb -o "$artifacts/vb235v-uart-only.dtb" "$script_dir/vb235v-uart-only.dts"
python3 "$script_dir/../tools/audit_uart_bringup.py" \
    --config "$build_dir/.config" --dtb "$artifacts/vb235v-uart-only.dtb" \
    --output "$artifacts/offline-policy.json"
make -C "$kernel_src" O="$build_dir" ARCH=arm64 CROSS_COMPILE="$cross_prefix" -j4 Image
cp "$build_dir/arch/arm64/boot/Image" "$artifacts/Image"
echo "BUILD COMPLETE. Local artifacts only; no hardware boot was performed."
