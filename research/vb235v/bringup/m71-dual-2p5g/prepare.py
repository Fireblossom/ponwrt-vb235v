#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Prepare isolated dual-2.5G RAM experiment after the integrated M70 image."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'m70-integrated-accel'))
from preserve_pcie import preserve_pcie
def install(source,dest,execute=False):
    data=source.read_bytes();dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():
        assert dest.read_bytes()==data,'Different existing file: '+str(dest)
        return
    dest.write_bytes(data);dest.chmod(0o755 if execute else 0o644)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('tree',type=Path);a=p.parse_args()
    tree=a.tree.resolve(strict=True)
    assert subprocess.check_output(['git','-C',str(tree),'rev-parse','HEAD'],text=True).strip()=='dcf140cb1d5d2c15c1d7c353c95c4c2a56629820'
    kernel=tree/'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60'
    preserve_pcie(tree,kernel)
    for name,expect in json.loads((HERE.parent/'m68-npu/source-hashes.json').read_text()).items():
        assert hashlib.sha256((kernel/name).read_bytes()).hexdigest()==expect['candidate'],'NPU prerequisite missing'
    for name,expect in json.loads((HERE.parent/'m70-integrated-accel/crypto-source-hashes.json').read_text()).items():
        assert hashlib.sha256((kernel/name).read_bytes()).hexdigest()==expect['candidate'],'Verified crypto prerequisite missing'
    assert hashlib.sha256((kernel/'net/netfilter/nf_flow_table_offload.c').read_bytes()).hexdigest()=='7454aebaffb09952e24decf95003af62d3ebacf807a68fa42c4f0592f1a93770'
    hashes=json.loads((HERE/'pcs-source-hashes.json').read_text())
    root=kernel/'drivers/net/pcs/airoha'
    current={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in hashes['original']}
    if current==hashes['original']:
        for patch in ['952-vb235v-pcs-ethernet-development.patch','984-vb235v-pcs-ethernet-receiver-development.patch']:
            subprocess.run(['patch','-p1','--batch','--fuzz=0','-i',str(HERE.parent/patch)],cwd=kernel,check=True)
    integration=json.loads((HERE/'integration-source-hashes.json').read_text())
    current={name:hashlib.sha256((kernel/name).read_bytes()).hexdigest() for name in integration}
    if all(current[name]==info['baseline'] for name,info in integration.items()):
        subprocess.run(['patch','-p1','--batch','--fuzz=0','-i',str(HERE/'ethernet-integration.patch')],cwd=kernel,check=True)
    assert all(hashlib.sha256((kernel/name).read_bytes()).hexdigest()==info['candidate'] for name,info in integration.items()),'Unexpected integrated Ethernet source'
    # Preserve the reviewed changes when OpenWrt recreates its kernel tree.
    patches=[('950-vb235v-npu-layout-development.patch','950-vb235v-npu-layout.patch'),
     ('951-vb235v-npu-layout-binding.patch','951-vb235v-npu-binding.patch'),
     ('952-vb235v-pcs-ethernet-development.patch','952-vb235v-pcs-ethernet.patch'),
     ('984-vb235v-pcs-ethernet-receiver-development.patch','953-vb235v-pcs-receiver.patch'),
     ('m69-flow-cleanup/flowtable-unbind-cleanup.patch','954-vb235v-flowtable-cleanup.patch'),
     ('m70-integrated-accel/eip93-verified-primitives.patch','955-vb235v-eip93-primitives.patch'),
     ('m71-dual-2p5g/ethernet-integration.patch','960-vb235v-ethernet-integration.patch')]
    for source,dest in patches:install(HERE.parent/source,tree/'target/linux/airoha/patches-6.18'/dest)
    install(HERE/'an7583-tplink_vb235v-ram-multigig.dts',tree/'target/linux/airoha/dts/an7583-tplink_vb235v-ram-multigig.dts')
    install(HERE/'image.mk',tree/'target/linux/airoha/image/vb235v-multigig.mk')
    install(HERE/'99-vb235v-ram-multigig',tree/'target/linux/airoha/vb235v/base-files/etc/uci-defaults/99-vb235v-ram-multigig',True)
    recipe=tree/'target/linux/airoha/image/vb235v.mk';include=b'\ninclude $(TOPDIR)/target/linux/airoha/image/vb235v-multigig.mk\n'
    if include not in recipe.read_bytes():recipe.write_bytes(recipe.read_bytes()+include)
    config=tree/'.config';data=config.read_bytes()
    old=b'CONFIG_TARGET_airoha_vb235v_DEVICE_tplink_vb235v-ram-accel=y';new=b'CONFIG_TARGET_airoha_vb235v_DEVICE_tplink_vb235v-ram-multigig=y'
    assert old in data or new in data;config.write_bytes(data.replace(old,new))
    print('Dual EN8811H/PCS paths prepared. No bridge or port-up action; hardware remains unverified.')
if __name__=='__main__':main()
