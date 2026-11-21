# M68: six NPU cores and real wired IPv4 NAT in RAM

Run `sh build.sh TREE 4` after the verified M67 build at the pinned PonWrt
baseline. Preparation verifies the original or candidate source hashes and
applies the existing 950/951 opt-in AN7583-v2p layout with zero fuzz. The
changed shared offload structure requires rebuilding all mt76 consumers.

This profile retains exactly two usable ARM CPUs, two PCIe hosts, one isolated
LAN socket and no storage controllers. It adds the original six-core NPU IRQ
layout, Ethernet's NPU reference and the native loader's 10 MiB code/heap
reservation at `0x84000000`. NPU core count is separate from ARM CPU count.

The firmware is a private owner-supplied input, absent from the image and this
repository. After RAM boot, supply the exact hash-verified originals as
`/lib/firmware/vb235v/stock-npu-rv32.bin` and `stock-npu-data.bin`, then bind
`1e900000.npu` through the `airoha-npu` platform driver's bind attribute.
Do not replace these inputs with similarly named reference firmware. The
missing firmware at initial probe is expected.

The bounded `../../tools/vb235v_npu_probe.c` module, compiled against the exact
running kernel configuration, reads bootmask `0x3f` and all six program
counters inside the loaded code range. Its existing mailbox GET_INFO request
returns success (`ret=0`, response status word `0x7`). The original firmware
does not answer the generic driver's GET_VERSION command (ID 10); its original
header defines GET commands 0 through 9. A missing version string alone is
not evidence that all cores failed. Heap/SRAM boot parameters are consumed by
firmware and do not retain their initial values for later assertions.

Real-wire hairpin NAT tests send random traffic from a workstation socket
through the physical isolated Ethernet cable, a router virtual address and
DNAT/SNAT, then back to a separate workstation server socket. The server
checks the translated source; clients verify returned addresses and data.
UDP completed 2000 echo exchanges; TCP completed SHA-256 checked 32 MiB
transfers in both directions. Successful hardware runs show matching bound
PPE tuples, conntrack HW_OFFLOAD, and far fewer CPU ingress packets than
software controls. The independent CPU counter runs at ingress priority
`-100`, before either software or hardware flowtable priority `-10`.
PPE byte/packet statistics are disabled in this kernel and read as zero;
those zero counters are not used as evidence of actual forwarding.

The initial repeated suite also reproduced stale driver cookies after deleting
flowtables: a subsequent TCP connection remained in software, with hardware
callbacks returning EEXIST. Therefore M68 proves NPU communication and working
hardware forwarding, not reliable flowtable replacement. The separate M69
cleanup experiment addresses that lifecycle bug. Keep only one test flowtable
active; save and temporarily disable fw4 offload while using the isolated
fixture, then restore its original settings.

The observed isolated LAN link remains 100 Mbps/full. No peak throughput,
gigabit/2.5G result, IPv6 or PPPoE offload, wireless NPU integration, crypto
engine validation, persistent installation or long-term stability is claimed.
The two linked 2.5G sockets remain outside the admitted DT and must not be
bridged into a loop. See `../../findings/npu-hardware-m68.json`.
