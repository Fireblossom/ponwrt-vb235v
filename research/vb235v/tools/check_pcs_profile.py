# SPDX-License-Identifier: GPL-2.0-only
"""Compile actual PCS functions against host mocks; never access router hardware.

Compares unchanged-profile behavior against an exact pre-change source copy.
This checks modeled control flow, not kernel ABI, register semantics or timing.
Only the reviewed M18 source hashes are accepted before compiling any C.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from pcs_rate_contract import braced_body, function_body, uncomment

METHODS = ('airoha_pcs_setup_scu_pon','airoha_pcs_setup_scu','airoha_pcs_pre_config',
           'airoha_pcs_post_config','airoha_pcs_config','airoha_pcs_inband_caps',
           'airoha_pcs_an_restart','airoha_pcs_get_state','airoha_pcs_link_up','airoha_pcs_link_down',
           'airoha_pcs_pon_config_rx','airoha_pcs_pon_retrain_rx','airoha_pcs_pon_stop_rx',
           'airoha_pcs_pon_get_rx_status')
EXTRA = ('airoha_pcs_interface_supported','airoha_pcs_parse_pon_ethernet')
REVIEWED = {
    'candidate': '4821cff95b020c5ed5990894fb644addafdbc7576ea73b549a8afc4d82296971',
    'reference': '41f8d86c70b053bb0c18c19898c0a67ab0ba786ef3011d2d181d4df077a53e01',
    'private_header': 'cc58b940119812b389c6487a2bd65d6b88e79ae38766e0e8810bf47dda724bb2',
    'pma': '67a7c9c9a6c59c434a4931df3047da45bc6db000ce7ebb5e00b3fc613fdc5aaf',
    'api': '10195a7891a22c9f3df714331d19bc236021127f3cb0fea62aa753deec7fb260',
    'phy': '760034201b62d69c1d9fd116eed7beaeaded1a6a7909288a8afbe4f3a64deaf0',
    'phylink': '27512d25be1d09c7504dacbaa219d907c74ae079fdc91057443f7954d0f41b2b',
    'ethtool': '8c83076d612c76f2a4f3bcef4ad8de510424ba70951b94bf1173400bf6be1bd6',
}


def functions(text, names):
    selected = []
    for name in names:
        pattern = r'(?:^|\n)((?:static\s+)?(?:unsigned\s+int|int|void|bool)\s+'+re.escape(name)+r'\s*\([^;{}]*\))\s*\{'
        matches = list(re.finditer(pattern, text))
        if len(matches) != 1:
            raise ValueError('Selected function not unique: '+name)
        selected.append((matches[0].start(), matches[0][1]+'\n{'+function_body(text,name)+'}\n'))
    return '\n'.join(body for _,body in sorted(selected))


def source(path, role):
    if not 0 < path.stat().st_size <= 4*1024*1024:
        raise ValueError('Unexpected source size')
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != REVIEWED[role]:
        raise ValueError('Source is outside the reviewed M18 snapshot: '+role)
    return data.decode('utf-8')


def bit_enum(text, prefix):
    values = {}
    for name, expression in re.findall(r'\b('+prefix+r'[A-Z0-9_]+)\s*=\s*([^,}]+)',uncomment(text)):
        expression = re.sub(r'BIT\((\d+)\)',lambda m: str(1 << int(m[1])),expression)
        value = 0
        for term in expression.split('|'):
            term = term.strip()
            if term.isdecimal():
                value |= int(term)
            elif term in values:
                value |= values[term]
            else:
                raise ValueError('Unsupported model enum expression')
        if name in values:
            raise ValueError('Repeated model enum name')
        values[name] = value
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kernel', type=Path)
    parser.add_argument('--reference-common', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    compiler = shutil.which('cc')
    if not compiler:
        raise ValueError('Host C compiler is required')
    common_path = args.kernel / 'drivers/net/pcs/airoha/pcs-airoha-common.c'
    header = source(args.kernel / 'drivers/net/pcs/airoha/pcs-airoha.h','private_header')
    common, original = source(common_path,'candidate'), source(args.reference_common,'reference')
    candidate = functions(common, METHODS+EXTRA)
    reference = functions(original, METHODS)
    for name in sorted(METHODS, key=len, reverse=True):
        reference = re.sub(r'\b'+name+r'\b', 'ref_'+name, reference)
    pma = source(args.kernel / 'drivers/net/pcs/airoha/pcs-an7583.c','pma')
    table = re.search(r'static const struct an7583_pcs_pon_rate an7583_pcs_pon_rates\[\]\s*=\s*\{',pma)
    if not table:
        raise ValueError('Missing actual rate table')
    rates = 'static const struct an7583_pcs_pon_rate an7583_pcs_pon_rates[] = {'+braced_body(pma,table.end())+'};\n'
    rate_helper = 'static const struct an7583_pcs_pon_rate *an7583_pcs_pon_rate(struct airoha_pcs_priv *priv) {'+function_body(pma,'an7583_pcs_pon_rate')+'}\n'
    api = source(args.kernel / 'include/linux/pcs/pcs-airoha.h','api')
    enum = re.search(r'enum airoha_pcs_pon_mode\s*\{([^{}]*)\}',uncomment(api))
    if not enum:
        raise ValueError('Missing actual optical mode enum')
    enum_text = 'enum airoha_pcs_pon_mode {'+enum[1]+'};\n'
    phy = source(args.kernel/'include/linux/phy.h','phy')
    phylink = source(args.kernel/'include/linux/phylink.h','phylink')
    ethtool = source(args.kernel/'include/uapi/linux/ethtool.h','ethtool')
    phy_enum = re.search(r'typedef\s+enum\s*\{([^{}]*PHY_INTERFACE_MODE_NA[^{}]*)\}\s*phy_interface_t;',uncomment(phy))
    if not phy_enum:
        raise ValueError('Missing actual PHY interface enum')
    enum_text += 'enum phy_interface_model {'+phy_enum[1]+'};\n'
    controls = bit_enum(phylink,'PHYLINK_PCS_NEG_')
    controls.update(bit_enum(phy,'LINK_INBAND_'))
    for name, value in re.findall(r'^#define\s+((?:SPEED|DUPLEX)_[A-Z0-9_]+)\s+(\(?-?(?:0x[0-9a-fA-F]+|[0-9]+)\)?)',ethtool,re.M):
        controls[name]=int(value.strip('()'),16 if '0x' in value.lower() else 10)
    all_text = reference+candidate+rates
    identifiers = set(re.findall(r'\b(?:AIROHA_[A-Z0-9_]+|PHY_INTERFACE_MODE_[A-Z0-9_]+|PHYLINK_[A-Z0-9_]+|LINK_INBAND_[A-Z0-9_]+|SPEED_[A-Z0-9_]+|DUPLEX_[A-Z0-9_]+)\b',all_text))
    identifiers |= {'PHY_INTERFACE_MODE_NA','PHY_INTERFACE_MODE_INTERNAL','SPEED_1000','DUPLEX_FULL'}
    enum_names = set(re.findall(r'(?:AIROHA_PCS_PON_MODE|PHY_INTERFACE_MODE)_[A-Z0-9_]+',enum_text))
    # Preserve the actual SCU routing definitions. Other model constants are
    # unique deterministic placeholders shared by both versions, not an ABI.
    definitions = dict(re.findall(r'^#define\s+(AIROHA_SCU_[A-Z0-9_]+)\s+([^\n]+)',header,re.M))
    exact = {name:body.strip() for name,body in definitions.items() if name in identifiers}
    pending = list(exact.values())
    while pending:
        for dependency in re.findall(r'AIROHA_SCU_[A-Z0-9_]+',pending.pop()):
            if dependency not in exact:
                if dependency not in definitions:
                    raise ValueError('Missing SCU definition')
                exact[dependency]=definitions[dependency].strip()
                pending.append(exact[dependency])
    constants = enum_text+'\n'.join('#define '+name+' '+value for name,value in sorted(exact.items()))+'\n'
    constants += '\n'.join('#define '+name+' '+str(value) for name,value in sorted(controls.items()))+'\n'
    constants += '\n'.join('#define '+name+' '+str(1000+i) for i,name in enumerate(sorted(identifiers-set(exact)-enum_names-set(controls))))+'\n'
    harness_path = Path(__file__).with_name('pcs_profile_harness.c')
    harness = harness_path.read_text().replace('/* CONSTANTS_INSERT */', constants)
    harness = harness.replace('/* FUNCTIONS_INSERT */',reference+candidate+rates+rate_helper)
    probe = function_body(common,'airoha_pcs_probe')
    if probe.index('airoha_pcs_parse_pon_ethernet(priv)') > probe.index('data->init(priv)'):
        raise ValueError('Profile parsed after backend initialization')
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root/'check.c').write_text(harness)
        result = subprocess.run([compiler,'-std=c11','-Wall','-Wextra','-Werror',
            '-Wno-unused-parameter','-Wno-unused-variable','-Wno-unused-but-set-variable',
            str(root/'check.c'),'-o',str(root/'check')],capture_output=True,text=True)
        if result.returncode:
            raise RuntimeError('Host harness compilation failed:\n'+result.stderr[:6000])
        checked = subprocess.run([str(root/'check')],capture_output=True,text=True,timeout=10)
        if checked.returncode:
            raise RuntimeError('Host harness failed: '+checked.stderr)
        report = json.loads(checked.stdout)
    report.update(scope='actual selected functions with host mocks; not hardware or ABI validation',
                  probe_source_order_verified=True,
                  kernel_probe_executed=False,
                  candidate_common_sha256=hashlib.sha256(common_path.read_bytes()).hexdigest(),
                  reference_common_sha256=hashlib.sha256(args.reference_common.read_bytes()).hexdigest(),
                  harness_sha256=hashlib.sha256(harness_path.read_bytes()).hexdigest(),
                  all_input_sources_match_reviewed_hashes=True,
                  control_constants_from_reviewed_kernel_headers=True,
                  hardware_access=False)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(report,stream,indent=2)
        stream.write('\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
