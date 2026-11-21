# Minimum original-runtime evidence needed next

Run collection in the complete original kernel/userspace, retaining COM3 and
factory recovery. The DSL telephone line is not needed for endpoint bootstrap
sampling. Do not run original HSM under the native kernel. Raw traces contain
firmware bytes, interface identities and possibly other private configuration;
keep them root0600 in RAM or the host's private `offline-analysis` directory.
Publish only screened contracts and hashes.

## 1. Read-only inventory, before changing anything

Copy `oem-readonly-inventory.sh` into original `/tmp` and invoke it with `sh`.
It only reads regular proc/sysfs metadata and cached PHY identity attributes;
it does not attach IPC, issue diagnostic ioctls, send packets or touch NAND.
It records the exact running HSM hash/argv, mapped libraries, netdev indices,
MDIO device paths, original boot arguments/log and tracepoint availability.
The output must establish which original kernel and interface actually own
the endpoint/PHY24, and whether HSM matches the pinned image artifact.

This identifies software ownership. It does not prove GPIO40 circuit routing,
GPIO21 bank0 register layout or simultaneous DSL/external-port availability.
Do not test guessed GPIO/MMIO values to answer those questions. Compare the
original board_cfg/serdes_cfg mode-selection caller and its actual ioctl data
offline, then correlate one original UI-controlled WAN-mode change with link
availability and the original selected mode. GPIO direction/pinctrl mode bits
must be verified before a native owner callback can be implemented.

## 2. Passive packet trace on original ae_wan

If a reviewed `tcpdump` exists, this is the exact passive filter:

```sh
umask 077
tcpdump -p -i ae_wan -s 0 -U -w /tmp/hsm-private.pcap \
  'ether proto 0xbeef or ether proto 0xbeec'
```

`-p` avoids changing promiscuous mode. First record the current idle heartbeat
without restarting anything. Verify observed source/destination, host request
and endpoint event lengths, zeros/padding and current interface identity.

The file-transfer questions need a *new* original HSM bootstrap, which resets
the endpoint and changes hardware. Schedule that single controlled action in
the complete factory runtime with serial recovery; the passive collector
must already be running. Use the exact private original arguments saved by
the inventory, not a fabricated identity or a guessed mode. A controlled HSM
restart measures endpoint reset/bootstrap on an initialized host, and must
not be labeled full host cold-start equivalence. A later original cold boot
with early RAM-only instrumentation is required to expose inherited PCS and
clock assumptions. Do not modify an installed factory init script on NAND.

Required packet evidence is narrowly bounded:

- Notify/RRQ/DATA/ACK for the exact pinned tclinux file; filename bytes, block
  indices, lengths and all final/duplicate/reordered behavior.
- Exact two bytes after declared DATA and checksum, including final short and
  zero-length blocks; determine whether their value is meaningful or ignored.
- Full final ACK plus any operation7-15/other final notification, subsequent
  first fresh0xbeec request/response and original SGMII check outcome.
- Retain the original process return/state transition and any observed
  timeout/retry. A host EOF or old handler return0 is insufficient evidence
  of a successful complete image execution.

## 3. Passive MDIO trace, if the original kernel exposes it

The inventory only lists available `mdio` tracepoint names. If the standard
`mdio_access` event is available **and used by this original controller**,
the parent can enable that event in a dedicated tracefs instance and stream
its `trace_pipe` to an original `/tmp` file while the same controlled original
HSM bootstrap runs. Tracefs setup changes instrumentation, not endpoint
register values; no extra MDIO reads or writes should be injected.

Review available RAM and event format before sizing buffers. Stream promptly;
record lost events and timing overhead. Do not assume a trace without the
expected PHY24 traffic is complete. If the proprietary controller bypasses
the standard event, use a narrowly reviewed userspace ioctl interposer or
kernel trace probe that copies the existing call arguments and forwards each
call unchanged. Generic `strace` may show only `ifr_data` pointers and therefore
cannot alone establish the eight-byte vendor MII argument values.

The minimum MDIO evidence is:

- Five-register write32 and gated read32 sequences, controller errors and
  actual mailbox values/timestamps for DDR and both iNIC segments.
- At the final firmware offset, the three CONF/configured-identity writes:
  actual address on *each* call, data/command ordering, announced length and
  endpoint response. Determine whether they really overwrite one RAM word,
  target a FIFO/window, or differ from the selected image artifact.
- After final INDN/finish, the endpoint's acknowledgement and fresh internal
  link/control readiness. Distinguish NOCR/CRC-disabled transfer from verified
  transport integrity; host SHA256 only proves local input identity.

Do not "repair" the repeated address into three increasing addresses from
intuition. Until these observations resolve the contract, the native core
stops at `INIC_TRAILER_UNVERIFIED`. Until actual endpoint execute readiness is
defined independently, the strict file-session core returns
`EXEC_ACK_UNVERIFIED` even after transferring every byte.

## Native owner admission after measurement

Only after those board observations should a board/Ethernet driver register
`pndsl_owner_ops`: quiesce affected DMA/NAPI/IRQs/phylink, select the verified
route/PCS/clocks, check reset-pin direction and alternate-function fields, and
provide deterministic rollback. The provider's DT flags and callback profile
must identify that measured implementation. No generic reset bank0 address,
GPIO40 mux polarity or keep-both-ports promise is supplied by this runtime.

Real line synchronization, ATM/PTM/VLAN service and automatic PPP acceptance
are subsequent gates. Remind the owner to attach the DSL line before those
tests. Neither these bootstrap captures nor offline vectors prove Telekom
Internet service.
