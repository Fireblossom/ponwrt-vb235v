#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
import importlib.util
from pathlib import Path
import sys
import unittest
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('thermalmodel', Path(__file__).with_name('temperature-model.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class ModelTests(unittest.TestCase):
    def sample(self, **changes):
        s = dict(logical_sensor=0, mux=0, serialized_triplet=True, zero=32230, d0=18000, d1=19000)
        s.update(changes)
        return s

    def test_known_integer_arithmetic(self):
        t = m.temperature(self.sample())
        self.assertEqual(t['denominator'], 22960)
        self.assertEqual(t['temperature_mC'], 30000)
        self.assertFalse(t['hardware_validated'])
        self.assertIn('per-die accuracy unverified', t['calibration'])

    def test_no_mux_as_coefficient_index(self):
        for index in (5, 6, -1, True):
            with self.assertRaises(ValueError):
                m.temperature(self.sample(logical_sensor=index))
        self.assertEqual([s['mux'] for s in m.SENSORS], [0, 5, 6])

    def test_reject_incoherent_or_invalid_triplet(self):
        truncated = self.sample()
        del truncated['d0']
        with self.assertRaises(ValueError):
            m.temperature(truncated)
        with self.assertRaises(ValueError):
            m.temperature([])
        for changes in ({'mux': 6}, {'serialized_triplet': False},
                        {'d0': 19000}, {'d0': 20000}, {'zero': 0},
                        {'zero': 0xffffffff}, {'d1': -1}, {'d1': True}):
            with self.assertRaises(ValueError):
                m.temperature(self.sample(**changes))

    def test_c_truncation_and_large_intermediates(self):
        self.assertEqual(m.trunc_div(-9, 2), -4)
        self.assertEqual(m.trunc_div(9, -2), -4)
        # Large operands must not silently wrap as the original signed int.
        with self.assertRaises(ValueError):
            m.temperature(self.sample(d0=0, d1=0xffffffff, zero=0xffffffff))

    def test_real_zero_temperature_not_missing(self):
        # Construct a synthetic tuple whose integer result is exactly 0 C.
        t = m.temperature(self.sample(zero=34576))
        self.assertEqual(t['temperature_mC'], 0)

    def test_voltage_calibration(self):
        efuse = (40000 << 16) | 24000
        v = m.calibrated_voltage(32000, efuse)
        self.assertEqual(v['low_code_shift4'], 1500)
        self.assertEqual(v['high_code_shift4'], 2500)
        self.assertEqual(v['voltage_mV'], 1000)
        for ef in (0, 0xffffffff, 24000, (24000 << 16) | 40000):
            with self.assertRaises(ValueError):
                m.calibrated_voltage(32000, ef)
        with self.assertRaises(ValueError):
            m.calibrated_voltage(24000, efuse)

if __name__ == '__main__':
    unittest.main()
