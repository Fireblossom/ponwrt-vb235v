/* SPDX-License-Identifier: GPL-2.0-only */
#include "core.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static unsigned assertions;
#define CHECK(x) do { assertions++; assert(x); } while(0)
static void pattern(uint8_t *p,size_t n){for(size_t i=0;i<n;i++)p[i]=(uint8_t)(i*7+3);}
static void unhex(const char *s,uint8_t *out,size_t n)
{for(size_t i=0;i<n;i++){unsigned v=0;assert(sscanf(s+i*2,"%2x",&v)==1);out[i]=(uint8_t)v;}}
static void checksums(void)
{
 uint8_t *p=malloc(4214743);assert(p);pattern(p,4214743);
 const size_t lens[]={0,1,2,3,4,8192,8193};const uint16_t expected[]={65535,65532,62972,62955,56811,63495,65535};
 for(unsigned i=0;i<7;i++)CHECK(dsl_checksum(p,lens[i])==expected[i]);
 /* Exact original RRQ: 8,498,449 guest instructions on this synthetic input. */
 CHECK(dsl_file_checksum(p,4214743)==14047);free(p);
 uint8_t digest[32],want[32];
 dsl_sha256((const uint8_t *)"",0,digest);unhex("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",want,32);CHECK(!memcmp(digest,want,32));
 dsl_sha256((const uint8_t *)"abc",3,digest);unhex("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",want,32);CHECK(!memcmp(digest,want,32));
 p=malloc(1000000);assert(p);memset(p,'a',1000000);dsl_sha256(p,1000000,digest);free(p);
 unhex("cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0",want,32);CHECK(!memcmp(digest,want,32));
}
struct call {unsigned reg;uint16_t value;bool read;};
struct bus {struct call calls[32];unsigned n,fail;};
static int bw(void *ctx,unsigned reg,uint16_t v)
{struct bus *b=ctx;assert(b->n<32);b->calls[b->n++]=(struct call){reg,v,false};return b->n==b->fail?-1:0;}
static int br(void *ctx,unsigned reg,uint16_t *v)
{struct bus *b=ctx;assert(b->n<32);*v=reg==3?0x1122:0x3344;b->calls[b->n++]=(struct call){reg,*v,true};return b->n==b->fail?-1:0;}
static void bridge(void)
{
 struct bus b={0};struct dsl_c22 io={&b,br,bw};
 const struct call expected[]={{1,0x5678,false},{2,0x1234,false},{3,0xef01,false},{4,0xabcd,false},{0,0xff,false}};
 CHECK(dsl_bridge_write32(&io,0x12345678,0xabcdef01)==DSL_OK);CHECK(b.n==5);
 for(unsigned i=0;i<5;i++)CHECK(b.calls[i].reg==expected[i].reg&&b.calls[i].value==expected[i].value&&!b.calls[i].read);
 for(unsigned i=1;i<=5;i++){memset(&b,0,sizeof(b));b.fail=i;CHECK(dsl_bridge_write32(&io,0x12345678,0xabcdef01)==DSL_E_IO);CHECK(b.n==i);}
 memset(&b,0,sizeof(b));uint32_t v=0;CHECK(dsl_bridge_read32(&io,0x12345678,&v)==DSL_OK);CHECK(v==0x33441122);CHECK(b.n==15);
 const struct call rd[]={{1,0x160,false},{2,0x1fa2,false},{3,0,false},{4,0,false},{0,0xff,false},
  {1,0x5678,false},{2,0x1234,false},{0,0xf0,false},{3,0x1122,true},{4,0x3344,true},
  {1,0x160,false},{2,0x1fa2,false},{3,0x800,false},{4,0,false},{0,0xff,false}};
 for(unsigned i=0;i<15;i++)CHECK(b.calls[i].reg==rd[i].reg&&b.calls[i].value==rd[i].value&&b.calls[i].read==rd[i].read);
 for(unsigned i=1;i<=15;i++){memset(&b,0,sizeof(b));b.fail=i;v=0xdeadbeef;CHECK(dsl_bridge_read32(&io,0x12345678,&v)==DSL_E_IO);CHECK(v==0);}
}
static void frames(void)
{
 uint8_t out[1500],expected[38],data[4];size_t n=0;pattern(data,4);const uint8_t tail[2]={0};
 struct dsl_rom_fields f={.op=5,.seq=0x1234,.file_sum=0x5566,.arg5=0x7788,.arg6=0x11223344,.arg7=0xaabbccdd};
 CHECK(dsl_rom_encode(out,sizeof(out),&f,data,4,tail,&n)==DSL_OK);CHECK(n==38);
 unhex("31623162000500000004dcfe123466557788000011223344aabbccdd00000000030a11180000",expected,38);CHECK(!memcmp(out,expected,38));
 CHECK(dsl_rom_encode(out,33,&f,NULL,0,tail,&n)==DSL_E_ARGUMENT);CHECK(n==0);
 struct dsl_rom_packet p;f=(struct dsl_rom_fields){.op=6,.seq=1};
 CHECK(dsl_rom_encode(out,sizeof(out),&f,NULL,0,tail,&n)==DSL_OK);
 CHECK(dsl_rom_decode(out,n,&p)==DSL_OK);CHECK(p.seq==1&&p.op==6&&!p.length);
 out[0]^=1;CHECK(dsl_rom_decode(out,n,&p)==DSL_E_FRAME);CHECK(p.op==0&&p.seq==0&&p.data==NULL);out[0]^=1;
 out[12]^=1;CHECK(dsl_rom_decode(out,n,&p)==DSL_E_CHECKSUM);out[12]^=1;
 out[10]=out[11]=0;CHECK(dsl_rom_decode(out,n,&p)==DSL_E_CHECKSUM);
 CHECK(dsl_rom_decode(out,13,&p)==DSL_E_FRAME);
 CHECK(dsl_rom_encode(out,sizeof(out),&f,NULL,0,tail,&n)==DSL_OK);
 out[8]=5;out[9]=0x79;CHECK(dsl_rom_decode(out,n,&p)==DSL_E_FRAME);
 CHECK(dsl_rom_encode(out,sizeof(out),&f,NULL,0,tail,&n)==DSL_OK);
 const uint8_t src[6]={2,0,0,0,0,2},dst[6]={2,0,0,0,0,1};uint8_t eth[1500]={0};
 memcpy(eth,dst,6);memcpy(eth+6,src,6);eth[12]=0xbe;eth[13]=0xef;memcpy(eth+14,out,n);
 CHECK(dsl_rom_decode_ethernet(eth,n+14,src,dst,&p)==DSL_OK);
 eth[6]^=2;CHECK(dsl_rom_decode_ethernet(eth,n+14,src,dst,&p)==DSL_E_FRAME);eth[6]^=2;
 eth[12]=0x81;eth[13]=0;CHECK(dsl_rom_decode_ethernet(eth,n+14,src,dst,&p)==DSL_E_FRAME);
}
static void sessions(void)
{
 uint8_t file[1500]={0},id[6]={2,0,0,0,0,1},reply[1500];size_t n;struct dsl_rom_session s;
 dsl_rom_init(&s,file,sizeof(file),id);struct dsl_rom_packet p={.op=1};
 CHECK(dsl_rom_handle(&s,&p,reply,sizeof(reply),&n)==DSL_BLOCK_ROM_TAIL);CHECK(s.phase==0);
 s.tail_verified=true;CHECK(dsl_rom_handle(&s,&p,reply,sizeof(reply),&n)==DSL_OK);CHECK(n==40&&s.phase==1);
 p=(struct dsl_rom_packet){.op=3,.data=(const uint8_t *)"../x",.length=5};CHECK(dsl_rom_handle(&s,&p,reply,sizeof(reply),&n)==DSL_E_SEQUENCE);
 p=(struct dsl_rom_packet){.op=3,.data=(const uint8_t *)"tclinux.bin",.length=12};
 CHECK(dsl_rom_handle(&s,&p,reply,sizeof(reply),&n)==DSL_OK);CHECK(n==1434&&s.last_seq==1);
 p=(struct dsl_rom_packet){.op=6,.seq=100};CHECK(dsl_rom_handle(&s,&p,reply,sizeof(reply),&n)==DSL_E_SEQUENCE);CHECK(s.last_seq==1&&s.phase==2);
 p.seq=1;CHECK(dsl_rom_handle(&s,&p,reply,sizeof(reply),&n)==DSL_OK);CHECK(n==134&&s.last_seq==2);
 CHECK(dsl_rom_handle(&s,&p,reply,sizeof(reply),&n)==DSL_OK);CHECK(n==134&&s.last_seq==2&&s.duplicate_acks==1);
 CHECK(dsl_rom_handle(&s,&p,reply,sizeof(reply),&n)==DSL_OK);
 CHECK(dsl_rom_handle(&s,&p,reply,sizeof(reply),&n)==DSL_OK);
 CHECK(dsl_rom_handle(&s,&p,reply,sizeof(reply),&n)==DSL_E_SEQUENCE);CHECK(n==0&&s.last_seq==2);
 p.seq=2;CHECK(dsl_rom_handle(&s,&p,reply,sizeof(reply),&n)==DSL_BLOCK_EXEC_ACK);CHECK(s.phase==3&&n==0);
}
struct hardware {uint32_t addresses[11000],values[11000],statuses[4];unsigned writes,reads,fail;uint64_t now;unsigned drift,cancel_at,resets;bool reset_values[2],pll_high,read_fail;};
static int hwread(void *ctx,uint32_t a,uint32_t *v)
{struct hardware *h=ctx;if(h->read_fail)return -1;
 if(a==0x1fb00f00){*v=h->statuses[h->reads<4?h->reads:3];h->reads++;}
 else if(a==0x1fb0009c||a==0x1fb0005c)*v=1;
 else {assert(a==0x1fa20174);*v=h->pll_high?0x10000:0;}
 return 0;}
static int hwwrite(void *ctx,uint32_t a,uint32_t v)
{struct hardware *h=ctx;assert(h->writes<11000);h->addresses[h->writes]=a;h->values[h->writes++]=v;h->now+=h->drift;return h->writes==h->fail?-1:0;}
static int hwreset(void *ctx,bool v){struct hardware *h=ctx;assert(h->resets<2);h->reset_values[h->resets++]=v;return 0;}
static uint64_t hwnow(void *ctx){return ((struct hardware *)ctx)->now;}
static int hwwait(void *ctx,unsigned n){((struct hardware *)ctx)->now+=n;return 0;}
static bool hwcancel(void *ctx){struct hardware *h=ctx;return h->cancel_at&&h->writes>=h->cancel_at;}
static void stages(void)
{
 uint8_t ddr[22744],inic[39556];pattern(ddr,sizeof(ddr));pattern(inic,sizeof(inic));struct hardware *h=calloc(1,sizeof(*h));assert(h);
 struct dsl_hw io={h,false,true,true,hwread,hwwrite,hwreset,hwnow,hwwait,hwcancel};
 CHECK(dsl_ddr_load(&io,ddr,sizeof(ddr))==DSL_E_OWNER);CHECK(h->writes==0&&h->reads==0);io.exclusive=true;
 CHECK(dsl_endpoint_prepare(&io)==DSL_OK);CHECK(h->resets==2&&h->reset_values[0]&&!h->reset_values[1]&&h->now==1000);
 CHECK(h->writes==3&&h->addresses[0]==0x1fa20190&&h->values[0]==0x12&&h->addresses[1]==0x1fa2020c&&h->values[1]==0x04000000&&h->addresses[2]==0x1fa20204&&h->values[2]==0x402);
 memset(h,0,sizeof(*h));h->pll_high=true;CHECK(dsl_endpoint_prepare(&io)==DSL_OK);CHECK(h->writes==6);
 CHECK(h->addresses[1]==0x1fa201f8&&h->values[1]==0x05001f08&&h->values[2]==0x05001f0a&&h->values[3]==0x05001f0e&&h->addresses[4]==0x1fa20208&&h->values[4]==0x03000000);
 memset(h,0,sizeof(*h));h->read_fail=true;CHECK(dsl_endpoint_prepare(&io)==DSL_E_IO);CHECK(h->writes==0);
 memset(h,0,sizeof(*h));
 h->statuses[0]=0x57414445;h->statuses[1]=0x46574f4b;
 CHECK(dsl_ddr_load(&io,ddr,sizeof(ddr))==DSL_OK);CHECK(h->writes==5690);
 CHECK(h->addresses[5686]==0x1fa30000+22744);CHECK(h->values[5686]==h->values[5685]);
 CHECK(h->addresses[5687]==0x1fb00f10&&h->values[5687]==22744);CHECK(h->values[5689]==0x66697368);
 memset(h,0,sizeof(*h));h->statuses[0]=0x57414445;h->statuses[1]=0x46574f4b;h->fail=3;
 CHECK(dsl_ddr_load(&io,ddr,sizeof(ddr))==DSL_E_IO);CHECK(h->writes==3); /* old guest incorrectly returned0 with independent FWOK */
 memset(h,0,sizeof(*h));h->statuses[0]=0x57414445;h->statuses[1]=0x4352464c;
 CHECK(dsl_ddr_load(&io,ddr,sizeof(ddr))==DSL_E_CRC);CHECK(h->values[h->writes-1]==0x444f4e45); /* no finish on CRC rejection */
 memset(h,0,sizeof(*h));CHECK(dsl_ddr_load(&io,ddr,sizeof(ddr))==DSL_E_TIMEOUT);CHECK(h->writes==0);
 memset(h,0,sizeof(*h));h->statuses[0]=0x57414445;h->drift=100;CHECK(dsl_ddr_load(&io,ddr,sizeof(ddr))==DSL_E_TIMEOUT);CHECK(h->writes<5686);
 memset(h,0,sizeof(*h));h->statuses[0]=0x57414445;h->cancel_at=20;CHECK(dsl_ddr_load(&io,ddr,sizeof(ddr))==DSL_E_CANCEL);CHECK(h->writes==20);
 memset(h,0,sizeof(*h));h->statuses[0]=h->statuses[1]=0x5244494e;
 CHECK(dsl_inic_load_known(&io,inic,sizeof(inic))==DSL_BLOCK_INIC_TRAILER);CHECK(h->writes==9893);
 CHECK(h->addresses[7683]==0x1fb00f04&&h->values[7683]==0x494e5345);
 for(unsigned i=0;i<h->writes;i++)CHECK(h->addresses[i]!=0x1fb00f0c&&!(h->addresses[i]==0x1fb00f04&&h->values[i]==0x494e444e));
 free(h);
}
int main(void)
{checksums();bridge();frames();sessions();stages();printf("DSL host contracts: %u assertions passed; no hardware operations\n",assertions);return 0;}
