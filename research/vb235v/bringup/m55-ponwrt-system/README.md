# VB235v PonWrt system development

This stage creates an independent `airoha/vb235v` subtarget and a
controller-free RAM image containing normal PonWrt userspace. The first
profile is `tplink_vb235v-ram`. It does not provide working wired networking,
Wi-Fi, DSL, telephone, acceleration or persistent installation. Build status
and hardware results must be recorded separately.

The pinned source is PonWrt revision
`dcf140cb1d5d2c15c1d7c353c95c4c2a56629820`, with Linux 6.18.60. The authored
overlay and installer avoid changing the existing reference checkout or
inheriting the Nokia bootloader, ECC, environment and upgrade policy.

The RAM DT retains the verified UART resources, CPU0, GIC, timer and 512-MiB
RAM. Reservations exclude the first 2 MiB, the stock NPU region and the two
stock log regions. It has no storage or Ethernet controller nodes. Normal
PonWrt init, procd, ubus, UCI, netifd, rpcd, uhttpd and Dropbear are selected;
network services cannot be reached until a separate network profile is
integrated. `ponwrt-ram-check` reports actual PID1, ubus and MTD observations.
It does not infer subsystem support from package presence.
The reference QDMA0/QDMA1 windows are also reserved conservatively until DMA
quiescence at the boot handoff is measured. This reservation does not establish
that an arbitrary inherited device has stopped DMA.

Both platform upgrade hooks return an error, including the write hook that
can be reached after forced image checks. There is no production writer.
The image definition emits no sysupgrade, preloader, FIP or factory artifact.

## Reproduce a host build

Use a case-sensitive Linux filesystem and ordinary OpenWrt build
prerequisites. The source/output tree must have no spaces; the research
overlay itself may have spaces in its path.
The wrapper removes relative and whitespace-containing PATH components, which
WSL can inherit from Windows. This avoids OpenWrt recipe splitting and GNU
find's `-execdir` rejection during package installation.

```sh
git -C /path/to/ponwrt worktree add --detach /path/to/new-vb235v-tree \
  dcf140cb1d5d2c15c1d7c353c95c4c2a56629820
sh research/vb235v/bringup/m55-ponwrt-system/build.sh /path/to/new-vb235v-tree 8
```

`prepare.py` requires this exact baseline and refuses to overwrite a different
overlay or existing build config. External feeds are not needed for this core
RAM profile. Downloads retain upstream hash and TLS checks. Build logs and
the final offline FIT/config report are written inside the new tree.

The optional `wifi-compile.config` selects native MT7990 packages for later
compilation without installing them into the RAM rootfs or enabling PCIe.
See [the pinned native-driver audit](../../WIFI-MT7990-CANDIDATE.md).

## Post-rescue system contract

`system-layout.json` defines only the 319 blocks at
`0x5c80000 + 0x4fc0000`. The earlier 320-block whole-slot diagnostic layout is
not accepted. All other logical ranges are enumerated as protected, including
the rescue block immediately before the system body.

`tools/vb235v_system_layout.py` validates this fixed geometry and budgets
kernel, rootfs and rootfs_data. It retains the 512-MiB chip basis for the
40-PEB bad-block reserve, two volume-table PEBs and two UBI operational reserve
PEBs. With no known bad blocks, 275 LEBs remain for volumes. Known bad blocks
first consume the existing bad-block reserve. At least 24 LEBs are left for
rootfs_data; that is volume capacity, not usable UBIFS file capacity.
Fastmap is disabled in this contract; enabling it requires a new capacity and
boot-compatibility review.

```sh
python3 research/vb235v/tools/vb235v_system_layout.py plan \
  --kernel-bytes 8388608 --rootfs-bytes 33554432
python3 research/vb235v/tools/vb235v_system_layout.py prepare-inputs \
  /path/to/reviewed-sysupgrade.bin /path/to/new-inputs \
  --expected-sha256 TRUSTED_COMPLETE_IMAGE_SHA256
```

The second command uses the M41 complete-image inspector, extracts the exact
FIT and used SquashFS bytes, and creates a relocatable ubinize config. The
volumes are static `kernel`, dynamic `rootfs`, and autoresizing `rootfs_data`.
It invokes no flash, UBI attach or formatting operation. The M55 RAM image is
deliberately a different board identity and cannot be used as production input.
An input hash validates identity against the supplied value; it is not a
signature or proof of origin.

## Validation and remaining work

The capacity and compiled-DT/FIT tests exercise reserve accounting, exact
volume limits, rescue exclusion, UART/reservation changes, unexpected nodes,
FIT hashes and kernel placement. The separate
`tools/check_system_ubi_packaging.py` exercises actual mkimage, SquashFS and
ubinize tools, checks extracted bytes and every emitted EC/VID header CRC and
offset. Its synthetic kernel and DT are explicitly offline fixtures.

The first actual image passed host FIT, kernel configuration and embedded
initramfs inspection, then booted on the owner's VB235v through the installed
M54 recovery core. See [M55 hardware evidence](../../PONWRT-RAM-BOOT.md).
Compiler-generated `__symbols__` metadata is allowed only when its complete
contents equal the two expected GIC/UART label paths; peripheral admission
remains exact.

Next gates remain audited wired/PCIe profiles,
native NAND/ECC/mapping integration, production UBI mounting and boot,
protected sysupgrade, trial-boot accounting and failure recovery. Cold Reset
entry needs a separately captured installed-hardware result. DSL, analog
telephone and acceleration still require implementation and functional tests;
a successful RAM build does not satisfy those requirements.

The bounded complete-image inspector and explicit-limit FDT parser prerequisites
are published on the research branch. This directory uses those shared tools
and is not a standalone repository.
