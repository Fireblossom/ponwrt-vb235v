# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from kernel_symbol_providers import correlate, parse_kallsyms, parse_symvers


class KernelProviderTest(unittest.TestCase):
    def test_zero_addresses_are_usable_and_module_tags_are_preserved(self):
        definitions = parse_kallsyms('echo command\n0000000000000000 T core_api\n'
                                    '0000000000000000 t wifi_api [wifi]\n'
                                    '0000000000000000 U missing\n~ #')
        self.assertEqual(definitions['core_api'], {('T', 'vmlinux')})
        self.assertEqual(definitions['wifi_api'], {('t', 'wifi')})
        self.assertNotIn('missing', definitions)

    def test_runtime_and_archived_exports_remain_separate(self):
        artifact = {'path': 'npu.ko', 'sha256': 'a' * 64,
                    'undefined_symbols': ['core_api', 'unknown'], 'exported_symbols': []}
        definitions = parse_kallsyms('0000000012345678 T core_api\n')
        exports = parse_symvers('0x00000000 core_api vmlinux EXPORT_SYMBOL\n')
        result = correlate([artifact], definitions, exports, ['npu'])
        row = result['consumers']['npu']
        self.assertEqual(row['only_live_vmlinux_provider'], ['core_api'])
        self.assertEqual(row['not_observed_in_live_symbols'], ['unknown'])
        self.assertNotIn('12345678', str(result))
        self.assertEqual(row['imports'][0]['archived_build_exports'][0]['provider'], 'vmlinux')

    def test_conflicting_duplicate_builds_are_rejected(self):
        artifact = {'path': 'a/npu.ko', 'sha256': 'a' * 64, 'undefined_symbols': [], 'exported_symbols': []}
        with self.assertRaises(ValueError):
            correlate([artifact, {**artifact, 'path': 'b/npu.ko', 'sha256': 'b' * 64}], {})


if __name__ == '__main__':
    unittest.main()
