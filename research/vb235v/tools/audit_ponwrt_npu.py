#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exact opt-in NPU RAM gate, retaining the M67 storage and network boundaries."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from audit_ponwrt_smp import audit_smp_dtb_nodes, SMP_BOARD
from audit_ponwrt_lan import audit_lan_config
from audit_ponwrt_ram import audit_fit, cells, require, MAX_FIT
from fdt_board_inventory import parse

NPU_BOARD='tplink,vb235v-ram-npu-development'
SOURCE=Path(__file__).resolve().parents[1]/'bringup/m68-npu'

def audit_npu_dtb(data):
    nodes,reserved=parse(data)
    return audit_npu_dtb_nodes(nodes,reserved,hashlib.sha256(data).hexdigest())

def audit_npu_dtb_nodes(nodes,reserved,dtb_sha256):
    base=copy.deepcopy(nodes)
    expected_compat=(NPU_BOARD+'\0'+SMP_BOARD+'\0tplink,vb235v-ram-dual-pcie-development\0tplink,vb235v-ram-pcie-development\0airoha,an7583\0').encode()
    require(base['/']['compatible']==expected_compat,'Unexpected NPU board identity')
    base['/']['compatible']=expected_compat[len(NPU_BOARD)+1:]
    memory='/reserved-memory/npu@84000000';npu='/npu@1e900000'
    def h(path):
        value=nodes.get(path,{}).get('phandle')
        require(value is not None and len(value)==4 and value!=cells(0),'Missing NPU handle: '+path)
        return value
    expected={'compatible':b'airoha,an7583-npu\0','reg':cells(0,0x1e900000,0,0x313000),
      'airoha,npu-layout':b'an7583-v2p\0',
      'interrupts':b''.join(cells(0,i,4) for i in [125,134,135,136,137,109,110,118,119,120,121,122,123]),
      'memory-region':h(memory),'memory-region-names':b'binary\0',
      'firmware-name':b'vb235v/stock-npu-rv32.bin\0vb235v/stock-npu-data.bin\0'}
    actual=base.pop(npu,None)
    require(actual is not None and {k:v for k,v in actual.items() if k not in ['phandle','linux,phandle']}==expected,'Unexpected NPU resources')
    require(base['/ethernet@1fb50000'].pop('airoha,npu',None)==h(npu),'Incorrect Ethernet NPU reference')
    require(base[memory]['reg']==cells(0,0x84000000,0,0xa00000) and base[memory].get('no-map')==b'','Incorrect NPU carveout')
    base[memory]['reg']=cells(0,0x84000000,0,0x100000)
    base[memory].pop('phandle',None)
    if '/__symbols__' in base:
        for key,path in [('npu',npu),('npu_binary',memory)]:
            require(base['/__symbols__'].pop(key,None)==(path+'\0').encode(),'Incorrect NPU symbol')
    result=audit_smp_dtb_nodes(base,reserved,dtb_sha256)
    result.update(board=NPU_BOARD,dt_nodes=len(nodes),NPU_nodes=1,NPU_processing_cores=6,
                  NPU_reserved_bytes=0xa00000,NPU_firmware_private_input=True,NPU_hardware_validated=False)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['fit','kernel-config','initramfs','output']:p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();require(a.fit.stat().st_size<=MAX_FIT and a.initramfs.stat().st_size<=MAX_FIT,'NPU image too large')
    result=audit_fit(a.fit.read_bytes(),a.initramfs.read_bytes(),dtb_auditor=audit_npu_dtb,
      initramfs_extra_sources={'etc/uci-defaults/99-vb235v-ram-npu':SOURCE/'99-vb235v-ram-npu'})
    result['kernel_config_sha256']=audit_lan_config(a.kernel_config)
    for key in ['SMP=y','NR_CPUS=4','NET_AIROHA_NPU=y']:
        require('CONFIG_'+key+'\n' in a.kernel_config.read_text(),'Missing NPU config '+key)
    a.output.write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print('Six-core NPU RAM image admitted; firmware communication and offload still require hardware tests.')
if __name__=='__main__':main()
