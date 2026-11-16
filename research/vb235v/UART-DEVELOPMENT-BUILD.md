# M12: Cross-built UART-only development profile

A locally built **Linux 6.18.60 ARM64 Image, development DTB, and embedded minimal initramfs** now exist. The Image is 4,536,328 bytes. The independently authored profile describes the stock-observed UART, GIC, timer, RAM and retained reservations, with only CPU0 in the tree. It does not include the stock/PonWrt peripheral tree.

This is a development artifact using the exact kernel archive version/hash selected by the pinned PonWrt tree. It is **not a complete PonWrt build or installable VB235v image**: the Airoha target patch stack, normal OpenWrt userspace, Ethernet, Wi-Fi, DSL, telephone and acceleration drivers are not included. No hardware boot or installation has been performed.

## Implementation

- `bringup/vb235v-uart-only.dts` retains the observed 512 MiB RAM range, UART register layout/clock, GIC resources and architectural timer. It reserves 2 MiB for ATF conservatively and preserves the stock NPU/log reservations. It contains no NAND, SPI, network, PCIe, GPIO, SLIC/PCM, NPU, watchdog or other peripheral nodes.
- `bringup/uart-only.config` merges onto ARM64 `allnoconfig`. Storage, network, module loading, GPIO, input, pinctrl, watchdog and the other audited subsystems are disabled. ARM64 itself selects SMP and the power-reset framework; the DT has one CPU and the checker forbids every concrete `POWER_RESET_*` driver. Virtual-terminal support is disabled so it cannot re-enable the input subsystem.
- `bringup/uart-init.S` is a static AArch64 executable with only `write` and `nanosleep` syscalls. It prints a heartbeat every three seconds. There is no shell, network client, device-opening code, ioctl, reboot or storage operation.
- The generated initramfs contains exactly `dev`, `dev/console` (character device 5:1), and the verified executable `init`. The console device is an archive entry; creating the archive does not create a host device node.

The kernel release is `6.18.60-vb235v-uart-dev`. Fixed build user/host/timestamp inputs and disabled initramfs file-mtime preservation reduce incidental build differences; bit-identical reproducibility across toolchain versions has not been established.

## Validation

The final configuration and compiled DT pass `tools/audit_uart_bringup.py`. Its DT check accepts only the exact development node/property set and expected resource values; even an extra disabled NAND node is rejected. It rejects enabled MTD or concrete reset drivers and altered console clocks. These are static admission checks, not a proof that an arbitrary kernel has no hardware effects or that existing DMA is quiescent.

`tools/uart_artifact_inventory.py` additionally verifies the ARM64 Image header, a static AArch64 init without an interpreter/dynamic segment or executable stack, and the exact initramfs entries and embedded-init bytes. The final Image header declares 4,849,664 bytes of memory, flags 10, and text offset 0; future load-placement review must use these fields rather than assume an older fixed offset.

QEMU user-mode 7.2.22 executed the self-authored init for a bounded 4.53 seconds: two exact expected heartbeats, no stderr, then test-directed termination. This tests init's ARM64 execution/syscalls; **it does not boot this kernel, emulate VB235v peripherals, or validate the real UART**.

All 29 regression tests included through this milestone pass in WSL, including independent DTC compilation and negative tests for the DT/config/initramfs gates. The prior Windows-only assumption that a usable build host was unavailable is superseded: WSL2 Debian 11 supplies GCC/Make/Python, and extracted local Debian packages supply GCC 10.2.1's AArch64 cross compiler, binutils, DTC, Flex/Bison and related tools. No system package installation or router configuration change was needed.

Artifact/source hashes, kernel archive identity and the init smoke result are in [findings/uart-development-build.json](findings/uart-development-build.json). Build logs, full final config, vmlinux and the Image/DTB/initramfs remain local.

## Reproduction

Use the archive whose SHA-256 is recorded in `target/linux/generic/kernel-6.18` at PonWrt baseline `d9dd3a49f7bb7661c01e9c57c9e2aac2a1114b3e`: `linux-6.18.60.tar.xz`, SHA-256 `3c2f44ef6acc021a7ad444d9a2e6ec1ef488ff09368793d0004a6080f69d621e`. Extract a clean source tree and provide a working cross compiler and host build tools. Keep the kernel/build/tool-prefix paths free of spaces; the public source directory itself may contain spaces.

```sh
sh research/vb235v/bringup/build-uart-only.sh \
  /private/linux-6.18.60 /private/new-uart-build \
  /private/toolchain/bin/aarch64-linux-gnu-
cp /private/new-uart-build/usr/initramfs_data.cpio /private/new-uart-build/artifacts/
python3 -B research/vb235v/tools/uart_artifact_inventory.py \
  /private/new-uart-build/artifacts --config /private/new-uart-build/.config \
  --output /private/uart-artifact-inventory.json
python3 -B -m unittest discover -s research/vb235v/tests -v
```

The script performs local compilation only. It has no router connection, reboot, bootloader command or flashing action. Kernel compilation succeeding is not a reason to bypass the recovery/board-state checks in M1/M9. Before any real RAM experiment, verify the boot handoff/load placement, DDR/reservations, UART continuity, current DMA/peripheral state, and a suitable recovery method. Full functional firmware still requires the missing subsystems and their hardware tests.
