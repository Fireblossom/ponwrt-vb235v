# M5: Exact live-module inventory and comparison with the supplied BSP

## Evidence checked

The owner-side read-only collector retrieved 80 regular module files, totaling 13,683,016 bytes. Device SHA-256 before/after each read and local decoded SHA-256 matched. All lengths and hashes were rechecked locally before this analysis. No module was loaded or replaced.

The 80 paths represent 79 distinct basenames. Two `ppp_mppe.ko` paths have identical SHA-256; this is a duplicate artifact, not two driver implementations. The proc capture lists 86 loaded module names. The capture is therefore not a complete binary inventory of every loaded module.

Known omissions are the `mt_wifi.ko` size/parsing gate and six paths beyond the file-count limit (`voip`, `wireguard`, and four `xt_*` modules). The MAC driver is important and must be acquired before claiming full Wi-Fi coverage.

## Voice build comparison

Fifteen voice module names match the supplied AN7583 demo BSP subset. All fifteen live file hashes differ from the BSP file hashes. Their imported/exported symbol-name sets match, but those names do not establish compatible function arguments, structure layouts, constants or behavior.

The comparison checks every executable section, including `.text.*`, rather than only `.text` (which is empty in some function-section builds). Five modules have byte-identical unrelocated executable sections and matching canonical relocation descriptions: `acodec_ext`, `acodec_x`, `ksocket`, `srtp`, and `sys_mod`. Ten have executable-section differences.

Seven have identical canonical relocation descriptions after numeric symbol-table indexes are resolved to symbols/sections. In particular, equal relocations alone do not imply equal executable bytes. Conversely, different raw `.rela.*` bytes can arise solely from symbol-table renumbering; the tool has a regression test for that case.

The exact summarized comparison is `findings/live-vs-bsp-comparison.json`. Raw files remain private. No conclusion of runtime ABI compatibility or safe binary loading is made.

## Reproduction

```sh
python research/vb235v/tools/module_compare.py /private/live/module.ko /private/bsp/module.ko --output /private/comparison.json
python -m unittest discover -s research/vb235v/tests -v
```

The six synthetic ELF tests exercise branch ownership, symbol-table renumbering, additional executable sections, malformed opcodes, truncated files, and out-of-range function symbols. They do not exercise hardware or certify a driver port.
