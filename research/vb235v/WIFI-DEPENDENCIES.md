# M2: MT7993 source registration and NPU dependencies

This milestone audits existing vendor source. It does not claim the driver has been ported or rebuilt.

## Registration chain

The selected GPL `mt_wifi7/src/wlan_hwifi/chips/mt7993/mt7993.c` defines `MT7993_CHIP_ID` as `0x7993` (line 69) and a PCI table with vendor `0x14c3` (lines 1466–1469). The table is assigned to the chip driver descriptor around line 1751, which is registered through `mtk_chip_register()` at line 1911. This matches the PCI identifier observed in the original boot log; a binary/source equivalence check remains separate.

The chip description supplies DMA, interrupt, firmware-download and receive-reordering operations. Firmware normal/test-mode selections occur around lines 1651–1655. Header-embedded firmware is conditional on the vendor configuration, so availability of one firmware representation is not proof every build mode is complete.

## Acceleration is coupled to the bus layer

- `bus/mtk_pci.c:40–43` exports `arht_pdev_pci` under `TCSUPPORT_NPU_WIFI_OFFLOAD`; its comment identifies `npu.ko` as a consumer.
- The PCI path negotiates DMA masks and publishes PCI-device state; this must be considered when changing memory or DMA APIs.
- `bus/en_npu.c:37–38` includes the vendor `ecnt_hook_pcie.h` and `modules/npu/wifi_mail.h` interfaces.
- `mt7993.c:1899–1900` can select `MTK_BUS_NPU` under `CONFIG_HWIFI_HIF_NPU`.

These observations make a bus/firmware integration audit necessary. They do not establish that replacing this bus layer with a generic PCI driver preserves hardware offload.

## Availability audit

`tools/source_dependency_audit.py` checked SHA-256 of 107 locally extracted C/header files under the chosen `mt_wifi7` framework and examined 358 textual includes:

- 163 include paths exist relative to the including source.
- 188 have filename candidates elsewhere in the vendor archive; actual compiler include paths still need evaluation.
- 7 have no filename match. These include conditional headers for other chip variants and `linux/soc/mediatek/muldf.h`; do not assume they are required by this board's selected configuration.

The exact selected OS-abstraction nested archive contains 50 C/header files. It must be audited recursively rather than classified as missing because it is packaged inside `.tar.xz`.

Reproduction uses the GPL archive index and locally extracted source manifest:

```sh
python research/vb235v/tools/source_dependency_audit.py \
  --index /private/gpl-archive-index.jsonl \
  --manifest /private/source-manifest.json \
  --source-root /private/extracted \
  --contains /mt_wifi7/ --output /private/include-audit.json
```

The sanitized summary is in `findings/wifi-source-audit.json`. Vendor source contents and firmware remain outside this repository. Next steps are configuration selection, transitive include resolution, ABI comparison, and matching actual loaded-module metadata before considering a source port.
