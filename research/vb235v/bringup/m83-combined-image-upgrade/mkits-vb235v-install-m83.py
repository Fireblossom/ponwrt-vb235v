#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build a RAM-only installer role using a private DT copy, never normal DT."""
import argparse,struct,subprocess,sys
from pathlib import Path
SAFE_BOOTARGS='console=ttyS0,115200n8 earlycon=uart8250,mmio32,0x1fbf0000,115200n8 rdinit=/init cpufreq.default_governor=performance loglevel=7 panic=0'

def ram_dtb(data):
 h=list(struct.unpack_from('>10I',data));magic,total,off,strings,_,_,_,_,ssize,tsize=h
 assert magic==0xd00dfeed and total==len(data) and off+tsize<=strings and strings+ssize<=total
 table=data[strings:strings+ssize];out=bytearray();at=off;stack=[];changed=0
 while at<off+tsize:
  start=at;token=struct.unpack_from('>I',data,at)[0];at+=4
  if token==1:
   end=data.index(0,at);stack.append(data[at:end].decode());at=(end+4)&~3
  elif token==2:stack.pop()
  elif token==3:
   length,nameoff=struct.unpack_from('>II',data,at);at+=8
   name=table[nameoff:table.index(0,nameoff)].decode();at=(at+length+3)&~3
   if '/'.join(stack)=='/chosen' and name=='bootargs':
    value=SAFE_BOOTARGS.encode()+b'\0';out+=struct.pack('>III',3,len(value),nameoff)+value
    out+=bytes((-len(out))&3);changed+=1;continue
  elif token==4:pass
  elif token==9:out+=data[start:at];break
  else:raise ValueError('Invalid FDT token')
  out+=data[start:at]
 assert changed==1 and not stack
 h[3]=off+len(out);h[9]=len(out);h[1]=h[3]+len(table)
 result=bytearray(data[:off]+out+table);struct.pack_into('>10I',result,0,*h)
 return bytes(result)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('kernel',type=Path);p.add_argument('dtb',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
 original=a.dtb.read_bytes();copy=a.output.with_suffix('.ram.dtb');copy.write_bytes(ram_dtb(original))
 builder=Path(__file__).resolve().with_name('mkits-vb235v-system.py')
 subprocess.run([sys.executable,str(builder),str(a.kernel),str(copy),str(a.output)],check=True)
 old='vb235v,firmware-image = <1>; vb235v,sequence = <1>;'
 its=a.output.read_text();assert its.count(old)==1
 a.output.write_text(its.replace(old,'vb235v,ram-installer = <1>;'),encoding='ascii')
 assert a.dtb.read_bytes()==original,'Normal DT source changed'
if __name__=='__main__':main()
