# M73: persistent system installation and upgrade development

This profile is being validated on the owner's VB235v. It does not establish
working DSL, analog telephone, AP operation or stable dual-2.5G data. Hardware
installation and upgrade results must be recorded separately from compilation.

On 2026-11-21, initial NAND installation, installed M73 normal-core cold boot,
standard v1-to-v2 sysupgrade with configuration retention, and a second cold
boot of the upgraded system passed on the owner's device. The normal core
is M73; the independent fixed rescue remains M54. See the sanitized
[hardware validation record](../../findings/m73-persistent-install-upgrade-validation.json)
for exact artifact hashes, checks and remaining qualifications. Private images,
calibration, configuration, credentials and raw console logs are not included.

The only writable MTD partition is `vb235v-system`, physical
`0x5c80000 + 0x4fc0000`: 319 eraseblocks, excluding the fixed M54 rescue block.
Factory slot0 and all other physical ranges are read-only. SPI-NAND core also
checks actual physical program/erase requests before device selection or
WREN; a misleading MTD partition cannot bypass that boundary.

Before admitting writes, the driver validates the observed factory BBT/BMT,
identity mapping of blocks 370 through 688, 4096-byte pages, 256-byte OOB,
8-bit/512-byte ECC, zero subpage shift and the pinned early boot, ART and fixed
rescue anchors. It never repairs factory mapping tables. Runtime bad-block
retirement remains disabled: an unexpected failing block must stop the
experiment rather than silently alter factory mapping policy.

Initial formatting uses static `kernel`, dynamic `rootfs` and autoresizing
`rootfs_data` volumes. Standard sysupgrade recreates `kernel` as dynamic and
adds its one-LEB provisioning volume; the normal core reads the exact FIT
length and supports both kernel volume types. VID offset is 4096 and data
offset is 8192. The 512-MiB
backing-chip basis preserves the 40-PEB bad-block reserve. The existing M55
capacity/input preparer retains at least 24 LEBs for `rootfs_data`.

Build after verified M72 preparation, retaining its pinned private inputs:

```sh
sh build.sh /path/to/ponwrt 8 M73-install-v1
```

The normal kernel and the installation initramfs are distinct artifacts.
For RAM installation, explicitly override the boot arguments to `rdinit=/init`
without automatic UBI attachment. Check the complete original system-body hash
before any first format. The production kernel selects the `rootfs` UBI block
volume and mounts persistent UBIFS for configuration.

`image-check.c` parses the complete fwtool CRC envelope, bounded inline FIT,
production board/sequence markers, load/entry address, DTB board and XZ
SquashFS geometry/table bounds. It extracts exact FIT/rootfs bytes and hashes
for the shell hook to verify with SHA256. Firmware metadata must also list
`tplink,vb235v`. CRC and embedded hashes detect corruption; no signature or
secure-boot claim is made. `platform_do_upgrade` repeats the checks in RAM,
then uses the existing NAND UBI upgrade machinery with the fixed system
partition and no bootloader/environment volumes.

The early preinit hook detects an existing network configuration in the
persistent upper directory after backup restoration. The board defaults then
leave existing/restored settings intact; an empty overlay receives only the
isolated management-port setup. This avoids replaying the old RAM profile's
unconditional network reset during an upgrade.

The new normal-core source patch adds read-only system UBI boot and retains
explicit factory boot. The fixed rescue core remains M54. A validated system
FIT and a SquashFS header are required before boot. An unavailable system
returns to the preserved factory path. This is not persistent health
acknowledgement, trial counting or watchdog rollback.

Before flashing a new normal core, test it from RAM and boot the newly
installed system through it. Preserve complete fresh protected-region and
system-body backups. Every write requires independent readback evidence.
Power-cut recovery and sustained flash-wear qualification remain separate.

The first live upgrade attempt stopped before kernel/rootfs writes because
`mktemp` was absent from the stage2 RAM filesystem. Both system-volume hashes
were unchanged and v1 returned. `RAMFS_COPY_BIN` now explicitly includes it.
An isolated chroot built with the actual stage2 binary-selection and library
copy functions reproduced the failure without the dependency and passed image
admission with it. The corrected image then passed the actual NAND upgrade.
The generic stage2 completion message alone is not evidence of a successful
upgrade: verify revision, exact NAND-volume hashes, retained configuration
and reboot independently.

`vb235v-sysupgrade-envelope.h` is a local copy of the existing M41 read-only
framing helper. `build-checker.sh` uses this copy so the persistent profile
has no build dependency on the unpublished M41 directory. Rebuilding with
this local header produced the identical installed checker binary.
