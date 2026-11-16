# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from fdt_board_inventory import inventory, parse


def fixture(duplicate=False):
    strings = b'compatible\0serial-number\0bootargs\0reg\0'
    def word(*values):
        return struct.pack('>' + 'I' * len(values), *values)
    def node(name):
        encoded = name.encode() + b'\0'
        return word(1) + encoded + bytes((-len(encoded)) % 4)
    def prop(name, data):
        return word(3, len(data), strings.index(name.encode() + b'\0')) + data + bytes((-len(data)) % 4)
    structure = node('') + prop('compatible', b'test,board\0') + prop('serial-number', b'SECRET_SERIAL\0')
    if duplicate:
        structure += prop('compatible', b'test,other\0')
    structure += node('chosen') + prop('bootargs', b'PASSWORD_PRIVATE\0') + word(2)
    structure += node('memory@80000000') + prop('reg', word(0, 0x80000000, 0, 0x20000000)) + word(2, 2, 9)
    header = word(0xd00dfeed, 56 + len(structure) + len(strings), 56, 56 + len(structure), 40, 17, 16, 0, len(strings), len(structure))
    return header + bytes(16) + structure + strings


class FdtInventoryTest(unittest.TestCase):
    def test_tree_resources_and_private_values_are_separate(self):
        data = fixture()
        nodes, reservations = parse(data)
        self.assertEqual(len(nodes), 3)
        self.assertEqual(reservations, [])
        result = inventory(data)
        self.assertEqual(result['selected_nodes'][1]['properties']['reg'], [0, 0x80000000, 0, 0x20000000])
        self.assertNotIn('SECRET_SERIAL', str(result))
        self.assertNotIn('PASSWORD_PRIVATE', str(result))
        self.assertEqual(result['excluded_property_count'], 2)

    def test_overlapping_blocks_and_truncated_input_are_rejected(self):
        overlap = bytearray(fixture())
        struct.pack_into('>I', overlap, 12, 60)
        for data in (bytes(overlap), fixture()[:-1]):
            with self.subTest(length=len(data)), self.assertRaises(ValueError):
                parse(data)

    def test_duplicate_property_is_rejected(self):
        with self.assertRaises(ValueError):
            parse(fixture(duplicate=True))

    def test_invalid_string_offset_and_end_node_are_rejected(self):
        bad_name = bytearray(fixture())
        struct.pack_into('>I', bad_name, 56 + 8 + 8, 0xffffffff)
        bad_end = bytearray(fixture())
        struct.pack_into('>I', bad_end, 56, 2)
        for data in (bad_name, bad_end):
            with self.assertRaises(ValueError):
                parse(data)


if __name__ == '__main__':
    unittest.main()
