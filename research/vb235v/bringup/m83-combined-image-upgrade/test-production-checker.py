#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Compile exact production checker natively and reject mini RAM images."""
import argparse,json,struct,subprocess,tempfile,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
def main():
 p=argparse.ArgumentParser();p.add_argument('tree',type=Path);p.add_argument('mini',type=Path);a=p.parse_args()
 lib=a.tree/'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60/scripts/dtc/libfdt';src=HERE.parent/'m73-persistent-system'
 with tempfile.TemporaryDirectory(prefix='m83-production-checker-') as temp:
  root=Path(temp);binary=root/'checker'
  command=['cc','-O2','-std=c11','-D_GNU_SOURCE','-Wall','-Wextra','-Werror','-I'+str(lib),'-I'+str(src),str(src/'image-check.c')]+[str(lib/f) for f in ['fdt.c','fdt_ro.c','fdt_strerror.c']]+['-o',str(binary)]
  subprocess.run(command,check=True,capture_output=True)
  raw=(a.mini/'cpu-mini.itb').read_bytes();meta=json.dumps({'metadata_version':'1.1','compat_version':'1.0','supported_devices':['tplink,vb235v']}).encode()
  # Give the framed negative input ordinary post-FIT padding so framing and
  # FIT-size admission pass; rejection must reach production role/count gates.
  body=raw+bytes(128*1024)+bytes(8)+meta
  framed=body+struct.pack('>IIB3sI',0x46577830,(~zlib.crc32(body))&0xffffffff,1,bytes(3),len(meta)+24)
  results=[]
  for index,data in enumerate([raw,framed]):
   path=root/f'input{index}';path.write_bytes(data)
   result=subprocess.run([str(binary),str(path),str(root/f'output{index}')],capture_output=True,text=True)
   assert result.returncode!=0 and not (root/f'output{index}').exists(),result
   assert ('single FIT configuration/two images' if index else 'complete fwtool framing/CRC') in result.stderr
   results.append({'metadata_appended':bool(index),'rejected':True,'stderr':result.stderr.strip()})
  report={'exact_production_C_checker':True,'native_host_execution':True,'mini_inputs_rejected':results,'device_accessed':False}
  (a.mini/'production-checker-host-checks.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
