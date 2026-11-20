# SPDX-License-Identifier: GPL-2.0-only
ARCH:=aarch64
SUBTARGET:=vb235v
BOARDNAME:=TP-LinkBox 7 (VB235v development)
CPU_TYPE:=cortex-a53
KERNELNAME:=Image dtbs

# An independent subtarget prevents inheriting Nokia's ECC/upgrade policy.
DEFAULT_PACKAGES := $(filter-out mtd uboot-envtools kmod-leds-gpio kmod-gpio-button-hotplug,$(DEFAULT_PACKAGES))

define Target/Description
  VB235v board bring-up with the complete PonWrt userspace in RAM.
  Persistent firmware and peripheral support require separate validation.
endef
