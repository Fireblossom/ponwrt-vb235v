/* SPDX-License-Identifier: GPL-2.0-only */
/* Included in SPI-NAND core: admit only the measured 319-PEB system body. */
#include <crypto/sha2.h>
#include <linux/of.h>
#include "vb235v-map.h"
#include "vb235v-system-anchors.h"

static int vb_system_table_read(void *context, u16 block, u8 *page)
{
 struct mtd_info *mtd=context; u8 oob[256];
 struct mtd_oob_ops op={.mode=MTD_OPS_PLACE_OOB,.len=4096,.ooblen=256,.datbuf=page,.oobbuf=oob};
 int ret=mtd_read_oob(mtd,(u64)block*0x40000,&op);
 if ((ret&&!mtd_is_bitflip(ret))||op.retlen!=4096||op.oobretlen!=256||oob[0]!=255||oob[1]!=255)
  return -EIO;
 return 0;
}

static int vb_system_anchor(struct mtd_info *mtd, const struct vb_map *map,
                           u32 start, u32 bytes, const char *expected)
{
 struct sha256_ctx hash; u8 digest[32],*buf; char hex[65];
 u32 offset,physical; size_t done; unsigned i; int ret=0;
 buf=kmalloc(65536,GFP_KERNEL);if(!buf)return -ENOMEM;
 sha256_init(&hash);
 for(offset=0;offset<bytes;offset+=65536) {
  ret=vb_translate(map,start+offset,&physical);if(ret)goto out;
  ret=mtd_read(mtd,physical,min_t(u32,65536,bytes-offset),&done,buf);
  if((ret&&!mtd_is_bitflip(ret))||done!=min_t(u32,65536,bytes-offset)){ret=-EIO;goto out;}
  sha256_update(&hash,buf,done);cond_resched();
 }
 sha256_final(&hash,digest);
 for(i=0;i<32;i++)sprintf(hex+i*2,"%02x",digest[i]);
 ret=strcmp(hex,expected)?-EBADMSG:0;
out:
 kfree(buf);return ret;
}

static int vb235v_system_admit(struct spinand_device *chip)
{
 struct mtd_info *mtd=spinand_to_mtd(chip);struct vb_map *map;
 unsigned i;int ret;
 if(!device_property_read_bool(&chip->spimem->spi->dev,"tplink,vb235v-system-install"))return 0;
 if(!chip->vb235v_hybrid||!of_machine_is_compatible("tplink,vb235v")||
    mtd->size!=0x20000000||mtd->erasesize!=0x40000||mtd->writesize!=4096||
    mtd->oobsize!=256||mtd->ecc_strength!=8||mtd->ecc_step_size!=512||
    mtd->bitflip_threshold!=6||mtd->subpage_sft)return -EINVAL;
 map=kzalloc(sizeof(*map),GFP_KERNEL);if(!map)return -ENOMEM;
 ret=vb_map_load(map,vb_system_table_read,mtd);if(ret)goto out;
 /* Rescue block 369 is never admitted; physical addresses are not compacted. */
 for(i=370;i<689;i++)if(map->physical[i]!=i){ret=-EXDEV;goto out;}
 ret=vb_system_anchor(mtd,map,0,0x80000,VB_SYSTEM_BOOT_PREFIX_SHA);if(ret)goto out;
 ret=vb_system_anchor(mtd,map,0xc0000,0x380000,VB_SYSTEM_ART_SHA);if(ret)goto out;
 ret=vb_system_anchor(mtd,map,0x5c40000,0x40000,VB_SYSTEM_RESCUE_SHA);if(ret)goto out;
 /* A newly failing block stops writes; runtime retirement needs its own qualification. */
 chip->vb235v_policy=(struct vb_hybrid_policy){.identity_verified=true,.writes_admitted=true};
 pr_info("VB235V_SYSTEM admitted offset=05c80000 bytes=04fc0000 pebs=319 ecc=8/512 protected_anchors=3 retirement=0\n");
out:
 kfree(map);
 if(ret)pr_err("VB235V_SYSTEM admission failed %d; no writes admitted\n",ret);
 return ret;
}
