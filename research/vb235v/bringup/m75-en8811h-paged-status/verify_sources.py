#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Verify kernel integration and the separately rebuilt mt76 calibration guard."""
import argparse,hashlib,importlib.util,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
def verify_sources(tree):
 spec=importlib.util.spec_from_file_location('m72_verify',HERE.parent/'m72-phy-reset-receiver/verify_sources.py')
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 report=m.verify_sources(tree)
 kernel=tree/'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60'
 for name,row in json.loads((HERE/'source-hashes.json').read_text()).items():
  digest=hashlib.sha256((kernel/name).read_bytes()).hexdigest()
  assert digest==row['candidate'],'PHY page fix missing from prepared kernel'
  report['source_sha256'][name]=digest
 assert (tree/'target/linux/airoha/patches-6.18/963-vb235v-en8811h-standard-page.patch').read_bytes()==(HERE/'en8811h-paged-status.patch').read_bytes()
 persistent=HERE.parent/'m73-persistent-system'
 for name,row in json.loads((persistent/'source-hashes.json').read_text()).items():
  digest=hashlib.sha256((kernel/name).read_bytes()).hexdigest()
  assert digest==row['candidate'],'Persistent NAND source changed'
  report['source_sha256'][name]=digest
 for name in ['vb235v-map.c','vb235v-map.h','vb235v-system-admit.h','vb235v-system-anchors.h','vb235v-hybrid-policy.h']:
  relative=('include/linux/mtd/' if name=='vb235v-hybrid-policy.h' else 'drivers/mtd/nand/spi/')+name
  digest=hashlib.sha256((kernel/relative).read_bytes()).hexdigest()
  assert digest==hashlib.sha256((persistent/name).read_bytes()).hexdigest(),'NAND policy/anchor differs'
  report['source_sha256'][relative]=digest
 assert (tree/'target/linux/airoha/patches-6.18/962-vb235v-persistent-nand.patch').read_bytes()==(persistent/'persistent-nand.patch').read_bytes()
 report['kernel_NAND_and_PHY_patch_queues_verified']=True
 mt76=tree/'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/mt76-2026.10.28~0936617d/mt7996/eeprom.c'
 digest=hashlib.sha256(mt76.read_bytes()).hexdigest()
 assert digest==json.loads((HERE.parent/'m65-wifi-station/source-hashes.json').read_text())['candidate'],'Private calibration guard lost during mt76 rebuild'
 report['source_sha256']['mt76/mt7996/eeprom.c']=digest
 patch=tree/'package/kernel/mt76/patches/120-vb235v-private-art-calibration.patch'
 assert patch.read_bytes()==(HERE.parent/'m65-wifi-station/mt76-vb235v-private-calibration.patch').read_bytes()
 report['mt76_calibration_guard_persisted_in_package_queue']=True
 return report
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('tree',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 report=verify_sources(a.tree);a.output.write_bytes((json.dumps(report,indent=2)+'\n').encode())
 print(str(len(report['source_sha256']))+' integrated source files and all persistent patch queues verified.')
