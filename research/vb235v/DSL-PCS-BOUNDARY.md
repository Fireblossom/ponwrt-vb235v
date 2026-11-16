# M16: stock DSL SerDes selections and the PonWrt PCS boundary

The stock boot-provided FDT selects **SerDes-1 as DSL / WAN / USXGMII**. This is
a more specific porting input than the generic device tree alone. The existing
reference AN7583 PCS implementation also cross-compiles successfully, but its
PON behavior still needs adaptation before it can be used for this DSL path.
No device commands were issued for this milestone.

## Decode board selections without publishing the command line

The selected GPL `drivers/char/arht/arht_serdes.c` parses `rfb_cfg` as one
three-digit hexadecimal record per SerDes port. Its digit order is PHY type,
Ethernet role, interface. `srdsPortCombo` has hexadecimal counts followed by
supported interface indexes. The component-name tables have decimal counts.
The archived compiler command includes `TCSUPPORT_BOARD_SELECT`.

Applying that grammar to the verified private FDT produces:

| Boot port name | PHY label | Ethernet role | Interface |
| --- | --- | --- | --- |
| SerDes-1 | DSL | WAN | USXGMII |
| SerDes-2 | an8811 | LAN | USXGMII |
| SerDes-3 | NONE | NONE | XFI |
| SerDes-4 | NONE | NONE | XFI |
| SerDes-5 | NONE | NONE | NONE |

These are **boot configuration labels**, not measurements of line state, pin
wiring, endpoint chip identity, or current register values. SerDes-3/4 labels do
not establish an active Ethernet endpoint. Two trailing `rfb_cfg` records are
outside the five-port grammar; their values are deliberately not exported.

The new standard-library tool
[`serdes_boot_inventory.py`](tools/serdes_boot_inventory.py) requires the eight
specific fields, validates counts/indexes/options, and exports only the decoded
ports. MAC addresses, boot commands, other board parameters and the complete
command line stay private. Synthetic tests cover malformed/truncated tables,
duplicate fields, decimal/hexadecimal distinctions and exclusion of unrelated
input. See [the boot inventory](findings/stock-serdes-boot.json).

The exact-token archive search examined 52,041 kernel `.c`/`.h` members and
found four matching source/header files. It identifies the board-select parser
and the alternate non-board-select implementation separately. This is not proof
that the archived source bytes match the running kernel.

## `ae_wan` is a vendor data-path driver

The live-file snapshot contains `ae_wan.ko` (97,424 bytes; module license string
`Proprietary`). Its initializer has direct calls to netdev allocation and
registration, SerDes selection, XSI lookup, MAC initialization, IRQ setup and
vendor hook registration. Its transmit function calls `__ECNT_HOOK`; its receive
function reaches `eth_type_trans` and `netif_receive_skb`.

The snapshot resolves XSI, Frame Engine, SerDes-selector and `xsgmii_api` symbols
to the built-in kernel; `macSend` resolves to module `eth`. A kernel `depends`
string alone would miss built-in providers and indirect hooks. A netdev with the
same name would not reproduce the DMA, hook, packet-metadata or initialization
contract.

The GPL package recipe points to `MODULES_AE_WAN_MAC_DIR`; a recipe named
`ae_wan` does not supply its implementation. The `client_info` recipe points to
`MODULES_PRIV_SRC_DIR/client_info`. The selected vendor netifd patches exempt
`ae_wan` from interface-down and state-clearing operations, adding another
lifecycle difference to investigate rather than copy blindly.

## Resource correspondence is an input, not a finished DTS

The stock XSI node has five 0x300-byte windows at `0x1fa08000`, `0x1fa04000`,
`0x1fa07000`, `0x1fa05000`, and `0x1fa09000`. The reference DTS groups larger
MAC/PCS/analog windows into `pon_pcs` and `eth_pcs`, beginning at `0x1fa08000`
and `0x1fa09000`; its gdm2/gdm3 nodes reference those respective PCS instances.
This gives candidate resource correspondences, not a verified VB235v GDMA/port
mapping. The archived feature defines include multiple CPU generations together;
they must not be interpreted as mutually exclusive when reviewing `#if` paths.

The pinned `pcs-an7583.c` chooses optical rate tables for several TXPLL/TX/RX/
analog operations whenever its physical `port_type` is PON. In particular,
`an7583_pcs_common_phya_txpll` selects the PON table before considering the
Ethernet interface-mode switch. Thus using the PON physical block with
`phy-mode = "usxgmii"` alone does not prove Ethernet-mode initialization.
The vendor XPON source has separate selector/initialization paths to compare.

[M17](DSL-PMA-RATE-CONTRACT.md) follows that path to the PMA provider: the
ordinary USXGMII rate tuple matches the symmetric EPON tuple, while its Ethernet
WAN route differs from the optical configuration API.

## Compile coverage

The new [`compile-pcs-objects.sh`](bringup/compile-pcs-objects.sh) and
[`pcs-compile.config`](bringup/pcs-compile.config) build only these reference
objects against Linux 6.18.60 with the complete pinned PonWrt target patch stack:

- `drivers/net/pcs/airoha/pcs-airoha-common.o`
- `drivers/net/pcs/airoha/pcs-an7583.o`

Both compile successfully with AArch64 GCC 10.2.1. Resolved configuration checks
require `PCS_AIROHA`, `PCS_AIROHA_AN7583`, `PHYLINK`, and `NVMEM`. Kconfig selects
PHYLINK through `NET_AIROHA`, which also selects NPU support; this is an object
build configuration, not a configuration to boot on the router. The M14 object
check had not enabled the AN7583 PCS implementation.

Source/config/script/object hashes and the selected dependency facts are in
[the build/boundary record](findings/dsl-pcs-boundary.json). Neither a complete
kernel link nor hardware behavior is validated by these object builds. No DTS
node, MMIO access, reset, DSL request or optical subsystem was enabled.

```sh
python research/vb235v/tools/serdes_boot_inventory.py /private/stock.dtb \
  --output /private/serdes-boot.json
sh research/vb235v/bringup/compile-pcs-objects.sh \
  /private/prepared-kernel /private/new-pcs-output /tools/aarch64-linux-gnu-
python -B -m unittest discover -s research/vb235v/tests -v
```

Next implementation work must distinguish physical PCS location from Ethernet
versus optical programming, retain the endpoint control/data protocols, and map
the vendor FE/GDMA path. DSL synchronization and user traffic remain untested.
