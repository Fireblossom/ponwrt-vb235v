# M23: new recovery NAND driver program/readback/restore test

The owner authorized the next staged hardware test after [M22](UBOOT-FIRST-NAND-TEST.md). The new recovery NAND path has now erased, programmed and verified a complete 256 KiB block at the end of inactive firmware slot 1, then restored its entire main and OOB areas to erased `FF`. Original Linux subsequently downloaded the complete 80 MiB secondary slot and matched it byte-for-byte against the pre-test backup. Boot code, environment, ART, misc, active firmware and selector contents remained unchanged.

This tests the new driver's physical erase/page-program/ECC/OOB/readback path. It does **not** install a new firmware FIT, change boot selection, install an automatic recovery hook, simulate loss of power or demonstrate a complete firmware upgrade.

## Target and preconditions

The target was the final erase block of slot 1: logical/physical `0x0ac00000`, slot-relative `0x04fc0000`, length `0x40000`. The first block containing the secondary firmware header was excluded. The active factory slot was 0.

Before rebooting, original Linux produced two independent ECC-corrected copies of the entire 83,886,080-byte secondary slot. Each transfer's device-before/device-after/local SHA-256 matched, and the two complete copies were identical. The chosen final block's main area was entirely `FF`. Three previously captured physical images also showed that exact block's 64 physical pages, including all OOB bytes, were erased. Their factory BBT/BMT records had no initial bad blocks or runtime remaps.

The command independently repeats the live checks immediately before writing: board anchors, active-slot scan, full hashes of both firmware slots, identity mapping for the fixed target, and a raw read of all main and OOB bytes in that block. A changed hash, active slot 1, nonidentity mapping or any non-erased byte rejects the test before an erase/program.

## Implementation

[Patch 956](bringup/956-vb235v-nand-slot-selftest.patch) follows cumulative M21 patch 955. It extracts the existing installer erase/page-program operations into shared helpers and adds `CONFIG_VB235V_NAND_SELFTEST`, which defaults **off**. The standard build has no selftest symbol. A separately built RAM diagnostic image enables a serial-only command; there is no web endpoint and no arbitrary target/address argument.

The test command requires both full-slot baseline hashes and is confined to the fixed inactive-slot tail block. It:

1. Erases that block using the same helper as the protected FIT installer.
2. Programs 64 full 4 KiB pages with a deterministic pseudorandom pattern, using on-die ECC and the same physical OOB index placement as the installer.
3. Reads every page back, checks the full pattern SHA-256, and verifies each page's erased bad-block markers and OOB block index.
4. Erases the block again and raw-reads all 278,528 main-plus-OOB bytes, requiring every byte to be `FF`.
5. Checks both complete firmware-slot hashes and snapshots of bootloader, ART, misc and selector against the pre-test values.

Restoration is attempted before returning a program/readback failure. A restoration failure is reported explicitly; the command does not rebuild BBT/BMT tables or allocate replacements. These failure cases were injected in the host model, not physically induced on the device.

The diagnostic U-Boot was loaded into RAM through S-records, checked by RAM CRC and both original-U-Boot FIT SHA-256 checks, then booted. It was **not written into the boot partition**. The M22 staged recovery core and its original boot command remain unchanged.

## Recorded results

The real command verified all 64 ECC-enabled pages, the pattern SHA-256, OOB indices, raw erased restoration and both full-slot/protected-region hashes, and returned success. Its source and actual host model pass **1,193 cases / 5,042 assertions** under ASan/UBSan, including unsafe-state rejection, a page-33 program failure with restoration, restore failure and initial erase failure. The existing web callback checks remain 28 cases / 132 assertions, and the actual lwIP DHCP packet tests remain 8 / 78.

The complete public build workflow was replayed from a fresh pinned checkout with patches 955 then 956. It builds a standard candidate and the opt-in diagnostic separately, checks the command is absent from the standard ELF, and reproduces the exact diagnostic binary/FIT hashes tested on the device. See [source pins](findings/uboot-nand-selftest-source.json) and [validation summary](findings/uboot-nand-selftest-validation.json).

After the test, direct original-U-Boot chainload started original Linux. The serial collector did not receive its expected interactive-shell banner and timed out; this was an automation-marker failure, not evidence of a failed boot. A separate pinned root SSH session confirmed original Linux was running, downloaded the full boot partition, checked the active/secondary firmware and all protected hashes, and downloaded the entire secondary slot again. The complete secondary download was byte-identical to the pre-test backup, and all protected comparisons passed.

Private evidence includes all three 80 MiB ECC-corrected secondary reads, the original raw tail capture, build/serial logs, complete post-test boot readback, and SHA-256 manifests. Device binaries, environment, calibration and logs are not published.

## Reproduction and remaining limits

On pristine upstream revision `4b91e112c345b8a4ad4f954775f3f4955f2cafb2`, apply [955](bringup/955-vb235v-full-recovery-uboot.patch), then [956](bringup/956-vb235v-nand-slot-selftest.patch). Set a native AArch64 `CROSS_COMPILE` prefix and run:

```sh
sh research/vb235v/bringup/build-uboot-nand-selftest.sh /work/uboot /work/new-m23-build
```

This command only builds and tests files on the host. Both resulting FITs remain RAM development inputs, not factory update files or FIPs. The diagnostic image is for a separately reviewed destructive test with complete backups; it must not be used as an ordinary persistent recovery image.

The next unresolved installation risks are broader firmware/FIT installation and interruption behavior, a verified recovery-entry mechanism, the physical DHCP path, and replacement of the block shared by original code and environment. This successful restored-block test does not make that shared-block write power-loss safe or establish programmer recovery.
