#!/usr/bin/env python3
"""Compile changed units with optional WED/NPU branches enabled, never link/load.

These are synthetic compile configurations; the final image must select and
build the complete matching backend before either offload may be enabled.
"""
import json
from pathlib import Path
import shlex
import subprocess
import sys

baseline, patched, out = map(Path, sys.argv[1:4])
toolchain = baseline.parents[3]/'staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin'
out.mkdir(exist_ok=True, parents=True)
report = {}
for name, flags in [('wed',['-DCONFIG_NET_MEDIATEK_SOC_WED']),
                    ('npu',['-DCONFIG_MT76_NPU','-DCONFIG_MT7996_NPU']),
                    ('wed-npu',['-DCONFIG_NET_MEDIATEK_SOC_WED','-DCONFIG_MT76_NPU','-DCONFIG_MT7996_NPU'])]:
    report[name] = {}
    for unit in ['mt7996/pci','mt7996/init','mt7996/mac','dma']:
        path = Path(unit)
        cmdfile = baseline/path.parent/('.'+path.name+'.o.cmd')
        command = cmdfile.read_text().splitlines()[0].split(' := ',1)[1]
        argv = shlex.split(command.replace(str(baseline), str(patched)))
        argv[0] = str(toolchain/argv[0])
        obj = out/(name+'-'+unit.replace('/','-')+'.o')
        argv[argv.index('-o')+1] = str(obj)
        # MMD follows the object path in the baseline, so also isolate deps.
        argv = [('-Wp,-MMD,'+str(obj)+'.d') if x.startswith('-Wp,-MMD,') else x for x in argv]
        argv[1:1] = flags
        run = subprocess.run(argv,cwd=patched,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        (out/(obj.name+'.log')).write_text(run.stdout)
        report[name][unit] = {'exit_status':run.returncode}
        if run.returncode:
            print(name,unit,run.stdout[-5000:])
    print(name,report[name])
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
assert all(x['exit_status']==0 for units in report.values() for x in units.values())
