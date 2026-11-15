# Driver research roadmap

No missing driver is implemented yet. An item is complete only when its evidence and validation are recorded.

## R0: Source and artifact inventory

- [x] Locate MT7993 chip source and the vendor Wi-Fi framework in the GPL archive.
- [x] Inspect the voice driver package recipe and identify its external BSP dependency.
- [x] Record board hardware without device identifiers or credentials.
- [ ] Audit transitive Wi-Fi headers, OS abstraction, connectivity infrastructure, firmware, and build inputs.
- [ ] Locate the precise DSL PHY/DSP driver, firmware loader, and data-plane modules.
- [ ] Inventory the exact stock modules, their vermagic, undefined symbols, and dependencies.
- [ ] Determine which voice BSP components have source versus prebuilt-only artifacts.

## R1: MT7993 Wi-Fi

- [ ] Relate PCI `14c3:7993` to the actual vendor chip registration path.
- [ ] Trace EEPROM loading, ART offsets, firmware messages, and DMA ownership.
- [ ] Separate chip-specific logic from vendor kernel, NPU, and cfg80211 dependencies.
- [ ] Compare with the contemporary mt76 support matrix; do not assume an adjacent chip ID is compatible.
- [ ] Choose source porting or a narrowly scoped upstream-driver implementation based on evidence.

## R2: DSL

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
- [ ] Keep permanent installation blocked until all three required subsystems pass hardware tests.

Record experiments with artifact SHA-256, kernel/config/compiler versions, exact commands, observed results, and reproducible limitations. Avoid speculative hardware register writes.
