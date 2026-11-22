#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# CPU mini initramfs PID1. No UCI/procd, flash mount, network configuration,
# module loading, CPU SET, ADC access, AVS access or upgrade action.
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
mkdir -p /proc /sys /dev /tmp
mount -t proc proc /proc
mount -t sysfs sysfs /sys
mount -t devtmpfs devtmpfs /dev
mount -t tmpfs -o mode=1777,nosuid,nodev tmpfs /tmp
printf '\n%s\n' 'M81 CPU observation RAM: no flash mounted; CPU transitions remain disabled.'
printf '%s\n' 'Run /usr/libexec/vb235v-cpu-observe first. Network/PHY setup remains a separate coordinated step.'
# Keep PID1 alive if the serial shell exits. /dev/console uses the already
# verified kernel console; no UART clock or baud registers are changed here.
while :; do
 /bin/sh -i < /dev/console > /dev/console 2>&1
 sleep 1
done
