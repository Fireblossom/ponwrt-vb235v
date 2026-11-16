# SPDX-License-Identifier: GPL-2.0-only
"""Synthetic PMA selector and Ethernet/optical route separation tests."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from pcs_rate_contract import compare, function_body, reference_vector, vendor_vector


def fixture():
    vendor = 'void pon_WanSelInit(unsigned x) { switch(x) { '
    reference = 'static const struct rates rates[] = {'
    for old, new, values in (('Async_GPON', 'AIROHA_PCS_PON_MODE_GPON', (2,5,3,2,3)),
                              ('Sync_XEPON', 'AIROHA_PCS_PON_MODE_EPON_10G_10G', (1,1,1,1,1))):
        vendor += 'case '+old+':'+''.join('InitSpd_Pon_'+n+'='+str(v)+';' for n,v in
                                         zip(('TXPLL','TX','RX','ANA','Preset'), values))+'break;'
        reference += '['+new+']={'+','.join('.'+n+'='+str(v) for n,v in
                                          zip(('txpll','tx','rx','ana','preset'),values))+'},'
    vendor += '}}'
    reference += '};'
    xpon = '''int xsgmii_chg(int xsgmii) {
        switch(xsgmii_bk) {case USXGMII: speed=7; break;}
        switch(xsgmii) {case USXGMII: SCU_SetModSel(1); SET_WAN_CONF(wan_cfg|0x12); break;}
    }'''
    common = '''int airoha_pcs_pon_config_rx(int mode) { switch(mode) {
        case AIROHA_PCS_PON_MODE_EPON_10G_10G:
        wan_sel=FIELD_PREP(AIROHA_SCU_WAN_SEL,7); break;
    }}'''
    header = '#define AIROHA_SCU_WAN_SEL_USXGMII FIELD_PREP_CONST(AIROHA_SCU_WAN_SEL,0x12)\n'
    return vendor, xpon, reference, common, header


class PcsRateContractTest(unittest.TestCase):
    def test_equal_rates_do_not_hide_different_wan_routes(self):
        report = compare(*fixture())
        self.assertTrue(all(v['selectors_equal'] for v in report['vectors'].values()))
        self.assertEqual(report['vendor_dsl_wan_selector'], 18)
        self.assertEqual(report['reference_ethernet_usxgmii_wan_selector'], 18)
        self.assertEqual(report['reference_optical_epon_10g10g_wan_selector'], 7)
        self.assertEqual(len(report['gpon_vs_dsl_differing_selectors']), 5)

    def test_rate_change_is_reported_instead_of_assumed_equivalent(self):
        inputs = list(fixture())
        inputs[2] = inputs[2].replace('.txpll=1', '.txpll=9')
        self.assertFalse(compare(*inputs)['vectors']['dsl_usxgmii_rate']['selectors_equal'])

    def test_unsupported_expression_or_missing_field_is_rejected(self):
        vendor, _, reference, _, _ = fixture()
        for source in (vendor.replace('InitSpd_Pon_TXPLL=1;', 'InitSpd_Pon_TXPLL=1+0;'),
                       vendor.replace('InitSpd_Pon_TXPLL=1;', '')):
            with self.assertRaises(ValueError):
                vendor_vector(source, 'Sync_XEPON')
        with self.assertRaises(ValueError):
            reference_vector(reference.replace('.txpll=1', '.txpll=SOME_MACRO'),
                             'AIROHA_PCS_PON_MODE_EPON_10G_10G')

    def test_ambiguous_function_case_and_selector_are_rejected(self):
        inputs = fixture()
        with self.assertRaises(ValueError):
            vendor_vector(inputs[0]+inputs[0], 'Sync_XEPON')
        with self.assertRaises(ValueError):
            vendor_vector(inputs[0].replace('case Sync_XEPON:', 'case Sync_XEPON: case Alias:'), 'Sync_XEPON')
        changed = list(inputs)
        changed[4] += changed[4]
        with self.assertRaises(ValueError):
            compare(*changed)

    def test_comments_and_literal_braces_do_not_truncate_function(self):
        source = 'void example(int x) { /* } */ log("a } // literal"); x++; }'
        body = function_body(source, 'example')
        self.assertIn('x++;', body)
        self.assertIn('// literal', body)

    def test_conditional_call_is_not_mistaken_for_a_definition(self):
        source = 'static bool helper(int n) { return n; }\nvoid caller(void) { if (!helper(1)) { return; } }'
        self.assertEqual(function_body(source, 'helper').strip(), 'return n;')


if __name__ == '__main__':
    unittest.main()
