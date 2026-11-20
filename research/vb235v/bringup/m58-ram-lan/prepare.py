#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Prepare the separate single-port LAN experiment in a pinned M55 worktree.

This changes the active target's kernel configuration. Preserve M55 artifacts
first; its strict controller-free config gate must not admit the LAN variant.
"""
import argparse
from pathlib import Path
import re
import subprocess

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'm55-ponwrt-system'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def install(source, target, executable=False):
    data = source.read_bytes()
    if target.exists() and target.read_bytes() != data:
        raise ValueError('Refusing to overwrite different LAN overlay: ' + str(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    if executable:
        target.chmod(0o755)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tree', type=Path)
    parser.add_argument('--reuse-m55-tree', action='store_true')
    args = parser.parse_args()
    tree = args.tree.resolve(strict=True)
    require(subprocess.check_output(['git', '-C', str(tree), 'rev-parse', 'HEAD'], text=True).strip() == 'dcf140cb1d5d2c15c1d7c353c95c4c2a56629820', 'Unexpected PonWrt baseline')
    if not (tree / '.config').exists():
        subprocess.run(['python3', str(BASE / 'prepare.py'), str(tree)], check=True)
    elif not args.reuse_m55_tree:
        raise ValueError('Use a new worktree or explicitly preserve/reuse a prepared M55 worktree')
    original = BASE / 'overlay/target/linux/airoha/dts/an7583-tplink_vb235v-ram.dts'
    require((tree / 'target/linux/airoha/dts' / original.name).read_bytes() == original.read_bytes(), 'M55 base DT differs')
    install(HERE / 'an7583-tplink_vb235v-ram-lan.dts', tree / 'target/linux/airoha/dts/an7583-tplink_vb235v-ram-lan.dts')
    install(HERE / 'image.mk', tree / 'target/linux/airoha/image/vb235v-lan.mk')
    install(HERE / '99-vb235v-ram-lan', tree / 'target/linux/airoha/vb235v/base-files/etc/uci-defaults/99-vb235v-ram-lan', True)
    image = tree / 'target/linux/airoha/image/vb235v.mk'
    expected = (BASE / 'overlay/target/linux/airoha/image/vb235v.mk').read_bytes()
    include = b'\ninclude $(TOPDIR)/target/linux/airoha/image/vb235v-lan.mk\n'
    require(image.read_bytes() in (expected, expected + include), 'Base image recipe differs')
    image.write_bytes(expected + include)
    kernel = tree / 'target/linux/airoha/vb235v/config-6.18'
    changes = {'NET_AIROHA': 'y', 'NET_AIROHA_NPU': 'y', 'NET_AIROHA_FLOW_STATS': 'n',
               'NET_DSA': 'y', 'NET_DSA_MT7530': 'y', 'NET_DSA_MT7530_MMIO': 'y',
               'MEDIATEK_GE_SOC_PHY': 'y'}
    pattern = re.compile(r'^(?:CONFIG_|# CONFIG_)(' + '|'.join(changes) + r')(?:=| is not set)')
    lines = [line for line in kernel.read_text().splitlines() if not pattern.match(line)]
    lines += ['CONFIG_' + key + '=y' if value == 'y' else '# CONFIG_' + key + ' is not set' for key, value in changes.items()]
    kernel.write_bytes(('\n'.join(lines) + '\n').encode())
    config = (BASE / 'ram.config').read_text().replace('DEVICE_tplink_vb235v-ram=y', 'DEVICE_tplink_vb235v-ram-lan=y')
    (tree / '.config').write_bytes(config.encode())
    print('Separate RAM LAN profile prepared; no device operations performed.')


if __name__ == '__main__':
    main()
