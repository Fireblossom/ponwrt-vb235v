# SPDX-License-Identifier: GPL-2.0-only
define Build/vb235v-system-fit
  python3 $(TOPDIR)/target/linux/airoha/image/mkits-vb235v-system.py \
	$@ $(KDIR)/image-$(DEVICE_DTS).dtb $@.its
  $(call Build/fit-image,lzma)
endef

define Device/tplink_vb235v
  DEVICE_VENDOR := TP-Link
  DEVICE_MODEL := LinkBox 7 VB235v
  DEVICE_VARIANT := persistent development
  DEVICE_DTS := an7583-tplink_vb235v
  SUPPORTED_DEVICES := tplink,vb235v
  KERNEL_LOADADDR := 0x80200000
  KERNEL_ENTRY := 0x80200000
  KERNEL := kernel-bin | lzma | vb235v-system-fit
  KERNEL_INITRAMFS := kernel-bin | lzma | vb235v-system-fit
  KERNEL_INITRAMFS_SUFFIX := -install.itb
  BLOCKSIZE := 256k
  PAGESIZE := 4096
  IMAGE_SIZE := 80m
  IMAGES := sysupgrade.bin
  IMAGE/sysupgrade.bin := append-kernel | pad-to 128k | append-rootfs | pad-rootfs | append-metadata
endef
TARGET_DEVICES += tplink_vb235v
