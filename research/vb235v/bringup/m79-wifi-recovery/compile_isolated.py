#!/usr/bin/env python3
"""Replay prepared kernel compile/link commands in an isolated source copy.

No make invocation and no writes to the shared build/kernel/staging tree.
This is a compile/link check, not a fresh modpost/firmware build or install.
"""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

src, dst = map(lambda x: Path(x).resolve(), sys.argv[1:3])
assert src != dst and src not in dst.parents
toolchain = src.parents[3] / 'staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin'
# src parents: linux platform, build target, build_dir, project root.
assert (toolchain / 'aarch64-openwrt-linux-musl-gcc').is_file(), toolchain
logs = dst.parent / 'compile-logs'
logs.mkdir(exist_ok=True)

def command(path):
    first = path.read_text().splitlines()[0]
    assert first.startswith('savedcmd_') and ' := ' in first, path
    argv = shlex.split(first.split(' := ', 1)[1].replace(str(src), str(dst)))
    argv[0] = str(toolchain / argv[0])
    return argv

def run(path):
    argv = command(path)
    out = subprocess.run(argv, cwd=dst, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log = str(path.relative_to(src)).replace('/', '_')+'.log'
    (logs/log).write_text(out.stdout)
    if out.returncode:
        raise RuntimeError(str(path)+':\n'+out.stdout[-6000:])
    return str(path.relative_to(src))

modules = ['mt76', 'mt76-connac-lib', 'mt7996/mt7996e']
units = set()
for module in modules:
    mod = module+'.mod'
    shutil.copy2(src/mod, dst/mod)
    for obj in (src/mod).read_text().split():
        obj = Path(obj)
        units.add(src/obj.parent/('.'+obj.name+'.cmd'))
    shutil.copy2(src/(module+'.mod.c'), dst/(module+'.mod.c'))
    p = Path(module+'.mod.o')
    units.add(src/p.parent/('.'+p.name+'.cmd'))
shutil.copy2(src/'.module-common.o', dst/'.module-common.o')
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
    compiled = list(pool.map(run, sorted(units)))
for module in modules:
    p = Path(module)
    run(src/p.parent/('.'+p.name+'.o.cmd'))
    run(src/p.parent/('.'+p.name+'.ko.cmd'))
report = {
    'status': 'compile-link-passed',
    'source_tree_read_only': str(src),
    'isolated_output': str(dst),
    'compiled_units': compiled,
    'limitations': ['Prepared exact .cmd flags and mod.c metadata replayed; no new modpost. Kernel .module-common.o reused.',
                    'No module installed or loaded. Full image build and live tests required.'],
    'modules': {m+'.ko': hashlib.sha256((dst/(m+'.ko')).read_bytes()).hexdigest() for m in modules},
}
(logs/'report.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
