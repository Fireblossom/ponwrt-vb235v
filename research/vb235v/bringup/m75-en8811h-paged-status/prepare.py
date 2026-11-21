#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Prepare M73 persistent system plus the page-preserving PHY status fix."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('tree',type=Path);p.add_argument('--revision',default='M75-phy-page-v1');a=p.parse_args()
 assert re.fullmatch(r'M75-[A-Za-z0-9_.-]{1,48}',a.revision)
 tree=a.tree.resolve(strict=True)
 subprocess.run(['python3',str(HERE.parent/'m73-persistent-system/prepare.py'),str(tree),'--revision','M73-page-fix-preparation'],check=True)
 kernel=tree/'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60'
 hashes=json.loads((HERE/'source-hashes.json').read_text())
 for name,row in hashes.items():
  actual=hashlib.sha256((kernel/name).read_bytes()).hexdigest()
  assert actual in [row['baseline'],row['candidate']],'Different PHY prerequisite'
  if actual==row['baseline']:
   subprocess.run(['patch','-p1','--batch','--fuzz=0','-i',str(HERE/'en8811h-paged-status.patch')],cwd=kernel,check=True)
  assert hashlib.sha256((kernel/name).read_bytes()).hexdigest()==row['candidate']
 dest=tree/'target/linux/airoha/patches-6.18/963-vb235v-en8811h-standard-page.patch'
 patch=(HERE/'en8811h-paged-status.patch').read_bytes()
 if dest.exists():assert dest.read_bytes()==patch
 else:dest.write_bytes(patch)
 # Persist the M65 guard in the package patch queue, not only build_dir.
 # A clean package rebuild otherwise silently restores reference fallback.
 calibration=(HERE.parent/'m65-wifi-station/mt76-vb235v-private-calibration.patch').read_bytes()
 dest=tree/'package/kernel/mt76/patches/120-vb235v-private-art-calibration.patch'
 if dest.exists():assert dest.read_bytes()==calibration
 else:dest.write_bytes(calibration)
 (tree/'files/etc/vb235v-system-revision').write_bytes((a.revision+'\n').encode())
 print('M75 standard-page PHY read and persistent M73 prerequisites verified.')
if __name__=='__main__':main()
