#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Strict offline gate for the separately reviewed M58 single-port RAM LAN DT."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

from audit_ponwrt_ram import audit_config, audit_dtb_nodes, audit_fit, cells, require, BOARD, MAX_FIT
from fdt_board_inventory import parse

LAN_BOARD = 'tplink,vb235v-ram-lan-development'
SOURCE = Path(__file__).resolve().parents[1] / 'bringup/m58-ram-lan'
ETH = '/ethernet@1fb50000'
GSW = '/switch@1fb58000'


def audit_lan_dtb(data):
    nodes, reserved = parse(data)

    def handle(path):
        value = nodes.get(path, {}).get('phandle')
        require(value is not None and len(value) == 4 and value != cells(0), 'Missing LAN phandle: ' + path)
        return value

    scu = handle('/system-controller@1fb00000')
    gdm = handle(ETH + '/ethernet@1')
    expected = {
        '/syscon@1fa20000': {'compatible': b'airoha,en7581-chip-scu\0syscon\0simple-mfd\0',
                               'reg': cells(0, 0x1fa20000, 0, 0x388)},
        '/system-controller@1fb00000': {'compatible': b'airoha,an7583-scu\0syscon\0',
            'reg': cells(0, 0x1fb00000, 0, 0x970), '#clock-cells': cells(1), '#reset-cells': cells(1),
            'airoha,chip-scu': handle('/syscon@1fa20000')},
        ETH: {'compatible': b'airoha,an7583-eth\0',
            'reg': cells(0, 0x1fb50000, 0, 0x2600, 0, 0x1fb54000, 0, 0x2000, 0, 0x1fb56000, 0, 0x2000),
            'reg-names': b'fe\0qdma0\0qdma1\0',
            'resets': b''.join(scu + cells(i) for i in (40, 26, 27, 13, 14, 22)),
            'reset-names': b'fe\0pdma\0qdma\0hsi0-mac\0hsi1-mac\0xfp-mac\0',
            'interrupts': b''.join(cells(0, i, 4) for i in (37, 55, 56, 57, 38, 58, 59, 60, 49, 64)),
            'memory-region': handle('/reserved-memory/qdma0@87000000') + handle('/reserved-memory/qdma1@89000000'),
            'memory-region-names': b'qdma0-buf\0qdma1-buf\0', '#address-cells': cells(1), '#size-cells': cells(0)},
        ETH + '/ethernet@1': {'compatible': b'airoha,eth-mac\0', 'reg': cells(1), 'phy-mode': b'internal\0'},
        ETH + '/ethernet@1/fixed-link': {'speed': cells(10000), 'full-duplex': b'', 'pause': b''},
        GSW: {'compatible': b'airoha,an7583-switch\0', 'reg': cells(0, 0x1fb58000, 0, 0x8000),
            'resets': scu + cells(42), 'interrupt-controller': b'', '#interrupt-cells': cells(1),
            'interrupt-parent': handle('/interrupt-controller@9000000'), 'interrupts': cells(0, 209, 4),
            '#address-cells': cells(1), '#size-cells': cells(1)},
        GSW + '/ports': {'#address-cells': cells(1), '#size-cells': cells(0)},
        GSW + '/ports/port@3': {'reg': cells(3), 'label': b'lan-test\0', 'phy-mode': b'internal\0',
                               'phy-handle': handle(GSW + '/mdio/ethernet-phy@b')},
        GSW + '/ports/port@6': {'reg': cells(6), 'ethernet': gdm, 'phy-mode': b'internal\0'},
        GSW + '/ports/port@6/fixed-link': {'speed': cells(10000), 'full-duplex': b'', 'pause': b''},
        GSW + '/mdio': {'#address-cells': cells(1), '#size-cells': cells(0)},
        GSW + '/mdio/ethernet-phy@b': {'compatible': b'ethernet-phy-ieee802.3-c22\0',
                                     'reg': cells(11), 'phy-mode': b'internal\0'},
    }
    base = copy.deepcopy(nodes)
    for path, props in expected.items():
        actual = base.pop(path, None)
        require(actual is not None, 'Missing admitted LAN node: ' + path)
        actual = {k: v for k, v in actual.items() if k not in ('phandle', 'linux,phandle')}
        require(actual == props, 'LAN resource/property mismatch: ' + path)
    require(base['/']['compatible'] == (LAN_BOARD + '\0airoha,an7583\0').encode(), 'Incorrect RAM LAN identity')
    base['/']['compatible'] = (BOARD + '\0airoha,an7583\0').encode()
    require(base['/aliases'].pop('ethernet0', None) == (ETH + '/ethernet@1\0').encode(), 'Incorrect RAM LAN alias')
    if '/__symbols__' in base:
        for name, path in {'chip_scu': '/syscon@1fa20000', 'scuclk': '/system-controller@1fb00000',
                           'gdm1': ETH + '/ethernet@1', 'lan_phy': GSW + '/mdio/ethernet-phy@b'}.items():
            require(base['/__symbols__'].pop(name, None) == (path + '\0').encode(), 'Incorrect LAN symbol metadata')
    result = audit_dtb_nodes(base, reserved, hashlib.sha256(data).hexdigest())
    result.update(board=LAN_BOARD, dt_nodes=len(nodes), ethernet_controllers=1,
                  admitted_switch_ports=[3, 6], test_PHY_address=11,
                  storage_controllers=0, PCIe_controllers=0, NPU_nodes=0,
                  DSL_endpoint_nodes=0, GPIO_LED_nodes=0)
    return result


def audit_lan_config(path):
    digest = audit_config(path, allow_native_lan=True)
    content = path.read_text()
    for name in ('NET_AIROHA', 'NET_AIROHA_NPU', 'NET_DSA', 'NET_DSA_MT7530',
                 'NET_DSA_MT7530_MMIO', 'MEDIATEK_GE_SOC_PHY'):
        require('CONFIG_' + name + '=y\n' in content, 'Missing native LAN kernel driver: ' + name)
    require('CONFIG_NET_AIROHA_FLOW_STATS=y' not in content, 'Unreviewed NPU flow statistics')
    return digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dtb', type=Path)
    parser.add_argument('--fit', type=Path)
    parser.add_argument('--kernel-config', type=Path)
    parser.add_argument('--initramfs', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require((args.dtb is None) != (args.fit is None), 'Supply exactly one DTB or FIT')
    if args.fit:
        require(args.fit.stat().st_size <= MAX_FIT, 'FIT exceeds byte budget')
        require(args.initramfs is not None and args.initramfs.stat().st_size <= MAX_FIT,
                'Embedded initramfs required for RAM LAN gate')
        report = audit_fit(args.fit.read_bytes(), args.initramfs.read_bytes(), dtb_auditor=audit_lan_dtb,
                           initramfs_extra_sources={'etc/uci-defaults/99-vb235v-ram-lan': SOURCE / '99-vb235v-ram-lan'})
    else:
        require(args.dtb.stat().st_size <= 1024 * 1024, 'DTB exceeds byte budget')
        report = audit_lan_dtb(args.dtb.read_bytes())
    if args.kernel_config:
        report['kernel_config_sha256'] = audit_lan_config(args.kernel_config)
    report['wired_data_transfer_verified'] = False
    args.output.write_bytes((json.dumps(report, indent=2) + '\n').encode())
    print(json.dumps(report))


if __name__ == '__main__':
    main()
