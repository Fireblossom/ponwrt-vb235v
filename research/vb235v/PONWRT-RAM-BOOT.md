# M55: PonWrt full userspace RAM boot

The first independent `airoha/vb235v` image has booted on the owner's actual
TP-LinkBox 7. This validates the operating-system base, not a complete router.
Wired networking, Wi-Fi, DSL, telephone and persistent installation remain
unvalidated and are not provided by this controller-free profile.

## Image and host checks

The source baseline is `dcf140cb1d5d2c15c1d7c353c95c4c2a56629820`.
The image is 8,768,860 bytes, SHA-256
`61c775d257a532fa2d90f7a536d865c4d00d6c367caa7f410e51bd471091d34d`.
Its decompressed AArch64 kernel is 28,370,952 bytes and declares 28,704,768
bytes of memory at `0x80200000`, below the retained NPU reservation.

The final FIT contains the exact checked 15,188,992-byte initramfs, with 786
entries. Required BusyBox/procd/ubus/UCI/netifd/rpcd/uhttpd/Dropbear executables
are AArch64 ELF files. The runtime checker matches the authored source.
The kernel configuration rejects the unsafe diagnostic, inherited BMT, UBI
and Ethernet/NPU paths for this profile. Both payload SHA-256 hashes and the
exact UART, GIC, timer and memory reservations passed inspection.

The build encountered two host integration issues: inherited Windows PATH
components caused `find -execdir` to reject package installation, and the real
DT build emitted a `__symbols__` node. The build wrapper now filters unsuitable
PATH components. The DT inspector accepts only the exact two expected label
paths, with a regression case rejecting additional labels. Seven DT/FIT tests
and the previously completed seven system-layout tests pass.

## Actual hardware observations

The owner explicitly authorized COM3 TTL access and SP3 control of the router's
power supply. A 20-second power-off cycle restored power successfully, and the
original OEM U-Boot banner, prompt and version response were captured. The
installed M54 normal core was loaded from its existing third boot block and
checked by RAM CRC32 and FIT payload hashes. Its authenticated recovery HTTP
readback of the complete boot partition remained SHA-256
`42659dd2475afa0824b79882d4cbc74f05fcfb1da1cb34f8da028d037b470354`.
No Reset-button action was performed or inferred from this test.

The new image was uploaded into RAM at `0x90000000`; both the upload SHA-256
and a separate UART CRC32 agreed. After stopping the recovery HTTP service,
two samples of both QDMA global configuration registers showed TX/RX enable
and busy bits clear:

| Register | Both sampled values | Bits 3:0 |
| --- | --- | --- |
| `0x1fb54004` | `0x14080070` | zero |
| `0x1fb56004` | `0x1c0800d0` | zero |

This measures these two engines at this handoff; it does not establish a
general DMA shutdown guarantee for arbitrary inherited peripherals.

`iminfo` verified both FIT payload hashes before `bootm`. Linux 6.18.60 reached
the root console. The runtime checker exited zero and observed:

- Board `tplink,vb235v-ram-development`, PID 1 `procd`, and ubus `system` ready.
- No MTD devices; `/` mounted as tmpfs and no MTD/UBI mounts.
- Readable UCI system configuration and an ubus board report identifying an
  initramfs root.
- netifd, rpcd and uhttpd service objects. Service presence does not prove
  network reachability; this DT has no Ethernet controller.

The first command burst during module startup lost input characters. Paced
read-only UART commands subsequently passed. The current UART identifies as
16550; FIFO/interrupt behavior requires further work before treating burst
console input as reliable. The successful check was performed on the same
running kernel, without repeating the upload or reboot.

No flash-write operation or `saveenv` was sent. The runtime root is ephemeral.
The runtime checker explicitly reports networking, Wi-Fi, DSL, telephone and
persistent installation as false. Structured evidence is in
`findings/ponwrt-ram-hardware-m55.json`, `findings/ponwrt-ram-artifact-m55.json`
and `findings/m55-serial-power-control.json`.
