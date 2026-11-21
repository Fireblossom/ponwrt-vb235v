// SPDX-License-Identifier: GPL-2.0-only
/* Bounded local image inspection/extraction; no device or NAND operations. */
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <limits.h>
#include <libfdt.h>
typedef uint8_t u8;typedef uint32_t u32;
static u32 crc32(u32 seed,const u8 *p,size_t n)
{
 u32 c=~seed;while(n--){c^=*p++;for(unsigned i=0;i<8;i++)c=(c>>1)^(0xedb88320U&-(c&1));}return ~c;
}
#include "vb235v-sysupgrade-envelope.h"
static void require(int okay,const char *why){if(!okay){fprintf(stderr,"VB235v image rejected: %s\n",why);exit(1);}}
static uint64_t le64(const u8 *p){uint64_t v=0;for(unsigned i=0;i<8;i++)v|=(uint64_t)p[i]<<(i*8);return v;}
static unsigned le16(const u8 *p){return p[0]|p[1]<<8;}
static const char *strprop(const void *fdt,int node,const char *key)
{
 int n;const char *p=fdt_getprop(fdt,node,key,&n);require(p&&n>0&&!p[n-1]&&strlen(p)==(size_t)n-1,key);return p;
}
static unsigned prop32(const void *fdt,int node,const char *key)
{
 int n;const fdt32_t *p=fdt_getprop(fdt,node,key,&n);require(p&&n==4,key);return fdt32_to_cpu(*p);
}
static unsigned children(const void *fdt,int parent){unsigned n=0;int c;fdt_for_each_subnode(c,fdt,parent)n++;return n;}
static int check_tree(const void *fdt,size_t bytes)
{
 if(bytes<40||fdt_check_header(fdt)||fdt_totalsize(fdt)>bytes)return -1;
 int offset=0,next=0,depth=0,roots=0;
 for(unsigned i=0;i<100000;i++) {
  unsigned tag=fdt_next_tag(fdt,offset,&next);if(next<0)return -1;
  if(tag==FDT_BEGIN_NODE){if(!depth&&roots++)return -1;depth++;}
  else if(tag==FDT_END_NODE){if(depth<=0)return -1;depth--;}
  else if(tag==FDT_PROP){const char *name;int n;if(!depth||!fdt_getprop_by_offset(fdt,offset,&name,&n)||n<0)return -1;}
  else if(tag==FDT_END)return depth||!roots?-1:0;
  else if(tag!=FDT_NOP)return -1;
  if(next<=offset)return -1;
  offset=next;
 }
 return -1;
}
static void save(const char *dir,const char *name,const void *data,size_t n)
{
 char path[PATH_MAX];require(snprintf(path,sizeof(path),"%s/%s",dir,name)<(int)sizeof(path),"output path");
 FILE *f=fopen(path,"wbx");require(f!=NULL,"new output file");require(fwrite(data,1,n,f)==n,"output write");require(!fclose(f),"output close");
}
static const u8 *image(const void *fit,const char *name,const char *type,int *bytes,const u8 **hash)
{
 char path[128];require(snprintf(path,sizeof(path),"/images/%s",name)<(int)sizeof(path),"image name");
 int node=fdt_path_offset(fit,path);require(node>=0,"FIT image node");
 require(!strcmp(strprop(fit,node,"type"),type),"FIT image type");
 require(!strcmp(strprop(fit,node,"arch"),"arm64"),"FIT architecture");
 require(!fdt_getprop(fit,node,"data-offset",NULL)&&!fdt_getprop(fit,node,"data-position",NULL),"inline FIT data required");
 const u8 *data=fdt_getprop(fit,node,"data",bytes);require(data&&*bytes>0,"FIT payload");
 require(children(fit,node)==1,"single image hash required");
 int h=fdt_first_subnode(fit,node),hn;
 require(!strcmp(strprop(fit,h,"algo"),"sha256"),"FIT SHA256 required");
 *hash=fdt_getprop(fit,h,"value",&hn);require(*hash&&hn==32,"FIT hash length");return data;
}
int main(int argc,char **argv)
{
 require(argc==3,"usage: image-check IMAGE NEW_PRIVATE_OUTPUT_DIRECTORY");
 FILE *f=fopen(argv[1],"rb");require(f!=NULL,"input file");require(!fseek(f,0,SEEK_END),"input seek");
 long length=ftell(f);require(length>0&&length<=0x3800000,"image size");rewind(f);
 u8 *data=malloc((size_t)length);require(data!=NULL,"memory");require(fread(data,1,length,f)==(size_t)length,"input read");require(!fclose(f),"input close");
 struct vb_sysupgrade_envelope env;require(!vb_sysupgrade_envelope_inspect(data,length,&env),"complete fwtool framing/CRC");
 require(!env.signature_bytes,"signature verification unavailable");
 require(env.payload_bytes>sizeof(struct fdt_header),"FIT header");
 require(!fdt_check_header(data),"FIT header");size_t fitbytes=fdt_totalsize(data);
 require(fitbytes<=0x1000000&&fitbytes<env.payload_bytes&&!check_tree(data,fitbytes),"bounded complete FIT");
 int configs=fdt_path_offset(data,"/configurations"),images=fdt_path_offset(data,"/images");
 require(configs>=0&&images>=0&&children(data,configs)==1&&children(data,images)==2,"single FIT configuration/two images");
 const char *name=strprop(data,configs,"default");int conf=fdt_subnode_offset(data,configs,name);require(conf>=0,"default configuration");
 require(!strcmp(strprop(data,conf,"compatible"),"tplink,vb235v")&&prop32(data,conf,"vb235v,firmware-image")==1&&prop32(data,conf,"vb235v,sequence")>0,"production FIT marker");
 require(!fdt_getprop(data,conf,"ramdisk",NULL)&&!fdt_getprop(data,conf,"loadables",NULL)&&!fdt_getprop(data,conf,"firmware",NULL),"ambiguous FIT role");
 const char *kn=strprop(data,conf,"kernel"),*dn=strprop(data,conf,"fdt");require(strcmp(kn,dn)!=0,"separate kernel and DTB");
 int kb,db;const u8 *kh,*dh,*kernel=image(data,kn,"kernel",&kb,&kh),*dtb=image(data,dn,"flat_dt",&db,&dh);
 char kp[128];require(snprintf(kp,sizeof(kp),"/images/%s",kn)<(int)sizeof(kp),"kernel path");int node=fdt_path_offset(data,kp);
 require(!strcmp(strprop(data,node,"os"),"linux")&&!strcmp(strprop(data,node,"compression"),"lzma"),"kernel Linux/LZMA");
 require(prop32(data,node,"load")==0x80200000&&prop32(data,node,"entry")==0x80200000,"kernel load/entry");
 require(db<=0x100000,"DTB size");
 u8 *aligned_dtb=malloc((size_t)db);require(aligned_dtb!=NULL,"aligned DTB memory");memcpy(aligned_dtb,dtb,(size_t)db);
 require(!check_tree(aligned_dtb,(size_t)db)&&fdt_totalsize(aligned_dtb)==(unsigned)db,"complete DTB");
 int count;const char *compatible=fdt_getprop(aligned_dtb,0,"compatible",&count);
 require(compatible&&fdt_stringlist_contains(compatible,count,"tplink,vb235v"),"DTB board");
 size_t root_at=(fitbytes+0x1ffff)&~(size_t)0x1ffff;require(root_at<env.payload_bytes&&env.payload_bytes-root_at>=96,"rootfs header");
 for(size_t i=fitbytes;i<root_at;i++)require(data[i]==0||data[i]==255,"FIT padding");
 const u8 *root=data+root_at;
 require(!memcmp(root,"hsqs",4)&&le16(root+20)==4&&le16(root+28)==4&&le16(root+30)==0,"SquashFS v4/XZ");
 uint64_t rootbytes=le64(root+40);require(rootbytes>=96&&rootbytes<=env.payload_bytes-root_at,"rootfs bounds");
 unsigned block=(unsigned)root[12]|(unsigned)root[13]<<8|(unsigned)root[14]<<16|(unsigned)root[15]<<24;
 require(block>=4096&&block<=1048576&&!(block&(block-1))&&le16(root+22)<31&&block==(1U<<le16(root+22)),"SquashFS block geometry");
 for(unsigned i=48;i<96;i+=8){uint64_t at=le64(root+i);if(at!=UINT64_MAX)require(at>=96&&at<rootbytes,"SquashFS table bounds");else require(i!=48&&i!=64&&i!=72,"SquashFS required table");}
 require((fitbytes+253951)/253952+(rootbytes+253951)/253952+24<=275,"UBI capacity and overlay reserve");
 require(env.payload_bytes-root_at-(size_t)rootbytes<=0x40004,"rootfs padding bound");
 save(argv[2],"kernel.bin",data,fitbytes);save(argv[2],"rootfs.bin",root,rootbytes);
 save(argv[2],"kernel-payload.bin",kernel,kb);save(argv[2],"dtb.bin",dtb,db);
 save(argv[2],"metadata.json",data+env.metadata_offset,env.metadata_bytes);
 char hashes[220];int used=0;
 for(unsigned j=0;j<2;j++){
  const u8 *h=j?dh:kh;for(unsigned i=0;i<32;i++)used+=snprintf(hashes+used,sizeof(hashes)-used,"%02x",h[i]);
  used+=snprintf(hashes+used,sizeof(hashes)-used,"  %s\n",j?"dtb.bin":"kernel-payload.bin");
 }
 save(argv[2],"fit-hashes.txt",hashes,used);free(aligned_dtb);free(data);
 printf("{\"complete\":true,\"kernel_bytes\":%zu,\"rootfs_bytes\":%llu,\"NAND_operations\":false}\n",fitbytes,(unsigned long long)rootbytes);return 0;
}
