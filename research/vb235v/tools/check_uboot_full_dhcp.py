# SPDX-License-Identifier: GPL-2.0-only
"""Exercise actual recovery DHCP through upstream lwIP IPv4/UDP, no hardware."""
from pathlib import Path
import argparse,subprocess,tempfile
parser=argparse.ArgumentParser();parser.add_argument('--source',required=True);args=parser.parse_args()
src=Path(args.source).resolve();lw=src/'lib/lwip/lwip/src'
opts=r'''
#define NO_SYS 1
#define SYS_LIGHTWEIGHT_PROT 0
#define MEM_LIBC_MALLOC 1
#define MEMP_MEM_MALLOC 1
#define LWIP_IPV4 1
#define LWIP_IPV6 0
#define LWIP_TCP 0
#define LWIP_RAW 0
#define LWIP_UDP 1
#define LWIP_DHCP 1
#define LWIP_DHCP_DOES_ACD_CHECK 0
#define LWIP_AUTOIP 0
#define LWIP_DNS 0
#define LWIP_IGMP 0
#define LWIP_NETCONN 0
#define LWIP_SOCKET 0
#define LWIP_STATS 0
#define LWIP_NETIF_HOSTNAME 0
#define LWIP_ARP 0
'''
common=r'''
#ifndef VB_NATIVE_COMMON
#define VB_NATIVE_COMMON
#include <stdio.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <stddef.h>
#include <errno.h>
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef uint64_t u64;
typedef unsigned long ulong;
#define __packed __attribute__((packed))
#define ARRAY_SIZE(x) (sizeof(x)/sizeof((x)[0]))
#define max_t(t,a,b) ((t)(a)>(t)(b)?(t)(a):(t)(b))
#define CONFIG_HTTPD_DHCP_POOL_START 2
#define CONFIG_HTTPD_DHCP_POOL_END 2
static ulong ticks;
static ulong get_timer(ulong base){return ticks-base;}
static const char *env_get(const char *key){return NULL;}
static int env_get_yesno(const char *key){return -1;}
#endif
'''
main=r'''
#include "common.h"
#include "lwip/init.h"
#include "lwip/ip4.h"
#include "lwip/inet_chksum.h"
#include "server.c"
static unsigned char last[2048];static unsigned last_len,replies,cases,checks;
#define CHECK(x) do{checks++;if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
#define CASE() do{cases++;}while(0)
u32_t sys_now(void){return ticks;}
static err_t capture(struct netif *n,struct pbuf *p,const ip4_addr_t *ip){
 CHECK(p->tot_len<=sizeof(last));last_len=p->tot_len;
 CHECK(pbuf_copy_partial(p,last,p->tot_len,0)==p->tot_len);replies++;return ERR_OK;
}
static err_t init_if(struct netif *n){n->output=capture;n->mtu=1500;n->flags=NETIF_FLAG_BROADCAST;return ERR_OK;}
static void send_request(struct netif *n,int kind,int port,u32 requested,int bad_cookie,int short_options){
 unsigned char raw[328]={0};struct dhcp_packet *d=(void*)(raw+28);
 raw[0]=0x45;raw[2]=sizeof(raw)>>8;raw[3]=sizeof(raw)&255;raw[8]=64;raw[9]=17;
 memset(raw+16,255,4);u16_t checksum=inet_chksum(raw,20);memcpy(raw+10,&checksum,2);
 raw[20]=port>>8;raw[21]=port;raw[23]=67;raw[24]=300>>8;raw[25]=300&255;
 d->op=1;d->htype=1;d->hlen=6;d->xid=PP_HTONL(0x12345678);d->flags=PP_HTONS(0x8000);
 d->chaddr[0]=2;d->chaddr[5]=1;d->cookie=PP_HTONL(bad_cookie?0:DHCP_MAGIC_COOKIE);
 u8 *o=d->options;u8 k=kind;o=dhcp_add_option(o,53,&k,1);
 if(requested){u32 value=PP_HTONL(requested);o=dhcp_add_option(o,50,&value,4);}
 if(short_options){*o++=54;*o++=255;}else *o++=255;
 struct pbuf *p=pbuf_alloc(PBUF_RAW,sizeof(raw),PBUF_RAM);CHECK(p);CHECK(pbuf_take(p,raw,sizeof(raw))==ERR_OK);
 CHECK(ip4_input(p,n)==ERR_OK);
}
static void check_reply(unsigned kind,bool offered){
 CHECK(last_len==328);CHECK(last[0]==0x45&&last[9]==17);CHECK(inet_chksum(last,20)==0);
 CHECK(last[20]==0&&last[21]==67&&last[22]==0&&last[23]==68);
 CHECK(!memcmp(last+16,"\xff\xff\xff\xff",4));
 struct dhcp_packet *d=(void*)(last+28);struct dhcp_options o;
 CHECK(d->op==2&&d->xid==PP_HTONL(0x12345678));CHECK(d->yiaddr==(offered?PP_HTONL(0xc0a80102):0));
 CHECK(dhcp_parse_options(d,300,&o)==0&&o.type==kind);CHECK(o.server==PP_HTONL(0xc0a80101));
}
int main(void){
 struct netif n={0};ip4_addr_t ip,mask,gw;
 lwip_init();IP4_ADDR(&ip,192,168,1,1);IP4_ADDR(&mask,255,255,255,0);ip4_addr_set_zero(&gw);
 CHECK(netif_add(&n,&ip,&mask,&gw,NULL,init_if,ip4_input));netif_set_default(&n);netif_set_up(&n);netif_set_link_up(&n);
 CHECK(!uboot_httpd_dhcp_start(&n));
 CASE();send_request(&n,1,68,0,0,0);CHECK(replies==1);check_reply(DHCP_OFFER,true);
 CASE();send_request(&n,3,68,0xc0a80102,0,0);CHECK(replies==2);check_reply(DHCP_ACK,true);
 CASE();send_request(&n,3,68,0xc0a80202,0,0);CHECK(replies==3);check_reply(DHCP_NAK,false);
 CASE();send_request(&n,1,1068,0,0,0);CHECK(replies==3);
 CASE();send_request(&n,1,68,0,1,0);CHECK(replies==3);
 CASE();send_request(&n,1,68,0,0,1);CHECK(replies==3);
 CASE();send_request(&n,7,68,0,0,0);CHECK(replies==3);
 CASE();send_request(&n,1,68,0,0,0);CHECK(replies==4);check_reply(DHCP_OFFER,true);
 uboot_httpd_dhcp_stop();netif_remove(&n);
 printf("RESULT cases=%u assertions=%u; actual lwIP IPv4/UDP DHCP OFFER/ACK/NAK verified\n",cases,checks);return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='vb235v-dhcp-') as directory:
 p=Path(directory)
 for name,data in {'lwipopts.h':opts,'common.h':common,'arch/cc.h':'#include <stdint.h>\n#include <stdlib.h>\n#include <stdio.h>\n#define LWIP_PLATFORM_DIAG(x) do{printf x;}while(0)\n#define LWIP_PLATFORM_ASSERT(x) do{fprintf(stderr,"%s\\n",x);abort();}while(0)\n','env.h':'#include "common.h"\n','time.h':'#include_next <time.h>\n#include "common.h"\n','linux/errno.h':'#define EINVAL 22\n#define ENOMEM 12\n#define EADDRINUSE 98\n','linux/kernel.h':'#include "common.h"\n','net/httpd.h':'#include "common.h"\nstruct netif;\nvoid uboot_httpd_dhcp_stop(void);\n','main.c':main,'server.c':(src/'net/lwip/httpd-dhcp.c').read_text()}.items():
  f=p/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(data)
 sources=sorted((lw/'core').glob('*.c'))+sorted((lw/'core/ipv4').glob('*.c'))
 cmd=['cc','-std=gnu11','-O1','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I',str(p),'-I',str(lw/'include'),str(p/'main.c'),*map(str,sources),'-o',str(p/'check')]
 r=subprocess.run(cmd,capture_output=True,text=True)
 if r.returncode:raise RuntimeError(r.stderr[-6500:])
 r=subprocess.run([str(p/'check')],capture_output=True,text=True)
 if r.returncode:raise RuntimeError(r.stdout[-2000:]+r.stderr[-6500:])
 print(r.stdout)
