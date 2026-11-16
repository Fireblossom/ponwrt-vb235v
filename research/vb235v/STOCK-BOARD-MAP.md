# M11: Stock boot-provided device-tree resource map

A pinned-SSH read-only capture obtained the 20,480-byte `/sys/firmware/fdt` blob with matching device SHA-256 before and after transfer and matching local readback. The bounded parser finds **145 nodes**, independently matching the node count in DTC 1.6.0's decompilation. It emits an allowlisted inventory of 116 nodes and excludes 120 property payloads. The raw blob and decompiled tree remain private because the chosen boot arguments contain device-specific information.

The root compatible is only `airoha,an7583`; it is a generic SoC tree rather than an independently identifying VB235v binding. Node presence is not hardware-function validation.

## Resource facts relevant to bring-up

| Resource | Stock tree observation |
| --- | --- |
| RAM | `0x80000000` + `0x20000000` (512 MiB) |
| ATF reservation | `0x80000000` + `0x50000`, no-map |
| NPU firmware reservation | `0x84000000` + `0x100000` (1 MiB), no-map |
| Ramoops reservation | `0x8b000000` + `0x100000` |
| Persistent log reservation | `0x8b100000` + `0x100000` |
| Console UART | `0x1fbf0000` + `0x30`, SPI selector 18, 1,843,200 Hz, status okay |
| GICv3 | `0x09000000` + `0x20000`; `0x09080000` + `0x80000` |
| Architectural timer | 25 MHz; PPI selectors 13, 14, 11, 10 |
| NPU | `0x1e800000` + `0x80000`; `0x1e900000` + `0x313000`; 15 interrupt tuples |
| PCM | node named `pcm@bfbd0000`, actual reg `0x1fbd0000` + `0x4fff`, SPI selector 27 |
| EIP93 | `0x1fb70000` + `0x804`, SPI selector 44 |

Interrupt selectors above are raw GIC binding numbers, not Linux interrupt numbers. The PCM name/address mismatch demonstrates why node unit names must not be treated as MMIO addresses.

The tree declares four Cortex-A53 CPU nodes, while the previously captured live `/proc/cpuinfo` exposes processors 0 and 1. This does not prove four usable cores. Resolve the difference before describing topology in a new board file.

The NPU reservation differs materially from PonWrt's current AN7583 SoC description, which reserves 10 MiB at the same base. The stock ATF reservation is also smaller than PonWrt's 2 MiB reservation. A future image needs an explicit reservation plan and must not merge trees by merely copying node names.

The MDIO node declares PHY addresses 13, 14, 15, 29 and 31. These are declarations, not a proven mapping of the physical WAN/LAN sockets. Vendor GPIO banks, a polled reset key, and nodes under `leds` named `voip_reset` and `phy_tx_power_disable` are present. Those names can represent functional control signals, so enabling a generic LEDs driver is not automatically harmless. Pin polarity, defaults and board wiring need separate validation.

## Partition offsets

The FDT's logical partition offsets agree with the readable sysfs offset attributes captured from all 13 MTD entries. Selected nonoverlapping views are:

| Partition | Offset | Bytes |
| --- | --- | --- |
| bootloader | `0x0` | `0xc0000` |
| ART | `0xc0000` | `0x380000` |
| misc | `0x440000` | `0x800000` |
| primary firmware | `0xc40000` | `0x5000000` |
| alternate firmware | `0x5c40000` | `0x5000000` |
| reserve | `0xb840000` | `0x40000` |
| runtime data | `0xb880000` | `0x600000` |
| log | `0xbe80000` | `0x800000` |

Kernel/rootfs aliases inside each firmware view must not be counted again. These are the vendor driver's logical offsets, not a raw physical/OOB map; the BBT/BMT and ECC limitations in M9 still apply. No partition was written.

## Reproduction and privacy boundary

```sh
python -B research/vb235v/tools/fdt_board_inventory.py \
  /private/stock.dtb --output /private/board-inventory.json
dtc -I dtb -O dts -o /private/stock.dts /private/stock.dtb
python -B -m unittest discover -s research/vb235v/tests -v
```

The parser implements the [DTSpec flattened format](https://devicetree-specification.readthedocs.io/en/stable/flattened-format.html) with a 1 MiB input cap, bounded block/string accesses, nesting/node limits, and rejection of duplicate paths/properties, invalid phandles, malformed termination and block overlap. It copies only explicitly selected resource properties. Chosen/alias payloads, unknown values, MACs, serials and calibration are excluded. A regression test verifies that private serial and boot-argument values are absent from output; the full suite passes 23 tests.

See [findings/stock-board-map.json](findings/stock-board-map.json) for derived cells and hashes. No driver was loaded, pin was toggled, register was accessed, device was restarted, or alternate DT was booted. The next implementation step is a separately reviewed, UART-only development DT with hazardous peripheral probing excluded, followed by a cross-build and offline policy checks; it is not permission to boot it.
