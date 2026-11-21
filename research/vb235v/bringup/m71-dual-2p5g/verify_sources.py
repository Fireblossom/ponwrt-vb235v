# SPDX-License-Identifier: GPL-2.0-only
"""Check all integrated source prerequisites after OpenWrt kernel preparation."""
import argparse,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
def verify_sources(tree):
    kernel=tree/'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60'
    expected={}
    for folder,manifest in [('m68-npu','source-hashes.json'),('m70-integrated-accel','crypto-source-hashes.json'),('m71-dual-2p5g','integration-source-hashes.json')]:
        for name,row in json.loads((HERE.parent/folder/manifest).read_text()).items():expected[name]=row['candidate']
    for folder,source,manifest in [('m63-ram-pcie','pcie-mediatek-gen3.c','host-source-hashes.json'),('m64-dual-pcie','pcie-mediatek.c','second-host-source-hashes.json')]:
        expected['drivers/pci/controller/'+source]=json.loads((HERE.parent/folder/manifest).read_text())['candidate']
    expected['net/netfilter/nf_flow_table_offload.c']='7454aebaffb09952e24decf95003af62d3ebacf807a68fa42c4f0592f1a93770'
    for name in ['phy-vb235v-qp-pcie.c','qphy-fields.h','qphy-sequence.inc']:
        relative='drivers/phy/airoha/'+name
        expected[relative]=hashlib.sha256((HERE.parent/'m64-dual-pcie'/name).read_bytes()).hexdigest()
        assert hashlib.sha256((tree/'target/linux/airoha/files'/relative).read_bytes()).hexdigest()==expected[relative],'QPHY overlay differs'
    actual={name:hashlib.sha256((kernel/name).read_bytes()).hexdigest() for name in expected}
    assert actual==expected,'Integrated source prerequisite changed'
    assert (kernel/'drivers/phy/airoha/Makefile').read_bytes().count(b'obj-y += phy-vb235v-qp-pcie.o')==1
    return {'complete':True,'source_sha256':actual,'QPHY_persisted_in_target_overlay':True}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('tree',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.write_bytes((json.dumps(verify_sources(a.tree),indent=2)+'\n').encode())
    print('All 14 integrated source hashes and the persistent QPHY overlay verified.')
