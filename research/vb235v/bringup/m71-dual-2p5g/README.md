# M71: two external 2.5G PHY paths

Build after the verified M70 tree, retaining its private firmware inputs:

```sh
sh build.sh /path/to/ponwrt 8
```

Preparation checks the M70 NPU, crypto and flowtable source prerequisites and
the exact baseline/candidate PCS hashes. It applies the earlier reviewed M59
Ethernet receiver/profile changes and preserves all patches in the target
queue for kernel re-creation. The image has two EN8811H PHYs at MDIO addresses
14 and 15, bounded to 2500 Mbps, plus separate PCS paths for GDM2 and GDM3.
GDM3 receives with source-port ID 0x16. Read-only eFuse cells supply the PON
block's electrical trim values; no OTP programming is involved.

The MAC/PHY side uses 2500BASE-X, matching native EN8811H mode 1. The physical
PON block uses an explicit Ethernet profile and the existing interface-specific
Ethernet PLL/TX/RX sequences, while retaining physical reset and trim resources.
This does not establish DSL functionality. The initial USXGMII candidate did
not establish the paired links and is not a release artifact. The chip's
[interface specification](https://www.airoha.com/products/p/tKkm7DPXi5m6wY2D)
and [upstream driver](https://kernel.googlesource.com/pub/scm/linux/kernel/git/torvalds/linux/+/4dbe5ea929ac5a5b8dc21787d0e79fc55a0ea9ac/drivers/net/phy/air_en8811h.c)
support this mode selection. Actual path assignment still requires hardware
evidence; see the milestone findings for results and limitations.

The first build also exposed missing persistence of M63/M64 PCIe edits when
OpenWrt recreated its kernel sources. M70's shared `preserve_pcie.py` now
replays the hash-pinned host patches and retains QPHY sources/Makefile in the
target overlay and patch queue. A board-specific MAC allocation fix gives
GDM1/GDM3 a common LAN prefix and distinct addresses; their initial independent
random addresses violated the hardware's shared-prefix constraint. Factory
identity reading remains separate from these temporary RAM identities.

Original-module disassembly shows a default polarity register low value of 1;
the modern driver's TX_NORMAL bit is bit 0 and RX_REVERSE is bit 1, so its
default is also 1. No polarity inversion properties are required by that
comparison. `vb235v_phy_status.c` reads the actual polarity, firmware version,
clock output, firmware-ready and negotiation state using the driver's page-4
address window. It changes address selectors, restores page/window mode and
does not write PHY data registers. Build diagnostics with `build_probes.sh`
and run `phy_status_fixture.py --connection ... --module ... --output ...`.

The development image keeps the 1G management socket isolated. Both 2.5G
interfaces start unused, without bridge membership or interface IP settings.
**Never bridge the two sockets while they are cabled to each other.**

Compile `../../tools/vb235v_port_pair_probe.c` with the target's static AArch64
toolchain using `-O2 -std=c11 -Wall -Wextra -Werror -static`. Then run the Windows
fixture over the isolated USB management connection:

```sh
python port_fixture.py --connection /private/connection.json \
  --probe /private/vb235v-port-pair-probe --output /private/new-port-results
```

The connection uses M69's console-pinned format with `board` set to
`tplink,vb235v-ram-multigig-development`. The fixture requires both unused ports
to start down and unenslaved. It enables them temporarily, requires 2500/full
carrier on each, and sends 10,000 full-size frame round trips over the separate
cable. A random nonce and every frame byte are verified at the opposite port;
locally outgoing packet copies cannot satisfy reception. It checks per-port
RX/TX and CRC error deltas, management reachability and both ARM CPUs, and
restores both ports down. IPv4 addressing and a bridge are unnecessary.
This establishes physical data transfer and integrity, not maximum throughput
or NAT acceleration across the two new ports.

## Hardware results

The final RAM FIT is `50c945b59c447222bdce38e211e312ead8f94307effe73b73cd58597814ffea4`.
It cold-boots with the embedded firmware, both ARM CPUs and native userspace.
After the owner changed/reseated workstation Ethernet connections, the isolated
management socket negotiated 1000/full. The firmware had not changed between
the earlier 100 Mbps observation and this result, so the earlier cause remains
unresolved. A further power-off cold boot and three explicit renegotiations
also reached 1000/full. Three 32 MiB HTTP downloads passed SHA256 at 318–324
Mbps; a 32 MiB SSH upload passed too. These application results are not line-rate
benchmarks. RX/TX/CRC error counters did not increase.

All 16 NAT software/hardware control cases passed at the gigabit connection.
Two bound PPE entries, live HW_OFFLOAD, NPU attachment and reduced CPU ingress
counts establish real offload. Twelve dual-CPU shared-memory runs and forty
crypto oracle rounds passed concurrently with fw4 wire upload/download. Native
netifd/wpad station tests passed on both bands, with 8 MiB each direction and
matching digests. Credentials and private firmware are not published.

**The paired 2.5G data path has not passed.** Both PHYs load firmware and read
back polarity low bits 1. One cold run briefly reported 2.5G on one side and
unknown speed on the other; subsequent port-open and cold-first-open trials
did not achieve stable 2500/full on both sides. No paired data success is
claimed. Substituting the original DSP firmware, local clock callbacks,
skipping repeated MCU restart, and paired master/slave role experiments did
not establish stable links. Runtime experiments restore the original image
module/firmware and leave both ports down. The original Linux RAM comparison
did not finish wired initialization, so it supplies no wired link baseline.

See [sanitized findings](../../findings/integrated-multigig-experiment-m71.json)
for the artifact, measured controls and remaining work. Persistent Linux
installation, DSL automatic provisioning and telephone qualification remain
separate, unfinished requirements.
