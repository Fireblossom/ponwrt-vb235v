# M25: corrected recovery core updated in NAND and function-tested

The owner explicitly requested updating the recovery core and testing its functions. The memory-corrected [M24](UBOOT-FIT-INSTALL-VALIDATION.md) recovery FIT now replaces the older core in the pre-reserved third logical boot block, `0x80000`–`0xc0000`. The first two blocks, original boot code, complete environment and boot command are preserved. This is a NAND-resident recovery core update; automatic recovery entry is not enabled.

The installed FIT is the already reproduced and hardware-tested M24 standard build, not a new diagnostic build. Its SHA-256 is `cd550837fc4f35f3b384390a7e61a49c2791b441e77f40e42c9061de6c5935fe`. It retains the corrected secure-memory reservation and has the destructive diagnostic command and persistent environment backends disabled.

## Bounded update

A fresh pinned root SSH session verified the pre-update boot, ART, misc, both complete firmware-slot and selector hashes and downloaded the complete boot partition. The new core FIT was padded to one 256 KiB block, and the exact expected post-update boot bytes were prepared. The old block and entire original boot backup were retained privately.

At the original U-Boot prompt, readback CRCs checked the current complete boot partition, then the first two blocks and old target block immediately before programming. The new block was transferred into RAM and checked by CRC and both FIT SHA-256 values. The original MTD driver performed one erase and one program command, both confined to the third block. No `saveenv`, boot-command change, firmware installation or calibration write was sent.

After programming, the complete target block was read into a separate RAM address. Its CRC and both FIT payload hashes matched. The first two blocks still matched their original CRC, and the complete boot partition matched its exact predicted CRC. The recovery was then started from this **NAND readback**, rather than from the original upload buffer.

The new core reached its recovery prompt, showed the corrected secure range ending at `0x8004ffff`, verified factory mapping/board anchors and selected factory slot 0. Its own full boot backup SHA-256 matched the predicted update, and its ART backup matched the original baseline.

## Function checks

The NAND-loaded core passed:

- HTTP root-page and status checks over the owner's ordinary 1 GbE LAN.
- Complete HTTP downloads of bootloader, ART, misc and selector, with the expected sizes and SHA-256 values.
- A 3,766,005-byte RAM upload of the private original-kernel FIT, with matching device and host hashes. No firmware-slot install request was made in M25.
- Booting that original kernel directly from RAM, demonstrating the corrected low-memory loading path from the now NAND-resident core.
- Independent pinned root SSH verification of the trial DT identity, byte-exact original command line and the entire downloaded boot partition. The first `0x80000` bytes and complete environment were byte-exact to the pre-update backup; the third block was byte-exact to the new padded core. ART, misc, both complete firmware slots and selector hashes remained unchanged.

One early read-only SSH verification attempt met a connection reset while the original Linux service was starting. A later pinned handshake and complete checks succeeded; the NAND operation was not repeated.

An additional ordinary software reset was then allowed to autoboot without serial interception. Original BL2, original U-Boot and original Linux started normally, and the experimental recovery prompt did not appear. A separate pinned root session verified the factory DT identity, original boot arguments, complete boot readback and unchanged protected/firmware hashes after that reset. See [uboot-core-update-validation.json](findings/uboot-core-update-validation.json).

## Current behavior and remaining limits

The corrected core is now stored in NAND and can be entered manually through the original U-Boot's read/boot path. Normal power-on continues to use the original boot command and original system. This milestone does not install the shared code/environment-block hook or replace BL2/BL31/original BL33.

Default recovery HTTP addressing remains `192.168.1.1/24`; physical DHCP lease acquisition is unresolved. The tested Windows host used volatile `httpd_ipaddr=169.254.1.1` and `httpd_netmask=255.255.0.0` settings on the recovery console, with no Windows static-address configuration. A recovery button, automatic entry, actual power-cut behavior and independently demonstrated programmer recovery remain unverified.

No firmware or calibration data is redistributed. Private backups retain the complete boot partition before and after this update, the old rollback block, the new padded block and the verified current calibration downloads. The public tree records the bounded operation and derived results; the installed executable bytes are the unchanged M24 candidate.
