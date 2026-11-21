# M75: explicit PHY page state and component behavior audit

The original `8811_bbu_api` routine `air_ref_clk_speed` explicitly selects
Clause 22 page 0 before reading register `0x1d`. The native EN8811H callback
read it without selecting a page. A live PHY15 snapshot reproduced page 4,
unpaged AUX `0`, standard-page AUX `0x28`, and restored page 4. Standard
registers still reported link/autonegotiation, which hid this vendor-bank
failure. The correct page's speed field is 1000 Mbps.

The patch uses `phy_read_paged()` with the standard page. Linux's MDIO helper
serializes the page selection/read/restoration and returns read failures.
The original routine's unknown-code default of 2500 Mbps is deliberately not
copied. Existing speed decoding and error handling remain in place.

The exact callback is exercised by `check_status.py`: 130 cases reproduce the
old page-4 failure, decode 100/1000/2500 under all 32 prior pages, propagate
injected MDIO errors and avoid AUX reads while link is down. The executable
runs with ASAN/UBSAN. These host checks do not replace hardware validation.

```sh
python3 check_status.py --source /path/to/kernel/drivers/net/phy/air_en8811h.c \
 --output /private/status-checks.json
sh build.sh /path/to/prepared/ponwrt 8 M75-phy-page-v1
python3 verify_sources.py /path/to/prepared/ponwrt --output /private/sources.json
```

The persistent build retains M73's NAND admission/protection and M72's kernel
integration. It also persists the existing M65 private ART EEPROM guard in
the **mt76 package patch queue**. That guard previously existed only in a
prepared package directory and disappeared during a full rebuild. Installed
M73 had the private input but lacked the driver marker and used a reference
EEPROM. Merely checking that a calibration file was packaged missed this.

Final-source admission now includes the 14 integrated kernel prerequisites,
EN8811H, mt76 EEPROM code, seven NAND policy files and the persistent
kernel/package patch queues. Final artifact
checks must also inspect the actual installer/SquashFS drivers, private-input
hashes and cold-boot calibration result. Firmware, calibration, raw console
logs, keys, credentials and device addresses remain private.

Live replacement on the owner's connected external LAN PHY reached four
1000/full samples, three port reopen cycles, and SHA256-checked 8 MiB traffic
in each direction. This is a one-port 1G integrity result, not qualification
of the other port, 2.5G peers, maximum throughput or routed hardware offload.
Persistent-image results are recorded separately from the live replacement.

The [18-component behavioral audit](../../findings/driver-behavior-audit-m75.json)
distinguishes confirmed defects, intentional protective differences, source
ordering risks and missing coverage. It compares explicit hardware-state
ownership and lifecycle behavior rather than assuming that a loaded driver,
matching version string, successful compilation or a link bit proves
equivalence. The captured original live modules often differ from the GPL/BSP
copies; each source of evidence must keep its provenance.

M75 subsequently passed persistent NAND upgrade and automatic cold boot, with
the private ART marker present and reference fallback absent. Deliberately
invalid calibration correctly prevented creation of an operational wiphy.
However, valid-data rebinding after failed probe did **not** recover: a repeat
with firmware search-path restoration read back first reproduced MSI/vector,
firmware initialization and reset-work warnings. Cold power cycling restored
normal operation. This remains a release blocker for driver failure recovery;
invalid-input rejection alone is not a successful recovery test. No IRQ or
reset workaround is guessed into this image.
