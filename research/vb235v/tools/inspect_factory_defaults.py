#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Inspect only the pinned read-only factory defaults; never output raw secrets.

Requires cryptography. Derives the AES parameters from the pinned original ELF,
without loading it into the host process. No device or network backend exists.
"""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET

from elf_dynamic_inventory import SharedObject

LIB_SHA256 = '467e0faffa63fd8f7b1ccc39e796c673c6a73753d65fd2cdefc5cd6a0e5ef1b8'
CONFIG_SHA256 = '600b318ba00ff59dc5e122d61774b236983ffe5b74f19de9839b42818cc43275'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def remove_padding(data):
    require(bool(data) and len(data) % 16 == 0, 'Invalid AES block framing')
    size = data[-1]
    require(1 <= size <= 16 and data[-size:] == bytes([size]) * size,
            'Invalid PKCS#7 padding')
    return data[:-size]


def parse_vendor_xml(data):
    require(len(data) <= 1024 * 1024, 'Factory XML exceeds budget')
    require(b'<!' not in data, 'XML declarations/entities/comments are not accepted')
    text = data.decode('utf-8', 'strict')
    # This firmware writes one unquoted val per line, including empty values.
    text, values = re.subn(
        r'(?m)^(\s*<[A-Za-z_][A-Za-z0-9_.:-]*\s+val=)([^\r\n]*?)([ \t]*/>)[ \t]*$',
        lambda match: match[1] + '"' + html.escape(match[2], quote=True) + '"' + match[3], text)
    text, instances = re.subn(r'(\s+(?:instance|nextInstance)=)([0-9]+)(?=[\s/>])',
                              r'\1"\2"', text)
    root = ET.fromstring(text)
    require(root.tag == 'DslCpeConfig', 'Unexpected factory XML root')
    require(sum(1 for _ in root.iter()) <= 20000, 'Too many factory XML elements')
    return root, {'quoted_values': values, 'quoted_instance_attributes': instances}


def management_report(root):
    servers = list(root.iter('ManagementServer'))
    require(len(servers) == 1, 'Expected exactly one factory ManagementServer')
    rows = {}
    for child in servers[0]:
        require(child.tag not in rows, 'Duplicate ManagementServer field')
        rows[child.tag] = child.get('val')
    require(rows.get('EnableCWMP') in ('0', '1') and
            rows.get('PeriodicInformEnable') in ('0', '1'), 'Missing CWMP enable flags')
    # Explicit allowlist: no credentials, tokens, URLs or arbitrary field values.
    return {'cwmp_enabled': rows['EnableCWMP'] == '1',
            'periodic_inform_enabled': rows['PeriodicInformEnable'] == '1',
            'acs_url_present': bool(rows.get('URL')),
            'live_configuration_inspected': False,
            'telekom_acs_verified': False,
            'personal_account_download_verified': False,
            'telephone_provisioning_verified': False}


def factory_parameters(module):
    symbols = {symbol['name']: symbol for table in module.symbol_tables.values()
               for symbol in table if symbol['section'] and symbol['name']}
    require(symbols['oal_sys_aes_decryptFile']['value'] == 0x319db8,
            'Factory AES wrapper differs')
    # The pinned wrapper loads gKey and gIv through these GOT witnesses.
    slots = module.got_slots()
    for pc, words, slot, name in [
        (0x319e44, (0xf0000ba0, 0xf9448c00), 0x490918, 'gKey'),
        (0x319e6c, (0xf0000ba0, 0xf946e000), 0x490dc0, 'gIv'),
    ]:
        require(struct.unpack('<II', module.at(pc, 8, executable=True)) == words
                and slots.get(slot) == name, 'Factory AES load witness differs')
    relatives = {}
    for section in module.sections:
        if section['type'] != 4:
            continue
        for offset in range(0, section['size'], 24):
            address, info, addend = struct.unpack_from('<QQq', module.payload(section), offset)
            if info & 0xffffffff == 1027:
                require(address not in relatives, 'Duplicate ELF relative relocation')
                relatives[address] = addend
    result = []
    for name in ('gKey', 'gIv'):
        symbol = symbols[name]
        require(symbol['size'] == 8 and symbol['value'] in relatives, 'Missing factory AES parameter')
        value = module.at(relatives[symbol['value']], 17)
        require(value[-1] == 0 and 0 not in value[:16], 'Unexpected factory AES parameter length')
        result.append(value[:16])
    return result


def inspect(library, encrypted):
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    module = SharedObject(library)
    require(hashlib.sha256(module.data).hexdigest() == LIB_SHA256, 'Unexpected original management library')
    require(encrypted.stat().st_size <= 1024 * 1024, 'Factory ciphertext exceeds budget')
    source = encrypted.read_bytes()
    require(hashlib.sha256(source).hexdigest() == CONFIG_SHA256, 'Unexpected read-only factory configuration')
    key, iv = factory_parameters(module)
    decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
    padded = decryptor.update(source) + decryptor.finalize()
    decoded = remove_padding(padded)
    encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    require(encryptor.update(padded) + encryptor.finalize() == source, 'Factory AES roundtrip differs')
    root, normalization = parse_vendor_xml(decoded)
    return {'schema': 1, 'source': 'pinned-read-only-original-rootfs',
            'library_sha256': LIB_SHA256, 'ciphertext_sha256': CONFIG_SHA256,
            'algorithm': 'AES-128-CBC', 'padding': 'PKCS#7',
            'decoded_bytes': len(decoded), 'decoded_sha256': hashlib.sha256(decoded).hexdigest(),
            'ciphertext_roundtrip_verified': True,
            'xml_root': root.tag, 'xml_elements': sum(1 for _ in root.iter()),
            'vendor_xml_normalization': normalization,
            'management': management_report(root), 'raw_configuration_exported': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', required=True, type=Path)
    parser.add_argument('--factory-config', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    report = inspect(args.library, args.factory_config)
    args.output.write_bytes((json.dumps(report, indent=2) + '\n').encode('utf-8'))
    print(json.dumps(report['management']))


if __name__ == '__main__':
    main()
