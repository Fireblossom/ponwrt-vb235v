#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Prepare integrated RAM acceleration after verified M68; private blobs stay local."""
import argparse,hashlib,json,re,subprocess
from preserve_pcie import preserve_pcie
from pathlib import Path
HERE=Path(__file__).resolve().parent

def install(source,dest,execute=False):
    data=source.read_bytes();dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():
        assert dest.read_bytes()==data,'Different existing file: '+str(dest)
        return
    dest.write_bytes(data);dest.chmod(0o755 if execute else 0o644)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('tree',type=Path);p.add_argument('--npu-inputs',type=Path,required=True);p.add_argument('--wifi-eeprom',type=Path,required=True)
    a=p.parse_args();tree=a.tree.resolve(strict=True)
    assert subprocess.check_output(['git','-C',str(tree),'rev-parse','HEAD'],text=True).strip()=='dcf140cb1d5d2c15c1d7c353c95c4c2a56629820'
    kernel=tree/'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60'
    preserve_pcie(tree,kernel)
    for name,expect in json.loads((HERE.parent/'m68-npu/source-hashes.json').read_text()).items():
        assert hashlib.sha256((kernel/name).read_bytes()).hexdigest()==expect['candidate'],'M68 NPU prerequisite missing'
    source=kernel/'net/netfilter/nf_flow_table_offload.c'
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    if digest=='f4a24675d8199ee0a60f044e28a1d1e2bc95d4f48965d881181f7995377b165f':
        subprocess.run(['patch','-p1','--batch','--fuzz=0','-i',str(HERE.parent/'m69-flow-cleanup/flowtable-unbind-cleanup.patch')],cwd=kernel,check=True)
    assert hashlib.sha256(source.read_bytes()).hexdigest()=='7454aebaffb09952e24decf95003af62d3ebacf807a68fa42c4f0592f1a93770'
    for name,expect in json.loads((HERE/'crypto-source-hashes.json').read_text()).items():
        source=kernel/name;digest=hashlib.sha256(source.read_bytes()).hexdigest()
        if digest==expect['baseline']:
            subprocess.run(['patch','-p1','--batch','--fuzz=0','-i',str(HERE/'eip93-verified-primitives.patch')],cwd=kernel,check=True)
        assert hashlib.sha256(source.read_bytes()).hexdigest()==expect['candidate'],'Unexpected EIP93 source'
    # Keep reviewed changes if OpenWrt recreates the prepared kernel sources.
    for source,dest in [('950-vb235v-npu-layout-development.patch','950-vb235v-npu-layout.patch'),
     ('951-vb235v-npu-layout-binding.patch','951-vb235v-npu-binding.patch'),
     ('m69-flow-cleanup/flowtable-unbind-cleanup.patch','954-vb235v-flowtable-cleanup.patch'),
     ('m70-integrated-accel/eip93-verified-primitives.patch','955-vb235v-eip93-primitives.patch')]:
        install(HERE.parent/source,tree/'target/linux/airoha/patches-6.18'/dest)
    manifest=json.loads((HERE/'private-inputs.json').read_text())
    for name,expect in manifest.items():
        path=a.wifi_eeprom if expect['input']=='eeprom' else a.npu_inputs/expect['input']
        data=path.read_bytes();assert len(data)==expect['bytes'] and hashlib.sha256(data).hexdigest()==expect['sha256'],'Wrong private input: '+name
        dest=tree/'files'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists():assert dest.read_bytes()==data
        dest.write_bytes(data);dest.chmod(0o600)
    install(HERE/'an7583-tplink_vb235v-ram-accel.dts',tree/'target/linux/airoha/dts/an7583-tplink_vb235v-ram-accel.dts')
    install(HERE/'image.mk',tree/'target/linux/airoha/image/vb235v-accel.mk')
    install(HERE/'99-vb235v-ram-accel',tree/'target/linux/airoha/vb235v/base-files/etc/uci-defaults/99-vb235v-ram-accel',True)
    install(HERE/'wireless',tree/'files/etc/config/wireless')
    recipe=tree/'target/linux/airoha/image/vb235v.mk';include=b'\ninclude $(TOPDIR)/target/linux/airoha/image/vb235v-accel.mk\n'
    if include not in recipe.read_bytes():recipe.write_bytes(recipe.read_bytes()+include)
    config=tree/'target/linux/airoha/vb235v/config-6.18'
    content=config.read_text()
    for name in ['EXPERT','CRYPTO_SELFTESTS','CRYPTO_SELFTESTS_FULL']:
        content=re.sub(r'^(?:# )?CONFIG_'+name+r'(?:=.*| is not set)\n','',content,flags=re.M)+'CONFIG_'+name+'=y\n'
    config.write_bytes(content.encode())
    config=tree/'.config';content=config.read_text()
    content=content.replace('CONFIG_TARGET_airoha_vb235v_DEVICE_tplink_vb235v-ram-npu=y','CONFIG_TARGET_airoha_vb235v_DEVICE_tplink_vb235v-ram-accel=y')
    assert 'CONFIG_TARGET_airoha_vb235v_DEVICE_tplink_vb235v-ram-accel=y' in content
    packages=['kmod-crypto-hw-eip93','kmod-crypto-user','kmod-crypto-cbc','kmod-crypto-ecb','kmod-crypto-ctr',
     'kmod-cfg80211','kmod-mac80211','kmod-mt76-connac','kmod-mt76-core','kmod-mt7990-firmware','kmod-mt7996e',
     'hostapd-common','wpad-mbedtls','ethtool','iw','kmod-phy-airoha-en8811h','airoha-en8811h-firmware']
    for name in packages:
        symbol='CONFIG_PACKAGE_'+name
        content=re.sub(r'^(?:# )?'+re.escape(symbol)+r'(?:=.*| is not set)\n','',content,flags=re.M)+symbol+'=y\n'
    config.write_bytes(content.encode())
    print('Integrated NPU firmware, private Wi-Fi calibration, M69 fix, EIP93 and MDIO discovery prepared; no router commands sent.')

if __name__=='__main__':main()
