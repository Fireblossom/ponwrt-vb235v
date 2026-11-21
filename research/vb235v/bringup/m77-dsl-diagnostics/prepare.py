#!/usr/bin/env python3
"""Stage the diagnostic package; do not change a device or networking roles."""
import argparse
import hashlib
from pathlib import Path
import re
import shutil
import subprocess

p=argparse.ArgumentParser()
p.add_argument('tree',type=Path)
args=p.parse_args()
tree=args.tree.resolve()
here=Path(__file__).resolve().parent
assert subprocess.check_output(['git','-C',str(tree),'rev-parse','HEAD'],text=True).strip()=='dcf140cb1d5d2c15c1d7c353c95c4c2a56629820'
guard=tree/'package/kernel/mt76/patches/120-vb235v-private-art-calibration.patch'
assert hashlib.sha256(guard.read_bytes()).hexdigest()=='753ddae900ba240fd7116f95b23f7c7395099ce6ca67237b2a4ead15980d0dae'
package=tree/'package/ponwrt/diagnostics'
package.mkdir(parents=True,exist_ok=True)
(package/'src').mkdir(exist_ok=True)
shutil.copyfile(here/'package.Makefile',package/'Makefile')
for name in ['diagnostics.c','setup.c']:
    shutil.copyfile(here/name,package/'src'/name)
for name in ['overlay','www']:
    shutil.copytree(here/name,package/name,dirs_exist_ok=True)
config=tree/'.config'
text=config.read_text()
text=re.sub(r'^(?:# )?CONFIG_PACKAGE_ponwrt-diagnostics(?:=.*| is not set)\n','',text,flags=re.M)
config.write_text(text+'CONFIG_PACKAGE_ponwrt-diagnostics=y\n')
print('Staged ponwrt-diagnostics package. Run make defconfig, package compile and full image verification.')
