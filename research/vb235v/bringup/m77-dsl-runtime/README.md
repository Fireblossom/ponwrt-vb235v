# Native DSL runtime development core

This directory implements the confirmed part of the M77 contract in native C.
It is **not a DSL-ready image**. There is no default DT node, bus name, GPIO
number, board owner, unverified write override, PPP service or fake showtime.
The service is disabled by default. Private firmware is never included.

`core.c` implements the exact C22 bridge sequence, guarded endpoint reset/PLL,
DDR mailbox transfer, confirmed iNIC segments, the mixed-endian ROM envelope,
the exact wrapped whole-file checksum and a strict notify/RRQ/ACK session.
It stops before the unresolved iNIC CONF/MAC trailer. File transfer completion
returns `EXEC_ACK_UNVERIFIED`, not endpoint ready or successful Internet.

`provider.c` uses the new restricted ioctl UAPI, never the old pointer-based
network ioctl. Its AF_PACKET transport validates interface, direction, source,
destination, EtherType, bounds, checksum and transaction sequence. ROM-tail
policy and peer capabilities must be independently verified before it can
transmit. Current kernel provider never advertises the unresolved tail policy.

`runtime.c` hashes all three private inputs before provider CLAIM. Its memory
snapshot is used for subsequent transfers, avoiding file replacement after
verification. The default private directory is `/lib/firmware/ponwrt/dsl`;
filenames, sizes and SHA256 values match `dsl-host-boot-artifacts.json`.
Regular root-owned files with no group/other write permission are required.
Only fixed, sanitized status text is emitted.

## Independent build and tests

Use a build directory without spaces. No shared kernel tree is modified:

```sh
make BUILD=/tmp/ponwrt-m77-host all test
make BUILD=/tmp/ponwrt-m77-asan CFLAGS='-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer' test
make BUILD=/tmp/ponwrt-m77-target CC=/path/to/aarch64-openwrt-linux-musl-gcc all
```

Host tests include exact original ARM64 golden frame/checksum vectors,
32-bit whole-file accumulator overflow, SHA256 standard vectors, each MDIO
step failure, read-gate restoration, rejected short/foreign/zero-checksum
frames, stale ACKs, CRC rejection, deadlines/cancellation and the mandatory
unknown-trailer/execute-ACK blocks. They use modeled hardware only.
Only the immediately preceding acknowledged block can request a replay of the
current DATA, at most three times; replay never advances sequence or readiness.

`host-runtime-test.py /path/to/ponwrt-dsl` runs isolated root-only state/socket
checks on the build host; it uses missing inputs and never calls a hardware
provider. Optional `--firmware-source DIR` copies the three pinned private files
into its isolated temporary directory to verify the real manifest, stopping at
the absent provider. It refuses to run if the build host has `/dev/ponwrt-dsl`.

## State and retry integration

The service atomically publishes root0600 `/tmp/ponwrt/dsl-state.json` with
schema1, current boot UUID, monotonically increasing generation,
`CLOCK_BOOTTIME` timestamp, six stages, bounded fixed-message events and retry
availability. Idle updates occur every5seconds. `line.showtime` is false and
`internet.authenticated/ipv4/ipv6` are false until future real providers exist.

The root0600 Unix datagram endpoint is
`/var/run/ponwrt-dsl-control.sock`. A named root client sends exactly `retry`.
`SCM_CREDENTIALS` and exact command/length are checked. `ACK N` is returned only
after the new generation's running state is atomically published; otherwise
the response is `NACK`. No password, account, IP, MAC or raw command is logged.
Unexpected ancillary messages are rejected; received file descriptors are
closed, including on rejected requests, rather than retained by the daemon.
`--once`, `--state-dir`, `--control-path` and `--firmware-dir` support isolated
integration tests; none bypasses provider, ownership or input validation.

## Kernel provider integration

`provider_kernel.c`, `provider_owner.h`, `provider_uapi.h` and `Kbuild` form an
optional external module, to compile in a **separate reviewed kernel build**.
It is not added to the shared kernel tree or automatically loaded here.
`of_mdio_find_bus()` resolves an explicit `mdio-parent-bus` phandle; no guessed
bus ID is used. `QUERY` is read-only. `RAW_READ` additionally requires an explicit
DT `ponwrt,raw-read-safe` decision and root `CAP_SYS_RAWIO`.

CLAIM requires the exact profile `vb235v-dsl-exclusive-v1`, the pinned manifest,
nonzero generation, DT `ponwrt,board-mode-verified` and
`ponwrt,gpio-mode-verified`, and registered board-owner callbacks. Those
callbacks are **not supplied**: the native board/Ethernet owner must first
quiesce affected queues/NAPI/DMA/IRQs/phylink, establish actual mux/PCS routing,
check GPIO direction and pinctrl fields, and provide restoration. They must
not recursively call the owner-registration API. Merely setting DT flags
cannot supply the missing owner callbacks or prove physical routing.

The reset descriptor is acquired as `GPIOD_ASIS` only after owner admission;
probe never pulses or changes direction. Direction/value changes remain
inside an admitted claim and are read back. No bank0 GPIO registers or GPIO21
global numbering are assumed. A complete bridge transaction holds the real
MDIO bus mutex and calls `__mdiobus_read/write`. Address/value allowlists reject
arbitrary register writes and unresolved final trailer/INDN commands.

The selected native MDIO controller must also have verified bounded completion
and error handling: userspace deadlines cannot interrupt an indefinitely
blocked kernel callback. Zero-checksum receive frames are currently rejected;
their actual endpoint policy is another observation required before ROM service
qualification. Rejected decodes and failed encodes clear output metadata.

RELEASE or file close asserts endpoint reset while the claim is still owned,
then invokes the board owner's restoration. A failed restoration poisons the
provider against future claims. Open-file references survive driver detach;
new operations fail after detach. No firmware blob is accepted through ioctl.

## Package integration

`python3 stage-package.py /new/package/ponwrt-dsl-runtime` stages an ordinary
OpenWrt userspace package in a new directory. It includes only authored source,
disabled init/config files, and no firmware, DT or kernel ownership activation.
The parent integrator may add it to an image after review. Service activation
alone cannot bypass the kernel owner contract.

## Remaining release gates

The independent M76/M77 findings still apply. Actual board-mode ownership,
GPIO layout/pinmux and physical routing require original-system evidence.
The repeated-address iNIC trailer, ROM tail policy and final endpoint execution
ACK remain explicit protocol blockers. The native ae_wan-equivalent datapath,
fresh live line provider, ATM/PTM/VLAN programming, automatic PPP authentication
and IPv4/IPv6/PD service are not implemented by this bootstrap core. Real line
tests require reminding the owner to connect the currently disconnected DSL
line. No host/model result qualifies any of those hardware/service gates.
