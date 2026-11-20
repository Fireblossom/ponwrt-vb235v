# M59: reconcile selected Ethernet XFI receiver operations

The M19 source comparison identified five receiver-clock differences, a direct
TDC-on call and a different post-calibration reset sequence. The new
`bringup/984-vb235v-pcs-ethernet-receiver-development.patch`, applied after M18's
952 patch, reconciles these selected operations only for the explicit
PON-block Ethernet profile. Default optical/ETH/USB/PCIe profiles retain their
original path. No device-tree enablement is changed.

For the Ethernet profile, receiver clock parameters become divider `0x42`,
selector 2, reset release 1, XFI clock enable 1, forced clock selection 1 and
clock-select value 0. The post-calibration helper clears bits
`0,6,5,4,2,1,3`, delays 10 microseconds, then sets `5,4,3,0,6,2,1`, matching
the original `XPON_DIG_reset` sequence at `0x1fa8e460`. `regmap_write_bits`
retains each explicit RMW operation even when its value already matches; the
prepared Linux 6.18.60 implementation passes `force=true` to its backend.
The explicit final TDC-on call is skipped for this profile, while the existing
eye-scan call remains. This says nothing about unmodeled nested TDC changes.

## Checks actually performed

The 952+984 patch stack was replayed in an isolated directory and matched the
reviewed candidate bytes exactly. The common and AN7583 objects cross-compiled
as AArch64 using the owned M58 Linux 6.18.60/GCC 14.4.0 compiler flags and
generated headers. Only source, output and dependency paths were redirected.
The active M58 source/build tree and running device were not modified.

`tools/check_pcs_receiver_model.py` checks all seven original/candidate source
hashes before compiling selected actual C functions into a host-only model.
Register offsets/masks and control enums come from the pinned native headers.
The original vendor reset function itself is compiled with memory-only
register and delay callbacks; no vendor library is loaded on the host.

| Model result | Cases |
| --- | ---: |
| Unchanged-profile RX regmap call traces equal the original | 1,008 |
| Unchanged-profile first-plug call traces equal the original | 1,008 |
| New reset call trace equals the original vendor function | 3 |
| Ethernet receiver fields and direct TDC/reset call policy pass | 3 |

The default comparisons cover four port types, seven interface enum values,
all six array indices of the actual optical selector table, two modeled maps
and three initial register patterns. This is finite control-flow coverage,
including the table's unused index, not a declaration that every combination
is a valid hardware mode. The Ethernet cases check all six vendor clock
fields and the explicit TDC/eye-scan/reset calls. Lower calibration helpers
are modeled callbacks; their electrical behavior, timing, side effects and
success are not established.

```sh
python3 research/vb235v/tools/check_pcs_receiver_model.py \
  --kernel /private/prepared-reference-linux \
  --candidate /private/reviewed-952-plus-984-pcs-directory \
  --vendor-pma /private/13-pon_pma.c \
  --vendor-header /private/12-an7583_pon_pma.h \
  --output /private/pcs-receiver-model.json
```

For a clean prepared kernel source, the existing
`bringup/compile-pcs-objects.sh` can compile the patched objects in a new output
directory. Keep the original source copy for the independent default-path
comparison; the model deliberately rejects other input hashes.

Structured results are in `findings/pcs-ethernet-receiver-m59.json`. This step
built objects and ran host models, not a new boot image. DSL remains absent
from the running M58 LAN tree. Endpoint reset/boot, MDIO, complete calibration,
native data transport, real line state, ATM/PTM/VLAN placement and automatic
Telekom PPPoE remain functional gates. Successful LAN traffic does not satisfy
any of these DSL gates.
