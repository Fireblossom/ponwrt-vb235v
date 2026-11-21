# M63: port-0 PCIe RAM development

This separate, one-lane RAM profile enumerates the **14c3:799b auxiliary Wi-Fi
interface**, not the 7993 primary interface. The actual VB235v boot passed with
PCIe at **5.0 GT/s x1** and working isolated LAN. No Wi-Fi driver or firmware is
installed in this image. RF and station connectivity remain untested.

The first verifier incorrectly expected the primary 7993 device on port 0.
Read-only checks on the same running kernel established 799b instead. Do not
turn that observation into a claim of complete Wi-Fi support. The original
board also has a second host at 0x1fa92000 with a different register interface;
its QPHY and controller still require adaptation for the primary endpoint.

## Reproduce

Start with a completed M58 host build on baseline
`dcf140cb1d5d2c15c1d7c353c95c4c2a56629820`, preserving its artifacts first:

```sh
sh research/vb235v/bringup/m63-ram-pcie/build.sh /path/to/vb235v-lan 8
```

The preparer applies patch 985 to the already prepared kernel source, with
zero fuzz and exact before/after SHA256 checks. It deliberately does not add
the patch to another subtarget or silently modify the reference checkout.
A kernel clean requires preparing/building M58 again before reapplying it.

The development compatible is restricted to this RAM board and port-0 address.
It uses the native MediaTek Gen3 configuration/interrupt implementation and
the existing AN7583 G3 PHY. The additional power sequence follows the selected
GPL `controller/pcie-ecnt.c` function `mt7512_pcie_reset0`: PBUS aperture,
open-drain bit for port 0, host-bridge reset, MAC reset, PERST assertion, PHY
initialization, MAC equalization registers and PERST release. Other PCIe
controllers are absent. The native clock implementation also accesses shared
PCIe SCU fields; this is not proof of zero writes outside port-0-local blocks.
The original pinmux is inherited from the preserved boot chain, and the native
PHY has not yet been proven equivalent to every original efuse/calibration path.

The DT gate admits exactly the PBUS, G3 PHY and port-0 nodes, checks every
resource, reset, clock, interrupt and outbound window, then checks the unchanged
M58/M55 LAN and RAM boundaries. All 16 M55/M58/M63 DT/FIT regression tests pass.
Both sysupgrade hooks still reject writes; NAND and UBI nodes remain absent.

## Hardware evidence

- FIT 8,803,608 bytes, SHA256
  `7e4c571d1475d6b6ee1f7abad14806d6cd5ef3668a0e7316e579a86c45f5634a`.
- User-authorized SP3 cold cycle and COM3 interception; M54 recovery anchors
  and the full boot partition SHA256 rechecked before the RAM upload.
- Native root port 14c3:6899; endpoint 0000:01:00.0, 14c3:799b; 5.0 GT/s x1.
- procd/initramfs root, no MTD or UBI; isolated switch port 3 remains 100/full.
- 8-MiB TCP download and 8-MiB SSH upload hashes matched; RX/TX errors zero.
- No flash writer, saveenv, WLAN module loading or radio transmission performed.

See the [allowlisted result](../../findings/ram-pcie-hardware-m63.json).
Raw serial logs and host public-key pins remain in the owner's private workspace.
