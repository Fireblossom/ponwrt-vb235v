# M56: original libpt command envelope

The owner's 2026-11-20 request prioritizes reverse engineering the original DSL
implementation while the M55 PonWrt RAM build continues. This stage advances
the M15 user-space packet transport boundary. It is not a replacement DSL
driver or a line-synchronization test.

The exact previously verified `libpt.so.1.0.0` has SHA256
`eb8dc5d2929120e48b58d9bb67a717346a46837e191533f02b957d363f77ff7f`.
Static disassembly identifies its `SRC_blapi` wrapper, `pt_pkt_send`,
`pt_pkt_recv`, and packet-buffer helpers. The implementation was then executed
as ARM64 instructions in Unicorn 2.1.4 with modeled external callbacks.
The vendor library was not loaded through the host dynamic loader.

## Verified wrapper geometry

For this `SRC_blapi` command path, the original instruction sequence produces
204 payload bytes and a 218-byte ordinary Ethernet frame before any physical
link tags/FCS. The EtherType is `0xbeea`. The modeled receive path also uses
`0xbeea`; the M15 `client_info.ko` handler for `0xbeed` remains a separate
interface and must not be assumed to share this complete contract.

All offsets below are relative to the 204-byte payload:

| Offset | Bytes | Observation |
| --- | --- | --- |
| 0 | 4 | Network-order magic `0x75177517` |
| 4 | 2 | Network-order wrapper version 1 |
| 6 | 6 | Zero in the exercised request path; semantics unresolved |
| 12 | 4 | Zero in request; response copied back through `ntohl` to host offset 0 |
| 16 | 4 | Copied unchanged from host record offset 4 |
| 20 | 4 | Copied unchanged from host record offset 8 |
| 24 | 4 | Zero in the exercised request path; semantics unresolved |
| 28 | 160 | Copied unchanged from host record offset 16 |
| 188 | 16 | Copied unchanged from host record offset 176 |

The wrapper accepts a 192-byte host record. It does not copy host offsets 0
and 12 into those corresponding request words. Operation/tail meanings,
command vocabulary, side effects, concurrency and endpoint acceptance still
need investigation. A selector that looks like a query is not assumed to be
read-only.

## Execution checks and limits

`tools/emulate_dsl_libpt.py` verifies the complete library hash, maps its ELF
sections and relocations into an emulator, and invokes the actual `SRC_blapi`
entry. Its internal packet helpers and send/receive wrapper instructions run
unchanged. The initial representative transaction executes 601 guest
instructions. There is a 200,000-instruction and two-second limit per call.

External descriptor setup, memory allocation/copy helpers, byte-order helpers,
logging, the two interface-metadata ioctl calls, sendto, recvfrom, free and
close are modeled. There are no host socket, ioctl, shared-memory, subprocess
or device backends. Unmodeled imports and guest interrupts are rejected.
Interface addresses, descriptor values and replies are synthetic. In
particular, the response status word is supplied by the harness, not observed
from a physical DSL endpoint.

The independently authored `tools/dsl_pt_wire.py` matches the complete request
payload emitted by those actual instructions for 68 input vectors: a readable
fixture, all-zero/all-ones/incrementing records and 64 seeded arbitrary binary
records. The first, second and third allocation failures all return errors
without reaching the modeled send callback. Four ordinary decoder tests cover
independent offset vectors, redaction, VLAN extraction, malformed framing and
the distinction from `0xbeed`.

`dsl_pt_wire.py` only decodes a supplied frame/payload or constructs bytes for
host comparison. It cannot transmit. Its default JSON omits MAC addresses,
VLAN IDs, command text and opaque tail bytes; command text requires the
explicit `--show-command` option. VLAN extraction is host parser coverage,
not an observation that the original endpoint uses VLAN tags.

The sanitized results are in
[findings/dsl-pt-wire-emulation.json](findings/dsl-pt-wire-emulation.json).
Original binaries and full disassembly stay private.

## Reproduction

Install Unicorn 2.1.4 into an isolated analysis environment and provide the
exact locally retained original library:

```sh
python3 research/vb235v/tools/emulate_dsl_libpt.py /private/libpt.so.1.0.0 \
  --output /private/libpt-emulation.json
python3 -B -m unittest discover -s research/vb235v/tests -p test_dsl_pt_wire.py -v
python3 research/vb235v/tools/dsl_pt_wire.py /private/single-captured-frame.bin
```

Next work traces the producer of shared-memory metadata key `0x1492`,
initial interface/endpoint discovery, firmware/reset sequencing, command
serialization and the distinction between this user-space channel and the
kernel proc channel. Actual DSL traffic additionally needs the correctly
initialized SerDes/PCS, Frame Engine path and endpoint control lifecycle.

[M62](DSL-METADATA-READINESS.md) subsequently executes the original consumer's
readiness/interface logic and socket setup against memory-only backends. It
does not establish the producer's complete layout or live endpoint readiness.
