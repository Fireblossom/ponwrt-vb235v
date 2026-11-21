#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exact resource gate for the no-radio two-controller PCIe RAM experiment."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from audit_ponwrt_pcie import audit_pcie_dtb_nodes, PCIE_BOARD
from audit_ponwrt_lan import audit_lan_config
from audit_ponwrt_ram import audit_fit, cells, require, MAX_FIT
from fdt_board_inventory import parse

DUAL_BOARD = 'tplink,vb235v-ram-dual-pcie-development'
SOURCE = Path(__file__).resolve().parents[1] / 'bringup/m64-dual-pcie'


def audit_dual_dtb(data):
    nodes, reserved = parse(data)
    return audit_dual_dtb_nodes(nodes, reserved, hashlib.sha256(data).hexdigest())


def audit_dual_dtb_nodes(nodes, reserved, dtb_sha256):

    def h(path):
        v = nodes.get(path, {}).get('phandle')
        require(v is not None and len(v) == 4 and v != cells(0), 'Missing dual PCIe phandle: '+path)
        return v

    efuse='/efuse'
    layout=efuse+'/nvmem-layout'
    valid=layout+'/pcie-valid@4'
    term=layout+'/tx-term@8'
    imp=layout+'/rx-impedance@8'
    phy='/phy@1fa5f000'
    host='/pcie@1fa92000'
    intc=host+'/interrupt-controller'
    expected={
        efuse:{'compatible':b'airoha,an7583-efuse\0'},
        layout:{'compatible':b'fixed-layout\0','#address-cells':cells(1),'#size-cells':cells(1)},
        valid:{'reg':cells(4,1),'bits':cells(0,1)},
        term:{'reg':cells(8,1),'bits':cells(3,2)},
        imp:{'reg':cells(8,2),'bits':cells(5,5)},
        phy:{'compatible':b'tplink,vb235v-qp-pcie-development\0',
             'reg':cells(0,0x1fa5f000,0,0x1000,0,0x1fa5a000,0,0x1000,0,0x1fa5e000,0,0x1000),
             'reg-names':b'ana\0dig\0pma\0','#phy-cells':cells(0),
             'airoha,scu':h('/system-controller@1fb00000'),
             'nvmem-cells':h(valid)+h(term)+h(imp),'nvmem-cell-names':b'pcie-valid\0tx-term\0rx-impedance\0'},
        host:{'compatible':b'airoha,an7583-pcie1-development\0','device_type':b'pci\0',
              'linux,pci-domain':cells(1),'#address-cells':cells(3),'#size-cells':cells(2),
              'reg':cells(0,0x1fa92000,0,0x1000),'reg-names':b'port1\0',
              'clocks':h('/system-controller@1fb00000')+cells(7),'clock-names':b'sys_ck1\0',
              'phys':h(phy),'phy-names':b'pcie-phy1\0','airoha,pbus':h('/syscon@1fbe3400'),
              'ranges':cells(0x02000000,0,0x24000000,0,0x24000000,0,0x4000000),
              'bus-range':cells(0,255),'interrupts':cells(0,40,4),'interrupt-names':b'pcie_irq\0',
              '#interrupt-cells':cells(1),'interrupt-map-mask':cells(0,0,0,7),
              'interrupt-map':b''.join(cells(0,0,0,i+1)+h(intc)+cells(i) for i in range(4))},
        intc:{'interrupt-controller':b'','#address-cells':cells(0),'#interrupt-cells':cells(1)},
    }
    base=copy.deepcopy(nodes)
    for path,properties in expected.items():
        actual=base.pop(path,None)
        require(actual is not None and {k:v for k,v in actual.items() if k not in ('phandle','linux,phandle')} == properties,
                'Dual PCIe resource/property mismatch: '+path)
    require(base['/']['compatible'] == (DUAL_BOARD+'\0'+PCIE_BOARD+'\0airoha,an7583\0').encode(), 'Wrong dual PCIe identity')
    base['/']['compatible']=(PCIE_BOARD+'\0airoha,an7583\0').encode()
    if '/__symbols__' in base:
        for name,path in {'qp_valid':valid,'qp_tx_term':term,'qp_rx_imp':imp,'qphy':phy,'pcie1':host,'pcie1_intc':intc}.items():
            require(base['/__symbols__'].pop(name,None)==(path+'\0').encode(),'Incorrect dual PCIe symbol metadata')
    result=audit_pcie_dtb_nodes(base,reserved,dtb_sha256)
    result.update(board=DUAL_BOARD,dt_nodes=len(nodes),PCIe_controllers=2,QPHY_efuse_cells=3,
                  PCIe_primary_host_base='0x1fa92000',radio_tested=False)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fit',type=Path,required=True)
    p.add_argument('--kernel-config',type=Path,required=True)
    p.add_argument('--initramfs',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    require(a.fit.stat().st_size<=MAX_FIT and a.initramfs.stat().st_size<=MAX_FIT,'Artifact exceeds budget')
    archive=a.initramfs.read_bytes()
    require(b'mt7996e.ko' not in archive and b'mt7990_wm.bin' not in archive,'WLAN payload in no-radio image')
    result=audit_fit(a.fit.read_bytes(),archive,dtb_auditor=audit_dual_dtb,
                    initramfs_extra_sources={'etc/uci-defaults/99-vb235v-ram-dual-pcie':SOURCE/'99-vb235v-ram-dual-pcie'})
    result['kernel_config_sha256']=audit_lan_config(a.kernel_config)
    for name in ('PCIE_MEDIATEK','NVMEM_AIROHA_EFUSE'):
        require('CONFIG_'+name+'=y\n' in a.kernel_config.read_text(),'Missing required native driver '+name)
    result['WLAN_module_or_firmware_in_initramfs']=False
    a.output.write_bytes((json.dumps(result,indent=2)+'\n').encode())
    print('Dual PCIe no-radio RAM image and exact QPHY/eFuse resources verified.')


if __name__=='__main__':
    main()
