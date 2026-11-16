# M18: opt-in USXGMII rate profile on the physical PON PCS

The development patch now implements the rate/profile boundary identified in
M17. An AN7583 PON PCS can explicitly request an Ethernet USXGMII profile. It
keeps the physical register/reset/trim mapping, selects the verified
`1/1/1/1/1` PMA rate tuple, and retains the Ethernet WAN selector `0x12`.
It does not call the optical configuration API that would select `0x07`.

This is a compiled development prototype. Complete calibration behavior,
endpoint boot/discovery, board wiring, DSL synchronization and traffic remain
unvalidated. No device command, reset, module load or firmware boot was used.

## Source changes

Apply these after the complete pinned target stack and M14 development patches:

1. [`952-vb235v-pcs-ethernet-development.patch`](bringup/952-vb235v-pcs-ethernet-development.patch)
2. [`953-vb235v-pcs-ethernet-binding.patch`](bringup/953-vb235v-pcs-ethernet-binding.patch)

The optional PCS property is `airoha,pon-ethernet-mode = "usxgmii"`. The parser
accepts it only on `airoha,an7583-pcs-pon`, requires exactly one string, and
rejects unsupported/malformed values before the existing backend initialization.
Without the property, the existing default rate state and behavior are retained.

The Ethernet profile uses the existing internal symmetric-10G rate entry; that
enum name does not turn the DSL endpoint into an optical EPON endpoint. The
ordinary PCS SCU path still programs the Ethernet route. Four optical APIs,
including configuration, retraining, stop and status, return `-EOPNOTSUPP` for
the Ethernet profile before backend access.

Interface checks cover SCU setup, pre/config/post callbacks, link callbacks,
state reads, AN restart and in-band capability reporting. In particular,
`pcs_pre_config` returns before SCU/reset writes for a non-USXGMII request;
checking only `pcs_config` would have been too late. This does not change the
reference driver's unrelated error handling or establish runtime compatibility.

## Disabled board-development overlay

[`vb235v-pcs-ethernet-disabled.dtso`](bringup/vb235v-pcs-ethernet-disabled.dtso)
sets the profile on `/soc/pcs@1fa08000` and the interface mode on the candidate
gdm2 MAC. Both nodes explicitly remain disabled. It changes no register window,
reset, firmware, memory reservation or NAND configuration.

The overlay was also compiled and applied offline to the full pinned reference
SoC tree, containing 131 nodes. All node inventories and unrelated properties
were preserved. Exactly three property values changed; the repeated disabled
status on the MAC was already present. PCS, MAC, parent Ethernet and NPU all
remained disabled. This is an overlay application check, not validation of a
complete VB235v board tree; baseline DTS diagnostics remain recorded separately.

## Checks and their limits

- Both PCS objects cross-compile with AArch64 GCC 10.2.1 against the prepared
  Linux 6.18.60 target source. No complete kernel link or boot image is produced.
- Both patches reapply to the exact saved originals with fuzz 0. All three
  resulting C/header/schema hashes match the checked development source.
- Checkpatch reports no errors/checks. The driver patch has no warnings; the
  binding has the generic new-file MAINTAINERS warning. Checks use
  `--no-signoff`; these research patches do not claim an upstream DCO submission.
- The binding passes dtschema meta-validation. Two disabled valid examples are
  accepted; five invalid mode/SoC/block/string-count/window examples are rejected.
- All 54 ordinary Python unittest cases pass, including DTC/native helper checks.

The additional host harness compiles selected **actual source functions** with
modeled backends. It first checks all eight input source hashes against the
reviewed snapshot; it does not compile arbitrary replacement sources. Its 647
modeled cases comprise:

| Check | Cases |
| --- | ---: |
| Compare absent-profile result/state/access traces against the original source | 546 |
| Unsupported profile interfaces return before modeled access | 78 |
| Optical APIs reject the Ethernet profile before modeled access | 4 |
| Missing/valid/invalid profile parsing | 8 |
| Valid USXGMII entry callbacks | 9 |
| Ethernet WAN route in pre-config and SCU setup | 2 |

The default comparisons cover seven interface modes, three actual phylink
negotiation settings and both normal/error backend returns. Control enums and
SCU constants come from the reviewed kernel headers. Other register identifiers
and backend behavior are model placeholders. These checks establish selected
control-flow properties, not kernel ABI equivalence, electrical behavior,
register semantics, timing, or the full probe path. The probe-order check is a
source-order assertion; the kernel probe is not executed by the harness.

The hashes, artifacts and outcomes are in
[`findings/pcs-ethernet-prototype.json`](findings/pcs-ethernet-prototype.json).

```sh
# Keep a private copy of pcs-airoha-common.c before applying 952.
sh research/vb235v/bringup/compile-pcs-objects.sh \
  /private/prepared-patched-kernel /private/new-output /tools/aarch64-linux-gnu-
python research/vb235v/tools/check_pcs_profile.py /private/prepared-patched-kernel \
  --reference-common /private/original-pcs-airoha-common.c --output /private/flow.json
python research/vb235v/tools/check_pcs_binding_samples.py \
  /private/prepared-patched-kernel/Documentation/devicetree/bindings/net/pcs/airoha,an7583-pcs-pon.yaml \
  --output /private/schema.json
python research/vb235v/tools/check_pcs_overlay.py \
  --reference-dts /private/pinned-ponwrt/target/linux/airoha/dts \
  --kernel-include /private/prepared-patched-kernel/include --output /private/overlay.json
```

The next step is comparison of the vendor XFI first-plug receiver/reset sequence
with the reference bring-up path. The selected rate tuple and route are only
part of that contract. The development overlay must stay disabled while that
work and the endpoint/FE/GDMA investigation continue.

[M19](PCS-RECEIVER-GAPS.md) subsequently records specific receiver-clock,
TDC-call and post-calibration reset differences that the M18 host model does
not cover.
