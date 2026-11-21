// SPDX-License-Identifier: GPL-2.0-only
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_mdio.h>
#include <linux/phy.h>
#include <linux/io.h>
#include <linux/delay.h>
static void sample(struct mii_bus *bus,unsigned gpio,const char *phase)
{
 unsigned addr;
 for(addr=14;addr<=15;addr++)
  pr_info("M72_HARD_RESET gpio=%u phase=%s addr=%u id=%04x%04x bmcr=%04x\n",gpio,phase,addr,
   mdiobus_read(bus,addr,MII_PHYSID1),mdiobus_read(bus,addr,MII_PHYSID2),mdiobus_read(bus,addr,MII_BMCR));
}
static int __init probe_init(void)
{
 struct device_node *np;struct mii_bus *bus;void __iomem *base;u32 old;unsigned addr,gpio;
 if(!of_machine_is_compatible("tplink,vb235v-ram-multigig-development"))return -ENODEV;
 np=of_find_node_by_path("/system-controller@1fb00000/mdio-bus@c8");if(!np)return -ENODEV;
 bus=of_mdio_find_bus(np);of_node_put(np);if(!bus)return -ENODEV;
 for(addr=14;addr<=15;addr++) {
  struct phy_device *phy=mdiobus_get_phy(bus,addr);
  if(!phy||phy->phy_id!=0x03a2a411||phy->drv){put_device(&bus->dev);return -EBUSY;}
 }
 base=ioremap(0x1fbf0200,0x80);if(!base){put_device(&bus->dev);return -ENOMEM;}
 old=readl(base+0x70);
 if((old&0xc)!=0xc||(readl(base+0x78)&0xc)!=0xc||(readl(base+0x60)&0xf0)!=0x50){
  iounmap(base);put_device(&bus->dev);return -EINVAL;
 }
 /* Exactly the GPIO35 then GPIO34 low/high sequence in OEM rcS. */
 for(gpio=35;gpio>=34;gpio--) {
  u32 mask=BIT(gpio-32);
  sample(bus,gpio,"before");
  writel(readl(base+0x70)&~mask,base+0x70);readl(base+0x70);
  msleep(1000);sample(bus,gpio,"asserted");
  writel((readl(base+0x70)&~mask)|(old&mask),base+0x70);readl(base+0x70);
  msleep(1000);sample(bus,gpio,"released");
 }
 pr_info("M72_HARD_RESET restored_mask=%x current_mask=%x\n",old&0xc,readl(base+0x70)&0xc);
 iounmap(base);put_device(&bus->dev);return 0;
}
static void __exit probe_exit(void){}
module_init(probe_init);module_exit(probe_exit);
MODULE_LICENSE("GPL");MODULE_DESCRIPTION("RAM-only external PHY reset replay with strict inherited pin guards");
