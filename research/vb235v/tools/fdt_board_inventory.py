# SPDX-License-Identifier: GPL-2.0-only
"""Bounded FDT-v17 parser and allowlisted board inventory; raw DT remains private.

Format: https://devicetree-specification.readthedocs.io/en/stable/flattened-format.html
Unknown property values, boot arguments, MAC addresses, serials and calibration
are never copied into the output. This is resource inventory, not a DTS port.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct


def bounded(data, offset, size):
    if offset < 0 or size < 0 or offset + size > len(data):
        raise ValueError('FDT range outside its block')
    return data[offset:offset + size]


def string_at(data, offset):
    if not 0 <= offset < len(data):
        raise ValueError('FDT string offset outside block')
    end = data.find(b'\0', offset)
    if end < 0:
        raise ValueError('Unterminated FDT string')
    return data[offset:end].decode('ascii'), end + 1


def parse(data, *, max_bytes=1024 * 1024):
    if not 40 <= max_bytes <= 0x5000000 or not 40 <= len(data) <= max_bytes:
        raise ValueError('FDT input outside its explicit size bound')
    magic, total, off_struct, off_strings, off_reserve, version, compatible, cpu, size_strings, size_struct = struct.unpack('>10I', data[:40])
    if magic != 0xd00dfeed or version < 17 or compatible > 17 or compatible > version or total > len(data):
        raise ValueError('Unsupported/invalid FDT header')
    data = data[:total]
    if off_reserve < 40 or off_reserve % 8 or off_struct % 4 or size_struct % 4:
        raise ValueError('Invalid FDT block alignment')
    if not off_reserve < off_struct < off_strings or off_struct + size_struct > off_strings:
        raise ValueError('Invalid/overlapping FDT block ordering')
    strings = bounded(data, off_strings, size_strings)
    structure = bounded(data, off_struct, size_struct)
    reserve = []
    cursor = off_reserve
    while True:
        if cursor + 16 > off_struct:
            raise ValueError('Unterminated reservation map')
        address, size = struct.unpack('>QQ', bounded(data, cursor, 16))
        cursor += 16
        if not address and not size:
            break
        if not size or address + size > 1 << 64:
            raise ValueError('Invalid reservation range')
        reserve.append({'address': address, 'bytes': size})
    nodes, stack, child_started = {}, [], set()
    cursor = 0
    ended = False
    while cursor < len(structure):
        token = struct.unpack('>I', bounded(structure, cursor, 4))[0]
        cursor += 4
        if token == 1:
            name, cursor = string_at(structure, cursor)
            cursor = (cursor + 3) & ~3
            if len(stack) >= 128 or len(nodes) >= 4096 or (stack and not re.fullmatch(r'[A-Za-z0-9,._+*#?@-]+', name)):
                raise ValueError('Invalid/oversized FDT node tree')
            if not stack:
                if name or nodes:
                    raise ValueError('Expected exactly one empty-name root')
                path = '/'
            else:
                child_started.add(stack[-1])
                path = stack[-1].rstrip('/') + '/' + name
            if path in nodes:
                raise ValueError('Duplicate FDT path')
            nodes[path] = {}
            stack.append(path)
        elif token == 2:
            if not stack:
                raise ValueError('Unbalanced FDT end-node')
            stack.pop()
        elif token == 3:
            if not stack or stack[-1] in child_started:
                raise ValueError('Property outside node or after child')
            length, name_offset = struct.unpack('>II', bounded(structure, cursor, 8))
            cursor += 8
            name, _ = string_at(strings, name_offset)
            value = bounded(structure, cursor, length)
            cursor = (cursor + length + 3) & ~3
            if name in nodes[stack[-1]]:
                raise ValueError('Duplicate FDT property')
            nodes[stack[-1]][name] = value
        elif token == 4:
            continue
        elif token == 9:
            if stack or not nodes or cursor != len(structure):
                raise ValueError('Premature FDT end or trailing structure bytes')
            ended = True
            break
        else:
            raise ValueError('Unknown FDT token')
    if not ended:
        raise ValueError('Missing FDT end token')
    return nodes, reserve


def cells(value):
    if len(value) % 4:
        raise ValueError('Non-cell property used as cells')
    return list(struct.unpack('>' + 'I' * (len(value) // 4), value))


STRINGS = {'model', 'compatible', 'device_type', 'status', 'phy-mode', 'clock-names',
           'reg-names', 'interrupt-names', 'memory-region-names', 'pinctrl-names'}
CELLS = {'reg', 'ranges', 'dma-ranges', 'interrupts', 'interrupt-parent', 'interrupt-map',
         '#address-cells', '#size-cells', '#interrupt-cells', '#clock-cells', '#reset-cells', '#gpio-cells',
         'clock-frequency', 'clocks', 'resets', 'memory-region', 'phandle', 'linux,phandle',
         'bus-width', 'spi-max-frequency', 'spi-tx-bus-width', 'spi-rx-bus-width', 'phy-handle',
         'reset-gpios', 'gpios', 'reset-assert-us', 'reset-deassert-us', 'num-lanes'}
FLAGS = {'no-map', 'reusable', 'gpio-controller', 'interrupt-controller', 'dma-coherent'}


def inventory(data):
    nodes, reservations = parse(data)
    selected, excluded = [], 0
    phandles = {}
    for path, properties in nodes.items():
        for key in ('phandle', 'linux,phandle'):
            if key in properties:
                value = cells(properties[key])
                if len(value) != 1 or value[0] in (0, 0xffffffff):
                    raise ValueError('Invalid phandle')
                if value[0] in phandles and phandles[value[0]] != path:
                    raise ValueError('Conflicting phandle')
                phandles[value[0]] = path
    for path, properties in nodes.items():
        if path.split('/')[1] in ('chosen', 'aliases', '__symbols__', '__fixups__', '__local_fixups__'):
            excluded += len(properties)
            continue
        values = {}
        for key, value in properties.items():
            if key in STRINGS:
                if not value.endswith(b'\0'):
                    raise ValueError('Unterminated selected string property')
                values[key] = value[:-1].decode('ascii').split('\0')
            elif key in CELLS or re.fullmatch(r'pinctrl-\d+', key):
                values[key] = cells(value)
            elif key in FLAGS and not value:
                values[key] = True
            else:
                excluded += 1
        if values:
            selected.append({'path': path, 'properties': values})
    return {'classification': 'allowlisted resources from the stock boot-provided FDT, not physical wiring validation',
            'dtb_sha256': hashlib.sha256(data).hexdigest(), 'dtb_file_bytes': len(data),
            'parsed_nodes': len(nodes), 'selected_nodes': selected, 'reservation_map': reservations,
            'excluded_property_count': excluded,
            'phandles': {str(key): value for key, value in sorted(phandles.items())},
            'limitations': ['Node presence does not establish hardware availability or enabled runtime state.',
                           'Raw cells require the relevant bus binding and driver to interpret.',
                           'No boot arguments, MAC addresses, serial-number values or unknown property payloads are emitted.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dtb', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.dtb.stat().st_size > 1024 * 1024:
        raise ValueError('DTB exceeds 1 MiB')
    result = inventory(args.dtb.read_bytes())
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'parsed_nodes': result['parsed_nodes'], 'selected_nodes': len(result['selected_nodes']),
                      'excluded_properties': result['excluded_property_count']}))


if __name__ == '__main__':
    main()
