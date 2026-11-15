# Initial source audit

Examined on 2026-11-15 using the owner's TP-LinkBox 7 / VB235v GPL archive and local stock boot evidence. Archive path prefixes below are vendor archive paths, not user filesystem paths.

## Wi-Fi: source exists; completeness still needs checking

Under `VB235v_GPL/bba_3_0_platform/sdk/an7551/openwrt-21.02/openwrt-21.02.1_dev/feeds/wifi_package/mtk/drivers/mt_wifi7/`:

- `src/wlan_hwifi/chips/mt7993/mt7993.c`
- `src/wlan_hwifi/chips/mt7993/mt799b.c`
- `src/wlan_hwifi/chips/mt7993/` register headers
- `src/wlan_hwifi/main.c`, `bus.c`, and package `Makefile`

Seven selected Wi-Fi/voice build files were extracted and hashed for local review. The Wi-Fi recipe names `mt7993-Griffin8312.tar.xz` and dependencies including `kmod-mt_wifi_osal` and optional connectivity/HNAT components. `mt7993.c` includes chip, MAC-interface, core, and connectivity headers. Source presence does not prove this framework builds against PonWrt's kernel.

The reviewed chip file contains a redistribution notice, and its SPDX line is a placeholder rather than a valid expression. `wlan_hwifi/main.c` and `mt799b.c` declare `MODULE_LICENSE("Dual BSD/GPL")`. Keep original notices and audit dependencies rather than assigning one license to the whole vendor tree.

## Voice: external BSP dependency identified

The recipe at `feeds/airoha/package/airoha/drivers/voip_driver/Makefile` references `VOIP_BSP_DIR`, `VOIP_BSP_CRITICAL_DIR`, `UNOPEN_BACKUP_DIR`, and `make_voip_bsp`. Its prepare/compile rules depend on that separate BSP; the package recipe alone is not the driver implementation.

The initial archive index finds voice package recipes and prebuilt `sipclient` artifacts, but this is not an exhaustive proof that all voice source is absent. Search BSP naming and dependency paths next, then inventory stock kernel modules.

## DSL: exact implementation unresolved

The stock boot log contains `tcadslcmd_init` and DSL SerDes initialization. An archive filename match for Lantiq DSL packages is not evidence of support for this Airoha board. Do not conflate bundled generic OpenWrt packages with the selected vendor BSP.

## Upstream references

- [PonWrt](https://github.com/pbs05/ponwrt)
- [AN7583 image profiles](https://github.com/pbs05/ponwrt/blob/master/target/linux/airoha/image/an7583.mk)
- [PonWrt target kernel](https://github.com/pbs05/ponwrt/blob/master/target/linux/airoha/Makefile)
- [Vendor GPL download page](https://www.tp-link.com/de/support/download/tp-linkbox-7/)
- [Linux kernel driver ABI explanation](https://docs.kernel.org/process/stable-api-nonsense.html)

No vendor firmware, calibration dump, private module binary, or raw serial log is included in this initial contribution.
