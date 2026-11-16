# SPDX-License-Identifier: GPL-2.0-only
"""Check selected receiver source differences; no C execution or hardware I/O.

Reports branch assignments and direct call sequences, not complete C dataflow,
macro semantics, nested backend state, calibration success or electrical timing.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from pcs_rate_contract import case_body, function_body


def require(condition, message):
    if not condition:
        raise ValueError(message)


def compare(vendor, header, reference):
    setting = function_body(vendor,'XPON_XFI_RX_Setting')
    require(re.search(r'if\s*\(\s*pon_Spd\s*==\s*Sync_XEPON\s*\)',setting),'Unsupported XFI setting condition')
    calls = re.findall(r'IO_SPHYA_REG_BITS\(\s*([A-Za-z0-9_]+)\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(0x[0-9a-fA-F]+|\d+)\s*\)',setting)
    require(len(calls)==6,'Expected exactly six XFI field writes')
    expected_fields = (
        ('AN7583_PON_ANA_RG_XPON_RX_PHYCK_DIV',7,0),
        ('AN7583_PON_ANA_RG_XPON_RX_PHYCK_DIV',9,8),
        ('AN7583_PON_ANA_RG_XPON_RX_PHYCK_DIV',16,16),
        ('AN7583_PON_ANA_RG_XPON_CDR_PR_MONPR_EN',2,2),
        ('AN7583_PON_ANA_RG_XPON_RX_BUSBIT_SEL',24,24),
        ('AN7583_PON_ANA_RG_XPON_RX_BUSBIT_SEL',16,16))
    require([(r,int(h),int(l)) for r,h,l,_ in calls]==list(expected_fields),'XFI field order/layout changed')
    base = re.findall(r'^#define\s+XPON_PMA_BASE\s+\(?\s*(0x[0-9a-fA-F]+)\s*\)?\s*$',header,re.M)
    require(len(base)==1,'Unsupported PMA base definition')
    rx = function_body(reference,'an7583_pcs_common_phya_rx')
    branches = re.findall(r'case\s+1:\s*case\s+2:(.*?)break;',rx,re.S)
    require(len(branches)==1,'Unsupported PON RX rate branch')
    selected = {}
    for name in ('phyck_div','phyck_sel','phyck_rstb','cdr_pr_xfick_en','phyck_sel_force'):
        values = re.findall(r'\b'+name+r'\s*=\s*(0x[0-9a-fA-F]+|\d+|true|false)\s*;',branches[0])
        require(len(values)==1,'Unsupported RX field assignment: '+name)
        selected[name] = 1 if values[0]=='true' else 0 if values[0]=='false' else int(values[0],0)
    require(re.search(r'AIROHA_PCS_ANA_RX_PHY_CK_SEL_FORCE\s*\|\s*AIROHA_PCS_ANA_RX_PHY_CK_SEL\s*,\s*phyck_sel_force\s*\?\s*AIROHA_PCS_ANA_RX_PHY_CK_SEL_FORCE\s*:\s*0\s*\)',rx),
            'RX PHY clock select clear is not the reviewed expression')
    labels = ('RX_PHYCK_DIV','RX_PHYCK_SEL','RX_PHYCK_RSTB','CDR_PR_XFICK_EN','RX_PHY_CK_SEL_FORCE','RX_PHY_CK_SEL')
    variables = ('phyck_div','phyck_sel','phyck_rstb','cdr_pr_xfick_en','phyck_sel_force',None)
    entries = []
    for (reg,high,low,value),label,var in zip(calls,labels,variables):
        address = re.findall(r'^#define\s+'+re.escape(reg)+r'\s+XPON_PMA_BASE\s*\+\s*(0x[0-9a-fA-F]+)\s*$',header,re.M)
        require(len(address)==1,'Unsupported register address expression')
        hi,lo = int(high),int(low)
        require(0 <= lo <= hi < 32,'Invalid register field width')
        expected = int(value,0)
        require(expected < 1 << (hi-lo+1),'Field value outside declared width')
        current = selected[var] if var else 0
        entries.append({'field':label,'physical_address_from_vendor_source':hex(int(base[0],16)+int(address[0],16)),
                        'high_bit':hi,'low_bit':lo,'vendor_xfi_value':expected,
                        'reference_pon_rx_rate_1_value':current,'different':expected!=current})
    xfi = case_body(function_body(vendor,'fiber_plug_reset'),'XFI_PON_FIRST_PLUG_IN')
    require(re.search(r'\bXPON_XFI_RX_Setting\s*\(',xfi),'Missing dedicated XFI settings call')
    off = bool(re.search(r'\bXPON_TDC_off\s*\(',xfi))
    on = bool(re.search(r'\bXPON_TDC_on\s*\(',xfi))
    first = function_body(reference,'an7583_pcs_first_plug_in')
    require('pon_ethernet' not in first,'Receiver profile changed; review branch semantics')
    ref_on = bool(re.search(r'\ban7583_pcs_pon_tdc_on\s*\(',first))
    require(re.search(r'\bXPON_DIG_reset\s*\(',xfi) and re.search(r'\ban7583_pcs_dig_reset_release\s*\(',first),
            'Unsupported post-calibration reset calls')
    reset = function_body(vendor,'XPON_DIG_reset')
    pattern = r'IO_SPHYA_REG_BITS\(\s*AN7583_PON_PMA_SW_RST_SET\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*(0x[0-9a-fA-F]+|\d+)\s*\)'
    writes = list(re.finditer(pattern,reset))
    require(len(writes)==14 and all(m[1]==m[2] for m in writes),'Unsupported reset pulse writes')
    require([int(m[3],0) for m in writes]==[0]*7+[1]*7,'Reset pulse is not clear-then-set')
    delay = re.findall(r'udelay\(\s*(\d+)\s*\)',reset[writes[6].end():writes[7].start()])
    require(len(delay)==1,'Missing unique delay between clear and set')
    release = function_body(reference,'an7583_pcs_dig_reset_release')
    release_delay = re.findall(r'\busleep_range\(\s*(\d+)\s*,\s*(\d+)\s*\)',release)
    require(len(release_delay)==1,'Unsupported reference reset-release delay')
    return {'source_contract_only':True,'receiver_clock_fields':entries,
            'differing_clock_fields':sum(row['different'] for row in entries),
            'tdc_sequence':{'vendor_xfi_case_explicit_tdc_off':off,'vendor_xfi_case_explicit_tdc_on':on,
                            'reference_pon_first_plug_explicit_tdc_on':ref_on,
                            'meaning':'direct calls only; nested state transitions are not proven'},
            'post_calibration_reset':{'vendor_clear_bit_order':[int(m[1]) for m in writes[:7]],
                                      'vendor_delay_us':int(delay[0]),'vendor_set_bit_order':[int(m[1]) for m in writes[7:]],
                                      'reference_release_helper_has_clear_operations':bool(re.search(r'\bregmap_clear_bits\s*\(',release)),
                                      'reference_release_delay_range_us':[int(n) for n in release_delay[0]]},
            'hardware_actions':False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('vendor-pma','vendor-header','reference-pma'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    inputs, sources = [], []
    for role in ('vendor_pma','vendor_header','reference_pma'):
        path = getattr(args,role)
        require(0 < path.stat().st_size <= 4*1024*1024,'Source outside 4 MiB input limit')
        data = path.read_bytes()
        inputs.append(data.decode('utf-8'))
        sources.append({'role':role,'file':path.name,'sha256':hashlib.sha256(data).hexdigest()})
    report = compare(*inputs)
    report.update(milestone='M19',sources=sources,kernel_patch_added=False)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(report,stream,indent=2)
        stream.write('\n')
    print(json.dumps({'differing_clock_fields':report['differing_clock_fields'],'hardware_actions':False}))


if __name__ == '__main__':
    main()
