# M6: Relocation-backed NPU call sites and host-descriptor layout

## Direct-call evidence from the actual modules

Analysis of the SHA-256-verified live artifacts recovers 71 retained direct-call/tail-branch relocation sites in `npu.ko` and 202 in `npu_wifi.ko`. The tool validates the AArch64 B/BL instruction class and requires the branch to lie inside a sized function symbol.

In the captured `npu.ko` (16,688 bytes), `init_module` calls `set_npu_needed_info`, `boot_npu_all_cores`, `get_ecnt_npu_dev`, and `host_notify_npuMbox`. The module is an entry point into additional implementation, rather than a complete self-contained NPU stack.

In `npu_wifi.ko`, `npu_wifi_oper_init` makes four retained calls to `host_notify_npuMbox` and obtains receive/transmit-buffer addresses and force-to-CPU state. Additional retained mailbox calls occur in the debug-counter address helper. These are static call-site observations, not evidence those paths were executed.

The relevant filtered call sites are recorded in `findings/npu-host-interface.json`. Section offsets are file-object offsets, not live kernel addresses.

## Provider coverage

After deduplicating the identical PPP module copies, the 79 captured module objects yield 71 unambiguous cross-module provider edges. `npu.ko` resolves two imported symbols to `npu_wifi.ko`, while core APIs such as `host_notify_npuMbox` and `get_ecnt_npu_dev` are not exported by the captured module set. The implementation could be built into the original kernel or reside in an uncaptured component; the current evidence does not choose between those possibilities.

The `depends` modinfo field is not a complete description of vendor callbacks, exported globals, or built-in provider APIs. Missing `mt_wifi.ko` also limits the Wi-Fi provider graph.

Update: [M7](STOCK-MODULE-COVERAGE.md) completes loaded-module file coverage, including `mt_wifi.ko`. [M8](NPU-CORE-PROVIDER.md) identifies the four named core functions in the live built-in kernel and correlates them with archived source and build exports.

## Source-defined host descriptor

The selected `npuMboxAPI.h` has an explicit GPL-2.0-only notice. Its enum and structure declarations give this layout under the ordinary AArch64 C ABI (4-byte enums/u32, 8-byte pointers/unsigned long, default alignment):

| Field | Offset | Storage bytes |
| --- | --- | --- |
| core selector | 0 | 4 |
| function selector | 4 | 4 |
| virtual-address value | 8 | 8 |
| physical-address value | 16 | 4 |
| length | 20 | 2 |
| padding | 22 | 2 |
| flags storage | 24 | 4 |
| timeout, source units 100 microseconds | 28 | 4 |
| callback-address value | 32 | 8 |

The resulting source-derived descriptor size is 40 bytes. Function selectors cover Wi-Fi, tunnel, notification, DBA, TR471 and hardware NAT. This is a host-side descriptor passed to an API, not proof of the firmware mailbox's register/wire layout or its DMA address rules. Live compiler/layout/handler validation remains outstanding.

`tools/npu_mailbox_capture.py` decodes an already saved descriptor according to that explicitly stated layout. It does not dereference addresses, invoke callbacks, allocate DMA, contact hardware or send commands. `tools/module_calls.py` reads the module objects offline; it is not a full disassembler or control-flow analysis.

## Source and validation boundaries

Other supplied Wi-Fi mailbox headers carry a proprietary notice. They remain local and are not copied into this repository. The initial public contribution consists of authored interface notes, artifact/source hashes, and independent offline tools; it does not redistribute those implementation bodies or firmware blobs.

Before implementing an integration layer, locate the live core provider, establish its locking/completion and timeout behavior, confirm pointer/physical-address widths and coherency, and match the firmware build and command semantics. No speculative NPU command or MMIO write was issued for this milestone.
