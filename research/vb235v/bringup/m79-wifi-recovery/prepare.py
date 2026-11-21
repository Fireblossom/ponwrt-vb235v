#!/usr/bin/env python3
"""Install only this mt76 package patch after verifying its M75 prerequisites.

Does not run a build, flash, unload a driver, or copy an experimental module.
The parent integrator chooses and authorizes the target build tree.
"""
import argparse
import hashlib
from pathlib import Path
import shutil

parser = argparse.ArgumentParser()
parser.add_argument('tree', type=Path)
args = parser.parse_args()
tree = args.tree.resolve()
here = Path(__file__).resolve().parent
package = tree/'package/kernel/mt76'
assert '0936617dc529ff9da0385221d3fa6de732231177' in (package/'Makefile').read_text()
guard = package/'patches/120-vb235v-private-art-calibration.patch'
assert hashlib.sha256(guard.read_bytes()).hexdigest() == '753ddae900ba240fd7116f95b23f7c7395099ce6ca67237b2a4ead15980d0dae', 'Private calibration protection prerequisite differs'
source = here/'121-vb235v-mt7996-pci-recovery.patch'
target = package/'patches'/source.name
if target.exists():
    assert target.read_bytes() == source.read_bytes(), 'Refusing to replace a different existing patch'
else:
    shutil.copyfile(source, target)
assert guard.is_file()
print('Installed:', target)
print('Reprepare/rebuild mt76 and the full image; verify_sources.py on prepared mt76 before hardware tests.')
