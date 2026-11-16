# SPDX-License-Identifier: GPL-2.0-only
"""Compare explicit source-derived PMA selector vectors; never program hardware.

This is a bounded grammar checker, not a C preprocessor or semantic equivalence
proof. Unsupported/ambiguous expressions are rejected instead of evaluated.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

FIELDS = ('txpll', 'tx', 'rx', 'ana', 'preset')
VENDOR = dict(zip(('TXPLL', 'TX', 'RX', 'ANA', 'Preset'), FIELDS))
NUMBER = r'(?:0[xX][0-9a-fA-F]+|[0-9]+)'


def uncomment(text):
    token = r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*'
    return re.sub(token, lambda m: '' if m[0].startswith('/') else m[0], text, flags=re.S)


def function_body(text, name):
    # Strings are left in place; selected functions must have balanced braces.
    text = uncomment(text)
    literals = r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\''
    masked = re.sub(literals, lambda m: re.sub(r'[^\n]', ' ', m[0]), text)
    matches = list(re.finditer(r'(?:^|[;}\n])\s*[A-Za-z_][A-Za-z0-9_ \t*\n]*?\b'+
                              re.escape(name)+r'\s*\([^;{}]*\)\s*\{', masked))
    if len(matches) != 1:
        raise ValueError('Function definition not unique: '+name)
    return braced_body(text, matches[0].end())


def braced_body(text, start):
    depth = 1
    cursor = start
    while cursor < len(text):
        char = text[cursor]
        if char in ('"', "'"):
            quote = char
            cursor += 1
            while cursor < len(text) and text[cursor] != quote:
                cursor += 2 if text[cursor] == '\\' else 1
            if cursor >= len(text):
                raise ValueError('Unterminated source literal')
        elif char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if not depth:
                return text[start:cursor]
        cursor += 1
    raise ValueError('Unterminated function body')


def switch_body(body, expression):
    matches = list(re.finditer(r'\bswitch\s*\(\s*'+re.escape(expression)+r'\s*\)\s*\{', body))
    if len(matches) != 1:
        raise ValueError('Switch expression not unique')
    return braced_body(body, matches[0].end())


def case_body(body, label):
    matches = list(re.finditer(r'\bcase\s+'+re.escape(label)+r'\s*:', body))
    if len(matches) != 1:
        raise ValueError('Case label not unique: '+label)
    tail = body[matches[0].end():]
    end = re.search(r'\bbreak\s*;', tail)
    if not end or re.search(r'\b(?:case|default)\b', tail[:end.start()]):
        raise ValueError('Unsupported fallthrough or missing break')
    return tail[:end.start()]


def vendor_vector(text, label):
    body = case_body(function_body(text, 'pon_WanSelInit'), label)
    pattern = r'InitSpd_Pon_(TXPLL|TX|RX|ANA|Preset)\s*=\s*('+NUMBER+r')\s*;'
    entries = re.findall(pattern, body)
    if re.sub(pattern, '', body).strip() or len(entries) != 5 or len({e[0] for e in entries}) != 5:
        raise ValueError('Unsupported or incomplete vendor selector case')
    values = {VENDOR[name]: int(value, 16 if value.lower().startswith('0x') else 10) for name, value in entries}
    return {key: values[key] for key in FIELDS}


def reference_vector(text, label):
    text = uncomment(text)
    matches = re.findall(r'\[\s*'+re.escape(label)+r'\s*\]\s*=\s*\{([^{}]*)\}', text)
    if len(matches) != 1:
        raise ValueError('Reference selector entry not unique')
    pattern = r'\.([A-Za-z_]+)\s*=\s*('+NUMBER+r')\s*,?'
    entries = re.findall(pattern, matches[0])
    if re.sub(pattern, '', matches[0]).strip() or len(entries) != 5 or {e[0] for e in entries} != set(FIELDS):
        raise ValueError('Unsupported or incomplete reference selectors')
    values = {name: int(value, 16 if value.lower().startswith('0x') else 10) for name, value in entries}
    return {key: values[key] for key in FIELDS}


def compare(vendor_pma, vendor_xpon, reference_pma, reference_common, reference_header):
    vectors = {}
    for label, old, new in (('gpon', 'Async_GPON', 'AIROHA_PCS_PON_MODE_GPON'),
                            ('dsl_usxgmii_rate', 'Sync_XEPON', 'AIROHA_PCS_PON_MODE_EPON_10G_10G')):
        first, second = vendor_vector(vendor_pma, old), reference_vector(reference_pma, new)
        vectors[label] = {'vendor_case': old, 'reference_entry': new, 'vendor': first,
                          'reference': second, 'selectors_equal': first == second}
    xpon = case_body(switch_body(function_body(vendor_xpon, 'xsgmii_chg'), 'xsgmii'), 'USXGMII')
    old_wan = re.findall(r'SET_WAN_CONF\(\s*wan_cfg\s*\|\s*('+NUMBER+r')\s*\)', xpon)
    old_xsi = re.findall(r'SCU_SetModSel\(\s*('+NUMBER+r')\s*\)', xpon)
    new_wan = re.findall(r'^#define\s+AIROHA_SCU_WAN_SEL_USXGMII\s+FIELD_PREP_CONST\(\s*AIROHA_SCU_WAN_SEL\s*,\s*('+NUMBER+r')\s*\)',
                         uncomment(reference_header), re.M)
    optical = case_body(function_body(reference_common, 'airoha_pcs_pon_config_rx'),
                        'AIROHA_PCS_PON_MODE_EPON_10G_10G')
    optical_wan = re.findall(r'wan_sel\s*=\s*FIELD_PREP\(\s*AIROHA_SCU_WAN_SEL\s*,\s*('+NUMBER+r')\s*\)', optical)
    if any(len(values) != 1 for values in (old_wan, old_xsi, new_wan, optical_wan)):
        raise ValueError('WAN/XSI selector expression not unique or unsupported')
    number = lambda s: int(s, 16 if s.lower().startswith('0x') else 10)
    changed = [key for key in FIELDS if vectors['gpon']['reference'][key] != vectors['dsl_usxgmii_rate']['reference'][key]]
    return {'vectors': vectors, 'gpon_vs_dsl_differing_selectors': changed,
            'vendor_dsl_wan_selector': number(old_wan[0]), 'vendor_dsl_xsi_selector': number(old_xsi[0]),
            'reference_ethernet_usxgmii_wan_selector': number(new_wan[0]),
            'reference_optical_epon_10g10g_wan_selector': number(optical_wan[0]),
            'scope': 'selected numeric source contract; not complete programming sequence or runtime equivalence',
            'hardware_access': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('vendor-pma', 'vendor-xpon', 'reference-pma', 'reference-common', 'reference-header'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    inputs, sources = [], []
    for name in ('vendor_pma', 'vendor_xpon', 'reference_pma', 'reference_common', 'reference_header'):
        path = getattr(args, name)
        if not 0 < path.stat().st_size <= 4*1024*1024:
            raise ValueError('Source exceeds 4 MiB input bound')
        data = path.read_bytes()
        sources.append({'role':name,'file':path.name,'sha256':hashlib.sha256(data).hexdigest()})
        inputs.append(data.decode('utf-8'))
    result = compare(*inputs)
    result['sources'] = sources
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'selector_vectors_equal': all(v['selectors_equal'] for v in result['vectors'].values()),
                      'hardware_access': False}))


if __name__ == '__main__':
    main()
