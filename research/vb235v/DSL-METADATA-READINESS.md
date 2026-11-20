# M62: original DSL transport readiness and interface metadata

The original `libpt` `pt_fd_open` function has now run unchanged under ARM64
emulation with modeled IPC and socket callbacks. The exact M56 library hash
is retained. No real System V segment, interface, socket, firmware or device
was accessed.

The consumer requests shared-memory key `0x1492`, size 40, with flags `0x3b6`
(`IPC_CREAT|0666`). Its selected code copies only the first 28 bytes before
detaching. The verified fields for this function are:

| Byte offset | Consumer operation |
| ---: | --- |
| 0 | Native little-endian u32 flags; bit 0 gates selector `0xbeea` |
| 4 | Native little-endian u32 interface copy length |
| 16 | Interface bytes, copied according to that length |
| 8–15 | Copied but not assigned semantics in this result |
| 28–39 | Not read by this selected consumer |

The interface copy is bounded to 12 bytes by this binary. A modeled length of
13 reaches its original `BRK #1000` bounds trap before requesting a socket.
This is a consumer constraint, not a completed reconstruction of every HSM
producer field or a guarantee that arbitrary interface names are valid.

With bit 0 clear, selector `0xbeea` returns **2** without requesting a socket.
With it set, the function requests an AF_PACKET/SOCK_RAW socket and returns
zero when the modeled operations succeed. Other tested selectors
`0xbeeb`/`0xbeec`/`0xbeed`/`0xbeef` do not use that readiness gate in this
function; their complete message roles are not inferred here.

The actual code requests SO_REUSEADDR, SO_BINDTODEVICE with 15 bytes, the
receive timeout passed by its caller, and SO_MARK `0x10`. Option numbers were
checked against the prepared Linux UAPI headers. A modeled socket-creation
failure returns **1**, while a modeled SO_BINDTODEVICE failure closes the
descriptor and requests `exit(1)`. The emulator captures that request rather
than terminating the host. Callers cannot test only for negative errors.

Twenty vectors cover selectors/readiness bits, copy-length boundaries, the
unconsumed suffix and socket/binding failures. The interface and timeout are
synthetic. Callback success does not establish that the device has a usable
interface, privileges, route, endpoint or line synchronization.

```sh
PYTHONPATH=/private/unicorn-2.1.4 python3 \
  research/vb235v/tools/emulate_dsl_metadata.py /private/libpt.so.1.0.0 \
  --output /private/dsl-metadata-model.json
```

This refines the existing software contract: endpoint readiness, real DSL
showtime, bearer selection, bearer/VLAN programming and successful PPPoE are
separate states. The readiness flag alone is not Internet connectivity. M61
also requires checking the original status getter's return value rather than
using its potentially untouched caller state. Both findings inform the new
automatic-connection logic without substituting manual account entry.

`findings/dsl-metadata-readiness-m62.json` contains the instruction runs and
modeled socket options. HSM producer/lifecycle reconstruction and live native
DSL behavior remain open. The owner has confirmed that the DSL line is not
currently attached and requests a reminder before physical DSL tests.
