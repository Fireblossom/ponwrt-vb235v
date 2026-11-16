# M21: VB235v recovery U-Boot with mapped NAND backup and firmware slots

The recovery candidate now boots in RAM on the owner's VB235v v1. Its ordinary 1 GbE LAN port serves the recovery page, downloads verified boot/ART/misc/selector backups, and accepts hash-checked RAM uploads. Returning through the original U-Boot to the original Linux system also works. **Persistent recovery installation is not complete, and this is not an installable FIP or a finished PonWrt port.**

This follows [M20](UBOOT-RAM-RECOVERY.md), whose smaller profiles intentionally excluded NAND. M21 adds the facilities the owner requested, including calibration backup. Hardware observations and build hashes are recorded separately in [uboot-full-validation.json](findings/uboot-full-validation.json).

## Facilities and verification

| Facility | Implemented behavior | Verification |
| --- | --- | --- |
| Serial recovery | `VB235v-Recovery>` prompt, S-record/Kermit loading, hashes, TFTP and explicit boot commands | RAM serial loading, CRC and original FIT hash verification, prompt and DRAM bounds tested on device |
| Calibration backup | Download the entire ART and misc areas; `vb backup art 90000000` also reads ART to RAM | Device-side and downloaded ART SHA-256 match the earlier original-system backup |
| Boot and NAND backup | Logical boot/firmware/selector downloads; physical raw main+OOB stream | Critical logical hashes match; three complete 544 MiB raw reads obtained |
| Existing bad-block mapping | Independently authored, read-only factory BBT/BMT parser; initial-bad compaction followed by runtime remapping | Real board anchors match; native parser corruption/range tests |
| Firmware installation | Board/hash/type/sequence checks before erase; writes only the effective inactive 80 MiB slot, with existing mapping, ECC and per-page/final readback | Native NAND model, failure injection and interrupted-page cold-scan tests; **no hardware erase/program performed** |
| Slot selection | Highest valid positive FIT sequence wins; damaged or partial FITs are rejected; factory selector remains untouched | Native cold-start scans and interrupted writes |
| Original-system boot | Verify the original compressed and decoded BL33 hashes, add a separate ARM64 handoff header below it, then use `bootm` | Original BL33 bytes remain exact; direct chainload to original Linux tested without a board reset |
| Web recovery | Backup links, upload SHA-256, inactive-slot installation, boot action and operation status | Page root, downloads and 1,171,456-byte upload tested over ordinary 1 GbE LAN |
| DHCP server | Local OFFER/ACK/NAK server and bounded lease pool | Real upstream lwIP IPv4/UDP packet tests pass; **Windows lease acquisition remains unverified on hardware** |

The tested image has a 15-second automatic recovery window. An HTTP request keeps that session open; otherwise it attempts verified firmware slots and then original-system boot. `httpd` or `httpd dhcp` starts an indefinite manual session. A physical recovery-button assignment has not been established, so no guessed button GPIO is enabled. A serial operator can interrupt autoboot.

The web install and serial `vb install` paths do not offer bootloader, ART, miscellaneous configuration or selector writes. Generic NAND/MTD erase/write commands and persistent environment backends are disabled. Existing runtime-remapped blocks are supported; allocating a new replacement block after a fresh program/erase failure is deliberately not implemented. Such a failure stops the operation and preserves the active slot and boot/calibration areas.

Hash checks provide integrity, not image authentication. A structurally valid, newer FIT can still contain a nonworking kernel. There is no kernel-health acknowledgement or automatic rollback after a kernel hangs; the next power-on/serial recovery path must remain usable independently of that kernel.

## Addressing on the tested Windows host

Default HTTP addressing is `192.168.1.1/24`, with DHCP pool `.2` only. The owner's Windows USB adapter acquired an APIPA address instead of a recovery DHCP lease. HTTP tests therefore used the following **volatile recovery-console overrides**; no Windows address configuration or flash environment was changed:

```text
setenv httpd_ipaddr 169.254.1.1
setenv httpd_netmask 255.255.0.0
httpd
```

The unmodified compiled image then served `http://169.254.1.1/` to that host. Earlier raw-NAND streaming tests used an older RAM image with verified temporary RAM string changes to achieve the same subnet; these are not presented as unmodified-image network tests. The later image supports the overrides directly.

`setenv vb_dhcp_debug 1` enables a port/length-only DHCP Ethernet trace and a DHCP request-type trace. It prints no packet bodies, MACs or lease identities. No port-67 frames reached that trace in the Windows probes. A vendor protocol-forwarding-register experiment did not establish DHCP operation and was excluded from the released source. This leaves the physical DHCP path unresolved rather than attributing it conclusively to Windows or the switch.

## NAND backups and limits

The Micron device has 131,072 physical pages, each with 4,096 main bytes and 256 OOB bytes. `/api/backup/nand-raw-main-oob` streams pages in physical order, interleaving main and OOB: 536,870,912 main bytes plus 33,554,432 OOB bytes, totaling **570,425,344 bytes**. It includes the tail mapping pool and is distinct from the vendor's 198.5 MiB logical `whole` partition.

Raw mode bypasses on-die ECC. The second and third reads differed from the first in 9 and 5 bytes respectively, each a single-bit difference. The first `0x440000` physical main-byte region and the tail mapping pool were identical across all three reads. Complete private captures and exact repeat deltas were retained. The private archive also contains the separately verified, ECC-corrected critical logical backups. **The complete raw image is not repeat-bit-exact, and programmer restoration has not been tested.** Device configuration, calibration, raw NAND, serial logs and credentials are not in this public repository.

The fixed write guard checks this board's recorded ART and original compressed BL33 hashes. It is intentionally specific to the tested board/calibration set; adapting another VB235v requires an independently verified baseline rather than disabling that guard.

## Reproduce the candidate

Use the same pinned upstream [revision](https://github.com/pbs05/uboot-an758x/tree/4b91e112c345b8a4ad4f954775f3f4955f2cafb2). [Patch 955](bringup/955-vb235v-full-recovery-uboot.patch) is **cumulative from the pristine revision** and includes the M20 changes. Apply 955 alone, not 954 followed by 955. Reviewed files/hashes are in [uboot-full-source.json](findings/uboot-full-source.json).

```sh
git clone https://github.com/pbs05/uboot-an758x.git /work/uboot-vb235v
git -C /work/uboot-vb235v checkout 4b91e112c345b8a4ad4f954775f3f4955f2cafb2
git -C /work/uboot-vb235v apply /work/ponwrt/research/vb235v/bringup/955-vb235v-full-recovery-uboot.patch
export CROSS_COMPILE=/native/tools/aarch64-linux-gnu-
sh /work/ponwrt/research/vb235v/bringup/build-uboot-full-recovery.sh \
  /work/uboot-vb235v /work/new-full-recovery-build
```

Dependencies are AArch64 GCC, normal U-Boot host build tools, native C compiler with ASan/UBSan, Python 3 and DTC. Use native tool paths without spaces. The wrapper checks the pinned source scope/hashes, uses a fresh output directory, builds the candidate, runs native storage/web/lwIP tests, and packages its LZMA FIT. The complete public workflow was replayed in a fresh worktree and reproduced the hardware-tested binary and FIT hashes.

The FIT uses a Linux ARM64 handoff at `0x81e00000`; it is a RAM development image, **not a factory-updater input, replacement FIP or programmer image**. BL2/BL31 are not rebuilt. No vendor executable or calibration data is redistributed.

To prepare future firmware for the protected slot installer, use [pack_vb235v_firmware.py](tools/pack_vb235v_firmware.py) with an uncompressed ARM64 Linux Image, a `tplink,vb235v` DT, optional initramfs and a sequence newer than installed FITs. It packages kernel/FDT/ramdisk payloads with SHA-256, verifies their extracted bytes, and adds the required firmware/sequence markers. Its constrained RAM layout is documented in its argument errors and source. It creates files only; packaging does not establish a working kernel or driver set. The packer was checked against the actual C FIT validator using a nonbootable host fixture; that fixture was never sent to the device.

## Persistent-installation review

The factory environment at `0x7c000` shares the second 256 KiB erase block with compressed original BL33. A generic `saveenv` erase can destroy boot code. The third logical boot block (`0x80000`–`0xc0000`) is blank, and the compressed recovery FIT fits inside it. The original U-Boot's `mtd read bootloader` path and the RAM guard's `itest`/`mw` syntax were verified read-only on hardware.

Private review images preserve every existing BL2/BL31/BL33/certificate byte, propose putting the new core in that blank third block, and modify only `bootcmd` plus its environment CRC/padding in the shared second block. The hook can consume the factory-return RAM guard, otherwise read/boot the new core and fall back to the captured original boot command if loading fails. These review images are not installed or power-loss tested.

The initial shared code/environment-block replacement is **not power-loss safe**. An independently usable programmer recovery path is still needed before that step. Subsequent ordinary firmware-slot recovery is designed to leave the boot blocks untouched, but it has only been exercised with a host NAND model. No claim of an absolutely unbrickable or completed persistent bootloader is made.
