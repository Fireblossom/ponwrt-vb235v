// SPDX-License-Identifier: GPL-2.0-only
/* Two one-shot register reads. No driver binding, MDIO/IAC, reset or writes. */
#define pr_fmt(fmt) KBUILD_MODNAME ": " fmt
#include <linux/errno.h>
#include <linux/io.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_address.h>

#define EXPECTED_BASE 0x1fb58000ULL
#define SYS_CTRL_OFF 0x7000
#define GEPHY_CONN_CFG_OFF 0x7c14

static int __init vb235v_switch_snapshot_init(void)
{
	struct device_node *np;
	struct resource resource;
	void __iomem *sys_ctrl, *gephy;
	u32 sys_value, gephy_value;
	int ret;

	if (!of_machine_is_compatible("tplink,vb235v") ||
	    !of_machine_is_compatible("airoha,an7583"))
		return -ENODEV;
	np = of_find_compatible_node(NULL, NULL, "airoha,an7583-switch");
	if (!np)
		return -ENODEV;
	if (!of_device_is_available(np)) {
		of_node_put(np);
		return -ENODEV;
	}
	ret = of_address_to_resource(np, 0, &resource);
	of_node_put(np);
	if (ret)
		return ret;
	if (resource.start != EXPECTED_BASE ||
	    resource_size(&resource) < GEPHY_CONN_CFG_OFF + sizeof(u32))
		return -ENODEV;
	/* Both are ordinary configuration registers: native source RMWs GEPHY
	 * and writes SYS_CTRL. Neither is an interrupt status/read-clear port.
	 * Do not claim the live driver's resource or map any IAC data register.
	 */
	sys_ctrl = ioremap(EXPECTED_BASE + SYS_CTRL_OFF, sizeof(u32));
	if (!sys_ctrl)
		return -ENOMEM;
	gephy = ioremap(EXPECTED_BASE + GEPHY_CONN_CFG_OFF, sizeof(u32));
	if (!gephy) {
		iounmap(sys_ctrl);
		return -ENOMEM;
	}
	sys_value = readl(sys_ctrl);
	gephy_value = readl(gephy);
	iounmap(gephy);
	iounmap(sys_ctrl);
	pr_info("READ ONLY: SYS_CTRL[0x1fb5f000]=0x%08x GEPHY_CONN_CFG[0x1fb5fc14]=0x%08x; two reads, no MMIO/MDIO/IAC writes\n",
		sys_value, gephy_value);
	pr_info("GEPHY fields: DPHY_CKIN_SEL=%u PHY_CORE_REG_CLK_SEL=%u ETHER_AFE_PWD=0x%x; PHY_RST=%u\n",
		!!(gephy_value & BIT(31)), !!(gephy_value & BIT(30)),
		(gephy_value >> 24) & 0x1f, !!(sys_value & BIT(2)));
	return 0;
}
module_init(vb235v_switch_snapshot_init);

static void __exit vb235v_switch_snapshot_exit(void)
{
	pr_info("read-only snapshot removed; no hardware state changed\n");
}
module_exit(vb235v_switch_snapshot_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("VB235v one-shot switch GEPHY/SYS_CTRL read-only snapshot");
