#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Offline preservation-archive failures; no real keys, passwords or device."""
import importlib.util,io,tarfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('m83backup',HERE/'backup.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
payloads={name:('synthetic '+name+'\n').encode() for name in m.REQUIRED+['etc/ponwrt/setup.token','etc/ponwrt/test-owner-state.json']};expected={name:m.sha(data) for name,data in payloads.items()}
def archive(mode):
 out=io.BytesIO()
 with tarfile.open(fileobj=out,mode='w:gz') as tar:
  rows=dict(payloads)
  if mode.startswith('missing:'):rows.pop(mode.split(':',1)[1])
  if mode=='wrong-wireless':rows['etc/config/wireless']=b'synthetic modified wifi\n'
  if mode=='wrong-owner-token':rows['etc/ponwrt/setup.token']=b'synthetic rotated token\n'
  if mode=='unsafe':rows['../outside']=b'x'
  for name,data in rows.items():
   item=tarfile.TarInfo(name);item.size=len(data);item.mode=0o600;tar.addfile(item,io.BytesIO(data))
  if mode=='duplicate':
   item=tarfile.TarInfo('etc/shadow');item.size=1;tar.addfile(item,io.BytesIO(b'x'))
  if mode=='device':
   item=tarfile.TarInfo('etc/special');item.type=tarfile.CHRTYPE;tar.addfile(item)
 return out.getvalue()
cases=['good','wrong-wireless','wrong-owner-token','unsafe','duplicate','device']+['missing:'+name for name in payloads]
for case in cases:
 try:result=m.inspect_archive(archive(case),expected)
 except (AssertionError,ValueError):assert case!='good',case
 else:assert case=='good' and result['all_required_config_and_identity_files_present'],case
print(str(len(cases))+' offline backup cases passed, including each required SSH/TLS/shadow/rpcd/WiFi file omission; no device IO')
