# SPDX-License-Identifier: GPL-2.0-only
REQUIRE_IMAGE_METADATA=1
CI_UBIPART='vb235v-system'
CI_KERNPART='kernel'
CI_ROOTPART='rootfs'
CI_SKIP_KERNEL_MTD=1
RAMFS_COPY_BIN='/usr/libexec/vb235v-image-check /usr/bin/jsonfilter /usr/bin/sha256sum /bin/mktemp'

vb235v_geometry_check() {
 [ "$(board_name)" = 'tplink,vb235v' ] || return 1
 local index="$(find_mtd_index vb235v-system)"
 [ -n "$index" ] || return 1
 [ "$(cat /sys/class/mtd/mtd${index}/size)" = 83623936 ] || return 1
 [ "$(cat /sys/class/mtd/mtd${index}/erasesize)" = 262144 ] || return 1
 [ "$(cat /sys/class/mtd/mtd${index}/writesize)" = 4096 ] || return 1
 [ "$(cat /sys/class/mtd/mtd${index}/ecc_strength)" = 8 ] || return 1
}

vb235v_image_check() {
 local image="$1" out="$2"
 vb235v_geometry_check || { echo 'VB235v protected system geometry unavailable' >&2; return 1; }
 /usr/libexec/vb235v-image-check "$image" "$out" || return 1
 jsonfilter -i "$out/metadata.json" -e '@.supported_devices[*]' | grep -Fxq 'tplink,vb235v' || return 1
 (cd "$out" && sha256sum -c fit-hashes.txt) || return 1
}

platform_check_image() {
 local out result
 out="$(mktemp -d /tmp/vb235v-image-check.XXXXXX)" || return 1
 vb235v_image_check "$1" "$out"; result=$?
 rm -rf "$out"
 return "$result"
}

platform_do_upgrade() {
 local out
 out="$(mktemp -d /tmp/vb235v-upgrade.XXXXXX)" || return 1
 vb235v_image_check "$1" "$out" || return 1
 mkdir "$out/sysupgrade-tplink_vb235v" || return 1
 mv "$out/kernel.bin" "$out/sysupgrade-tplink_vb235v/kernel" || return 1
 mv "$out/rootfs.bin" "$out/sysupgrade-tplink_vb235v/root" || return 1
 tar -C "$out" -cf /tmp/vb235v-system-upgrade.tar sysupgrade-tplink_vb235v || return 1
 nand_do_upgrade /tmp/vb235v-system-upgrade.tar
}
