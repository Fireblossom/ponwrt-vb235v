# Evidence discipline

Use these labels in research notes:

- **Observed**: directly supported by a local artifact or an instrumented experiment.
- **Source-derived**: found in a named source revision; it may not match the running firmware.
- **Hypothesis**: a proposed interpretation needing a stated test.
- **Validated**: supported by a reproducible test on the target board.

The public hardware summary is observed from the original system's boot log and GPL model configuration. It deliberately omits MAC addresses, serial numbers, passwords, ISP/VoIP credentials, and calibration contents.

For each artifact, store its SHA-256, origin/version, architecture, kernel ABI, and local analysis findings. Hashes of seven reviewed vendor files are supplied in `source-review-manifest.json`; their contents remain local.

Kernel module analysis should begin with section metadata, dependencies, and undefined symbols. Do not load unknown modules merely to inspect them. Tools here do not contact hardware, call ioctls, unload drivers, write registers, erase NAND, or invoke flashing utilities.

A successful RAM boot is not proof that all initialization code is read-only. Permanent installation requires separate validation of board layout, calibration preservation, DSL, voice, and Wi-Fi.
