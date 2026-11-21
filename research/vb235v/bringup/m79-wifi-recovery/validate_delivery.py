#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

tree, baseline, out = map(Path, sys.argv[1:4])
here=Path(__file__).resolve().parent
out.mkdir(exist_ok=True,parents=True)
fixture=Path(tempfile.mkdtemp(prefix='patch-fixture-',dir=out))
expected=json.loads((here/'baseline-hashes.json').read_text())
before={n:hashlib.sha256((baseline/n).read_bytes()).hexdigest() for n in expected}
assert before==expected
prepared=fixture/'prepared'
for name in [*expected,'mt7996/eeprom.c']:
    dest=prepared/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(baseline/name,dest)
with (here/'121-vb235v-mt7996-pci-recovery.patch').open('rb') as f:
    subprocess.run(['patch','--batch','--forward','-p1','-d',str(prepared)],stdin=f,check=True,capture_output=True)
subprocess.run([sys.executable,str(here/'verify_sources.py'),str(prepared),'--output',str(out/'prepared-source-report.json')],check=True,capture_output=True)
package=fixture/'build/package/kernel/mt76'
(package/'patches').mkdir(parents=True)
shutil.copyfile(tree/'package/kernel/mt76/Makefile',package/'Makefile')
guard='patches/120-vb235v-private-art-calibration.patch'
shutil.copyfile(tree/'package/kernel/mt76'/guard,package/guard)
guard_before=hashlib.sha256((package/guard).read_bytes()).hexdigest()
for _ in range(2):
    subprocess.run([sys.executable,str(here/'prepare.py'),str(fixture/'build')],check=True,capture_output=True)
assert hashlib.sha256((package/guard).read_bytes()).hexdigest()==guard_before
(package/guard).write_bytes(b'synthetic invalid prerequisite\n')
bad=subprocess.run([sys.executable,str(here/'prepare.py'),str(fixture/'build')],capture_output=True)
assert bad.returncode!=0
kernel=baseline.parent/'linux-6.18.60'
style=subprocess.run(['perl',str(kernel/'scripts/checkpatch.pl'),'--no-tree','--strict','--no-signoff',str(here/'121-vb235v-mt7996-pci-recovery.patch')],capture_output=True,text=True)
assert style.returncode==0,style.stdout+style.stderr
after={n:hashlib.sha256((baseline/n).read_bytes()).hexdigest() for n in expected}
assert before==after
report={'status':'passed','baseline_source_hashes_unchanged':True,'patch_applied_to_fresh_fixture':True,
        'prepared_source_hashes_match':True,'prepare_idempotent':True,'calibration_prerequisite_preserved':True,
        'changed_calibration_prerequisite_rejected':True,'checkpatch':style.stdout.strip(),
        'patch_sha256':hashlib.sha256((here/'121-vb235v-mt7996-pci-recovery.patch').read_bytes()).hexdigest(),
        'fixture':str(fixture)}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
