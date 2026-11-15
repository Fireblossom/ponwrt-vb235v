# SPDX-License-Identifier: GPL-2.0-only
"""Decode an already captured xdslmgr_ioctl buffer. Never opens /dev/xdsl."""
import argparse
import json
from pathlib import Path
import struct

# Source-derived standard AArch64 C ABI assumptions: enums/u32 are 4 bytes,
# XDSL_LINEDATA is the largest union member (288 bytes), no packed attribute.
SIZE = 296
REQUEST = (3 << 30) | (SIZE << 16) | (ord('X') << 8)
FUNCTIONS = ('GET_FWVER', 'GET_LINKSTATUS', 'GET_MODE', 'GET_ANNEX', 'GET_TPSTC',
             'GET_CHANDATA', 'GET_PERFDATA', 'GET_LINEDATA', 'GET_ATTAIN_RATE',
             'GET_UPTIME', 'GET_LINESTATE', 'GET_SHOWTIME', 'GET_PMS', 'GET_EVENT')


def decode(data):
    if len(data) != SIZE:
        raise ValueError('Expected exactly 296 bytes for the stated source ABI')
    function, status = struct.unpack_from('<ii', data)
    if not 0 <= function < len(FUNCTIONS):
        raise ValueError('Function selector outside reviewed source enum')
    body = data[8:]
    result = {'function': FUNCTIONS[function], 'function_id': function, 'return_value': status,
              'abi_classification': 'source-derived; not verified against the live ioctl handler'}
    if function == 0:
        result['firmware_version'] = body[:64].split(b'\0', 1)[0].decode('ascii', 'replace')
    elif function in (1, 2, 3, 4, 9, 10, 13):
        result['value_u32'] = struct.unpack_from('<I', body)[0]
    elif function == 8:
        result['rx_rate'], result['tx_rate'] = struct.unpack_from('<II', body)
    elif function == 5:
        result['interleaved_rate'] = list(struct.unpack_from('<II', body))
        result['fast_rate'] = list(struct.unpack_from('<II', body, 8))
    else:
        result['union_hex'] = body.hex()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    args = parser.parse_args()
    result = decode(args.capture.read_bytes())
    result['source_derived_request'] = hex(REQUEST)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
