# SPDX-License-Identifier: GPL-2.0-only
"""Package an ARM64 Linux Image and VB235v DT as a recovery firmware FIT.

This creates a file only. It does not install, flash or establish driver readiness.
"""
import argparse
import hashlib
import json
import lzma
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

from fdt_board_inventory import parse


def run(command, cwd):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr[-2000:] or result.stdout[-2000:])
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel', type=Path, required=True, help='uncompressed ARM64 Linux Image')
    parser.add_argument('--dtb', type=Path, required=True)
    parser.add_argument('--initramfs', type=Path)
    parser.add_argument('--sequence', type=int, required=True)
    parser.add_argument('--mkimage', type=Path, required=True)
    parser.add_argument('--dumpimage', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='new directory')
    args = parser.parse_args()
    if not 1 <= args.sequence <= 0xffffffff:
        raise ValueError('Sequence must be a positive u32 and newer than installed FITs')
    kernel = args.kernel.read_bytes()
    if len(kernel) < 64 or kernel[56:60] != b'ARM\x64':
        raise ValueError('Expected an uncompressed ARM64 Linux Image header')
    footprint = struct.unpack_from('<Q', kernel, 16)[0]
    offset = struct.unpack_from('<Q', kernel, 8)[0]
    if offset != 0x80000 or not len(kernel) <= footprint <= 0x3f80000:
        raise ValueError('Image must use text_offset 0x80000 and fit below 0x84000000')
    dtb = args.dtb.read_bytes()
    nodes, _ = parse(dtb)
    if b'tplink,vb235v' not in nodes['/'].get('compatible', b'').split(b'\0'):
        raise ValueError('DT does not identify tplink,vb235v')
    ramdisk = args.initramfs.read_bytes() if args.initramfs else None
    if ramdisk is not None and not 0 < len(ramdisk) <= 0x4000000:
        raise ValueError('Optional initramfs must be 1 byte to 64 MiB')
    encoded = lzma.compress(kernel, format=lzma.FORMAT_ALONE)
    mkimage = args.mkimage.resolve()
    dumpimage = args.dumpimage.resolve()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError(output)
    with tempfile.TemporaryDirectory(prefix='vb235v-firmware-') as directory:
        work = Path(directory)
        payloads = [('kernel.lzma', encoded), ('board.dtb', dtb)]
        extra_image = extra_ref = ''
        if ramdisk is not None:
            payloads.append(('initramfs.bin', ramdisk))
            extra_image = '''ramdisk { description="Linux initramfs"; data=/incbin/("initramfs.bin"); type="ramdisk"; arch="arm64"; os="linux"; compression="none"; load=<0x8c000000>; hash-1 { algo="sha256"; }; };'''
            extra_ref = 'ramdisk="ramdisk";'
        for name, data in payloads:
            (work / name).write_bytes(data)
        its = '''/dts-v1/;
/ { description="VB235v recovery firmware"; #address-cells=<1>;
 images {
  kernel { description="ARM64 Linux"; data=/incbin/("kernel.lzma"); type="kernel"; arch="arm64"; os="linux"; compression="lzma"; load=<0x80080000>; entry=<0x80080000>; hash-1 { algo="sha256"; }; };
  fdt { description="VB235v board"; data=/incbin/("board.dtb"); type="flat_dt"; arch="arm64"; compression="none"; load=<0x87e00000>; hash-1 { algo="sha256"; }; };
  EXTRA_IMAGE
 };
 configurations { default="firmware"; firmware { compatible="tplink,vb235v"; vb235v,firmware-image=<1>; vb235v,sequence=<SEQUENCE>; kernel="kernel"; fdt="fdt"; EXTRA_REF }; };
};
'''.replace('EXTRA_IMAGE', extra_image).replace('EXTRA_REF', extra_ref).replace('SEQUENCE', str(args.sequence))
        (work / 'firmware.its').write_text(its)
        old_epoch = os.environ.get('SOURCE_DATE_EPOCH')
        os.environ['SOURCE_DATE_EPOCH'] = '1794787200'
        try:
            listing = run([str(mkimage), '-f', 'firmware.its', 'firmware.itb'], work)
        finally:
            if old_epoch is None:
                os.environ.pop('SOURCE_DATE_EPOCH', None)
            else:
                os.environ['SOURCE_DATE_EPOCH'] = old_epoch
        fit = (work / 'firmware.itb').read_bytes()
        if len(fit) > 0x5000000:
            raise ValueError('Complete FIT exceeds the 80 MiB firmware slot')
        for index, (_, data) in enumerate(payloads):
            name = 'check-' + str(index) + '.bin'
            run([str(dumpimage), '-T', 'flat_dt', '-p', str(index), '-o', name, 'firmware.itb'], work)
            if (work / name).read_bytes() != data:
                raise RuntimeError('FIT payload extraction differs')
        output.mkdir(parents=True)
        shutil.copyfile(work / 'firmware.itb', output / 'vb235v-firmware.itb')
        (output / 'firmware.its').write_text(its)
        (output / 'fit-list.txt').write_text(listing)
        report = {'sequence': args.sequence, 'bytes': len(fit), 'sha256': hashlib.sha256(fit).hexdigest(),
                  'payload_roundtrips_verified': True, 'flashed': False, 'hardware_booted': False,
                  'note': 'Packaging does not establish kernel, DT or driver readiness.'}
        (output / 'manifest.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
