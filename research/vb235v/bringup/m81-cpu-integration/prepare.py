#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Stage M81 after M78 without rerunning any earlier prepare or accessing a device."""
import argparse, hashlib, json, os, subprocess
from pathlib import Path
HERE = Path(__file__).resolve().parent
PIN = 'dcf140cb1d5d2c15c1d7c353c95c4c2a56629820'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('tree', type=Path)
    a = p.parse_args()
    tree = a.tree.resolve(strict=True)
    assert subprocess.check_output(['git','-C',str(tree),'rev-parse','HEAD'],text=True).strip() == PIN
    kernel = tree/'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60'
    m78 = HERE.parent/'m78-cpu-dvfs'
    for name, row in json.loads((m78/'source-hashes.json').read_text()).items():
        assert sha(kernel/name) == row['candidate'], 'M78 Kconfig/Makefile absent: '+name
    board = tree/'target/linux/airoha/dts/an7583-tplink_vb235v.dts'
    assert 'tplink,m78-boot-voltage-cpufreq;' in board.read_text(), 'M78 DT opt-in absent'
    for config in [tree/'target/linux/airoha/vb235v/config-6.18', kernel/'.config']:
        text = config.read_text()
        assert 'CONFIG_ARM_VB235V_BOOT_VOLTAGE_CPUFREQ=y\n' in text
        assert '# CONFIG_ARM_AIROHA_SOC_CPUFREQ is not set\n' in text
        assert 'CONFIG_CPU_FREQ_DEFAULT_GOV_PERFORMANCE=y\n' in text
    hashes = json.loads((HERE/'source-hashes.json').read_text())
    destinations = []
    for name, row in hashes.items():
        for base in [kernel, tree/'target/linux/airoha/files']:
            dest = base/'drivers/cpufreq'/name
            assert sha(dest) in [row['baseline'],row['candidate']], 'Different CPU prerequisite: '+str(dest)
            destinations.append((HERE/name,dest))
    # All checked before the first mutation. Only the coordinating build owner
    # should invoke this while holding the shared-tree build lease.
    for src, dest in destinations:
        dest.write_bytes(src.read_bytes())
    libexec = tree/'files/usr/libexec'
    libexec.mkdir(parents=True, exist_ok=True)
    for src, name in [('cpu-observe.sh','vb235v-cpu-observe'),('cpu-cycle.sh','vb235v-cpu-cycle')]:
        dest = libexec/name
        if dest.exists(): assert dest.read_bytes() == (HERE/src).read_bytes()
        dest.write_bytes((HERE/src).read_bytes()); dest.chmod(0o755)
    cross = tree/'staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin/aarch64-openwrt-linux-musl-gcc'
    source = HERE.parent.parent/'tools/vb235v_smp_probe.c'
    subprocess.run([str(cross),'-O2','-std=c11','-Wall','-Wextra','-Werror','-pthread',
                    str(source),'-o',str(libexec/'vb235v-cpu-smp-probe')], check=True,
                   env=dict(os.environ, STAGING_DIR=str(tree/'staging_dir')))
    print('M81 staged over M78: query/arm preflight, exact BL31 gate, SET counter, SCU exclusion and RAM-only one-pair scripts; default disarmed.')
if __name__ == '__main__': main()
