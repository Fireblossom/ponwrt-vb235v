# M81 CPU integration and staged hardware validation

M81 advances the M78 boot-voltage-preserving CPU frequency driver. It does not
claim complete DVFS, AVS voltage control or thermal protection. M78 and M80
sources remain unchanged. The default stays **performance + transitions N**.

The first real hardware observation passed on the existing M75 system:

| Observation | Result |
| --- | --- |
| SMC GET | 1200 MHz |
| CPU mux/divider register | `0x000002ff` |
| Source / divider encoding | ARMPLL 1 / divide-by-one 0 |
| Linux CPUs | 2 possible, 2 online |
| Probe lifecycle | loaded once, read-only, then removed |
| Wired link afterward | eth2 still 1000 Mbit/s |

The coordinating agent recorded this in
`offline-analysis/m81-cpu-query-hardware/report.json`. No SET, MMIO write, DT
change, or cpufreq registration was performed. **A real policy and 500/1200 MHz
transitions are still pending the M81 RAM image.**

## Two deliberately separate artifacts

`vb235v-cpu-query.c` is the already-tested one-shot module for an existing M75
kernel. It requires the exact board and two possible/online CPUs, performs one
SMC GET, logs it before any MCUCFG access, then reads `0x1efbe7c0`. Unknown GET
stops further probing. It has no cpufreq, MTD, AVS or SET interface. Its tested
module SHA256 is `9bc1f15ae8c70a6a47f304a119b349112394dae63b4bc0dd98cbb7e5556a1b24`.

`vb235v-cpufreq.c` is the enhanced real driver for the RAM/integrated image,
requiring the existing M78 DT opt-in. Do not load it on M75 to bypass that gate.
It retains exact BL31 payload hashing, 500/1200 state0/14, independent GET and
final CPU mux/divider verification, legacy -2 acknowledgement semantics and
permanent failure latching. No voltage or direct PLL writes are added.

M81 adds:

* A read-only `preflight` parameter that performs GET/mux verification and the
  read-only BL31 MTD hash before any frequency control is armed.
* `probe_complete`, `last_mux_div` and `set_count` diagnostics. `set_count`
  counts actual SMC SET calls, including failed ones, allowing zero-write
  observation and exactly-two-write tests to be proven.
* A controlled `allow_transitions` setter: enabling is refused before probe,
  after a fault, on unknown clock/identity, or while a known thermal/AVS DT node
  is available. Disarming is always allowed and emits no hardware operation.
* Getter-only operations for internal diagnostic/admission fields. A sysfs
  permission of0400 alone does not stop boot/module parameter assignments;
  M81 removes those setters so `retained_bl31_verified` or `probe_complete`
  cannot be injected through command-line/module arguments.

The thermal/AVS exclusion is intentional: M80 identified shared SCU protection
key ownership without safe cross-driver serialization. Enabling a temperature
zone now requires holding CPU transitions disabled. M81 does not guess a
voltage, calibrate a sensor, or pretend that a boot-voltage frequency change
provides AVS/thermal parity.

## Build and integration contract

The coordinating build owner applies, in order, the existing M75+ preparation,
M77/package stages as required, M78, then:

```sh
python3 research/vb235v/bringup/m81-cpu-integration/prepare.py "$TREE"
```

Do not rerun M78 after M81: its source equality checks correctly reject the
newer driver. M81 checks the M78 Kconfig/Makefile hashes, DT opt-in, performance
default and disabled generic Airoha driver before changing only the two CPU
source files in `build_dir` and persistent target `files/`. Baseline/candidate
SHA256 values are in `source-hashes.json`. It preserves the integrated revision,
networking, frontend, Wi-Fi and all NAND protection code. It installs:

```text
/usr/libexec/vb235v-cpu-observe
/usr/libexec/vb235v-cpu-cycle
/usr/libexec/vb235v-cpu-smp-probe
```

The SMP probe reuses the proven M67 two-thread/affinity/shared-memory/barrier
checker. It verifies CPU mask3, checksums and memory patterns and returns a
failure status on any detected error.

For isolated compile checks without shared-tree make:

```sh
python3 research/vb235v/bringup/m81-cpu-integration/compile-isolated.py \
 --tree "$TREE" --template /home/duanx/m78-cpu-dvfs-check \
 --work /home/duanx/m81-cpu-isolated
python3 research/vb235v/bringup/m81-cpu-integration/check-objects.py /home/duanx/m81-cpu-isolated
python3 research/vb235v/bringup/m81-cpu-integration/test-prepare.py "$TREE"
```

The compile helper reuses the exact prior external-module compiler/link flags
and runs GCC/modpost/ld directly, with output only in its explicit work directory.
It verifies shared `.config` and Module.symvers hashes did not change. Actual
ARM64 ELF checks prove the internal parameter ops lack setters and the query
object contains exactly one SMC call and only its audited import set. OpenWrt's
MODULE_INFO_STRIP causes the known description metadata warning; all modules
link with no unresolved symbols.

## Minimal RAM image and transport

The coordinator also approved a separate **M75-module RAM experiment**: keep
the exact installed M75 normal kernel payload, provide an offline-reviewed DT
with the real M78 opt-in and safe RAM bootargs, and load the actual M81 `.ko`
only after the RAM system has shown no existing policy. This is not a forced
load into the current live M75 DT. The same board/CPU/BL31/GET/mux/arming gates
remain mandatory; final M83 integration still builds the driver in with the
M78 configuration.

The normal FIT SHA256 is `3c1528eeb4cb4ea2e8494d39a61873cf6ed605445dd803e1a138118b632e42cc`;
its unchanged LZMA kernel payload SHA256 is
`9181e3529ad48ea5196449f6e1ba0e72e6d1c30bbb523c28d9fe554d9d9fe357`.
The matched normal ELF proves performance/userspace governors are compiled
with initcalls and a strong performance fallback. Although M75 defaults to
ondemand, the exact core falls back to performance before starting a dynamic
governor when M81's NO_AUTO_DYNAMIC_SWITCHING is set. The mini bootargs also
explicitly choose `cpufreq.default_governor=performance`. Runtime must still
verify unique `vb235v-smc`, performance and zero SETs after loading.

The normal kernel embeds only a512B default archive with dev/dev-console/root
and a trailer, no `/init`; the CPU mini supplies an external uncompressed newc
ramdisk. Its bootargs contain `rdinit=/init` and no `ubi.*`, `root=` or
`rootfstype=` parameters, preventing the old persistent-root auto-attach path.
M83 mini-r3 has been independently checked for unchanged normal payload,
correct module/script hashes, two CPU nodes, exact read-only boot-prefix
partition and no active thermal/AVS node. Root has now booted those exact bytes
through both serial and HTTP RAM paths and observed the sole real vb235v-smc
policy at1200MHz/performance, two online CPUs, verified BL31 and zero SETs.

The current kernel has KEXEC_FILE, OF_OVERLAY and DEVMEM disabled. The verified
U-Boot console has a fixed1.8432MHz UART input and115200 baud; no UART/DDR clock
experiments are needed. The coordinator owns serial/power and RAM loading.

The CPU mini image can use the same kernel machine code, M78/M81 opt-in DT and
NAND protection, with a small initramfs containing `mini-init.sh` as `/init`,
BusyBox plus its actual ELF interpreter/libraries, and the three CPU tools.
The init only mounts proc/sysfs/devtmpfs and tmpfs `/tmp`, then presents a
serial shell. It does not mount flash, start procd/UCI, load modules, configure
networking, sample an ADC or arm CPU transitions. A successfully registered
RAM thermal zone can itself sample and change ADC selectors; do not include one
in this initial frequency test image.

For the same-boot wired check, retain the two small NPU firmware files:
`vb235v/stock-npu-rv32.bin` (121132B) and `vb235v/stock-npu-data.bin` (3220B)
under `/lib/firmware`, plus `air_en8811h.ko` and its `airoha/EthMD32.dm.bin` /
`airoha/EthMD32.DSP.bin`. NET_AIROHA_NPU/NET_AIROHA and SNFI/SPI_NAND are already
built in. Load the PHY and set up the actual connected interface explicitly
before network checks. The internal1G socket currently has no carrier in both
the mini and full installed M75; root is waiting for the physical test fixture
to return to the previously verified external eth2/PHY15 path.
Do not remove NPU/PHY dependencies and claim wired validation succeeded.

The M83 coordinator owns final mini-cpio/FIT derivation and whole-image build.
The full combined production image keeps all features. The full initramfs and
shared `usr/initramfs_data.cpio` must remain unchanged while producing the mini
artifact. Any reduced-cpio derivation must verify exact ELF/Image placement,
complete cpio contents and all non-cpio kernel bytes; no magic-byte guessing.

## Hardware procedure and failure behavior

All hardware is leased by the parent. First boot the reviewed RAM image with
serial logging, then run `vb235v-cpu-observe`. Verify one shared `vb235v-smc`
policy, real1200MHz, CPUs0-1, default performance, `set_count=0`, `faulted=0`,
exact BL31 verified and no active incompatible SCU client. Cold boot must show
that default boot and observation issue zero SETs.

After the root coordinator explicitly sets up the wired peer/interface, it can
run one pair:

```sh
/usr/libexec/vb235v-cpu-cycle --run-one-pair PEER_IPV4 EGRESS_INTERFACE \
 /usr/libexec/vb235v-cpu-smp-probe
```

The script refuses non-initramfs boots (`rdinit=/init` required), prior SETs,
wrong policy/defaults/CPU membership, a bad route or unreachable peer. It first
checks that a userspace500MHz request while disarmed fails with zero SETs.
The kernel sysfs store discards the governor callback's return value, so the
negative check uses a new explicit kernel denial plus counter0/fault0/live1200
readback rather than the shell write status. It then restores the userspace
cached request to the known current1200MHz with zero SETs before arming.
It then arms through the kernel preflight, performs exactly one500MHz SET and
one1200MHz SET, checks fresh `cpuinfo_cur_freq`/preflight and fault/call counters,
and runs the two-core memory/barrier probe with concurrent wired pings at each
rate. It returns to disarmed performance only after successful1200MHz readback.
Receipts stay under `/tmp/vb235v-m81-*`; no credentials/configuration are read.

On any failure it only disarms, preserves evidence and stops. It never retries
a SET, guesses a recovery frequency, restores a governor on the failure path,
or writes a flash recovery record. Physical frequency may remain500MHz after
a late failure. Root must use the already-authorized serial/cold recovery and
then check the boot1200MHz/zero-SET default again. Real policy observation has
passed under root's hardware lease. The controlled frequency pair, runtime
negative test, SMP/network checks at both rates and post-cycle cold recovery
remain pending the working wired fixture. The independent PHY diagnosis has
issued no CPU SETs and does not establish a production PHY fix.
