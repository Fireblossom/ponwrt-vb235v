#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Negative gates for prep's second FDT allocation and final live reservation."""
import importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('prepared',HERE/'verify-prepared-fdt.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
prep='Loading Device Tree to 000000009ad41000, end 000000009ad49f96 ... OK\nWorking FDT set to 9ad41000\n'
header='totalsize: 0x4000 (16384)\n'
args='console=ttyS0,115200n8 rdinit=/init panic=0'
chosen='bootargs = "'+args+'";\n'
before='reserved[0] [0x9ad4a000-0x9ad4ff96]\nreserved[1] [0x9ad50000-0x9af51dff]\nreserved[2] [0x9af52b70-0x9fffffff]\n'
after=before+'reserved[3] [0x9ad41000-0x9ad44fff]\n'
base=dict(prep=prep,header=header,chosen=chosen,before=before,after=after,known=[(0x80200000,0x80fb0000),(0x90000000,0x9064a480)],bootargs=args,initrd=None)
cases=[('good',{}),('wrong-working-address',{'prep':prep.replace('set to 9ad41000','set to 9ad4a000')}),('oversize-final',{'header':'totalsize: 0x10000\n'}),('transient-overlap',{'prep':prep.replace('9ad49f96','9ad4ffff')}),('no-final-reservation',{'after':before}),('old-reservation-lost',{'after':'reserved[0] [0x9ad41000-0x9ad44fff]\n'}),('unsafe-chosen',{'chosen':chosen.replace('panic=0','ubi.mtd=vb235v-system panic=0')}),('unexpected-initrd',{'chosen':chosen+'linux,initrd-start = <0x0 0x9ad50000>;\n'})]
for name,updates in cases:
 try:result=m.check(**dict(base,**updates))
 except AssertionError:assert name!='good',name
 else:assert name=='good' and result['gate_passed'],name
print(str(len(cases))+' prepared-FDT gate cases passed; no device IO')
