# SPDX-License-Identifier: GPL-2.0-only
"""Synthetic ELF regression cases; no vendor binaries or device access."""
import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
sys.path.insert(0, str(TOOLS))
from elf_module_analysis import Module
from module_compare import compare


def fixture(renumber=False, extra=b'\xc0\x03\x5f\xd6'):
    text = struct.pack('<II', 0x94000000, 0xd65f03c0)
    strings = b'\0caller\0callee\0'
    caller = struct.pack('<IBBHQQ', 1, 0x12, 0, 1, 0, 8)
    callee = struct.pack('<IBBHQQ', 8, 0x12, 0, 0, 0, 0)
    symbols = bytes(24) + (callee+caller if renumber else caller+callee)
    relocation = struct.pack('<QQq', 0, ((1 if renumber else 2) << 32) | 283, 0)
    names = ('', '.text', '.strtab', '.symtab', '.rela.text', '.extra.text', '.shstrtab')
    name_table = b''
    offsets = []
    for name in names:
        offsets.append(len(name_table))
        name_table += name.encode()+b'\0'
    payloads = (b'', text, strings, symbols, relocation, extra, name_table)
    types = (0, 1, 3, 2, 4, 1, 3)
    flags = (0, 6, 0, 0, 0, 6, 0)
    data = bytearray(64+len(names)*64)
    sections = []
    for index, payload in enumerate(payloads):
        data.extend(bytes((-len(data)) % 8))
        offset = len(data)
        data.extend(payload)
        sections.append(struct.pack('<IIQQQQIIQQ', offsets[index], types[index], flags[index], 0,
                                    offset, len(payload), 2 if index == 3 else 3 if index == 4 else 0,
                                    1 if index == 4 else 0, 8, 24 if index in (3, 4) else 0))
    ident = b'\x7fELF\x02\x01\x01'+bytes(9)
    data[:64] = struct.pack('<16sHHIQQQIHHHHHH', ident, 1, 183, 1, 0, 0, 64, 0, 64, 0, 0, 64, len(names), 6)
    data[64:64+len(names)*64] = b''.join(sections)
    return bytes(data)


class ModuleAnalysisTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def write(self, name, data):
        path = self.directory / name
        path.write_bytes(data)
        return path

    def test_direct_call_has_sized_owner_and_external_symbol(self):
        module = Module(self.write('a.ko', fixture()))
        self.assertEqual(module.direct_call_edges(), [{'caller': 'caller', 'callee': 'callee',
                         'section': '.text', 'offset': 0, 'tail_branch': False, 'external_symbol': True}])

    def test_symbol_numbering_does_not_change_canonical_relocations(self):
        result = compare(self.write('a.ko', fixture()), self.write('b.ko', fixture(renumber=True)))
        self.assertFalse(result['whole_artifact_equal'])
        self.assertTrue(result['all_executable_section_bytes_equal'])
        self.assertTrue(result['canonical_relocations_equal'])

    def test_extra_executable_section_is_not_ignored(self):
        result = compare(self.write('a.ko', fixture()), self.write('b.ko', fixture(extra=b'\x1f\x20\x03\xd5')))
        self.assertFalse(result['all_executable_section_bytes_equal'])
        self.assertEqual(result['changed_executable_sections'], ['.extra.text'])

    def test_mismatched_branch_opcode_is_rejected(self):
        data = bytearray(fixture())
        offset = struct.unpack_from('<Q', data, 64+64+24)[0]
        struct.pack_into('<I', data, offset, 0xd503201f)
        with self.assertRaises(ValueError):
            Module(self.write('a.ko', data)).direct_call_edges()

    def test_truncated_sections_are_rejected(self):
        with self.assertRaises(ValueError):
            Module(self.write('a.ko', fixture()[:-3]))

    def test_function_outside_section_is_rejected(self):
        data = bytearray(fixture())
        symbol_offset = struct.unpack_from('<Q', data, 64+3*64+24)[0]
        struct.pack_into('<Q', data, symbol_offset+24+16, 1000)
        with self.assertRaises(ValueError):
            Module(self.write('a.ko', data)).direct_call_edges()


if __name__ == '__main__':
    unittest.main()
