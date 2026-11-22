#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Generate a read-only, exact-artifact RAM installer memory/command plan."""
import argparse,hashlib,importlib.util,json,re,struct,subprocess,sys,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'tools'))
from fdt_board_inventory import parse
from inspect_vb235v_sysupgrade import image_data,kernel_bytes,text,number
FROZEN_MANIFEST='91fd972ed13ea3df38d8f6355bd4a9718a1fc030033ea5ef7f44abc7ac9ed762'
def sha(data):return hashlib.sha256(data).hexdigest()
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('candidate',type=Path);p.add_argument('tree',type=Path);p.add_argument('--bdinfo-baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 manifest_data=(a.candidate/'manifest.json').read_bytes();assert sha(manifest_data)==FROZEN_MANIFEST
 manifest=json.loads(manifest_data);raw=(a.candidate/'installer.itb').read_bytes();expected=manifest['artifact_sha256']['installer.itb']
 assert len(raw)==expected['bytes'] and sha(raw)==expected['sha256']
 nodes,_=parse(raw,max_bytes=56*1024*1024);conf=nodes['/configurations/'+text(nodes['/configurations']['default'])]
 assert conf['vb235v,ram-installer']==struct.pack('>I',1) and not {'ramdisk','loadables','firmware','vb235v,firmware-image'}&conf.keys()
 props,kernel=image_data(nodes,text(conf['kernel']),'kernel');_,dtb=image_data(nodes,text(conf['fdt']),'flat_dt')
 image,memory=kernel_bytes(kernel,text(props['compression']));load=number(props['load']);assert load==number(props['entry'])==0x80200000
 dt,memreserve=parse(dtb);args=text(dt['/chosen']['bootargs']);assert 'rdinit=/init' in args
 assert not any(term in args for term in ['ubi.','root=','rootfstype='])
 kd=a.tree/'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v';elf=kd/'vmlinux-initramfs.debug'
 readelf=a.tree/'staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin/aarch64-openwrt-linux-musl-readelf'
 symbols=subprocess.check_output([str(readelf),'-sW',str(elf)],text=True)
 names={name:int(value,16) for value,name in re.findall(r'^\s*\d+:\s+([0-9a-fA-F]+)\s+\d+\s+\w+\s+\w+\s+\w+\s+\S+\s+(_text|_edata|__bss_start|__bss_stop|_end)\s*$',symbols,re.M)}
 assert len(names)==5
 physical={name:load+address-names['_text'] for name,address in names.items()}
 assert physical['_edata']==physical['__bss_start']==load+len(image)
 assert physical['__bss_start']<physical['__bss_stop']<=physical['_end']==load+memory
 assert (kd/'Image-initramfs').read_bytes()==image,'ELF/raw and frozen FIT input chain differs'
 reservations=[{'name':'DT memreserve','start':r['address'],'end':r['address']+r['bytes']} for r in memreserve]
 for name,row in dt.items():
  if name.startswith('/reserved-memory/') and 'reg' in row:
   assert len(row['reg'])%16==0
   for offset in range(0,len(row['reg']),16):
    start,size=struct.unpack_from('>QQ',row['reg'],offset);reservations.append({'name':name,'start':start,'end':start+size})
 baseline=a.bdinfo_baseline.read_text();resident=[{'name':'observed M73 LMB reservation','start':int(lo,16),'end':int(hi,16)+1} for lo,hi in re.findall(r'reserved\[\d+\]\s*\[0x([0-9a-fA-F]+)-0x([0-9a-fA-F]+)\]',baseline)]
 assert resident and resident[-1]['end']==0xa0000000 and resident[-1]['start']>0x98000000
 regions=[{'name':'raw decompressed Image','start':load,'end':load+len(image)}, {'name':'full kernel including BSS/alignment','start':load,'end':load+memory}, {'name':'FIT input window','start':0x90000000,'end':0x90000000+len(raw)}, {'name':'fixed rescue one-shot page','start':0x97ff0000,'end':0x97ff1000}]
 def clear(row,others):
  assert 0x80000000<=row['start']<row['end']<=0xa0000000
  for other in others:assert row['end']<=other['start'] or other['end']<=row['start'],(row,other)
 for row in regions[:3]:clear(row,resident+reservations)
 clear(regions[1],[regions[2],regions[3]])
 pad=0x3000;fdt1=(resident[-1]['start']-len(dtb)-pad)&~0xfff;fdt2=(fdt1-len(dtb)-2*pad)&~0xfff
 predicted=[{'name':'predicted bootm fdt allocation','start':fdt1,'end':fdt1+len(dtb)+pad},{'name':'predicted bootm prep second FDT allocation','start':fdt2,'end':fdt2+len(dtb)+2*pad}]
 for row in predicted:clear(row,resident+reservations+regions)
 clear(predicted[0],[predicted[1]])
 plan={'schema':1,'candidate_manifest_sha256':FROZEN_MANIFEST,'installer':expected,'normal_sysupgrade':manifest['artifact_sha256']['sysupgrade.bin'],'installer_crc32':f'{zlib.crc32(raw):08x}','RAM_bootargs':args,
  'Image_bytes':len(image),'Image_sha256':sha(image),'ELF_sha256':sha(elf.read_bytes()),'ELF_physical_symbols':physical,'RAM_regions':regions,'DT_reservations':reservations,'observed_baseline_LMB':resident,'bdinfo_baseline_sha256':sha(a.bdinfo_baseline.read_bytes()),'predicted_FDT_relocations':predicted,
  'partition_contract':{name.rsplit('/',1)[1]:{'label':text(row['label']),'reg_hex':row['reg'].hex(),'readonly':'read-only' in row} for name,row in dt.items() if '/partitions/partition@' in name},
  'fresh_live_memory_gate_required':True,'predictions_are_not_observations':True,'external_ramdisk_present':False,
  'uboot_commands_before_any_go':['printenv bootm_low bootm_size bootm_mapsize initrd_high fdt_high fdt_fixup','bdinfo','md.l 1fb54004 1','md.l 1fb56004 1','crc32 90000000 '+format(len(raw),'x'),'iminfo 90000000','setenv bootargs '+args,'bootm start 90000000','bootm loados','bootm fdt','bdinfo','fdt print /chosen','bootm prep','fdt addr','fdt header','fdt print /chosen','bdinfo'],
  'required_before_go':['all environment relocation overrides absent','exact HTTP bytes/SHA and UART CRC match frozen installer','iminfo exactly two SHA256 successes','both QDMA low nibbles zero using audited M73 quiesce gate if needed','fresh live LMB excludes FIT, full kernel including BSS, DT reservations and handoff page','actual bootm fdt AND bootm prep relocation ranges checked against all live/known regions; prep relocates FDT again','prepared chosen exact safe arguments, no linux initrd fields or root/ubi args','prepared CPU root opt-in present; protected partition/reservation structure unchanged'],
  'after_RAM_boot_required':['rdinit=/init; no ubi.mtd/root/rootfstype in actual /proc/cmdline','root RAM and no /rom squashfs or UBIFS/UBI mount; /sys/class/ubi contains no ubi device','revision M83-combined-v1; CPU1200MHz, SET0, disarmed, 2 CPUs','declare actual physical management port from user cable state (lan-test or eth2); require that exact port carrier1 speed1000 full plus peer payload/management; do not substitute another port or waive any failed 1G acceptance','verify every protected mtd readonly and full hashes match baseline before write','upload verified NAND-origin preservation archive; recheck SHA and tar required identity/config contents','sysupgrade -T -f /tmp/m83-preserve.tgz /tmp/m83-sysupgrade.bin must succeed','no flash write until coordinator reviews the complete preflight receipt'],
  'single_write_command_after_preflight':'sysupgrade -f /tmp/m83-preserve.tgz /tmp/m83-sysupgrade.bin',
  'no_device_access':True,'flash_write_dispatched':False}
 a.output.write_text(json.dumps(plan,indent=2)+'\n');print(json.dumps({key:plan[key] for key in ['installer','installer_crc32','Image_bytes','ELF_physical_symbols','predicted_FDT_relocations','no_device_access']},indent=2))
if __name__=='__main__':main()
