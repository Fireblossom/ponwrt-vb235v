#!/usr/bin/env python3
"""Read shared build flags, compile only to an independent work directory."""
import argparse, hashlib, json, os, shlex, shutil, subprocess
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--tree', type=Path, required=True)
p.add_argument('--template', type=Path, required=True)
p.add_argument('--work', type=Path, required=True)
a = p.parse_args()
tree, template, work = a.tree.resolve(strict=True), a.template.resolve(strict=True), a.work.resolve()
here = Path(__file__).resolve().parent
assert work != tree and tree not in work.parents and work != here
work.mkdir(parents=True, exist_ok=True)
k = tree/'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60'
protected = [k/'.config', k/'Module.symvers', k/'include/generated/utsrelease.h', k/'include/generated/autoconf.h']
sha = lambda f: hashlib.sha256(f.read_bytes()).hexdigest()
before = {str(f): sha(f) for f in protected}
assert (k/'include/generated/utsrelease.h').read_text().strip() == '#define UTS_RELEASE "6.18.60"'
assert '# CONFIG_MODVERSIONS is not set' in (k/'.config').read_text()
name = 'vb235v-switch-snapshot'
shutil.copyfile(here/(name+'.c'), work/(name+'.c'))
env = dict(os.environ, STAGING_DIR=str(tree/'staging_dir'))
def run(argv):
    subprocess.run(argv, cwd=work, env=env, check=True)
def flags(cmd):
    line = (template/cmd).read_text().splitlines()[0]
    argv = shlex.split(line.split(':=', 1)[1])
    assert not any(x in argv for x in [';', '&&', '|', '||'])
    return [x.replace('vb235v-cpufreq', name).replace('vb235v_cpufreq', name.replace('-', '_')) for x in argv]
run(flags('.vb235v-cpufreq.o.cmd'))
(work/'modules.order').write_text(name+'.o\n')
run([str(k/'scripts/mod/modpost'), '-M', '-o', 'Module.symvers', '-T', 'modules.order', '-i', str(k/'Module.symvers'), '-e'])
run(flags('..module-common.o.cmd'))
run(flags('.vb235v-cpufreq.mod.o.cmd'))
run(flags('.vb235v-cpufreq.ko.cmd'))
assert before == {str(f): sha(f) for f in protected}
prefix = tree/'staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin/aarch64-openwrt-linux-musl-'
nm = subprocess.check_output([str(prefix)+'nm', '-u', str(work/(name+'.ko'))], text=True)
allowed = {'__stack_chk_fail', '_printk', '__ioremap', 'iounmap', 'of_machine_is_compatible',
           'of_find_compatible_node', 'of_device_is_available', 'of_address_to_resource', 'of_node_put',
           '__arm64_ioremap_prot', '__ioremap_prot', 'arm64_use_ng_mappings',
           'of_machine_compatible_match', '__of_find_compatible_node', '__of_device_is_available'}
imports = {line.split()[-1] for line in nm.splitlines()}
assert imports <= allowed, imports - allowed
disasm = subprocess.check_output([str(prefix)+'objdump', '-dr', str(work/(name+'.o'))], text=True)
(work/'snapshot-disassembly.txt').write_text(disasm)
report = {'make_executed': False, 'source_sha256': sha(here/(name+'.c')),
          'module': str(work/(name+'.ko')), 'module_sha256': sha(work/(name+'.ko')),
          'protected_inputs_unchanged': before, 'undefined_symbols': sorted(imports),
          'probe_addresses': ['0x1fb5f000', '0x1fb5fc14'], 'register_reads': 2,
          'mmio_writes': 0, 'smc_calls': 0, 'mdio_iac_operations': 0}
(work/'compile-report.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
