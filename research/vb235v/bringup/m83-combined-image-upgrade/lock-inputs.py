#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Freeze authored source inputs. No build-tree or device access."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
FILES={
 'm78-cpu-dvfs':['prepare.py','cpu-build.patch','source-hashes.json','vb235v-cpufreq.c','vb235v-cpufreq-contract.h'],
 'm81-cpu-integration':['prepare.py','source-hashes.json','vb235v-cpufreq.c','vb235v-cpufreq-contract.h','cpu-observe.sh','cpu-cycle.sh'],
 'm79-wifi-recovery':['prepare.py','121-vb235v-mt7996-pci-recovery.patch'],
 'm79-wifi-recovery-v2':['prepare.py','122-vb235v-mt7996-worker-teardown.patch','patched-v2-hashes.json','verify_sources.py'],
 'm82-wifi-acceleration':['prepare.py','verify_default_off.py'],
 'm77-dsl-diagnostics':['prepare.py','package.Makefile','diagnostics.c','setup.c','www/index.html','www/assets/diagnostics.js','www/assets/diagnostics.css','overlay/etc/init.d/ponwrt-diagnostics','overlay/usr/share/rpcd/acl.d/ponwrt-diagnostics.json','overlay/etc/uci-defaults/99-ponwrt-diagnostics'],
 'm77-dsl-runtime':['stage-package.py','openwrt-package.mk','ponwrt-dsl.init','ponwrt-dsl.config','core.c','core.h','sha256.c','provider.c','provider.h','provider_uapi.h','runtime.c'],
 'm83-combined-image-upgrade':['prepare.py','build.sh','audit.py','management.sh','99zz-ponwrt-management-m83','ponwrt-recovery-ssh-m83','dropbear-explicit-interface.patch','dropbear-hashes.json','mkits-vb235v-install-m83.py','installer-role.patch','installer-role-hashes.json'],
}
records={}
for directory,names in FILES.items():
    for name in names:
        path=ROOT/directory/name;assert path.is_file(),str(path)
        records[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
probe=ROOT.parent/'tools/vb235v_smp_probe.c'
records['../tools/vb235v_smp_probe.c']=hashlib.sha256(probe.read_bytes()).hexdigest()
report={'schema':1,'build_base_commit':'dcf140cb1d5d2c15c1d7c353c95c4c2a56629820',
        'revision':'M83-combined-v1','wireless_NPU':'default-off; hardware qualification pending',
        'dsl':'packaged but service disabled; not DSL-ready','source_sha256':records}
(HERE/'input-lock.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
print('Locked',len(records),'authored source inputs for',report['revision'])
