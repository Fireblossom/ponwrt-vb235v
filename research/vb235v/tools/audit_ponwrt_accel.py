#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exact integrated acceleration RAM gate, with private firmware hash checks."""
import argparse,copy,hashlib,json
from pathlib import Path
from audit_ponwrt_npu import audit_npu_dtb_nodes,NPU_BOARD
from audit_ponwrt_lan import audit_lan_config
from audit_ponwrt_ram import audit_fit,cells,require,MAX_FIT
from fdt_board_inventory import parse
ACCEL_BOARD='tplink,vb235v-ram-accel-development'
SOURCE=Path(__file__).resolve().parents[1]/'bringup/m70-integrated-accel'

def audit_accel_dtb(data):
    nodes,reserved=parse(data)
    return audit_accel_dtb_nodes(nodes,reserved,hashlib.sha256(data).hexdigest())

def audit_accel_dtb_nodes(nodes,reserved,dtb_sha256):
    base=copy.deepcopy(nodes)
    prefix=(ACCEL_BOARD+'\0').encode()
    require(base['/']['compatible'].startswith(prefix+(NPU_BOARD+'\0').encode()),'Incorrect acceleration identity')
    base['/']['compatible']=base['/']['compatible'][len(prefix):]
    crypto=base.pop('/crypto@1fb70000',None)
    require(crypto=={'compatible':b'inside-secure,safexcel-eip93ies\0','reg':cells(0,0x1fb70000,0,0x1000),'interrupts':cells(0,44,4)},'Incorrect EIP93 resources')
    scu='/system-controller@1fb00000';mdio=scu+'/mdio-bus@c8'
    handle=base[scu]['phandle']
    actual=base.pop(mdio,None)
    require(actual is not None and {k:v for k,v in actual.items() if k not in ['phandle','linux,phandle']}=={
     'compatible':b'airoha,an7583-mdio\0','reg':cells(0xc8),'clocks':handle+cells(9),'resets':handle+cells(23),
     '#address-cells':cells(1),'#size-cells':cells(0)},'Incorrect MDIO discovery resources')
    require(base[scu].pop('#address-cells',None)==cells(1) and base[scu].pop('#size-cells',None)==cells(0),'Incorrect MDIO parent cells')
    if '/__symbols__' in base:require(base['/__symbols__'].pop('mdio0',None)==(mdio+'\0').encode(),'Incorrect MDIO symbol')
    result=audit_npu_dtb_nodes(base,reserved,dtb_sha256)
    result.update(board=ACCEL_BOARD,dt_nodes=len(nodes),EIP93_nodes=1,external_MDIO_buses=1,external_PHY_nodes=0)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['fit','kernel-config','initramfs','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();require(a.fit.stat().st_size<=MAX_FIT and a.initramfs.stat().st_size<=MAX_FIT,'Acceleration image too large')
    pinned=json.loads((SOURCE/'private-inputs.json').read_text())
    wireless=(SOURCE/'wireless').read_bytes()
    pinned['etc/config/wireless']={'bytes':len(wireless),'sha256':hashlib.sha256(wireless).hexdigest()}
    result=audit_fit(a.fit.read_bytes(),a.initramfs.read_bytes(),dtb_auditor=audit_accel_dtb,
      initramfs_extra_sources={'etc/uci-defaults/99-vb235v-ram-accel':SOURCE/'99-vb235v-ram-accel'},
      initramfs_extra_files=pinned)
    result['kernel_config_sha256']=audit_lan_config(a.kernel_config)
    config=a.kernel_config.read_text()
    for key in ['SMP=y','NR_CPUS=4','NET_AIROHA_NPU=y','MDIO_AIROHA=y','CRYPTO_DEV_EIP93=m','CRYPTO_SELFTESTS=y','CRYPTO_SELFTESTS_FULL=y']:
        require('CONFIG_'+key+'\n' in config,'Missing acceleration configuration '+key)
    result.update(EIP93_hardware_verified=False,NPU_boot_time_firmware_embedded=True)
    a.output.write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print('Integrated acceleration RAM artifact admitted; hardware verification remains required.')

if __name__=='__main__':main()
