#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise real FIT/DT builder in private temporary output, no tree writes."""
import argparse,hashlib,json,os,shutil,struct,subprocess,sys,tempfile,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'tools'))
from fdt_board_inventory import parse
from inspect_vb235v_sysupgrade import image_data,text
def main():
 p=argparse.ArgumentParser();p.add_argument('tree',type=Path);a=p.parse_args();tree=a.tree
 kd=tree/'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v';normal=kd/'image-an7583-tplink_vb235v.dtb'
 original=normal.read_bytes();before,_=parse(original)
 with tempfile.TemporaryDirectory(prefix='m83-installer-role-') as tmp:
  root=Path(tmp);kernel=root/'kernel.lzma';kernel.write_bytes(b'synthetic not executed kernel payload')
  shutil.copyfile(HERE/'mkits-vb235v-install-m83.py',root/'mkits-vb235v-install-m83.py')
  shutil.copyfile(tree/'target/linux/airoha/image/mkits-vb235v-system.py',root/'mkits-vb235v-system.py')
  its=root/'installer.its';subprocess.run(['python3',str(root/'mkits-vb235v-install-m83.py'),str(kernel),str(normal),str(its)],check=True)
  env=dict(os.environ,PATH=str(kd/'linux-6.18.60/scripts/dtc')+':'+os.environ['PATH'],SOURCE_DATE_EPOCH='1795303547')
  subprocess.run([str(tree/'staging_dir/host/bin/mkimage'),'-f',str(its),str(root/'installer.itb')],check=True,capture_output=True,env=env)
  raw=(root/'installer.itb').read_bytes();nodes,_=parse(raw);conf=nodes['/configurations/'+text(nodes['/configurations']['default'])]
  assert conf['vb235v,ram-installer']==struct.pack('>I',1) and 'vb235v,firmware-image' not in conf
  _,dtb=image_data(nodes,text(conf['fdt']),'flat_dt');after,_=parse(dtb)
  assert set(before)==set(after)
  for name,properties in before.items():
   expected=dict(properties)
   if name=='/chosen':expected['bootargs']=after[name]['bootargs']
   assert expected==after[name],'Unexpected DT mutation '+name
  args=after['/chosen']['bootargs'];assert b'rdinit=/init' in args
  for forbidden in [b'ubi.mtd=',b'ubi.block=',b'rootfstype=',b'root=']:assert forbidden not in args
  assert normal.read_bytes()==original
  lib=kd/'linux-6.18.60/scripts/dtc/libfdt';src=HERE.parent/'m73-persistent-system';checker=root/'checker'
  subprocess.run(['cc','-O2','-std=c11','-D_GNU_SOURCE','-Wall','-Wextra','-Werror','-I'+str(lib),'-I'+str(src),str(src/'image-check.c')]+[str(lib/f) for f in ['fdt.c','fdt_ro.c','fdt_strerror.c']]+['-o',str(checker)],check=True,capture_output=True)
  meta=json.dumps({'metadata_version':'1.1','compat_version':'1.0','supported_devices':['tplink,vb235v']}).encode();body=raw+bytes(128*1024)+bytes(8)+meta
  framed=body+struct.pack('>IIB3sI',0x46577830,(~zlib.crc32(body))&0xffffffff,1,bytes(3),len(meta)+24);path=root/'framed.bin';path.write_bytes(framed)
  result=subprocess.run([str(checker),str(path),str(root/'admitted')],capture_output=True,text=True)
  assert result.returncode!=0 and not (root/'admitted').exists() and 'vb235v,firmware-image' in result.stderr,result
 print(json.dumps({'passed':True,'normal_DT_unchanged':True,'RAM_DT_only_chosen_bootargs_changed':True,'no_automatic_UBI_attach_args':True,'installer_role_marker':True,'production_checker_rejects_board_metadata_framed_installer':True,'source_DT_sha256':hashlib.sha256(original).hexdigest(),'device_accessed':False},indent=2))
if __name__=='__main__':main()
