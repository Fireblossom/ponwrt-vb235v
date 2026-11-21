#!/usr/bin/env python3
import hashlib
from pathlib import Path
import shutil
import sys

tree=Path(sys.argv[1]).resolve()
here=Path(__file__).resolve().parent
package=tree/'package/kernel/mt76'
assert '0936617dc529ff9da0385221d3fa6de732231177' in (package/'Makefile').read_text()
for name,digest in {
    '120-vb235v-private-art-calibration.patch':'753ddae900ba240fd7116f95b23f7c7395099ce6ca67237b2a4ead15980d0dae',
    '121-vb235v-mt7996-pci-recovery.patch':'44bd5ca699dd63a24c88cb5f3f6f88f14b60581be2e3f741018e0f1805ac81f6',
}.items():
    assert hashlib.sha256((package/'patches'/name).read_bytes()).hexdigest()==digest,name
source=here/'122-vb235v-mt7996-worker-teardown.patch'
target=package/'patches'/source.name
if target.exists():assert target.read_bytes()==source.read_bytes(),'Refusing different patch 122'
else:shutil.copyfile(source,target)
print('Installed additive patch:',target)
