# SPDX-License-Identifier: GPL-2.0-only
define Device/tplink_vb235v-ram-npu
  DEVICE_VENDOR := TP-Link
  DEVICE_MODEL := LinkBox 7 VB235v
  DEVICE_VARIANT := RAM NPU development
  DEVICE_DTS := an7583-tplink_vb235v-ram-npu
  SUPPORTED_DEVICES := tplink,vb235v-ram-npu-development
  KERNEL := kernel-bin | lzma | vb235v-ram-fit
  KERNEL_INITRAMFS := kernel-bin | lzma | vb235v-ram-fit
  KERNEL_INITRAMFS_SUFFIX := -ram.itb
  KERNEL_LOADADDR := 0x80200000
  KERNEL_ENTRY := 0x80200000
  IMAGES :=
  IMAGE/sysupgrade.bin :=
  ARTIFACTS :=
endef
TARGET_DEVICES += tplink_vb235v-ram-npu
