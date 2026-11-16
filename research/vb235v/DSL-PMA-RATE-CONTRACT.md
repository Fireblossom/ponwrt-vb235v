# M17: shared PMA rates do not imply the same WAN route

The vendor DSL USXGMII path uses the same five PMA rate selectors as the
reference symmetric 10G EPON rate entry. Its WAN routing selector is different:
**DSL Ethernet uses 0x12; the optical EPON configuration API uses 0x07**.
Calling that optical API solely to obtain the matching rate tuple would select
the wrong routing contract.

This milestone checks selected numeric source contracts offline. It does not
implement or validate the complete DSL initialization sequence.

## Trace from the Ethernet API to the analog provider

The selected original source
`arch/arm64/mach-econet/bbu_sgmii/an7583/air_xpon_xsgmii.c` has two separate
decisions in the ordinary USXGMII path:

- `xsgmii_chg`: select the USXGMII SCU mode, put 0x12 in the low WAN_CONF byte,
  then perform the PHY reset sequence.
- `XPON_xSGMII_API`: select `Sync_XEPON` for ordinary USXGMII, then call
  `xpon_init`, `fiber_plug_reset` with its XFI-PON first-plug selector, and
  `XFI_PON_PCS_Reset_Release` before the remaining PCS/AN handling.

The PMA definitions are in
`arch/arm64/mach-econet/combo_phy/an7583/pon_pma/src/pon_pma.c`, not the
similarly named PCIe PHY source. `xpon_init` reaches `pon_CfgPhyType`, which
calls `pon_WanSelInit` and sets the shared rate selectors. A bounded exact-token
search located the provider and declarations in the GPL kernel text. Live
kallsyms lists these APIs as built-in text symbols; source identity with the
running build is still not proven.

## Selected numeric comparison

| Rate selection | TXPLL | TX | RX | Analog | Preset |
| --- | --- | --- | --- | --- | --- |
| Vendor `Async_GPON` | 2 | 5 | 3 | 2 | 3 |
| Reference GPON entry | 2 | 5 | 3 | 2 | 3 |
| Vendor `Sync_XEPON`, used by ordinary DSL USXGMII | 1 | 1 | 1 | 1 | 1 |
| Reference EPON 10G/10G entry | 1 | 1 | 1 | 1 | 1 |

All five selectors differ between the GPON and DSL USXGMII rows. The reference
private PCS structure is initially zeroed, and ordinary phylink configuration
does not set its optical `pon_mode`. Its PON-specific analog functions use that
mode for their rate-table lookup. Consequently, an Ethernet use of the physical
PON PCS needs explicit rate selection rather than reliance on the zero/GPON
initial state. This is a source-derived concern, not an observed device fault.

The reference already contains the Ethernet SCU constant 0x12, and its ordinary
PON-block Ethernet setup selects that value for USXGMII. In contrast,
`airoha_pcs_pon_config_rx(EPON_10G_10G, ...)` programs WAN_SEL 7 and accepts
optical electrical settings before starting its receiver path. Equal PMA rate
rows do not make those two APIs interchangeable.

## Reproducible contract checker

[`tools/pcs_rate_contract.py`](tools/pcs_rate_contract.py) reads five private
source copies. It checks two explicit vendor switch cases against two reference
initializer entries, plus the separate vendor Ethernet, reference Ethernet and
reference optical WAN selectors. It rejects ambiguous functions/cases,
unsupported arithmetic/macros and incomplete vectors. Comments and quoted
braces are handled without truncating function bodies.

[The screened result](findings/pcs-dsl-rate-contract.json) records exact source
hashes and numeric facts. No source implementation, binary, device identifier,
raw disassembly or command line is published. The tool does not preprocess C or
prove equivalence of all register operations, timing or calibration.

```sh
python research/vb235v/tools/pcs_rate_contract.py \
  --vendor-pma /private/pon_pma.c \
  --vendor-xpon /private/air_xpon_xsgmii.c \
  --reference-pma /private/pcs-an7583.c \
  --reference-common /private/pcs-airoha-common.c \
  --reference-header /private/pcs-airoha.h \
  --output /private/pcs-rate-contract.json
python -B -m unittest discover -s research/vb235v/tests -v
```

## Constraints for the next implementation

A future opt-in DSL profile should retain the physical PON register/reset
mapping, select the verified USXGMII rate tuple, and retain the Ethernet WAN
route. It should reject incompatible PCS blocks or non-USXGMII requests before
bring-up writes, and keep the optical API separate. Absence of the profile must
preserve the existing reference behavior.

The entire reset, calibration, signal-detect, AN/rate adaptation and endpoint
lifecycle still need comparison. In particular, the vendor XFI first-plug path
has its own receiver-setting/calibration sequence; a matching five-number tuple
does not cover it. No new profile property or hardware programming patch is
introduced by this milestone, and no device command was issued.
