#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Install the authored RAM subtarget into a fresh pinned PonWrt worktree."""
import argparse
from pathlib import Path
import shutil
import subprocess

BASELINE = 'dcf140cb1d5d2c15c1d7c353c95c4c2a56629820'
HERE = Path(__file__).resolve().parent


def prepare(tree):
    tree = tree.resolve(strict=True)
    head = subprocess.check_output(['git', '-C', str(tree), 'rev-parse', 'HEAD'], text=True).strip()
    if head != BASELINE:
        raise ValueError('Use the pinned PonWrt baseline in a separate worktree')
    destinations = [(p, tree / p.relative_to(HERE / 'overlay'))
                    for p in sorted((HERE / 'overlay').rglob('*')) if p.is_file()]
    for source, target in destinations:
        if target.exists() and target.read_bytes() != source.read_bytes():
            raise ValueError('Refusing to replace a different file: ' + str(target))
    target_mk = tree / 'target/linux/airoha/Makefile'
    original = target_mk.read_text()
    marker = 'SUBTARGETS:=en7523 an7581 an7583'
    changed = marker + ' vb235v'
    if changed not in original:
        if original.count(marker) != 1:
            raise ValueError('Unexpected Airoha subtarget list')
        original = original.replace(marker, changed)
    config = (tree / 'target/linux/airoha/an7583/config-6.18').read_text()
    # These compiled drivers are unnecessary in a controller-free RAM DT.
    disabled = {
        'MTD_NAND_MTK_BMT', 'MTD_UBI', 'MTD_UBI_BLOCK', 'MTD_UBI_NVMEM',
        'UBIFS_FS', 'NET_AIROHA', 'NET_AIROHA_NPU', 'AIROHA_WATCHDOG', 'RANDOMIZE_BASE',
    }
    lines = [line for line in config.splitlines()
             if not any(line.startswith('CONFIG_' + key + '=') or
                        line == '# CONFIG_' + key + ' is not set' for key in disabled)]
    config = '\n'.join(lines + ['# CONFIG_' + key + ' is not set' for key in sorted(disabled)]) + '\n'
    config_path = tree / 'target/linux/airoha/vb235v/config-6.18'
    if config_path.exists() and config_path.read_text() != config:
        raise ValueError('Existing VB235v kernel configuration differs')
    if (tree / '.config').exists():
        raise ValueError('Refusing to overwrite an existing build configuration')
    feeds_path = tree / 'feeds.conf'
    feeds_content = '# M55 core-only RAM build; no external feeds.\n'
    if feeds_path.exists() and feeds_path.read_text() != feeds_content:
        raise ValueError('Refusing to overwrite an existing feeds configuration')
    for source, target in destinations:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        if 'base-files/usr/sbin/' in target.as_posix():
            target.chmod(0o755)
    target_mk.write_text(original)
    config_path.write_text(config)
    shutil.copyfile(HERE / 'ram.config', tree / '.config')
    # This stage uses only core packages; optional external feeds remain untouched.
    feeds_path.write_text(feeds_content)
    print('Prepared VB235v RAM subtarget; no device access')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tree', type=Path)
    args = parser.parse_args()
    prepare(args.tree)
