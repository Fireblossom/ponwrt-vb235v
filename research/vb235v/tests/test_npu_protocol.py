# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from npu_protocol_compare import enum_values, modern_masks, vendor_argument_masks


class NpuProtocolTest(unittest.TestCase):
    def test_enum_explicit_values_restart_incrementing(self):
        self.assertEqual(enum_values('enum { A=0x10, B, C=3, D, };', 'A'), {'A': 16, 'B': 17, 'C': 3, 'D': 4})
        with self.assertRaises(ValueError):
            enum_values('enum { A=1<<4, B };', 'A')

    def test_register_masks_use_field_widths_and_offsets(self):
        old = 'typedef union { struct { unsigned short wait:1; unsigned short done:1; unsigned short status:3; } bits; unsigned short hWord; } mboxArg_t;'
        current = '#define MBOX_MSG_STATUS GENMASK(4, 2)\n#define MBOX_MSG_DONE BIT(1)\n'
        self.assertEqual(vendor_argument_masks(old)['status'], modern_masks(current)['MBOX_MSG_STATUS'])
        self.assertEqual(vendor_argument_masks(old)['done'], modern_masks(current)['MBOX_MSG_DONE'])
        with self.assertRaises(ValueError):
            vendor_argument_masks(old.replace('status:3', 'status:17'))


if __name__ == '__main__':
    unittest.main()
