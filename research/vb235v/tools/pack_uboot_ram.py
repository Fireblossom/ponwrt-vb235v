# SPDX-License-Identifier: GPL-2.0-only
"""Package a checked BL33 RAM payload in a hash-verified FIT; never flash it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile

from fdt_board_inventory import parse


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--checks', type=Path, required=True)
    parser.add_argument('--mode', choices=('serial', 'net'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mkimage', type=Path, required=True)
    args = parser.parse_args()
    checks = json.loads(args.checks.read_text())
    selected = [b for b in checks['builds'] if b['mode'] == args.mode]
    if len(selected) != 1 or checks['flashable'] or checks['hardware_access']:
        raise ValueError('Unexpected check report')
    record = selected[0]
    binary = (args.build / 'u-boot.bin').read_bytes()
    dtb = (args.build / 'u-boot.dtb').read_bytes()
    config = (args.build / '.config').read_bytes()
    for data, field in ((binary, 'binary_sha256'), (dtb, 'dtb_sha256'), (config, 'config_sha256')):
        if sha(data) != record[field]:
            raise ValueError('Build differs from checked artifact: ' + field)
    if binary[56:60] != b'ARM\x64' or struct.unpack_from('<Q', binary, 8)[0] != 0x1e00000:
        raise ValueError('Missing reviewed ARM64 image header')
    if args.output.exists():
        raise ValueError('Output directory must be new')
    with tempfile.TemporaryDirectory(prefix='vb235v-fit-') as directory:
        root = Path(directory)
        (root / 'payload.bin').write_bytes(binary)
        (root / 'board.dtb').write_bytes(dtb)
        (root / 'recovery.its').write_text('''/dts-v1/;
/ {
 description = "VB235v RAM development only - DO NOT FLASH";
 #address-cells = <1>;
 images {
  recovery {
   description = "RAM BL33 development payload";
   data = /incbin/("payload.bin");
   type = "kernel"; arch = "arm64"; os = "linux"; compression = "none";
   load = <0x81e00000>; entry = <0x81e00000>;
   hash-1 { algo = "sha256"; };
  };
  fdt {
   description = "Development handoff DT";
   data = /incbin/("board.dtb");
   type = "flat_dt"; arch = "arm64"; compression = "none";
   hash-1 { algo = "sha256"; };
  };
 };
 configurations {
  default = "ram";
  ram { description = "RAM-only experiment"; kernel = "recovery"; fdt = "fdt"; };
 };
};
''')
        env = os.environ.copy()
        env['SOURCE_DATE_EPOCH'] = '1794787200'
        result = subprocess.run([str(args.mkimage.resolve()), '-f', 'recovery.its', 'recovery.itb'],
                                cwd=root, env=env, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError('mkimage failed: ' + result.stderr[-3000:])
        fit = (root / 'recovery.itb').read_bytes()
        nodes, _ = parse(fit)
        for name, expected in (('recovery', binary), ('fdt', dtb)):
            if nodes['/images/' + name]['data'] != expected:
                raise ValueError('FIT payload mismatch')
            if nodes['/images/' + name + '/hash-1']['value'] != hashlib.sha256(expected).digest():
                raise ValueError('FIT SHA-256 mismatch')
        if (nodes['/images/recovery']['load'] != bytes.fromhex('81e00000') or
                nodes['/images/recovery']['entry'] != bytes.fromhex('81e00000') or
                nodes['/configurations']['default'] != b'ram\0'):
            raise ValueError('Unexpected FIT handoff addresses')
        args.output.mkdir(parents=True)
        stem = 'vb235v-' + args.mode + '-RAM-ONLY'
        (args.output / (stem + '.itb')).write_bytes(fit)
        (args.output / (stem + '.Image')).write_bytes(binary)
        (args.output / 'development.dtb').write_bytes(dtb)
        (args.output / 'build.config').write_bytes(config)
        (args.output / 'fit-list.txt').write_text(result.stdout)
        metadata = {'mode': args.mode, 'flashable': False, 'hardware_booted': False,
                    'fit_bytes': len(fit), 'fit_sha256': sha(fit),
                    'payload_sha256': sha(binary), 'dtb_sha256': sha(dtb),
                    'fit_payload_hashes_verified': True,
                    'load_address': '0x81e00000', 'entry_address': '0x81e00000',
                    'stock_acceptance_verified': False, 'signature': 'unsigned development FIT'}
        (args.output / 'manifest.json').write_text(json.dumps(metadata, indent=2) + '\n')
        (args.output / 'README.txt').write_text(
            '仅供 RAM 开发验证，禁止写入 NAND/bootloader/UBI，也不是原厂升级文件。\n'
            '保留原厂 BL2、BL31、FIP、环境区和分区表。未进行实机启动验证。\n'
            'FIT 使用 Linux handoff 以请求原厂 bootm 清理缓存/MMU；不使用直接 go 跳转。\n'
            '原厂是否接受此未签名 FIT、实际 EL/PSCI 行为均待验证。\n'
            '串口版首先验证；LAN 候选版可能复位交换机/FE，物理端口尚未验证。\n'
            '16 MiB RAM 上传不验证固件格式，也不会执行。须在串口核对镜像后另行启动。\n',
            encoding='utf-8')
    print(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    main()
