# Agreed research scope

Owner requirements, clarified on 2026-11-15:

- A recovery-capable U-Boot is acceptable; the Breed implementation itself is not required.
- Hardware acceleration means NAT/packet forwarding, NPU integration, and cryptographic engines, not video decoding.
- Retain DSL connectivity, the analog telephone port, and Wi-Fi.
- Every reproducible milestone gets a separate Git commit and is published on the research branch.

Recovery is a property to test, not an absolute guarantee. A bootloader cannot recover itself if the earlier boot stages, flash, power, or physical recovery path are unusable. Preserve the original boot chain until a board-specific alternative and an appropriate recovery procedure are validated.

On 2026-11-16 the owner explicitly prioritized recovery U-Boot. Recovery development and its own installation gates now take precedence over DSL/PCS work. Requirements for validating DSL, telephone and Wi-Fi still apply to a permanent replacement Linux firmware; they do not require postponing independently validated recovery-bootloader work. See [M20](UBOOT-RAM-RECOVERY.md).

This branch currently contains research, not a supported firmware image. Progress claims distinguish source-derived findings, analysis of original artifacts, and live hardware validation.
