#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# One supervised RAM-only 1200->500->1200 MHz pair. Never retries a SET.
# Usage: cpu-cycle.sh --run-one-pair PEER_IPV4 EGRESS_INTERFACE SMP_PROBE
set -eu
test "$#" = 4 && test "$1" = --run-one-pair || {
 echo 'usage: cpu-cycle.sh --run-one-pair PEER_IPV4 EGRESS_INTERFACE SMP_PROBE' >&2; exit 2;
}
peer=$2; iface=$3; probe=$4
case "$peer" in ''|*[!0-9.]*) exit 2;; esac
case "$iface" in ''|*[!A-Za-z0-9_.:-]*) exit 2;; esac
test "$(id -u)" = 0
test "$(uname -r)" = 6.18.60
grep -Eq '(^| )rdinit=/init( |$)' /proc/cmdline
test -x "$probe"
command -v timeout >/dev/null
command -v ping >/dev/null
command -v ip >/dev/null
command -v sha256sum >/dev/null
p=/sys/module/vb235v_cpufreq/parameters
c=/sys/devices/system/cpu/cpufreq/policy0
test -r "$p/preflight"
test "$(cat /sys/devices/system/cpu/possible)" = 0-1
test "$(cat /sys/devices/system/cpu/online)" = 0-1
test "$(cat "$p/probe_complete")" = Y
test "$(cat "$p/boot_frequency_mhz")" = 1200
test "$(cat "$p/allow_transitions")" = N
test "$(cat "$p/faulted")" = 0
test "$(cat "$p/set_count")" = 0
test "$(cat "$c/scaling_driver")" = vb235v-smc
test "$(cat "$c/scaling_governor")" = performance
test "$(cat "$c/scaling_min_freq")" = 500000
test "$(cat "$c/scaling_max_freq")" = 1200000
test "$(cat "$c/related_cpus" | xargs)" = '0 1'
test "$(cat "$c/scaling_available_frequencies" | xargs)" = '500000 1200000'
policy_count=0
for policy in /sys/devices/system/cpu/cpufreq/policy*; do
 test -d "$policy" || continue
 policy_count=$((policy_count+1))
 test "$policy" = "$c"
done
test "$policy_count" = 1
ip -4 route get "$peer" | grep -F " dev $iface " >/dev/null
ping -I "$iface" -c 3 -W 2 "$peer" >/dev/null || {
 echo 'Peer did not answer the baseline ping; no CPU SET attempted. Verify peer ICMP policy before arming.' >&2
 exit 1
}
mkdir /tmp/vb235v-m81-cycle.lock
checker_ping=
cleanup() {
 result=$?
 # Disarming emits no hardware operation. Never write a recovery frequency,
 # retry a failed SET, or change a governor on the error path.
 printf 'N\n' > "$p/allow_transitions" 2>/dev/null || :
 if test -n "$checker_ping"; then kill "$checker_ping" 2>/dev/null || :; fi
 rmdir /tmp/vb235v-m81-cycle.lock 2>/dev/null || :
 if test "$result" != 0; then
  echo 'M81 stopped: transitions disarmed; do not retry; retain receipt and use coordinated cold recovery.' >&2
 fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM HUP
boot=$(cut -c1-8 /proc/sys/kernel/random/boot_id)
receipt=/tmp/vb235v-m81-"$boot"-"$(date +%s)"
mkdir "$receipt"
phase_check() {
 phase=$1
 ping -I "$iface" -c 12 -i 0.2 -W 2 "$peer" > "$receipt/ping-$phase.txt" &
 checker_ping=$!
 timeout 45 "$probe" > "$receipt/smp-$phase.json"
 wait "$checker_ping"
 checker_ping=
}
printf '%s\n' "$receipt"
cat /proc/cmdline > "$receipt/cmdline"
cat /proc/sys/kernel/random/boot_id > "$receipt/boot-id"
ip -4 route get "$peer" > "$receipt/route-before"
sha256sum "$probe" > "$receipt/smp-probe.sha256"
dmesg > "$receipt/dmesg-before"
cat "$p/preflight" > "$receipt/preflight-before.json"
test "$(cat "$p/retained_bl31_verified")" = Y
test "$(cat "$p/faulted")" = 0
test "$(cat "$c/cpuinfo_cur_freq")" = 1200000
test "$(cat "$p/set_count")" = 0
printf 'userspace\n' > "$c/scaling_governor"
test "$(cat "$p/set_count")" = 0
# Intentional negative gate check: this request must be rejected before SMC.
# The 6.18 sysfs store discards the governor return value, so a successful
# write does not prove a hardware transition. Judge counter/GET/new error log.
deny_pattern='Failed to change cpu frequency: -1'
denials_before=$(grep -Fc "$deny_pattern" "$receipt/dmesg-before" || :)
write_status=0
printf '500000\n' 2> "$receipt/disarmed-negative.txt" > "$c/scaling_setspeed" || write_status=$?
printf '%s\n' "$write_status" > "$receipt/disarmed-write-status"
dmesg > "$receipt/dmesg-disarmed"
denials_after=$(grep -Fc "$deny_pattern" "$receipt/dmesg-disarmed" || :)
test "$denials_after" -gt "$denials_before"
test "$(cat "$p/set_count")" = 0
test "$(cat "$p/faulted")" = 0
test "$(cat "$c/cpuinfo_cur_freq")" = 1200000
# userspace caches the requested setspeed even on rejected hardware changes.
# Clear the cached500 request at the known current1200 before allowing SETs.
printf '1200000\n' > "$c/scaling_setspeed"
test "$(cat "$p/set_count")" = 0
test "$(cat "$p/faulted")" = 0
test "$(cat "$c/cpuinfo_cur_freq")" = 1200000
printf 'Y\n' > "$p/allow_transitions"
test "$(cat "$p/allow_transitions")" = Y
test "$(cat "$p/set_count")" = 0
printf '500000\n' > "$c/scaling_setspeed"
test "$(cat "$c/cpuinfo_cur_freq")" = 500000
test "$(cat "$p/set_count")" = 1
test "$(cat "$p/faulted")" = 0
cat "$p/preflight" > "$receipt/preflight-500.json"
phase_check 500
test "$(cat "$c/cpuinfo_cur_freq")" = 500000
test "$(cat "$p/faulted")" = 0
printf '1200000\n' > "$c/scaling_setspeed"
test "$(cat "$c/cpuinfo_cur_freq")" = 1200000
test "$(cat "$p/set_count")" = 2
test "$(cat "$p/faulted")" = 0
cat "$p/preflight" > "$receipt/preflight-1200.json"
printf 'N\n' > "$p/allow_transitions"
printf 'performance\n' > "$c/scaling_governor"
test "$(cat "$p/set_count")" = 2
phase_check 1200
test "$(cat "$p/allow_transitions")" = N
test "$(cat "$p/faulted")" = 0
test "$(cat "$c/cpuinfo_cur_freq")" = 1200000
ip -4 route get "$peer" > "$receipt/route-after"
dmesg > "$receipt/dmesg-after"
printf '%s\n' 'PASS: one pair, exactly two SETs, independent readback, dual-core probe and wired peer checks passed.'
