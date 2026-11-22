#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Lease-only stage an uploaded exact M83 installer through prep, never go."""
import argparse,importlib.util,json,re,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[4]))
from vb235v_win32 import WinSerial
from backup import inspect_archive
spec=importlib.util.spec_from_file_location('prepared_gate',HERE/'verify-prepared-fdt.py');gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--upload-receipt',type=Path,required=True);p.add_argument('--backup-receipt',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 plan=json.loads(a.plan.read_text());uploaded=json.loads(a.upload_receipt.read_text())
 assert plan['candidate_manifest_sha256']=='91fd972ed13ea3df38d8f6355bd4a9718a1fc030033ea5ef7f44abc7ac9ed762'
 assert uploaded['complete'] and uploaded['normal_core_revision']=='M73' and uploaded['normal_core_role']=='normal'
 assert not uploaded['kernel_boot_dispatched'] and not uploaded['flash_write_commands_sent']
 assert uploaded['artifact_sha256']==plan['installer']['sha256'] and uploaded['bytes']==plan['installer']['bytes']
 backup=json.loads(a.backup_receipt.read_text());assert backup['persistent_revision']=='M75-phy-page-v1'
 backup_check=inspect_archive(a.backup_receipt.with_name('preserve.tgz').read_bytes(),backup['expected_live_file_SHA256'])
 assert backup_check['archive_sha256']==backup['archive_sha256']
 if backup['owner_setup_token_existed']:
  assert backup['owner_setup_token_in_keep'] and 'etc/ponwrt/setup.token' in backup_check['regular_file_SHA256']
 for name in backup['all_etc_ponwrt_regular_files_included']:assert name[1:] in backup['expected_live_file_SHA256']
 assert not a.output.exists();a.output.mkdir(parents=True);report={'complete':False,'go_sent':False,'flash_write_commands_sent':False,'saveenv_sent':False,'artifact_sha256':uploaded['artifact_sha256'],'preservation_archive_sha256':backup['archive_sha256']}
 u=WinSerial('COM3');u.open();log=(a.output/'console-private.log').open('xb',buffering=0);pending=bytearray();prompt=rb'(?:^|[\r\n])VB235v-Recovery>\s*$'
 def read():
  data=u.read();log.write(data);return data
 def wait(seconds=45):
  end=time.monotonic()+seconds
  while time.monotonic()<end:
   pending.extend(read());assert len(pending)<4*1024*1024
   if re.search(prompt,pending):data=bytes(pending);pending.clear();return data
  raise TimeoutError('Known normal-core prompt absent; no replay')
 def cmd(text,seconds=45):
  assert '\n' not in text and '\r' not in text and len(text)<240
  u.write((text+'\r').encode());data=wait(seconds)
  assert not any(s in data for s in [b'Unknown command',b'ERROR',b'FDT_ERR',b'Bad Data',b'Synchronous Abort'])
  return data
 def reg(address):
  data=cmd('md.l '+format(address,'x')+' 1');rows=re.findall(rb'(?:^|[\r\n])'+format(address,'x').encode()+rb':\s+([0-9a-fA-F]{8})',data);assert len(rows)==1;return int(rows[0],16)
 def clear(region,others):
  for span in others:assert region[1]<=span[0] or span[1]<=region[0],(region,span)
 try:
  read();u.write(b'\x03');wait(10)
  env=cmd('printenv bootm_low bootm_size bootm_mapsize initrd_high fdt_high fdt_fixup')
  for name in ['bootm_low','bootm_size','bootm_mapsize','initrd_high','fdt_high','fdt_fixup']:assert not re.search(rb'(?:^|[\r\n])'+name.encode()+rb'=',env)
  before=cmd('bdinfo');(a.output/'bdinfo-before-private.log').write_bytes(before)
  resident=gate.reservations(before.decode());assert resident
  assert re.search(rb'memory\[0\]\s*\[0x80000000-0x9fffffff\]',before)
  known=[(row['start'],row['end']) for row in plan['RAM_regions']+plan['DT_reservations']]
  for row in plan['RAM_regions'][:3]:clear((row['start'],row['end']),resident+[(r['start'],r['end']) for r in plan['DT_reservations']])
  crc=cmd('crc32 90000000 '+format(plan['installer']['bytes'],'x'))
  assert re.findall(rb'==>\s*([0-9a-fA-F]{8})',crc)==[plan['installer_crc32'].encode()]
  info=cmd('iminfo 90000000',90);assert info.count(b'sha256+')==2 and b'Bad' not in info
  values=[reg(address) for address in [0x1fb54004,0x1fb56004]];report['QDMA_before']=values
  if any(value&15 for value in values):
   assert not any(value&5 for value in values)
   old=reg(0x1fb00834);mask=(1<<21)|(1<<1)|(1<<2);assert not old&mask
   cmd('mw.l 1fb00834 '+format(old|mask,'x')+' 1');time.sleep(.1)
   cmd('mw.l 1fb00834 '+format(old,'x')+' 1');time.sleep(.1);assert reg(0x1fb00834)==old
   report['exact_M73_QDMA_quiesce_reset_used']=True
  for _ in range(2):assert not any(reg(address)&15 for address in [0x1fb54004,0x1fb56004]);time.sleep(.02)
  cmd('setenv bootargs '+plan['RAM_bootargs'])
  for stage in ['start 90000000','loados','fdt']:
   data=cmd('bootm '+stage,90);(a.output/('bootm-'+stage.split()[0]+'-private.log')).write_bytes(data)
  pre=cmd('bdinfo');(a.output/'bdinfo-before-prep-private.log').write_bytes(pre)
  # Verify the first relocation too, before issuing prep's second relocation.
  first=(a.output/'bootm-fdt-private.log').read_text();moves=re.findall(r'Loading Device Tree to (?:0x)?([0-9a-fA-F]+), end (?:0x)?([0-9a-fA-F]+)',first);assert len(moves)==1
  first_region=(int(moves[0][0],16),int(moves[0][1],16)+1);assert 0x80000000<=first_region[0]<first_region[1]<=0xa0000000;clear(first_region,resident+known)
  prep=cmd('bootm prep');(a.output/'bootm-prep-private.log').write_bytes(prep)
  header=cmd('fdt header');chosen=cmd('fdt print /chosen');post=cmd('bdinfo')
  for name,data in [('FDT-header-prepared-private.log',header),('chosen-prepared-private.log',chosen),('bdinfo-prepared-private.log',post)]: (a.output/name).write_bytes(data)
  final=gate.check(prep.decode(),header.decode(),chosen.decode(),pre.decode(),post.decode(),known,plan['RAM_bootargs'],None)
  assert b'tplink,m78-boot-voltage-cpufreq' in cmd('fdt print / tplink,m78-boot-voltage-cpufreq')
  partitions=cmd('fdt print /spi@1fa10000/nand@0/partitions');(a.output/'partitions-prepared-private.log').write_bytes(partitions)
  matches=re.findall(r'(partition@[0-9a-f]+)\s*\{([^{}]+)\}',partitions.decode());actual={}
  for name,body in matches:
   label=re.search(r'label\s*=\s*"([^"]+)"',body)[1];cells=re.search(r'reg\s*=\s*<([^>]+)>',body)[1].split()
   actual[name]={'label':label,'reg_hex':''.join(f'{int(cell,16):08x}' for cell in cells),'readonly':'read-only;' in body}
  assert actual==plan['partition_contract'],'Prepared protected NAND contract changed'
  report.update(complete=True,QDMA_quiet=True,first_FDT_allocation=list(first_region),prepared_FDT_gate=final,safe_bootargs=plan['RAM_bootargs'],prepared_partition_contract_verified=True,final_state='M73 installer prepared; no go sent')
 finally:
  u.close();log.close();(a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(report,indent=2))
if __name__=='__main__':main()
