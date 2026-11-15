# M3: DSL control ABI and voice module boundaries

## DSL source interface

The selected GPL header is `linux-5.4.55/include/global_inc/modules/xdsl/xdsl_ioctl.h` (an equivalent copy also exists in the Airoha feed). It declares `/dev/xdsl`, ioctl magic `X`, and 14 selectors for firmware version, link state, mode, annex, TPSTC, channel/performance/line data, attainable rate, uptime, line state, showtime, PMS, and events.

Under the stated ordinary AArch64 C ABI assumptions (4-byte enums/u32, no packing), the largest union member is 288 bytes and `XDSLMGR_IOCTL` is 296 bytes. The source-derived `_IOWR('X', 0, ...)` request is `0xc1285800`.

These are **not live-handler-validated ioctl values**. The driver implementation, device registration, exact structure layout, and behavior of each selector must be matched before issuing requests. A name beginning with `GET_` is not by itself a guarantee that its handler has no side effects.

`tools/xdsl_capture_decode.py` decodes an already captured buffer; it never opens a device, calls ioctl, or controls the line. Layout and malformed-buffer checks are exercised locally. This milestone does not establish DSL synchronization or a replacement PHY/DSP implementation.

## Voice binaries: distinguish supplied BSP from the running build

Nineteen AArch64 voice `.ko` files were inspected from the vendor's `UNION_AN7583_KITE_LOGAN_KERNEL_5_4_demo/BSP/voip_bsp/voip_module/ko/` directory. They advertise `5.4.55 SMP mod_unload aarch64`; this alone does not prove compatibility or identity with the running modules.

The original system's `/proc/modules` names select 15 corresponding BSP module basenames. The static analysis resolves 30 consumer/provider edges within that subset. These are name-selected BSP findings, **not yet an exact live-binary hash match**.

Representative boundaries:

- `slic3_silicon` consumes SPI byte-access interfaces and `SLICMGR_HOOK_REGISTER` from `fxs3_silicon`.
- `fxs3_silicon` depends on DSPCore, PCM, SPI, echo-cancellation, and shared logging interfaces.
- `pcm1` consumes DSPCore interfaces; `spi` also consumes PCM/reset-selection interfaces.
- `ovdsp` consumes DSPCore, codec, FoIP, FXS, socket, echo-cancellation and ORTP interfaces.
- ORTP and SRTP participate in additional kernel-module interfaces; a replacement user-space SIP client does not cover this graph.

The sanitized symbol graph is `findings/voice-bsp-symbol-map.json`. Undefined symbols outside the inspected set may be supplied by built-in Linux code or other modules; they must not automatically be classified as missing drivers.

## Tooling improvement

The original ELF inventory relied on local `__ksymtab_<symbol>` labels. These BSP binaries remove many of those labels while retaining `__ksymtab`, export strings and relocations. The tool now resolves AArch64 PREL32/ABS64 export-name relocations, including bounds checks, instead of mistaking namespace strings for exports.

For example, the selected `ovdsp.ko` yields eight resolved exports. This correction enables the dependency graph to reflect actual export tables rather than merely all defined function names.

Reproduce locally:

```sh
python research/vb235v/tools/elf_inventory.py /private/voice-ko --output /private/voice-elf.json
python research/vb235v/tools/module_dependencies.py /private/voice-elf.json \
  --select DSPCore,acodec_ext,acodec_x,foip,fxs3_silicon,ksocket,lec,lec_wb,ortp,ovdsp,pcm1,slic3_silicon,spi,srtp,sys_mod \
  --output /private/voice-graph.json
```

No supplied module was loaded or executed, and no DSL/SLIC register or flash data was written for this analysis.
