#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read the exact M73 normal U-Boot network config and compiled control DT."""
import argparse,hashlib,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'tools'))
from fdt_board_inventory import parse
def main():
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('build',type=Path);a=p.parse_args()
 cfg=(a.build/'.config').read_text();n,_=parse((a.build/'u-boot.dtb').read_bytes())
 root='/soc/ethernet@1fb50000';first=n[root+'/ethernet@1'];second=n[root+'/ethernet@2'];third=n[root+'/ethernet@3']
 assert 'CONFIG_DEFAULT_DEVICE_TREE="an7583-vb235v-recovery"' in cfg
 assert 'CONFIG_AIROHA_ETH=y\n' in cfg and '# CONFIG_PHY_AIROHA is not set\n' in cfg
 assert n['/aliases']['ethernet0']==(root+'/ethernet@1\0').encode()
 assert first['status']==b'okay\0' and first['phy-mode']==b'internal\0'
 assert second['status']==third['status']==b'disabled\0'
 rows={}
 for prefix,base,names in [('source',a.source,['arch/arm/dts/an7583-vb235v-recovery.dts','drivers/net/airoha_eth.c']),('build',a.build,['.config','u-boot.dtb'])]:
  for name in names:rows[prefix+'/'+name]=hashlib.sha256((base/name).read_bytes()).hexdigest()
 result={'schema':1,'artifact_sha256':rows,'control_DT_ethernet0':root+'/ethernet@1','gdm1':{'status':'okay','phy_mode':'internal','fixed_link_Mbps':int.from_bytes(n[root+'/ethernet@1/fixed-link']['speed'],'big')},'gdm2':{'status':'disabled'},'gdm3':{'status':'disabled'},'Airoha_PHY_driver_built':False,'current_external_EN8811H_port_management_supported':False,'previous_integrated_switch_1G_LAN_recovery_network_qualified_separately':True,'device_accessed':False}
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
