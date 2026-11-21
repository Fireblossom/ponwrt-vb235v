#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Prepare the two observed PSCI processors on the M64 RAM profile."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent

def install(source,target,executable=False):
    data=source.read_bytes()
    if target.exists() and target.read_bytes()!=data:raise ValueError('Different existing overlay: '+str(target))
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    if executable:target.chmod(0o755)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('tree',type=Path);a=p.parse_args()
    tree=a.tree.resolve(strict=True)
    assert subprocess.check_output(['git','-C',str(tree),'rev-parse','HEAD'],text=True).strip()=='dcf140cb1d5d2c15c1d7c353c95c4c2a56629820'
    kernel=tree/'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60'
    for stage,file,manifest in [('m63-ram-pcie','pcie-mediatek-gen3.c','host-source-hashes.json'),('m64-dual-pcie','pcie-mediatek.c','second-host-source-hashes.json')]:
        expected=json.loads((HERE.parent/stage/manifest).read_text())['candidate']
        assert hashlib.sha256((kernel/'drivers/pci/controller'/file).read_bytes()).hexdigest()==expected
    for name in ['phy-vb235v-qp-pcie.c','qphy-fields.h','qphy-sequence.inc']:
        assert (kernel/'drivers/phy/airoha'/name).read_bytes()==(HERE.parent/'m64-dual-pcie'/name).read_bytes()
    install(HERE/'an7583-tplink_vb235v-ram-smp.dts',tree/'target/linux/airoha/dts/an7583-tplink_vb235v-ram-smp.dts')
    install(HERE/'image.mk',tree/'target/linux/airoha/image/vb235v-smp.mk')
    install(HERE/'99-vb235v-ram-smp',tree/'target/linux/airoha/vb235v/base-files/etc/uci-defaults/99-vb235v-ram-smp',True)
    recipe=tree/'target/linux/airoha/image/vb235v.mk'
    include=b'\ninclude $(TOPDIR)/target/linux/airoha/image/vb235v-smp.mk\n'
    if include not in recipe.read_bytes():recipe.write_bytes(recipe.read_bytes()+include)
    config=tree/'.config';data=config.read_bytes()
    old=b'CONFIG_TARGET_airoha_vb235v_DEVICE_tplink_vb235v-ram-dual-pcie=y'
    new=b'CONFIG_TARGET_airoha_vb235v_DEVICE_tplink_vb235v-ram-smp=y'
    assert old in data or new in data
    config.write_bytes(data.replace(old,new))
    kconfig=tree/'target/linux/airoha/vb235v/config-6.18';data=kconfig.read_bytes()
    assert b'CONFIG_NR_CPUS=2\n' in data or b'CONFIG_NR_CPUS=4\n' in data
    kconfig.write_bytes(data.replace(b'CONFIG_NR_CPUS=2\n',b'CONFIG_NR_CPUS=4\n'))
    print('M67 two-core PSCI RAM profile prepared, kernel maximum four slots; no device operation.')

if __name__=='__main__':main()
