// SPDX-License-Identifier: GPL-2.0-only
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <errno.h>
#include <linux/ethtool.h>
#include <linux/if_packet.h>
#include <linux/sockios.h>
#include <net/if.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/random.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>
#define FRAME 1514
#define ROUNDS 10000
#define ETHERTYPE_TEST 0x88b5
struct port { int fd,index; unsigned char mac[6]; unsigned speed; };
static double now(void) { struct timespec t;clock_gettime(CLOCK_MONOTONIC,&t);return t.tv_sec+t.tv_nsec/1e9; }
static void die(const char *s) { perror(s);exit(1); }
static struct port open_port(const char *name)
{
	struct port p={.fd=-1};struct ifreq req={0};struct ethtool_cmd cmd={.cmd=ETHTOOL_GSET};
	int control=socket(AF_INET,SOCK_DGRAM,0);if(control<0)die("control socket");
	if(strlen(name)>=IFNAMSIZ)exit(2);
	strcpy(req.ifr_name,name);
	if(ioctl(control,SIOCGIFINDEX,&req))die("ifindex");
	p.index=req.ifr_ifindex;
	if(ioctl(control,SIOCGIFHWADDR,&req))die("MAC read");
	memcpy(p.mac,req.ifr_hwaddr.sa_data,6);
	req.ifr_data=(void *)&cmd;if(ioctl(control,SIOCETHTOOL,&req))die("link settings");
	p.speed=ethtool_cmd_speed(&cmd);
	if(p.speed!=2500 || cmd.duplex!=DUPLEX_FULL){fprintf(stderr,"Expected 2500 Mbps full duplex on %s\n",name);exit(1);}
	close(control);
	p.fd=socket(AF_PACKET,SOCK_RAW,htons(ETHERTYPE_TEST));if(p.fd<0)die("packet socket");
	struct sockaddr_ll address={.sll_family=AF_PACKET,.sll_protocol=htons(ETHERTYPE_TEST),.sll_ifindex=p.index};
	if(bind(p.fd,(void *)&address,sizeof(address)))die("packet bind");
#ifdef PACKET_IGNORE_OUTGOING
	int yes=1;if(setsockopt(p.fd,SOL_PACKET,PACKET_IGNORE_OUTGOING,&yes,sizeof(yes)))die("ignore outgoing");
#endif
	return p;
}
static void transmit(struct port p,const unsigned char *frame)
{
	struct sockaddr_ll address={.sll_family=AF_PACKET,.sll_protocol=htons(ETHERTYPE_TEST),.sll_ifindex=p.index,.sll_halen=6};
	memcpy(address.sll_addr,frame,6);
	if(sendto(p.fd,frame,FRAME,0,(void *)&address,sizeof(address))!=FRAME)die("send frame");
}
static void receive(struct port p,const unsigned char *expected)
{
	unsigned char got[2048];double end=now()+2.0;
	while(now()<end){
		int timeout=(int)((end-now())*1000);if(timeout<=0)break;
		struct pollfd fd={.fd=p.fd,.events=POLLIN};int ret=poll(&fd,1,timeout);
		if(ret<0){if(errno==EINTR)continue;die("poll");}if(!ret)break;
		struct sockaddr_ll peer;socklen_t n=sizeof(peer);
		ssize_t size=recvfrom(p.fd,got,sizeof(got),0,(void *)&peer,&n);
		if(size<0)die("receive frame");
		if(peer.sll_pkttype==PACKET_OUTGOING)continue;
		if(size<34||memcmp(got+14,expected+14,16))continue;
		if(size!=FRAME||memcmp(got,expected,FRAME)){fprintf(stderr,"Wire frame integrity mismatch\n");exit(1);}
		if(peer.sll_ifindex!=p.index){fprintf(stderr,"Wrong receive port\n");exit(1);}return;
	}
	fprintf(stderr,"Timed out waiting for the frame on the other physical port\n");exit(1);
}
int main(int argc,char **argv)
{
	if(argc!=3||!strcmp(argv[1],argv[2]))return 2;
	FILE *f=fopen("/tmp/sysinfo/board_name","r");char board[96]={0};
        if(!f||!fgets(board,sizeof(board),f))return 2;
        fclose(f);
	if(strcmp(board,"tplink,vb235v-ram-multigig-development\n")){fprintf(stderr,"Wrong RAM development board\n");return 2;}
	struct port a=open_port(argv[1]),b=open_port(argv[2]);
	if(a.index==b.index||!memcmp(a.mac,b.mac,6))return 2;
	unsigned char frame[FRAME],reply[FRAME],nonce[16];
	if(getrandom(nonce,sizeof(nonce),0)!=(ssize_t)sizeof(nonce))die("nonce");
	memcpy(frame,b.mac,6);memcpy(frame+6,a.mac,6);frame[12]=0x88;frame[13]=0xb5;memcpy(frame+14,nonce,16);
	for(unsigned i=34;i<FRAME;i++)frame[i]=(i*29+i/7)&255;
	double started=now();
	for(uint32_t seq=0;seq<ROUNDS;seq++){
		uint32_t wire=htonl(seq);memcpy(frame+30,&wire,4);transmit(a,frame);receive(b,frame);
		memcpy(reply,frame,FRAME);memcpy(reply,a.mac,6);memcpy(reply+6,b.mac,6);transmit(b,reply);receive(a,reply);
	}
	printf("{\"complete\":true,\"port_A_Mbps\":%u,\"port_B_Mbps\":%u,\"round_trips\":%u,\"frames_each_direction\":%u,\"bytes_each_direction\":%u,\"all_frame_bytes_verified\":true,\"seconds\":%.3f}\n",a.speed,b.speed,ROUNDS,ROUNDS,FRAME*ROUNDS,now()-started);
	close(a.fd);close(b.fd);return 0;
}
