# M19: remaining XFI receiver-clock and reset differences

Following the M18 rate/profile implementation, the selected vendor XFI first-plug
path still differs from the reference PON receiver path. Five of six clock
field assignments differ, and the direct TDC/reset helper sequences differ.
These findings concern the analog backend that M18's host control-flow model
deliberately mocked. Passing those model checks does not resolve these gaps.

No additional kernel patch, device command or hardware experiment is introduced
in this milestone. The development profile remains disabled.

## Clock fields

Vendor `XPON_XFI_RX_Setting(Sync_XEPON)` is called after RX preset/TDC-off and
before RX-on in the XFI first-plug case. The reference PON RX rate-1/2 branch
assigns the following different inputs and lacks that dedicated XFI call in its
first-plug function:

| Field | Vendor XFI setting | Reference PON RX branch |
| --- | ---: | ---: |
| RX PHY clock divider | 0x42 | 0 |
| RX PHY clock selector | 2 | 1 |
| RX PHY clock reset release | 1 | 0 |
| CDR PR XFI clock enable | 1 | 0 |
| RX PHY clock selection force | 1 | 0 |
| RX PHY clock selection value | 0 | 0 |

The vendor header gives source addresses `0x1fa8f0d8`, `0x1fa8f10c`, and
`0x1fa8f0cc` for these fields. These lie in the candidate reference analog window
already identified in M16. This records selected source assignments and address
definitions, not a measurement of final live register values. Complete dataflow,
later calibration overrides and register semantics still require review.

## TDC and post-calibration reset

In vendor `fiber_plug_reset`, `XFI_PON_FIRST_PLUG_IN` explicitly calls TDC-off.
Its TDC-on line is commented out. The reference `an7583_pcs_first_plug_in`
explicitly calls `an7583_pcs_pon_tdc_on` for the physical PON block, without an
Ethernet-profile distinction. This is a direct-call difference; it does not prove
that nested helpers leave the hardware TDC in a particular final state.

The vendor XFI case also calls `XPON_DIG_reset` after calibration. That helper
clears reset bits in order `0,6,5,4,2,1,3`, waits 10 microseconds, then sets them
in order `5,4,3,0,6,2,1`. The reference first-plug function instead calls
`an7583_pcs_dig_reset_release`, which has only set operations and a
100–200 microsecond delay. Startup reset handling elsewhere does not by itself
prove equivalence to this post-calibration pulse.

## Reproduce the narrow source check

[`pcs_receiver_contract.py`](tools/pcs_receiver_contract.py) checks the six
explicit XFI writes, their field order/width/address grammar, the selected PON
RX assignments, the direct TDC calls and the reset helper's clear/delay/set
sequence. It rejects changed or unsupported shapes rather than evaluating C.
Synthetic tests cover malformed fields, unsupported address expressions,
commented TDC calls and missing reset delay/profile changes.

[The screened source contract](findings/pcs-receiver-gaps.json) includes source
hashes and the extracted fields. The relevant source locations are:

- `combo_phy/an7583/pon_pma/src/pon_pma.c`: XFI setting, first-plug and reset helpers.
- `combo_phy/an7583/pon_pma/inc/an7583_pon_pma.h`: vendor source register definitions.
- `drivers/net/pcs/airoha/pcs-an7583.c`: reference receiver and first-plug helpers.

The first two paths are below the archived ARM64 `mach-econet` directory.
Raw vendor source remains outside the public tree.

```sh
python research/vb235v/tools/pcs_receiver_contract.py \
  --vendor-pma /private/pon_pma.c \
  --vendor-header /private/an7583_pon_pma.h \
  --reference-pma /private/pcs-an7583.c --output /private/receiver-contract.json
python -B -m unittest discover -s research/vb235v/tests -v
```

The next implementation must reconcile these operations only for the explicit
Ethernet profile, retain the default optical path, and extend backend-level
checks. Eye-scan/calibration details, endpoint lifecycle and hardware validation
remain separate work. Do not infer a complete DSL driver from the rate tuple.
