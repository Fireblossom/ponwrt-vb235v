/* SPDX-License-Identifier: GPL-2.0-only */
#include "core.h"
#include <limits.h>
#include <string.h>

static uint16_t le16(const uint8_t *p) { return (uint16_t)(p[0]|p[1]<<8); }
static uint16_t be16(const uint8_t *p) { return (uint16_t)(p[0]<<8|p[1]); }
static uint32_t le32(const uint8_t *p) { return (uint32_t)le16(p)|((uint32_t)le16(p+2)<<16); }
static uint32_t be32(const uint8_t *p) { return (uint32_t)be16(p)<<16|be16(p+2); }
static void put16(uint8_t *p,uint16_t v) { p[0]=(uint8_t)(v>>8); p[1]=(uint8_t)v; }
static void put32(uint8_t *p,uint32_t v) { put16(p,(uint16_t)(v>>16)); put16(p+2,(uint16_t)v); }
static int gate(struct dsl_hw *h)
{
 return h && h->exclusive && h->profile_verified && h->inputs_verified &&
        h->read32 && h->write32 && h->reset && h->now_ms && h->wait_ms ? DSL_OK:DSL_E_OWNER;
}
const char *dsl_code(int e)
{
 switch(e) {
 case DSL_OK:return "OK"; case DSL_E_ARGUMENT:return "ARGUMENT_INVALID";
 case DSL_E_IO:return "PROVIDER_IO_FAILED"; case DSL_E_TIMEOUT:return "STAGE_TIMEOUT";
 case DSL_E_CANCEL:return "CANCELLED"; case DSL_E_FRAME:return "FRAME_REJECTED";
 case DSL_E_CHECKSUM:return "CHECKSUM_REJECTED"; case DSL_E_SEQUENCE:return "SEQUENCE_REJECTED";
 case DSL_E_FIRMWARE:return "FIRMWARE_REJECTED"; case DSL_E_OWNER:return "OWNER_UNVERIFIED";
 case DSL_BLOCK_INIC_TRAILER:return "INIC_TRAILER_UNVERIFIED";
 case DSL_BLOCK_EXEC_ACK:return "EXEC_ACK_UNVERIFIED";
 case DSL_BLOCK_ROM_TAIL:return "ROM_TAIL_UNVERIFIED";
 case DSL_E_CRC:return "ENDPOINT_CRC_REJECTED"; default:return "INTERNAL_ERROR";
 }
}
int dsl_bridge_write32(struct dsl_c22 *b,uint32_t a,uint32_t v)
{
 const unsigned regs[]={1,2,3,4,0};
 uint16_t vals[]={(uint16_t)a,(uint16_t)(a>>16),(uint16_t)v,(uint16_t)(v>>16),0xff};
 if(!b||!b->write) return DSL_E_ARGUMENT;
 for(unsigned i=0;i<5;i++) if(b->write(b->ctx,regs[i],vals[i])) return DSL_E_IO;
 return DSL_OK;
}
int dsl_bridge_read32(struct dsl_c22 *b,uint32_t a,uint32_t *out)
{
 uint16_t lo=0,hi=0; int e;
 if(!b||!b->read||!b->write||!out) return DSL_E_ARGUMENT;
 *out=0;
 e=dsl_bridge_write32(b,0x1fa20160,0);
 if(!e && (b->write(b->ctx,1,(uint16_t)a)||b->write(b->ctx,2,(uint16_t)(a>>16))||
           b->write(b->ctx,0,0xf0)||b->read(b->ctx,3,&lo)||b->read(b->ctx,4,&hi))) e=DSL_E_IO;
 /* Always attempt gate restoration; never mask an earlier failure. */
 int restore=dsl_bridge_write32(b,0x1fa20160,0x800);
 if(!e) e=restore;
 if(!e) *out=(uint32_t)lo|((uint32_t)hi<<16);
 return e;
}
static int cancelled(struct dsl_hw *h)
{ return h->cancelled && h->cancelled(h->ctx) ? DSL_E_CANCEL:DSL_OK; }
static int write_checked(struct dsl_hw *h,uint32_t a,uint32_t v)
{ int e=cancelled(h); return e?e:(h->write32(h->ctx,a,v)?DSL_E_IO:DSL_OK); }
int dsl_endpoint_prepare(struct dsl_hw *h)
{
 int e=gate(h);uint32_t value;if(e)return e;
 if(h->reset(h->ctx,true))return DSL_E_IO;
 if(h->wait_ms(h->ctx,1000)||cancelled(h))return DSL_E_CANCEL;
 if(h->reset(h->ctx,false))return DSL_E_IO;
 if(h->read32(h->ctx,0x1fb0009c,&value))return DSL_E_IO;
 if(!(value&1))return DSL_OK;
 if(h->read32(h->ctx,0x1fb0005c,&value))return DSL_E_IO;
 if(value!=1)return DSL_OK;
 if(h->read32(h->ctx,0x1fa20174,&value))return DSL_E_IO;
 if((e=write_checked(h,0x1fa20190,0x12)))return e;
 if(value&0x10000){
  const uint32_t values[]={0x05001f08,0x05001f0a,0x05001f0e};
  for(unsigned i=0;i<3;i++)if((e=write_checked(h,0x1fa201f8,values[i])))return e;
  if((e=write_checked(h,0x1fa20208,0x03000000)))return e;
 }else if((e=write_checked(h,0x1fa2020c,0x04000000)))return e;
 return write_checked(h,0x1fa20204,0x402);
}
static int poll_word(struct dsl_hw *h,uint64_t start,unsigned timeout,uint32_t want,bool crc)
{
 for(;;) {
  uint32_t value=0; int e=cancelled(h); if(e) return e;
  if(h->now_ms(h->ctx)-start>=timeout) return DSL_E_TIMEOUT;
  if(h->read32(h->ctx,0x1fb00f00,&value)) return DSL_E_IO;
  if(crc && value==0x4352464c) return DSL_E_CRC;
  if(value==want || (crc && value==0x4e4f4352)) return DSL_OK;
  if(h->wait_ms(h->ctx,1)) return DSL_E_CANCEL;
 }
}
int dsl_ddr_load(struct dsl_hw *h,const uint8_t *data,size_t n)
{
 int e=gate(h); if(e) return e;
 if(!data||n!=22744||n%4) return DSL_E_FIRMWARE;
 uint64_t start=h->now_ms(h->ctx);
 if((e=poll_word(h,start,10000,0x57414445,false))) return e;
 for(size_t i=0;i<n;i+=4) {
  if(h->now_ms(h->ctx)-start>=10000)return DSL_E_TIMEOUT;
  if((e=write_checked(h,0x1fa30000+(uint32_t)i,le32(data+i)))) return e;
 }
 /* Exact pinned OEM loop writes one stale final word after aligned EOF. */
 if((e=write_checked(h,0x1fa30000+(uint32_t)n,le32(data+n-4)))) return e;
 if((e=write_checked(h,0x1fb00f10,(uint32_t)n))) return e;
 if((e=write_checked(h,0x1fb00f04,0x444f4e45))) return e;
 if((e=poll_word(h,start,10000,0x46574f4b,true))) return e;
 return write_checked(h,0x1fb00f04,0x66697368);
}
int dsl_inic_load_known(struct dsl_hw *h,const uint8_t *data,size_t n)
{
 int e=gate(h); if(e) return e;
 if(!data||n!=39556||n%4) return DSL_E_FIRMWARE;
 uint64_t start=h->now_ms(h->ctx); size_t at=0;
 while(at<n) {
  if((e=poll_word(h,start,20000,0x5244494e,false))) return e;
  size_t count=n-at; if(count>0x7800) count=0x7800;
  for(size_t i=0;i<count;i+=4) {
   if(h->now_ms(h->ctx)-start>=20000)return DSL_E_TIMEOUT;
   if((e=write_checked(h,0x1fa40000+(uint32_t)i,le32(data+at+i)))) return e;
  }
  at+=count;
  /* Unresolved trailer must be blocked BEFORE emitting CONF/MAC/INDN. */
  if(count<0x7800) return DSL_BLOCK_INIC_TRAILER;
  if((e=write_checked(h,0x1fb00f14,0x1000000))) return e;
  if((e=write_checked(h,0x1fb00f00,0))) return e;
  if((e=write_checked(h,0x1fb00f10,(uint32_t)at))) return e;
  if((e=write_checked(h,0x1fb00f04,0x494e5345))) return e;
 }
 return DSL_BLOCK_INIC_TRAILER;
}
uint16_t dsl_checksum(const uint8_t *p,size_t n)
{
 if(!p||n>8192) return 0xffff;
 uint32_t s=0;
 while(n>=2) { s+=le16(p);p+=2;n-=2; }
 if(n) s+=*p;
 s=(s&0xffff)+(s>>16);s+=s>>16;
 return (uint16_t)~s;
}
/* Defined arithmetic shift, avoiding implementation-defined signed shifts. */
static uint32_t asr16(uint32_t s) { return (s>>16)|(s&0x80000000?0xffff0000u:0); }
uint16_t dsl_file_checksum(const uint8_t *p,size_t n)
{
 uint32_t s=0;
 while(n>=2) { s+=le16(p);p+=2;n-=2; }
 if(n) s+=*p;
 s=(s&0xffff)+asr16(s);s+=asr16(s);
 return (uint16_t)~s;
}
int dsl_rom_encode(uint8_t *out,size_t cap,const struct dsl_rom_fields *f,
 const uint8_t *data,size_t n,const uint8_t tail[2],size_t *length)
{
 if(length)*length=0;
 if(!out||!f||!tail||!length||(!data&&n)||n>DSL_ROM_BLOCK||cap<n+34) return DSL_E_ARGUMENT;
 memset(out,0,32);put32(out,0x31623162);put16(out+4,f->op);put16(out+8,(uint16_t)n);
 put16(out+12,f->seq);out[14]=(uint8_t)f->file_sum;out[15]=(uint8_t)(f->file_sum>>8);
 put16(out+16,f->arg5);put32(out+20,f->arg6);put32(out+24,f->arg7);
 if(n) memcpy(out+32,data,n);
 uint16_t sum=dsl_checksum(out,32+n);out[10]=(uint8_t)sum;out[11]=(uint8_t)(sum>>8);
 memcpy(out+32+n,tail,2);*length=n+34;return DSL_OK;
}
int dsl_rom_decode(const uint8_t *p,size_t n,struct dsl_rom_packet *packet)
{
 if(packet)memset(packet,0,sizeof(*packet));
 if(!p||!packet||n<32||be32(p)!=0x31623162) return DSL_E_FRAME;
 size_t count=be16(p+8), logical=32+count;
 if(count>DSL_ROM_BLOCK||logical>n) return DSL_E_FRAME;
 /* Allow exactly logical, OEM two-byte tail, or Ethernet minimum padding. */
 if(n!=logical && n!=logical+2 && !(n==46 && logical<=46)) return DSL_E_FRAME;
 if(be16(p+6)||be16(p+16)||be16(p+18)||be32(p+20)||be32(p+24)||be32(p+28)) return DSL_E_FRAME;
 /* Zero-checksum bypass is deliberately not inherited. */
 if(!le16(p+10)||dsl_checksum(p,logical)) return DSL_E_CHECKSUM;
 uint16_t op=be16(p+4);
 if(op!=1&&op!=3&&op!=6) return DSL_E_FRAME;
 packet->op=op;packet->seq=be16(p+12);packet->data=p+32;packet->length=count;
 return DSL_OK;
}
int dsl_rom_decode_ethernet(const uint8_t *frame,size_t n,const uint8_t src[6],
 const uint8_t dst[6],struct dsl_rom_packet *packet)
{
 if(packet)memset(packet,0,sizeof(*packet));
 if(!frame||!src||!dst||n<46||n>1518||memcmp(frame+6,src,6)||memcmp(frame,dst,6)||
    frame[12]!=0xbe||frame[13]!=0xef)return DSL_E_FRAME;
 return dsl_rom_decode(frame+14,n-14,packet);
}
void dsl_rom_init(struct dsl_rom_session *s,const uint8_t *file,size_t n,const uint8_t id[6])
{
 if(!s)return;
 memset(s,0,sizeof(*s));if(!file||!n)return;
 s->file=file;s->file_len=n;s->file_sum=dsl_file_checksum(file,n);
 if(id) memcpy(s->identity,id,6);
 /* tail_verified remains false: independent endpoint evidence is required. */
}
static int data_reply(struct dsl_rom_session *s,size_t offset,uint16_t seq,
 uint8_t *out,size_t cap,size_t *n)
{
 if(offset>s->file_len) return DSL_E_SEQUENCE;
 size_t count=s->file_len-offset;if(count>1400) count=1400;
 struct dsl_rom_fields f={.op=5,.seq=seq,.file_sum=s->file_sum};
 int e=dsl_rom_encode(out,cap,&f,s->file+offset,count,s->tail,n);
 if(!e) { s->last_len=count;s->last_seq=seq; }
 return e;
}
int dsl_rom_handle(struct dsl_rom_session *s,const struct dsl_rom_packet *p,
 uint8_t *out,size_t cap,size_t *n)
{
 if(n)*n=0;
 if(!s||!p||!out||!n||!s->file||!s->file_len||s->file_len>4214743) return DSL_E_ARGUMENT;
 *n=0;if(!s->tail_verified) return DSL_BLOCK_ROM_TAIL;
 if(s->phase==0) {
  if(p->op!=1||p->length||p->seq) return DSL_E_SEQUENCE;
  struct dsl_rom_fields f={.op=2};int e=dsl_rom_encode(out,cap,&f,s->identity,6,s->tail,n);
  if(!e) s->phase=1;
  return e;
 }
 if(s->phase==1) {
  static const uint8_t file[]="tclinux.bin";
  if(p->op!=3||p->seq||p->length!=sizeof(file)||memcmp(p->data,file,sizeof(file))) return DSL_E_SEQUENCE;
  int e=data_reply(s,0,1,out,cap,n);if(!e)s->phase=2;return e;
 }
 if(s->phase!=2||p->op!=6||p->length) return DSL_E_SEQUENCE;
 if(p->seq!=s->last_seq) {
  /* The original seeks ACK*n for every ACK. Reproduce only the one-block
   * duplicate window, with bounded retransmission and no state advancement. */
  if(!s->ack_seen||p->seq!=s->last_ack||s->duplicate_acks>=3)return DSL_E_SEQUENCE;
  s->duplicate_acks++;
  return data_reply(s,(size_t)s->last_ack*1400,s->last_seq,out,cap,n);
 }
 s->last_ack=p->seq;s->ack_seen=true;s->duplicate_acks=0;
 size_t offset=(size_t)s->last_seq*1400;
 if(s->last_len<1400) { s->phase=3;return DSL_BLOCK_EXEC_ACK; }
 if(s->last_seq==UINT16_MAX) return DSL_E_SEQUENCE;
 if(offset>s->file_len) return DSL_E_SEQUENCE;
 return data_reply(s,offset,(uint16_t)(s->last_seq+1),out,cap,n);
}
