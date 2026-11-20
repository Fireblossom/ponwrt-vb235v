#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Offline codec for the pinned libpt SRC_blapi command envelope.

This module contains no socket/device operations and does not establish the
meaning or safety of any operation selector or command text.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

MAGIC = 0x75177517
VERSION = 1
ETHERTYPE = 0xbeea
PAYLOAD_BYTES = 204


def require(condition, message):
    if not condition:
        raise ValueError(message)


def encode_request(host_record):
    """Reconstruct the wrapper for host-model comparisons, not transmission."""
    require(type(host_record) is bytes and len(host_record) == 192, 'Expected a 192-byte host record')
    result = bytearray(PAYLOAD_BYTES)
    struct.pack_into('>IH', result, 0, MAGIC, VERSION)
    result[16:24] = host_record[4:12]
    result[28:188] = host_record[16:176]
    result[188:204] = host_record[176:192]
    return bytes(result)


def decode_payload(payload, *, show_command=False):
    require(type(payload) is bytes and len(payload) == PAYLOAD_BYTES, 'Expected a 204-byte libpt payload')
    magic, version = struct.unpack_from('>IH', payload)
    require(magic == MAGIC and version == VERSION, 'Unknown libpt magic/version')
    command = payload[28:188]
    result = {
        'profile': 'stock-libpt-SRC_blapi', 'payload_bytes': len(payload),
        'magic': hex(magic), 'version': version,
        'status_word_be': struct.unpack_from('>I', payload, 12)[0],
        'operation_word_be': struct.unpack_from('>I', payload, 16)[0],
        'suboperation_word_be': struct.unpack_from('>I', payload, 20)[0],
        'command_field_bytes': 160, 'command_sha256': hashlib.sha256(command).hexdigest(),
        'opaque_tail_bytes': 16, 'opaque_tail_sha256': hashlib.sha256(payload[188:]).hexdigest(),
        'unmapped_header_bytes_zero': not any(payload[6:12] + payload[24:28]),
        'selector_semantics_verified': False, 'request_is_read_only': None,
        'device_operations': False,
    }
    if show_command:
        prefix = command.split(b'\0', 1)[0]
        result['command_ascii'] = prefix.decode('ascii', errors='backslashreplace')
    return result


def decode_frame(frame, *, show_command=False):
    require(type(frame) is bytes and 14 <= len(frame) <= 230, 'Frame outside this command profile')
    offset = 14
    ethertype = struct.unpack_from('>H', frame, 12)[0]
    tags = 0
    while ethertype in (0x8100, 0x88a8):
        require(tags < 2 and len(frame) >= offset + 4, 'Unsupported or truncated VLAN tags')
        ethertype = struct.unpack_from('>H', frame, offset + 2)[0]
        offset += 4
        tags += 1
    require(ethertype == ETHERTYPE, 'Not the libpt 0xbeea command channel')
    result = decode_payload(frame[offset:], show_command=show_command)
    result.update(frame_bytes=len(frame), ethertype=hex(ethertype), vlan_tags=tags)
    # MACs, VLAN IDs and raw command/tail bytes are intentionally omitted.
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--payload-only', action='store_true')
    parser.add_argument('--show-command', action='store_true', help='Explicitly reveal captured command text')
    args = parser.parse_args()
    require(args.capture.stat().st_size <= 230, 'Supply one bounded frame or payload, not an entire capture')
    data = args.capture.read_bytes()
    decoder = decode_payload if args.payload_only else decode_frame
    print(json.dumps(decoder(data, show_command=args.show_command), indent=2))
