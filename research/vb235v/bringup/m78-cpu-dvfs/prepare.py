#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Apply only M78 to an already prepared M75+ tree; no device accessed."""
import argparse, hashlib, json, re, subprocess
from pathlib import Path
HERE = Path(__file__).resolve().parent
PIN = 'dcf140cb1d5d2c15c1d7c353c95c4c2a56629820'

def install(source, target):
    data = source.read_bytes()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        assert target.read_bytes() == data, 'Different existing file: ' + str(target)
    else:
        target.write_bytes(data)

def config(path):
    data = path.read_text()
    values = {'ARM_AIROHA_SOC_CPUFREQ': None,
              'ARM_VB235V_BOOT_VOLTAGE_CPUFREQ': 'y', 'CPU_FREQ': 'y',
              'CPU_FREQ_DEFAULT_GOV_PERFORMANCE': 'y',
              'CPU_FREQ_GOV_PERFORMANCE': 'y', 'CPU_FREQ_GOV_USERSPACE': 'y'}
    for name in sorted(set(re.findall(r'^(?:# )?CONFIG_(CPU_FREQ_DEFAULT_GOV_\w+)(?:=| is not set)', data, re.M))):
        if name != 'CPU_FREQ_DEFAULT_GOV_PERFORMANCE':
            values[name] = None
    for name, value in values.items():
        symbol = 'CONFIG_' + name
        data = re.sub(r'^(?:# )?' + symbol + r'(?:=.*| is not set)\n', '', data, flags=re.M)
        data += (symbol+'='+value if value else '# '+symbol+' is not set')+'\n'
    path.write_bytes(data.encode())

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('tree', type=Path)
    p.add_argument('--revision', help='Optional parent-owned integrated revision')
    a = p.parse_args()
    tree = a.tree.resolve(strict=True)
    assert subprocess.check_output(['git', '-C', str(tree), 'rev-parse', 'HEAD'], text=True).strip() == PIN
    kernel = tree/'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60'
    # Verify required corrected PHY code before adding CPU work; never call an
    # earlier prepare stage here because that could overwrite concurrent M77.
    phy = json.loads((HERE.parent/'m75-en8811h-paged-status/source-hashes.json').read_text())
    for name, row in phy.items():
        assert hashlib.sha256((kernel/name).read_bytes()).hexdigest() == row['candidate'], 'M75 prerequisite absent'
    manifest = json.loads((HERE/'source-hashes.json').read_text())
    for name, row in manifest.items():
        assert hashlib.sha256((kernel/name).read_bytes()).hexdigest() in [row['baseline'], row['candidate']], 'Different CPU integration prerequisite: '+name
    patch = HERE/'cpu-build.patch'
    if all(hashlib.sha256((kernel/name).read_bytes()).hexdigest() == row['baseline'] for name, row in manifest.items()):
        subprocess.run(['patch','-p1','--batch','--fuzz=0','-i',str(patch)], cwd=kernel, check=True)
    for name, row in manifest.items():
        assert hashlib.sha256((kernel/name).read_bytes()).hexdigest() == row['candidate']
    install(patch, tree/'target/linux/airoha/patches-6.18/965-vb235v-boot-voltage-cpufreq.patch')
    for name in ['vb235v-cpufreq.c','vb235v-cpufreq-contract.h']:
        for base in [kernel, tree/'target/linux/airoha/files']:
            install(HERE/name, base/'drivers/cpufreq'/name)
    for name in ['an7583-tplink_vb235v.dts']:
        dest = tree/'target/linux/airoha/dts'/name
        data = dest.read_text()
        marker = ' tplink,m78-boot-voltage-cpufreq;'
        if marker not in data:
            assert data.count('/ {') == 1 and '"tplink,vb235v"' in data
            data = data.replace('/ {', '/ {\n'+marker, 1)
            dest.write_bytes(data.encode())
    for path in [tree/'target/linux/airoha/vb235v/config-6.18', kernel/'.config']:
        config(path)
    if a.revision:
        assert re.fullmatch(r'M[0-9]+-[A-Za-z0-9_.-]{1,60}', a.revision)
        (tree/'files/etc/vb235v-system-revision').write_bytes((a.revision+'\n').encode())
    print('M78 prepared: genuine SMC cpufreq, performance default, transitions disabled, no AVS/PLL writes.')
if __name__ == '__main__':
    main()
