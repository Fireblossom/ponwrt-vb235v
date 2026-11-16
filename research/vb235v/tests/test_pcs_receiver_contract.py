# SPDX-License-Identifier: GPL-2.0-only
"""Synthetic receiver-contract shapes, not captured vendor source."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from pcs_receiver_contract import compare


def fixture():
    div='AN7583_PON_ANA_RG_XPON_RX_PHYCK_DIV'
    mon='AN7583_PON_ANA_RG_XPON_CDR_PR_MONPR_EN'
    bus='AN7583_PON_ANA_RG_XPON_RX_BUSBIT_SEL'
    fields=((div,7,0,0x21),(div,9,8,2),(div,16,16,1),(mon,2,2,1),(bus,24,24,1),(bus,16,16,0))
    vendor='void XPON_XFI_RX_Setting(int pon_Spd) { if(pon_Spd==Sync_XEPON) {'
    vendor+=''.join('IO_SPHYA_REG_BITS(%s,%d,%d,%d);' % row for row in fields)+'}}\n'
    vendor+='void fiber_plug_reset(int s) { switch(s) {case XFI_PON_FIRST_PLUG_IN: XPON_XFI_RX_Setting(0); XPON_TDC_off(); /* XPON_TDC_on(); */ XPON_DIG_reset(); break;}}\n'
    vendor+='void XPON_DIG_reset(void) {'
    vendor+=''.join('IO_SPHYA_REG_BITS(AN7583_PON_PMA_SW_RST_SET,%d,%d,0);' % (n,n) for n in range(7))
    vendor+='udelay(10);'
    vendor+=''.join('IO_SPHYA_REG_BITS(AN7583_PON_PMA_SW_RST_SET,%d,%d,1);' % (n,n) for n in reversed(range(7)))+'}\n'
    header='#define XPON_PMA_BASE (0x10000000)\n'
    header+=''.join('#define %s XPON_PMA_BASE+0x%x\n' % pair for pair in ((div,0x10),(mon,0x20),(bus,0x30)))
    reference='''void an7583_pcs_common_phya_rx(void) { switch(r) {case 1: case 2:
        phyck_div=0; phyck_sel=1; phyck_rstb=false; cdr_pr_xfick_en=false; phyck_sel_force=false; break;}
        regmap_update_bits(m,r,AIROHA_PCS_ANA_RX_PHY_CK_SEL_FORCE | AIROHA_PCS_ANA_RX_PHY_CK_SEL,
            phyck_sel_force ? AIROHA_PCS_ANA_RX_PHY_CK_SEL_FORCE : 0);
    }
    void an7583_pcs_first_plug_in(void) { an7583_pcs_dig_reset_release(p,i); an7583_pcs_pon_tdc_on(p,i); }
    void an7583_pcs_dig_reset_release(void) { regmap_set_bits(m,r,v); usleep_range(100,200); }
    '''
    return vendor,header,reference


class PcsReceiverContractTest(unittest.TestCase):
    def test_fields_and_direct_sequences_are_kept_separate(self):
        result=compare(*fixture())
        self.assertEqual(result['differing_clock_fields'],5)
        self.assertEqual(result['receiver_clock_fields'][0]['vendor_xfi_value'],0x21)
        self.assertEqual(result['receiver_clock_fields'][0]['physical_address_from_vendor_source'],'0x10000010')
        self.assertFalse(result['tdc_sequence']['vendor_xfi_case_explicit_tdc_on'])
        self.assertTrue(result['tdc_sequence']['reference_pon_first_plug_explicit_tdc_on'])
        self.assertEqual(result['post_calibration_reset']['vendor_clear_bit_order'],list(range(7)))

    def test_missing_or_reordered_field_and_unrecognized_header_fail(self):
        vendor,header,reference=fixture()
        cases=((vendor.replace(',7,0,33',',6,0,33'),header,reference),
               (vendor,header.replace('0x10000000','BASE_ALIAS'),reference),
               (vendor,header,reference.replace('phyck_sel=1','phyck_sel=OTHER_VALUE')))
        for args in cases:
            with self.assertRaises(ValueError):
                compare(*args)

    def test_changed_profile_or_missing_reset_delay_requires_review(self):
        vendor,header,reference=fixture()
        with self.assertRaises(ValueError):
            compare(vendor.replace('udelay(10);',''),header,reference)
        with self.assertRaises(ValueError):
            compare(vendor,header,reference.replace('an7583_pcs_pon_tdc_on(p,i);','if(pon_ethernet) {}'))


if __name__ == '__main__':
    unittest.main()
