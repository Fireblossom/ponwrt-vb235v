#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Integrate the locked M83 candidate into an existing M75+ tree; no device IO.

Run only while the parent holds the shared build-tree lease. Earlier M73/M75
preparers are deliberately never rerun, as they overwrite later board changes.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

HERE=Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run(*args):subprocess.run([str(a) for a in args],check=True)
def install(source,target,mode=0o644):
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():assert target.read_bytes()==source.read_bytes(),'Different existing M83 file '+str(target)
    else:shutil.copyfile(source,target)
    target.chmod(mode)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('tree',type=Path);p.add_argument('--check-only',action='store_true')
    a=p.parse_args();tree=a.tree.resolve(strict=True);lock=json.loads((HERE/'input-lock.json').read_text())
    assert subprocess.check_output(['git','-C',str(tree),'rev-parse','HEAD'],text=True).strip()==lock['build_base_commit']
    for name,digest in lock['source_sha256'].items():assert sha(HERE.parent/name)==digest,'Frozen source changed '+name
    spec=importlib.util.spec_from_file_location('m75verify',HERE.parent/'m75-en8811h-paged-status/verify_sources.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    baseline=m.verify_sources(tree)
    kernel=tree/'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60'
    cpu=kernel/'drivers/cpufreq/vb235v-cpufreq.c'
    m78=HERE.parent/'m78-cpu-dvfs';m81=HERE.parent/'m81-cpu-integration'
    cpu_stage='absent' if not cpu.exists() else sha(cpu)
    assert cpu_stage in ['absent',sha(m78/'vb235v-cpufreq.c'),sha(m81/'vb235v-cpufreq.c')],'Different CPU candidate already present'
    drop=json.loads((HERE/'dropbear-hashes.json').read_text());drop_path=tree/drop['path']
    assert sha(drop_path) in [drop['baseline'],drop['candidate']],'Different dropbear init prerequisite'
    role=json.loads((HERE/'installer-role-hashes.json').read_text());role_path=tree/role['path']
    assert sha(role_path) in [role['baseline'],role['candidate']],'Different installer role prerequisite'
    assert sha(tree/role['normal_builder_path'])==role['normal_builder_sha256'],'Normal FIT builder changed'
    for name,row in json.loads((HERE.parent/'m70-integrated-accel/private-inputs.json').read_text()).items():
        path=tree/'files'/name
        assert path.stat().st_size==row['bytes'] and sha(path)==row['sha256'],'Private firmware/calibration input differs '+name
    revision=tree/'files/etc/vb235v-system-revision'
    assert re.fullmatch(r'M(?:75|78|81|83)-[A-Za-z0-9_.-]+\n',revision.read_text()),'Unexpected installed build profile revision'
    if a.check_only:
        print(json.dumps({'preflight_passed':True,'source_count':len(lock['source_sha256']),'CPU_stage':cpu_stage,'M75_source_count':len(baseline['source_sha256']),'device_accessed':False},indent=2));return
    if cpu_stage!=sha(m81/'vb235v-cpufreq.c'):run('python3',m78/'prepare.py',tree)
    run('python3',m81/'prepare.py',tree)
    run('python3',HERE.parent/'m79-wifi-recovery/prepare.py',tree)
    run('python3',HERE.parent/'m79-wifi-recovery-v2/prepare.py',tree)
    run('python3',HERE.parent/'m82-wifi-acceleration/prepare.py',tree)
    run('python3',HERE.parent/'m77-dsl-diagnostics/prepare.py',tree)
    dsl=HERE.parent/'m77-dsl-runtime';package=tree/'package/ponwrt/dsl-runtime'
    if not package.exists():run('python3',dsl/'stage-package.py',package)
    else:
        expected={'Makefile':'openwrt-package.mk','ponwrt-dsl.init':'ponwrt-dsl.init','ponwrt-dsl.config':'ponwrt-dsl.config'}
        expected.update({'src/'+name:name for name in ['core.c','core.h','sha256.c','provider.c','provider.h','provider_uapi.h','runtime.c']})
        for dest,src in expected.items():assert (package/dest).read_bytes()==(dsl/src).read_bytes(),'Different existing DSL package '+dest
    if sha(drop_path)==drop['baseline']:
        run('patch','--batch','--fuzz=0','-p1','-d',tree,'-i',HERE/'dropbear-explicit-interface.patch')
    assert sha(drop_path)==drop['candidate']
    if sha(role_path)==role['baseline']:
        run('patch','--batch','--fuzz=0','-p1','-d',tree,'-i',HERE/'installer-role.patch')
    assert sha(role_path)==role['candidate']
    install(HERE/'mkits-vb235v-install-m83.py',tree/'target/linux/airoha/image/mkits-vb235v-install-m83.py',0o755)
    install(HERE/'management.sh',tree/'files/usr/libexec/ponwrt-management-m83',0o755)
    install(HERE/'99zz-ponwrt-management-m83',tree/'files/etc/uci-defaults/99zz-ponwrt-management-m83',0o755)
    install(HERE/'ponwrt-recovery-ssh-m83',tree/'files/etc/init.d/ponwrt-recovery-ssh-m83',0o755)
    for name in ['S95ponwrt-recovery-ssh-m83','K10ponwrt-recovery-ssh-m83']:
        path=tree/'files/etc/rc.d'/name;path.parent.mkdir(parents=True,exist_ok=True)
        target='../init.d/ponwrt-recovery-ssh-m83'
        if path.is_symlink():assert os.readlink(path)==target
        else:assert not path.exists();path.symlink_to(target)
    cfg=tree/'.config';data=cfg.read_text()
    for symbol in ['CONFIG_PACKAGE_ponwrt-diagnostics','CONFIG_PACKAGE_ponwrt-dsl-runtime']:
        data=re.sub(r'^(?:# )?'+re.escape(symbol)+r'(?:=.*| is not set)\n','',data,flags=re.M)+symbol+'=y\n'
    cfg.write_bytes(data.encode());revision.write_bytes((lock['revision']+'\n').encode())
    print('M83 prepared: M81 CPU disarmed, M79 v2 Wi-Fi, M77 diagnostics/disabled DSL, final guarded LAN/TLS migration and fail-closed SSH.')
if __name__=='__main__':main()
