#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Execute ONLY on the complete original runtime. No ioctl, MDIO, GPIO, MMIO,
# reset, network packet, shared-memory attach or NAND write is performed.
set -eu
umask 077
awk '$2 == "/tmp" && $3 == "tmpfs" { found = 1 } END { exit !found }' /proc/mounts || {
 printf '%s\n' 'Refusing capture: /tmp has not been verified as a tmpfs mount' >&2
 exit 1
}
dest="/tmp/ponwrt-oem-inventory-$$"
mkdir "$dest"
cat /proc/version >"$dest/version"
cat /proc/cmdline >"$dest/cmdline-private"
cat /proc/net/packet >"$dest/packet-sockets-private"
cat /proc/meminfo >"$dest/meminfo"
cat /proc/mounts >"$dest/mounts-private"
if command -v dmesg >/dev/null 2>&1; then dmesg >"$dest/dmesg-private"; fi
for node in /sys/bus/mdio_bus/devices/*; do
 [ -e "$node" ] || continue
 name=${node##*/}
 mkdir "$dest/mdio-$name"
 for attr in phy_id uevent; do
  [ ! -r "$node/$attr" ] || cat "$node/$attr" >"$dest/mdio-$name/$attr"
 done
 readlink -f "$node" >"$dest/mdio-$name/path"
 readlink -f "$node/driver" >"$dest/mdio-$name/driver" || :
 readlink -f "$node/of_node" >"$dest/mdio-$name/of-node" || :
done
for node in /sys/class/net/*; do
 [ -e "$node" ] || continue
 name=${node##*/}
 mkdir "$dest/net-$name"
 for attr in ifindex iflink address type carrier; do
  [ ! -r "$node/$attr" ] || cat "$node/$attr" >"$dest/net-$name/$attr" 2>/dev/null || :
 done
 readlink -f "$node/device" >"$dest/net-$name/device" || :
done
for comm in /proc/[0-9]*/comm; do
 [ -r "$comm" ] || continue
 [ "$(cat "$comm" 2>/dev/null)" = hsm ] || continue
 pid=${comm#/proc/};pid=${pid%/comm}
 cat "/proc/$pid/cmdline" >"$dest/hsm-$pid-argv-private"
 cat "/proc/$pid/maps" >"$dest/hsm-$pid-maps-private"
 sha256sum "/proc/$pid/exe" >"$dest/hsm-$pid-sha256"
done
# Inspect availability only; no tracepoint configuration is changed here.
for trace in /sys/kernel/tracing /sys/kernel/debug/tracing; do
 [ ! -d "$trace/events/mdio" ] || ls "$trace/events/mdio" >"$dest/mdio-tracepoint-names"
done
printf '%s\n' "Private RAM-only inventory written to $dest; do not publish raw files"
