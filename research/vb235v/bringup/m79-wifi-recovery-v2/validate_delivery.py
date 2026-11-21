#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

tree,baseline,out=map(Path,sys.argv[1:4])
here=Path(__file__).resolve().parent
out.mkdir(exist_ok=True,parents=True)
fixture=Path(tempfile.mkdtemp(prefix='fixture-',dir=out))
expected=json.loads((here/'baseline-v1-hashes.json').read_text())
hashes=lambda root:{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in expected}
assert hashes(baseline)==expected
prepared=fixture/'prepared'
for name in expected:
    target=prepared/name;target.parent.mkdir(exist_ok=True,parents=True);shutil.copyfile(baseline/name,target)
with (here/'122-vb235v-mt7996-worker-teardown.patch').open('rb') as f:
    subprocess.run(['patch','--batch','--forward','-p1','-d',str(prepared)],stdin=f,check=True,capture_output=True)
verified=subprocess.check_output([sys.executable,str(here/'verify_sources.py'),str(prepared)],text=True)
(out/'prepared-source-report.json').write_text(verified)
package=fixture/'build/package/kernel/mt76';(package/'patches').mkdir(parents=True)
shutil.copyfile(tree/'package/kernel/mt76/Makefile',package/'Makefile')
for name in ['120-vb235v-private-art-calibration.patch','121-vb235v-mt7996-pci-recovery.patch']:
    shutil.copyfile(tree/'package/kernel/mt76/patches'/name,package/'patches'/name)
for _ in range(2):subprocess.run([sys.executable,str(here/'prepare.py'),str(fixture/'build')],check=True,capture_output=True)
(package/'patches/121-vb235v-mt7996-pci-recovery.patch').write_bytes(b'wrong v1 prerequisite\n')
bad=subprocess.run([sys.executable,str(here/'prepare.py'),str(fixture/'build')],capture_output=True)
assert bad.returncode!=0
kernel=baseline.parent/'linux-6.18.60'
style=subprocess.run(['perl',str(kernel/'scripts/checkpatch.pl'),'--no-tree','--strict','--no-signoff',str(here/'122-vb235v-mt7996-worker-teardown.patch')],capture_output=True,text=True)
assert style.returncode==0,style.stdout+style.stderr
assert hashes(baseline)==expected
report={'status':'passed','fresh_additive_patch_applies':True,'seven_source_hashes_match':True,'only_init_c_changed':True,
        'prepare_idempotent':True,'wrong_v1_patch_rejected':True,'baseline_source_unchanged':True,
        'checkpatch':style.stdout.strip(),'patch_sha256':hashlib.sha256((here/'122-vb235v-mt7996-worker-teardown.patch').read_bytes()).hexdigest()}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
