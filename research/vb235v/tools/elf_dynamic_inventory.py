# SPDX-License-Identifier: GPL-2.0-only
"""Inventory AArch64 shared ELF dependencies and GOT slots without loading code.

Explicit ADRP/LDR/BLR witnesses check encodings and relocation correspondence.
They do not prove register liveness, control flow, interposition or runtime use.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from elf_module_analysis import Module


class SharedObject(Module):
    def __init__(self, path):
        super().__init__(path, elf_types=(3,))
        if self.machine != 183:
            raise ValueError('Expected AArch64 ET_DYN')

    def at(self, address, size, *, executable=False):
        matches = [s for s in self.sections if s['type'] == 1 and s['flags'] & 2
                   and (not executable or s['flags'] & 4)
                   and s['address'] <= address and address+size <= s['address']+s['size']]
        if size <= 0 or len(matches) != 1:
            raise ValueError('Virtual range not uniquely file backed')
        section = matches[0]
        return self.slice(section['offset']+address-section['address'], size)

    def dependencies(self):
        needed = []
        for section in self.sections:
            if section['type'] != 6:
                continue
            if section['entry_size'] != 16 or section['size'] % 16 or section['link'] >= len(self.sections):
                raise ValueError('Invalid dynamic table')
            strings = self.sections[section['link']]
            if strings['type'] != 3:
                raise ValueError('Dynamic strings do not refer to STRTAB')
            payload = self.payload(section)
            terminated = False
            for offset in range(0, len(payload), 16):
                tag, value = struct.unpack_from('<qQ', payload, offset)
                if tag == 0:
                    terminated = True
                    break
                if tag == 1:
                    needed.append(self.string(self.payload(strings), value))
            if not terminated:
                raise ValueError('Unterminated dynamic table')
        return needed

    def got_slots(self):
        result = {}
        for section in self.sections:
            if section['type'] != 4:
                continue
            symbols = self.symbol_tables.get(section['link'])
            if symbols is None or section['entry_size'] != 24 or section['size'] % 24:
                raise ValueError('Invalid dynamic RELA table')
            payload = self.payload(section)
            for offset in range(0, len(payload), 24):
                address, info, addend = struct.unpack_from('<QQq', payload, offset)
                index, kind = info >> 32, info & 0xffffffff
                if index >= len(symbols):
                    raise ValueError('Dynamic relocation symbol outside table')
                if kind not in (1025, 1026):  # GLOB_DAT / JUMP_SLOT only.
                    continue
                self.at(address, 8)
                if address in result or addend or not symbols[index]['name']:
                    raise ValueError('Ambiguous/unsupported GOT relocation')
                result[address] = symbols[index]['name']
        return result

    def inventory(self):
        tables = [self.symbol_tables[s['index']] for s in self.sections if s['type'] == 11]
        if len(tables) != 1:
            raise ValueError('Expected exactly one dynamic symbol table')
        symbols = tables[0]
        exports = sorted({s['name'] for s in symbols if s['name'] and s['section'] and s['binding'] in (1, 2)})
        imports = sorted({s['name'] for s in symbols if s['name'] and not s['section']})
        return {'file': self.path.name, 'bytes': len(self.data),
                'sha256': hashlib.sha256(self.data).hexdigest(),
                'needed': self.dependencies(), 'imports': imports, 'exports': exports,
                'got_slots': {hex(a): n for a, n in sorted(self.got_slots().items())}}

    def witness(self, adrp_pc, load_pc, call_pc):
        if any(p % 4 for p in (adrp_pc, load_pc, call_pc)) or not adrp_pc < load_pc < call_pc <= adrp_pc+128:
            raise ValueError('Witness must be ordered, aligned and bounded')
        adrp, load, call = [struct.unpack('<I', self.at(p, 4, executable=True))[0]
                            for p in (adrp_pc, load_pc, call_pc)]
        if adrp & 0x9f000000 != 0x90000000 or load & 0xffc00000 != 0xf9400000 or call & 0xfffffc1f != 0xd63f0000:
            raise ValueError('Expected ADRP, unsigned-offset LDR X, BLR')
        if (adrp & 31) != (load >> 5 & 31) or (load & 31) != (call >> 5 & 31):
            raise ValueError('Witness registers do not correspond')
        immediate = ((adrp >> 5 & 0x7ffff) << 2) | (adrp >> 29 & 3)
        if immediate & (1 << 20):
            immediate -= 1 << 21
        slot = (adrp_pc & ~4095) + immediate * 4096 + (load >> 10 & 4095) * 8
        symbol = self.got_slots().get(slot)
        if not symbol:
            raise ValueError('Witness has no supported GOT relocation')
        return {'adrp': hex(adrp_pc), 'load': hex(load_pc), 'call': hex(call_pc),
                'got_slot': hex(slot), 'symbol': symbol, 'register_liveness_verified': False,
                'runtime_use_verified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('elf', type=Path)
    parser.add_argument('--witness', nargs=3, type=lambda n: int(n, 0), action='append', default=[])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    obj = SharedObject(args.elf)
    report = obj.inventory()
    report['witnesses'] = [obj.witness(*pcs) for pcs in args.witness]
    report['executed_vendor_code'] = False
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'file': report['file'], 'needed': len(report['needed']), 'witnesses': len(report['witnesses'])}))


if __name__ == '__main__':
    main()
