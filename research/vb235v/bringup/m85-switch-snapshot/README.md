# M85 one-shot read-only switch snapshot

This diagnostic is separate from the frozen M81 CPU driver and mini-r3 image.
It reads SYS_CTRL at `0x1fb5f000` and GEPHY_CONN_CFG at `0x1fb5fc14` once each.
It has no module parameters, hardware writes, SMC calls, MDIO/IAC transactions,
driver registration, reset, or clock/voltage changes. It requires the exact
VB235v/AN7583 board and an available AN7583 switch node whose first resource
starts at `0x1fb58000` and covers both registers.

The exact prepared Linux 6.18.60 sources define SYS_CTRL `0x7000`, PHY_RST bit2;
GEPHY_CONN_CFG `0x7c14`, DPHY_CKIN_SEL bit31, PHY_CORE_REG_CLK_SEL bit30 and
ETHER_AFE_PWD bits28:24. Native `mt7988_setup()` resets the switch, sets the
GEPHY clock selections and clears AFE powerdown, then writes PHY_RST before
common setup. A later snapshot alone cannot establish which earlier operation
caused a value or prove that analog calibration remains valid.

Compile only into an independent WSL directory, without running make:

```sh
python3 compile-isolated.py \
  --tree /home/duanx/vb235v-build-20261116/ponwrt-system-m55 \
  --template /home/duanx/m78-cpu-dvfs-check \
  --work /home/duanx/m85-switch-snapshot
```

The compiler checks 6.18.60, no symbol versioning, bounded undefined imports,
and unchanged shared configuration/generated headers/Module.symvers. The
current prepared configuration is the later M83 build, so the report preserves
its identity rather than pretending it is the M75 configuration. The resulting
module and the previously loaded M81 module both have a 0x2c0-byte module
structure and the same release/SMP/module-unload architecture ABI. Actual load
admission is still determined by the kernel.

Under the parent agent's hardware lease only: upload into RAM, verify SHA256,
capture dmesg before/after insmod, then rmmod. Do not arm CPU transitions or
perform writes in response to the snapshot. The compile output includes the
actual AArch64 disassembly: two calls to readl (LDR plus read barrier), no store
through either mapped address, and no MDIO/reset/SMC imports. A missing module
description warning is the existing OpenWrt metadata filtering; the source
contains MODULE_DESCRIPTION.

The optional transfer copy was produced with the same cross toolchain's
`strip --strip-debug -o vb235v-switch-snapshot-stripped.ko vb235v-switch-snapshot.ko`.
It is 6296 bytes, SHA256
`2186121915eb7cad14ff7b04a45306107cc0ca997a7325b5f51a5524b3cbead9`.
Undefined imports and modinfo content are identical to the original; actual
stripped disassembly retains both readl calls and module loader sections.
The original artifact and compile report remain intact.

Related reset audit: exact AN7583 reset-controller map assigns SCU RST_CTRL1
bits1=FE_PDMA, bit2=FE_QDMA and bit21=FE; GSW is bit23. The known U-Boot quiesce
mask 21/1/2 does not explicitly assert GSW or a named PHY reset. Collateral
effects of global FE reset on PHY analog state are unproven.

CPU acceptance remains blocked at the independent wired fixture: actual
vb235v-smc/performance/1200 MHz policy has passed with SET count zero, while
internal PHY11 has no carrier. No controlled 500/1200 transition is claimed.
