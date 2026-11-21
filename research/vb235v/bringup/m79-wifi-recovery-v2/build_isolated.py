#!/usr/bin/env python3
"""Exact isolated compilation plus fresh MODPOST, never writes shared inputs."""
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

baseline,patched=map(lambda p:Path(p).resolve(),sys.argv[1:3])
here=Path(__file__).resolve().parent
v1=here.parent/'m79-wifi-recovery'
assert baseline!=patched and baseline not in patched.parents
subprocess.run([sys.executable,str(v1/'compile_isolated.py'),str(baseline),str(patched)],check=True,stdout=subprocess.DEVNULL)
logs=patched.parent/'compile-logs'
toolchain=baseline.parents[3]/'staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin'
def command(path):
    cmd=path.read_text().splitlines()[0].split(' := ',1)[1].replace(str(baseline),str(patched))
    args=shlex.split(cmd)
    if not Path(args[0]).is_absolute():args[0]=str(toolchain/args[0])
    return args
def run(args,name):
    result=subprocess.run(args,cwd=patched,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    (logs/name).write_text(result.stdout)
    assert result.returncode==0,result.stdout
shutil.copyfile(baseline/'modules.order',patched/'modules.order')
run(command(baseline/'.Module.symvers.cmd'),'fresh-modpost.log')
for module in ['mt76','mt76-connac-lib','mt7996/mt7996e']:
    p=Path(module)
    run(command(baseline/p.parent/('.'+p.name+'.mod.o.cmd')),p.name+'-fresh-mod.o.log')
    run(command(baseline/p.parent/('.'+p.name+'.ko.cmd')),p.name+'-fresh-ko.log')
report=json.loads((logs/'report.json').read_text())
report['status']='compile-link-fresh-modpost-passed'
report['fresh_modpost']=True
report['fresh_module_symvers_sha256']=hashlib.sha256((patched/'Module.symvers').read_bytes()).hexdigest()
report['modules']={m:hashlib.sha256((patched/m).read_bytes()).hexdigest() for m in report['modules']}
report['limitations']=['Exact prepared compile flags/kernel symbol inputs replayed in an isolated tree; fresh MODPOST and module metadata compilation completed.',
                       'Unchanged prepared kernel .module-common.o reused. No module installed/loaded; final image integration and live tests are parent-owned.']
(logs/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
