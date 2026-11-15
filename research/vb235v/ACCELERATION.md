# M4: Observed acceleration stack and source-reuse candidates

Scope is NAT/packet forwarding, NPU, and cryptographic engines. No video-decoding support is claimed.

## EIP93: observed registration, not a benchmark

The actual kernel's embedded configuration enables `CONFIG_CRYPTO_DEV_EIP93`, SKCIPHER, HMAC, AES, DES, and AEAD. A read-only `/proc/crypto` capture contains 23 driver registrations with `eip93` in their names, reporting `selftest: passed`. This establishes driver registration and the kernel-reported selftest state; it does not establish which traffic uses the engine or its throughput.

The vendor archive supplies `linux-5.4.55/drivers/crypto/airoha-eip93/` C and header files. `eip93-main.c:465` matches `airoha,airoha-eip93`; its probe uses platform MMIO and IRQ resources, and registration uses Linux crypto SKCIPHER/AEAD APIs. Source-porting and hardware integration should be evaluated before attempting to reverse engineer this already available implementation.

The PonWrt baseline tree also contains `target/linux/generic/hack-6.18/926-crypto-eip93-use-AES-fallback-for-small-requests.patch`. Its presence is a source-tree observation, not proof this board's device description or every crypto mode is supported. In particular, do not infer accelerated AES-GCM merely from the presence of AES and AEAD configuration symbols.

## NPU / hardware NAT / Wi-Fi

The actual loaded-module list includes `npu`, `npu_wifi`, `hw_nat`, `hwnat_blacklist`, `mt_wifi_osal`, `mtk_hwifi`, `en_npu`, `mt7993`, and `mt799b`. The saved I/O-memory map names the NPU at `0x1e800000` and additional associated ranges. These are observations of the original stack, not a PonWrt driver validation.

The selected vendor source sample `release_bsp/NPU/an7583_MT7993/` contains:

| Artifact | Bytes | SHA-256 |
| --- | --- | --- |
| `npu_data.bin` | 3220 | `81bd8ea4007842aed1c30c46f372ef38f532333cc210969a846a042feda2b4e2` |
| `npu_rv32.bin` | 121724 | `1a0566c0792c4c4f9d91d3a12a553fab5f31f12f6ad560c55eefe0279f031c6c` |

These sample binaries remain local. Their filenames and hashes do not prove they are the firmware currently executing on the router.

PonWrt's AN7583 target selects `airoha-an7583-npu-firmware` and contains AN7583 NPU support and mailbox/DMA patches. The current fork baseline is upstream commit `d9dd3a49f7bb7661c01e9c57c9e2aac2a1114b3e`. Inspect the actual package/feed source and firmware protocol before equating those components with the vendor Wi-Fi/NAT ABI.

References:

- [AN7583 target packages](https://github.com/pbs05/ponwrt/blob/master/target/linux/airoha/an7583/target.mk)
- [Bounded NPU mailbox wait](https://github.com/pbs05/ponwrt/blob/master/target/linux/airoha/patches-6.18/926-net-airoha-npu-bound-mailbox-wait.patch)

## Next validation

Match exact live module/firmware hashes, reconstruct their interfaces, identify which offload features require vendor hooks, and compare counters/traffic with offload enabled versus disabled in a controlled test environment. Configuration switches, algorithm names, and copied firmware alone are insufficient performance or correctness evidence.

The sanitized live crypto metadata is in `findings/acceleration-observations.json`; raw proc captures remain local. No crypto requests, module replacements, MMIO writes, flash writes or performance experiments were performed for this milestone.
