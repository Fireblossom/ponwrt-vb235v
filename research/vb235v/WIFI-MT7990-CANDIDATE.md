# Native mt76 candidate for PCI 14c3:7993

Checked on 2026-11-20 against the exact mt76 revision already selected by the
pinned PonWrt package: `0936617dc529ff9da0385221d3fa6de732231177`
(source date 2026-10-28). This supersedes the assumption that this PCI ID would
necessarily require porting the complete vendor Wi-Fi framework.

The [pinned header](https://github.com/openwrt/mt76/blob/0936617dc529ff9da0385221d3fa6de732231177/mt7996/mt7996.h)
defines `MT7990_DEVICE_ID` as `0x7993` and its second interface as `0x799b`.
The [pinned PCI registration](https://github.com/openwrt/mt76/blob/0936617dc529ff9da0385221d3fa6de732231177/mt7996/pci.c)
includes both in the primary and HIF tables respectively. This matches the
stock observation of the primary PCI ID, not a completed board validation.

The existing PonWrt package names are `kmod-mt7996e` and
`kmod-mt7990-firmware`; the latter installs the MT7990 WM firmware, ROM patch
and two reference EEPROM files. No PCI table edit is needed to make this
revision recognize the primary ID. Reference EEPROM availability does not
establish that reference calibration is correct for this board.

The driver requests a 36-bit streaming DMA mask and 32-bit coherent mask.
Its EEPROM path requests 7,680 bytes, checks the chip identifier, and can use
flash/NVMEM, extended EEPROM, efuse or default data depending on probe results.
The default-data fallback is a reason to inspect the actual loaded calibration
and radio capabilities before transmitting. The board's ART offsets and
calibration format have not yet been correlated with this native path.

The pinned package enables its NPU build integration only for the AN7581
subtarget. The new VB235v subtarget does not select that condition. Native
PCI operation and acceleration are therefore separate integration tasks.

`bringup/m55-ponwrt-system/wifi-compile.config` is an optional package-build
fragment. It does not add a PCIe node or enable a radio. Before a hardware
experiment, validate PCIe clocks/resets/pinmux, DMA ownership after the stock
boot handoff, actual FEM/antenna/EEPROM data, firmware loading and the recovery
path. Wi-Fi traffic, multi-band operation and acceleration remain untested.

The four inspected upstream files and their hashes are recorded in
`findings/mt7990-native-candidate.json`. No vendor source or device calibration
is included in that record.

## M60: native packages actually compiled

The optional fragment was built on the M58 development worktree with the pinned
PonWrt baseline. Both `kmod-mt7996e` and `kmod-mt7990-firmware` APKs completed.
The staged `mt7996e.ko` is AArch64, reports `6.18.60 SMP mod_unload aarch64`,
and includes PCI aliases for both `14c3:7993` and `14c3:799b`. Its dependencies
are `mt76,mac80211,cfg80211,mt76-connac-lib,hwmon`; no undefined symbol contains
`npu` or `airoha`. This is an output inspection, not acceleration support or
proof of full runtime symbol compatibility.

All four firmware files, including WM firmware, are present and byte-identical
to their build inputs. Both reference EEPROM files are 7,680 bytes. These are
reference files, not extracted or validated VB235v calibration.

Reproduce after completing an M58 host build:

```sh
sh research/vb235v/bringup/m55-ponwrt-system/build-wifi-packages.sh /path/to/vb235v-lan 8
```

The first packaging attempt exposed a missing `drbg.ko`: selecting Wi-Fi adds
kernel crypto dependencies, so the wrapper explicitly rebuilds kernel modules
before packaging. The completed build and offline output gate are recorded in
[M60](findings/mt7990-compile-m60.json). The audit checks the source baseline,
package selections, architecture, vermagic, PCI aliases, dependency set, staged
firmware contents and hashes of both APKs.

No package was installed on the running M58 system. Its kernel configuration
differs from this compile-only configuration; matching version text alone does
not establish module ABI compatibility. PCIe, firmware loading, calibration,
radio traffic and NPU Wi-Fi integration remain untested.
