# SPDX-License-Identifier: GPL-2.0-only
"""Decode only allowlisted SerDes boot fields from a private stock FDT.

Describes boot selections, not current registers or physical endpoint identity.
Never emits the complete command line or unrelated board/device identifiers.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from fdt_board_inventory import parse

KEYS = ('srdsPortCnt', 'srdsParmCntPerPort', 'srdsIfNameAllComp',
        'srdsPortNameAllComp', 'srdsEtherTypeAllComp', 'srdsEtherPhyTypeAllComp',
        'srdsPortCombo', 'rfb_cfg')


def decode_bootargs(data):
    if not 0 < len(data) <= 8192 or data[-1:] != b'\0' or b'\0' in data[:-1]:
        raise ValueError('Expected one bounded terminated boot string')
    command = data[:-1].decode('ascii')
    fields = {}
    for key in KEYS:
        values = re.findall(r'(?:^|\s)'+key+r'=([^\s]*)', command)
        if len(values) != 1 or not 0 < len(values[0]) <= 1024:
            raise ValueError('Missing, duplicate or oversized SerDes field: '+key)
        fields[key] = values[0]
    if not re.fullmatch(r'[0-9]{1,2}', fields['srdsPortCnt']):
        raise ValueError('Port count must be decimal')
    count = int(fields['srdsPortCnt'], 10)
    if not 1 <= count <= 16 or fields['srdsParmCntPerPort'] != '3':
        raise ValueError('Unsupported port count or parameter layout')

    def components(key):
        parts = fields[key].split(',')
        if not re.fullmatch(r'[0-9]{1,2}', parts[0]):
            raise ValueError('Component count must be decimal')
        length = int(parts[0], 10)
        names = parts[1:]
        if not 1 <= length <= 32 or len(names) != length or len(set(names)) != length:
            raise ValueError('Component count or uniqueness mismatch')
        if any(not re.fullmatch(r'[A-Za-z0-9_.+\-]{1,24}', n) for n in names):
            raise ValueError('Unsupported component name')
        return names

    interfaces = components('srdsIfNameAllComp')
    roles = components('srdsEtherTypeAllComp')
    phys = components('srdsEtherPhyTypeAllComp')
    names = fields['srdsPortNameAllComp'].split(',')
    if len(names) != count or len(set(names)) != count or any(not re.fullmatch('[0-9]{1,2}', n) for n in names):
        raise ValueError('Unsupported port-name table')
    rfb = fields['rfb_cfg'].split(',')
    if not count <= len(rfb) <= count+8 or any(not re.fullmatch('[0-9a-fA-F]{3}', n) for n in rfb):
        raise ValueError('Unsupported RFB parameter records')
    tokens = fields['srdsPortCombo'].split(',')
    if any(not re.fullmatch('[0-9a-fA-F]{1,2}', n) for n in tokens):
        raise ValueError('Invalid hexadecimal interface options')
    options = [int(n, 16) for n in tokens]
    cursor, ports = 0, []
    for i in range(count):
        if cursor >= len(options):
            raise ValueError('Truncated option-count table')
        length = options[cursor]
        cursor += 1
        allowed = options[cursor:cursor+length]
        cursor += length
        if not 1 <= length <= len(interfaces) or len(allowed) != length or len(set(allowed)) != length:
            raise ValueError('Invalid or truncated port options')
        if any(n >= len(interfaces) for n in allowed):
            raise ValueError('Interface option index outside component table')
        phy, role, interface = [int(n, 16) for n in rfb[i]]
        if phy >= len(phys) or role >= len(roles) or interface >= len(interfaces) or interface not in allowed:
            raise ValueError('Selected port parameter outside supported table')
        ports.append({'port_index': i, 'port_name': 'Serdes-'+names[i],
                      'phy_selector': phy, 'phy_label': phys[phy],
                      'ether_role_selector': role, 'ether_role_label': roles[role],
                      'interface_selector': interface, 'interface_label': interfaces[interface],
                      'supported_interfaces': [interfaces[n] for n in allowed]})
    if cursor != len(options):
        raise ValueError('Unconsumed interface options')
    return {'classification': 'boot-argument selections; no live-register or wiring validation',
            'port_count': count, 'parameters_per_port': 3, 'ports': ports,
            'uninterpreted_trailing_rfb_entries': len(rfb)-count,
            'unrelated_bootargs_exported': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dtb', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.dtb.stat().st_size > 1024*1024:
        raise ValueError('FDT exceeds 1 MiB limit')
    data = args.dtb.read_bytes()
    nodes, _ = parse(data)
    report = decode_bootargs(nodes.get('/chosen', {}).get('bootargs', b''))
    report['dtb_sha256'] = hashlib.sha256(data).hexdigest()
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'ports': report['port_count'], 'unrelated_bootargs_exported': False}))


if __name__ == '__main__':
    main()
