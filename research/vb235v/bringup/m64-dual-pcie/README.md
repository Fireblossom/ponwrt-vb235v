# M64: dual PCIe RAM development profile

This adds the second AN7583 PCIe host and its QPHY to the M63 RAM profile.
Build M63 first at PonWrt `dcf140cb1d5d2c15c1d7c353c95c4c2a56629820`, then run
`sh build.sh /path/to/ponwrt 4`. The preparation checks both host source hashes.
Changes in the prepared kernel are development overlays; after cleaning that
kernel, repeat M63 and M64 preparation. This is not a persistent installation.

The QPHY sequence and selected register layouts come from TP-Link's VB235v GPL
AN7583 source. `qphy-source-inputs.json` identifies the inputs and functions.
The adaptation reads calibration through the native Airoha eFuse NVMEM provider,
initializes the previously uninitialized INTF_CTRL7 value before updating it,
and returns a timeout after unsuccessful calibration retries. It never exports
the eFuse contents. The port-1 sequence resets its MAC and PERST without pulsing
the shared HB reset a second time.

Hardware RAM boot enumerated auxiliary `14c3:799b` on domain 0 and primary
`14c3:7993` on domain 1, both at 5.0 GT/s x1. The existing isolated LAN passed
8 MiB downloads and uploads with matching SHA-256 and zero RX/TX errors, at
100 Mbps/full duplex. WLAN modules were absent during this milestone; M65
records their separate station tests. Storage, the two connected 2.5G ports,
DSL, voice and NPU are not enabled by this profile.

Prototype limitations remain: port-0 initialization pulses a shared reset, so
port-1 initialization must follow it; a production driver needs explicit
ordering rather than relying on the observed probe order. The second root port
also reports an unassigned 8 GiB BAR0. Its Wi-Fi endpoint BARs are assigned and
working, but that root-port warning remains unresolved.

The four DT admission tests and sixteen M55/M58/M63 regression tests passed.
The modeled C harness executes the selected QPHY functions in 768 cases:

```
cc -std=c11 -Wall -Wextra -Werror -I . ../../tools/qphy_sequence_harness.c -o /tmp/vb235v-qphy
/tmp/vb235v-qphy
```

This validates control flow, field preservation and timeout handling, not analog
timing or electrical behavior. Allowlisted hardware evidence is in
`../../findings/ram-dual-pcie-hardware-m64.json`.
