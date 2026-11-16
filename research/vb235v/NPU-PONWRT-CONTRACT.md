# M13: Shared mailbox fields, different NPU integration contracts

The selected stock and PonWrt sources agree on six mailbox function-selector numbers and five control-word masks. That is useful protocol evidence, but **the owner board's observed core/IRQ contract differs from PonWrt's AN7583 description**. The stock modules and firmware cannot be treated as compatible merely by reusing a chip name or renaming a file.

## Reconstructed reference

The comparison pins PonWrt baseline `d9dd3a49f7bb7661c01e9c57c9e2aac2a1114b3e` and its SHA-256-verified Linux 6.18.60 archive. Eight patches targeting NPU driver/header files apply with fuzz disabled to a separate source copy. The last patch reports line offsets, but no context fuzz. These selected files are sufficient for the documented source comparison; this is not a complete OpenWrt target preparation or build.

The driver selects `airoha/an7583_npu_rv32.bin` and `airoha/an7583_npu_data.bin`, or two names supplied by the `firmware-name` property. The package recipe provides the default names. Neither naming nor the two-megabyte/64-KiB loader size limits establish compatibility with the stock `/userfs/` blobs already shown to differ from the GPL reference in M10.

## Shared control fields

| Function | Stock selector | PonWrt selector |
| --- | ---: | ---: |
| Wi-Fi | 0 | 0 |
| Tunnel | 1 | 1 |
| Notify | 2 | 2 |
| DBA | 3 | 3 |
| TR471 | 4 | 4 |
| HWNAT / PPE | 5 | 5 |

The stock argument bitfield, under the target's little-endian AArch64 allocation convention, matches PonWrt masks for wait/block bit 0, done bit 1, status bits 2–4, static-buffer bit 5 and function bits 11–14. This comparison concerns the register argument, not the 40-byte stock host descriptor. It does not compare Wi-Fi/PPE payload structs or firmware-side handlers.

`tools/npu_protocol_compare.py` derives these fields from saved sources, rejects unsupported enum expressions and emits facts/hashes without copying implementation bodies or contacting hardware.

## Six observed stock cores versus an eight-core reference

Three independent pieces of stock evidence agree on six configured NPU cores for this owner build:

1. The archived compiler command selects `TCSUPPORT_NPU_V2` and `TCSUPPORT_NPU_V2_P`; the selected GPL header defines `MAX_CORE_NUM` as six for that branch.
2. Static disassembly of the archived `boot_npu_all_cores` object contains a loop-limit compare against six.
3. The live interrupt snapshot registers `npu_wdog0` through `npu_wdog5`, with SPI selectors 134, 135, 136, 137, 109 and 110.

This establishes the stock build's configuration and six registered watchdogs; it is not a universal silicon-core-count claim about every AN7583 product. The stock FDT also contains unused watchdog declarations beyond those consumed by this build, so the FDT list alone would overstate coverage.

PonWrt's selected header reserves eight core slots and its driver uses that capacity as the active loop bound. Its AN7583 tree declares watchdog selectors 103, 109, 113, 117, 134, 135, 136 and 137. This differs from the stock registered set as well as its ordering.

The positional IRQ contracts also differ:

- Stock: six WLAN IRQs first, then the mailbox IRQ, then watchdog IRQs for configured cores.
- PonWrt: mailbox first, eight watchdog IRQs, then six WLAN IRQs.

Simply changing the stock node's compatible would therefore misassign IRQ roles. An experimental adaptation should keep the eight-slot capacity for existing consumers, use an explicitly validated active-core count for this board, and describe IRQ order for the driver being built. It must remain disabled until the exact variant and firmware initialization are validated.

## Other integration differences

| Contract | Stock source | Selected PonWrt source |
| --- | --- | --- |
| Host entry | exported descriptor API, caller core selection | internal send helper, core 0 |
| Buffer ownership | caller/static-buffer/callback paths | reusable coherent 256-byte per-core bounce buffer |
| Default polling | about 30 ms programmed delay | 100 ms bound |
| Return convention | zero error; nonzero firmware-defined statuses | only firmware status 1 accepted; Linux zero/negative errno |
| Coherent DMA mask | conditional `0xbfffffff` | 32-bit streaming/coherent mask |
| MMIO resources | SRAM plus register region | register region only |
| NPU reservation | 1 MiB at `0x84000000` | 10 MiB at `0x84000000` |

Both use a per-core bottom-half spinlock for ordinary sends, but timeout/lifetime/late-completion behavior still needs validation. A persistent coherent buffer avoiding a free-after-timeout problem does not by itself prove a late firmware response cannot interfere with its next use. There is no implemented or validated compatibility shim yet.

## Reproduction and next implementation

```sh
python -B research/vb235v/tools/npu_protocol_compare.py \
  /private/stock/npuMboxAPI.h /private/patched/airoha_npu.c \
  --output /private/protocol-fields.json
python -B -m unittest discover -s research/vb235v/tests -v
```

All 31 tests included through this milestone pass in WSL. Source/patch/result hashes, selector/mask facts and screened IRQ observations are in [findings/npu-ponwrt-contract.json](findings/npu-ponwrt-contract.json). Original objects, full disassembly, build command lines and raw interrupt captures remain private.

Next prepare the complete pinned target kernel stack, implement an opt-in active-core/IRQ adaptation in a development patch, cross-compile the resulting NPU/Ethernet objects and keep its DT node disabled. No register access, mailbox command, module loading, firmware upload or hardware restart was performed for this milestone.
