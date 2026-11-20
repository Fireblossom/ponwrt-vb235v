#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Audit compile-only MT7990 outputs without loading modules or enabling PCIe."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess

from elf_inventory import inspect, bounded, cstring

BASELINE = 'dcf140cb1d5d2c15c1d7c353c95c4c2a56629820'
VERSION = '2026.10.28~0936617d'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def record(path):
    data = path.read_bytes()
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def aliases(path):
    data = path.read_bytes()
    h = struct.unpack('<16sHHIQQQIHHHHHH', bounded(data, 0, 64))
    require(h[1] == 1 and h[2] == 183, 'Module must be AArch64 ET_REL')
    require(h[11] == 64 and 0 < h[12] <= 16384 and h[13] < h[12], 'Invalid section table')
    sections = [struct.unpack('<IIQQQQIIQQ', bounded(data, h[6] + i * 64, 64)) for i in range(h[12])]
    names = bounded(data, sections[h[13]][4], sections[h[13]][5])
    tables = [s for s in sections if cstring(names, s[0]) == '.modinfo']
    require(len(tables) == 1, 'Expected exactly one modinfo section')
    return sorted(e[6:].decode('ascii') for e in bounded(data, tables[0][4], tables[0][5]).split(b'\0') if e.startswith(b'alias='))


def audit(tree):
    head = subprocess.check_output(['git', '-C', str(tree), 'rev-parse', 'HEAD'], text=True).strip()
    require(head == BASELINE, 'Unexpected PonWrt baseline')
    config = (tree / '.config').read_text().splitlines()
    for line in ('CONFIG_TARGET_airoha_vb235v_DEVICE_tplink_vb235v-ram-lan=y',
                 'CONFIG_PACKAGE_kmod-mt7996e=m', 'CONFIG_PACKAGE_kmod-mt7990-firmware=m'):
        require(line in config, 'Missing selection: ' + line)
    require('CONFIG_TARGET_airoha_an7581=y' not in config, 'Unexpected AN7581 acceleration selection')
    linux = tree / 'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v'
    mt76 = linux / ('mt76-' + VERSION)
    module = mt76 / '.pkgdir/kmod-mt7996e/lib/modules/6.18.60/mt7996e.ko'
    inventory = inspect(module)
    require(inventory['elf_machine'] == 183, 'Wrong module architecture')
    info = inventory['modinfo']
    require(info.get('name') == ['mt7996e'], 'Wrong module name')
    require(info.get('vermagic') == ['6.18.60 SMP mod_unload aarch64'], 'Unexpected vermagic')
    require(set(info.get('depends', [''])[0].split(',')) == {'mt76', 'mac80211', 'cfg80211', 'mt76-connac-lib', 'hwmon'}, 'Unexpected module dependency set')
    pci_aliases = aliases(module)
    for device in ('7993', '799B'):
        require(any(a.startswith('pci:v000014C3d0000' + device) for a in pci_aliases), 'Missing MT7990 PCI alias ' + device)
    require(not any('airoha' in s.lower() or 'npu' in s.lower() for s in inventory['undefined_symbols']), 'Unexpected NPU dependency')
    fwdir = mt76 / '.pkgdir/kmod-mt7990-firmware/lib/firmware/mediatek/mt7996'
    expected = {'mt7990_eeprom.bin', 'mt7990_eeprom_2i5i.bin', 'mt7990_rom_patch.bin', 'mt7990_wm.bin'}
    require({p.name for p in fwdir.iterdir()} == expected, 'Unexpected firmware file set')
    firmware = {}
    for name in sorted(expected):
        path = fwdir / name
        require(path.is_file() and not path.is_symlink(), 'Firmware must be an ordinary file')
        require(path.read_bytes() == (mt76 / 'firmware/mt7996' / name).read_bytes(), 'Firmware staging mismatch')
        firmware[name] = record(path)
    for name in ('mt7990_eeprom.bin', 'mt7990_eeprom_2i5i.bin'):
        require(firmware[name]['bytes'] == 7680, 'Unexpected reference EEPROM length')
    packages = {}
    for name in ('kmod-mt7996e', 'kmod-mt7990-firmware'):
        paths = list((tree / 'bin/targets/airoha/vb235v/packages').glob(name + '-6.18.60.' + VERSION + '-r2.apk'))
        require(len(paths) == 1 and paths[0].stat().st_size > 0, 'Missing or ambiguous APK: ' + name)
        packages[paths[0].name] = record(paths[0])
    return {'milestone': 'M60', 'scope': 'host compile and staged-output audit only',
            'ponwrt_baseline': head, 'mt76_version': VERSION,
            'config': record(tree / '.config'), 'kernel_config': record(linux / 'linux-6.18.60/.config'),
            'module': {**record(module), 'architecture': inventory['architecture'], 'modinfo': info, 'pci_aliases': pci_aliases},
            'firmware': firmware, 'packages': packages,
            'npu_undefined_symbols': [], 'module_loaded': False, 'pcie_enabled': False,
            'board_calibration_validated': False, 'radio_tested': False,
            'running_M58_module_compatibility_claimed': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('tree', type=Path)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = audit(args.tree.resolve())
    args.output.write_bytes((json.dumps(result, indent=2) + '\n').encode())
    print('M60: AArch64 module, both MT7990 PCI aliases, four firmware files and two APKs verified; hardware untested.')


if __name__ == '__main__':
    main()
