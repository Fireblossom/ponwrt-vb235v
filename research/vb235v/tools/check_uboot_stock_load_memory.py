# SPDX-License-Identifier: GPL-2.0-only
"""Check recovery DT carveouts against the observed VB235v stock kernel load."""
import argparse
import json
from pathlib import Path
import struct

from fdt_board_inventory import parse


def overlap(a, n, b, m):
    return a < b + m and b < a + n


def check(dtb):
    nodes, _ = parse(dtb)
    checks = 0

    def require(value, message):
        nonlocal checks
        checks += 1
        if not value:
            raise ValueError(message)

    require(b'tplink,vb235v' in nodes['/']['compatible'].split(b'\0'), 'Unexpected board')
    require(nodes['/memory@80000000']['reg'] == struct.pack('>QQ', 0x80000000, 0x20000000), 'DRAM map differs')
    atf = nodes['/reserved-memory/atf@80000000']['reg']
    base, length = struct.unpack('>QQ', atf)
    require((base, length) == (0x80000000, 0x50000), 'Secure carveout differs from original board DT')
    require(nodes['/chosen']['u-boot,usable-memory-range'] == struct.pack('>QQ', 0x80050000, 0x1ffb0000), 'Usable range differs')
    # Measured original ARM64 Image header: text_offset 0x88000,
    # image footprint 13,828,096 bytes, linked/load/entry 0x80088000.
    load, footprint = 0x80088000, 13828096
    require(not overlap(load, footprint, base, length), 'Stock kernel overlaps secure memory')
    reservations = []
    for path, props in nodes.items():
        if path.startswith('/reserved-memory/') and 'reg' in props:
            address, size = struct.unpack('>QQ', props['reg'])
            require(not overlap(load, footprint, address, size), 'Stock kernel overlaps ' + path)
            reservations.append({'node': path, 'address': address, 'bytes': size})
    require(load + footprint <= 0xa0000000, 'Kernel outside observed DRAM')
    require(overlap(load, footprint, 0x80000000, 0x200000), 'Old two-MiB reservation no longer demonstrates regression')
    return {'checks': checks, 'kernel_load': load, 'kernel_footprint': footprint,
            'secure_reservation_bytes': length, 'reservations': reservations}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dtb', type=Path, required=True)
    parser.add_argument('--prior-dtb', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = check(args.dtb.read_bytes())
    if args.prior_dtb:
        try:
            check(args.prior_dtb.read_bytes())
        except ValueError:
            result['prior_two_mib_layout_rejected'] = True
        else:
            raise ValueError('Prior layout unexpectedly passed')
    text = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.write_text(text)
    print(text, end='')


if __name__ == '__main__':
    main()
