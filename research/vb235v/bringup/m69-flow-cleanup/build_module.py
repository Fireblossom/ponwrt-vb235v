#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build a reversible flowtable cleanup module against the exact M68 kernel."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
NAMES=['core','ip','path','offload','xdp']
BASELINE='f4a24675d8199ee0a60f044e28a1d1e2bc95d4f48965d881181f7995377b165f'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('tree',type=Path)
    p.add_argument('output',type=Path)
    a=p.parse_args();tree=a.tree.resolve(strict=True);out=a.output.resolve()
    k=tree/'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60'
    assert subprocess.check_output(['git','-C',str(tree),'rev-parse','HEAD'],text=True).strip()=='dcf140cb1d5d2c15c1d7c353c95c4c2a56629820'
    assert hashlib.sha256((k/'net/netfilter/nf_flow_table_offload.c').read_bytes()).hexdigest()==BASELINE
    assert not out.exists(),'Choose a new output directory'
    source=out/'net/netfilter';source.mkdir(parents=True)
    for name in NAMES:
        file='nf_flow_table_'+name+'.c';(source/file).write_bytes((k/'net/netfilter'/file).read_bytes())
    subprocess.run(['patch','-p1','--batch','--fuzz=0','-i',str(HERE/'flowtable-unbind-cleanup.patch')],cwd=out,check=True)
    (out/'Makefile').write_text('obj-m += nf_flow_table.o\nnf_flow_table-y := '+' '.join('net/netfilter/nf_flow_table_'+n+'.o' for n in NAMES)+'\n')
    env=os.environ.copy();env['STAGING_DIR']=str(tree/'staging_dir')
    env['PATH']=str(tree/'staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin')+':/usr/bin:/bin'
    subprocess.run(['make','-C',str(k),'M='+str(out),'ARCH=arm64','CROSS_COMPILE=aarch64-openwrt-linux-musl-','modules'],env=env,check=True)
    sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
    result={'kernel_config_sha256':sha(k/'.config'),'original_offload_source_sha256':BASELINE,
            'patched_offload_source_sha256':sha(source/'nf_flow_table_offload.c'),
            'module_sha256':sha(out/'nf_flow_table.ko'),'device_commands_sent':False}
    (out/'build-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Exact-kernel cleanup module built; hardware regression remains required.')

if __name__=='__main__':main()
