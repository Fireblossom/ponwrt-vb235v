#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise the actual integration twice in an isolated minimal tree copy."""
import argparse,hashlib,importlib.util,json,os,shutil,subprocess,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
def main():
 p=argparse.ArgumentParser();p.add_argument('tree',type=Path);a=p.parse_args();source=a.tree.resolve()
 spec=importlib.util.spec_from_file_location('m75fixture',HERE.parent/'m75-en8811h-paged-status/verify_sources.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 report=m.verify_sources(source);k='build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60';mt=str(Path(k).parent/'mt76-2026.10.28~0936617d')
 paths=['.config','files/etc/vb235v-system-revision',k+'/.config',k+'/drivers/phy/airoha/Makefile','target/linux/airoha/vb235v/config-6.18','target/linux/airoha/dts/an7583-tplink_vb235v.dts','target/linux/airoha/patches-6.18/962-vb235v-persistent-nand.patch','target/linux/airoha/patches-6.18/963-vb235v-en8811h-standard-page.patch','package/network/services/dropbear/files/dropbear.init','package/kernel/mt76/Makefile']
 paths += ['target/linux/airoha/image/vb235v-persistent.mk','target/linux/airoha/image/mkits-vb235v-system.py']
 paths += [mt+'/'+name.removeprefix('mt76/') if name.startswith('mt76/') else k+'/'+name for name in report['source_sha256']]
 paths += [k+'/'+name for name in json.loads((HERE.parent/'m78-cpu-dvfs/source-hashes.json').read_text())]
 paths += ['target/linux/airoha/files/drivers/phy/airoha/'+name for name in ['phy-vb235v-qp-pcie.c','qphy-fields.h','qphy-sequence.inc']]
 paths += ['files/'+name for name in json.loads((HERE.parent/'m70-integrated-accel/private-inputs.json').read_text())]
 paths += [str(p.relative_to(source)) for p in (source/'package/kernel/mt76/patches').iterdir() if p.is_file()]
 paths=sorted(set(paths));before={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in paths}
 with tempfile.TemporaryDirectory(prefix='m83-prepare-fixture-') as tmp:
  tree=Path(tmp)
  for name in paths:
   dest=tree/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/name,dest)
  # git is queried read-only solely for the pinned upstream HEAD. No git
  # command in prepare writes the actual repository or its index.
  gitdir=subprocess.check_output(['git','-C',str(source),'rev-parse','--absolute-git-dir'],text=True).strip()
  (tree/'.git').write_text('gitdir: '+gitdir+'\n')
  (tree/'staging_dir').mkdir();tool='toolchain-aarch64_cortex-a53_gcc-14.4.0_musl'
  (tree/'staging_dir'/tool).symlink_to(source/'staging_dir'/tool,target_is_directory=True)
  command=['python3',str(HERE/'prepare.py'),str(tree)]
  subprocess.run(command+['--check-only'],check=True)
  subprocess.run(command,check=True)
  def snapshot():return {str(p.relative_to(tree)):hashlib.sha256(p.read_bytes()).hexdigest() for p in tree.rglob('*') if p.is_file() and not p.is_symlink() and '.git' not in p.parts}
  first=snapshot();subprocess.run(command,check=True,capture_output=True);second=snapshot()
  assert first==second,'Second prepare was not byte-idempotent'
  subprocess.run(command+['--check-only'],check=True,capture_output=True)
  # Reject a foreign dropbear source before applying any integration mutation.
  (tree/'package/network/services/dropbear/files/dropbear.init').write_text('foreign init\n')
  bad=snapshot();result=subprocess.run(command,capture_output=True)
  assert result.returncode!=0 and snapshot()==bad,'Foreign prerequisite was accepted or mutated before rejection'
 after={p:hashlib.sha256((source/p).read_bytes()).hexdigest() for p in paths};assert before==after,'Shared source changed'
 print(json.dumps({'passed':True,'isolated_fixture':True,'prepare_twice_byte_idempotent':True,'foreign_source_rejected_before_mutation':True,'shared_inputs_unchanged':len(paths),'device_accessed':False},indent=2))
if __name__=='__main__':main()
