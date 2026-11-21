#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exact two-core topology gate on the previously audited M64 RAM resources."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from audit_ponwrt_dual_pcie import audit_dual_dtb_nodes, DUAL_BOARD
from audit_ponwrt_lan import audit_lan_config
from audit_ponwrt_ram import audit_fit, cells, require, MAX_FIT
from fdt_board_inventory import parse

SMP_BOARD='tplink,vb235v-ram-smp-development'
SOURCE=Path(__file__).resolve().parents[1]/'bringup/m67-smp'

def audit_smp_dtb(data):
    nodes,reserved=parse(data)
    return audit_smp_dtb_nodes(nodes,reserved,hashlib.sha256(data).hexdigest())


def audit_smp_dtb_nodes(nodes,reserved,dtb_sha256):
    base=copy.deepcopy(nodes)
    expected_compat=(SMP_BOARD+'\0'+DUAL_BOARD+'\0tplink,vb235v-ram-pcie-development\0airoha,an7583\0').encode()
    require(base['/']['compatible']==expected_compat,'Unexpected SMP board identity')
    base['/']['compatible']=expected_compat[len(SMP_BOARD)+1:]
    def handle(path):
        value=nodes.get(path,{}).get('phandle')
        require(value is not None and len(value)==4 and value!=cells(0),'Missing SMP handle: '+path)
        return value
    l2='/cpus/l2-cache'
    expected={l2:{'compatible':b'cache\0','cache-level':cells(2),'cache-unified':b''},
              '/cpus/cpu-map':{},'/cpus/cpu-map/cluster0':{}}
    cpu_handles=[]
    for i in range(2):
        path='/cpus/cpu@'+str(i)
        cpu_handles.append(handle(path))
        props={'device_type':b'cpu\0','compatible':b'arm,cortex-a53\0',
               'reg':cells(i),'enable-method':b'psci\0','next-level-cache':handle(l2)}
        expected[path]=props
        expected['/cpus/cpu-map/cluster0/core'+str(i)]={'cpu':handle(path)}
    require(len(set(cpu_handles))==2,'Duplicate CPU phandles')
    for path,properties in expected.items():
        actual=base.pop(path,None)
        require(actual is not None and {k:v for k,v in actual.items() if k not in ('phandle','linux,phandle')}==properties,
                'SMP resource/property mismatch: '+path)
    base['/cpus/cpu@0']={k:v for k,v in expected['/cpus/cpu@0'].items() if k!='next-level-cache'}
    if '/__symbols__' in base:
        for name,path in {**{'cpu'+str(i):'/cpus/cpu@'+str(i) for i in range(2)},'l2':l2}.items():
            require(base['/__symbols__'].pop(name,None)==(path+'\0').encode(),'Incorrect SMP symbol: '+name)
    result=audit_dual_dtb_nodes(base,reserved,dtb_sha256)
    result.update(board=SMP_BOARD,dt_nodes=len(nodes),CPU_count=2,CPU_MPIDRs=[0,1],CPU_start_method='PSCI SMC')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fit',type=Path,required=True)
    p.add_argument('--kernel-config',type=Path,required=True)
    p.add_argument('--initramfs',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    require(a.fit.stat().st_size<=MAX_FIT and a.initramfs.stat().st_size<=MAX_FIT,'Oversized SMP artifact')
    archive=a.initramfs.read_bytes()
    require(b'mt7996e.ko' not in archive,'Unexpected runtime WLAN payload')
    result=audit_fit(a.fit.read_bytes(),archive,dtb_auditor=audit_smp_dtb,
                    initramfs_extra_sources={'etc/uci-defaults/99-vb235v-ram-smp':SOURCE/'99-vb235v-ram-smp'})
    result['kernel_config_sha256']=audit_lan_config(a.kernel_config)
    config=a.kernel_config.read_text()
    for key in ['SMP=y','NR_CPUS=4','HOTPLUG_CPU=y','ARM_PSCI_FW=y','PCIE_MEDIATEK=y','NVMEM_AIROHA_EFUSE=y']:
        require('CONFIG_'+key+'\n' in config,'Missing SMP configuration: '+key)
    a.output.write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print('Two-core RAM FIT, complete userspace and inherited resource boundaries verified.')

if __name__=='__main__':main()
