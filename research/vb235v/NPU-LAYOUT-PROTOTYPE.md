# M14: Opt-in NPU layout implementation and object build

An experimental kernel patch now implements the source-derived six-core NPU layout while retaining the existing eight-core default. **The patched NPU, Ethernet and PPE objects cross-compile as AArch64**, and the example overlay explicitly leaves the NPU disabled. No development module, firmware or kernel was loaded on the router.

This is a build-validated prototype, not functioning acceleration support. Firmware/PPE/Wi-Fi payload compatibility, buffer ownership, interrupts and actual register behavior still need hardware validation.

## Prepared source and implementation

A separate source tree uses the verified Linux 6.18.60 archive, PonWrt reference revision `dcf140cb1d5d2c15c1d7c353c95c4c2a56629820`, the generic files overlay, and all four kernel patch groups in the order used by `include/quilt.mk`: 233 generic backports, 284 pending patches, 75 hacks and 172 Airoha patches, **764 in total**. Eleven patches report context fuzz under normal GNU patch behavior. This source preparation does not build OpenWrt packages, its toolchain, rootfs or upgrade images.

Apply the authored development patches after that target stack:

1. `bringup/950-vb235v-npu-layout-development.patch` adds the driver/layout helper changes.
2. `bringup/951-vb235v-npu-layout-binding.patch` documents and validates the optional profile.

Both reapply with fuzz zero to exact pre-change file copies. All four resulting source hashes match the files used for compilation.

The optional string property `airoha,npu-layout = "an7583-v2p"` is accepted only with the AN7583 compatible. Missing/explicit `legacy` preserves the eight-core profile; unknown/malformed values fail probe. The V2P profile selects:

- Six active cores and boot mask `0x3f`, while retaining the existing eight-slot array capacity.
- IRQ roles of mailbox, six watchdogs, then six WLAN lines.
- The source-derived 128-KiB SRAM information value, versus the legacy 256-KiB value.
- Shared watchdog controls: cores 0–3 use offset `0x310100`, cores 4–5 use `0x310200`; each bank uses distinct interrupt/enable bits. This replaces the legacy per-core `0x100` stride only when explicitly selected.

The shared watchdog path preserves the source-defined enable/control mask, writes only the selected acknowledgement bit among status bits, and serializes host read/modify/write operations with an IRQ-safe spinlock. This follows source-derived register semantics; neither W1C behavior nor concurrent firmware writers have been independently verified. Existing legacy register-layout defaults remain selected when the property is absent.

`bringup/vb235v-npu-layout-disabled.dtso` supplies the 13 IRQ tuples reconstructed from the stock mailbox/WLAN declarations and six live watchdog registrations. It sets `status = "disabled"`, changes no MMIO/reserved-memory/firmware properties, and is not applied to the physical router. The generic PonWrt 10-MiB reservation remains separate from the stock 1-MiB reservation issue.

## Validation

- GCC 10.2.1 cross-compiles `airoha_npu.o`, `airoha_eth.o` and `airoha_ppe.o` against the complete prepared target source. Their ELF headers identify relocatable AArch64 objects. This is translation-unit compilation, not final kernel/module linking or runtime validation.
- The actual added C helper is extracted from the public patch, compiled with `-Wall -Wextra -Werror`, and executed against independent stock register/mask vectors. It checks all six shared-bank lanes, legacy core seven, both boot masks/SRAM values, and invalid core rejection without output mutation.
- DTC compiles the development overlay. Tests enforce its disabled status and compare its IRQ roles with the independently recorded stock facts.
- Dtschema 2024.11 validates the binding document. Two valid disabled-node samples are accepted; three samples with a wrong IRQ count or incompatible V2P selection are rejected. The tests exposed and corrected binding cardinality/conditional issues before publication.
- Kernel checkpatch reports zero errors/checks for both patches. The driver patch has one generic new-file/MAINTAINERS warning; the existing Airoha directory ownership already covers the helper. The binding patch has no warnings.
- The full offline regression suite passes 33 tests in WSL, in addition to the five schema samples.

Hashes, source preparation counts, patch reapplication, object identities and schema outcomes are recorded in [findings/npu-layout-prototype.json](findings/npu-layout-prototype.json). Original vendor code, device logs, firmware blobs, objects and full local configs stay outside the public checkout.

## Reproduction

After preparing the pinned target kernel source and applying both development patches:

```sh
sh research/vb235v/bringup/compile-npu-objects.sh \
  /private/prepared-and-patched-linux /private/new-object-build \
  /private/toolchain/bin/aarch64-linux-gnu-
python3 -B research/vb235v/tools/check_npu_binding_samples.py \
  /private/prepared-and-patched-linux/Documentation/devicetree/bindings/net/airoha,en7581-npu.yaml \
  --output /private/binding-results.json
python3 -B -m unittest discover -s research/vb235v/tests -v
```

The first command intentionally builds three objects only. Neither command connects to a device, enables the NPU, sends a mailbox command, uploads firmware, creates an upgrade image or writes flash. Before enabling the prototype, validate the physical variant, firmware command/payload API, DMA/reserved-memory plan, shared-timer acknowledgement semantics and recovery path. Retaining DSL, telephone and Wi-Fi remains mandatory for the final port.
