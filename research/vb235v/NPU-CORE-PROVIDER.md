# M8: Core NPU provider and source contract

The provider ambiguity in M6 is resolved for four core functions. The stock device's saved `/proc/kallsyms` identifies `host_notify_npuMbox`, `get_ecnt_npu_dev`, `boot_npu_all_cores`, and `set_npu_needed_info` as global text symbols without a module tag, identifying **the built-in kernel** as their runtime provider. None is exported by the now-complete set of loaded-module files.

Independent build evidence in the owner's GPL archive agrees: `arch/arm64/mach-econet/Makefile` includes `ecnt_npu.o` in `obj-y`, `ecnt_npu.c` defines and exports these functions, and `Module.symvers` lists each against `vmlinux` with `EXPORT_SYMBOL`. This does not establish that the archived implementation is byte-for-byte identical to the running kernel.

The corresponding archived ELF function sizes and live distances to the next text symbol are:

| Function | Archived function bytes | Live next-symbol distance |
| --- | ---: | ---: |
| `get_ecnt_npu_dev` | 20 | 20 |
| `boot_npu_all_cores` | 200 | 208 |
| `set_npu_needed_info` | 144 | 144 |
| `host_notify_npuMbox` | 1,152 | 1,152 |

Distances may include alignment or other intervening data and are not a code-equivalence test. No live kernel memory was read. Addresses are omitted from the public findings.

## Symbol coverage

The offline join observes built-in definitions for 32 of `npu.ko`'s 39 imported names and 16 of `npu_wifi.ko`'s 21. Five names in each are absent from this kallsyms snapshot; these include data such as `npu_stat` and `mdc_lock_address`. Absence is not proof of a missing implementation. The archived configuration enables `CONFIG_KALLSYMS` while leaving `CONFIG_KALLSYMS_ALL` and `CONFIG_MODVERSIONS` unset; this is relevant context for data-symbol omissions, not a verification of the live configuration.

The tool keeps three evidence classes distinct: live definitions, exports parsed from module files, and exports in an optional archived build's `Module.symvers`. A symbol address, an export declaration, or an equal vermagic string alone does not establish compatibility with another kernel.

## Contract recovered from the archived implementation

The source-defined descriptor remains 40 bytes under the ordinary AArch64 ABI described in M6. The archived object was built for LP64, but its DWARF retains only a declaration of `npuMboxInfo`, so it does not provide a full compiled member-layout confirmation.

Review of `ecnt_npu.c:821` and the related header establishes constraints for a future implementation:

- Ordinary requests hold a per-core `spin_lock_bh`; the DBA selector bypasses that entry lock and requires its callers' locking behavior to be examined separately.
- The handler registers a callback and saves virtual address, physical address and length for the core/function. A later request can reuse that saved buffer. Nonblocking payload lifetime cannot be treated as ending when the API returns.
- The source writes physical address, length and argument/control state into mailbox registers, then polls completion. The default counter is 300 with a 100-microsecond delay per unsuccessful iteration. A blocking descriptor can replace the counter. This supports the header's 100-microsecond timeout units; a nearby prose comment saying microseconds is inconsistent with the implementation. Roughly 30 ms of programmed polling delay is not a wall-clock guarantee.
- Return status is a three-bit field; the documented zero error and nonzero firmware statuses need to be handled separately from Linux errno conventions.
- The descriptor stores physical addresses in 32 bits and lengths in 16 bits despite 64-bit virtual pointers. Probe requires reserved memory through `memory-region`, MMIO resources, the mailbox IRQ, and conditional per-core watchdog IRQs. The NPU-v2 branch requests a coherent DMA mask of `0xbfffffff`. A new kernel integration must establish actual address ranges and coherency rather than copy this value blindly.
- The missing-default-buffer error path contains `spin_unlock_irqrestore` despite the ordinary `spin_lock_bh` entry. This is a source-review issue requiring compiled/live-path verification; no request was sent to exercise it.

These observations identify a built-in vendor subsystem with memory, interrupt, callback and DMA dependencies. Moving only `npu.ko` and `npu_wifi.ko` cannot supply that subsystem on a different kernel.

## Reproduction and next checks

```sh
python -B research/vb235v/tools/kernel_symbol_providers.py \
  /private/evidence/elf-inventory.json /private/evidence/kallsyms.txt \
  --symvers /private/archive-kernel/Module.symvers \
  --consumers npu,npu_wifi,mt_wifi,voip --output /private/kernel-providers.json
python -B -m unittest discover -s research/vb235v/tests -v
```

The tool uses the standard library, accepts bounded saved inputs, omits live addresses, handles identical module duplicates, rejects conflicting variants, and keeps unresolved symbols explicit. The full suite now passes 14 tests. Selected results and archived source/object hashes are in [findings/npu-core-provider.json](findings/npu-core-provider.json). Vendor implementation bodies, raw proc output and compiler command lines remain private.

Next establish the exact firmware identity and module load sequence, compare the required built-in interfaces with PonWrt's AN7583 implementation, and validate locking/completion, address translation, IRQ and descriptor rules before any integration experiment. No firmware upload, NPU command, module loading, reboot or flash write was performed for this milestone.
