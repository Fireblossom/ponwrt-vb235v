# VB235v / TP-LinkBox 7 driver research

This research branch targets TP-LinkBox 7 (VB235v). It is **not an installable device port**. The goal is to retain DSL, the analog telephone port, and MT7993 Wi-Fi while investigating support in PonWrt.

Current owner priority (2026-11-16): recovery U-Boot first. [M21](UBOOT-FULL-RECOVERY.md) adds mapped NAND/calibration backups, protected inactive-slot FIT installation, a full web backend and original-system chainload. RAM boot, ordinary 1 GbE HTTP/backup/upload, and return to original Linux are hardware-verified. [M22](UBOOT-FIRST-NAND-TEST.md) verifies one blank-block program with the original MTD driver and manual boot of the staged recovery core. [M23](UBOOT-NAND-DRIVER-TEST.md) verifies the new driver's single-block erase/program/ECC/OOB/readback path and complete restoration of the secondary slot. Full firmware installation, automatic persistent recovery and DHCP lease acquisition remain unfinished; DSL/PCS work is deferred. [M20](UBOOT-RAM-RECOVERY.md) records the earlier minimal RAM profiles.

## Observed hardware

| Component | Observation |
| --- | --- |
| SoC | Airoha AN7583, ARM64 |
| RAM | 512 MiB |
| NAND | 512 MiB SLC; 256 KiB erase block; 4096-byte page; 256-byte OOB |
| Wi-Fi | MediaTek MT7993, PCI ID `14c3:7993` |
| Stock kernel | Linux 5.4.55 |
| Voice | Boot log identifies Silabs ProSLIC, PCM, and vendor DSP/SLIC modules |
| Access | Root SSH under the original init was verified locally |

PonWrt's Nokia AN7583 profile uses different NAND image geometry. Its device tree, preloader, U-Boot, and upgrade images are not VB235v images.

## Research order

1. Audit existing vendor sources before reverse engineering missing components.
2. Establish exact module dependencies and kernel ABI for DSL, voice, and Wi-Fi.
3. Map firmware-loading, ioctl, DMA, GPIO, interrupt, clock, and reset interfaces.
4. Develop a VB235v board description and assess source-porting paths.
5. Consider a dedicated RAM-only bring-up image after auditing initialization side effects.
6. Require DSL synchronization/traffic, telephone calls, and Wi-Fi tests before proposing persistent installation.

See [SCOPE.md](SCOPE.md), [ROADMAP.md](ROADMAP.md), [SOURCE-AUDIT.md](SOURCE-AUDIT.md), and [EVIDENCE.md](EVIDENCE.md). The first recovery milestone is documented in [RECOVERY-BOOT.md](RECOVERY-BOOT.md).

## Offline tools

The offline analysis tools use the Python 3 standard library and do not execute vendor code.

```sh
python research/vb235v/tools/gpl_inventory.py /path/to/gpl-archive-index.jsonl --output /private/gpl-inventory.json
python research/vb235v/tools/elf_inventory.py /private/extracted-modules --output /private/module-inventory.json
```

Keep original firmware, device dumps, calibration data, credentials, serial logs, and copied vendor sources outside the public tree. The initial research contribution contains authored notes, source-path/hash metadata, and offline analysis tools. Vendor source redistribution requires retaining the applicable notices and checking the relevant files individually.

New Python tools in this directory use `GPL-2.0-only`; existing upstream components keep their own licenses.

For bounded read-only SSH collection, see [STOCK-MODULE-COVERAGE.md](STOCK-MODULE-COVERAGE.md). That optional collector requires host-side Paramiko, private credentials and a previously verified host-key pin. M7 completes file coverage for all 86 loaded module names; firmware and built-in kernel coverage remain separate work.

[M8: NPU core provider](NPU-CORE-PROVIDER.md) identifies the four core NPU APIs in the live built-in kernel and audits their archived source contract. It does not certify a compatible PonWrt ABI.

[M9: NAND ECC and BMT](NAND-ECC-BMT.md) correlates the reported flash ECC path with vendor source and identifies conditional NAND writes during mapping-table initialization. Audit this path before any RAM-image boot.

[M10: NPU firmware identity](NPU-FIRMWARE-IDENTITY.md) establishes that both stock on-disk NPU files differ from the GPL reference blobs. Executing firmware memory and host-command compatibility remain unverified.

[M11: Stock board map](STOCK-BOARD-MAP.md) records allowlisted boot-provided FDT resources and logical partition offsets. The raw tree stays private; its generic nodes and GPIO control signals require board-specific review before use.

[M12: UART development build](UART-DEVELOPMENT-BUILD.md) supplies a compiled minimal ARM64 kernel/DT/initramfs profile with offline admission checks. It excludes normal router subsystems and has not been booted on VB235v.

[M13: NPU/PonWrt contract](NPU-PONWRT-CONTRACT.md) finds matching selected mailbox fields but different core-count, IRQ, DMA and host API contracts. Six stock watchdogs are observed; the reference driver uses eight core slots as its active bound.

[M14: NPU layout prototype](NPU-LAYOUT-PROTOTYPE.md) implements an opt-in source-derived layout and cross-compiles NPU/Ethernet/PPE objects against the complete target patch stack. Its development overlay keeps the NPU disabled; no runtime acceleration is validated.

[M15: DSL Ethernet transport](DSL-ETHERNET-TRANSPORT.md) distinguishes the legacy ioctl manager from installed Ethernet control implementations, including the stock kernel's `ae_wan` packet handler. Runtime library mappings and socket metadata are recorded without assuming live DSL use.

[M16: DSL/PCS boundary](DSL-PCS-BOUNDARY.md) decodes the stock DSL/WAN/USXGMII boot selection, traces `ae_wan` provider boundaries, and cross-compiles the existing AN7583 PCS objects. Physical PON PCS location and Ethernet programming still need to be distinguished.

[M17: DSL PMA rate contract](DSL-PMA-RATE-CONTRACT.md) finds matching selected PMA rate vectors but different Ethernet and optical WAN routing selectors. It provides a bounded source-contract checker; the complete reset/calibration sequence remains to be adapted.

[M18: PCS Ethernet prototype](PCS-ETHERNET-PROTOTYPE.md) implements an explicit USXGMII profile with pre-write interface checks and optical API separation. It cross-compiles and passes host-model/schema/overlay checks; all development hardware nodes remain disabled.

[M19: Receiver gaps](PCS-RECEIVER-GAPS.md) identifies five remaining clock-field differences and distinct direct TDC/reset sequences in the analog backend. Its source checker does not execute C or access hardware.

[M20: Recovery U-Boot builds](UBOOT-RAM-RECOVERY.md) supplies serial-first and experimental LAN profiles, a bounded RAM HTTP upload backend, native callback checks and a reproducible build/package wrapper. The outputs exclude NAND/UBI and persistent environment drivers and are not flash images.
