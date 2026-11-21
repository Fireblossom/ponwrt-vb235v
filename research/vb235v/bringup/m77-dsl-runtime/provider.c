/* SPDX-License-Identifier: GPL-2.0-only */
#define _GNU_SOURCE
#include "provider.h"
#include <errno.h>
#include <fcntl.h>
#include <net/if.h>
#include <poll.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <linux/if_packet.h>

static int provider_ioctl(int fd,unsigned long request,void *argument)
{
 /* glibc takes unsigned long; musl intentionally declares an int request. */
#ifdef __GLIBC__
 return ioctl(fd,request,argument);
#else
 return ioctl(fd,(int)request,argument);
#endif
}

static uint64_t now_ms(void *unused)
{ struct timespec t;(void)unused;clock_gettime(CLOCK_BOOTTIME,&t);return (uint64_t)t.tv_sec*1000+(uint64_t)t.tv_nsec/1000000; }
static int wait_ms(void *unused,unsigned n)
{ struct timespec t={.tv_sec=n/1000,.tv_nsec=(long)(n%1000)*1000000};(void)unused;return nanosleep(&t,NULL); }
static int rd(void *ctx,uint32_t a,uint32_t *v)
{ struct dsl_provider *p=ctx;struct pndsl_word w={.address=a};if(provider_ioctl(p->fd,PNDSL_READ32,&w))return -1;*v=w.value;return 0; }
static int wr(void *ctx,uint32_t a,uint32_t v)
{ struct dsl_provider *p=ctx;struct pndsl_word w={.address=a,.value=v};return provider_ioctl(p->fd,PNDSL_WRITE32,&w); }
static int reset(void *ctx,bool assert)
{ struct dsl_provider *p=ctx;__u32 value=assert?1:0;return provider_ioctl(p->fd,PNDSL_RESET,&value); }
int dsl_provider_open(struct dsl_provider *p)
{
 memset(p,0,sizeof(*p));p->fd=open("/dev/ponwrt-dsl",O_RDWR|O_CLOEXEC|O_NOFOLLOW);
 if(p->fd<0)return DSL_E_OWNER;
 if(provider_ioctl(p->fd,PNDSL_QUERY,&p->query)||p->query.abi!=PNDSL_ABI||
    memcmp(p->query.profile,PNDSL_PROFILE,sizeof(PNDSL_PROFILE))) {
  close(p->fd);p->fd=-1;return DSL_E_OWNER;
 }
 return DSL_OK;
}
int dsl_provider_claim(struct dsl_provider *p,const struct pndsl_claim *claim,struct dsl_hw *h)
{
 if(p->fd<0||!claim||!h ||
   (p->query.flags&(PNDSL_F_BOARD_VERIFIED|PNDSL_F_OWNER_PRESENT))!=
   (PNDSL_F_BOARD_VERIFIED|PNDSL_F_OWNER_PRESENT))return DSL_E_OWNER;
 if(provider_ioctl(p->fd,PNDSL_CLAIM,(void *)claim))return DSL_E_OWNER;
 p->claimed=true;
 if(provider_ioctl(p->fd,PNDSL_QUERY,&p->query)||!(p->query.flags&PNDSL_F_CLAIMED)) {
  dsl_provider_release(p);return DSL_E_OWNER;
 }
 *h=(struct dsl_hw){.ctx=p,.exclusive=true,.profile_verified=true,.inputs_verified=true,
  .read32=rd,.write32=wr,.reset=reset,.now_ms=now_ms,.wait_ms=wait_ms};return DSL_OK;
}
int dsl_provider_release(struct dsl_provider *p)
{
 int ret=DSL_OK;
 if(p->fd>=0) {
  if(p->claimed&&provider_ioctl(p->fd,PNDSL_RELEASE,NULL))ret=DSL_E_IO;
  close(p->fd);
 }
 p->fd=-1;p->claimed=false;return ret;
}
int dsl_rom_serve(struct dsl_provider *p,struct dsl_rom_session *session,unsigned timeout_ms)
{
 if(!p||!session||!p->claimed||!p->query.ifindex ||
    !(p->query.flags&PNDSL_F_PEER_VERIFIED))return DSL_E_OWNER;
 if(!session->tail_verified||!(p->query.flags&PNDSL_F_ROM_TAIL_VERIFIED))return DSL_BLOCK_ROM_TAIL;
 /* Current provider never advertises unmeasured ROM-tail capability. */
 int fd=socket(AF_PACKET,SOCK_RAW|SOCK_CLOEXEC,htons(0xbeef));if(fd<0)return DSL_E_IO;
 struct sockaddr_ll address={.sll_family=AF_PACKET,.sll_protocol=htons(0xbeef),.sll_ifindex=(int)p->query.ifindex};
 int ret=DSL_E_IO;
 if(bind(fd,(struct sockaddr *)&address,sizeof(address)))goto done;
 struct ifreq req={0};
 if(!if_indextoname(p->query.ifindex,req.ifr_name)||ioctl(fd,SIOCGIFHWADDR,&req))goto done;
 uint64_t start=now_ms(NULL);
 for(;;) {
  uint64_t elapsed=now_ms(NULL)-start;if(elapsed>=timeout_ms){ret=DSL_E_TIMEOUT;break;}
  struct pollfd pollfd={.fd=fd,.events=POLLIN};
  int wait=(int)(timeout_ms-elapsed);if(wait>2000)wait=2000;
  int ready=poll(&pollfd,1,wait);if(ready<0){if(errno==EINTR)continue;break;}if(!ready)continue;
  uint8_t frame[1600],reply[DSL_ROM_CAPACITY+14];struct sockaddr_ll from={0};socklen_t flen=sizeof(from);
  ssize_t n=recvfrom(fd,frame,sizeof(frame),MSG_TRUNC,(struct sockaddr *)&from,&flen);
  if(n<0){if(errno==EINTR)continue;break;}
  if(n<46||n>(ssize_t)sizeof(frame)||from.sll_ifindex!=(int)p->query.ifindex||
     from.sll_pkttype==PACKET_OUTGOING||memcmp(frame+6,p->query.peer,6)||
     memcmp(frame,req.ifr_hwaddr.sa_data,6)||frame[12]!=0xbe||frame[13]!=0xef)continue;
  struct dsl_rom_packet packet;int e=dsl_rom_decode_ethernet(frame,(size_t)n,p->query.peer,(const uint8_t *)req.ifr_hwaddr.sa_data,&packet);
  if(e)continue; /* Malformed/unmatched traffic cannot refresh the stage deadline. */
  size_t reply_len=0;e=dsl_rom_handle(session,&packet,reply+14,sizeof(reply)-14,&reply_len);
  if(e){ret=e;break;}
  if(reply_len) {
   memcpy(reply,p->query.peer,6);memcpy(reply+6,req.ifr_hwaddr.sa_data,6);reply[12]=0xbe;reply[13]=0xef;
   address.sll_halen=6;memcpy(address.sll_addr,p->query.peer,6);
   ssize_t sent=sendto(fd,reply,reply_len+14,0,(struct sockaddr *)&address,sizeof(address));
   if(sent!=(ssize_t)(reply_len+14)){ret=DSL_E_IO;break;}
  }
 }
done:close(fd);return ret;
}
