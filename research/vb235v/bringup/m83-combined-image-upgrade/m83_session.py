# SPDX-License-Identifier: GPL-2.0-only
"""Explicit source/NIC-bound pinned SSH session; constructing it accesses device.

Use only with the coordinator's device lease. Importing performs no network IO.
No address, route, credential, host key or router configuration is changed.
"""
import importlib.util,json,socket,struct,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
WORKSPACE=HERE.parents[4]
sys.path.insert(0,str(WORKSPACE))
from vb235v_native_session import Session
import paramiko

def discover():
 spec=importlib.util.spec_from_file_location('m83_discovery',HERE/'discover-management.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 import subprocess
 command="Get-NetIPAddress -InterfaceIndex 68 -AddressFamily IPv4 -ErrorAction Stop | Select-Object InterfaceIndex,IPAddress,PrefixLength,@{Name='AddressState';Expression={[string]$_.AddressState}} | ConvertTo-Json -Compress"
 rows=json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],text=True))
 return m.candidates(rows,68)

class PinnedManagementSession(Session):
 def __init__(self,candidate):
  assert candidate['interface_index']==68
  assert (candidate['target_address'],candidate['ssh_port']) in [('192.168.235.1',22),('169.254.235.1',22),('169.254.211.1',2222)]
  private=WORKSPACE/'router-root-ssh'
  pin=json.loads((private/'m73-native-ssh-pin.json').read_text())['host']
  self.sock=socket.socket();self.sock.settimeout(12)
  self.sock.setsockopt(socket.IPPROTO_IP,31,struct.pack('!I',68))
  self.sock.bind((candidate['source_address'],0))
  try:
   self.sock.connect((candidate['target_address'],candidate['ssh_port']))
   self.transport=paramiko.Transport(self.sock);self.transport.start_client(timeout=12)
   key=self.transport.get_remote_server_key()
   assert [key.get_name(),key.get_base64()]==pin,'Pinned router SSH identity mismatch'
   self.transport.auth_publickey('root',paramiko.Ed25519Key.from_private_key_file(str(private/'m73-native-development-key')))
   assert self.run('id -u; uname -r; cat /tmp/sysinfo/board_name').splitlines()==[b'0',b'6.18.60',b'tplink,vb235v']
  except BaseException:
   self.sock.close()
   if hasattr(self,'transport'):self.transport.close()
   raise
  self.candidate=dict(candidate)
