#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Admit built normal image with exact production C checker on native host."""
import argparse,hashlib,json,subprocess,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
def main():
 p=argparse.ArgumentParser();p.add_argument('tree',type=Path);p.add_argument('output',type=Path);a=p.parse_args();out=a.output
 lib=a.tree/'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60/scripts/dtc/libfdt';src=HERE.parent/'m73-persistent-system'
 with tempfile.TemporaryDirectory(prefix='m83-native-admission-') as temp:
  root=Path(temp);checker=root/'checker';extracted=root/'admitted'
  extracted.mkdir(mode=0o700)
  subprocess.run(['cc','-O2','-std=c11','-D_GNU_SOURCE','-Wall','-Wextra','-Werror','-I'+str(lib),'-I'+str(src),str(src/'image-check.c')]+[str(lib/f) for f in ['fdt.c','fdt_ro.c','fdt_strerror.c']]+['-o',str(checker)],check=True,capture_output=True)
  result=json.loads(subprocess.check_output([str(checker),str(out/'sysupgrade.bin'),str(extracted)],text=True));assert result['complete']
  manifest=json.loads((out/'manifest.json').read_text());verified={}
  for name,artifact in [('kernel.bin','kernel.itb'),('rootfs.bin','rootfs.squashfs')]:
   data=(extracted/name).read_bytes();row=manifest['artifact_sha256'][artifact]
   assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
   verified[name]=row
  report={'passed':True,'exact_production_C_checker_native_host':True,'actual_extracted_parts_match_manifest':verified,'device_accessed':False}
  (out/'production-admission-host.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
