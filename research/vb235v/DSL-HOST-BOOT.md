# M56 follow-up: original DSL host boot chain

Offline extraction from the independently hashed M54 factory-slot0 backup
found a complete original SquashFS at relative offset `0x1000000`, with
48,986,819 used bytes and legacy LZMA compression. Its extracted libpt hash
matches the earlier file copied from the running original system. No router
command, restart, flash write or DSL command was sent for this extraction.

The original `/etc/init.d/rcS.openwrt-21.02.econet` contains a DSL initialization
branch that labels the endpoint **EN7517**. It holds GPIO21 low, loads vendor
MDIO/PHY interfaces, selects the DSL SerDes path, loads `ae_wan`, invokes the
`hsm` host process with interface `ae_wan`, reset argument 21, MDIO argument
24 and skip argument 0, then loads `client_info` with `devName="ae_wan"`.
The fixed internal MAC argument is omitted from this note. Script arguments
are not a measurement of GPIO wiring or evidence that these operations are
safe to replay under a new kernel.

`hsm` is a 26,560-byte AArch64 executable. It depends on libpt, libgcc and libc.
Its static strings reference three supplied endpoint artifacts:

| Original path | Bytes | Role indicated by the host's messages |
| --- | ---: | --- |
| `/etc/iNIC/ddr_cal.bin` | 22,744 | DDR calibration stage |
| `/etc/iNIC/iNIC.bin` | 39,556 | iNIC boot stage |
| `/etc/iNIC/tclinux.bin` | 4,214,743 | Later endpoint image |

The complete host control flow, endpoint execution and firmware compatibility
have not yet been validated. The later image starts with `HDR2`; that is a
format observation, not an independently confirmed CPU/model identification.

Two reviewed hsm call sites set the arguments to shared-memory key `0x1492`,
size 40 and flags `0x3b6` before calling the GOT-resolved `shmget`. This connects
the host loader to the metadata consumed by the M15 libpt command path. The
first site is at `0x4013d8/0x4013e8/0x4013ec`; the second is at
`0x4018b0/0x4018c0/0x4018c4`. The following code attaches and writes metadata;
its complete field/state contract remains to be decoded. Static constants also
include libpt selector `0xbeec` and `0xbeef`; do not assign their complete
message semantics from the constants alone.

An exact filename search of the supplied GPL index found no hsm.c, libpt.c,
inic_server.c or files under an iNIC C/header directory. Three unrelated pt.c
files were found and were not treated as this transport's implementation.
This is a scoped filename result, not a claim about every possible nested
source archive.

The porting boundary therefore includes the original host boot/reset/MDIO
sequence and endpoint firmware, the libpt management channel, and the native
SerDes/PCS/Frame Engine transport. Initializing a generic PPPoE client does not
complete these prerequisites. Original artifacts, executable disassembly and
initialization scripts remain private; hashes and scoped results are recorded
in `findings/dsl-host-boot-artifacts.json`.
