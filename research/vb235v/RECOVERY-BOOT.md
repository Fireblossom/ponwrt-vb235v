# M1: Original boot chain and recovery prerequisites

## Original artifact analysis

The owner's original 768 KiB `bootloader` partition backup contains a structurally valid Arm TF-A FIP table at partition offset `0x800`. A second magic-byte occurrence at `0x330` does not pass the bounded parser. Recognition checks table termination, payload bounds and overlaps; it does not verify signatures.

Nine entries are present. Standard TF-A UUIDs identify these three payloads:

| Role | Partition offset | Encoded bytes | Result |
| --- | --- | --- | --- |
| BL2 | `0xc00` | 120131 | Payload identified by standard UUID; internal packing unresolved |
| BL31 | `0x21800` | 56846 | LZMA decoded to 136793 bytes |
| BL33 | `0x2f800` | 310799 | LZMA decoded to 903008 bytes |

Decoded BL33 contains `U-Boot 2023.04 (Aug 25 2026 - 09:33:23 +0000)`, matching the observed original serial boot. Decoded SHA-256:

- BL31: `b14982e68559230f2bf4bf65a5ffa6ec36e8c17eb99d2519f5d38fe666d5b15f`
- BL33: `e7e36e39ad9f97b379b8a1a8efc0fd7547add8da75b9a125ac1a28479ffbec8b`

Raw backups, certificates and extracted images remain local. The default recovery experiment has not been changed, and no new image was booted or flashed for this milestone.

Reproduce locally:

```sh
python research/vb235v/tools/boot_container_inventory.py /private/bootloader.bin --output /private/boot-chain.json
```

## Candidate recovery implementation

The AN758x U-Boot project supplies a Web recovery interface, but its current AN7583 board target is Nokia XG-040G-MF rather than VB235v. Its build script constructs separate BL2 and BL31/BL33 FIPs. Its signing script optionally signs them using an externally supplied RSA-4096 key. Optional signing in that project does not establish which images this physical board's Boot ROM will accept.

Source references:

- [TF-A FIP layout and UUIDs](https://github.com/ARM-software/arm-trusted-firmware/blob/master/include/tools_share/firmware_image_package.h)
- [AN758x build pipeline](https://github.com/pbs05/uboot-an758x/blob/main/scripts/build-an758x.sh)
- [FIP signing pipeline](https://github.com/pbs05/uboot-an758x/blob/main/scripts/sign-an758x-fip.sh)
- [Nokia AN7583 U-Boot configuration](https://github.com/pbs05/uboot-an758x/blob/main/configs/an7583_nokia_xg-040g-mf_defconfig)

## Remaining gates

1. Identify the exact NAND part, ECC/OOB behavior, Boot ROM boot policy and board-specific authentication requirements through supported read-only evidence.
2. Match RAM training, clocks, reset button, UART, Ethernet ports, PHY and pinmux to VB235v.
3. Define recovery entry independent of a valid Linux rootfs or writable Linux configuration.
4. Prove image validation rejects incorrect board/layout images before erasure.
5. Validate interruption behavior for each writable region and provide a tested external recovery option for early-stage failures.

Neither a Web page nor a UART prompt proves power-loss-safe bootloader replacement. No absolute "unbrickable" claim is made.
