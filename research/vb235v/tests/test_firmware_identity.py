# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from npu_firmware_identity import bounded_read, compare_bytes


class FirmwareIdentityTest(unittest.TestCase):
    def test_equal_length_is_not_identity_and_length_difference_is_separate(self):
        same_length = compare_bytes(b'abcd', b'abce')
        self.assertFalse(same_length['byte_exact'])
        self.assertEqual(same_length['different_positions_within_shared_length'], 1)
        shorter = compare_bytes(b'abcd', b'abcdextra')
        self.assertFalse(shorter['byte_exact'])
        self.assertEqual(shorter['different_positions_within_shared_length'], 0)
        self.assertEqual(shorter['actual_minus_reference_length'], -5)
        self.assertTrue(compare_bytes(b'abcd', b'abcd')['byte_exact'])

    def test_oversized_and_empty_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.bin'
            path.write_bytes(b'abc')
            with self.assertRaises(ValueError):
                bounded_read(path, 2)
            path.write_bytes(b'')
            with self.assertRaises(ValueError):
                bounded_read(path, 2)


if __name__ == '__main__':
    unittest.main()
