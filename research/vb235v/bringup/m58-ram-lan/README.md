# M58 single-port RAM LAN experiment

This is a separate RAM-only profile, `tplink_vb235v-ram-lan`. It enables the
native AN7583 Ethernet driver, switch CPU port 6 and only physical switch
port 3/PHY 0x0b, connected to the owner's Realtek USB GbE adapter through a USB
hub. The live PHY ID `c0ff0420` matches the pinned native driver. No NAND,
PCIe, NPU, DSL, external-MDIO, GPIO or LED nodes are added.

The strict audit inherits all M55 RAM/UART/interrupt/reservation checks and
enumerates every additional resource, phandle, reset and interrupt. M55's
controller-free gate continues to reject this LAN DT. Five compiled-DT/config
tests cover the allowed port and reject changed PHY/resources or extra
NAND/PCIe/NPU nodes; seven M55 regressions pass after the shared audit refactor.

`NET_AIROHA` selects the NPU driver code at compile time. There is no NPU DT
node in this image, and no NPU functionality is claimed. The SCU clock driver
initialization includes its pinned shared clock/reset register operations;
absence of a PCIe node is not a claim that no shared clock register is touched.

The rootfs remains an initramfs. Existing platform upgrade hooks reject writes.
The additional UCI default creates only `lan-test` at `192.168.235.1/24`, with
a single-client DHCP pool at `.2` and no advertised router/DNS option. It
modifies only the ephemeral RAM root. The old `ponwrt-ram-check` is the M55
controller-free check and intentionally does not admit this different board;
the independent M58 hardware report is authoritative for this variant.

Use a fresh, exact-baseline Linux worktree:

```sh
git -C /path/to/ponwrt worktree add --detach /path/to/vb235v-lan \
  dcf140cb1d5d2c15c1d7c353c95c4c2a56629820
sh research/vb235v/bringup/m58-ram-lan/build.sh /path/to/vb235v-lan 8
```

The implementation run reused the owned M55 build worktree only after
preserving the successful M55 image, configurations and evidence. Explicit
reuse uses `prepare.py TREE --reuse-m55-tree`; it changes the active kernel
configuration and selected device, and must not be described as reproducing
the older M55 image. The M55 wrapper rejects this selected profile.

The resulting image is 8,800,920 bytes, SHA-256
`93befa6fa4cf2b42865551372b218d91e718d7cee84b9ef06722f440f1df1712`.
Its actual DT has 29 nodes. Embedded initramfs, AArch64 programs, exact upgrade
hooks and the additional LAN default script passed host admission. The actual
hardware boot reached procd and the native AN7583/DSA interfaces.

On this socket, DHCP renewal succeeded and an 8,388,608-byte TCP HTTP response
matched the router-side SHA-256. Native RX/TX counters increased; both error
counters remained zero. Transfer time was 0.719 seconds, with a reported
100-Mbps/full-duplex external link. This is one observed transfer, not a
throughput benchmark or validation of gigabit speed. Other sockets, sustained
traffic, IPv6, WAN/NAT, acceleration, Wi-Fi, DSL, voice and installation remain
unvalidated. No flash-write command or `saveenv` was sent.

A subsequent check observed more than five minutes of uninterrupted kernel
uptime and repeated the same download with matching SHA-256. Development SSH
was then authorized only in the current RAM root, with the server host key
cross-checked against COM3. A separate 8-MiB upload also matched its target-side
SHA-256, and RX/TX error counters remained zero. The private workstation key
and server pin are excluded from published artifacts. These finite checks do
not establish long-term reliability or gigabit throughput.

The Linux 6.18 DSA PHY was verified via the MDIO bus sysfs device. The initial
check's older netdev `phydev/phy_id` path was absent; the corrected read-only
check passed on the same running system without another boot. UART commands
were paced, as required by the observed M55 input limitation.

See `../../findings/ram-lan-port-mapping-m58.json`,
`../../findings/ram-lan-artifact-m58.json` and
`../../findings/ram-lan-hardware-m58.json` for structured evidence.
