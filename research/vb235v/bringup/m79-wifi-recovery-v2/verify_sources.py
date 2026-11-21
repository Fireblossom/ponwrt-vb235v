#!/usr/bin/env python3
import hashlib
import json
from pathlib import Path
import sys

source=Path(sys.argv[1])
here=Path(__file__).resolve().parent
expected=json.loads((here/'patched-v2-hashes.json').read_text())
actual={n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in expected}
assert actual==expected,'Source differs from frozen M79 v2 or calibration guard changed'
print(json.dumps({'status':'passed','source_sha256':actual,'private_eeprom_guard_unchanged':True},indent=2))
