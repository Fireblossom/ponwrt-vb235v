#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import resource

src, out = map(Path, sys.argv[1:3])
here = Path(__file__).resolve().parent
out.mkdir(parents=True, exist_ok=True)
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

def function(path, name):
    text = (src/path).read_text()
    # Locate the definition rather than a call or declaration.
    import re
    match = re.search(r'^(?:static )?(?:void|int) '+name+r'\([^;]+?\)\n\{', text, re.M)
    assert match, (path, name)
    end = match.end()
    depth = 1
    while depth:
        depth += (text[end]=='{')-(text[end]=='}')
        end += 1
    return text[match.start():end]+'\n'

functions = [function('mt7996/pci.c','mt7996_pci_quiesce'),
             function('mt7996/init.c','mt7996_unregister_device'),
             function('mt7996/pci.c','mt7996_pci_release'),
             function('mt7996/pci.c','mt7996_pci_probe'),
             function('mt7996/pci.c','mt7996_pci_remove')]
c = (here/'host_lifecycle.c').read_text().replace('/* DRIVER_FUNCTIONS */','\n'.join(functions))
(out/'actual-source-lifecycle.c').write_text(c)
cmd = ['gcc','-std=gnu11','-g','-O1','-Wall','-Wextra','-Werror','-Wno-sign-compare','-fsanitize=address,undefined',
       '-fno-omit-frame-pointer',str(out/'actual-source-lifecycle.c'),'-o',str(out/'lifecycle')]
subprocess.run(cmd,check=True)
run = subprocess.run([str(out/'lifecycle')],check=True,text=True,capture_output=True)
print(run.stdout,end='')
mutations = {}
for name, old in {
    'hif2-vector-leak': 'pci_free_irq_vectors(to_pci_dev(dev->hif2->dev));',
    'handler-after-free': 'devm_free_irq(mdev->dev, dev->pci_irq, dev);',
    'reset-work-after-free': 'cancel_work_sync(&dev->reset_work);',
}.items():
    assert old in c
    bad = c.replace(old, '(void)0;')
    path = out/('mutation-'+name+'.c')
    path.write_text(bad)
    badcmd = cmd.copy()
    badcmd[-3] = str(path)
    badcmd[-1] = str(out/('mutation-'+name))
    subprocess.run(badcmd,check=True)
    result = subprocess.run([badcmd[-1]],text=True,capture_output=True)
    assert result.returncode != 0, name
    mutations[name] = {'detected':True,'returncode':result.returncode,'stderr_tail':result.stderr[-1200:]}
    print('PASS: regression mutation detected:',name)
(out/'report.json').write_text(json.dumps({'status':'passed','stdout':run.stdout.strip(),
    'compiler':cmd,'extracted_functions_sha256':hashlib.sha256(''.join(functions).encode()).hexdigest(),
    'regression_mutations':mutations,
    'limitations':['Mock kernel contracts; no hardware timings, PCI core device-link actions, or firmware validated.']},indent=2)+'\n')
