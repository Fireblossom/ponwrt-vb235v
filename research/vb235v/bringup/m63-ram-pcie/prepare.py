#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Prepare the no-radio PCIe experiment in an already built M58 worktree."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
BASELINE = 'dcf140cb1d5d2c15c1d7c353c95c4c2a56629820'


def install(source, target, executable=False):
    data = source.read_bytes()
    if target.exists() and target.read_bytes() != data:
        raise ValueError('Refusing different existing overlay: ' + str(target))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    if executable:
        target.chmod(0o755)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('tree', type=Path)
    args = p.parse_args()
    tree = args.tree.resolve(strict=True)
    assert subprocess.check_output(['git', '-C', str(tree), 'rev-parse', 'HEAD'], text=True).strip() == BASELINE
    lan = HERE.parent / 'm58-ram-lan'
    assert (tree / 'target/linux/airoha/dts/an7583-tplink_vb235v-ram-lan.dts').read_bytes() == (lan / 'an7583-tplink_vb235v-ram-lan.dts').read_bytes()
    kernel = tree / 'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60'
    source = kernel / 'drivers/pci/controller/pcie-mediatek-gen3.c'
    hashes = json.loads((HERE / 'host-source-hashes.json').read_text())
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    if digest == hashes['baseline']:
        subprocess.run(['patch', '-p1', '--fuzz=0', '--batch', '-i', str(HERE / '985-vb235v-ram-pcie-host-development.patch')], cwd=kernel, check=True)
    elif digest != hashes['candidate']:
        raise ValueError('Unexpected PCIe host source')
    assert hashlib.sha256(source.read_bytes()).hexdigest() == hashes['candidate']
    install(HERE / 'an7583-tplink_vb235v-ram-pcie.dts', tree / 'target/linux/airoha/dts/an7583-tplink_vb235v-ram-pcie.dts')
    install(HERE / 'image.mk', tree / 'target/linux/airoha/image/vb235v-pcie.mk')
    install(HERE / '99-vb235v-ram-pcie', tree / 'target/linux/airoha/vb235v/base-files/etc/uci-defaults/99-vb235v-ram-pcie', True)
    recipe = tree / 'target/linux/airoha/image/vb235v.mk'
    include = b'\ninclude $(TOPDIR)/target/linux/airoha/image/vb235v-pcie.mk\n'
    if include not in recipe.read_bytes():
        recipe.write_bytes(recipe.read_bytes() + include)
    config = tree / '.config'
    before = config.read_text()
    old = 'CONFIG_TARGET_airoha_vb235v_DEVICE_tplink_vb235v-ram-lan=y'
    new = 'CONFIG_TARGET_airoha_vb235v_DEVICE_tplink_vb235v-ram-pcie=y'
    assert old in before or new in before
    config.write_bytes(before.replace(old, new).encode())
    print('No-radio RAM PCIe profile prepared; exact host-source patch replay verified.')


if __name__ == '__main__':
    main()
