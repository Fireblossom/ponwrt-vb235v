#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Direct compiler/modpost/link reuse of prior verified external-module flags.

Never runs make or writes the shared kernel tree. Output lives only in --work.
The explicit template directory must be the earlier M78 check build.
"""
import argparse, hashlib, json, os, shlex, shutil, subprocess
from pathlib import Path
HERE = Path(__file__).resolve().parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--tree', type=Path, required=True)
p.add_argument('--template', type=Path, required=True)
p.add_argument('--work', type=Path, required=True)
p.add_argument('--query-only', action='store_true')
a = p.parse_args()
tree = a.tree.resolve(strict=True)
template = a.template.resolve(strict=True)
work = a.work.resolve()
assert work != tree and tree not in work.parents and work != HERE
work.mkdir(parents=True, exist_ok=True)
kernel = tree/'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60'
config_hash = hashlib.sha256((kernel/'.config').read_bytes()).hexdigest()
symvers_hash = hashlib.sha256((kernel/'Module.symvers').read_bytes()).hexdigest()
env = dict(os.environ, STAGING_DIR=str(tree/'staging_dir'))
def command(name):
    line = (template/name).read_text().splitlines()[0]
    assert ':=' in line
    argv = shlex.split(line.split(':=',1)[1])
    assert not any(x in argv for x in [';', '&&', '|', '||'])
    return argv
def run(argv):
    subprocess.run(argv, cwd=work, env=env, check=True)
def compile_one(name):
    shutil.copyfile(HERE/(name+'.c'), work/(name+'.c'))
    if name == 'vb235v-cpufreq':
        shutil.copyfile(HERE/'vb235v-cpufreq-contract.h', work/'vb235v-cpufreq-contract.h')
    argv = command('.vb235v-cpufreq.o.cmd')
    argv = [x.replace('vb235v-cpufreq',name).replace('vb235v_cpufreq',name.replace('-','_')) for x in argv]
    run(argv)
names = ['vb235v-cpu-query'] if a.query_only else ['vb235v-cpu-query','vb235v-cpufreq']
for name in names:
    compile_one(name)
(work/'modules.order').write_text(''.join(name+'.o\n' for name in names))
run([str(kernel/'scripts/mod/modpost'), '-M', '-o', 'Module.symvers',
     '-T', 'modules.order', '-i', str(kernel/'Module.symvers'), '-e'])
run(command('..module-common.o.cmd'))
for name in names:
    argv = command('.vb235v-cpufreq.mod.o.cmd')
    argv = [x.replace('vb235v-cpufreq',name).replace('vb235v_cpufreq',name.replace('-','_')) for x in argv]
    run(argv)
    argv = command('.vb235v-cpufreq.ko.cmd')
    argv = [x.replace('vb235v-cpufreq',name) for x in argv]
    run(argv)
assert hashlib.sha256((kernel/'.config').read_bytes()).hexdigest() == config_hash
assert hashlib.sha256((kernel/'Module.symvers').read_bytes()).hexdigest() == symvers_hash
report = {'kernel_config_sha256':config_hash, 'kernel_symvers_sha256':symvers_hash,
          'make_executed':False, 'modules':{}}
for name in names:
    artifact = work/(name+'.ko')
    report['modules'][name] = {'file':str(artifact), 'sha256':hashlib.sha256(artifact.read_bytes()).hexdigest()}
(work/'compile-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
