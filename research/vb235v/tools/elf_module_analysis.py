# SPDX-License-Identifier: GPL-2.0-only
"""Bounded ELF64 little-endian relocatable-object analysis; never executes code."""
import bisect
import hashlib
from pathlib import Path
import struct


class Module:
    def __init__(self, path):
        self.path = Path(path)
        if self.path.stat().st_size > 64 * 1024 * 1024:
            raise ValueError('Artifact exceeds 64 MiB limit')
        self.data = self.path.read_bytes()
        if self.data[:6] != b'\x7fELF\x02\x01':
            raise ValueError('Expected ELF64 little-endian object')
        header = struct.unpack('<16sHHIQQQIHHHHHH', self.slice(0, 64))
        if header[1] != 1:
            raise ValueError('Expected ET_REL kernel-module object')
        self.machine = header[2]
        if header[11] != 64 or not 0 < header[12] <= 16384 or header[13] >= header[12]:
            raise ValueError('Unsupported ELF section table')
        raw = [struct.unpack('<IIQQQQIIQQ', self.slice(header[6]+i*64, 64)) for i in range(header[12])]
        names = self.slice(raw[header[13]][4], raw[header[13]][5])
        self.sections = []
        for index, entry in enumerate(raw):
            section = dict(zip(('name_index', 'type', 'flags', 'address', 'offset', 'size', 'link', 'info', 'alignment', 'entry_size'), entry))
            section.update(index=index, name=self.string(names, entry[0]))
            if section['type'] != 8:
                self.payload(section)
            self.sections.append(section)
        self.symbol_tables = {}
        for section in self.sections:
            if section['type'] not in (2, 11):
                continue
            if section['entry_size'] != 24 or section['size'] % 24 or section['link'] >= len(raw):
                raise ValueError('Invalid symbol table')
            strings = self.sections[section['link']]
            if strings['type'] != 3:
                raise ValueError('Symbol names do not refer to a string table')
            names = self.payload(strings)
            payload = self.payload(section)
            symbols = []
            for offset in range(0, len(payload), 24):
                name, info, other, index, value, size = struct.unpack('<IBBHQQ', payload[offset:offset+24])
                symbols.append({'name': self.string(names, name), 'type': info & 15, 'binding': info >> 4,
                                'section': index, 'value': value, 'size': size})
            self.symbol_tables[section['index']] = symbols

    def slice(self, offset, size):
        if offset < 0 or size < 0 or offset+size > len(self.data):
            raise ValueError('ELF range outside artifact')
        return self.data[offset:offset+size]

    @staticmethod
    def string(data, offset):
        if not 0 <= offset < len(data):
            raise ValueError('ELF string offset out of range')
        end = data.find(b'\0', offset)
        if end < 0:
            raise ValueError('Unterminated ELF string')
        return data[offset:end].decode('utf-8', 'replace')

    def payload(self, section):
        if section['type'] == 8:
            raise ValueError('SHT_NOBITS has no file payload')
        return self.slice(section['offset'], section['size'])

    def relocations(self):
        for section in self.sections:
            if section['type'] != 4:
                continue
            if section['entry_size'] != 24 or section['size'] % 24 or section['info'] >= len(self.sections):
                raise ValueError('Invalid RELA section')
            symbols = self.symbol_tables.get(section['link'])
            if symbols is None:
                raise ValueError('Relocations refer to an unsupported symbol table')
            target = self.sections[section['info']]
            payload = self.payload(section)
            for offset in range(0, len(payload), 24):
                address, info, addend = struct.unpack('<QQq', payload[offset:offset+24])
                index = info >> 32
                if index >= len(symbols) or address >= target['size']:
                    raise ValueError('Relocation refers outside its symbol/target table')
                yield {'target': target, 'offset': address, 'kind': info & 0xffffffff,
                       'symbol': symbols[index], 'addend': addend}

    def section_signatures(self):
        result = {}
        for section in self.sections:
            name = section['name']
            if name in result:
                raise ValueError('Duplicate section names require explicit disambiguation')
            result[name] = {'type': section['type'], 'flags': section['flags'], 'bytes': section['size'],
                            'sha256': None if section['type'] == 8 else hashlib.sha256(self.payload(section)).hexdigest()}
        return result

    def canonical_relocations(self):
        result = []
        for relocation in self.relocations():
            symbol = relocation['symbol']
            section = symbol['section']
            if section < len(self.sections):
                owner = self.sections[section]['name']
            else:
                owner = f'reserved:{section}'
            # Resolve numeric symbol-table indexes to names/sections. This is
            # descriptive canonicalization, not equivalence of relocated code.
            result.append((relocation['target']['name'], relocation['offset'], relocation['kind'],
                           symbol['name'], owner, symbol['value'], relocation['addend']))
        return sorted(result)

    def direct_call_edges(self):
        if self.machine != 183:
            raise ValueError('Direct-call analysis is currently AArch64 only')
        functions = {}
        for symbols in self.symbol_tables.values():
            for symbol in symbols:
                index = symbol['section']
                if symbol['type'] != 2 or not symbol['name'] or not symbol['size'] or index >= len(self.sections):
                    continue
                section = self.sections[index]
                if not section['flags'] & 4:
                    continue
                if symbol['value']+symbol['size'] > section['size']:
                    raise ValueError('Function extends outside executable section')
                functions.setdefault(index, []).append(symbol)
        for index in functions:
            functions[index].sort(key=lambda s: (s['value'], s['name']))
        starts = {index: [s['value'] for s in values] for index, values in functions.items()}

        def owner(index, offset):
            if index not in functions:
                return None
            values = functions[index]
            position = bisect.bisect_right(starts[index], offset)-1
            if position < 0 or offset >= values[position]['value']+values[position]['size']:
                return None
            return values[position]['name']

        edges = []
        for relocation in self.relocations():
            if relocation['kind'] not in (282, 283) or not relocation['target']['flags'] & 4:
                continue
            target = relocation['target']
            if target['type'] == 8 or relocation['offset'] % 4 or relocation['offset']+4 > target['size']:
                raise ValueError('Branch relocation outside aligned executable bytes')
            word = struct.unpack('<I', self.slice(target['offset']+relocation['offset'], 4))[0]
            opcode = 0x94000000 if relocation['kind'] == 283 else 0x14000000
            if word & 0xfc000000 != opcode:
                raise ValueError('Branch relocation does not match an AArch64 B/BL instruction')
            caller = owner(target['index'], relocation['offset'])
            if caller is None:
                continue
            symbol = relocation['symbol']
            callee = symbol['name']
            if symbol['type'] == 3 and symbol['section'] < len(self.sections):
                callee = owner(symbol['section'], symbol['value']+relocation['addend'])
            if not callee:
                continue
            edges.append({'caller': caller, 'callee': callee, 'section': target['name'],
                          'offset': relocation['offset'], 'tail_branch': relocation['kind'] == 282,
                          'external_symbol': symbol['section'] == 0})
        return edges
