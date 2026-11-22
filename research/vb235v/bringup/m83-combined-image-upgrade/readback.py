#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read actual UBI/protected-region hashes after coordinator-dispatched upgrade.

Requires the device lease. Performs no mount, configuration, upgrade or reboot.
It deliberately cannot mark config preservation or rescue-path tests complete.
"""
import argparse,json,re
from pathlib import Path
from m83_session import PinnedManagementSession,discover

def collect(session,manifest,baseline,output):
 assert not output.exists();output.mkdir(parents=True)
 report={'schema':1,'complete':False,'flash_write_commands_sent':False,'source_bound_session':session.candidate,'protected_after':{},'volumes':{}}
 def save():(output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 save()
 assert session.run('cat /etc/vb235v-system-revision').decode()==manifest['revision']+'\n'
 assert session.run('cat /sys/devices/system/cpu/online').strip()==b'0-1'
 mounts=session.run('cat /proc/mounts');assert b' /rom squashfs ro,' in mounts and b' /overlay ubifs rw,' in mounts
 assert session.run('cat /sys/class/ubi/ubi0/mtd_num').strip()==b'5'
 rows=session.run('for v in /sys/class/ubi/ubi0_*; do printf "%s " "${v##*/}"; cat "$v/name"; done').decode().splitlines()
 names={}
 for row in rows:
  node,name=row.split(' ',1);assert re.fullmatch(r'ubi0_\d+',node);assert name not in names;names[name]=node
 info=manifest['sysupgrade_format_audit']
 for name,length,expected in [('kernel',info['fit_bytes'],info['fit_SHA256']),('rootfs',info['rootfs_bytes_used'],info['rootfs_SHA256'])]:
  assert name in names and type(length) is int and 0<length<0x3800000
  node=names[name];actual=session.run(f'head -c {length} /dev/{node} | sha256sum',timeout=180).split()[0].decode()
  assert actual==expected,'Actual written UBI volume differs: '+name
  report['volumes'][name]={'node':node,'bytes_hashed':length,'sha256':actual,'matches_candidate':True};save()
 protected=baseline['protected_after'];assert {v['index'] for v in protected.values()}=={0,1,2,3,4,6}
 for name,row in protected.items():
  index=row['index'];assert type(index) is int
  flags=int(session.run(f'cat /sys/class/mtd/mtd{index}/flags').strip(),0);assert not flags&0x400,'Protected region writable'
  actual=session.run(f'sha256sum /dev/mtd{index}',timeout=900).split()[0].decode()
  assert re.fullmatch('[0-9a-f]{64}',actual) and actual==row['sha256'],'Protected region changed: '+name
  report['protected_after'][name]={'index':index,'sha256':actual,'entire_region_read':True,'readonly':True};save()
 state=session.run('cat /etc/ponwrt/management-m83.json').decode();report['management_migration']=json.loads(state)
 for label,command in [('live-link','for p in lan-test eth2; do echo "$p"; ip -s link show dev "$p"; ethtool "$p"; done'),('listeners','ss -lntp'),('CPU','/usr/libexec/vb235v-cpu-observe'),('mounts','cat /proc/mounts'),('boot-log','dmesg')]:
  code,data,errors=session.run(command,timeout=60,check=False)
  (output/(label+'-private.log')).write_bytes(data+errors);report[label+'_exit_status']=code
 report.update(complete=True,booted_revision=manifest['revision'],two_CPUs_online=True,actual_volume_hashes_matched=True,all_protected_regions_unchanged=True,configuration_preservation_accepted=False,normal_and_rescue_paths_accepted=False)
 save();return report

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',type=Path,required=True);p.add_argument('--protected-baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--target',required=True);a=p.parse_args()
 options=[row for row in discover() if row['target_address']==a.target];assert len(options)==1,'No unique live NIC68 source for target'
 session=PinnedManagementSession(options[0])
 try:
  report=collect(session,json.loads(a.manifest.read_text()),json.loads(a.protected_baseline.read_text()),a.output)
  print(json.dumps({key:report[key] for key in ['complete','booted_revision','actual_volume_hashes_matched','all_protected_regions_unchanged']},indent=2))
 finally:session.close()
if __name__=='__main__':main()
