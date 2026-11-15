# M7: Complete loaded-module file coverage

The new read-only collection covers all **86 module names** present in the stock system's `/proc/modules`. It contains **87 verified files / 29,469,464 bytes**, including two byte-identical `ppp_mppe.ko` copies. Loaded names were unchanged at the end of collection. This establishes coverage of files corresponding to loaded names, rather than a dump or attestation of their relocated in-memory code.

The earlier 80 files were revalidated against the current device before reuse; seven missing files were transferred. Each accepted file has a device SHA-256 before and after transfer/reuse and a matching local size/hash readback. No candidate was skipped in this run.

| Newly collected object | Bytes |
| --- | ---: |
| `mt_wifi.ko` | 15,436,008 |
| `voip.ko` | 13,168 |
| `wireguard.ko` | 169,368 |
| `xt_DPI.ko` | 33,400 |
| `xt_TRIGGER.ko` | 9,208 |
| `xt_massurl.ko` | 14,416 |
| `xt_pctl_homeshield.ko` | 110,880 |

The exact size now confirms that `mt_wifi.ko` exceeds the previous collector's 8 MiB limit. Its file declares `Proprietary`, imports 280 symbol names and exports 47 according to the offline ELF reader. Its empty `depends` string does not mean it is independent: the completed module set resolves imports to providers including `cfg80211`, `ecnt_legacy_api`, and other vendor components.

All 87 objects passed the existing ELF64 reader with no parse errors. Deduplicating the identical PPP copies yields 86 objects and **80 unambiguous consumer/provider edges**, compared with 79 objects and 71 edges in M6. This is a static symbol relationship, not proof of driver compatibility or executed traffic paths. Derived metadata, hashes and selected edges are in [findings/stock-module-coverage.json](findings/stock-module-coverage.json).

## Reproduction

`tools/collect_stock_modules.py` uses host-side Paramiko and the already established stock root SSH shell. It pins the provided OpenSSH host key before sending the password and binds the explicitly selected Windows USB interface/source. Recheck those interface values on the current host.

```sh
python -B research/vb235v/tools/collect_stock_modules.py \
  --credentials /private/credentials.json --host-keys /private/device-public-keys.json \
  --source USB_SOURCE_ADDRESS --interface USB_INTERFACE_INDEX \
  --resume /private/previous-evidence --output /private/new-evidence
python -B research/vb235v/tools/elf_inventory.py \
  /private/new-evidence/modules --output /private/new-evidence/elf-inventory.json
python -B -m unittest discover -s research/vb235v/tests -v
```

Credentials JSON contains `username`, `password`, and `port`; the pinned-key JSON contains `host` with the OpenSSH key text. Keep both and all output outside this public tree. `/proc/kallsyms` and other proc snapshots may contain addresses or device-specific data and stay private as well.

The collector enforces a 32 MiB per-file, 96 MiB aggregate, and 128-file limit. It records exact sizes before applying those limits, rejects unsafe paths and nonregular/symlink files, respects the stock 235-byte command-line limit, and does not use unsupported BusyBox `find -type` or `dd`. Receive buffers and timeouts are bounded. Checkpoints accept only complete verified files; a new run can reuse such entries from `--resume`, but does not continue a partial file. A corrupt local resume copy is transferred again; a changing device digest aborts acceptance.

The regression suite includes corrupt/truncated transfers, path rejection, completed-file reuse with current device checks, device mutation during reuse, and exact oversize reporting. Together with the prior ELF tests, 11 tests pass. No module loading, ioctl, NPU command, firmware upload, restart or flash write was performed.

## Remaining coverage limits

Built-in kernel components, unloaded modules, firmware identity, ABI details and functional hardware tests remain separate work. The private kallsyms snapshot now supplies evidence for the core NPU provider; a dedicated provider/source analysis follows this collection milestone. Having every currently loaded module file does not make a PonWrt port buildable or ready to flash.
