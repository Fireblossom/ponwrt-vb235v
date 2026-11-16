# SPDX-License-Identifier: GPL-2.0-only
"""Synthetic shared ELF failures and indirect-call correspondence tests."""
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from elf_dynamic_inventory import SharedObject
from elf_module_analysis import Module


def fixture(*, load=0xf9400c42, slot=0x11018, symbol=2, terminated=True):
    names = ('', '.text', '.dynstr', '.dynsym', '.rela.dyn', '.got', '.dynamic', '.shstrtab')
    table, offsets = b'', []
    for name in names:
        offsets.append(len(table))
        table += name.encode()+b'\0'
    strings = b'\0caller\0socket\0libc.so\0'
    symbols = bytes(24)+struct.pack('<IBBHQQ', 1, 0x12, 0, 1, 0x1000, 12)
    symbols += struct.pack('<IBBHQQ', 8, 0x12, 0, 0, 0, 0)
    dynamic = struct.pack('<qQ', 1, 15)+(bytes(16) if terminated else b'')
    payloads = (b'', struct.pack('<III', 0x90000082, load, 0xd63f0040), strings, symbols,
                struct.pack('<QQq', slot, (symbol << 32) | 1025, 0), bytes(8), dynamic, table)
    types = (0, 1, 3, 11, 4, 1, 6, 3)
    flags = (0, 6, 2, 2, 2, 3, 3, 0)
    addresses = (0, 0x1000, 0x2000, 0x3000, 0x4000, 0x11018, 0x5000, 0)
    links = (0, 0, 0, 2, 3, 0, 2, 0)
    sizes = (0, 0, 0, 24, 24, 0, 16, 0)
    data = bytearray(64+len(names)*64)
    sections = []
    for i, payload in enumerate(payloads):
        data.extend(bytes((-len(data)) % 8))
        offset = len(data)
        data.extend(payload)
        sections.append(struct.pack('<IIQQQQIIQQ', offsets[i], types[i], flags[i], addresses[i],
                                    offset, len(payload), links[i], 0, 8, sizes[i]))
    ident = b'\x7fELF\x02\x01\x01'+bytes(9)
    data[:64] = struct.pack('<16sHHIQQQIHHHHHH', ident, 3, 183, 1, 0, 0, 64, 0,
                           64, 0, 0, 64, len(names), 7)
    data[64:64+len(names)*64] = b''.join(sections)
    return data


class DynamicElfTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'synthetic.so'

    def obj(self, **kwargs):
        self.path.write_bytes(fixture(**kwargs))
        return SharedObject(self.path)

    def test_needed_imports_exports_and_got(self):
        report = self.obj().inventory()
        self.assertEqual(report['needed'], ['libc.so'])
        self.assertEqual(report['imports'], ['socket'])
        self.assertEqual(report['exports'], ['caller'])
        self.assertEqual(report['got_slots'], {'0x11018': 'socket'})

    def test_correspondence_is_not_reported_as_dataflow_or_runtime(self):
        report = self.obj().witness(0x1000, 0x1004, 0x1008)
        self.assertEqual(report['symbol'], 'socket')
        self.assertFalse(report['register_liveness_verified'])
        self.assertFalse(report['runtime_use_verified'])

    def test_module_relocation_api_rejects_shared_objects(self):
        obj = self.obj()
        with self.assertRaises(ValueError):
            list(obj.relocations())
        with self.assertRaises(ValueError):
            Module(self.path)

    def test_register_or_opcode_mismatch_is_rejected(self):
        for load in (0xf9400c43, 0xf9400c62, 0xd503201f):
            with self.subTest(load=load), self.assertRaises(ValueError):
                self.obj(load=load).witness(0x1000, 0x1004, 0x1008)

    def test_missing_relocation_or_outside_slot_is_rejected(self):
        with self.assertRaises(ValueError):
            self.obj(slot=0x11010).got_slots()
        with self.assertRaises(ValueError):
            self.obj(symbol=100).got_slots()

    def test_unterminated_dynamic_or_truncated_elf_is_rejected(self):
        with self.assertRaises(ValueError):
            self.obj(terminated=False).dependencies()
        self.path.write_bytes(fixture()[:-1])
        with self.assertRaises(ValueError):
            SharedObject(self.path)

    def test_unaligned_unordered_or_nonexecutable_witness_is_rejected(self):
        obj = self.obj()
        for pcs in ((0x1001, 0x1004, 0x1008), (0x1004, 0x1000, 0x1008),
                    (0x11018, 0x1101c, 0x11020), (0x1000, 0x1004, 0x1084)):
            with self.subTest(pcs=pcs), self.assertRaises(ValueError):
                obj.witness(*pcs)


if __name__ == '__main__':
    unittest.main()
