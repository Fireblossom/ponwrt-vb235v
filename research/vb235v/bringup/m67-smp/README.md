# M67: two usable ARM CPUs, verified in RAM

The original live `/proc/cpuinfo` exposes CPUs 0 and 1, and ATF lists two CPU
power nodes. The stock generic DT's four CPU nodes do not prove four usable
processors. M67 admits only MPIDRs 0 and 1, with PSCI SMC startup, one cluster
and shared L2. The test kernel's maximum slot count is four; its actual
possible, present and online sets are all `0-1`. An initial four-node image
was corrected before any hardware boot. No four-core result is claimed.

Run `sh build.sh TREE 4` after M64 at the pinned PonWrt baseline. This keeps
the M64 storage exclusion, RAM reservations, single isolated LAN and two PCIe
controllers. M67 adds no new peripheral MMIO resources. This remains a RAM
development profile with persistent installation disabled.

The console reports CPU1 starting at MPIDR 1, GIC redistributor `0x90a0000`,
and two active processors. The static AArch64 `vb235v_smp_probe.c` pins one
thread to each CPU and repeatedly checks both CPUs' shared arrays across
barriers. Each run checks 134,217,728 64-bit words, checks CPU placement, and
produces the independently host-executed checksum `3fd3420cdc24990e`.
Three initial runs passed, including one after each of two CPU1 offline/online
cycles. Both CPUs accumulated user ticks. Ten additional runs passed while
network tests executed. All thirteen runs reported zero errors.

The isolated LAN passed 8 MiB download and upload SHA-256 checks at 100 Mbps.
Both authorized Wi-Fi bands separately passed authentication, DHCP, gateway
reachability and 8 MiB transfers in each direction under the SMP kernel.
Both PCIe links remained 5.0 GT/s x1. These are short integrity/concurrency
tests, not long-term stability or peak-performance measurements.

On this fresh boot netifd's logical LAN object was present and up. The default
Dropbear `DirectInterface` setting takes precedence over `Interface` and can
listen on wildcard addresses while binding to a network device. The console
test removed that precedence and verified address-bound managed listeners
and public-key reconnection. Restarting Dropbear over its own SSH connection
can terminate that command; the accepted restart was issued from COM3.
This supersedes a blanket assumption that the LAN object is always missing.

The read-only `vb235v_link_probe.c` also captures supported, advertised and
partner link modes and selected Clause-22 PHY registers. At this test point
the router advertised gigabit, while the partner report contained 10/100
modes only. Gigabit end-to-end operation and both 2.5G ports remain separate
work. CPU frequency/OPP integration also remains open: the kernel reports
that the CPU clock is absent from this development DT.

Evidence: `../../findings/smp-hardware-m67.json`. Probe binaries, console logs,
credentials and private calibration remain outside the public tree.
