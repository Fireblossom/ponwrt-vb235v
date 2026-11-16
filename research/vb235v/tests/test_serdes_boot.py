# SPDX-License-Identifier: GPL-2.0-only
"""Synthetic board-selector grammar and privacy-boundary checks."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from serdes_boot_inventory import decode_bootargs


def fixture(**changes):
    fields = {'srdsPortCnt': '2', 'srdsParmCntPerPort': '3',
              'srdsIfNameAllComp': '3,NONE,XFI,USXGMII',
              'srdsPortNameAllComp': '1,2', 'srdsEtherTypeAllComp': '3,NONE,LAN,WAN',
              'srdsEtherPhyTypeAllComp': '3,NONE,DSL,PHY',
              'srdsPortCombo': '02,00,02,02,00,01', 'rfb_cfg': '122,211,aaa,bbb'}
    fields.update(changes)
    text = 'private_identifier=NONSERDES_SECRET_SENTINEL '
    text += ' '.join(k+'='+v for k, v in fields.items())
    return text.encode()+b'\0'


class SerdesBootTest(unittest.TestCase):
    def test_boot_selection_is_named_and_unrelated_fields_are_excluded(self):
        result = decode_bootargs(fixture())
        self.assertEqual(result['ports'][0]['phy_label'], 'DSL')
        self.assertEqual(result['ports'][0]['ether_role_label'], 'WAN')
        self.assertEqual(result['ports'][0]['interface_label'], 'USXGMII')
        self.assertEqual(result['ports'][1]['interface_label'], 'XFI')
        self.assertEqual(result['uninterpreted_trailing_rfb_entries'], 2)
        self.assertNotIn('NONSERDES_SECRET_SENTINEL', json.dumps(result))
        self.assertNotIn('aaa', json.dumps(result))

    def test_component_counts_are_decimal_and_option_indexes_hexadecimal(self):
        result = decode_bootargs(fixture(srdsIfNameAllComp='13,'+','.join('C'+str(i) for i in range(13)),
                                        srdsPortCombo='02,00,0c,02,00,01', rfb_cfg='12c,211'))
        self.assertEqual(result['ports'][0]['interface_label'], 'C12')

    def test_duplicate_missing_terminated_or_oversized_fields_fail(self):
        for data in (fixture()[:-1], fixture()+b'x', b'\0',
                     b'x'*8192+b'\0', fixture()[:-1]+b' srdsPortCnt=2\0',
                     fixture().replace(b'srdsPortCnt=2', b'other=2')):
            with self.subTest(size=len(data)), self.assertRaises(ValueError):
                decode_bootargs(data)

    def test_mismatched_names_counts_or_parameter_layout_fail(self):
        for change in ({'srdsPortCnt':'17'}, {'srdsPortCnt':'0x2'}, {'srdsParmCntPerPort':'4'},
                       {'srdsIfNameAllComp':'2,NONE,XFI,USXGMII'},
                       {'srdsPortNameAllComp':'1,1'}, {'srdsPortNameAllComp':'1'},
                       {'srdsEtherPhyTypeAllComp':'3,NONE,DSL,DSL'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                decode_bootargs(fixture(**change))

    def test_truncated_extra_duplicate_or_outside_options_fail(self):
        for options in ('02,00', '02,00,02,02,00,01,00', '02,00,00,02,00,01',
                        '02,00,ff,02,00,01', '00,02,00,01', '02,00,ZZ,02,00,01'):
            with self.subTest(options=options), self.assertRaises(ValueError):
                decode_bootargs(fixture(srdsPortCombo=options))

    def test_unavailable_selection_and_invalid_triplets_fail(self):
        for cfg in ('121,211', 'f22,211', '1f2,211', '12f,211', '122',
                    '122,211,aaaa', '122,211,xxz'):
            with self.subTest(cfg=cfg), self.assertRaises(ValueError):
                decode_bootargs(fixture(rfb_cfg=cfg))


if __name__ == '__main__':
    unittest.main()
