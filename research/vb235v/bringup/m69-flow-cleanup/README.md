# M69: remove hardware flows before unbinding their callback

M68's real-wire tests exposed a lifecycle bug. Deleting a flowtable removed
the direct device callback before final flowtable cleanup could send the
driver FLOW_CLS_DESTROY requests. Bound PPE entries and software cookie
indices survived. Later allocations could reuse a cookie and receive EEXIST
from the Airoha driver, leaving otherwise valid traffic in software.
Diagnostic callback logging reproduced `ret=-17` in both directions. Limiting
the fixture to one flowtable did not fix it; delaying admission with a packet
count was not accepted as the solution.

The patch calls the existing device-scoped `nf_flow_table_gc_cleanup()` while
the callback is still reachable, before FLOW_BLOCK_UNBIND. The cleanup tears
down matching flows and flushes queued hardware work. It does not mask EEXIST
or overwrite a live cookie. Both direct and indirect paths retain their
existing setup logic.

Build the module on Linux after M68:

```sh
python3 build_module.py /path/to/ponwrt /path/to/new-output-directory
```

This verifies the pinned PonWrt revision and baseline netfilter source hash,
copies the five flowtable source files into a new directory, applies the
patch with zero fuzz, and builds against the exact existing kernel. Review
`build-audit.json` and compare its kernel configuration hash with the running
M68 artifact. The frozen M68 FIT itself remains unchanged; M69 is a separately
built replacement `nf_flow_table.ko`, loaded into the RAM development system.
For a later integrated image, apply the same patch to the kernel source and
rebuild/re-audit/retest the complete image. That image is not claimed here.

For the reversible RAM experiment, first save both fw4 offload options, disable
them and reload the firewall so no flowtables remain. Unload nft_flow_offload,
nf_flow_table_inet and nf_flow_table in that order, load the hash-verified M69
module, then reload the original nf_flow_table_inet and nft_flow_offload
modules. Load the private NPU firmware as documented in M68. Restore the
original firewall options after testing. No flash writer is part of this
experiment.

The Windows physical-wire fixtures require Python with Paramiko and an
already console-pinned SSH host identity. Keep the connection JSON outside
the repository:

```json
{
  "Windows_interface_index": 68,
  "host_key": ["ssh-ed25519", "REPLACE_WITH_CONSOLE_VERIFIED_PUBLIC_HOST_KEY"],
  "private_key": "path-relative-to-this-json-or-absolute-private-key"
}
```

Use the actual isolated adapter index. The fixtures bind all client traffic
to that adapter and source `192.168.235.2`, verify RAM root, board identity
and Linux version, and refuse existing fixture tables. The peer is the M68
single-socket router at `192.168.235.1`. They temporarily create virtual
address `.99`, exact DNAT/SNAT rules, and a CPU ingress counter before the
flowtable. The UDP preparation packet is marked untracked and dropped to
avoid creating a conflicting conntrack entry. All test rules, the alias,
sysctls and saved firewall options are cleaned up on normal completion.
Raw logs contain local network identifiers; keep output outside this tree.

```powershell
python run_suite.py --connection C:\private\connection.json --output C:\private\new-results
```

The suite checks UDP and 32 MiB TCP upload/download software controls, hardware
controls, four further pairs of fresh TCP hardware connections, and default
fw4 hardware forwarding in both directions. Every hardware case requires
successful data validation, conntrack HW_OFFLOAD, two distinct matching
bound PPE entries, and fewer than 256 packets at the independent CPU hook.
Software controls must exceed 3000 CPU packets and have no HW_OFFLOAD flag.
Each case also checks that fixture PPE entries disappear after deleting its
flowtable or reloading fw4. The tests use ordinary established-flow admission,
without a packet-count warmup workaround.

The recorded 14-case isolated suite and two default-fw4 cases all passed.
Twelve two-CPU shared-memory probes also ran alongside another default-fw4
TCP upload/download pair; both CPUs remained online and all probes reported
zero errors. These are short functional and lifecycle tests at the observed
100 Mbps link, not peak throughput or endurance measurements. Full gigabit,
both 2.5G sockets, IPv6/PPPoE offload, wireless NPU, crypto, DSL and persistent
installation remain separate work.

During cold re-entry, M54 twice left RX busy set with DMA enables cleared.
The boot gate correctly refused the handoff. A console-only pulse of the
documented FE/PDMA/QDMA resets (SCU `0x1fb00834`, bits 21, 1, 2), preserving
all other bits, cleared both QDMA engines. Two idle samples and the original
FIT CRC/hash checks then passed before boot. The installed recovery image
was not changed; its general shutdown fix remains pending.

Evidence: `../../findings/flow-cleanup-hardware-m69.json`.
