#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Ensure a success banner cannot substitute for actual volume/protected reads."""
import importlib.util,json,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('m83readback',HERE/'readback.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
DIGEST='a'*64
manifest={'revision':'M83-combined-v1','sysupgrade_format_audit':{'fit_bytes':4096,'fit_SHA256':DIGEST,'rootfs_bytes_used':8192,'rootfs_SHA256':DIGEST}}
baseline={'protected_after':{str(i):{'index':i,'sha256':DIGEST} for i in [0,1,2,3,4,6]}}
class Mock:
 candidate={'interface_index':68,'source_address':'192.168.235.2','target_address':'192.168.235.1','ssh_port':22}
 def __init__(self,failure):self.failure=failure;self.commands=[]
 def run(self,command,**kwargs):
  self.commands.append(command)
  assert not any(bad in command for bad in ['ubiupdatevol','ubiformat','sysupgrade ','saveenv','flash_erase'])
  if kwargs.get('check') is False:return 0,b'synthetic read-only fixture\n',b''
  if command=='cat /etc/vb235v-system-revision':return b'M83-combined-v1\n'
  if command=='cat /sys/devices/system/cpu/online':return b'0-1\n'
  if command=='cat /proc/mounts':return b'/dev/root /rom squashfs ro,relatime 0 0\n/dev/ubi0_2 /overlay ubifs rw,relatime 0 0\n'
  if command=='cat /sys/class/ubi/ubi0/mtd_num':return b'5\n'
  if command.startswith('for v in '):return b'ubi0_7 kernel\nubi0_9 rootfs\nubi0_2 rootfs_data\n'
  if command.startswith('head -c '):return ((('b'*64) if self.failure=='rootfs' and '/dev/ubi0_9' in command else DIGEST)+'  -\n').encode()
  if '/flags' in command:return b'0x400\n' if self.failure=='writable' and 'mtd3/' in command else b'0x0\n'
  if command.startswith('sha256sum /dev/mtd'):return ((('b'*64) if self.failure=='protected' and command.endswith('mtd4') else DIGEST)+'  fixture\n').encode()
  if command=='cat /etc/ponwrt/management-m83.json':return b'{"state":"configured"}\n'
  raise AssertionError(command)
with tempfile.TemporaryDirectory(prefix='m83-readback-test-') as tmp:
 for failure in ['none','rootfs','writable','protected']:
  session=Mock(failure);output=Path(tmp)/failure
  try:result=m.collect(session,manifest,baseline,output)
  except AssertionError:
   assert failure!='none'
   assert not json.loads((output/'report.json').read_text())['complete']
  else:
   assert failure=='none' and result['complete']
   assert result['volumes']['kernel']['node']=='ubi0_7' and result['volumes']['rootfs']['node']=='ubi0_9'
   assert not result['configuration_preservation_accepted'] and not result['normal_and_rescue_paths_accepted']
print('4 readback cases passed: named volumes, actual mismatch, writable protection and whole protected-region mismatch; no device IO')
