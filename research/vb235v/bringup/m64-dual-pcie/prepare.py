#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Prepare a no-radio dual PCIe RAM profile after a completed M63 host build."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent


def install(source,target,executable=False):
    data=source.read_bytes()
    if target.exists() and target.read_bytes()!=data:
        raise ValueError('Refusing different existing overlay: '+str(target))
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(data)
    if executable:
        target.chmod(0o755)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('tree',type=Path)
    a=p.parse_args()
    tree=a.tree.resolve(strict=True)
    assert subprocess.check_output(['git','-C',str(tree),'rev-parse','HEAD'],text=True).strip()=='dcf140cb1d5d2c15c1d7c353c95c4c2a56629820'
    kernel=tree/'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60'
    first=json.loads((HERE.parent/'m63-ram-pcie/host-source-hashes.json').read_text())
    assert hashlib.sha256((kernel/'drivers/pci/controller/pcie-mediatek-gen3.c').read_bytes()).hexdigest()==first['candidate']
    source=kernel/'drivers/pci/controller/pcie-mediatek.c'
    hashes=json.loads((HERE/'second-host-source-hashes.json').read_text())
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    if digest==hashes['baseline']:
        subprocess.run(['patch','-p1','--fuzz=0','--batch','-i',str(HERE/'986-vb235v-ram-second-pcie-host.patch')],cwd=kernel,check=True)
    elif digest!=hashes['candidate']:
        raise ValueError('Unexpected port-1 host source')
    assert hashlib.sha256(source.read_bytes()).hexdigest()==hashes['candidate']
    for name in ('phy-vb235v-qp-pcie.c','qphy-fields.h','qphy-sequence.inc'):
        install(HERE/name,kernel/'drivers/phy/airoha'/name)
    makefile=kernel/'drivers/phy/airoha/Makefile'
    include=b'\nobj-y += phy-vb235v-qp-pcie.o\n'
    if include not in makefile.read_bytes():
        makefile.write_bytes(makefile.read_bytes()+include)
    name='an7583-tplink_vb235v-ram-dual-pcie.dts'
    install(HERE/name,tree/'target/linux/airoha/dts'/name)
    install(HERE/'image.mk',tree/'target/linux/airoha/image/vb235v-dual-pcie.mk')
    install(HERE/'99-vb235v-ram-dual-pcie',tree/'target/linux/airoha/vb235v/base-files/etc/uci-defaults/99-vb235v-ram-dual-pcie',True)
    recipe=tree/'target/linux/airoha/image/vb235v.mk'
    include=b'\ninclude $(TOPDIR)/target/linux/airoha/image/vb235v-dual-pcie.mk\n'
    if include not in recipe.read_bytes():
        recipe.write_bytes(recipe.read_bytes()+include)
    config=tree/'.config'
    old=b'CONFIG_TARGET_airoha_vb235v_DEVICE_tplink_vb235v-ram-pcie=y'
    new=b'CONFIG_TARGET_airoha_vb235v_DEVICE_tplink_vb235v-ram-dual-pcie=y'
    assert old in config.read_bytes() or new in config.read_bytes()
    config.write_bytes(config.read_bytes().replace(old,new))
    print('Separate dual PCIe RAM profile prepared; no WLAN or device operations.')


if __name__=='__main__':
    main()
