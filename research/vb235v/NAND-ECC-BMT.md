# M9: NAND ECC path and initialization writes

## Geometry and selected ECC path

Retained original U-Boot and Linux boot captures both report **Using Flash ECC**, followed by Micron `MT29F4G01ABAFDWB` identification. Linux additionally reports manufacturer/device `2c:34`, 512 MiB SLC, 256 KiB erase blocks, 4,096-byte pages and 256-byte OOB. That gives 2,048 physical erase blocks and 64 pages per erase block. The reported BMT pool is 163 blocks.

The archived `drivers/mtd/chips/spi_nand_flash.c` explains why Linux can also print `NAND_ECC_NONE selected by board driver`:

- `SPI_NAND_Flash_Init` has distinct controller-ECC and flash-ECC branches. The branch producing the observed Flash ECC message calls `SPI_NAND_Flash_Enable_OnDie_ECC`; its DMA setup disables the controller ECC encoder/decoder while retaining NAND transport.
- The legacy raw-NAND integration can set `chip->ecc.mode = NAND_ECC_NONE` while enabling chip ECC through the vendor driver. The core warning describes the generic NAND layer's ECC mode, rather than establishing that the physical chip has no correction.
- The chip table selects the Micron part's geometry, feature-register ECC enable mask/value `0x10`, and a status mask/value `0x70`/`0x20` for its uncorrectable-ECC check. It selects an OOB-free layout of 28 logical bytes at raw offset 32, distinct from the 256-byte physical OOB area.

This is corroborated software-path evidence for **on-die flash ECC**, not an independent feature-register readback, correction-strength measurement, or injected-error test. No commands were sent to change ECC settings. Compiler defines enabling controller-ECC support do not establish which runtime branch the board selected.

## Mapping and reserved space

The vendor read path translates a logical block through BBT then BMT, before constructing the physical read address. `drivers/mtd/econet/bmt.c` stores the bad-to-replacement mapping and uses OOB metadata. A standard NAND driver with the same page geometry does not automatically preserve this mapping.

The archived `calc_bmt_pool_size` seeks `floor(total_blocks * 8 / 100)` good blocks by scanning from the tail, while the maximum reservation calculation uses one eighth of the physical block count. For a 2,048-block device, these calculations yield 163 requested good blocks and a 256-block reservation ceiling. Bad blocks can enlarge the tail span needed to find 163 good blocks; the observed pool count alone is not a count of all bad blocks or proof that the entire chip has none.

The current proc table's `mtd0` entry named `whole` is only `0x0c680000` bytes (198.5 MiB), not the complete 512 MiB chip. The table also includes overlapping kernel/rootfs/firmware views and their alternate-image counterparts. Do not sum those entries or use the name `whole` as a physical-backup coverage guarantee. The table does not provide offsets, OOB contents or BootROM-level layout.

## RAM boot can still reach NAND writes

The archived initialization path contains this call chain:

```text
spi_nand_setup
  -> init_bmt_bbt
     -> init_bmt / start_init_bbt
        -> load existing table or reconstruct and set a write-needed flag
     -> write_bbt_or_bmt_to_flash
        -> conditional write_bmt_to_flash / write_bbt_to_flash
           -> NAND erase / page program / bad-block marking helpers
```

In this source revision, `init_bmt_bbt` calls the writeback dispatcher during setup. Actual programming is conditional on reconstruction flags; this does **not** mean every normal boot rewrites the tables. Nevertheless, an incompatible parser or changed layout in a new kernel could trigger reconstruction before userspace starts. A read-only root filesystem or RAM-loaded image is insufficient to prevent this path.

A future RAM bring-up image must first exclude NAND initialization or implement and review a probe-time no-write path, including BMT/BBT reconstruction, repair, erase and bad-block marking. Merely setting an MTD partition read-only after probe does not cover lower-level initialization writes. Existing logical MTD backups remain valuable but are not raw chip/OOB/ECC programmer images.

## Reproduction and evidence

```sh
python -B research/vb235v/tools/nand_boot_evidence.py \
  /private/stock-boot.log /private/proc-mtd.txt --output /private/nand-observations.json
python -B -m unittest discover -s research/vb235v/tests -v
```

The offline extractor emits only allowlisted geometry, reported ECC paths, pool counts and MTD entries; it does not reproduce unrelated boot-log contents. It preserves conflicting reported ECC paths rather than choosing one silently, rejects conflicting geometry/duplicate MTD indexes, and keeps the generic-core warning separate from chip ECC observations. All 17 regression tests pass.

Derived observations are in [findings/nand-boot-observations.json](findings/nand-boot-observations.json), with source artifact hashes and reviewed entry points in [findings/nand-source-contract.json](findings/nand-source-contract.json). No full boot log, calibration, flash dump or vendor implementation body is published. No reboot, register access, flash write or alternative image boot was performed for this milestone.

Before bootloader work, establish the exact raw spare-area representation, bad-block marker rules, boot-stage mapping compatibility, ROM authentication policy and an external recovery path. A VB235v device tree, build and interrupted-update recovery tests are still required.
