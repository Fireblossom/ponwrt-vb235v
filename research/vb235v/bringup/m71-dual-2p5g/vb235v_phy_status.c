// SPDX-License-Identifier: GPL-2.0-only
/* Read PHY data through the driver's page-4 address window; never write data. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_mdio.h>
#include <linux/phy.h>
static int read_pbus(struct phy_device *phy,u32 address,u32 *value)
{
	int page=phy_select_page(phy,4),ret=0,high=0,low=0,mode=-1;
	if(page<0)return phy_restore_page(phy,page,0);
	mode=__phy_read(phy,0x10);
	if(mode<0){ret=mode;goto done;}
	ret=__phy_write(phy,0x10,0);if(ret<0)goto done;
	ret=__phy_write(phy,0x15,address>>16);if(ret<0)goto done;
	ret=__phy_write(phy,0x16,address&0xffff);if(ret<0)goto done;
	high=__phy_read(phy,0x17);if(high<0){ret=high;goto done;}
	low=__phy_read(phy,0x18);if(low<0){ret=low;goto done;}
	*value=(u32)high<<16|low;
done:
	if(mode>=0){int restore=__phy_write(phy,0x10,mode);if(!ret&&restore<0)ret=restore;}
	return phy_restore_page(phy,page,ret);
}
static int __init vb235v_phy_status_init(void)
{
	struct device_node *np;struct mii_bus *bus;int result=0;
	if(!of_machine_is_compatible("tplink,vb235v-ram-multigig-development"))return -ENODEV;
	np=of_find_node_by_path("/system-controller@1fb00000/mdio-bus@c8");if(!np)return -ENODEV;
	bus=of_mdio_find_bus(np);of_node_put(np);if(!bus)return -EPROBE_DEFER;
	for(unsigned addr=14;addr<=15;addr++){
		struct phy_device *phy=mdiobus_get_phy(bus,addr);u32 polarity=0,version=0,clock=0;int ret;
		if(!phy||phy->phy_id!=0x03a2a411){result=-ENODEV;break;}
		mutex_lock(&phy->lock);
		ret=read_pbus(phy,0xca0f8,&polarity);
		if(!ret)ret=read_pbus(phy,0x3b3c,&version);
		if(!ret)ret=read_pbus(phy,0xcf958,&clock);
		pr_info("M71_PHY_STATUS addr=%u ret=%d polarity=%08x firmware=%08x clock=%08x ready=%04x cmd3=%04x bmsr=%04x lp=%04x ctrl1000=%04x stat1000=%04x aux=%04x cached_speed=%d\n",
			addr,ret,polarity,version,clock,phy_read_mmd(phy,MDIO_MMD_VEND1,0x8009),
			phy_read_mmd(phy,MDIO_MMD_VEND1,0x800e),phy_read(phy,MII_BMSR),phy_read(phy,MII_LPA),
			phy_read(phy,MII_CTRL1000),phy_read(phy,MII_STAT1000),phy_read(phy,0x1d),phy->speed);
		mutex_unlock(&phy->lock);if(ret)result=ret;
	}
	put_device(&bus->dev);return result;
}
static void __exit vb235v_phy_status_exit(void) {}
module_init(vb235v_phy_status_init);module_exit(vb235v_phy_status_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("VB235v bounded EN8811H status without PHY data writes");
