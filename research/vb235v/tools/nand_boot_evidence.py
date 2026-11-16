# SPDX-License-Identifier: GPL-2.0-only
"""Extract an allowlisted NAND fact set from private boot/proc captures offline."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def summarize(boot, mtd):
    geometries = {tuple(map(int, row)) for row in re.findall(
        r'nand: (\d+) MiB, SLC, erase size: (\d+) KiB, page size: (\d+), OOB size: (\d+)', boot)}
    if len(geometries) != 1:
        raise ValueError('Expected one unambiguous SLC geometry')
    mib, erase_kib, page, oob = next(iter(geometries))
    total, erase = mib * 1024 * 1024, erase_kib * 1024
    if not page or not erase or not total or total % erase or erase % page or not 0 < oob < page:
        raise ValueError('Invalid/inconsistent NAND geometry')
    ids = sorted(set(re.findall(r'nand: device found, Manufacturer ID: (0x[0-9a-fA-F]+), Chip ID: (0x[0-9a-fA-F]+)', boot)))
    partitions = []
    seen = set()
    for index, size, block, name in re.findall(r'^mtd(\d+):\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+"([A-Za-z0-9_-]+)"\s*$', mtd, re.M):
        if int(index) in seen:
            raise ValueError('Duplicate MTD index')
        seen.add(int(index))
        partitions.append({'index': int(index), 'name': name, 'bytes': int(size, 16), 'erase_bytes': int(block, 16)})
    if not partitions:
        raise ValueError('No MTD entries parsed')
    return {'classification': 'allowlisted facts from retained private stock boot and proc captures',
            'physical_geometry': {'bytes': total, 'erase_bytes': erase, 'page_bytes': page, 'oob_bytes': oob,
                                  'physical_erase_blocks': total // erase, 'pages_per_erase_block': erase // page},
            'reported_ids': [{'manufacturer': manufacturer.lower(), 'device': device.lower()} for manufacturer, device in ids],
            'reported_ecc_paths': sorted(set(re.findall(r'Using (Flash|SoC) ECC\.', boot))),
            'nand_core_ecc_none_warning': 'NAND_ECC_NONE selected by board driver' in boot,
            'reported_bmt_pool_blocks': sorted({int(value) for value in re.findall(r'bmt pool size:\s*(\d+)', boot)}),
            'mtd_entries': partitions,
            'limitations': ['Boot messages report the selected software path, not an electrical ECC test or a feature-register readback.',
                           'MTD entries can overlap and do not supply partition offsets or raw OOB/ECC data.',
                           'The name whole does not establish coverage of the physical chip.']}


def bounded_read(path):
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('Capture exceeds 16 MiB')
    return path.read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('boot_log', type=Path)
    parser.add_argument('proc_mtd', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    boot, mtd = bounded_read(args.boot_log), bounded_read(args.proc_mtd)
    result = summarize(boot.decode('utf-8', 'replace'), mtd.decode('ascii', 'replace'))
    result['input_sha256'] = {'boot_log': hashlib.sha256(boot).hexdigest(), 'proc_mtd': hashlib.sha256(mtd).hexdigest()}
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({key: result[key] for key in ('physical_geometry', 'reported_ecc_paths', 'reported_bmt_pool_blocks')}))


if __name__ == '__main__':
    main()
