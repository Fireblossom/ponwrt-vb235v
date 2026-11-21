// SPDX-License-Identifier: GPL-2.0-only
/* Read-only page-address diagnostic; restore every selected PHY page. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_mdio.h>
#include <linux/phy.h>
static int __init probe_init(void)
{
 struct device_node *np;struct mii_bus *bus;unsigned addr;
 if(!of_machine_is_compatible("tplink,vb235v"))return -ENODEV;
 np=of_find_node_by_path("/system-controller@1fb00000/mdio-bus@c8");if(!np)return -ENODEV;
 bus=of_mdio_find_bus(np);of_node_put(np);if(!bus)return -ENODEV;
 for(addr=14;addr<=15;addr++) {
  struct phy_device *phy=mdiobus_get_phy(bus,addr);int page,raw,standard,after;
  if(!phy||phy->phy_id!=0x03a2a411){put_device(&bus->dev);return -ENODEV;}
  mutex_lock(&phy->lock);
  page=phy_read(phy,0x1f);raw=phy_read(phy,0x1d);
  standard=phy_read_paged(phy,0,0x1d);after=phy_read(phy,0x1f);
  pr_info("M75_PAGE addr=%u before=%04x raw=%04x standard=%04x after=%04x bmsr=%04x cached_speed=%d\n",
   addr,page,raw,standard,after,phy_read(phy,MII_BMSR),phy->speed);
  mutex_unlock(&phy->lock);
 }
 put_device(&bus->dev);return 0;
}
static void __exit probe_exit(void){}
module_init(probe_init);module_exit(probe_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("VB235v EN8811H page-preserving status diagnostic");
