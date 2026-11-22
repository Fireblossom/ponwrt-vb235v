#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
# Read-only observation; output may be redirected to a /tmp receipt by caller.
set -eu
p=/sys/module/vb235v_cpufreq/parameters
q=/sys/module/vb235v_cpu_query/parameters
printf 'kernel='; uname -r
printf 'possible='; cat /sys/devices/system/cpu/possible
printf 'online='; cat /sys/devices/system/cpu/online
if test -r "$p/preflight"; then
 cat "$p/preflight"
 for name in boot_frequency_mhz probe_complete allow_transitions faulted set_count legacy_ack last_status last_mhz last_mux_div retained_bl31_verified; do
  printf '%s=' "$name"; cat "$p/$name"
 done
 for policy in /sys/devices/system/cpu/cpufreq/policy*; do
  test -d "$policy" || continue
  printf 'policy=%s\n' "$policy"
  for name in scaling_driver scaling_governor related_cpus affected_cpus scaling_available_frequencies cpuinfo_cur_freq; do
   printf '%s=' "$name"; cat "$policy/$name"
  done
 done
elif test -r "$q/smc_mhz"; then
 for name in smc_mhz mux_div_raw possible_cpus online_cpus armpll_div1; do
  printf 'query_%s=' "$name"; cat "$q/$name"
 done
 printf '%s\n' 'policy=unavailable; query module does not register one'
else
 printf '%s\n' 'cpu_observation=unavailable; no M81 driver or query probe loaded'
 exit 1
fi
