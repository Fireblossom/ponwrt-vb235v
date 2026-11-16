# M22: first controlled NAND program and staged-core boot

After asking about risk, the owner explicitly authorized staged hardware tests. The first test programmed only the previously blank third logical boot erase block, `0x80000`–`0xc0000`. The original U-Boot's existing MTD driver performed one program command. No erase, environment save, boot-command change or automatic recovery installation was performed.

The [M21 recovery core](UBOOT-FULL-RECOVERY.md) is now stored in that block and has been manually loaded from NAND and booted. This verifies a staged persistent core, **not automatic persistent recovery and not the new recovery driver's firmware-slot write path**.

## Checks before and after programming

Before the sole write, three independent physical raw captures showed that the first three physical blocks' main areas exactly matched the original logical boot backup, and their raw bad-block marker bytes were erased. Original Linux had also verified the complete original boot-partition SHA-256.

At the original U-Boot prompt, the entire boot partition and blank third block were read and checked against their expected CRCs. The fixed, padded 256 KiB candidate block was transferred into RAM, checked by CRC, and both FIT payload SHA-256 values were verified. The unchanged first two blocks and blank target were read and checked again immediately before programming.

After programming:

1. The entire third block was read back and matched the prepared block CRC; both embedded FIT SHA-256 checks passed.
2. The first two blocks still matched their original CRC.
3. `bootm` started the recovery image from that NAND readback. Its factory mapping/board anchors verified, and its boot-partition and ART backups matched the expected SHA-256 values.
4. The recovery image directly chainloaded original U-Boot and original Linux.
5. Original Linux independently downloaded the complete boot partition. Every byte matched the expected one-block change: the first `0x80000` bytes and entire environment were unchanged, and the third block exactly matched the candidate. ART and misc hashes were unchanged.
6. A further ordinary software reset was allowed to autoboot without serial interception. Original BL2, original U-Boot and original Linux started normally; the experimental recovery prompt did not appear. The complete readback and protected-partition checks were repeated after this reset.

The serial automation initially waited for a newline before the stock prompt, while the successful MTD program printed progress dots directly before `U-Boot>`. The UART reader was stopped after that completed command, then readback continued with a fresh console synchronization. **The block was not programmed a second time.** Full private logs preserve this distinction.

## Current state and remaining gates

The factory boot command and environment remain byte-exact. Normal boot still runs the original system. The new core is present in NAND but is entered only by manually reading that block and booting its FIT. This milestone neither enables an automatic hook nor modifies the shared original-code/environment erase block.

The next write-path validation needs a separately reviewed target and complete restorable backup, particularly before touching the secondary factory firmware slot. The new recovery driver's ECC/OOB programming, newly failing-block behavior and interrupted firmware writes remain hardware-unvalidated. DHCP lease acquisition and a physical button assignment also remain unresolved.

Changing the environment at `0x7c000` would require replacing a block that also contains original executable code. That is still a distinct, higher-risk installation step; it is not power-loss safe and was excluded from this test. A programmer recovery path has not been demonstrated. No claim of an unbrickable bootloader follows from one successful NAND program.

Only derived test results are public. Raw NAND, device environment, calibration, original binaries and serial logs remain private. See [uboot-first-nand-test.json](findings/uboot-first-nand-test.json) for the bounded test summary.
