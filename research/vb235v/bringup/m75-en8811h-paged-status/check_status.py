#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise the actual status callback with paged MDIO and injected errors."""
import argparse,json,re,subprocess,tempfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();s=a.source.read_text()
m=re.search(r'static int en8811h_read_status\([^;]+?\)\s*\{',s);assert m
end=m.end();depth=1
while depth:depth+=(s[end]=='{')-(s[end]=='}');end+=1
fixed=s[m.start():end]
call='phy_read_paged(phydev, AIR_PHY_PAGE_STANDARD,\n\t\t\t     AIR_AUX_CTRL_STATUS)'
assert fixed.count(call)==1
old=fixed.replace('en8811h_read_status','old_status').replace(call,'phy_read(phydev, AIR_AUX_CTRL_STATUS)')
code=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
typedef uint32_t u32;
#define MASTER_SLAVE_CFG_UNSUPPORTED 0
#define MASTER_SLAVE_STATE_UNSUPPORTED 0
#define SPEED_UNKNOWN -1
#define DUPLEX_UNKNOWN 255
#define DUPLEX_FULL 1
#define SPEED_100 100
#define SPEED_1000 1000
#define SPEED_2500 2500
#define RATE_MATCH_PAUSE 1
#define EN8811H_2P5G_LPA 0x3b30
#define EN8811H_2P5G_LPA_2P5G 1
#define ETHTOOL_LINK_MODE_2500baseT_Full_BIT 0
#define AIR_PHY_PAGE_STANDARD 0
#define AIR_AUX_CTRL_STATUS 0x1d
#define AIR_AUX_CTRL_STATUS_SPEED_MASK 0x1c
#define AIR_AUX_CTRL_STATUS_SPEED_100 4
#define AIR_AUX_CTRL_STATUS_SPEED_1000 8
#define AIR_AUX_CTRL_STATUS_SPEED_2500 12
struct en8811h_priv {u32 firmware_version;};
struct phy_device {void *priv;int master_slave_get,master_slave_state,speed,duplex,pause,asym_pause,rate_matching;bool link,autoneg_complete;unsigned long lp_advertising[1];};
static unsigned page,paged_calls;
static int aux,error;
static int genphy_update_link(struct phy_device *p){return 0;}
static int genphy_read_master_slave(struct phy_device *p){return 0;}
static int genphy_read_lpa(struct phy_device *p){return 0;}
static int air_buckpbus_reg_read(struct phy_device *p,u32 a,u32 *v){*v=0;return 0;}
static void linkmode_mod_bit(unsigned b,unsigned long *p,bool v){}
static void phy_resolve_aneg_pause(struct phy_device *p){}
static int phy_read(struct phy_device *p,unsigned reg){assert(reg==0x1d);return error?error:(page?0:aux);}
static int phy_read_paged(struct phy_device *p,unsigned selected,unsigned reg){unsigned saved=page;page=selected;paged_calls++;int ret=phy_read(p,reg);page=saved;return ret;}
'''+old+'\n'+fixed+r'''
int main(void){
 struct en8811h_priv priv={0x25062302};
 struct phy_device p={.priv=&priv,.link=true,.autoneg_complete=true};
 unsigned cases=0;
 page=4;aux=0x28;assert(!old_status(&p)&&p.speed==SPEED_UNKNOWN);cases++;
 for(unsigned saved=0;saved<32;saved++)for(unsigned i=0;i<3;i++){
  const int raw[]={0x24,0x28,0x2c},speed[]={100,1000,2500};
  page=saved;aux=raw[i];p.link=true;
  assert(!en8811h_read_status(&p));assert(p.speed==speed[i]&&p.duplex==DUPLEX_FULL);assert(page==saved);cases++;
 }
 for(unsigned saved=0;saved<32;saved++){
  page=saved;error=-5;p.link=true;
  assert(en8811h_read_status(&p)==-5&&p.speed==SPEED_UNKNOWN&&page==saved);cases++;
 }
 error=0;unsigned before=paged_calls;p.link=false;
 assert(!en8811h_read_status(&p)&&p.speed==SPEED_UNKNOWN&&paged_calls==before);cases++;
 printf("{\"complete\":true,\"cases\":%u,\"old_page4_unknown_reproduced\":true,\"all_32_prior_pages_preserved\":true,\"100_1000_2500_decoding_checked\":true,\"MDIO_error_propagation_checked\":true,\"ASAN_UBSAN\":true}\n",cases);
}
'''
with tempfile.TemporaryDirectory() as td:
 d=Path(td);(d/'check.c').write_text(code)
 subprocess.run(['cc','-O1','-g','-fsanitize=address,undefined',str(d/'check.c'),'-o',str(d/'check')],check=True)
 result=subprocess.check_output([str(d/'check')],text=True)
 a.output.write_text(json.dumps(json.loads(result),indent=2)+'\n');print(result,end='')
