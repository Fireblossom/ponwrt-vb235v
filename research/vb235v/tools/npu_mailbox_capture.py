# SPDX-License-Identifier: GPL-2.0-only
"""Decode a saved source-layout NPU host descriptor; never sends a mailbox request."""
import argparse
import json
from pathlib import Path
import struct

FUNCTIONS = ('WIFI', 'TUNNEL', 'NOTIFY', 'DBA', 'TR471', 'HWNAT')
FORMAT = '<IIQIH2xIIQ'
SIZE = struct.calcsize(FORMAT)


def decode(data):
    if len(data) != SIZE:
        raise ValueError('Expected 40 bytes for the reviewed standard AArch64 source layout')
    core, function, virtual, physical, length, flags, timeout, callback = struct.unpack(FORMAT, data)
    if core > 7 or function >= len(FUNCTIONS):
        raise ValueError('Selector outside the reviewed source enums')
    return {'classification': 'source-derived host structure; not verified against a live handler',
            'core_id': core, 'function_id': function, 'function_name': FUNCTIONS[function],
            'virtual_address': hex(virtual), 'physical_address': hex(physical),
            'payload_length': length, 'raw_flags': hex(flags),
            'blocking_mode': bool(flags & 1), 'static_buffer_init': bool(flags & 2),
            'static_buffer_delete': bool(flags & 4), 'unknown_flag_bits': hex(flags & ~7),
            'timeout_units_100us': timeout, 'callback_address': hex(callback),
            'note': 'This host descriptor is not by itself the NPU firmware wire protocol.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    args = parser.parse_args()
    print(json.dumps(decode(args.capture.read_bytes()), indent=2))


if __name__ == '__main__':
    main()
