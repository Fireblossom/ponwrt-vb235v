# SPDX-License-Identifier: GPL-2.0-only
"""Inspect self-authored development artifacts offline, without executing them."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from audit_uart_bringup import check_config, check_dtb


def check_init(data):
    if len(data) < 64 or data[:6] != b'\x7fELF\x02\x01':
        raise ValueError('Expected ELF64 little-endian init')
    header = struct.unpack('<16sHHIQQQIHHHHHH', data[:64])
    if header[1:3] != (2, 183) or header[8] != 64 or header[9] != 56 or not 0 < header[10] <= 16:
        raise ValueError('Expected bounded static AArch64 executable')
    entry, phoff, count = header[4], header[5], header[10]
    if phoff < 64 or phoff + count * 56 > len(data):
        raise ValueError('Program headers outside init')
    entry_mapped = False
    for index in range(count):
        kind, flags, offset, address, physical, filesz, memsz, align = struct.unpack_from('<IIQQQQQQ', data, phoff + index * 56)
        if kind in (2, 3):
            raise ValueError('Init has dynamic linking or an interpreter')
        if kind == 1:
            if filesz > memsz or offset + filesz > len(data):
                raise ValueError('Load segment outside init')
            entry_mapped |= bool(flags & 1 and address <= entry < address + filesz)
        if kind == 0x6474e551 and flags & 1:
            raise ValueError('Init requests an executable stack')
    if not entry_mapped:
        raise ValueError('Init entry is not mapped by an executable file segment')
    return {'architecture': 'AArch64', 'static_executable': True, 'entry_in_executable_segment': True}


def check_cpio(data, init):
    cursor = 0
    entries = {}
    ended = False
    while cursor < len(data):
        if cursor + 110 > len(data) or data[cursor:cursor+6] != b'070701':
            raise ValueError('Invalid/truncated newc header')
        try:
            fields = [int(data[cursor+6+i*8:cursor+14+i*8], 16) for i in range(13)]
        except ValueError as error:
            raise ValueError('Invalid newc numeric field') from error
        cursor += 110
        namesize, size, mode = fields[11], fields[6], fields[1]
        if not 1 <= namesize <= 128 or cursor + namesize > len(data):
            raise ValueError('Invalid newc name range')
        name = data[cursor:cursor+namesize]
        if name[-1:] != b'\0' or b'\0' in name[:-1]:
            raise ValueError('Invalid newc path termination')
        name = name[:-1].decode('ascii')
        cursor = (cursor + namesize + 3) & ~3
        if cursor + size > len(data):
            raise ValueError('Truncated newc payload')
        payload = data[cursor:cursor+size]
        cursor = (cursor + size + 3) & ~3
        if name == 'TRAILER!!!':
            if size or any(data[cursor:]):
                raise ValueError('Unexpected data after newc trailer')
            ended = True
            break
        if name not in ('dev', 'dev/console', 'init') or name in entries or fields[2:4] != [0, 0]:
            raise ValueError('Unexpected/duplicate/non-root initramfs entry')
        if name == 'dev' and (mode != 0o40755 or size):
            raise ValueError('Unexpected dev directory')
        if name == 'dev/console' and (mode != 0o20600 or fields[9:11] != [5, 1] or size):
            raise ValueError('Unexpected console device')
        if name == 'init' and (mode != 0o100755 or payload != init):
            raise ValueError('Embedded init differs from verified static executable')
        entries[name] = {'mode': oct(mode), 'bytes': size}
    if not ended or set(entries) != {'dev', 'dev/console', 'init'}:
        raise ValueError('Incomplete minimal initramfs')
    return {'entries': entries, 'embedded_init_matches': True, 'no_shell_or_other_files': True}


def check_image(data):
    if len(data) < 64 or data[56:60] != b'ARM\x64':
        raise ValueError('Expected ARM64 Image header')
    header = struct.unpack('<IIQQQQQQII', data[:64])
    if not header[3] or header[3] < len(data):
        raise ValueError('Invalid ARM64 Image memory size')
    return {'file_bytes': len(data), 'text_offset': header[2], 'image_memory_bytes': header[3],
            'flags': header[4], 'arm64_magic_valid': True}


def read_file(path, maximum):
    if not path.is_file() or path.is_symlink() or not 0 < path.stat().st_size <= maximum:
        raise ValueError('Expected bounded regular artifact')
    return path.read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifacts', type=Path)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    files = {name: read_file(args.artifacts / name, maximum) for name, maximum in
             (('Image', 64 * 1024 * 1024), ('init', 1024 * 1024), ('initramfs_data.cpio', 1024 * 1024),
              ('vb235v-uart-only.dtb', 1024 * 1024))}
    config = read_file(args.config, 1024 * 1024)
    result = {'classification': 'local cross-build and offline artifact checks, not a hardware boot',
              'config_gate': check_config(config.decode()), 'dtb_gate': check_dtb(files['vb235v-uart-only.dtb']),
              'init_elf': check_init(files['init']), 'initramfs': check_cpio(files['initramfs_data.cpio'], files['init']),
              'kernel_image': check_image(files['Image']), 'hardware_boot_performed': False,
              'files': [{'file': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                        for name, data in files.items()], 'config_sha256': hashlib.sha256(config).hexdigest()}
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'kernel_bytes': len(files['Image']), 'all_offline_gates_passed': True}))


if __name__ == '__main__':
    main()
