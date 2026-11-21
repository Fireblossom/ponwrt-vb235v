# M65: native Wi-Fi station tests in RAM

The M64 Linux 6.18.60 RAM kernel loaded native mt76 `0936617d` modules, the
MT7990 firmware, iw and wpad-mbedtls. The guarded driver accepts the owner's
7680-byte ART EEPROM only on the exact M64 development board. Missing or
incompatible calibration fails initialization; generic reference fallback is
disabled there. Credentials and calibration binaries are private inputs and
are not included in this source or its runtime package.

After building the M60 packages and M64 image, run `python3 prepare.py TREE`.
Select `CONFIG_PACKAGE_wpad-mbedtls=m` and `CONFIG_PACKAGE_wpa-cli=m`, run
`make defconfig`, and compile `package/network/services/hostapd/compile` and
`package/kernel/mt76/compile`. Package the result with
`../../tools/package_wifi_station_runtime.py TREE --kernel-config FROZEN_CONFIG
--output NEW_DIRECTORY`. The tool checks the exact RAM kernel configuration,
module vermagic, AArch64 ELF dependencies and the calibration guard. Keep the
kernel configuration unchanged; do not force incompatible modules to load.

Load the runtime and separately supplied private calibration into RAM. The
driver exposes one wiphy with two radios/bands, rather than two separate phys.
The in-driver EEPROM digest matched the extracted ART input. A managed station
interface sequentially authenticated to the owner's authorized 5 GHz and
2.4 GHz networks with WPA2-PSK/CCMP, acquired DHCP leases and reached each
gateway. Each band passed an 8 MiB random download and upload with matching
SHA-256. Station RX/TX byte counters verified the wireless data path. Both
PCIe links remained 5.0 GT/s x1 afterward.

The temporary data receiver was on the workstation's main wired LAN, reached
through the router's wireless station. The isolated USB LAN remained the
control path. No bridge was created. Management listeners were explicitly
bound to the isolated LAN before association. The prototype's managed Dropbear
configuration could not find a netifd LAN object; the verified session used an
explicitly bound, public-key-only daemon. That service integration still needs
repair before a production image.

These short transfers are integrity checks, not maximum-throughput results.
A sampled 6 Mbps TX rate after a transfer does not establish its data rate.
AP mode, simultaneous dual-band station operation, MLO, Wi-Fi 7/EHT, long-term
stability, persistent Wi-Fi configuration and NPU acceleration remain unproven.
See `../../findings/wifi-station-hardware-m65.json` for allowlisted results.
