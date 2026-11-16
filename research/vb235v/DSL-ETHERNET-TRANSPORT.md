# M15: distinguish the legacy DSL ioctl from Ethernet control paths

The installed software contains multiple DSL control paths. The M3 header alone
does not identify the interface to port. Static analysis now connects DSL
user-space APIs and a loaded kernel module to proprietary Ethernet control
protocols. This is a transport boundary, not proof of a particular companion
chip, live DSL synchronization, or a working replacement driver.

## Verified artifacts and dependencies

Four selected regular files were copied over the existing root SSH connection;
device SHA-256 before/after transfer and local readback agree. No vendor binary
was executed. Sizes, hashes, dependencies and six selected GOT witnesses are in
[the screened findings](findings/dsl-ethernet-transport.json).

| Installed artifact | Static observation |
| --- | --- |
| `xdsl_cmd` | Needs `libapi_lib_xdslmgr.so.1`; imports mode/annex setters |
| `libapi_lib_xdslmgr.so.1.0.0` | Contains `/dev/xdsl`; imports `open`, `ioctl`, `close` |
| `libblapi_xdsl.so` | Needs `libpt.so.1`; imports `SRC_blapi`; no `ioctl` import |
| `libpt.so.1.0.0` | Exports `SRC_blapi`, packet open/send/receive; imports socket, sendto, recvfrom and ioctl |

The four explicitly checked device nodes `/dev/xdsl`, `/dev/xdsl0`, `/dev/bbu`
and `/dev/mdio` were absent. This does not exclude another device name, a node
created later, or a different namespace. The old ioctl number remains an
unissued source-derived interface rather than a verified live handler.

## User-space Ethernet path

Manual review of the pinned AArch64 functions and their GOT relocations finds:

1. `blapi_xdsl_client_command` builds a 192-byte host record, places
   network-order values 22 and 1 at offsets 4 and 8, and copies a command string
   at offset 16 before calling `SRC_blapi` through GOT slot `0x26f50`.
2. `SRC_blapi` calls `pt_fd_open` with a value whose low 16 bits are `0xbeea`;
   its send/receive calls use the same protocol selector.
3. On its socket-creation branch, `pt_fd_open` calls
   `socket(17, 3, htons(protocol & 0xffff))`: Linux AF_PACKET, SOCK_RAW.
   Its ioctl import therefore must not be treated as proof of `/dev/xdsl` use.
4. That function obtains 40 bytes of interface metadata using System V shared
   memory key `0x1492`. For protocol `0xbeea`, a clear metadata flag bit can
   return 2 before socket creation. The research did not attach to that segment.

The 192-byte host record is **not a complete proven wire format**. `SRC_blapi`
constructs a separate buffer, and `pt_pkt_send` adds Ethernet framing. The
destination, discovery, reset/boot lifecycle, response correlation, locking,
timeouts and payload semantics still need review. An additional
`/tmp/atmcmd_sock` string in `libblapi_xdsl.so` belongs to another possible
control path; it does not establish the transport of every exported API.

## Kernel DSL proc path

The verified stock `client_info.ko` supplies DSL-related proc handlers. Its
relocations and manually reviewed initializer show:

- The interface-name pointer resolves to `ae_wan`.
- A `packet_type` object at `.data + 0x70` starts with network-order `0xbeed`.
- Its function relocation at `.data + 0x80` resolves to
  `client_proc_skb_recv`; the initializer passes the object to `dev_add_pack`.
- `client_proc_send_packet` writes EtherType `0xbeea` at Ethernet offset 12
  and calls `dev_queue_xmit`.

This establishes an additional kernel Ethernet request/reply implementation.
It does not prove that its framing or command namespace equals the user-space
`SRC_blapi` implementation. Reading a DSL proc file may transmit a request;
none of those diagnostic handlers was read during this milestone.

## Runtime metadata has narrower meaning

A bounded read-only snapshot of process maps and existing AF_PACKET socket
metadata found 47 processes mapping `libpt`, 46 mapping `libblapi_xdsl`, and
none mapping the legacy manager. Common framework linkage can explain broad
library presence; it does not show that those processes called a DSL function.

The packet-socket table was unchanged across the collection and contained no
`0xbeea` or `0xbeed` socket. The observed `0xbeec` socket belonged to `hsm`;
it must not be relabeled as a DSL control socket. Short-lived sockets can be
missed, and `/proc/net/packet` does not enumerate kernel `packet_type` handlers.
No packet capture, diagnostic command or injected traffic was used.

## Reproduction and port boundary

`tools/elf_dynamic_inventory.py` extends the existing bounded ELF reader for
AArch64 ET_DYN metadata. It checks dynamic-table termination, string/symbol
indexes, file-backed GOT slots, and selected ADRP/LDR/BLR encodings. Explicit
witnesses prove instruction/relocation correspondence only; intervening register
liveness, control flow and runtime interposition require separate review.
The kernel-module relocation API still rejects ET_DYN objects.

```sh
python research/vb235v/tools/elf_dynamic_inventory.py /private/libpt.so.1.0.0 \
  --witness 0x2104 0x2110 0x2134 \
  --witness 0x17cc 0x17d8 0x17dc --output /private/libpt-inventory.json
python -B -m unittest discover -s research/vb235v/tests -v
```

The port must establish how `ae_wan` is created and connected, how the DSL
endpoint is booted and discovered, and which control/data protocols are needed.
Rebuilding the old ioctl header cannot provide those pieces. Existing binary
libraries also have ABI and dependency requirements; their presence does not
make them drop-in PonWrt packages. No DSL component was loaded, configured or
restarted, and no line state or nonvolatile data was changed.
