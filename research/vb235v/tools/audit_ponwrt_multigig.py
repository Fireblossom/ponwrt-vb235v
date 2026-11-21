#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Admit exactly the two discovered EN8811H PHYs and their candidate PCS paths."""
import argparse,copy,hashlib,json
from pathlib import Path
from audit_ponwrt_accel import audit_accel_dtb_nodes,ACCEL_BOARD
from audit_ponwrt_lan import audit_lan_config
from audit_ponwrt_ram import audit_fit,cells,require,MAX_FIT
from fdt_board_inventory import parse
MULTIGIG_BOARD='tplink,vb235v-ram-multigig-development'
SOURCE=Path(__file__).resolve().parents[1]/'bringup/m71-dual-2p5g'

def audit_multigig_dtb(data):
    nodes,reserved=parse(data);base=copy.deepcopy(nodes)
    prefix=(MULTIGIG_BOARD+'\0').encode()
    require(base['/']['compatible'].startswith(prefix+(ACCEL_BOARD+'\0').encode()),'Incorrect multigig identity')
    base['/']['compatible']=base['/']['compatible'][len(prefix):]
    def h(path):
        value=nodes.get(path,{}).get('phandle');require(value is not None and len(value)==4,'Missing handle '+path);return value
    scu=h('/system-controller@1fb00000');mdio='/system-controller@1fb00000/mdio-bus@c8'
    layout='/efuse/nvmem-layout';eth='/ethernet@1fb50000'
    expected={}
    for path,reg,bits in [('pon-impedance-valid@4',[4,1],[5,1]),('pon-tx-term@f',[15,1],[5,2]),('pon-rx-impedance@f',[15,2],[7,2])]:
        expected[layout+'/'+path]={'reg':cells(*reg),'bits':cells(*bits)}
    for suffix in ['e','f']:
        expected[mdio+'/ethernet-phy@'+suffix]={'compatible':b'ethernet-phy-ieee802.3-c22\0','reg':cells(int(suffix,16)),'max-speed':cells(2500)}
    names=b'pcs_mac\0hsgmii_an\0hsgmii_pcs\0multi_sgmii\0usxgmii\0hsgmii_rate_adp\0pcs_ana\0pcs_pma\0'
    common_offsets=[(0,0x1000),(0,0x60),(0xa00,0x164),(0x4000,0x450),(0x5900,0x338),(0x6000,0x300),(0xf000,0x1000),(0xe000,0x1000)]
    for unit,analog,kind,resets in [(0x1fa08000,0x1fa80000,'pon',[48,0,15]),(0x1fa09000,0x1fa70000,'eth',[7,8])]:
        windows=[(unit,0x1000)]+[(analog+offset,size) for offset,size in common_offsets[1:]]
        props={'compatible':('airoha,an7583-pcs-'+kind+'\0').encode(),'reg':b''.join(cells(0,addr,0,size) for addr,size in windows),
         'reg-names':names,'resets':b''.join(scu+cells(i) for i in resets),
         'reset-names':b'mac\0phy\0xfi\0' if kind=='pon' else b'mac\0phy\0','airoha,scu':scu,'#pcs-cells':cells(0)}
        if kind=='pon':props.update({'airoha,pon-ethernet-mode':b'2500base-x\0',
          'nvmem-cells':b''.join(h(layout+'/'+p) for p in ['pon-impedance-valid@4','pon-tx-term@f','pon-rx-impedance@f']),
          'nvmem-cell-names':b'pon-impedance-valid\0pon-tx-term\0pon-rx-impedance\0'})
        expected['/pcs@'+format(unit,'x')]=props
    for i,phy,pcs in [(2,'e','1fa08000'),(3,'f','1fa09000')]:
        props={'compatible':b'airoha,eth-mac\0','reg':cells(i),'phy-mode':b'2500base-x\0',
         'pcs-handle':h('/pcs@'+pcs),'phy-handle':h(mdio+'/ethernet-phy@'+phy)}
        if i==3:props['airoha,gdm-srcport']=cells(0x16)
        expected[eth+'/ethernet@'+str(i)]=props
    for path,props in expected.items():
        actual=base.pop(path,None)
        require(actual is not None and {k:v for k,v in actual.items() if k not in ['phandle','linux,phandle']}==props,'Incorrect multigig resources: '+path)
    symbols={'pcs_wan':'/pcs@1fa08000','pcs_lan':'/pcs@1fa09000','pon_valid':layout+'/pon-impedance-valid@4',
     'pon_tx_term':layout+'/pon-tx-term@f','pon_rx_imp':layout+'/pon-rx-impedance@f',
     'phy_wan':mdio+'/ethernet-phy@e','phy_lan':mdio+'/ethernet-phy@f','gdm2':eth+'/ethernet@2','gdm3':eth+'/ethernet@3'}
    if '/__symbols__' in base:
        for name,path in symbols.items():require(base['/__symbols__'].pop(name,None)==(path+'\0').encode(),'Incorrect symbol '+name)
    result=audit_accel_dtb_nodes(base,reserved,hashlib.sha256(data).hexdigest())
    result.update(board=MULTIGIG_BOARD,dt_nodes=len(nodes),external_PHY_nodes=2,PCS_nodes=2,wired_MAC_devices=3,multigig_hardware_verified=False)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['fit','kernel-config','initramfs','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();require(a.fit.stat().st_size<=MAX_FIT and a.initramfs.stat().st_size<=MAX_FIT,'Multigig image too large')
    parent=SOURCE.parent/'m70-integrated-accel';pinned=json.loads((parent/'private-inputs.json').read_text())
    wireless=(parent/'wireless').read_bytes();pinned['etc/config/wireless']={'bytes':len(wireless),'sha256':hashlib.sha256(wireless).hexdigest()}
    result=audit_fit(a.fit.read_bytes(),a.initramfs.read_bytes(),dtb_auditor=audit_multigig_dtb,
     initramfs_extra_sources={'etc/uci-defaults/99-vb235v-ram-multigig':SOURCE/'99-vb235v-ram-multigig'},initramfs_extra_files=pinned)
    result['kernel_config_sha256']=audit_lan_config(a.kernel_config)
    config=a.kernel_config.read_text()
    for key in ['SMP=y','NR_CPUS=4','NET_AIROHA_NPU=y','AIR_EN8811H_PHY=m','PCS_AIROHA_AN7583=y',
                'MDIO_AIROHA=y','CRYPTO_DEV_EIP93=m','CRYPTO_SELFTESTS=y','CRYPTO_SELFTESTS_FULL=y']:
        require('CONFIG_'+key+'\n' in config,'Missing multigig configuration '+key)
    a.output.write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print('Dual-PHY multigig RAM artifact admitted; no line rate or data result inferred.')
if __name__=='__main__':main()
