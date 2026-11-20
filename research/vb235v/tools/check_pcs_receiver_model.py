#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Execute pinned receiver C functions against memory-only register/call models.

No driver is loaded and there is no device, socket, ioctl or register backend.
This checks selected control/data flow, not calibration, electrical timing or
the complete nested PHY bring-up sequence.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from check_pcs_profile import functions
from pcs_rate_contract import braced_body, function_body, uncomment
from pcs_receiver_contract import compare

PINS = {
    'reference': '67a7c9c9a6c59c434a4931df3047da45bc6db000ce7ebb5e00b3fc613fdc5aaf',
    'candidate': '85f05dd453d3d7e3384e4262c9e56131e82afb51db029964e4c872b872c51214',
    'header': 'cc58b940119812b389c6487a2bd65d6b88e79ae38766e0e8810bf47dda724bb2',
    'phy': '760034201b62d69c1d9fd116eed7beaeaded1a6a7909288a8afbe4f3a64deaf0',
    'api': '10195a7891a22c9f3df714331d19bc236021127f3cb0fea62aa753deec7fb260',
    'vendor': 'c7828d2d722f1527c339959a4d8b836c194b000d028e403a314b4ba0ebd19236',
    'vendor_header': '349ec7c24207557adf891cf290edec7b17ca6001793eecb04c408c15513cc34e',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_source(path, role):
    require(0 < path.stat().st_size <= 4 * 1024 * 1024, 'Source outside input budget: ' + role)
    data = path.read_bytes()
    require(hashlib.sha256(data).hexdigest() == PINS[role], 'Unreviewed source: ' + role)
    return data.decode('utf-8')


def native_definitions(header):
    lines = uncomment(header).splitlines()
    result = []
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if not re.match(r'^#define\s+AIROHA_', line):
            continue
        while line.endswith('\\'):
            require(index < len(lines), 'Truncated native macro')
            line += '\n' + lines[index]
            index += 1
        result.append(line)
    require(len(result) > 500, 'Native register definitions missing')
    return '\n'.join(result) + '\n'


def enum_source(text, pattern):
    matches = re.findall(pattern, uncomment(text), re.S)
    require(len(matches) == 1, 'Expected unique control enum')
    return matches[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel', required=True, type=Path)
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--vendor-pma', required=True, type=Path)
    parser.add_argument('--vendor-header', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    sources = {
        'reference': args.kernel / 'drivers/net/pcs/airoha/pcs-an7583.c',
        'candidate': args.candidate / 'pcs-an7583.c', 'header': args.candidate / 'pcs-airoha.h',
        'phy': args.kernel / 'include/linux/phy.h', 'api': args.kernel / 'include/linux/pcs/pcs-airoha.h',
        'vendor': args.vendor_pma, 'vendor_header': args.vendor_header,
    }
    text = {role: read_source(path, role) for role, path in sources.items()}
    reference, candidate = text['reference'], text['candidate']
    contract = compare(text['vendor'], text['vendor_header'], reference)
    definitions = native_definitions(text['header'])
    definitions += 'enum xfi_port_type {' + enum_source(text['header'], r'enum xfi_port_type\s*\{([^{}]*)\}') + '};\n'
    definitions += 'enum airoha_pcs_pon_mode {' + enum_source(text['api'], r'enum airoha_pcs_pon_mode\s*\{([^{}]*)\}') + '};\n'
    definitions += 'typedef enum {' + enum_source(text['phy'], r'typedef\s+enum\s*\{([^{}]*PHY_INTERFACE_MODE_NA[^{}]*)\}\s*phy_interface_t;') + '} phy_interface_t;\n'
    base = int(re.findall(r'^#define\s+XPON_PMA_BASE\s+\(?\s*(0x[0-9a-fA-F]+)\s*\)?\s*$', text['vendor_header'], re.M)[0], 16)
    offset = re.findall(r'^#define\s+AN7583_PON_PMA_SW_RST_SET\s+XPON_PMA_BASE\s*\+\s*(0x[0-9a-fA-F]+)\s*$', text['vendor_header'], re.M)
    require(len(offset) == 1 and base + int(offset[0], 16) == 0x1fa8e460, 'Unreviewed vendor reset address')
    definitions += '#define AN7583_PON_PMA_SW_RST_SET 0x1fa8e460U\n'
    rates = re.search(r'static const struct an7583_pcs_pon_rate an7583_pcs_pon_rates\[\]\s*=\s*\{', reference)
    require(rates is not None, 'Optical selector table missing')
    bodies = 'static const struct an7583_pcs_pon_rate an7583_pcs_pon_rates[] = {' + braced_body(reference, rates.end()) + '};\n'
    bodies += 'static const struct an7583_pcs_pon_rate *an7583_pcs_pon_rate(struct airoha_pcs_priv *priv) {' + function_body(reference, 'an7583_pcs_pon_rate') + '}\n'
    require(function_body(candidate, 'an7583_pcs_dig_reset_release') == function_body(reference, 'an7583_pcs_dig_reset_release'), 'Default reset helper changed')
    bodies += functions(reference, ['an7583_pcs_dig_reset_release'])
    original = functions(reference, ['an7583_pcs_common_phya_rx', 'an7583_pcs_first_plug_in'])
    original = re.sub(r'\ban7583_pcs_common_phya_rx\b', 'ref_rx', original)
    original = re.sub(r'\ban7583_pcs_first_plug_in\b', 'ref_first_plug', original)
    bodies += original + functions(candidate, ['an7583_pcs_pon_eth_dig_reset', 'an7583_pcs_common_phya_rx', 'an7583_pcs_first_plug_in'])
    bodies += 'static void XPON_DIG_reset(void) {' + function_body(text['vendor'], 'XPON_DIG_reset') + '}\n'
    calls = re.findall(r'\b(an7583_[a-z0-9_]+)\(priv, index(, interface)?\)', function_body(reference, 'an7583_pcs_first_plug_in'))
    backends = []
    ids = {}
    for name, interface in sorted(set(calls)):
        if name == 'an7583_pcs_dig_reset_release':
            continue
        require(name not in ids, 'Ambiguous modeled backend signature')
        number = len(ids) + 1
        ids[name] = number
        extra = ', phy_interface_t interface' if interface else ''
        value = 'interface' if interface else '0'
        backends.append(f'static void {name}(struct airoha_pcs_priv *priv, int index{extra}) {{ record(\'B\',{number},index,{value}); }}')
    for key, name in [('TDC_OFF_ID', 'an7583_pcs_common_phya_tdc_off'), ('TDC_ON_ID', 'an7583_pcs_pon_tdc_on'), ('EO_SCAN_ID', 'an7583_pcs_common_phya_eo_scan')]:
        definitions += f'#define {key} {ids[name]}\n'
    expectations = 'static void check_vendor_clocks(void) {\n'
    for field in contract['receiver_clock_fields']:
        high, low = field['high_bit'], field['low_bit']
        expectations += f" assert(((*location({field['physical_address_from_vendor_source']}U) >> {low}) & {(1 << (high-low+1))-1}U) == {field['vendor_xfi_value']}U);\n"
    expectations += '}\n'
    harness = Path(__file__).with_name('pcs_receiver_harness.c').read_text()
    harness = harness.replace('/* @DEFINITIONS@ */', definitions).replace('/* @BACKENDS@ */', '\n'.join(backends))
    harness = harness.replace('/* @FUNCTIONS@ */', bodies).replace('/* @EXPECTATIONS@ */', expectations)
    compiler = shutil.which('cc')
    require(compiler is not None, 'Native C compiler required')
    with tempfile.TemporaryDirectory() as temporary:
        directory = Path(temporary)
        source = directory / 'model.c'; executable = directory / 'model'
        source.write_bytes(harness.encode())
        built = subprocess.run([compiler, '-std=gnu11', '-O2', '-Wall', '-Wextra', '-Werror',
            '-Wno-unused-parameter', '-Wno-unused-function', str(source), '-o', str(executable)],
            capture_output=True, text=True)
        require(built.returncode == 0, 'Host model compile failed:\n' + built.stderr[:6000])
        run = subprocess.run([str(executable)], capture_output=True, text=True, timeout=15)
        require(run.returncode == 0, 'Receiver model mismatch:\n' + run.stderr[:2000])
        result = json.loads(run.stdout)
    result.update(stage='M59', reviewed_source_sha256=PINS,
                  native_register_masks_used=True, vendor_reset_body_executed_with_memory_model=True,
                  complete_calibration_or_electrical_behavior_verified=False, device_operations=False)
    args.output.write_bytes((json.dumps(result, indent=2) + '\n').encode())
    print(json.dumps(result))


if __name__ == '__main__':
    main()
