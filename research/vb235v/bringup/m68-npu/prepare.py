#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Prepare the opt-in NPU RAM experiment after a verified M67 build."""
import argparse,hashlib,json,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
def install(source,dest,execute=False):
    data=source.read_bytes()
    if dest.exists() and dest.read_bytes()!=data:raise ValueError('Different existing M68 file: '+str(dest))
    dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    if execute:dest.chmod(0o755)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('tree',type=Path);a=p.parse_args()
    tree=a.tree.resolve(strict=True)
    assert subprocess.check_output(['git','-C',str(tree),'rev-parse','HEAD'],text=True).strip()=='dcf140cb1d5d2c15c1d7c353c95c4c2a56629820'
    kernel=tree/'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60'
    hashes=json.loads((HERE/'source-hashes.json').read_text())
    current={name:hashlib.sha256((kernel/name).read_bytes()).hexdigest() if (kernel/name).exists() else None for name in hashes}
    if all(current[n]==v['baseline'] for n,v in hashes.items()):
        for patch in ['950-vb235v-npu-layout-development.patch','951-vb235v-npu-layout-binding.patch']:
            subprocess.run(['patch','-p1','--fuzz=0','--batch','-i',str(HERE.parent/patch)],cwd=kernel,check=True)
        for stamp in kernel.parent.glob('mt76-*/.built*'):
            if stamp.is_file():stamp.unlink()
    final={name:hashlib.sha256((kernel/name).read_bytes()).hexdigest() if (kernel/name).exists() else None for name in hashes}
    assert all(final[n]==v['candidate'] for n,v in hashes.items()),'Unexpected NPU source after preparation'
    assert 'CONFIG_NR_CPUS=4\n' in (tree/'target/linux/airoha/vb235v/config-6.18').read_text()
    install(HERE/'an7583-tplink_vb235v-ram-npu.dts',tree/'target/linux/airoha/dts/an7583-tplink_vb235v-ram-npu.dts')
    install(HERE/'image.mk',tree/'target/linux/airoha/image/vb235v-npu.mk')
    install(HERE/'99-vb235v-ram-npu',tree/'target/linux/airoha/vb235v/base-files/etc/uci-defaults/99-vb235v-ram-npu',True)
    recipe=tree/'target/linux/airoha/image/vb235v.mk';include=b'\ninclude $(TOPDIR)/target/linux/airoha/image/vb235v-npu.mk\n'
    if include not in recipe.read_bytes():recipe.write_bytes(recipe.read_bytes()+include)
    c=tree/'.config';data=c.read_bytes()
    old=b'CONFIG_TARGET_airoha_vb235v_DEVICE_tplink_vb235v-ram-smp=y';new=b'CONFIG_TARGET_airoha_vb235v_DEVICE_tplink_vb235v-ram-npu=y'
    assert old in data or new in data;c.write_bytes(data.replace(old,new))
    print('M68 NPU profile prepared; firmware remains private input, no device commands sent.')
if __name__=='__main__':main()
