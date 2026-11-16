# M20: VB235v recovery U-Boot development builds

The owner's 2026-11-16 priority is recovery U-Boot before further DSL/PCS work. Two VB235v BL33 development profiles now compile and link. They are **RAM experiments, not persistent installation images**. Neither has been booted on the router. A working, persistent recovery bootloader is still unfinished.

## Implemented behavior

| Profile | Devices and entry | Recovery facilities |
| --- | --- | --- |
| `an7583_vb235v_ram_defconfig` | Minimal UART/timer/PSCI DT; automatic boot disabled | Serial prompt, serial file loading, image/hash inspection, explicit RAM image boot commands |
| `an7583_vb235v_ram_net_defconfig` | Experimental integrated-switch/GDM1 LAN; automatic boot disabled | Same serial facilities plus an explicit `httpd` command, static address `192.168.0.1` |

Both profiles use the observed 512 MiB DRAM map and UART at `0x1fbf0000`, 115200 baud. They inherit DDR training from the factory early stages. The VB235v option reads DRAM geometry from its own DT rather than assuming the upstream BL2 scratch-register encoding. Its MMU map covers the board's 512 MiB DDR and omits the upstream high-DDR range. DT reservations cover the first 2 MiB, the observed NPU area and persistent logs.

There are no MTD/NAND/UBI/SPI/MMC drivers or persistent environment backends in either checked configuration. `ENV_IS_NOWHERE` keeps changes in RAM. The serial DT has only four compatible nodes: root, PSCI, timer and UART. Buttons, LEDs, GPIO and networking are excluded from that first profile. The LAN candidate leaves both external PCS paths, GDM2/GDM3, SNFI and MMC disabled. Its driver can reset/configure FE and the integrated switch: physical ports, PHY behavior and network recovery remain unverified.

The RAM HTTP backend is a separately linked implementation. It provides only a page, device/status GETs and `POST /api/upload`. Uploads allocate at most 16 MiB from U-Boot's 32 MiB heap, support one receiving connection, invalidate previous ready state when a replacement begins, and expose a SHA-256 only after complete receipt. Completed uploads set volatile `fileaddr`/`filesize` for subsequent serial inspection. File bytes are not interpreted or executed. This size cap does not accommodate every full firmware image.

Arbitrary commands, web environment editing, reset/boot tasks, storage download, flash writes, NAND scrubbing, UBI rebuild and early-stage updates have no handlers in this backend. The original management backend and page are not linked into this profile. A completed upload survives leaving the service; an interrupted upload never becomes ready. An inactive-tab disconnect, malformed TCP exchange or hostile network is not fully modeled by the host tests.

The page displays the device SHA-256. Browsers offering `crypto.subtle` additionally compare it with the local file; ordinary HTTP browsers without that API still display the device result. The service has no authentication; a local operator can replace the RAM upload. Network upload does not authorize booting a file.

## Build and package

Base: [pbs05/uboot-an758x at `4b91e112c345b8a4ad4f954775f3f4955f2cafb2`](https://github.com/pbs05/uboot-an758x/tree/4b91e112c345b8a4ad4f954775f3f4955f2cafb2). Apply [954-vb235v-uboot-ram-recovery.patch](bringup/954-vb235v-uboot-ram-recovery.patch) to that checkout. It changes 12 files; replay against the original files applied without fuzz and matched the compiled source bytes. Sixteen reviewed source hashes are recorded in [uboot-ram-source.json](findings/uboot-ram-source.json).

```sh
git clone https://github.com/pbs05/uboot-an758x.git /work/uboot-an758x
git -C /work/uboot-an758x checkout 4b91e112c345b8a4ad4f954775f3f4955f2cafb2
git -C /work/uboot-an758x apply /work/ponwrt/research/vb235v/bringup/954-vb235v-uboot-ram-recovery.patch
export CROSS_COMPILE=/native/tools/usr/bin/aarch64-linux-gnu-
sh /work/ponwrt/research/vb235v/bringup/build-uboot-ram-recovery.sh \
  /work/uboot-an758x /work/new-vb235v-ram-build
```

The wrapper requires a new output directory and the pinned revision/source hashes. It compiles both profiles, checks outputs, executes the native callback harness, and packages two unsigned FITs with independently verified payload hashes. Dependencies include the usual U-Boot host build tools, AArch64 cross GCC, native C compiler with ASan/UBSan, Python 3 and DTC. The recorded build used Debian 11 and GCC 10.2.1. Use native tool paths without spaces: this U-Boot make logic splits GCC's internal include-directory path when it resolves into a Windows username containing a space. No ARM32 BL2 or TF-A build is part of this wrapper.

Each `.Image` has the upstream Linux-compatible ARM64 header, text offset `0x1e00000` relative to RAM base and a declared image footprint covering its BSS. The FIT describes a Linux handoff to load/entry `0x81e00000`, with a development DT and SHA-256 subimage hashes. This requests the original bootloader's normal Linux handoff rather than relying on a raw function-call jump. Factory acceptance of an unsigned FIT and its actual cache/MMU/EL/PSCI handoff are **not verified**. Hashes establish integrity, not signature authorization.

Do not feed these files to the stock firmware updater, write them into a boot partition, or treat them as FIPs. They contain neither the original proprietary `ldtpimg` loader nor replacement BL2/BL31. No automatic stock firmware boot path is implemented in these profiles.

## Recorded checks

[uboot-ram-build.json](findings/uboot-ram-build.json) records final artifact hashes and package metadata. Both cross-builds link successfully. The final board descriptions compile without DTC warnings. Config and symbol checks find no selected storage driver/backend or linked MTD/UBI/NAND access functions; pinctrl's static NAND pin-name tables in the LAN candidate are not flash drivers.

The native harness executes the actual backend source with network/environment/pbuf/allocation mocks and the pinned upstream SHA-256 source. **42 cases / 181 assertions** pass under AddressSanitizer and UndefinedBehaviorSanitizer, including forbidden paths, upload limits, ownership, truncation, oversize/short copies, replacement state, allocation/environment failure, known hashes, service failures and cleanup. This is not a TCP-stack, SoC or hardware test. The checker's source hashes intentionally prevent silently retesting different code under the same milestone.

The build wrapper was then run from a fresh output directory to exercise the published build/check/package workflow. The public tree contains authored patches, tools and derived facts. Local packages, ELF/map files, full configs and build logs remain outside it; no factory binaries or device credentials are redistributed.

## Persistent recovery work remaining

The upstream [Nokia layout](https://github.com/pbs05/uboot-an758x/blob/4b91e112c345b8a4ad4f954775f3f4955f2cafb2/arch/arm/dts/an7583-nokia-xg-040g-mf.dts) places BL2 in 128 KiB and describes a 256 MiB device. VB235v reports 256 KiB erase blocks and 512 MiB NAND. Its factory partition and mapping scheme cannot be replaced with that layout by assumption.

The original environment at `0x7c000` occupies the same erase block (`0x40000`–`0x80000`) as part of compressed BL33. An environment-only erase there can destroy executable bootloader data. The preserved factory erase-block backup is local; it is not a complete physical NAND/OOB backup. The logical `whole` MTD view is also not the entire 512 MiB flash. See [M1](RECOVERY-BOOT.md) and [M9](NAND-ECC-BMT.md).

The next recovery stages are:

1. Validate the serial RAM handoff and prompt, DRAM/relocation bounds and original-boot return by reset. Establish factory FIT acceptance before attempting the LAN candidate.
2. Validate integrated-switch LAN and choose a verified recovery-entry signal. Stock boot arguments name decimal GPIOs 34/35, while the generic DT template names pin 0; neither the physical button assignment nor polarity has been established. The builds deliberately define no recovery button.
3. Resolve boot-stage authentication and FIP certificate policy, physical bad-block/ECC/OOB representation, early-stage mapping and an independently usable recovery path. Preserve factory BL2/BL31 until compatibility is demonstrated.
4. Implement and test a persistent layout with boot-region/ART protection, an environment outside shared boot-code erase blocks, board/layout/hash validation before erasure, and alternate firmware-slot updates that preserve a known recovery path on interrupted writes. The RAM upload API currently performs no such flash installation.

No device was rebooted, flashed, power-cycled or given new commands for M20. The priority remains recovery U-Boot; the M19 DSL receiver gaps remain deferred, not resolved.
