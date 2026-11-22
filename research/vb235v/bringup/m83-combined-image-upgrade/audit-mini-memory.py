#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Audit mini against the observed M84 normal-core memory map, offline only."""
import argparse,hashlib,json,re
from pathlib import Path
HERE=Path(__file__).resolve().parent
RESIDENT=(0x9af52b70,0xa0000000)
LIVE=[(0x80000000,0x80050000),(0x84000000,0x84100000),(0x8b000000,0x8b200000),(0x97ff0000,0x97ff1000),RESIDENT]
def main():
 p=argparse.ArgumentParser();p.add_argument('mini',type=Path);p.add_argument('uboot_source',type=Path);p.add_argument('uboot_config',type=Path);p.add_argument('bdinfo',type=Path);a=p.parse_args()
 r=json.loads((a.mini/'manifest.json').read_text());log=a.bdinfo.read_text();cfg=a.uboot_config.read_text()
 # Assert this report refers to the actual recorded map, not an assumed board.
 for address in (0x80000000,0x9fffffff,0x9ff5a000,0x9af52b70):assert f'{address:08x}' in log.lower()
 observed=[(int(lo,16),int(hi,16)+1) for lo,hi in re.findall(r'reserved\[\d+\]\s+\[0x([0-9a-f]+)-0x([0-9a-f]+)\]',log.lower())]
 assert observed==LIVE,'Recorded live LMB map changed'
 assert 'CONFIG_SYS_BOOT_RAMDISK_HIGH=y' in cfg and 'CONFIG_SYS_FDT_PAD=0x3000' in cfg
 known=r['memory_audit']['regions'];reserved=r['memory_audit']['DT_reserved_memory']
 def clear(region,others):
  for low,high in others:assert region['end']<=low or high<=region['start'],region
 for region in known[:2]:clear(region,LIVE)
 # Exact M73 MAX allocator rounds down beneath its highest reserved block.
 initrd=(RESIDENT[0]-r['ramdisk_bytes'])&~0xfff
 fdtlen=r['memory_audit']['FIT_inline_payloads']['fdt']['bytes']+0x3000
 fdt=(initrd-fdtlen)&~0xfff
 predictions=[{'name':'predicted relocated initrd','start':initrd,'end':initrd+r['ramdisk_bytes']},
              {'name':'predicted padded FDT','start':fdt,'end':fdt+fdtlen}]
 for region in predictions:
  clear(region,LIVE+[(v['start'],v['end']) for v in known+reserved])
 clear(predictions[0],[(predictions[1]['start'],predictions[1]['end'])])
 sources={}
 for name in ['boot/image-board.c','boot/image-fdt.c','boot/bootm.c','cmd/bootm.c','drivers/serial/ns16550.c']:
  sources[name]=hashlib.sha256((a.uboot_source/name).read_bytes()).hexdigest()
 result={'schema':1,'mini_fit_sha256':r['mini_fit_sha256'],'bdinfo_sha256':hashlib.sha256(a.bdinfo.read_bytes()).hexdigest(),
  'source_sha256':sources,'uboot_config_sha256':hashlib.sha256(a.uboot_config.read_bytes()).hexdigest(),
  'observed_before_upload_LMB':[{'start':lo,'end':hi} for lo,hi in LIVE],
  'known_RAM_ranges_disjoint':True,'predicted_relocations':predictions,
  'prediction_assumptions':['bootm_low/size/mapsize, initrd_high, fdt_high unset','no new LMB allocations since M84 bdinfo'],
  'staged_boot_required':['CRC32 matches uploaded bytes','iminfo all SHA256 hashes pass','QDMA both low nibbles zero','RAM-only bootargs exactly match mini safe chosen args','bootm start 90000000','bootm loados','bootm ramdisk','bootm fdt','capture actual relocation ranges and bdinfo before prep/go; stop if any overlap'],
  'hardware_relocations_verified':False,'kernel_boot_authorized_by_this_report':False,'flash_writes':False}
 (a.mini/'memory-live-baseline-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
