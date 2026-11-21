#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise preparation in a small disposable fixture, never in the input tree."""
import importlib.util, json, shutil, sys, tempfile
from pathlib import Path
from unittest.mock import patch
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('m78prepare', HERE/'prepare.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
source = Path(sys.argv[1]).resolve(strict=True)
krel = Path('build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60')
phy = json.loads((HERE.parent/'m75-en8811h-paged-status/source-hashes.json').read_text())
build = json.loads((HERE/'source-hashes.json').read_text())
with tempfile.TemporaryDirectory(prefix='m78-prepare-') as tmp:
    tree = Path(tmp)
    paths = [krel/name for name in [*phy, *build, '.config']]
    paths += [Path('target/linux/airoha/vb235v/config-6.18'),
              Path('target/linux/airoha/dts/an7583-tplink_vb235v.dts')]
    for name in paths:
        dest = tree/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source/name, dest)
    # Only the pinned Git identity is mocked. Actual SHA gates and patch execute.
    with patch.object(m.subprocess, 'check_output', return_value=m.PIN+'\n'), \
         patch.object(sys, 'argv', ['prepare.py', str(tree)]):
        m.main()
        before = {str(p.relative_to(tree)): p.read_bytes() for p in tree.rglob('*') if p.is_file()}
        m.main()
        after = {str(p.relative_to(tree)): p.read_bytes() for p in tree.rglob('*') if p.is_file()}
        assert before == after, 'Preparation is not idempotent'
        cfg = (tree/krel/'.config').read_text()
        assert 'CONFIG_CPU_FREQ_DEFAULT_GOV_PERFORMANCE=y\n' in cfg
        assert 'CONFIG_CPU_FREQ_DEFAULT_GOV_ONDEMAND=y' not in cfg
        assert '# CONFIG_ARM_AIROHA_SOC_CPUFREQ is not set\n' in cfg
        assert 'CONFIG_ARM_VB235V_BOOT_VOLTAGE_CPUFREQ=y\n' in cfg
        assert (tree/'target/linux/airoha/dts/an7583-tplink_vb235v.dts').read_text().count('tplink,m78-boot-voltage-cpufreq;') == 1
        bad = tree/krel/next(iter(phy))
        bad.write_bytes(b'wrong PHY prerequisite\n')
        try:
            m.main()
        except AssertionError as e:
            assert 'M75 prerequisite absent' in str(e)
        else:
            raise AssertionError('Unknown prerequisite accepted')
print('M78 preparation: real patch/SHA gates, two-pass idempotence, governor/driver/DT integration and wrong-PHY rejection PASS')
