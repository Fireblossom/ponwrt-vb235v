#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise offline production-input packaging with real FIT/SquashFS/UBI tools.

Generated images contain a synthetic kernel header and are never bootable.
All outputs live in a temporary host directory; no device is accessed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import zlib

from vb235v_system_layout import DEFAULT_LAYOUT, prepare_inputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mkimage', type=Path, required=True)
    parser.add_argument('--mksquashfs', type=Path, required=True)
    parser.add_argument('--ubinize', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    layout = json.loads(DEFAULT_LAYOUT.read_text())
    with tempfile.TemporaryDirectory(prefix='vb235v-offline-ubi-') as temporary:
        t = Path(temporary)
        (t / 'root').mkdir()
        (t / 'root/NEVER-BOOT').write_text('Offline format test; no working kernel or board drivers.\n')
        subprocess.run([str(args.mksquashfs), str(t / 'root'), str(t / 'root.squashfs'),
                        '-noappend', '-comp', 'xz', '-all-root', '-no-xattrs', '-no-exports',
                        '-no-progress', '-processors', '1'], check=True, capture_output=True)
        image = bytearray(4096)
        image[56:60] = b'ARMd'
        struct.pack_into('<Q', image, 16, 0x100000)
        (t / 'Image').write_bytes(image)
        subprocess.run(['dtc', '-I', 'dts', '-O', 'dtb', '-o', str(t / 'board.dtb')],
                       input=b'/dts-v1/; / { compatible="tplink,vb235v"; };\n',
                       check=True, capture_output=True)
        (t / 'image.its').write_text('''/dts-v1/;
/ { description="OFFLINE FORMAT TEST ONLY"; #address-cells=<1>;
 images {
  kernel { data=/incbin/("Image"); type="kernel"; arch="arm64"; os="linux";
   compression="none"; load=<0x80200000>; entry=<0x80200000>; hash-1 { algo="sha256"; }; };
  fdt { data=/incbin/("board.dtb"); type="flat_dt"; arch="arm64";
   compression="none"; hash-1 { algo="sha256"; }; };
 };
 configurations { default="conf"; conf { kernel="kernel"; fdt="fdt"; }; };
};
''')
        subprocess.run([str(args.mkimage), '-f', 'image.its', 'kernel.itb'], cwd=t,
                       check=True, capture_output=True)
        kernel = (t / 'kernel.itb').read_bytes()
        squashfs = (t / 'root.squashfs').read_bytes()
        payload = kernel + bytes((-len(kernel)) % 0x20000) + squashfs
        metadata = json.dumps({'metadata_version': '1.1', 'supported_devices': ['tplink,vb235v']}).encode()
        framed = payload + bytes(8) + metadata
        framed += struct.pack('>IIB3sI', 0x46577830, (~zlib.crc32(framed)) & 0xffffffff,
                              1, bytes(3), len(metadata) + 24)
        path = t / 'offline-sysupgrade.bin'
        path.write_bytes(framed)
        sha = hashlib.sha256(framed).hexdigest()
        plan = prepare_inputs(layout, path, t / 'inputs', sha)
        assert (t / 'inputs/kernel.bin').read_bytes() == kernel
        used = struct.unpack_from('<Q', squashfs, 40)[0]
        assert (t / 'inputs/rootfs.bin').read_bytes() == squashfs[:used]
        command = [str(args.ubinize)] + plan['ubinize_command'][1:]
        subprocess.run(command, cwd=t / 'inputs', check=True, capture_output=True)
        ubi = (t / 'inputs/system.ubi').read_bytes()
        assert len(ubi) % 0x40000 == 0 and len(ubi) <= layout['system']['bytes']
        ids = set()
        for offset in range(0, len(ubi), 0x40000):
            peb = ubi[offset:offset + 0x40000]
            assert peb[:4] == b'UBI#'
            assert struct.unpack_from('>II', peb, 16) == (4096, 8192)
            assert ((~zlib.crc32(peb[:60])) & 0xffffffff) == struct.unpack_from('>I', peb, 60)[0]
            vid = peb[4096:4160]
            assert vid[:4] == b'UBI!'
            assert ((~zlib.crc32(vid[:60])) & 0xffffffff) == struct.unpack_from('>I', vid, 60)[0]
            ids.add(struct.unpack_from('>I', vid, 8)[0])
        assert ids == {0, 1, 0x7fffefff}
        for bad_sha, destination in [('0' * 64, t / 'bad-sha'), (sha, t / 'inputs')]:
            try:
                prepare_inputs(layout, path, destination, bad_sha)
            except ValueError:
                pass
            else:
                raise AssertionError('Invalid hash or existing output directory accepted')
        report = {'real_mkimage_squashfs_ubinize_roundtrip': True,
                  'fit_and_rootfs_extraction_exact': True,
                  'UBI_EC_VID_geometry_and_CRC_verified': True,
                  'physical_pebs_emitted': len(ubi) // 0x40000,
                  'whole_chip_bad_reserve_pebs': plan['bad_reserve_target_pebs'],
                  'volume_capacity_lebs': plan['volume_capacity_lebs'],
                  'production_geometry_pebs': 319, 'kernel_fixture_is_bootable': False,
                  'hardware_validated': False, 'device_operations': False}
    args.output.write_bytes((json.dumps(report, indent=2) + '\n').encode('utf8'))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
