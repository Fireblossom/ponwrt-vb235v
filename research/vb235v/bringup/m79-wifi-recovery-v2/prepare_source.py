#!/usr/bin/env python3
"""Make the additive v2 patch in an explicitly isolated v1 source copy."""
import difflib
import hashlib
import json
from pathlib import Path
import sys

source=Path(sys.argv[1]).resolve()
here=Path(__file__).resolve().parent
v1=here.parent/'m79-wifi-recovery'
expected=json.loads((v1/'patched-hashes.json').read_text())
before={n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in expected}
assert before==expected,'Need exact frozen v1 prepared source'
name='mt7996/init.c'
old=(source/name).read_text()
needle='\tmt76_worker_disable(&dev->mt76.tx_worker);'
assert old.count(needle)==1
new=old.replace(needle,'\t/* Permanent shutdown: later DMA/free cleanup must see no worker. */\n\tmt76_worker_teardown(&dev->mt76.tx_worker);')
(source/name).write_text(new)
patch='''Subject: [PATCH] wifi: mt7996: terminate TX worker before permanent teardown

M79 first parked the worker before releasing IRQs. Common DMA cleanup then
parked it again, triggering kthread_park's already-parked warning on real
hardware. Terminate this worker instead: the existing helper stops it and
clears task, making the later disable and final teardown no-ops. Preserve
the producer-before-IRQ teardown order and private calibration guard.

---
'''+''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+name,tofile='b/'+name))
(here/'122-vb235v-mt7996-worker-teardown.patch').write_text(patch)
(here/'baseline-v1-hashes.json').write_text(json.dumps(before,indent=2)+'\n')
after={n:hashlib.sha256((source/n).read_bytes()).hexdigest() for n in expected}
(here/'patched-v2-hashes.json').write_text(json.dumps(after,indent=2)+'\n')
print('Patched:',source/name)
