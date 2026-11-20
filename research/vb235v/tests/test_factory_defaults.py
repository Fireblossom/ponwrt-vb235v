# SPDX-License-Identifier: GPL-2.0-only
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from inspect_factory_defaults import management_report, parse_vendor_xml, remove_padding


class FactoryDefaultsTest(unittest.TestCase):
    def test_vendor_values_and_report_allowlist(self):
        data = b'''<?xml version="1.0"?>
<DslCpeConfig>
 <ManagementServer instance=1>
  <EnableCWMP val=0 />
  <PeriodicInformEnable val=1 />
  <URL val=https://test.invalid/?a=1&b=2 />
  <Username val=PRIVATE_USER />
  <Password val=PRIVATE_PASSWORD />
  <Empty val= />
 </ManagementServer>
</DslCpeConfig>'''
        root, counts = parse_vendor_xml(data)
        self.assertEqual(counts, {'quoted_values': 6, 'quoted_instance_attributes': 1})
        self.assertEqual(root.find('ManagementServer/URL').get('val'), 'https://test.invalid/?a=1&b=2')
        self.assertEqual(root.find('ManagementServer/Empty').get('val'), '')
        report = management_report(root)
        self.assertFalse(report['cwmp_enabled'])
        self.assertTrue(report['periodic_inform_enabled'])
        self.assertTrue(report['acs_url_present'])
        encoded = json.dumps(report)
        for sensitive in ('PRIVATE_USER', 'PRIVATE_PASSWORD', 'test.invalid'):
            self.assertNotIn(sensitive, encoded)

    def test_padding_validation(self):
        self.assertEqual(remove_padding(b'A' * 15 + b'\x01'), b'A' * 15)
        self.assertEqual(remove_padding(bytes([16]) * 16), b'')
        for invalid in (b'', b'A' * 15, b'A' * 15 + b'\0', b'A' * 15 + b'\x02'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                remove_padding(invalid)

    def test_reject_declarations_and_unexpected_root(self):
        for invalid in (b'<!DOCTYPE x><DslCpeConfig/>', b'<!ENTITY x "secret">',
                        b'<OtherRoot/>', b'x' * (1024 * 1024 + 1)):
            with self.assertRaises(ValueError):
                parse_vendor_xml(invalid)

    def test_reject_ambiguous_management(self):
        for xml in (b'<DslCpeConfig/>',
                    b'<DslCpeConfig><ManagementServer/><ManagementServer/></DslCpeConfig>',
                    b'<DslCpeConfig><ManagementServer><EnableCWMP val="0"/>'
                    b'<EnableCWMP val="1"/></ManagementServer></DslCpeConfig>'):
            root, _ = parse_vendor_xml(xml)
            with self.assertRaises(ValueError):
                management_report(root)


if __name__ == '__main__':
    unittest.main()
