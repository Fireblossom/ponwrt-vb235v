#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Compile this provider against existing native headers without running kernel make.

Reads one existing .cmd for the exact architecture/compiler flags. Rewrites every
output to a separate directory; never executes shell text or modifies the tree.
This verifies a compilation unit, not module linking/loading or board admission.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shlex
import subprocess

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--kernel-tree',type=Path,required=True)
p.add_argument('--cc',type=Path,required=True)
p.add_argument('--output-dir',type=Path,required=True)
a=p.parse_args()
tree=a.kernel_tree.resolve()
out=a.output_dir.resolve()
here=Path(__file__).resolve().parent
if out.is_relative_to(tree) or out.is_relative_to(here):
    raise SystemExit('Outputs must be outside the kernel and authored source trees')
cmd=tree/'drivers/net/ethernet/airoha/.airoha_eth.o.cmd'
rows=[s.split(' := ',1)[1] for s in cmd.read_text().splitlines() if s.startswith('savedcmd_')]
if len(rows)!=1:
    raise SystemExit('Expected one pinned driver compilation command')
args=shlex.split(rows[0])
if any(x in [';','&&','||','>','|'] for x in args) or args.count('-o')!=1 or args.count('-c')!=1:
    raise SystemExit('Unsupported build-command grammar')
if any(x.startswith(('-fprofile','-fauto-profile','-fdump','-save-temps','-ftime-trace','-fplugin','-MJ','-auxbase','-dumpdir')) for x in args):
    raise SystemExit('Unexpected additional compiler outputs or plugin execution')
if not args[-1].endswith('/airoha_eth.c'):
    raise SystemExit('Unexpected reference source')
out.mkdir(parents=True,exist_ok=True)
args[0]=str(a.cc.resolve())
args=[x for x in args if not x.startswith(('-DKBUILD_','-D__KBUILD_'))]
args=[('-Wp,-MMD,'+str(out/'provider_kernel.d')) if x.startswith('-Wp,-MMD,') else x for x in args]
args[args.index('-o')+1]=str(out/'provider_kernel.o')
args[-1]=str(here/'provider_kernel.c')
args[1:1]=['-DMODULE','-Werror','-DKBUILD_MODFILE="ponwrt_dsl_provider"',
           '-DKBUILD_BASENAME="provider_kernel"','-DKBUILD_MODNAME="ponwrt_dsl_provider"',
           '-D__KBUILD_MODNAME=kmod_ponwrt_dsl_provider']
subprocess.run(args,cwd=tree,env=os.environ.copy(),check=True)
print(json.dumps({'provider_object_compiled':True,'shared_tree_writes':False,
                  'module_link_or_load_verified':False,
                  'sha256':hashlib.sha256((out/'provider_kernel.o').read_bytes()).hexdigest()}))
