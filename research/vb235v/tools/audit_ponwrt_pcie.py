#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Strict gate for the separate no-radio, one-lane PCIe RAM experiment."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
from audit_ponwrt_ram import audit_fit, cells, require, MAX_FIT
from audit_ponwrt_lan import audit_lan_dtb_nodes, audit_lan_config, LAN_BOARD
from fdt_board_inventory import parse

PCIE_BOARD = 'tplink,vb235v-ram-pcie-development'
SOURCE = Path(__file__).resolve().parents[1] / 'bringup/m63-ram-pcie'


def audit_pcie_dtb(data):
    nodes, reserved = parse(data)
    return audit_pcie_dtb_nodes(nodes, reserved, hashlib.sha256(data).hexdigest())


def audit_pcie_dtb_nodes(nodes, reserved, dtb_sha256):

    def h(path):
        value = nodes.get(path, {}).get('phandle')
        require(value is not None and len(value) == 4 and value != cells(0), 'Missing PCIe phandle: ' + path)
        return value

    scu = h('/system-controller@1fb00000')
    chip = h('/syscon@1fa20000')
    pbus = '/syscon@1fbe3400'
    phy = '/phy@1fc7f000'
    mac = '/pcie@1fc20000'
    intc = mac + '/interrupt-controller'
    expected = {
        pbus: {'compatible': b'airoha,en7581-pbus-csr\0syscon\0', 'reg': cells(0, 0x1fbe3400, 0, 0x100)},
        phy: {'compatible': b'airoha,an7583-pcie-gen3-phy\0',
              'reg': cells(0, 0x1fc7f000, 0, 0x1000, 0, 0x1fc7e000, 0, 0x1000,
                           0, 0x1fc30044, 0, 4, 0, 0x1fc35030, 0, 4),
              'reg-names': b'g3-ana\0g3-pma\0xr-dtime\0rx-aeq\0', '#phy-cells': cells(0)},
        mac: {'compatible': b'airoha,an7583-pcie-development\0', 'device_type': b'pci\0',
              'linux,pci-domain': cells(0), '#address-cells': cells(3), '#size-cells': cells(2),
              'reg': cells(0, 0x1fc20000, 0, 0x2000), 'reg-names': b'pcie-mac\0',
              'clocks': scu + cells(7), 'clock-names': b'sys-ck\0',
              'resets': scu + cells(44), 'reset-names': b'mac\0',
              'phys': h(phy), 'phy-names': b'pcie-phy\0', 'airoha,scu': scu,
              'airoha,chip-scu': chip, 'airoha,pbus': h(pbus), 'num-lanes': cells(1),
              'max-link-speed': cells(3), 'ranges': cells(0x02000000, 0, 0x20000000, 0, 0x20000000, 0, 0x4000000),
              'bus-range': cells(0, 255), '#interrupt-cells': cells(1), 'interrupts': cells(0, 39, 4),
              'interrupt-map-mask': cells(0, 0, 0, 7),
              'interrupt-map': b''.join(cells(0, 0, 0, i+1) + h(intc) + cells(i) for i in range(4))},
        intc: {'interrupt-controller': b'', '#address-cells': cells(0), '#interrupt-cells': cells(1)},
    }
    base = copy.deepcopy(nodes)
    for path, properties in expected.items():
        actual = base.pop(path, None)
        require(actual is not None, 'Missing admitted PCIe node: ' + path)
        require({k:v for k,v in actual.items() if k not in ('phandle', 'linux,phandle')} == properties,
                'PCIe resources/properties differ: ' + path)
    require(base['/']['compatible'] == (PCIE_BOARD + '\0airoha,an7583\0').encode(), 'Incorrect PCIe RAM identity')
    base['/']['compatible'] = (LAN_BOARD + '\0airoha,an7583\0').encode()
    if '/__symbols__' in base:
        for name, path in {'pbus':pbus, 'pciephy':phy, 'pcie0':mac, 'pcie_intc':intc}.items():
            require(base['/__symbols__'].pop(name, None) == (path + '\0').encode(), 'Incorrect PCIe symbol metadata')
    result = audit_lan_dtb_nodes(base, reserved, dtb_sha256)
    result.update(board=PCIE_BOARD, dt_nodes=len(nodes), PCIe_controllers=1, PCIe_lanes=1,
                  PCIe_host_base='0x1fc20000', PCIe_outbound_window='0x20000000+0x4000000',
                  WLAN_endpoint_nodes=0, radio_tested=False)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--fit', type=Path, required=True)
    p.add_argument('--initramfs', type=Path, required=True)
    p.add_argument('--kernel-config', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    require(args.fit.stat().st_size <= MAX_FIT and args.initramfs.stat().st_size <= MAX_FIT, 'Artifact exceeds budget')
    archive = args.initramfs.read_bytes()
    require(b'mt7996e.ko\0' not in archive and b'mt7990_wm.bin\0' not in archive, 'WLAN payload in no-radio image')
    result = audit_fit(args.fit.read_bytes(), archive, dtb_auditor=audit_pcie_dtb,
                      initramfs_extra_sources={'etc/uci-defaults/99-vb235v-ram-pcie': SOURCE / '99-vb235v-ram-pcie'})
    result['kernel_config_sha256'] = audit_lan_config(args.kernel_config)
    content = args.kernel_config.read_text()
    for name in ('PCI', 'PCI_MSI', 'PCIE_MEDIATEK_GEN3', 'PHY_AIROHA_AN7583_PCIE'):
        require('CONFIG_' + name + '=y\n' in content, 'Missing PCIe driver: ' + name)
    result['WLAN_module_or_firmware_in_initramfs'] = False
    args.output.write_bytes((json.dumps(result, indent=2)+'\n').encode())
    print('No-radio PCIe RAM FIT, exact resources, userspace and storage exclusions verified.')


if __name__ == '__main__':
    main()
