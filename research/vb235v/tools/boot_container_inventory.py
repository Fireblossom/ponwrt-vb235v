# SPDX-License-Identifier: GPL-2.0-only
"""Read bounded Arm TF-A FIP tables from a local dump. No hardware operations."""
import argparse
import hashlib
import json
import lzma
from pathlib import Path
import re
import struct
import uuid

MAGIC = 0xaa640001
ROLES = {'5ff9ec0b-4d22-3e4d-a544-c39d81c73f0a': 'BL2',
         '47d4086d-4cfe-9846-9b95-2950cbbd5a00': 'BL31',
         'd6d0eea7-fcea-d54b-9782-9934f234b6e4': 'BL33'}


def read_fip(data, start):
    if start < 0 or start + 16 > len(data):
        raise ValueError('FIP header outside artifact')
    magic, serial, flags = struct.unpack_from('<IIQ', data, start)
    if magic != MAGIC:
        raise ValueError('FIP magic mismatch')
    entries = []
    position = start + 16
    for unused in range(128):
        if position + 40 > len(data):
            raise ValueError('Truncated FIP table')
        identity, offset, size, entry_flags = struct.unpack_from('<16sQQQ', data, position)
        position += 40
        if identity == bytes(16):
            break
        if size == 0 or offset < 16 or offset + size > len(data) - start:
            raise ValueError('FIP payload outside local artifact')
        payload = data[start+offset:start+offset+size]
        identifier = str(uuid.UUID(bytes=identity))
        entry = {'uuid': identifier, 'role': ROLES.get(identifier, 'other'), 'relative_offset': offset,
                        'artifact_offset': start+offset, 'bytes': size,
                        'sha256': hashlib.sha256(payload).hexdigest(), 'flags': entry_flags}
        if entry['role'] in ('BL31', 'BL33'):
            try:
                decoder = lzma.LZMADecompressor(format=lzma.FORMAT_AUTO, memlimit=64*1024*1024)
                decoded = decoder.decompress(payload, max_length=8*1024*1024+1)
                if not decoder.eof or len(decoded) > 8*1024*1024:
                    raise ValueError('Incomplete or oversized stage')
                entry['lzma'] = {'bytes': len(decoded), 'sha256': hashlib.sha256(decoded).hexdigest(),
                                 'uboot_banners': [b.decode('ascii') for b in re.findall(rb'U-Boot 20[0-9]{2}\.[0-9]{2}[^\x00\r\n]{0,100}', decoded)]}
            except (lzma.LZMAError, ValueError) as error:
                entry['lzma_unresolved'] = str(error)
        entries.append(entry)
    else:
        raise ValueError('FIP table has no bounded terminator')
    if not entries or any(e['artifact_offset'] < position for e in entries):
        raise ValueError('Empty FIP or payload overlaps table')
    ranges = sorted((e['artifact_offset'], e['artifact_offset']+e['bytes']) for e in entries)
    if any(a[1] > b[0] for a, b in zip(ranges, ranges[1:])):
        raise ValueError('Overlapping FIP payloads')
    return {'artifact_offset': start, 'header_flags': flags, 'entries': entries,
            'signature_verified': False, 'boot_rom_acceptance_tested': False}


def inspect(path):
    if path.stat().st_size > 128 * 1024 * 1024:
        raise ValueError('Input exceeds 128 MiB limit')
    data = path.read_bytes()
    candidates = []
    position = 0
    attempts = 0
    needle = struct.pack('<I', MAGIC)
    while attempts < 256:
        start = data.find(needle, position)
        if start < 0:
            break
        position = start + 1
        attempts += 1
        try:
            candidates.append(read_fip(data, start))
        except ValueError:
            continue
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            'valid_bounded_fip_tables': candidates,
            'note': 'Structural recognition only; not a signature or recovery validation.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifact', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.artifact)
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2)
        output.write('\n')
    print(json.dumps({'fip_tables': len(result['valid_bounded_fip_tables']), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
