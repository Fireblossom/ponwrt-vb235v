# SPDX-License-Identifier: GPL-2.0-only
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from telekom_factory_profile import cross_check, normalize, select_candidate, unique_object


class TelekomFactoryProfileTests(unittest.TestCase):
    def setUp(self):
        self.config = {'internet': [
            {'name': 'Telekom_ADSL', 'vpi': 1, 'vci': 32, 'vtag': 7, 'atm_encap': 'LLC',
             'access_mode': 'ADSL', 'conn_type': 'PPPoE'},
            {'name': 'Telekom_VDSL', 'vid': 7, 'access_mode': 'VDSL', 'conn_type': 'PPPoE'}],
            'preset_pppoe_username': 'synthetic-user', 'preset_pppoe_password': 'synthetic-password'}
        self.ui = ('var telekomUsr = "synthetic-user"; var telekomPwd = "synthetic-password"; '
                   'DEV2_X_TP_AUTODETECT autoDetectState PPPUsername PPPPassword')

    def test_cross_checked_profile_needs_no_manual_account(self):
        profile, login = cross_check(self.config, self.ui)
        self.assertFalse(profile['manual_credentials_required'])
        self.assertNotIn('username', profile)
        self.assertEqual(login['username'], 'synthetic-user')
        self.assertFalse(profile['hardware_connection_verified'])

    def test_selects_atm_for_adsl_and_ptm_for_vdsl(self):
        profile = normalize(self.config)
        for mode in ('ADSL', 'ADSL2', 'ADSL2+', 'adsl2plus'):
            self.assertEqual(select_candidate(profile, mode)['bearer'], 'atm')
        self.assertEqual(select_candidate(profile, 'VDSL2')['bearer'], 'ptm')
        for mode in ('training', 'unknown', '', 'gpon'):
            with self.assertRaises(ValueError):
                select_candidate(profile, mode)

    def test_disagreeing_credentials_rejected(self):
        for key in ('preset_pppoe_username', 'preset_pppoe_password'):
            changed = copy.deepcopy(self.config)
            changed[key] = 'different'
            with self.assertRaises(ValueError):
                cross_check(changed, self.ui)

    def test_wrong_pvc_vlan_or_bearer_rejected(self):
        for index, key, value in [(0, 'vpi', 8), (0, 'vci', 35), (0, 'vtag', 8),
                                   (0, 'atm_encap', 'VCMUX'), (1, 'vid', 8)]:
            changed = copy.deepcopy(self.config)
            changed['internet'][index][key] = value
            with self.assertRaises(ValueError):
                normalize(changed)

    def test_duplicate_json_key_rejected(self):
        with self.assertRaises(ValueError):
            unique_object([('password', 'one'), ('password', 'two')])


if __name__ == '__main__':
    unittest.main()
