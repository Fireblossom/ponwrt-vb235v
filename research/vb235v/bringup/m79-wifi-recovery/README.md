# M79 Wi-Fi probe failure and reload recovery

Status: source repair and isolated offline validation complete; **hardware regression pending**. This fixes confirmed resource lifetime defects and associated cleanup risks. It is not a demonstrated remote exploit, security CVE, or proof of complete Wi-Fi security.

Baseline: mt76 `0936617dc529ff9da0385221d3fa6de732231177` (`2026.10.28~0936617d`), Linux 6.18.60, M75 private ART patch 120. The board uses MT7993 primary at `0001:01:00.0` and MT799b HIF2 at `0000:01:00.0`. Source hashes and the unchanged guarded EEPROM source are pinned in `baseline-hashes.json` / `patched-hashes.json`.

## Evidence and repair

The controlled M75 invalid-calibration experiment rejected calibration correctly, but a subsequent valid primary bind stalled. Serial evidence includes `MSI already enabled`, firmware/patch-semaphore timeouts, a reset-work scan flush warning, and IRQ40 being disabled. Both experiments and cold recovery are parent-owned evidence in `offline-analysis/m75-calibration-negative-r2` and `m75-negative-r2-recovery-cold`.

The pinned primary probe allocates vectors on the secondary PCI device while requesting both IRQ handlers against the primary's devres. Linux's managed MSI release action belongs to the PCI device passed to allocation. Removing the primary leaves the secondary bound and does not invoke secondary MSI devres release. The next primary bind attempts to allocate already enabled HIF2 MSI. The pinned remove also frees the mt76 device while devm handlers still reference it; failed registration does not unwind the DMA/MCU initialization already completed before EEPROM rejection.

Patch 121 makes the primary explicitly own its requested handlers and native vector allocations on both PCI devices. Its resource ledger distinguishes native vectors from WED-owned resources, avoiding a free after WED detach merely changed the active flag. A supplier device link is established using a retained PCI device reference **before** looking at secondary devm HIF/BAR state. Only `DL_STATE_CONSUMER_PROBE` permits that lookup; absent/unbinding suppliers defer primary probe. The driver core waits for that probe to finish and unbinds an active consumer before supplier removal. HIF list deletion now uses its list lock.

Teardown closes recovery admission, cancels initialization and existing recovery work, unregisters mac80211, and exits the MCU while IRQ/NAPI service still exists. It then parks the TX worker and stops NAPI, clears INITIALIZED, masks IRQs, synchronizes existing handlers, kills their tasklet, masks again, and releases handlers. Recovery workers have their own removal guard against a producer which passed its admission check before teardown. Work is drained again before DMA/RRO/device memory release. Native vectors and the HIF2 reference are released before the device is freed.

Failed registration follows the same cleanup, using DMA/MCU stage flags. RRO lists are initialized before any hardware-init error return. Common DMA cleanup tolerates absent NAPI on partial initialization; its second dummy-netdev allocation failure clears the freed pointer. Coredump cleanup accepts an allocation which never succeeded. EEPROM rejection, the 7680-byte private calibration input, and the prohibition on reference EEPROM fallback remain unchanged.

The existing MT7990 `wfsys_reset()` early return for a fresh device with `hw_full_reset == false` is unchanged. Proper MCU exit may restore firmware-download state, but that is a hardware acceptance requirement, not an offline conclusion. No PCIe/QPHY register sequence was guessed or changed.

## Original firmware comparison

The exact live original `mtk_pci.ko` SHA256 is `237719af024e52fe52b7cfcfc835f57d97809ec300ece6aa0162e16257a7a519` from `offline-analysis/live-driver-evidence/20261115T235533Z/modules/5.4.55`. Its local function names are stripped. Relocations show `free_irq` at text `0x2284` followed by `pci_free_irq_vectors` at `0x229c`; another error-path pair is at `0x4584` / `0x459c`. These demonstrate explicit handler/vector pairing in those live code paths, not the equivalence of every vendor function or every reload path.

GPL/BSP `wlan_hwifi/bus/mtk_pci_dma.c`, SHA256 `8d39d1bf6dc1015472aff28bccb2030d58702bf3721d234b62c585d4234367a5`, names `pci_dma_sw_exit_irq()` and error cleanup explicitly free IRQs before vectors on each transport. Its PCI remove calls transport unregister then free. This is source-level corroboration; the GPL source has not been proven byte-identical to the live original module. The exact live `mt_wifi.ko` and `mt7993.ko` hashes are recorded in the finding JSON.

The original firmware WM build recorded by M66 is `20260421124444`; the negative-test native WM build is `20260720165918`. Both post-driver PCIe rates were measured at 5 GT/s x1. Neither a firmware version difference nor this rate match proves initialization/recovery equivalence.

Primary references: [pinned upstream PCI source](https://github.com/openwrt/mt76/blob/0936617dc529ff9da0385221d3fa6de732231177/mt7996/pci.c), [pinned upstream initialization source](https://github.com/openwrt/mt76/blob/0936617dc529ff9da0385221d3fa6de732231177/mt7996/init.c), [Linux device-link contracts](https://docs.kernel.org/driver-api/device_link.html). The exact local Linux `drivers/pci/msi/msi.c` was checked for `pcim_setup_msi_release()` and `pcim_msi_release()` ownership. Current upstream PCI/init source was inspected as a comparison; this delivery does not upgrade mt76 or claim an upstream security fix.

## Offline validation

`test_host.py PATCHED_MT76 OUTPUT` extracts the actual patched PCI probe/quiesce/release/remove and unregister function bodies into a C harness. With ASan/UBSan it runs 1,440 combinations of native/WED IRQ ownership, HIF2 presence, allocation/request/registration failures, partial initialization stage contracts, primary-only unbind/rebind, and post-DMA versus pre-DMA WED detach boundaries. It asserts no duplicate allocation, vector release after handler release, work draining, MCU service before poller/IRQ shutdown, and no device free with outstanding handlers/vectors/references. Three mutations (HIF2 vector leak, surviving primary handler, surviving reset work) must each fail. The host mocks kernel/firmware/DMA internals: real module unload, PCI-core device-link actions, partial DMA allocation internals and hardware races remain live validation items.

`test_calibration.py PATCHED_MT76 OUTPUT` extracts the **unchanged** private loader and supplies synthetic data only. Ninety-four ASan/UBSan cases cover lengths 0/1/2/400/407/7679/7680/7681/8192, chip ID, each of the eight capability bytes, wrong chip/FEM, missing input and I/O error. Length rejection short-circuits before header/config reads, failed input does not modify the destination, and the successful copy is exactly 7680 bytes. This is a compatibility/size gate, not RF-table authentication: a same-size file with the accepted header/config can still contain bad calibration tables. The existing private full-file image/input integrity checks remain required. No actual private calibration bytes enter the host tests.

`compile_isolated.py BASELINE PATCHED_MT76` replays exact prepared M75 compiler/linker commands in the isolated source copy. Thirty translation units and mt76/connac/mt7996e links pass. It deliberately does not run make against the shared tree. Prepared `mod.c` metadata and the unchanged kernel `.module-common.o` are reused; this is **not fresh modpost or an installable release**. Optional WED/NPU compilation is a separate synthetic compile check, not offload qualification.

`checkpatch.pl --no-tree --strict --no-signoff` reports zero errors/warnings/checks. There is no human signoff or commit. Public validation reports live beside this README; module paths and exact hashes are in `offline-compile-report.json`. No module was loaded or installed, and no SSH/serial/power/flash operation was performed by this agent.

## Integration

Use `python3 prepare.py BUILD_TREE` to copy patch 121 into the package patch queue. It requires the exact pinned mt76 version and SHA256 `753ddae900ba240fd7116f95b23f7c7395099ce6ca67237b2a4ead15980d0dae` of private-calibration patch 120, and refuses to overwrite a different patch 121. It does not rebuild or touch a device.

Reprepare and rebuild the complete mt76 package, run `verify_sources.py PREPARED_MT76 --output REPORT`, and build the full image through the parent's current M77/M78 integration workflow. Full package rebuilding must regenerate module metadata and include the changed common mt76 module as well as mt7996e. Retain the final-image private ART integrity gates. Do not copy only mt7996e over an otherwise unchecked system and do not force-load these compile-check objects.

For independent offline reproduction, `develop_patch.py EXACT_M75_MT76 ISOLATED_MT76` regenerates the patch and hashes after the caller has copied the source tree to its own directory. It should not be used against a different baseline or the shared prepared tree as its destination.

## Parent-only hardware acceptance sequence

Keep COM3 logging and the already-authorized SP3 cold recovery available; a hang must end in bounded recovery rather than repeated blind binds. Start with radios disabled and record the final image/module hashes, EEPROM marker, firmware path parameter, binding state, `/proc/interrupts`, and both devices' `msi_irqs` sets. Confirm ordinary cold boot and the unchanged calibration marker first.

1. Do three primary-only unbind/rebind cycles with HIF2 still bound. After each unbind require no primary handler and **no HIF2 vector belonging to that primary**; after bind require one expected IRQ/vector per active native HIF and a usable wiphy. Compare counts to the initial baseline, rather than assuming an IRQ number stays fixed.
2. Repeat the controlled invalid-calibration test using the existing private fixture. Require `-EINVAL`, no operational wiphy, and no reference fallback. Restore the exact firmware path (NUL clear plus readback for an originally empty path), then bind valid calibration within a bounded interval. Repeat twice only if the first recovery passes. Require no MSI/WARN/scan-work/firmware-timeout/IRQ-disabled messages and no vector/handler growth.
3. Unload/reload the complete mt7996e stack in dependency order while retaining serial recovery, then verify both PCI devices, HIF supplier/consumer linkage and vector counts. Separately test secondary-only unbind: the driver core must first unbind the primary consumer. Rebind supplier then consumer and verify normal operation. Driver-core supplier removal and full module exit cannot be proven by the host mocks.
4. Re-enable each already-authorized station profile separately (5 GHz and 2.4 GHz); require association, address acquisition, bidirectional payload/hash checks, disconnection and reload/reconnection, and then both radios' intended concurrency. Keep Wi-Fi credentials and private EEPROM contents out of public logs.
5. WED and Wi-Fi NPU are separate qualifications. Do not enable a backend merely to test this patch. On a complete matching backend image, repeat failure/unload tests and require no double detach/free or callback after teardown, plus real payload/flow cleanup checks.

After success, record bounded warm restart, ordinary reboot and SP3 cold boot separately. Recheck wired SSH reachability and protected NAND hashes using the established parent workflow. A successful cold boot alone does not close the failed-bind recovery issue. If valid bind still times out, preserve the complete trace and investigate MT7990 firmware reset/state ownership and shared PCIe reset order next; calibration rejection must remain fail-closed.
