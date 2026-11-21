# M72: PHY reset mapping and PON Ethernet receiver correction

This development continues M71's isolated two-port cable test. It does not
require a routed traffic benchmark, an IP address on either 2.5G interface,
or a bridge between the sockets.

The original startup script pulses GPIO35 and GPIO34 before loading the PHY
driver. Live RAM tests identify GPIO35 as reset for MDIO PHY15 and GPIO34 as
reset for PHY14: only the selected PHY stops answering its ID while held low,
and the expected ID returns after release. Both inherited output-high pin
settings are checked before a pulse. Other GPIO, direction and mux settings
are preserved. These identities are measured; their presence alone does not
establish a working Ethernet driver.

One coordinated reset and native firmware reload produced 2500/full on both
PHYs, but the paired frame test timed out. Three identical repetitions did not
reproduce stable dual carrier. A per-PHY reset/reload candidate also failed its
first link cycle and was restored. Consequently reset is not claimed as a
complete negotiation fix. A reversible replay of the OEM GPIO40 startup state
did not fix negotiation either; its earlier state was restored.

The receiver patch fixes an error introduced by M71's Ethernet profile on the
physical PON block. The electrical RX branch still selected by physical port
type skipped the initialization of `rx_rev0`, `fe_gain_ctrl`,
`rx_force_mode_0` and three RX clock booleans for PON Ethernet. It now selects
that branch using the optical/electrical profile, applies the Ethernet 2.5G
CDR band setting, and preserves the physical PON PLL clock-driver supply
condition. Optical profiles and PCIe's special handling are retained.

The corrected image intentionally uses the existing M71 RAM device profile
and board identity. Its FIT hash, source audit and hardware results identify
the revision. No NAND installation is supported by this recipe.

Build after M71 preparation, retaining its hash-pinned private inputs:

```sh
sh build.sh /path/to/ponwrt 8
```

`prepare.py` verifies all integrated prerequisites, applies the correction
without fuzz and retains it in the target patch queue. `verify_sources.py`
checks the corrected PCS source plus the other M71 prerequisites.

Build the two diagnostic modules with:

```sh
sh build_probes.sh /path/to/ponwrt /private/new-probe-directory
```

The Windows reset fixture requires the console-pinned M71 connection file,
both unused ports down and unenslaved, and no active native GPIO controller.
It unloads the idle native PHY module, replays only the already configured
reset outputs, verifies selective reset, reloads the image's original PHY
module, then runs M71's raw paired frame fixture. It restores the module and
ports even when the paired test fails. `vb235v_phy_detail.c` reads PHY data and
the PCS MAC/PMA status, restores the PHY page/window mode and does not write
PHY data registers.

```sh
python reset_fixture.py --connection /private/connection.json \
 --reset-module /private/vb235v_phy_hard_reset.ko \
 --status-module /private/vb235v_phy_detail.ko \
 --pair-probe /private/vb235v-port-pair-probe --output /private/new-results
```

Hardware results are recorded in
[the milestone findings](../../findings/phy-reset-receiver-hardware-m72.json).
Stable physical data, port reopen and eventual persistent image integration
must each be validated independently.

The corrected FIT `9d7b8055f147dab4695512546db80b213bc25cbe999e31652226bcbb5596e6b8`
cold-booted successfully. The 1G management port remained 1000/full and 8 MiB
wire transfers in both directions passed their digests. Both PCS BMSR link bits
were set, including the PON side previously observed unsynchronized. Copper
negotiation and paired frames still did not pass. Matching both Clause 22 and
Clause 45 master/slave controls in either direction did not establish links;
the original roles were restored. The public reset fixture subsequently
reproduced selective reset and both copper PHYs at 2500/full, but the first
physical frame still timed out. Another identical reset did not reach dual
carrier. Both PCS link bits were set in the earlier cold-start snapshot; a
later reset snapshot had the PON-side bit clear. These observations do not
establish stable PCS synchronization or stable copper negotiation. The
planned reversed-direction and promiscuous-mode trials were not reached in
that repeat because the required dual carrier was absent.

Adding the original startup's packet-pool settings before QDMA, together with
corrected module order, allowed the byte-exact original kernel's wired drivers
to initialize in RAM. Its same 1G socket also reported 1000/full. The original
PHY, MAC and management modules reported both external PHYs down even after
explicit power-up. This is still a limited RAM comparison: the MAC modules
reported an XSI interrupt-registration failure and factory userspace was not
run, so it does not establish a full factory 2.5G baseline.

The original firmware's cable diagnostics reported open pairs in both
directions, but also timed out in NLP Hi-Z detection on every pair. These are
inconclusive diagnostics, not proof of a bad cable. A verified cable or an
independent PHY peer is needed for the next hardware control.
