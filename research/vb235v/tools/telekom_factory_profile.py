#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Cross-check the original Telekom automatic DSL profile and export it locally.

Only the pinned read-only firmware's ISP database and quick-setup page are
accepted. This tool does not read saved customer accounts, connect to an ACS,
configure a modem, start PPPoE or send credentials over a network.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import zlib

PROFILE_SHA256 = 'a1a6db3f7e4810547dee6d68e63931875685bdf633f76b92e40d3d729d6e6ac0'
UI_SHA256 = 'e24a82123335e5989b3250b277cc767b50ab2f3b8aa315a0eb946ad436b178dd'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate provider JSON key')
        result[key] = value
    return result


def normalize(config):
    require(type(config) is dict, 'Invalid automatic DSL configuration')
    candidates = config.get('internet')
    require(type(candidates) is list and len(candidates) == 2, 'Unexpected Telekom candidate list')
    expected = [
        {'name': 'Telekom_ADSL', 'vpi': 1, 'vci': 32, 'vtag': 7,
         'atm_encap': 'LLC', 'access_mode': 'ADSL', 'conn_type': 'PPPoE'},
        {'name': 'Telekom_VDSL', 'vid': 7, 'access_mode': 'VDSL', 'conn_type': 'PPPoE'},
    ]
    require(candidates == expected, 'Transport settings differ from the verified factory profile')
    for candidate in candidates:
        for key in ('vpi', 'vci', 'vtag', 'vid'):
            if key in candidate:
                require(type(candidate[key]) is int, 'Invalid provider integer type')
    return {
        'schema': 1, 'id': 'de-telekom-dsl-auto', 'country': 'DE', 'provider': 'Telekom',
        'automatic_connection': True, 'manual_credentials_required': False,
        'credentials_source': 'verified-factory-autodetect-preset',
        'candidates': [
            {'id': 'adsl', 'line_modes': ['adsl', 'adsl2', 'adsl2plus'],
             'bearer': 'atm', 'vpi': 1, 'vci': 32, 'atm_encapsulation': 'llc',
             'vlan_id': 7, 'protocol': 'pppoe', 'ipv4': True, 'ipv6': True},
            {'id': 'vdsl', 'line_modes': ['vdsl', 'vdsl2'], 'bearer': 'ptm',
             'vlan_id': 7, 'protocol': 'pppoe', 'ipv4': True, 'ipv6': True},
        ],
        'vlan_placement': 'requires-endpoint-host-path-validation',
        'acs_endpoint': None, 'personal_account_download_verified': False,
        'telephone_provisioning_verified': False, 'hardware_connection_verified': False,
    }


def select_candidate(profile, line_mode):
    require(type(line_mode) is str, 'Missing line mode')
    mode = line_mode.strip().lower().replace(' ', '').replace('+', 'plus')
    choices = [candidate for candidate in profile['candidates'] if mode in candidate['line_modes']]
    require(len(choices) == 1, 'DSL line mode is not ready or is unsupported')
    return choices[0]


def check_explicit_ip_modes(data):
    for family in ('ipv4', 'ipv6'):
        settings = data.get(family)
        require(type(settings) is dict and type(settings.get('wan')) is dict and
                settings['wan'].get('enable') is True,
                'Explicit Telekom IP-family enable flag differs: ' + family)


def cross_check(config, ui):
    profile = normalize(config)
    user = re.search(r'var\s+telekomUsr\s*=\s*"([^"\r\n]+)"\s*;', ui)
    password = re.search(r'var\s+telekomPwd\s*=\s*"([^"\r\n]+)"\s*;', ui)
    require(user is not None and password is not None, 'Missing UI automatic-login preset')
    preset_user = config.get('preset_pppoe_username')
    preset_password = config.get('preset_pppoe_password')
    require(type(preset_user) is str and type(preset_password) is str and
            1 <= len(preset_user) <= 128 and 1 <= len(preset_password) <= 128,
            'Invalid factory login preset')
    require(user.group(1) == preset_user and password.group(1) == preset_password,
            'Factory database and automatic-setup credentials disagree')
    require(all(32 <= ord(c) < 127 for c in preset_user + preset_password),
            'Unexpected control characters in the factory preset')
    require(all(value in ui for value in
                ('DEV2_X_TP_AUTODETECT', 'autoDetectState', 'PPPUsername', 'PPPPassword')),
            'Missing automatic-detection backend contract')
    return profile, {'username': preset_user, 'password': preset_password,
                     'scope': 'static-factory-provider-preset-not-a-saved-customer-account'}


def inspect_factory(root):
    profile_path = root / 'web/js/ispprofileV3.json.gz'
    ui_path = root / 'web/main/qsIsp.htm'
    require(profile_path.stat().st_size <= 65536 and ui_path.stat().st_size <= 262144,
            'Factory input exceeds its size budget')
    compressed = profile_path.read_bytes()
    ui_bytes = ui_path.read_bytes()
    require(hashlib.sha256(compressed).hexdigest() == PROFILE_SHA256 and
            hashlib.sha256(ui_bytes).hexdigest() == UI_SHA256,
            'Factory sources differ from the verified read-only firmware')
    decoder = zlib.decompressobj(31)
    decoded = decoder.decompress(compressed, 2 * 1024 * 1024 + 1)
    require(len(decoded) <= 2 * 1024 * 1024 and decoder.eof and not decoder.unused_data,
            'Unsupported or oversized compressed provider database')
    database = json.loads(decoded.decode('utf8'), object_pairs_hook=unique_object)
    telekom = database['region_isp']['DE']['Telekom']
    profile, login = cross_check(telekom['Auto_DSL']['config'], ui_bytes.decode('utf8'))
    # Independently check the two explicit presets, not just the Auto_DSL list.
    for name, expected_mode in [('Telekom_ADSL', 'adsl'), ('Telekom_VDSL', 'vdsl')]:
        data = telekom[name]['internet']
        check_explicit_ip_modes(data)
        require(data['dial_mode_type'] == 'pppoe' and data['vlan_info'] == {'enable': True, 'vlan_id': 7},
                'Explicit provider preset disagrees with automatic detection')
        require(data['dsl_info']['xdsl_mode_type'] == expected_mode, 'Explicit line mode differs')
        if expected_mode == 'adsl':
            require(data['dsl_info']['adsl_info'] == {'vpi': 1, 'vci': 32, 'atm_encap': 'LLC'},
                    'Explicit ADSL PVC differs')
    evidence = {
        'profile_sha256': PROFILE_SHA256, 'quick_setup_sha256': UI_SHA256,
        'database_UI_login_preset_equal': True, 'explicit_and_automatic_transports_equal': True,
        'explicit_ipv4_ipv6_enable_flags_cross_checked': True,
        'factory_preset_present': True, 'customer_saved_credentials_read': False,
        'backend_object': 'DEV2_X_TP_AUTODETECT', 'backend_state': 'Requested',
        'acs_contacted': False, 'router_commands_sent': False,
    }
    return profile, login, evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('extracted_factory_root', type=Path)
    parser.add_argument('--private-output', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    profile, login, evidence = inspect_factory(args.extracted_factory_root)
    if args.private_output:
        require(not args.private_output.exists(), 'Private output already exists')
        args.private_output.mkdir(mode=0o700, parents=True)
        (args.private_output / 'telekom-de.json').write_bytes((json.dumps(profile, indent=2) + '\n').encode('utf8'))
        secret_path = args.private_output / 'telekom-de-login.json'
        secret_path.write_bytes((json.dumps(login, indent=2) + '\n').encode('utf8'))
        secret_path.chmod(0o600)
        evidence['factory_preset_exported_locally'] = True
    report = {'profile': profile, 'evidence': evidence}
    if args.report:
        args.report.write_bytes((json.dumps(report, indent=2) + '\n').encode('utf8'))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
