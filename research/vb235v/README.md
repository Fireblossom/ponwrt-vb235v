# VB235v / TP-LinkBox 7 driver research

This research branch targets TP-LinkBox 7 (VB235v). It is **not an installable device port**. The goal is to retain DSL, the analog telephone port, and MT7993 Wi-Fi while investigating support in PonWrt.

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

Python 3 standard library only; neither tool connects to the router or executes vendor code.

```sh
python research/vb235v/tools/gpl_inventory.py /path/to/gpl-archive-index.jsonl --output /private/gpl-inventory.json
python research/vb235v/tools/elf_inventory.py /private/extracted-modules --output /private/module-inventory.json
```

Keep original firmware, device dumps, calibration data, credentials, serial logs, and copied vendor sources outside the public tree. The initial research contribution contains authored notes, source-path/hash metadata, and offline analysis tools. Vendor source redistribution requires retaining the applicable notices and checking the relevant files individually.

New Python tools in this directory use `GPL-2.0-only`; existing upstream components keep their own licenses.
