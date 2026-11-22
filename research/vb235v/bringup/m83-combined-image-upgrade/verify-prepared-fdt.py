#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Check actual post-prep working FDT and transient allocation before bootm go.

Consumes saved observations only. May be imported by a lease-holding hardware
controller before it sends go; this file never accesses serial or the device.
"""
import argparse,hashlib,json,re
from pathlib import Path
def reservations(log):
 return [(int(lo,16),int(hi,16)+1) for lo,hi in re.findall(r'reserved\[\d+\]\s*\[0x([0-9a-fA-F]+)-0x([0-9a-fA-F]+)\]',log)]
def check(prep,header,chosen,before,after,known,bootargs,initrd=None):
 moves=re.findall(r'Loading Device Tree to (?:0x)?([0-9a-fA-F]+), end (?:0x)?([0-9a-fA-F]+)',prep)
 working=re.findall(r'Working FDT set to (?:0x)?([0-9a-fA-F]+)',prep)
 sizes=re.findall(r'totalsize:\s*(0x[0-9a-fA-F]+)',header)
 assert len(moves)==len(working)==len(sizes)==1,'Ambiguous actual prep/FDT observations'
 allocation=(int(moves[0][0],16),int(moves[0][1],16)+1);address=int(working[0],16);total=int(sizes[0],16)
 final=(address,address+total)
 assert allocation[0]==address and 40<=total<=allocation[1]-allocation[0]
 assert 0x80000000<=allocation[0]<allocation[1]<=0xa0000000
 old=reservations(before);new=reservations(after);assert old and new
 assert final in new,'Prepared working FDT lacks exact live LMB reservation'
 def clear(region,others):
  for span in others:assert region[1]<=span[0] or span[1]<=region[0],('FDT overlaps',region,span)
 clear(allocation,old+known)
 clear(final,[span for span in new if span!=final]+known)
 # Every old reservation remains; shrinking/freeing the newly allocated tail
 # is allowed, but no old kernel/initrd/resident reservation may disappear.
 assert all(span in new for span in old),'Existing live LMB reservation changed during prep'
 observed=re.findall(r'bootargs\s*=\s*"([^"]*)"',chosen);assert observed==[bootargs]
 assert not any(term in observed[0] for term in ['ubi.','root=','rootfstype='])
 for name,index in [('linux,initrd-start',0),('linux,initrd-end',1)]:
  cells=re.findall(re.escape(name)+r'\s*=\s*<([^>]+)>',chosen)
  if initrd is None:assert not cells,'Unexpected external initrd in full installer'
  else:
   assert len(cells)==1;value=0
   for cell in cells[0].split():value=(value<<32)|int(cell,16)
   assert value==initrd[index]
 if initrd is not None:clear(final,[initrd]);clear(allocation,[initrd])
 return {'gate_passed':True,'prep_transient_FDT_allocation':list(allocation),'final_working_FDT':list(final),'final_totalsize':total,'exact_final_live_LMB_reservation':True,'transient_and_final_ranges_nonoverlap':True,'old_kernel_initrd_resident_reservations_preserved':True,'safe_chosen_verified':True,'no_device_access':True}
def main():
 p=argparse.ArgumentParser();p.add_argument('--mini-manifest',type=Path,required=True);p.add_argument('--stage',type=Path,required=True);p.add_argument('--boot',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 m=json.loads(a.mini_manifest.read_text());stage=json.loads((a.stage/'report.json').read_text())
 assert m['mini_fit_sha256']==stage['artifact_sha256']
 names={'prep':a.boot/'bootm-prep-private.log','header':a.boot/'FDT-header-prepared-private.log','chosen':a.boot/'chosen-prepared-private.log','before':a.stage/'bdinfo-after-private.log','after':a.boot/'bdinfo-prepared-private.log'}
 logs={key:path.read_text() for key,path in names.items()}
 known=[(row['start'],row['end']) for row in m['memory_audit']['regions']+m['memory_audit']['DT_reserved_memory']]
 result=check(**logs,known=known,bootargs=stage['safe_bootargs'],initrd=tuple(stage['actual_initrd']))
 result.update(artifact_sha256=m['mini_fit_sha256'],historical_offline_review=True,input_sha256={key:hashlib.sha256(path.read_bytes()).hexdigest() for key,path in names.items()})
 a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
