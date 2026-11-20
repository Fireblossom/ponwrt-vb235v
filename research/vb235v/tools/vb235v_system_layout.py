#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Budget the post-rescue 319-PEB system, or prepare offline UBI inputs.

This never opens a device, attaches UBI, formats flash or invokes a writer.
Prepared inputs still require production mapping/ECC/boot validation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from inspect_vb235v_sysupgrade import MAX_IMAGE, inspect

DEFAULT_LAYOUT = Path(__file__).resolve().parents[1] / 'bringup/m55-ponwrt-system/system-layout.json'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, name, minimum=1):
    require(type(value) is int and value >= minimum, 'Invalid integer: ' + name)
    return value


def validate(layout):
    # A new geometry is a new board contract, not a command-line override.
    expected = {
        'schema': 1, 'board': 'tplink,vb235v', 'chip_bytes': 0x20000000,
        'page_bytes': 4096, 'oob_bytes': 256, 'erase_bytes': 0x40000,
        'ecc_step_bytes': 512, 'ecc_strength': 8, 'ubi_vid_offset': 4096,
        'ubi_data_offset': 8192, 'ubi_leb_bytes': 253952,
        'bad_pebs_per_1024': 20, 'ubi_fastmap': False, 'ubi_layout_pebs': 2,
        'ubi_wl_reserve_pebs': 1, 'ubi_atomic_reserve_pebs': 1,
        'minimum_overlay_lebs': 24,
    }
    require(type(layout) is dict, 'Layout must be an object')
    for key, value in expected.items():
        require(type(layout.get(key)) is type(value) and layout[key] == value,
                'Unexpected board contract: ' + key)
    require(layout.get('system') == {'offset': 0x5c80000, 'bytes': 0x4fc0000, 'pebs': 319},
            'System must exclude the fixed rescue block')
    protected = layout.get('protected')
    require(type(protected) is list and len(protected) == 7, 'Missing protected ranges')
    bounds = [(0, 0x80000), (0x80000, 0x40000), (0xc0000, 0x380000),
              (0x440000, 0x800000), (0xc40000, 0x5000000),
              (0x5c40000, 0x40000), (0xac40000, 0x153c0000)]
    for item, (offset, size) in zip(protected, bounds):
        require(type(item) is dict and item.get('offset') == offset and item.get('bytes') == size,
                'Protected range differs from the M54 layout')
    require(layout.get('volumes') == [
        {'id': 0, 'name': 'kernel', 'type': 'static'},
        {'id': 1, 'name': 'rootfs', 'type': 'dynamic'},
        {'id': 2, 'name': 'rootfs_data', 'type': 'dynamic', 'autoresize': True},
    ], 'Unexpected UBI volume contract')
    require(all(type(vol['id']) is int for vol in layout['volumes']) and
            type(layout['volumes'][2]['autoresize']) is bool,
            'Invalid UBI volume field type')
    return layout


def budget(layout, kernel_bytes, rootfs_bytes, bad_pebs=0):
    validate(layout)
    integer(kernel_bytes, 'kernel_bytes')
    integer(rootfs_bytes, 'rootfs_bytes')
    integer(bad_pebs, 'bad_pebs', 0)
    pebs = layout['system']['pebs']
    require(bad_pebs < pebs, 'Too many bad PEBs')
    # Linux computes the reserve from the full 512-MiB chip, not this partition.
    chip_pebs = layout['chip_bytes'] // layout['erase_bytes']
    target_reserve = (chip_pebs * layout['bad_pebs_per_1024'] + 1023) // 1024
    remaining_reserve = max(0, target_reserve - bad_pebs)
    internal = sum(layout[key] for key in
                   ('ubi_layout_pebs', 'ubi_wl_reserve_pebs', 'ubi_atomic_reserve_pebs'))
    available = pebs - bad_pebs - remaining_reserve - internal
    leb = layout['ubi_leb_bytes']
    kernel_lebs = (kernel_bytes + leb - 1) // leb
    rootfs_lebs = (rootfs_bytes + leb - 1) // leb
    overlay_lebs = available - kernel_lebs - rootfs_lebs
    require(overlay_lebs >= layout['minimum_overlay_lebs'], 'Insufficient rootfs_data capacity')
    return {
        'board': layout['board'], 'system_offset': layout['system']['offset'],
        'system_bytes': layout['system']['bytes'], 'system_pebs': pebs,
        'leb_bytes': leb, 'known_bad_pebs': bad_pebs,
        'bad_reserve_chip_basis_pebs': chip_pebs, 'bad_reserve_target_pebs': target_reserve,
        'remaining_bad_reserve_pebs': remaining_reserve, 'internal_pebs': internal,
        'volume_capacity_lebs': available, 'kernel_bytes': kernel_bytes,
        'rootfs_bytes': rootfs_bytes, 'kernel_lebs': kernel_lebs,
        'rootfs_lebs': rootfs_lebs, 'minimum_overlay_lebs': layout['minimum_overlay_lebs'],
        'overlay_lebs': overlay_lebs, 'overlay_volume_bytes': overlay_lebs * leb,
        'overlay_usable_filesystem_bytes': None,
        'physical_mapping_verified': False, 'hardware_validated': False,
        'installation_authorized': False, 'device_operations': False,
    }


def prepare_inputs(layout, image, output, expected_sha256, bad_pebs=0):
    require(bool(re.fullmatch(r'[a-fA-F0-9]{64}', expected_sha256)), 'Expected SHA256 is required')
    require(image.is_file() and image.stat().st_size <= MAX_IMAGE, 'Invalid or oversized input')
    data = image.read_bytes()
    checked = inspect(data, expected_sha256)
    plan = budget(layout, checked['fit_bytes'], checked['rootfs_bytes_used'], bad_pebs)
    require(not output.exists(), 'Output directory already exists')
    # Relative, fixed input names make the ubinize config relocatable.
    config = []
    for vol in layout['volumes']:
        name = vol['name']
        config.extend(['[' + name + ']', 'mode=ubi', 'vol_id=' + str(vol['id']),
                       'vol_type=' + vol['type'], 'vol_name=' + name])
        if name != 'rootfs_data':
            config.extend(['image=' + name + '.bin',
                           'vol_size=' + str(plan[name + '_lebs'] * plan['leb_bytes'])])
        else:
            config.extend(['vol_size=' + str(plan['minimum_overlay_lebs'] * plan['leb_bytes']),
                           'vol_flags=autoresize'])
        config.append('')
    output.mkdir(parents=True)
    (output / 'kernel.bin').write_bytes(data[:checked['fit_bytes']])
    start = checked['rootfs_offset']
    (output / 'rootfs.bin').write_bytes(data[start:start + checked['rootfs_bytes_used']])
    (output / 'ubinize.cfg').write_bytes('\n'.join(config).encode('ascii'))
    plan.update(input_sha256=hashlib.sha256(data).hexdigest(), input_inspection=checked,
                ubinize_command=['ubinize', '-p', '262144', '-m', '4096', '-s', '4096',
                                 '-O', '4096', '-o', 'system.ubi', 'ubinize.cfg'])
    (output / 'manifest.json').write_bytes((json.dumps(plan, indent=2) + '\n').encode('utf8'))
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--layout', type=Path, default=DEFAULT_LAYOUT)
    parser.add_argument('--bad-pebs', type=int, default=0)
    commands = parser.add_subparsers(dest='command', required=True)
    plan = commands.add_parser('plan')
    plan.add_argument('--kernel-bytes', type=int, required=True)
    plan.add_argument('--rootfs-bytes', type=int, required=True)
    pack = commands.add_parser('prepare-inputs')
    pack.add_argument('image', type=Path)
    pack.add_argument('output', type=Path)
    pack.add_argument('--expected-sha256', required=True)
    args = parser.parse_args()
    layout = validate(json.loads(args.layout.read_text()))
    if args.command == 'plan':
        result = budget(layout, args.kernel_bytes, args.rootfs_bytes, args.bad_pebs)
    else:
        result = prepare_inputs(layout, args.image, args.output, args.expected_sha256, args.bad_pebs)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
