# Driver research roadmap

No complete replacement driver has passed hardware validation. M14 supplies a
compiled opt-in NPU layout prototype; M18 adds a compiled opt-in PCS Ethernet
profile. M12 and M16 add UART and reference PCS build coverage.
An item is complete only when its evidence and validation are recorded.

## Current priority: recovery U-Boot

The owner requested recovery first on 2026-11-16. DSL receiver/calibration work is deferred. [M20](UBOOT-RAM-RECOVERY.md) records the implementation and remaining gates.

- [x] Pin the AN758x U-Boot source and implement VB235v serial and LAN RAM development configurations.
- [x] Exclude NAND/UBI and persistent environment backends; replace the management HTTP backend with bounded RAM upload/status only.
- [x] Cross-build both profiles, run native callback checks and verify FIT payload hashes.
- [ ] Validate factory-to-RAM handoff and the serial prompt on VB235v.
- [ ] Validate physical LAN/PHY operation and recovery-button assignment/polarity.
- [ ] Resolve authentication, physical NAND mapping/ECC and independent early-stage recovery.
- [ ] Implement and test protected persistent layout, image admission and interrupted-update behavior.

## R0: Source and artifact inventory

- [x] Locate MT7993 chip source and the vendor Wi-Fi framework in the GPL archive.
- [x] Inspect the voice driver package recipe and identify its external BSP dependency.
- [x] Record board hardware without device identifiers or credentials.
- [ ] Audit transitive Wi-Fi headers, OS abstraction, connectivity infrastructure, firmware, and build inputs.
- [ ] Locate the precise DSL PHY/DSP driver, firmware loader, and data-plane modules.
- [x] Inventory files for all 86 currently loaded stock module names, their vermagic, imports and module providers; see [M7](STOCK-MODULE-COVERAGE.md). Built-in providers and unloaded components remain to be mapped.
- [ ] Determine which voice BSP components have source versus prebuilt-only artifacts.

## R1: MT7993 Wi-Fi

- [ ] Relate PCI `14c3:7993` to the actual vendor chip registration path.
- [ ] Trace EEPROM loading, ART offsets, firmware messages, and DMA ownership.
- [ ] Separate chip-specific logic from vendor kernel, NPU, and cfg80211 dependencies.
- [ ] Compare with the contemporary mt76 support matrix; do not assume an adjacent chip ID is compatible.
- [ ] Choose source porting or a narrowly scoped upstream-driver implementation based on evidence.

## R2: DSL

M15 establishes Ethernet control boundaries; M16 decodes the boot-selected
DSL/WAN/USXGMII path and compiles the existing PCS sources. Neither establishes
the exact endpoint, its full lifecycle, or working DSL traffic.
M18 implements the explicit rate/profile boundary with disabled development
nodes; complete calibration and endpoint/data-path behavior remain open.

- [ ] Identify the exact PHY/DSP and transport path; PPPoE support alone does not establish DSL support.
- [ ] Map firmware loading, line-state control, interrupts, and ATM/PTM/Ethernet interfaces.
- [ ] Trace user-space ioctls and event messages using read-only observations first.
- [ ] Establish a source-porting path or document the exact missing binary interfaces.
- [ ] Validate synchronization and actual data transfer on the owner's DSL connection.

## R3: Analog telephone port

- [ ] Identify the exact Silabs SLIC model/revision, reset GPIO, SPI, and PCM wiring.
- [ ] Separate SLIC control, PCM transport, DSP/codec processing, SIP, and provisioning.
- [ ] Map module dependencies and external voice BSP build inputs.
- [ ] Validate audio and incoming/outgoing calls; a SIP client alone is insufficient.

## R4: Board bring-up

- [ ] Create a VB235v-specific device tree and NAND layout; preserve board calibration.
- [ ] Document a recovery path appropriate to 4 KiB-page SPI NAND.
- [ ] Inspect potential persistent writes before any RAM-image experiment.
- [ ] Require all three subsystem hardware tests before permanent replacement Linux installation; validate recovery-bootloader installation through its separate gates above.

Record experiments with artifact SHA-256, kernel/config/compiler versions, exact commands, observed results, and reproducible limitations. Avoid speculative hardware register writes.
