// SPDX-License-Identifier: GPL-2.0-only
/* Normal recovery core: read the protected-layout UBI system, or return. */
#include <command.h>
#include <env.h>
#include <malloc.h>
#include <net.h>
#include <stdio.h>
#include <linux/delay.h>
#include <linux/errno.h>
#include <linux/libfdt.h>
#include <asm/io.h>
#include <ubi_uboot.h>
#include <vb235v-recovery.h>
#include "vb235v-ubi-ro.h"

static int vb_system_idle_dma(void)
{
 void __iomem *reset=(void __iomem *)0x1fb00834;
 u32 a,b,old,mask=BIT(21)|BIT(1)|BIT(2);
 eth_halt();
 a=readl((void __iomem *)0x1fb54004);b=readl((void __iomem *)0x1fb56004);
 if((a|b)&5)return -EBUSY;
 if((a|b)&15) {
  old=readl(reset);if(old&mask)return -EBUSY;
  writel(old|mask,reset);mdelay(100);writel(old,reset);mdelay(100);
  if(readl(reset)!=old)return -EIO;
 }
 for(unsigned i=0;i<2;i++) {
  if((readl((void __iomem *)0x1fb54004)|readl((void __iomem *)0x1fb56004))&15)return -EBUSY;
  mdelay(20);
 }
 return 0;
}

int vb_boot_system(void)
{
 void *fit=(void *)0x90000000;u8 *root;u32 bytes;int ret,configs,conf,n;
 const char *name;
 if(IS_ENABLED(CONFIG_VB235V_BOOTSTRAP_LOADER))return -EPERM;
 ret=vb_storage_init();if(ret)return ret;
 ret=vb_ubi_system_ro_enable();if(ret)return ret;
 ret=ubi_part("vb235v-system-ro",NULL);if(ret)return ret;
 if(!ubi_volume_exists("kernel")||!ubi_volume_exists("rootfs"))return -ENOENT;
 ret=ubi_volume_read("kernel",fit,0,4096);if(ret)return ret;
 if(fdt_check_header(fit))return -EBADMSG;
 bytes=fdt_totalsize(fit);if(bytes<40||bytes>0x1000000)return -EFBIG;
 ret=ubi_volume_read("kernel",fit,0,bytes);if(ret)return ret;
 ret=vb_fit_validate(fit,bytes);if(ret)return ret;
 configs=fdt_path_offset(fit,"/configurations");name=fdt_getprop(fit,configs,"default",&n);
 if(!name||n<=0||name[n-1])return -EINVAL;
 conf=fdt_subnode_offset(fit,configs,name);
 if(conf<0||fdt_getprop(fit,conf,"ramdisk",NULL))return -EINVAL;
 root=memalign(8,4096);if(!root)return -ENOMEM;
 ret=ubi_volume_read("rootfs",root,0,4096);
 if(!ret&&(memcmp(root,"hsqs",4)||root[28]!=4||root[29]||root[30]||root[31]))ret=-EBADMSG;
 free(root);if(ret)return ret;
 ret=vb_system_idle_dma();if(ret)return ret;
 ret=env_set("bootargs","console=ttyS0,115200n8 earlycon=uart8250,mmio32,0x1fbf0000,115200n8 root=/dev/ubiblock0_1 rootfstype=squashfs ubi.mtd=vb235v-system ubi.block=0,rootfs ro loglevel=7 panic=10");
 if(ret)return ret;
 puts("Booting validated VB235v persistent UBI system; fixed rescue and factory slot0 preserved\n");
 return run_command("bootm 0x90000000",0);
}
