# SPDX-License-Identifier: GPL-2.0-only
"""Read ELF metadata and symbols offline; never load a module or execute a binary."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def bounded(data, offset, size):
    if offset < 0 or size < 0 or offset + size > len(data):
        raise ValueError('ELF section lies outside the file')
    return data[offset:offset + size]


def cstring(data, offset):
    if not 0 <= offset < len(data):
        raise ValueError('ELF string offset out of range')
    end = data.find(b'\0', offset)
    if end < 0:
        raise ValueError('Unterminated ELF string')
    return data[offset:end].decode('utf-8', 'replace')


def inspect(path):
    if path.stat().st_size > 64 * 1024 * 1024:
        raise ValueError('Artifact exceeds 64 MiB analysis limit')
    data = path.read_bytes()
    if data[:6] != b'\x7fELF\x02\x01':
        raise ValueError('This initial tool supports ELF64 little-endian files only')
    header = struct.unpack('<16sHHIQQQIHHHHHH', bounded(data, 0, 64))
    machine, section_offset, section_size, count, names_index = header[2], header[6], header[11], header[12], header[13]
    if count == 0 or count > 16384 or section_size != 64 or names_index >= count:
        raise ValueError('Unsupported or invalid ELF section table')
    sections = [struct.unpack('<IIQQQQIIQQ', bounded(data, section_offset + i * section_size, 64)) for i in range(count)]
    names_header = sections[names_index]
    names = bounded(data, names_header[4], names_header[5])
    metadata, undefined, exports = {}, set(), set()
    for section in sections:
        name = cstring(names, section[0])
        if section[1] == 8:  # SHT_NOBITS has no file payload.
            continue
        payload = bounded(data, section[4], section[5])
        if name == '.modinfo':
            for entry in payload.split(b'\0'):
                key, sep, value = entry.partition(b'=')
                if sep and key in (b'vermagic', b'depends', b'license', b'firmware', b'srcversion', b'name'):
                    metadata.setdefault(key.decode(), []).append(value.decode('utf-8', 'replace'))
        if section[1] not in (2, 11):  # SYMTAB / DYNSYM
            continue
        if section[9] != 24 or len(payload) % 24 or section[6] >= count:
            raise ValueError('Invalid ELF symbol table')
        strings_header = sections[section[6]]
        strings = bounded(data, strings_header[4], strings_header[5])
        for offset in range(0, len(payload), 24):
            symbol_name, info, other, index, value, size = struct.unpack('<IBBHQQ', payload[offset:offset+24])
            if not symbol_name:
                continue
            symbol = cstring(strings, symbol_name)
            if index == 0:
                undefined.add(symbol)
            if symbol.startswith('__ksymtab_'):
                exports.add(symbol.removeprefix('__ksymtab_'))
    # Stripped AArch64 .ko files often retain the export table and its
    # relocations but remove the local __ksymtab_<name> symbol labels.
    # Resolve the name field, rather than treating every export-string
    # candidate (including namespace strings) as an exported function.
    for relocation in sections:
        if machine != 183 or relocation[1] != 4:
            continue
        if relocation[7] >= count or relocation[6] >= count:
            raise ValueError('Invalid relocation section links')
        target = sections[relocation[7]]
        target_name = cstring(names, target[0])
        if target_name not in ('__ksymtab', '__ksymtab_gpl', '__ksymtab_unused', '__ksymtab_unused_gpl', '__ksymtab_gpl_future'):
            continue
        symbols = sections[relocation[6]]
        if symbols[1] != 2 or symbols[9] != 24 or relocation[9] != 24 or relocation[5] % 24:
            raise ValueError('Invalid export relocation table')
        payload = bounded(data, relocation[4], relocation[5])
        for offset in range(0, len(payload), 24):
            address, info, addend = struct.unpack('<QQq', payload[offset:offset+24])
            kind, symbol_index = info & 0xffffffff, info >> 32
            width, name_offset = (12, 4) if kind == 261 else (24, 8) if kind == 257 else (0, 0)
            if not width or address % width != name_offset:
                continue
            if address + (4 if kind == 261 else 8) > target[5] or symbol_index * 24 + 24 > symbols[5]:
                raise ValueError('Export relocation outside table')
            referenced = struct.unpack('<IBBHQQ', bounded(data, symbols[4]+symbol_index*24, 24))
            if not 0 < referenced[3] < count:
                raise ValueError('Export name has no valid string section')
            strings_header = sections[referenced[3]]
            if cstring(names, strings_header[0]) != '__ksymtab_strings':
                continue
            strings = bounded(data, strings_header[4], strings_header[5])
            exports.add(cstring(strings, referenced[4]+addend))
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest(),
            'elf_machine': machine, 'architecture': 'aarch64' if machine == 183 else f'ELF machine {machine}',
            'modinfo': metadata, 'undefined_symbols': sorted(undefined), 'exported_symbols': sorted(exports)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    files = [root] if root.is_file() else sorted(root.rglob('*.ko'))
    results = []
    for path in files:
        if path.is_symlink():
            continue
        relative = path.name if root.is_file() else path.relative_to(root).as_posix()
        try:
            result = inspect(path)
        except (ValueError, OSError, struct.error) as error:
            result = {'error': str(error)}
        results.append({'path': relative, **result})
    with args.output.open('x', encoding='utf-8') as output:
        json.dump({'artifacts': results, 'executed_vendor_code': False}, output, indent=2)
        output.write('\n')
    print(json.dumps({'artifacts': len(results), 'errors': sum('error' in r for r in results)}))


if __name__ == '__main__':
    main()
