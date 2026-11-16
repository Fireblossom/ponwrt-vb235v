# M10: Stock NPU firmware differs from the GPL reference

The SHA-256-verified stock `npu.ko` contains the fixed paths `/userfs/npu_rv32.bin` and `/userfs/npu_data.bin`. A pinned-SSH read-only collection obtained both regular nonsymlink files with matching device hashes before and after transfer, matching lengths, and local hash readback.

Both files differ from the corresponding `release_bsp/NPU/an7583_MT7993` files in the owner's GPL archive:

| File | Stock on-disk bytes | GPL reference bytes | Byte-exact match |
| --- | ---: | ---: | --- |
| `npu_rv32.bin` | 121,132 | 121,724 | No |
| `npu_data.bin` | 3,220 | 3,220 | No |

The data file illustrates why matching filenames and lengths do not establish firmware identity. Full file hashes and bounded positional comparisons are in [findings/npu-firmware-identity.json](findings/npu-firmware-identity.json).

This closes the file-identity gap left in M4: the archived reference blobs cannot be assumed identical to the stock files named by the loader module. It does **not** determine their relative age, firmware command compatibility, bug fixes or feature set. The files on disk have not been compared with executing NPU instruction/data memory, so this is not an attestation of the currently running firmware image.

## Reproduction

Acquire only the two named files over the already pinned stock SSH connection. Check each is a regular nonsymlink file, record `wc -c`, compute `/usr/sbin/openssl dgst -sha256` before and after a bounded base64 transfer, and verify the local size/hash. The observed files fit a fixed 1 MiB per-file limit. No firmware loading or NPU command is needed.

Compare saved copies offline:

```sh
python -B research/vb235v/tools/npu_firmware_identity.py \
  /private/stock-npu-firmware /private/reference-an7583_MT7993 \
  --module /private/stock-modules/npu.ko --output /private/npu-firmware-identity.json
python -B -m unittest discover -s research/vb235v/tests -v
```

The standard-library tool verifies that the supplied module contains exactly the two expected path strings, bounds file reads, and emits hashes and derived metadata without firmware contents. Positional differences compare equal offsets over the shorter length; they are not an aligned code-difference or semantic comparison. All 19 regression tests pass.

Before integration, identify the intended PonWrt firmware format and host ABI, trace stock loading and initialization, and decide whether a compatible independently distributable firmware/API combination exists. Do not substitute the archive blobs merely because the chip family matches. No module load, firmware upload, reboot, NPU command or flash write was performed.
