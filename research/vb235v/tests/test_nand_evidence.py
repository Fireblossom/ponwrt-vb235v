# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from nand_boot_evidence import summarize

BOOT = '''nand: device found, Manufacturer ID: 0x2c, Chip ID: 0x34
nand: 512 MiB, SLC, erase size: 256 KiB, page size: 4096, OOB size: 256
Using Flash ECC.
nand: NAND_ECC_NONE selected by board driver. This is not recommended!
bmt pool size: 163
'''
MTD = 'mtd0: 0c680000 00040000 "whole"\n'


class NandEvidenceTest(unittest.TestCase):
    def test_ecc_warning_does_not_override_reported_flash_ecc(self):
        result = summarize(BOOT + 'unrelated private serial XYZ123\n', MTD)
        self.assertEqual(result['reported_ecc_paths'], ['Flash'])
        self.assertTrue(result['nand_core_ecc_none_warning'])
        self.assertEqual(result['physical_geometry']['physical_erase_blocks'], 2048)
        self.assertEqual(result['reported_bmt_pool_blocks'], [163])
        self.assertNotIn('XYZ123', str(result))
        self.assertLess(result['mtd_entries'][0]['bytes'], result['physical_geometry']['bytes'])

    def test_conflicting_geometry_and_duplicate_mtd_are_rejected(self):
        with self.assertRaises(ValueError):
            summarize(BOOT + BOOT.replace('512 MiB', '256 MiB'), MTD)
        with self.assertRaises(ValueError):
            summarize(BOOT, MTD + MTD)

    def test_multiple_reported_paths_remain_observations(self):
        self.assertEqual(summarize(BOOT + 'Using SoC ECC.\n', MTD)['reported_ecc_paths'], ['Flash', 'SoC'])


if __name__ == '__main__':
    unittest.main()
