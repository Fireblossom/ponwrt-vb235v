#!/usr/bin/env python3
import argparse
import hashlib
import json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('mt76_source', type=Path)
p.add_argument('--output', type=Path)
a = p.parse_args()
here = Path(__file__).resolve().parent
expected = json.loads((here/'patched-hashes.json').read_text())
actual = {n: hashlib.sha256((a.mt76_source/n).read_bytes()).hexdigest() for n in expected}
assert actual == expected, 'Prepared mt76 code or private EEPROM guard differs from reviewed source'
report = {'status':'passed','source_sha256':actual,'private_eeprom_guard_unchanged':True}
if a.output:
    a.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
