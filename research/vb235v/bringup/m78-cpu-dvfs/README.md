# M78 CPU frequency bring-up

This is implemented **frequency scaling at the unchanged boot voltage**, ready
for supervised RAM testing. It is not full OEM DVFS or thermal parity. No device
has been accessed by this work and no clock transition has been tested yet.

The stock DT's `opp-hz` values are 500 MHz and 1200 MHz, shared by the ARM CPUs.
The second node's name contains an extra zero. Four stock template CPU nodes do
not imply four usable CPUs: this implementation requires exactly two possible
Linux CPUs. The separate NPU processors are not part of this clock policy.

The original Linux callback gets MHz with SMC `0x82000301`, op `0xddddddd2`.
It sets `x3=(Hz-500000000)/50000000` with op `0xddddddd1`: states 0 and 14,
not OPP ordinals 0 and 1. For >700 MHz, OEM Linux calls SET_AVS(0) before
SMC; for <=700 MHz it calls SET_AVS(1) after SMC. AVS includes calibrated
TADC/DAC control and voltage settling. M78 never writes that machinery. It
requires 1200 MHz at boot, retains its already-running voltage, and never goes
above that rate. This leaves voltage power savings and thermal protection open.

The existing 6.18 generic Airoha driver expects a CPU clock and perf power
domain absent from our DT. Merely adding a fixed clock would falsify control.
The new board-specific driver uses the real OEM SMC directly, registers one
shared policy, supplies real readback, and disables the other Airoha cpufreq
driver in this profile. It does not create an invented CCF clock provider.
The DT opt-in is a development switch, not a claim of upstream binding support.

Two reverse-engineering details are essential:

* Exact retained BL31 always overwrites the PLL switch routine's status with
  `-2`, including after a successful switch. A zero status cannot be required
  for this firmware. Before the first permitted SET, M78 reads the read-only
  `bootloader-protected` MTD region's 56846-byte BL31 payload at offset
  `0x21800` and checks its SHA256. An absent/writable/different-size partition,
  failed/short read, or different hash forbids all SETs. Only then is legacy
  `-2` accepted as **untrusted acknowledgement**; independent GET must equal
  the target. A successful GET is not inferred from `-2`.
* GET reports ARMPLL PCW/POSDIV, not the final CPU mux/divider. M78 also reads
  MCUCFG `0x1efbe7c0`, requiring ARMPLL source bits[10:9]=1 and divider
  bits[21:17]=0 (1:1), before and after changes. There are no MMIO writes.
  First RAM testing must verify that this nonsecure read is accessible on the
  board before this can be considered a boot-tested driver.

BL31 retains its own PLL2 intermediate source, protected PLL updates, >=0.5 us
settling, mux readback and relock. Linux does not reproduce those sequences.
No DDR/bus/EMI/NPU/ethernet/PCIe/AES clock is directly changed by M78. Actual
shared supply interactions still require hardware testing. No documented PLL
lock bit or measured worst-case transition latency has been established;
M78 reports unspecified latency (0) and refuses dynamic governors instead of
inventing a measurement. Only performance/powersave/userspace operation is
eligible for supervised use; the default is performance.

## Checks and integration

Run on Linux/WSL with the current M75 prepared tree:

```sh
sh research/vb235v/bringup/m78-cpu-dvfs/check.sh "$TREE" /home/duanx/m78-cpu-dvfs-check
python3 research/vb235v/bringup/m78-cpu-dvfs/verify-evidence.py /mnt/c/Users/duan\ changxu/Desktop/TP
python3 research/vb235v/bringup/m78-cpu-dvfs/prepare.py "$TREE"
```

`check.sh` compiles the shared production transition contract with UBSan and
negative tests, builds an ARM64 external `.ko` against exact Linux 6.18.60
headers/Module.symvers, and exercises prepare twice in a small disposable
fixture. It never installs or loads a module. The OpenWrt kernel strips
MODULE_DESCRIPTION via MODULE_INFO_STRIP, so modpost emits that metadata warning
despite the source having MODULE_DESCRIPTION. There are no unresolved symbols.

`prepare.py` mutates the specified build tree, so only the coordinating agent
should run it on the shared build tree. It requires the pinned tree and M75
PHY candidate hashes, never reruns earlier prepare stages, and preserves M77
and later work. It installs CPU sources/patch queue entry 965, modifies only the
persistent board DTS's root opt-in (installation RAM inherits it), selects the
new built-in driver and performance default in target and prepared kernel
configs. It leaves the integrated system revision unchanged unless explicitly
given `--revision`. Run the existing profile's kernel/package/image build
sequence afterward. Before a clean kernel prepare, retain the target `files/`
copies and patch queue; after a re-prepare verify both config choices survived.
It does not replace the existing image-builder entry point.

## Hardware gates and recovery

First boot must be in the existing RAM recovery workflow, with serial available,
and `allow_transitions=N` (default). Observe the original retained boot prefix,
two CPU policy membership, actual SMC boot frequency 1200 MHz, ARMPLL 1:1 mux,
policy governor performance and both advertised frequencies. Compare existing
dual-core load/network/PCIe/NPU checks before enabling any SET. Default boot and
same-rate performance requests emit zero SETs, even if explicitly enabled.

The coordinator can later use `/sys/module/vb235v_cpufreq/parameters/` to inspect
`allow_transitions`, `boot_frequency_mhz`, `retained_bl31_verified`, `faulted`,
`legacy_ack`, `last_status`, and `last_mhz`. Only `allow_transitions` is writable
(root 0600); it stays N across reboot. Enable only after the RAM observation
gate and retained-prefix verification. Select userspace, make one 500000 kHz
request, verify independent GET/mux and both-core progress/network operation,
then request 1200000 and repeat; do not use an automatic load governor.
Check the fingerprint flag and legacy_ack counter after the first actual SET.

Unknown GET, bad mux/divider, identity failure, nonzero status other than the
proved legacy -2, or target readback mismatch latches all future SETs off until
reboot. The actual last MHz and raw status remain inspectable. There is no
automatic retry or speculative rollback: a failure may leave the CPU running
at 500 MHz or a different source. Reboot through the retained boot chain is
the recovery, and its boot frequency must be checked again. Suspend also
invalidates admission until reboot because voltage retention is unproved.
Module unload at low frequency leaves that physical frequency in place; this
profile builds the driver in and must use reboot for recovery.

Production readiness still requires repeated cold boots, supervised paired
transitions under both-core load and network traffic, independent timing and
frequency checks, voltage/temperature observation, a calibrated AVS regulator
port with sequencing/error handling, and a genuine thermal sensor/cooling
policy. No automatic thermal protection is added here.
