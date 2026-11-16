# M24: FIT installation, NAND kernel boot, incomplete-image fallback and restoration

The next staged test exercised the real web installer with a bootable FIT, started its kernel from secondary-slot NAND, rejected a deliberately incomplete copy after a cold recovery scan, and restored the modified secondary contents from backup. Original boot code/environment, active firmware, calibration and selector were kept unchanged. This validates a kernel/FDT FIT installation path; it does not establish a PonWrt port, rootfs upgrade, automatic persistent recovery or actual power-cut tolerance.

## RAM-first gate and the memory-layout fix

The first RAM-only boot exposed a real board-description problem: the recovery DT reserved the first 2 MiB of RAM, overlapping the observed original kernel load/entry at `0x80088000`. U-Boot refused the OS allocation. No NAND installation was performed before addressing this failure.

The original board DT declares the secure carveout as `0x80000000` plus `0x50000` bytes, while the original ARM64 Image declares a text offset of `0x88000` and a 13,828,096-byte footprint. [Patch 957](bringup/957-vb235v-stock-kernel-memory.patch) makes the recovery secure reservation match that board DT and adjusts its usable-memory range accordingly. NPU/log reservations remain unchanged. This changes the recovery DT only; BL2/BL31 and their flash bytes are not modified.

[check_uboot_stock_load_memory.py](tools/check_uboot_stock_load_memory.py) checks the actual compiled DT, the observed DRAM range, secure/usable ranges and kernel/reservation intersections. The old layout fails the regression check. The corrected recovery was RAM-booted, and its real LMB dump showed the expected secure range ending at `0x8004ffff`.

The private trial FIT contains the byte-exact original compressed kernel, with its original load/entry and a SHA-256 hash. Its private board DT preserves the current original-system boot arguments byte-for-byte, appends the `tplink,vb235v` compatible identifier, declares the observed 512 MiB memory size and adds an inert `/chosen/vb235v,trial` identity property. The original kernel and modified DT remain private. The existing primary-slot root filesystem is reused; no rootfs data is replaced.

With the corrected recovery, that FIT booted from RAM first. Pinned root SSH then verified its DT identity, byte-exact original command line and every protected/firmware partition baseline. Original Linux's command line was already close to its length bound, so the trial identity was put in a separate DT property rather than appended to it.

## Installation and boot

Before writing, the restoration prefix was uploaded into RAM, carried through direct original-U-Boot chainload, and checked again. The original MTD reader also matched the intended target prefix to its backup. This rehearsal performed no flash write.

One real web install request then wrote a 3,766,005-byte sequence-1 kernel/FDT FIT into inactive slot 1. Its touched range was the first fifteen 256 KiB erase blocks: logical `0x05c40000`, total `0x003c0000` bytes. The installer used the mapped NAND/ECC/OOB path established in [M23](UBOOT-NAND-DRIVER-TEST.md), with its before-erase FIT/board/hash/sequence checks and per-page/final readback.

The web operation finished successfully and selected slot 1 in recovery's volatile state. The complete 80 MiB secondary-slot hash matched the exact predicted result, including untouched bytes beyond the fifteen-block prefix. `vb boot` reloaded the image from NAND and started its kernel. An independent pinned root SSH session observed the trial DT identity, verified the original command line, and checked the expected installed secondary hash plus unchanged boot, ART, misc, primary-slot and selector hashes.

The factory selector was never rewritten. The test did not make this kernel the original bootloader's normal boot target.

## Deliberately incomplete image and fallback

After rechecking the installed image, the original U-Boot erased only the trial FIT's final touched block, at secondary-relative `0x00380000`, length `0x40000`. This models an incomplete/corrupted image; **it is not a physical power cut during programming**.

The unchanged M22 recovery core was then loaded from its existing NAND block. Its cold scan rejected the incomplete FIT and selected the factory slot. The complete secondary hash matched the exact one-block-erasure prediction. `vb boot` followed the hash-verified original-U-Boot fallback path, and original Linux started without the trial DT identity. Pinned root verification confirmed the original command line and unchanged protected/primary contents.

This also confirms that fallback for this malformed image works through the already staged recovery core. It does not provide kernel-health acknowledgement or automatic rollback from a kernel that has passed FIT checks but subsequently hangs.

## Restoration and final state

The original fifteen-block prefix was uploaded and carried into original U-Boot, where both its RAM CRC and the current deliberately corrupted target CRC were checked. The original MTD driver erased and restored only that prefix. Full prefix readback and the entire boot partition CRC passed before allowing normal original-system boot.

Final independent original-Linux verification downloaded the full restored secondary slot and matched it byte-for-byte against the original 80 MiB backup. Boot/environment/calibration/primary/selector baselines and the absence of the trial DT identity also passed. The original driver regenerates ECC/OOB during restoration: the restoration claim concerns complete logical main data, not byte-identical equality of every physical OOB byte.

The NAND-staged M21 recovery core from M22 remains unchanged, and the original boot command is unchanged. Patch 957's corrected candidate was used in RAM and is supplied as a development artifact; it was not silently substituted into the boot partition. The earlier staged core retains the conservative low-memory reservation and should not be treated as the corrected kernel-loading candidate.

## Reproduce and verify

Starting from pristine upstream revision `4b91e112c345b8a4ad4f954775f3f4955f2cafb2`, apply patches [955](bringup/955-vb235v-full-recovery-uboot.patch), [956](bringup/956-vb235v-nand-slot-selftest.patch) and [957](bringup/957-vb235v-stock-kernel-memory.patch), in order. With a native AArch64 compiler prefix:

```sh
sh research/vb235v/bringup/build-uboot-fit-memory.sh /work/uboot /work/new-m24-build
```

The wrapper checks source pins, builds a standard recovery with the diagnostic command disabled, runs the DT memory contract, ASan/UBSan storage/web checks and actual lwIP DHCP packet checks, then packages its RAM FIT. A fresh checkout replay reproduced the exact corrected recovery binary/FIT hashes used for the hardware tests. Source pins and the bounded hardware summary are in [uboot-fit-memory-source.json](findings/uboot-fit-memory-source.json) and [uboot-fit-install-validation.json](findings/uboot-fit-install-validation.json).

All vendor kernel/DT/firmware bytes, captured command lines, calibration, environment, restoration data and full serial logs remain private. The public repository contains authored changes, tools and derived results. Physical DHCP, recovery-button assignment, shared code/environment-block installation and independent programmer recovery remain unresolved.
