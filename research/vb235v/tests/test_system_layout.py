# SPDX-License-Identifier: GPL-2.0-only
import copy
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from vb235v_system_layout import DEFAULT_LAYOUT, budget, validate


class SystemLayoutTests(unittest.TestCase):
    def setUp(self):
        self.layout = json.loads(DEFAULT_LAYOUT.read_text())

    def test_protected_ranges_and_system_cover_chip_without_overlap(self):
        validate(self.layout)
        ranges = self.layout['protected'] + [self.layout['system']]
        cursor = 0
        for item in sorted(ranges, key=lambda r: r['offset']):
            self.assertEqual(item['offset'], cursor)
            cursor += item['bytes']
        self.assertEqual(cursor, 0x20000000)

    def test_real_chip_bad_reserve_and_internal_accounting(self):
        p = budget(self.layout, 8 * 1024**2, 32 * 1024**2)
        self.assertEqual(p['bad_reserve_target_pebs'], 40)
        self.assertEqual(p['volume_capacity_lebs'], 275)
        self.assertEqual(p['internal_pebs'], 4)
        self.assertFalse(p['hardware_validated'])

    def test_bad_blocks_consume_the_existing_reserve_first(self):
        for bad in range(41):
            p = budget(self.layout, 1, 1, bad)
            self.assertEqual(p['volume_capacity_lebs'], 275)
            self.assertEqual(p['remaining_bad_reserve_pebs'], 40 - bad)
        self.assertEqual(budget(self.layout, 1, 1, 41)['volume_capacity_lebs'], 274)

    def test_exact_overlay_boundary(self):
        leb = 253952
        p = budget(self.layout, leb, 250 * leb)
        self.assertEqual(p['overlay_lebs'], 24)
        with self.assertRaises(ValueError):
            budget(self.layout, leb + 1, 250 * leb)

    def test_reject_old_320_peb_slot_and_any_geometry_change(self):
        for field in ('chip_bytes', 'page_bytes', 'erase_bytes', 'ecc_strength',
                      'ubi_data_offset', 'bad_pebs_per_1024'):
            changed = copy.deepcopy(self.layout)
            changed[field] += 1
            with self.assertRaises(ValueError):
                validate(changed)
        changed = copy.deepcopy(self.layout)
        changed['system'] = {'offset': 0x5c40000, 'bytes': 0x5000000, 'pebs': 320}
        with self.assertRaises(ValueError):
            validate(changed)

    def test_reject_invalid_sizes_and_boolean_integers(self):
        for k, r, bad in [(0, 1, 0), (1, -1, 0), (True, 1, 0), (1, 1, -1),
                          (1, 1, True), (1, 1, 319), (1, 100 * 1024**2, 0)]:
            with self.assertRaises(ValueError):
                budget(self.layout, k, r, bad)

    def test_reject_boolean_volume_identifier(self):
        changed = copy.deepcopy(self.layout)
        changed['volumes'][0]['id'] = False
        with self.assertRaises(ValueError):
            validate(changed)


if __name__ == '__main__':
    unittest.main()
