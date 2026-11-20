# M61: original DSL link-status parser and failure semantics

The original `libblapi_xdsl.so` does not route every DSL getter directly through
`SRC_blapi`. Its `blapi_xdsl_get_xdsl_linkstatus` opens
`/proc/tc3162/adsl_stats` with flags `0x800` (`O_RDONLY|O_NONBLOCK`), reads up
to 127 bytes, copies a zero-terminated result into a caller's 128-byte text
buffer and searches for case-sensitive substrings.

The actual unchanged ARM64 instructions were executed under Unicorn 2.1.4,
with only bounded in-memory substitutes for open/read/close, memory functions
and substring searches. The exact library hash is pinned. Guest syscalls and
all other imports are rejected. Neither the proc file nor a DSL endpoint was
accessed on the host or router.

| Modeled parser input/result | Return | Caller state word |
| --- | ---: | --- |
| Contains `up`, without `PTM` | 0 | 1 |
| Contains both `up` and `PTM` | 0 | 2 |
| No `up`, empty read, open failure or read failure | -1 | Unchanged |

This establishes the original classification logic, not independently measured
ATM/PTM, modulation, annex or showtime. The caller must check the return value:
a failed query can leave a previous state word untouched. A nonempty down
response may still replace the text buffer before the function returns -1.

Seventeen vectors exercise success, failure, case sensitivity, embedded NULs,
read-boundary truncation and substring behavior. Synthetic `startup`/`backup`
inputs demonstrate that the original check is a substring search; they are not
evidence that the original device produces or mishandles those strings during
normal operation. Complete live proc framing and response freshness still need
verification before choosing a new parser contract.

```sh
PYTHONPATH=/private/unicorn-2.1.4 python3 \
  research/vb235v/tools/emulate_dsl_linkstatus.py \
  /private/original/libblapi_xdsl.so --output /private/linkstatus-model.json
```

This further connects the application logic to the kernel proc/Ethernet
boundary documented in M15. Reading a real DSL proc handler may send a query;
the emulation has no such backend. `findings/dsl-original-linkstatus-m61.json`
records the actual instruction runs and modeled callback counts.

The Telekom extractor was also tightened: both separate original ADSL/VDSL
presets must explicitly enable IPv4 and IPv6 before exporting the normalized
dual-stack profile. This check passes against the pinned factory database;
six profile tests now pass, including rejection of disabled or nonboolean
enable flags. IPv4/IPv6 Internet connectivity remains untested.

Endpoint boot, actual line-state observation, ATM/PTM bearer programming,
VLAN placement and automatic PPPoE after link loss or power loss are still
required. No manual-account fallback replaces the owner's automatic setup
requirement.
