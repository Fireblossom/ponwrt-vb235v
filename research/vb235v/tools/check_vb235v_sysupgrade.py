#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise full-image inspection with real mkimage, SquashFS and upstream fwtool."""
import argparse, hashlib, json, os, struct, subprocess, tempfile, zlib
from pathlib import Path
from fdt_board_inventory import parse
from inspect_vb235v_sysupgrade import inspect, envelope, MAX_IMAGE

p=argparse.ArgumentParser();p.add_argument('--build-base',type=Path,required=True)
p.add_argument('--fwtool-source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
b=a.build_base;tools=b/'m41-squashfs-tools';env=os.environ.copy()
env['PATH']=str(b/'uboot-tools/usr/bin')+':'+env.get('PATH','')
env['LD_LIBRARY_PATH']=':'.join(str(x) for x in [tools/'lib/x86_64-linux-gnu',tools/'usr/lib/x86_64-linux-gnu',b/'uboot-tools/usr/lib/x86_64-linux-gnu'])
env['SOURCE_DATE_EPOCH']='1794787200'
kernel_fixture=(b/'m34-ubi-fixture/fit.itb').read_bytes();nodes,_=parse(kernel_fixture,max_bytes=0x5000000)
kernel=nodes['/images/kernel']['data'];mkimage=b/'uboot-factory-slot0-m40-build/tools/mkimage'
checks=0;negative=0
def rejected(data,sha=None):
 global negative,checks
 try:inspect(data,sha)
 except (ValueError,KeyError,struct.error):negative+=1;checks+=1;return
 raise AssertionError('Malformed full image accepted')
def seal(payload,meta):
 if isinstance(meta,dict):meta=json.dumps(meta,separators=(',',':')).encode()+b'\n'
 value=payload+bytes(8)+meta
 return value+struct.pack('>IIB3sI',0x46577830,(~zlib.crc32(value))&0xffffffff,1,bytes(3),len(meta)+24)

with tempfile.TemporaryDirectory(prefix='vb235v-full-sysupgrade-') as td:
 t=Path(td);rootfs=t/'root';rootfs.mkdir();(rootfs/'format-fixture.txt').write_text('VB235v offline format fixture; never boot or flash this image.\n')
 sq=t/'root.squashfs'
 subprocess.run([str(tools/'usr/bin/mksquashfs'),str(rootfs),str(sq),'-noappend','-comp','xz','-all-root','-no-xattrs','-no-exports','-no-progress','-processors','1'],env=env,check=True,capture_output=True)
 subprocess.run([str(tools/'usr/bin/unsquashfs'),'-d',str(t/'unpacked'),str(sq)],env=env,check=True,capture_output=True)
 assert (t/'unpacked/format-fixture.txt').read_bytes()==(rootfs/'format-fixture.txt').read_bytes();checks+=1
 (t/'kernel.lzma').write_bytes(kernel)
 (t/'board.dts').write_text('/dts-v1/; / { compatible="tplink,vb235v", "airoha,an7583"; #address-cells=<2>; #size-cells=<2>; memory@80000000 { device_type="memory"; reg=<0 0x80000000 0 0x20000000>; }; };\n')
 subprocess.run(['dtc','-I','dts','-O','dtb','-o',str(t/'board.dtb'),str(t/'board.dts')],env=env,check=True,capture_output=True)
 its='''/dts-v1/;
/ { description="OFFLINE FORMAT FIXTURE, NEVER BOOT OR FLASH"; #address-cells=<1>;
 images {
  kernel { data=/incbin/("kernel.lzma"); type="kernel"; arch="arm64"; os="linux"; compression="lzma"; load=<0x80200000>; entry=<0x80200000>; hash-1 { algo="sha256"; }; };
  fdt { data=/incbin/("board.dtb"); type="flat_dt"; arch="arm64"; compression="none"; hash-1 { algo="sha256"; }; };
 };
 configurations { default="conf"; conf { kernel="kernel"; fdt="fdt"; }; };
};
'''
 (t/'image.its').write_text(its)
 def make_fit(name,source=its,external=False):
  (t/'image.its').write_text(source)
  subprocess.run([str(mkimage)]+(['-E'] if external else [])+['-f','image.its',name],cwd=t,env=env,check=True,capture_output=True)
  return (t/name).read_bytes()
 fit=make_fit('kernel.itb')
 meta={'metadata_version':'1.1','compat_version':'1.0','supported_devices':['tplink,vb235v'],'version':{'target':'airoha/an7583'}}
 (t/'metadata.json').write_text(json.dumps(meta)+'\n')
 subprocess.run(['cc','-O2',str(a.fwtool_source/'fwtool.c'),'-o',str(t/'fwtool')],check=True)
 def payload_for(value):return value+bytes((-len(value))%0x20000)+sq.read_bytes()
 payload=payload_for(fit);image=t/'full-sysupgrade.bin';image.write_bytes(payload)
 subprocess.run([str(t/'fwtool'),'-I',str(t/'metadata.json'),str(image)],check=True)
 raw=image.read_bytes();sha=hashlib.sha256(raw).hexdigest();report=inspect(raw,sha);checks+=1
 assert report['rootfs_offset']%0x20000==0 and report['metadata_board_matches'] and not report['upgrade_authorized'];checks+=1
 assert report['kernel_uncompressed_bytes']>1024*1024 and report['fit_bytes']>1024*1024;checks+=1
 assert envelope(raw)[0]==len(payload);checks+=1
 # Correct outer CRC must not hide role, kernel hash, board or rootfs defects.
 broken=bytearray(payload);at=payload.find(kernel);assert at>=0;broken[at+100]^=1;rejected(seal(broken,meta))
 root_at=report['rootfs_offset']
 for offset,value in [(root_at,0),(root_at+20,6),(root_at+28,3),(root_at+12,1234)]:
  bad=bytearray(payload);struct.pack_into('<I' if offset in [root_at,root_at+12] else '<H',bad,offset,value);rejected(seal(bad,meta))
 bad=bytearray(payload);struct.pack_into('<Q',bad,root_at+40,len(payload)+1);rejected(seal(bad,meta))
 for offset in [48,64,72]:
  bad=bytearray(payload);struct.pack_into('<Q',bad,root_at+offset,0xffffffffffffffff);rejected(seal(bad,meta))
 for field,value in [('supported_devices',['nokia,xg-040g-mf']),('supported_devices','tplink,vb235v'),('supported_devices',['tplink,vb235v','tplink,vb235v']),('metadata_version','2.0'),('compat_version','2.0')]:
  bad=dict(meta);bad[field]=value;rejected(seal(payload,bad))
 rejected(seal(payload,b'{"metadata_version":"1.1","compat_version":"1.0","supported_devices":["tplink,vb235v"],"supported_devices":["tplink,vb235v"]}'))
 rejected(raw,'0'*64)
 rejected(seal(payload_for(make_fit('bad-address.itb',its.replace('0x80200000','0x80000000'))),meta))
 rejected(seal(payload_for(make_fit('recovery.itb',its.replace('conf { kernel=','conf { vb235v,recovery-core; kernel='))),meta))
 rejected(seal(payload_for(make_fit('external.itb',external=True)),meta))
 # Existing diagnostic DTB has a different compatibility and must be refused.
 rejected(seal(payload_for(kernel_fixture),meta))
 for at in [0,4,root_at-1,root_at,root_at+40,len(raw)-1]:
  bad=bytearray(raw);bad[at]^=1;rejected(bad)
 rejected(b'\0'*(MAX_IMAGE+1))
 # An opaque signature remains explicitly unverified.
 sig=t/'signature.bin';sig.write_bytes(b'opaque-untrusted-test-signature')
 subprocess.run([str(t/'fwtool'),'-S',str(sig),str(image)],check=True)
 signed=inspect(image.read_bytes());assert signed['signature_present'] and not signed['signature_cryptographically_verified'] and not signed['upgrade_authorized'];checks+=1
 report.update(checks=checks,negative_cases=negative,real_mkimage_and_mksquashfs_fixture=True,
   real_upstream_fwtool_metadata_and_signature=True,rootfs_extraction_roundtrip_verified=True,
   source_kernel='Previously built native Linux diagnostic kernel; fixture DTB/rootfs are offline test data',
   hardware_boot_tested=False,NAND_operations=False)
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
