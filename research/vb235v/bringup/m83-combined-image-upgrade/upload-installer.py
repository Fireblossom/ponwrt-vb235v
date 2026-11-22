#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Lease-only upload to an already-observed M73 normal HTTP core; never boot."""
import argparse,hashlib,http.client,json,socket,struct,time
from pathlib import Path
from m83_session import WORKSPACE,discover
MANIFEST_SHA='91fd972ed13ea3df38d8f6355bd4a9718a1fc030033ea5ef7f44abc7ac9ed762'
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--candidate',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 raw=(a.candidate/'manifest.json').read_bytes();assert hashlib.sha256(raw).hexdigest()==MANIFEST_SHA;manifest=json.loads(raw)
 data=(a.candidate/'installer.itb').read_bytes();row=manifest['artifact_sha256']['installer.itb']
 assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
 options=[row for row in discover() if row['target_address']=='192.168.235.1'];assert len(options)==1
 source=options[0]['source_address'];assert not a.output.exists();a.output.mkdir(parents=True)
 key=json.loads((WORKSPACE/'router-root-ssh/m50-persistent-web-key-updated.json').read_text())['key']
 class Connection(http.client.HTTPConnection):
  def connect(self):
   self.sock=socket.socket();self.sock.settimeout(self.timeout)
   self.sock.setsockopt(socket.IPPROTO_IP,31,struct.pack('!I',68));self.sock.bind((source,0));self.sock.connect(('192.168.235.1',80))
 def request(path,body=None):
  connection=Connection('192.168.235.1',80,timeout=180 if body is not None else 12)
  try:
   headers={'X-VB235v-Action':'1','X-VB235v-Key':key} if body is not None else {}
   connection.request('POST' if body is not None else 'GET',path,body,headers);response=connection.getresponse();assert response.status==200
   return json.loads(response.read())
  finally:connection.close()
 state=request('/api/status');assert state['core_revision']=='M73' and state['core_role']=='normal' and not state['pending'] and not state['expert_armed']
 started=time.monotonic();result=request('/api/upload',data)
 assert result['sha256']==row['sha256'] and result['ready_bytes']==len(data)
 receipt={'complete':True,'normal_HTTP_status':200,'normal_core_revision':'M73','normal_core_role':'normal','artifact_sha256':row['sha256'],'bytes':len(data),'source_address':source,'interface_index':68,'RAM_address':'0x90000000','network_upload_seconds':time.monotonic()-started,'flash_write_commands_sent':False,'saveenv_sent':False,'kernel_boot_dispatched':False}
 (a.output/'report.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
