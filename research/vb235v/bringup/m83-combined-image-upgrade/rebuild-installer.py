#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Lease-only focused repair of the installer role after a successful build."""
import argparse,fcntl,hashlib,json,os,shutil,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('tree',type=Path);p.add_argument('output',type=Path);p.add_argument('--resume',action='store_true');a=p.parse_args();tree=a.tree.resolve();out=a.output.resolve();assert out.is_dir()
 with (tree/'.m55-build.lock').open('w') as lease:
  fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
  subprocess.run(['python3',str(HERE/'prepare.py'),str(tree),'--check-only'],check=True)
  paths=['bin/targets/airoha/vb235v/ponwrt-airoha-vb235v-tplink_vb235v-squashfs-sysupgrade.bin','build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/Image','build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/image-an7583-tplink_vb235v.dtb','build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/tplink_vb235v-kernel.bin']
  before=json.loads((out/'normal-before-installer-repair.json').read_text()) if a.resume else {path:sha(tree/path) for path in paths}
  if not a.resume:(out/'normal-before-installer-repair.json').write_text(json.dumps(before,indent=2)+'\n')
  role=json.loads((HERE/'installer-role-hashes.json').read_text());dest=tree/role['path']
  assert sha(tree/role['normal_builder_path'])==role['normal_builder_sha256']
  wrapper=tree/'target/linux/airoha/image/mkits-vb235v-install-m83.py'
  if not a.resume:
   assert sha(dest)==role['baseline'] and not wrapper.exists()
   subprocess.run(['patch','--batch','--fuzz=0','-p1','-d',str(tree),'-i',str(HERE/'installer-role.patch')],check=True)
   shutil.copyfile(HERE/wrapper.name,wrapper);wrapper.chmod(0o755)
  assert sha(dest)==role['candidate'] and wrapper.read_bytes()==(HERE/wrapper.name).read_bytes()
  environment=dict(os.environ,PATH=':'.join(path for path in os.environ['PATH'].split(':') if path.startswith('/') and not any(ch.isspace() for ch in path)))
  with (out/('installer-finish.log' if a.resume else 'installer-rebuild.log')).open('wb') as log:
   if not a.resume:subprocess.run(['make','-j4','target/linux/install','V=s'],cwd=tree,stdout=log,stderr=subprocess.STDOUT,check=True,env=environment)
   # Direct V=s metadata target recursion contaminates the upstream value
   # query's stdout. Run ordinary world finalization as in the successful build.
   subprocess.run(['make','-j4'],cwd=tree,stdout=log,stderr=subprocess.STDOUT,check=True,env=environment)
  after={path:sha(tree/path) for path in paths}
  assert before==after,'Normal artifact changed during isolated installer-role repair'
  (out/'normal-preserved-by-installer-repair.json').write_text(json.dumps({'byte_hashes_unchanged':True,'files':after},indent=2)+'\n')
  subprocess.run(['python3',str(HERE/'audit.py'),str(tree),str(out)],check=True)
if __name__=='__main__':main()
