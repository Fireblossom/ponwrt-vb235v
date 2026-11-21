/* SPDX-License-Identifier: GPL-2.0-only */
#define _GNU_SOURCE
#include <errno.h>
#include <linux/ethtool.h>
#include <linux/mii.h>
#include <linux/sockios.h>
#include <net/if.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <unistd.h>
int main(int argc,char **argv)
{
	struct ifreq ifr={0};
	struct { struct ethtool_link_settings settings; uint32_t masks[3*127]; } ls={0};
	int fd,n;
	if(argc!=2||strlen(argv[1])>=IFNAMSIZ) return 2;
	strcpy(ifr.ifr_name,argv[1]);
	fd=socket(AF_INET,SOCK_DGRAM,0);
	if(fd<0) return 2;
	ls.settings.cmd=ETHTOOL_GLINKSETTINGS; ifr.ifr_data=(void *)&ls;
	if(ioctl(fd,SIOCETHTOOL,&ifr)<0) { perror("link settings size");return 1; }
	n=-ls.settings.link_mode_masks_nwords;
	if(n<=0||n>127) return 1;
	ls.settings.link_mode_masks_nwords=n;
	if(ioctl(fd,SIOCETHTOOL,&ifr)<0) { perror("link settings");return 1; }
	printf("{\"interface\":\"%s\",\"speed_Mbps\":%u,\"duplex\":%u,\"autoneg\":%u,\"mask_words\":%d,\"supported\":[",argv[1],ls.settings.speed,ls.settings.duplex,ls.settings.autoneg,n);
	for(int k=0;k<3;k++) {
		if(k) printf("],\"%s\":[",k==1?"advertising":"partner_advertising");
		for(int i=0;i<n;i++) printf("%s%u",i?",":"",ls.masks[k*n+i]);
	}
	printf("],\"mii_registers\":{");
	struct mii_ioctl_data *mii=(void *)&ifr.ifr_data;
	memset(&ifr.ifr_ifru,0,sizeof(ifr.ifr_ifru));
	int first=1;
	if(ioctl(fd,SIOCGMIIPHY,&ifr)==0) {
		static const int regs[]={0,1,2,3,4,5,9,10,15};
		for(unsigned i=0;i<sizeof(regs)/sizeof(regs[0]);i++) {
			mii->reg_num=regs[i];
			if(ioctl(fd,SIOCGMIIREG,&ifr)==0) {
				printf("%s\"%d\":%u",first?"":",",regs[i],mii->val_out);first=0;
			}
		}
	}
	printf("}}\n");close(fd);return 0;
}
