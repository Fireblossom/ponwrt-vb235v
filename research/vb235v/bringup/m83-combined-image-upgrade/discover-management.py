#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read Windows test-NIC addresses and derive bound management probe options.

No NIC/address/route changes and no connections. Call before each new session;
DHCP can remove APIPA when eth2 joins the isolated LAN bridge.
"""
import argparse,ipaddress,json,subprocess
def candidates(rows,index=68):
 if isinstance(rows,dict):rows=[rows]
 result=[]
 for row in rows:
  if row.get('InterfaceIndex')!=index or row.get('AddressState') not in ['Preferred',4]:continue
  source=ipaddress.IPv4Address(row['IPAddress']);network=ipaddress.IPv4Network(str(source)+'/'+str(row['PrefixLength']),strict=False)
  for target,ports in [('192.168.235.1',[22]),('169.254.235.1',[22]),('169.254.211.1',[2222])]:
   if ipaddress.IPv4Address(target) in network and str(source)!=target:
    for port in ports:result.append({'interface_index':index,'source_address':str(source),'target_address':target,'ssh_port':port})
 return result
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--interface-index',type=int,default=68);p.add_argument('--fixture');a=p.parse_args()
 assert 1<=a.interface_index<=65535
 if a.fixture:
  with open(a.fixture) as f:rows=json.load(f)
 else:
  command=f"Get-NetIPAddress -InterfaceIndex {a.interface_index} -AddressFamily IPv4 -ErrorAction Stop | Select-Object InterfaceIndex,IPAddress,PrefixLength,@{{Name='AddressState';Expression={{[string]$_.AddressState}}}} | ConvertTo-Json -Compress"
  rows=json.loads(subprocess.check_output(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],text=True))
 print(json.dumps({'read_only':True,'candidate_bound_sessions':candidates(rows,a.interface_index),'upstream_NIC_changed':False,'default_route_changed':False},indent=2))
if __name__=='__main__':main()
