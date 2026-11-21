// SPDX-License-Identifier: GPL-2.0-only
/* Read-only PHY discovery; no PHY is reset, configured or attached. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_mdio.h>
#include <linux/phy.h>
static int __init vb235v_mdio_probe_init(void)
{
	struct device_node *np;struct mii_bus *bus;
	if(!of_machine_is_compatible("tplink,vb235v-ram-accel-development"))return -ENODEV;
	np=of_find_node_by_path("/system-controller@1fb00000/mdio-bus@c8");
	if(!np)return -ENODEV;
	bus=of_mdio_find_bus(np);of_node_put(np);if(!bus)return -EPROBE_DEFER;
	for(unsigned int addr=0;addr<32;addr++){
		int id1=mdiobus_read(bus,addr,MII_PHYSID1),id2=mdiobus_read(bus,addr,MII_PHYSID2);
		if(id1<0||id2<0){pr_info("M70_MDIO addr=%u read_error=%d,%d\n",addr,id1,id2);continue;}
		if((id1==0xffff&&id2==0xffff)||(id1==0&&id2==0))continue;
		pr_info("M70_MDIO addr=%u id=%04x%04x bmcr=%04x bmsr=%04x adv=%04x lp=%04x aux=%04x\n",addr,id1,id2,
			mdiobus_read(bus,addr,MII_BMCR),mdiobus_read(bus,addr,MII_BMSR),
			mdiobus_read(bus,addr,MII_ADVERTISE),mdiobus_read(bus,addr,MII_LPA),mdiobus_read(bus,addr,0x1d));
	}
	put_device(&bus->dev);return 0;
}
static void __exit vb235v_mdio_probe_exit(void) {}
module_init(vb235v_mdio_probe_init);module_exit(vb235v_mdio_probe_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("VB235v RAM-only read-only external MDIO discovery");
