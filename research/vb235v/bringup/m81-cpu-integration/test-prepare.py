#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise M78->M81 preparation only in a disposable small fixture."""
import importlib.util, json, shutil, sys, tempfile
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
def load(name, path):
    s = importlib.util.spec_from_file_location(name,path)
    m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
    return m
m78 = load('m78prepare',HERE.parent/'m78-cpu-dvfs/prepare.py')
m81 = load('m81prepare',HERE/'prepare.py')
source = Path(sys.argv[1]).resolve(strict=True)
krel = Path('build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60')
phy = json.loads((HERE.parent/'m75-en8811h-paged-status/source-hashes.json').read_text())
build = json.loads((HERE.parent/'m78-cpu-dvfs/source-hashes.json').read_text())
with tempfile.TemporaryDirectory(prefix='m81-prepare-') as temporary:
    tree = Path(temporary)
    paths = [krel/name for name in [*phy,*build,'.config']]
    paths += [Path('target/linux/airoha/vb235v/config-6.18'),
              Path('target/linux/airoha/dts/an7583-tplink_vb235v.dts')]
    for name in paths:
        dest = tree/name; dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source/name,dest)
    (tree/'staging_dir').symlink_to(source/'staging_dir',target_is_directory=True)
    revision = tree/'files/etc/vb235v-system-revision'
    revision.parent.mkdir(parents=True,exist_ok=True); revision.write_text('M83-preserve-parent-revision\n')
    with patch.object(m78.subprocess,'check_output',return_value=m78.PIN+'\n'), \
         patch.object(sys,'argv',['prepare.py',str(tree)]):
        m78.main()
        m81.main()
        first = {str(p.relative_to(tree)):p.read_bytes() for p in tree.rglob('*') if p.is_file()}
        m81.main()
        second = {str(p.relative_to(tree)):p.read_bytes() for p in tree.rglob('*') if p.is_file()}
        assert first == second, 'M81 is not byte-idempotent'
        assert revision.read_text() == 'M83-preserve-parent-revision\n'
        target = tree/krel/'drivers/cpufreq/vb235v-cpufreq.c'
        assert target.read_bytes() == (HERE/'vb235v-cpufreq.c').read_bytes()
        target.write_text('unknown CPU source\n')
        before = {str(p.relative_to(tree)):p.read_bytes() for p in tree.rglob('*') if p.is_file()}
        try: m81.main()
        except AssertionError as e: assert 'Different CPU prerequisite' in str(e)
        else: raise AssertionError('Unknown source accepted')
        after = {str(p.relative_to(tree)):p.read_bytes() for p in tree.rglob('*') if p.is_file()}
        assert before == after, 'Unknown source triggered partial mutation'
print('M81 prepare: M78 prerequisite chain, source gates, two-pass idempotence, parent revision retention and early wrong-source rejection PASS')
