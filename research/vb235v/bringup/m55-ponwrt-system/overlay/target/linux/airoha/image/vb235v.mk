# SPDX-License-Identifier: GPL-2.0-only
define Build/vb235v-ram-fit
  python3 $(TOPDIR)/target/linux/airoha/image/mkits-vb235v.py \
	$@ $(KDIR)/image-$(DEVICE_DTS).dtb $@.its
  $(call Build/fit-image,lzma)
endef

define Device/tplink_vb235v-ram
  DEVICE_VENDOR := TP-Link
  DEVICE_MODEL := LinkBox 7 VB235v
  DEVICE_VARIANT := RAM development
  DEVICE_DTS := an7583-tplink_vb235v-ram
  SUPPORTED_DEVICES := tplink,vb235v-ram-development
  KERNEL_LOADADDR := 0x80200000
  KERNEL_INITRAMFS := kernel-bin | lzma | vb235v-ram-fit
  KERNEL_INITRAMFS_SUFFIX := -ram.itb
  BLOCKSIZE := 256k
  PAGESIZE := 4096
  IMAGES :=
  ARTIFACTS :=
endef
TARGET_DEVICES += tplink_vb235v-ram
