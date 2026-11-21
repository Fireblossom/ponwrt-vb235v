// SPDX-License-Identifier: GPL-2.0-only
/* Restricted bootstrap provider. No DT, bus name, GPIO or owner is invented. */
#include <linux/capability.h>
#include <linux/etherdevice.h>
#include <linux/fs.h>
#include <linux/gpio/consumer.h>
#include <linux/kref.h>
#include <linux/miscdevice.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_mdio.h>
#include <linux/platform_device.h>
#include <linux/uaccess.h>
#include "provider_uapi.h"
#include "provider_owner.h"
struct pndsl_device {
 struct device *dev;struct mii_bus *bus;struct gpio_desc *reset;
 struct miscdevice misc;struct file *claimant;
 bool verified,read_safe,poisoned,dying;unsigned int ifindex;u8 peer[6];struct kref refs;
};
static DEFINE_MUTEX(owner_lock);
static struct device *owner_dev;
static const struct pndsl_owner_ops *owner_ops;
static struct pndsl_device *active_device;
static void free_provider(struct kref *ref)
{struct pndsl_device *p=container_of(ref,struct pndsl_device,refs);put_device(&p->bus->dev);put_device(p->dev);kfree(p);}
int ponwrt_dsl_owner_register(struct device *dev,const struct pndsl_owner_ops *ops)
{
 int ret=0;if(!dev||!ops||!ops->claim||!ops->release||!ops->profile||strcmp(ops->profile,PNDSL_PROFILE))return -EINVAL;
 mutex_lock(&owner_lock);if(owner_ops)ret=-EBUSY;else {owner_dev=get_device(dev);owner_ops=ops;}mutex_unlock(&owner_lock);return ret;
}
EXPORT_SYMBOL_GPL(ponwrt_dsl_owner_register);
int ponwrt_dsl_owner_unregister(struct device *dev)
{
 int ret=0;mutex_lock(&owner_lock);
 if(dev!=owner_dev)ret=-ENOENT;
 else if(active_device&&active_device->claimant)ret=-EBUSY;
 else {put_device(owner_dev);owner_dev=NULL;owner_ops=NULL;}
 mutex_unlock(&owner_lock);return ret;
}
EXPORT_SYMBOL_GPL(ponwrt_dsl_owner_unregister);
static int c22w(struct pndsl_device *p,unsigned int r,u16 v){return __mdiobus_write(p->bus,24,r,v);}
static int w32(struct pndsl_device *p,u32 a,u32 v)
{
 int e;if((e=c22w(p,1,a))||(e=c22w(p,2,a>>16))||(e=c22w(p,3,v))||(e=c22w(p,4,v>>16)))return e;
 return c22w(p,0,0xff);
}
static int r32(struct pndsl_device *p,u32 a,u32 *v)
{
 int e,lo=0,hi=0,restore;*v=0;e=w32(p,0x1fa20160,0);
 if(!e)e=c22w(p,1,a);
 if(!e)e=c22w(p,2,a>>16);
 if(!e)e=c22w(p,0,0xf0);
 if(!e){lo=__mdiobus_read(p->bus,24,3);if(lo<0)e=lo;}
 if(!e){hi=__mdiobus_read(p->bus,24,4);if(hi<0)e=hi;}
 restore=w32(p,0x1fa20160,0x800);if(!e)e=restore;if(!e)*v=(u16)lo|((u32)(u16)hi<<16);return e;
}
static bool read_allowed(u32 a)
{return a==0x1fb00f00||a==0x1fb0009c||a==0x1fb0005c||a==0x1fa20174||a==0x1fa70b04;}
static bool write_allowed(u32 a,u32 v)
{
 if(a&3)return false;
 if(a>=0x1fa30000&&a<=0x1fa30000+22744)return true;
 if(a>=0x1fa40000&&a<0x1fa47800)return true;
 switch(a){
 case 0x1fb00f00:return v==0;
 case 0x1fb00f04:return v==0x444f4e45||v==0x66697368||v==0x494e5345;
 case 0x1fb00f10:return v==22744||v==30720;
 case 0x1fb00f14:return v==0x1000000;
 case 0x1fa20160:return v==0||v==0x800;
 case 0x1fa20190:return v==0x12;
 case 0x1fa2020c:return v==0x04000000;
 case 0x1fa20204:return v==0x402;
 case 0x1fa201f8:return v==0x05001f08||v==0x05001f0a||v==0x05001f0e;
 case 0x1fa20208:return v==0x03000000;
 default:return false;
 }
}
static int release_claim(struct pndsl_device *p)
{
 int e=0,t;
 if(!p->claimant)return 0;
 if(p->reset){e=gpiod_direction_output(p->reset,1);gpiod_put(p->reset);p->reset=NULL;}
 t=owner_ops->release(owner_dev);if(!e)e=t;
 if(e)p->poisoned=true;
 p->claimant=NULL;p->ifindex=0;eth_zero_addr(p->peer);module_put(owner_ops->module);return e;
}
static bool hashes_match(const struct pndsl_claim *c)
{
 static const unsigned int sizes[]={22744,39556,4214743};
 static const char *const hashes[]={
 "7ea80b9b2c30f6687a0b14e1e8bc259f9daaf554b138770b4fb1b1886dfe1404",
 "2840bd859eb27dbcc2997abde5223a7059ef3d97e89d047a2854eef664ed341f",
 "c6e0a8d0cbaf282b956a9fd3b9050cb073434947c6a32c9b95976b72eaa2a412"};
 u8 expected[32];unsigned int i;
 if(c->abi!=PNDSL_ABI||!c->generation||memcmp(c->profile,PNDSL_PROFILE,sizeof(PNDSL_PROFILE)))return false;
 for(i=0;i<3;i++)if(c->sizes[i]!=sizes[i]||hex2bin(expected,hashes[i],32)||memcmp(expected,c->sha256[i],32))return false;
 return true;
}
static long control_ioctl(struct file *file,unsigned int cmd,unsigned long arg)
{
 struct pndsl_device *p=file->private_data;void __user *u=(void __user *)arg;int e=0;
 if(!capable(CAP_SYS_RAWIO))return -EPERM;
 mutex_lock(&owner_lock);
 if(p->dying){e=-ENODEV;goto out;}
 if(cmd==PNDSL_QUERY){
  struct pndsl_query q={.abi=PNDSL_ABI,.ifindex=p->ifindex};strscpy(q.profile,PNDSL_PROFILE,sizeof(q.profile));
  if(p->verified&&!p->poisoned)q.flags|=PNDSL_F_BOARD_VERIFIED;
  if(owner_ops)q.flags|=PNDSL_F_OWNER_PRESENT;
  if(p->claimant==file)q.flags|=PNDSL_F_CLAIMED;
  if(p->read_safe)q.flags|=PNDSL_F_RAW_READ_SAFE;
  if(is_valid_ether_addr(p->peer)){q.flags|=PNDSL_F_PEER_VERIFIED;ether_addr_copy(q.peer,p->peer);}
  /* ROM tail and final execution ACK remain unverified, with no bypass flag. */
  e=copy_to_user(u,&q,sizeof(q))?-EFAULT:0;goto out;
 }
 if(cmd==PNDSL_RAW_READ){
  struct pndsl_raw r;if(!p->read_safe){e=-EPERM;goto out;}
  if(copy_from_user(&r,u,sizeof(r))){e=-EFAULT;goto out;}if(r.reg>31){e=-EINVAL;goto out;}
  e=mdiobus_read(p->bus,24,r.reg);if(e>=0){r.value=e;e=copy_to_user(u,&r,sizeof(r))?-EFAULT:0;}goto out;
 }
 if(cmd==PNDSL_CLAIM){
  struct pndsl_claim c;if(copy_from_user(&c,u,sizeof(c))){e=-EFAULT;goto out;}
  if(!hashes_match(&c)){e=-EKEYREJECTED;goto out;}
  if(!p->verified||p->poisoned||!owner_ops){e=-EOPNOTSUPP;goto out;}
  if(p->claimant){e=-EBUSY;goto out;}
  if(!try_module_get(owner_ops->module)){e=-ENODEV;goto out;}
  e=owner_ops->claim(owner_dev,&p->ifindex,p->peer);
  if(e){module_put(owner_ops->module);goto out;}
  p->claimant=file;
  /* ASIS only AFTER successful board-owner/pinmux admission; never at probe. */
  p->reset=gpiod_get(p->dev,"reset",GPIOD_ASIS);
  if(IS_ERR(p->reset)){e=PTR_ERR(p->reset);p->reset=NULL;release_claim(p);}goto out;
 }
 if(p->claimant!=file){e=-EPERM;goto out;}
 if(cmd==PNDSL_RELEASE){e=release_claim(p);goto out;}
 if(cmd==PNDSL_RESET){
  u32 value;if(copy_from_user(&value,u,sizeof(value))){e=-EFAULT;goto out;}
  if(value>1){e=-EINVAL;goto out;}e=gpiod_direction_output(p->reset,value);
  if(!e){int actual=gpiod_get_value_cansleep(p->reset);if(actual<0)e=actual;else if(actual!=(int)value)e=-EIO;}goto out;
 }
 if(cmd==PNDSL_READ32||cmd==PNDSL_WRITE32){
  struct pndsl_word w;if(copy_from_user(&w,u,sizeof(w))){e=-EFAULT;goto out;}
  if((cmd==PNDSL_READ32&&!read_allowed(w.address))||(cmd==PNDSL_WRITE32&&!write_allowed(w.address,w.value))){e=-EPERM;goto out;}
  mutex_lock(&p->bus->mdio_lock);e=cmd==PNDSL_READ32?r32(p,w.address,&w.value):w32(p,w.address,w.value);mutex_unlock(&p->bus->mdio_lock);
  if(!e&&cmd==PNDSL_READ32)e=copy_to_user(u,&w,sizeof(w))?-EFAULT:0;
  goto out;
 }
 e=-ENOTTY;
out:mutex_unlock(&owner_lock);return e;
}
static int control_open(struct inode *inode,struct file *file)
{struct miscdevice *misc=file->private_data;struct pndsl_device *p=container_of(misc,struct pndsl_device,misc);int e=0;(void)inode;
 mutex_lock(&owner_lock);if(p->dying)e=-ENODEV;else {kref_get(&p->refs);file->private_data=p;}mutex_unlock(&owner_lock);
 if(!e)e=nonseekable_open(inode,file);
 return e;}
static int control_close(struct inode *inode,struct file *file)
{struct pndsl_device *p=file->private_data;(void)inode;mutex_lock(&owner_lock);if(p->claimant==file)release_claim(p);mutex_unlock(&owner_lock);kref_put(&p->refs,free_provider);return 0;}
static const struct file_operations control_ops={.owner=THIS_MODULE,.open=control_open,.release=control_close,.unlocked_ioctl=control_ioctl};
static int provider_probe(struct platform_device *pdev)
{
 struct pndsl_device *p;struct device_node *node;const char *profile;int e;
 if(of_property_read_string(pdev->dev.of_node,"ponwrt,board-profile",&profile)||strcmp(profile,PNDSL_PROFILE))return -EINVAL;
 node=of_parse_phandle(pdev->dev.of_node,"mdio-parent-bus",0);if(!node)return -EINVAL;
 p=kzalloc(sizeof(*p),GFP_KERNEL);if(!p){of_node_put(node);return -ENOMEM;}
 p->bus=of_mdio_find_bus(node);of_node_put(node);if(!p->bus){kfree(p);return -EPROBE_DEFER;}
 p->dev=get_device(&pdev->dev);kref_init(&p->refs);
 p->verified=of_property_read_bool(pdev->dev.of_node,"ponwrt,board-mode-verified")&&of_property_read_bool(pdev->dev.of_node,"ponwrt,gpio-mode-verified");
 p->read_safe=of_property_read_bool(pdev->dev.of_node,"ponwrt,raw-read-safe");
 p->misc=(struct miscdevice){.minor=MISC_DYNAMIC_MINOR,.name="ponwrt-dsl",.fops=&control_ops,.parent=&pdev->dev,.mode=0600};
 mutex_lock(&owner_lock);
 if(active_device){mutex_unlock(&owner_lock);kref_put(&p->refs,free_provider);return -EBUSY;}
 active_device=p;mutex_unlock(&owner_lock);
 /* Avoid owner_lock -> misc_mtx inversion with misc_open -> owner_lock. */
 e=misc_register(&p->misc);
 if(e){mutex_lock(&owner_lock);active_device=NULL;mutex_unlock(&owner_lock);kref_put(&p->refs,free_provider);}
 else platform_set_drvdata(pdev,p);
 return e;
}
static void provider_remove(struct platform_device *pdev)
{
 struct pndsl_device *p=platform_get_drvdata(pdev);misc_deregister(&p->misc);
 mutex_lock(&owner_lock);p->dying=true;release_claim(p);active_device=NULL;mutex_unlock(&owner_lock);kref_put(&p->refs,free_provider);
}
static const struct of_device_id provider_match[]={{.compatible="ponwrt,vb235v-dsl-bootstrap"},{}};
MODULE_DEVICE_TABLE(of,provider_match);
static struct platform_driver provider_driver={.probe=provider_probe,.remove=provider_remove,.driver={.name="ponwrt-dsl",.of_match_table=provider_match}};
module_platform_driver(provider_driver);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Fail-closed PonWrt DSL MDIO bootstrap provider; board owner required");
