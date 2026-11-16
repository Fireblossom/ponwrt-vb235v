# SPDX-License-Identifier: GPL-2.0-only
"""Create a hash-checked LZMA FIT for serial RAM testing and size budgeting."""
from pathlib import Path
import argparse,hashlib,json,lzma,os,subprocess,sys,tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fdt_board_inventory import parse
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--build',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();B=args.build.resolve();OUT=args.output.resolve()
OUT.mkdir(parents=True,exist_ok=False)
binary=(B/'u-boot.bin').read_bytes();dtb=(B/'u-boot.dtb').read_bytes()
encoded=lzma.compress(binary,format=lzma.FORMAT_ALONE)
with tempfile.TemporaryDirectory(prefix='vb235v-recovery-fit-') as d:
 p=Path(d);(p/'core.lzma').write_bytes(encoded);(p/'board.dtb').write_bytes(dtb)
 (p/'recovery.its').write_text('''/dts-v1/;
/ { description="VB235v recovery development core"; #address-cells=<1>;
 images {
  core { description="recovery U-Boot"; data=/incbin/("core.lzma"); type="kernel"; arch="arm64"; os="linux"; compression="lzma"; load=<0x81e00000>; entry=<0x81e00000>; hash-1 { algo="sha256"; }; };
  fdt { description="VB235v recovery board"; data=/incbin/("board.dtb"); type="flat_dt"; arch="arm64"; compression="none"; hash-1 { algo="sha256"; }; };
 };
 configurations { default="recovery"; recovery { compatible="tplink,vb235v"; vb235v,recovery-core; kernel="core"; fdt="fdt"; }; };
};
''')
 env=os.environ.copy();env['SOURCE_DATE_EPOCH']='1794787200'
 r=subprocess.run([str(B/'tools/mkimage'),'-f','recovery.its','recovery.itb'],cwd=p,env=env,capture_output=True,text=True)
 if r.returncode:raise RuntimeError(r.stderr)
 fit=(p/'recovery.itb').read_bytes();nodes,_=parse(fit)
 assert nodes['/images/core']['data']==encoded
 assert nodes['/images/core/hash-1']['value']==hashlib.sha256(encoded).digest()
 assert nodes['/images/fdt']['data']==dtb
 assert nodes['/images/fdt/hash-1']['value']==hashlib.sha256(dtb).digest()
 assert lzma.decompress(encoded,format=lzma.FORMAT_ALONE)==binary
 (OUT/'vb235v-recovery-core-RAM-ONLY.itb').write_bytes(fit)
 (OUT/'fit-list.txt').write_text(r.stdout)
 (OUT/'recovery.its').write_text((p/'recovery.its').read_text())
 (OUT/'u-boot.bin').write_bytes(binary)
 report={'binary_bytes':len(binary),'binary_sha256':hashlib.sha256(binary).hexdigest(),
  'compressed_core_bytes':len(encoded),'fit_bytes':len(fit),'fit_sha256':hashlib.sha256(fit).hexdigest(),
  'fit_subimage_hashes_verified':True,'lzma_roundtrip_verified':True,
  'fits_in_one_256k_erase_block':len(fit)<=0x40000,'hardware_validation':'not evaluated by packaging tool','flashed':False}
 (OUT/'manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
