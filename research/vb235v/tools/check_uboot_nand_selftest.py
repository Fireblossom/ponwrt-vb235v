# SPDX-License-Identifier: GPL-2.0-only
"""Execute the actual VB235v map/install code against a host NAND model."""
from pathlib import Path
import argparse,json,os,shutil,subprocess,tempfile

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,required=True)
parser.add_argument('--build',type=Path,required=True)
parser.add_argument('--output',type=Path)
parser.add_argument('--extra-fit',type=Path,help='also validate a packaged firmware FIT without installing it')
args=parser.parse_args();SRC=args.source.resolve();BUILD=args.build.resolve()

MOCK=r'''
#ifndef MOCK_H
#define MOCK_H
#define CONFIG_VB235V_NAND_SELFTEST 1
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef uint64_t u64;
typedef unsigned long ulong;
#define EINVAL 22
#define EBADMSG 74
#define ENOENT 2
#define ENODEV 19
#define ENOMEM 12
#define EIO 5
#define EXDEV 18
#define EPERM 1
#define EOPNOTSUPP 95
#define ERANGE 34
#define ARRAY_SIZE(x) (sizeof(x)/sizeof((x)[0]))
#define min(a,b) ((a)<(b)?(a):(b))
#define min_t(t,a,b) ((t)(a)<(t)(b)?(t)(a):(t)(b))
#define DECLARE_GLOBAL_DATA_PTR
#define U_BOOT_CMD(...)
#define CMD_RET_USAGE -1
#define CMD_RET_FAILURE 1
#define CMD_RET_SUCCESS 0
#define MTD_OPS_PLACE_OOB 0
#define MTD_OPS_RAW 2
struct cmd_tbl {int unused;};
struct mtd_info {u64 size;u32 erasesize,writesize,oobsize;};
struct erase_info {u64 addr,len;};
struct mtd_oob_ops {int mode;size_t len,retlen,ooblen,oobretlen;u32 ooboffs;u8 *datbuf,*oobbuf;};
static struct mtd_info fake={0x20000000,0x40000,4096,256};
static u8 *chip;
static u8 *scan_buffer;
#define VB_SLOT_SCRATCH ((ulong)scan_buffer)
static struct {ulong start_addr_sp;} fake_gd={~0UL};
static typeof(fake_gd) *gd=&fake_gd;
static u16 metadata[2048*64];
static unsigned int erases,writes,fail_erase,fail_write,flip_read,reads,corrupt_after_write,fail_restore;
#define mtd_for_each_device(v) for((v)=&fake;(v);(v)=NULL)
static int mtd_is_partition(struct mtd_info *m){return 0;}
static int mtd_is_bitflip(int ret){return ret==-117;}
static void mtd_probe_devices(void){}
static int mtd_read(struct mtd_info *m,u32 a,size_t n,size_t *done,void *p){
 if(a>=m->size||n>m->size-a)return -EIO;
 memcpy(p,chip+a,n);*done=n;reads++;
 if((flip_read||(corrupt_after_write&&writes))&&n)((u8*)p)[0]^=1;
 return 0;
}
static int mtd_erase(struct mtd_info *m,struct erase_info *e){
 erases++;if(fail_erase||(fail_restore&&erases==2))return -EIO;
 if(e->addr%0x40000||e->len!=0x40000||e->addr+e->len>m->size)return -EIO;
 memset(chip+e->addr,255,e->len);memset(metadata+e->addr/4096,255,(e->len/4096)*sizeof(metadata[0]));return 0;
}
static int mtd_write_oob(struct mtd_info *m,u32 a,struct mtd_oob_ops *o){
 writes++;if(fail_write==writes)return -EIO;
 if(a%4096||o->len!=4096||o->ooboffs!=2||o->ooblen!=2||o->mode!=MTD_OPS_PLACE_OOB)return -EIO;
 for(unsigned i=0;i<4096;i++)chip[a+i]&=o->datbuf[i];
 metadata[a/4096]=o->oobbuf[0]|((u16)o->oobbuf[1]<<8);
 o->retlen=o->len;o->oobretlen=o->ooblen;return 0;
}
static int mtd_read_oob(struct mtd_info *m,u32 a,struct mtd_oob_ops *o){
 if(a>=m->size||o->len>m->size-a)return -EIO;
 if(o->datbuf){memcpy(o->datbuf,chip+a,o->len);o->retlen=o->len;}
 if(o->oobbuf){
  memset(o->oobbuf,255,o->ooblen);o->oobretlen=o->ooblen;
  for(unsigned i=0;i<o->ooblen;i++){
   unsigned index=o->ooboffs+i;
   if(index==2)o->oobbuf[i]=metadata[a/4096]&255;
   if(index==3)o->oobbuf[i]=metadata[a/4096]>>8;
  }
 }
 return 0;
}
static int env_set_hex(const char *n,ulong v){return 0;}
static ulong hextoul(const char *p,char **end){return strtoul(p,end,16);}
static int run_command(const char *c,int f){return -EIO;}
static int vb_factory_boot(void){return -EIO;}
#endif
'''

MAIN=r'''
#include "mock.h"
#include "map.c"
#include "storage.c"
#include <libfdt.h>
static unsigned int cases,checks;
#define CHECK(v) do{checks++;if(!(v)){fprintf(stderr,"line %d: %s\n",__LINE__,#v);exit(1);}}while(0)
#define CASE() do{cases++;}while(0)
static u8 bbt[4096],bmt[4096];
static void checksum_bbt(void){u16 sum=bbt[8]+bbt[9];for(int i=12;i<512;i++)sum+=bbt[i];bbt[4]=sum;bbt[5]=sum>>8;bbt[6]=bbt[7]=0;}
static void checksum_bmt(void){u8 sum=bmt[3]+bmt[5];for(int i=20;i<20+VB_POOL*4;i++)sum+=bmt[i];bmt[6]=sum;}
static void tables(void){memset(bbt,0,sizeof(bbt));memcpy(bbt,"RAWB",4);bbt[8]=1;checksum_bbt();memset(bmt,0,sizeof(bmt));memcpy(bmt,"BMT",3);bmt[3]=1;checksum_bmt();}
static int page_read(void *context,u16 block,u8 *out){
 memset(out,255,4096);if(block==1900)memcpy(out,bbt,4096);if(block==2040)memcpy(out,bmt,4096);return 0;
}
static void reset_storage(void){
 memset(&mapping,0,sizeof(mapping));for(int i=0;i<2048;i++)mapping.physical[i]=i;
 mapping.valid=true;mapping.logical_blocks=1885;mapping.bbt_block=1900;mapping.bmt_block=2040;
 flash=&fake;attempted=true;anchors_verified=true;erases=writes=fail_erase=fail_write=flip_read=reads=corrupt_after_write=fail_restore=0;
 cached_active=-99;cached_sequence=0;
 memset(chip+0xc40000,0,0x40000);memset(chip+0x5c40000,0,0x40000);
 u8 flag[8]={1,1,1,0,0,0,0,3};memcpy(chip+0xb840000,flag,8);
}
static void hexhash(const void *p,size_t n,char *hex){u8 h[32];sha256_csum_wd(p,n,h,65536);for(int i=0;i<32;i++)sprintf(hex+2*i,"%02x",h[i]);}

static void reset_tail(char secondary[65],char active[65]){
 reset_storage();memset(chip+VB_TEST_LOGICAL,255,VB_ERASE);
 memset(metadata+VB_TEST_LOGICAL/4096,255,64*sizeof(metadata[0]));
 hexhash(chip+0x5c40000,0x5000000,secondary);hexhash(chip+0xc40000,0x5000000,active);
}
static void selftest_cases(const void *fit,size_t size){
 char secondary[65],active[65];
 reset_tail(secondary,active);CASE();CHECK(vb_storage_nand_selftest(secondary,active)==0);
 CHECK(erases==2&&writes==64&&cached_active==0);CHECK(bytes_ff(chip+VB_TEST_LOGICAL,VB_ERASE));
 CHECK(metadata[VB_TEST_LOGICAL/4096]==65535);
 reset_tail(secondary,active);CASE();anchors_verified=false;CHECK(vb_storage_nand_selftest(secondary,active)==-EXDEV);CHECK(!erases&&!writes);
 reset_tail(secondary,active);CASE();memcpy(chip+0x5c40000,fit,size);CHECK(vb_storage_nand_selftest(secondary,active)==-EPERM);CHECK(!erases&&!writes);
 reset_tail(secondary,active);CASE();mapping.physical[VB_TEST_LOGICAL/VB_ERASE]++;CHECK(vb_storage_nand_selftest(secondary,active)==-EXDEV);CHECK(!erases&&!writes);
 reset_tail(secondary,active);CASE();secondary[0]=secondary[0]=='0'?'1':'0';CHECK(vb_storage_nand_selftest(secondary,active)==-EBADMSG);CHECK(!erases&&!writes);
 reset_tail(secondary,active);CASE();chip[VB_TEST_LOGICAL]=0;hexhash(chip+0x5c40000,0x5000000,secondary);CHECK(vb_storage_nand_selftest(secondary,active)==-EBADMSG);CHECK(!erases&&!writes);
 reset_tail(secondary,active);CASE();metadata[VB_TEST_LOGICAL/4096]=0;CHECK(vb_storage_nand_selftest(secondary,active)==-EBADMSG);CHECK(!erases&&!writes);
 reset_tail(secondary,active);CASE();fail_write=33;CHECK(vb_storage_nand_selftest(secondary,active)==-EIO);CHECK(erases==2&&writes==33);CHECK(bytes_ff(chip+VB_TEST_LOGICAL,VB_ERASE));
 reset_tail(secondary,active);CASE();fail_restore=1;CHECK(vb_storage_nand_selftest(secondary,active)==-EIO);CHECK(erases==2&&writes==64);CHECK(!bytes_ff(chip+VB_TEST_LOGICAL,VB_ERASE));
 reset_tail(secondary,active);CASE();fail_erase=1;CHECK(vb_storage_nand_selftest(secondary,active)==-EIO);CHECK(erases==2&&!writes);
 reset_tail(secondary,active);CASE();CHECK(vb_storage_nand_selftest(NULL,active)==-EINVAL);CHECK(vb_storage_nand_selftest("short",active)==-EINVAL);CHECK(!erases&&!writes);
}
int main(int argc,char **argv){
 struct vb_map map;u32 physical;u8 original;char sha[65];u8 *fit,*mutated;long size;
 CHECK(argc==2||argc==3);chip=calloc(1,0x20000000);scan_buffer=malloc(0x5000000);CHECK(chip&&scan_buffer);tables();
 CASE();CHECK(vb_map_load(&map,page_read,NULL)==0);CHECK(map.valid&&map.logical_blocks==1885);
 for(unsigned i=0;i<1885;i++){CHECK(map.physical[i]==i);CHECK(vb_translate(&map,i*VB_ERASE,&physical)==(i*VB_ERASE<VB_LIMIT?0:-EINVAL));}
 CASE();CHECK(vb_translate(&map,VB_LIMIT,&physical)==-EINVAL);CHECK(vb_translate(NULL,0,&physical)==-EINVAL);CHECK(vb_translate(&map,0,NULL)==-EINVAL);
 CASE();bbt[9]=2;bbt[12]=0;bbt[14]=5;checksum_bbt();bmt[5]=1;bmt[20]=7;bmt[22]=0xd0;bmt[23]=7;checksum_bmt();
 CHECK(vb_map_load(&map,page_read,NULL)==0);CHECK(map.physical[0]==1&&map.physical[4]==6&&map.physical[5]==2000);
 CHECK(vb_translate(&map,5*VB_ERASE+123,&physical)==0&&physical==2000*VB_ERASE+123);
 for(int i=12;i<512;i++){CASE();bbt[i]^=1;CHECK(vb_decode_bbt(&map,bbt,4096)!=0);bbt[i]^=1;}
 for(int i=20;i<20+VB_POOL*4;i++){CASE();bmt[i]^=1;CHECK(vb_decode_bmt(&map,bmt,4096)!=0);bmt[i]^=1;}
 CASE();CHECK(vb_decode_bbt(&map,bbt,511)!=0);CHECK(vb_decode_bmt(&map,bmt,20+VB_POOL*4-1)!=0);
 CASE();bbt[14]=0;checksum_bbt();CHECK(vb_decode_bbt(&map,bbt,4096)!=0);tables();
 CASE();bmt[5]=2;bmt[20]=1;bmt[22]=0xd0;bmt[23]=7;bmt[24]=2;bmt[26]=0xd0;bmt[27]=7;checksum_bmt();CHECK(vb_decode_bmt(&map,bmt,4096)!=0);tables();
 CASE();bmt[5]=1;bmt[20]=1;bmt[22]=0xf8;bmt[23]=7;checksum_bmt();CHECK(vb_map_load(&map,page_read,NULL)!=0);tables();
 FILE *f=fopen(argv[1],"rb");CHECK(f);fseek(f,0,SEEK_END);size=ftell(f);rewind(f);fit=malloc(size);CHECK(fread(fit,1,size,f)==size);fclose(f);mutated=malloc(size+4096);hexhash(fit,size,sha);
 reset_storage();CASE();if(vb_fit_validate(fit,size)){
  int z,nd=fdt_path_offset(fit,"/images/fdt");const void *dt=fdt_getprop(fit,nd,"data",&z);
  fprintf(stderr,"validation=%d inner_dt_align=%lu inner_dt_check=%d compat=%d\n",vb_fit_validate(fit,size),(ulong)dt%8,fdt_check_full(dt,z),fdt_node_check_compatible(dt,0,"tplink,vb235v"));
 }CHECK(vb_fit_validate(fit,size)==0);CHECK(vb_active_slot()==0);
 CASE();CHECK(vb_storage_install(0,fit,size,sha)==-EPERM);CHECK(!erases&&!writes);
 CASE();CHECK(vb_storage_install(2,fit,size,sha)==-EINVAL);CHECK(!erases&&!writes);
 CASE();CHECK(vb_storage_install(1,fit,size,"0000000000000000000000000000000000000000000000000000000000000000")==-EBADMSG);CHECK(!erases&&!writes);
 CASE();anchors_verified=false;CHECK(vb_storage_install(1,fit,size,sha)==-EXDEV);CHECK(!erases);anchors_verified=true;
 CASE();chip[0xb840007]^=1;cached_active=-99;CHECK(vb_storage_install(1,fit,size,sha)==-EBADMSG);CHECK(!erases);chip[0xb840007]^=1;cached_active=-99;
 CASE();CHECK(vb_storage_install(1,fit,size,sha)==0);CHECK(erases==1&&writes>0);CHECK(!memcmp(chip+0x5c40000,fit,size));CHECK(metadata[0x5c40000/4096]==369);
 reset_storage();CASE();mapping.physical[369]=2000;mapping.mapped_count=1;mapping.bad[0]=369;mapping.replacement[0]=2000;
 CHECK(vb_storage_install(1,fit,size,sha)==0);CHECK(!memcmp(chip+2000U*VB_ERASE,fit,size));CHECK(metadata[2000*64]==369);
 reset_storage();CASE();fail_erase=1;CHECK(vb_storage_install(1,fit,size,sha)==-EIO);CHECK(erases==1&&!writes);
 reset_storage();CASE();fail_write=1;CHECK(vb_storage_install(1,fit,size,sha)==-EIO);CHECK(erases==1&&writes==1);
 reset_storage();CASE();flip_read=1;CHECK(vb_storage_install(1,fit,size,sha)!=0);CHECK(!erases);
 for(int type=0;type<5;type++){
  reset_storage();CASE();CHECK(fdt_open_into(fit,mutated,size+4096)==0);
  int conf=fdt_path_offset(mutated,"/configurations/ram"),node=fdt_path_offset(mutated,"/images/kernel");
  if(type==0)CHECK(fdt_setprop_string(mutated,conf,"compatible","other,board")==0);
  if(type==1)CHECK(fdt_setprop_string(mutated,node,"arch","arm")==0);
  if(type==2)CHECK(fdt_setprop_string(mutated,node,"type","script")==0);
  if(type==3)CHECK(fdt_setprop_string(mutated,node,"data","wrong data")==0);
  if(type==4)CHECK(fdt_delprop(mutated,conf,"fdt")==0);
  CHECK(fdt_pack(mutated)==0);unsigned n=fdt_totalsize(mutated);hexhash(mutated,n,sha);
  CHECK(vb_storage_install(1,mutated,n,sha)!=0);CHECK(!erases&&!writes);
 }
 reset_storage();CASE();u8 raw[4352];const struct vb_target *t=vb_target_find("nand-raw-main-oob");
 CHECK(t&&t->size==570425344);CHECK(vb_storage_read(t,t->size-1,raw,2)==-EINVAL);CHECK(vb_storage_read(t,4090,raw,20)==0);
 reset_storage();CASE();memcpy(chip+0x5c40000,fit,size);CHECK(vb_active_slot()==1);CHECK(cached_sequence==1);
 CHECK(vb_storage_install(0,fit,size,sha)==-ERANGE);CHECK(!erases&&!writes);
 for(unsigned cut=1;cut<=(size+4095)/4096;cut++){
  reset_storage();CASE();fail_write=cut;hexhash(fit,size,sha);
  CHECK(vb_storage_install(1,fit,size,sha)==-EIO);CHECK(erases==1&&writes==cut);
  fail_write=0;cached_active=-99;cached_sequence=0;CHECK(vb_active_slot()==0);
  CHECK(!memcmp(chip+0xc40000,"\0\0\0\0",4));
 }
 reset_storage();CASE();corrupt_after_write=1;hexhash(fit,size,sha);
 CHECK(vb_storage_install(1,fit,size,sha)==-EIO);CHECK(erases==1&&writes==1);
 corrupt_after_write=0;cached_active=-99;cached_sequence=0;CHECK(vb_active_slot()==0);
 if(argc==3){
  CASE();FILE *extra=fopen(argv[2],"rb");CHECK(extra);fseek(extra,0,SEEK_END);long n=ftell(extra);rewind(extra);
  CHECK(n>0&&n<=0x5000000);u8 *data=malloc(n);CHECK(data);CHECK(fread(data,1,n,extra)==n);fclose(extra);
  CHECK(vb_fit_validate(data,n)==0);free(data);
 }
 selftest_cases(fit,size);
 free(scan_buffer);free(mutated);free(fit);free(chip);printf("RESULT cases=%u assertions=%u\n",cases,checks);return 0;
}
'''

with tempfile.TemporaryDirectory(prefix='vb235v-full-host-') as directory:
 root=Path(directory)
 (root/'mock.h').write_text(MOCK)
 for h in ['asm/global_data.h','command.h','env.h','image.h','malloc.h','mtd.h','linux/err.h','linux/mtd/mtd.h','u-boot/crc.h']:
  p=root/h;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('#include "mock.h"\n')
 for h,s in {'linux/types.h':'#include "mock.h"\n','linux/errno.h':'#include "mock.h"\n','linux/libfdt.h':'#include <libfdt.h>\n','linux/kconfig.h':'#define CONFIG_IS_ENABLED(x) 0\n','linux/compiler_attributes.h':'#define __weak __attribute__((weak))\n#define __always_unused __attribute__((unused))\n'}.items():
  p=root/h;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s)
 (root/'u-boot').mkdir(exist_ok=True)
 shutil.copyfile(SRC/'include/u-boot/sha256.h',root/'u-boot/sha256.h')
 shutil.copyfile(SRC/'include/vb235v-recovery.h',root/'vb235v-recovery.h')
 for name,new in [('vb235v-map.c','map.c'),('vb235v-map.h','vb235v-map.h'),('vb235v-storage.c','storage.c')]:
  shutil.copyfile(SRC/'board/airoha/an7583'/name,root/new)
 (root/'main.c').write_text(MAIN)
 libfdt=SRC/'scripts/dtc/libfdt'
 if not libfdt.exists():libfdt=SRC/'lib/libfdt'
 (root/'kernel.bin').write_bytes(b'host test kernel')
 shutil.copyfile(BUILD/'u-boot.dtb',root/'board.dtb')
 (root/'image.its').write_text('''/dts-v1/;
/ { description="host test"; #address-cells=<1>;
 images {
  kernel { description="test"; data=/incbin/("kernel.bin"); type="kernel"; arch="arm64"; os="linux"; compression="none"; load=<0x81800000>; entry=<0x81800000>; hash-1 { algo="sha256"; }; };
  fdt { description="test"; data=/incbin/("board.dtb"); type="flat_dt"; arch="arm64"; compression="none"; hash-1 { algo="sha256"; }; };
 };
 configurations { default="ram"; ram { compatible="tplink,vb235v"; vb235v,firmware-image=<1>; vb235v,sequence=<1>; kernel="kernel"; fdt="fdt"; }; };
};
''')
 subprocess.run([str(BUILD/'tools/mkimage'),'-f','image.its','image.itb'],cwd=root,check=True,capture_output=True)
 sources=[str(p) for p in libfdt.glob('*.c') if not p.name.endswith('_overlay.c')]
 command=['cc','-std=gnu11','-O1','-g','-DUSE_HOSTCC','-fsanitize=address,undefined','-fno-omit-frame-pointer',
          '-I',str(root),'-I',str(libfdt),str(root/'main.c'),str(SRC/'lib/sha256.c'),str(SRC/'lib/sha256_common.c'),*sources,'-o',str(root/'test')]
 result=subprocess.run(command,capture_output=True,text=True)
 if result.returncode:raise RuntimeError(result.stderr[-10000:])
 result=subprocess.run([str(root/'test'),str(root/'image.itb')]+([str(args.extra_fit.resolve())] if args.extra_fit else []),capture_output=True,text=True)
 if result.returncode:raise RuntimeError(result.stdout[-2000:]+result.stderr[-10000:])
 print(result.stdout)
 if args.output:args.output.write_text(result.stdout)
