# PCIe speed after Wi-Fi driver initialization (M66)

On 2026-11-21, both the original Linux 5.4.55 driver stack and the native
PonWrt Linux 6.18.60 stack negotiated **5.0 GT/s x1** on both Wi-Fi links:

| PCI address | Endpoint | Original post-driver | PonWrt after station tests |
| --- | --- | --- | --- |
| `0000:01:00.0` | `14c3:799b` auxiliary HIF | 5.0 GT/s x1 | 5.0 GT/s x1 |
| `0001:01:00.0` | `14c3:7993` primary | 5.0 GT/s x1 | 5.0 GT/s x1 |

The original early enumeration log reports 2.5 GT/s for the primary endpoint.
It is not a post-initialization measurement. The later sysfs readings on all
four root ports/endpoints were 5 GT/s x1. Direct reads of each endpoint's PCIe
configuration space independently returned Link Status `0x1012`: speed field
2 (5 GT/s), width field 1. These values match PonWrt's later readings.

The comparison used the byte-exact original kernel, original 5.4.55 modules
and firmware, and private ART calibration, with a minimal uncompressed RAM
initramfs. Both chip drivers were present in `/proc/modules` and bound to
their PCI devices. WM firmware build `20260421124444` reached state 3 before
the final reads. NAND nodes were removed and the original `airoha_mtd_init`
initcall was blacklisted; no NAND filesystem or LAN bridge was mounted or
created. The installed recovery partition hash remained unchanged afterward.

This was not a normal complete factory-userspace boot: NPU firmware was not
started, and its vendor adapter logged mailbox timeouts. It establishes the
post-driver PCIe rate, without validating original NPU acceleration, AP data
traffic or maximum wireless throughput. The diagnostic's initial flash-init
crash and missing adapter dependency were resolved before taking the accepted
measurements. No firmware binaries, calibration, credentials or raw console
logs are published.

Machine-readable evidence: [comparison](findings/pcie-post-driver-comparison-m66.json),
[M64 hardware](findings/ram-dual-pcie-hardware-m64.json),
[M65 station transfers](findings/wifi-station-hardware-m65.json).
