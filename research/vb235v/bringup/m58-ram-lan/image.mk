# SPDX-License-Identifier: GPL-2.0-only
define Device/tplink_vb235v-ram-lan
  DEVICE_VENDOR := TP-Link
  DEVICE_MODEL := LinkBox 7 VB235v
  DEVICE_VARIANT := RAM LAN development
  DEVICE_DTS := an7583-tplink_vb235v-ram-lan
  SUPPORTED_DEVICES := tplink,vb235v-ram-lan-development
  KERNEL_LOADADDR := 0x80200000
  KERNEL_INITRAMFS := kernel-bin | lzma | vb235v-ram-fit
  KERNEL_INITRAMFS_SUFFIX := -ram.itb
  BLOCKSIZE := 256k
  PAGESIZE := 4096
  IMAGES :=
  ARTIFACTS :=
endef
TARGET_DEVICES += tplink_vb235v-ram-lan
