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
