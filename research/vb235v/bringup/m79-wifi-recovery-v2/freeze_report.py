#!/usr/bin/env python3
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

work=Path(sys.argv[1]).resolve()
here=Path(__file__).resolve().parent
repo=here.parents[3]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for name,target in [('host/report.json','host-test-report.json'),('compile-logs/report.json','offline-compile-report.json'),
                    ('optional-compile/report.json','optional-compile-report.json'),('delivery/report.json','delivery-validation.json'),
                    ('delivery/prepared-source-report.json','prepared-source-report.json')]:shutil.copyfile(work/name,here/target)
compiled=json.loads((here/'offline-compile-report.json').read_text())
assert compiled['fresh_modpost'] and compiled['status']=='compile-link-fresh-modpost-passed'
baseline=Path(compiled['source_tree_read_only'])
tool=baseline.parents[3]/'staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin/aarch64-openwrt-linux-musl-readelf'
modules={}
for name,digest in compiled['modules'].items():
    path=work/'mt76'/name;assert sha(path)==digest
    meta=subprocess.check_output([str(tool),'-p','.modinfo',str(path)],text=True)
    vermagic=re.search(r'vermagic=([^\n]+)',meta).group(1).strip();assert vermagic=='6.18.60 SMP mod_unload aarch64'
    modules[name]={'path':str(path),'sha256':digest,'vermagic':vermagic}
before=json.loads((here/'baseline-v1-hashes.json').read_text())
after=json.loads((here/'patched-v2-hashes.json').read_text())
assert [name for name in before if before[name]!=after[name]]==['mt7996/init.c']
host=json.loads((here/'host-test-report.json').read_text())
assert host['status']=='passed' and host['v1_regression']['reproduced'] and len(host['mutations'])==5
subprocess.run(['git','diff','--exit-code','--','research/vb235v/bringup/m79-wifi-recovery','research/vb235v/findings/wifi-recovery-m79.json'],cwd=repo,check=True,capture_output=True)
trace=repo.parent/'offline-analysis/m79-wifi-primary-rebind/cycle-1-private.log'
assert 'kthread_park' in trace.read_text(errors='replace') and 'mt76_dma_cleanup' in trace.read_text(errors='replace')
report={
 'schema':1,'milestone':'M79-v2','frozen_utc':datetime.now(timezone.utc).isoformat(),
 'classification':'minimal-followup-fix-for-v1-live-double-park-regression; offline-complete-hardware-pending',
 'v1_commit':'3fdc6a21','v1_files_unchanged':True,
 'security_claim':'Resource cleanup regression; no demonstrated remote exploit or CVE.',
 'live_v1_evidence':{'trace':'offline-analysis/m79-wifi-primary-rebind/cycle-1-private.log','sha256':sha(trace),
    'observed':'WARNING kthread_park, lr mt76_dma_cleanup; common cleanup attempted second park.',
    'parent_reported':'Cold r2 passed, both vectors released with HIF2 still bound; valid calibration rebind restored wiphy within 3 seconds. WARN means clean-teardown acceptance failed.'},
 'root_cause':'v1 explicitly disabled TX worker, then common DMA cleanup disabled the same live task again; kthread_park rejects already-set KTHREAD_SHOULD_PARK.',
 'test_gap_corrected':'v1 host worker-disable was a no-op and DMA cleanup omitted the real common body. V2 extracts real util.h helpers, common DMA cleanup and final free-device body.',
 'minimal_fix':'Permanent unregister uses mt76_worker_teardown (kthread_stop then task=NULL); subsequent common disable and final teardown are no-ops while producer-before-IRQ order remains intact.',
 'production_changes':['mt7996/init.c: one disable-to-teardown call replacement plus comment'],
 'napi_audit':{'production_changed':False,
    'tx':'Unregister disables/deletes once; LISTED clears although dev remains non-NULL; common LISTED guard prevents second disable/delete.',
    'rx':'Unregister disables once; common DMA cleanup only deletes.'},
 'calibration':{'changed':False,'private_guard_eeprom_c_sha256':after['mt7996/eeprom.c'],
    'fail_closed_reference_fallback_policy':'unchanged','v1_94_synthetic_boundary_cases':'Remain applicable to byte-identical loader; not claimed as a new hardware test.'},
 'pinned_contracts':{'mt76_util_h_sha256':sha(baseline/'util.h'),
    'linux_kthread_c_sha256':sha(baseline.parent/'linux-6.18.60/kernel/kthread.c')},
 'validation':{'host_scenarios':1440,'sanitizers':['ASan','UBSan'],
    'worker_model':'Initial unparked and already-parked tasks; v2 park=0 stop=576, no live worker survives cleanup.',
    'v1_regression_reproduced':True,'v1_warning_prior_successful_park_calls':1,
    'mutation_failures_detected':list(host['mutations']),
    'compile':'30 distinct translation units; fresh MODPOST and three regenerated metadata objects; three modules linked.',
    'optional_compile':'12 unit/config combinations passed for WED, NPU, WED+NPU; no offload qualification.',
    'source_and_package_patch_fixture':'passed: seven hashes, only init.c differs, idempotent prepare and wrong-v1-prerequisite rejection.',
    'checkpatch':'strict --no-signoff: 0 errors / warnings / checks',
    'limitations':compiled['limitations']+host['limitations']},
 'modules':modules,
 'patch':{'path':'bringup/m79-wifi-recovery-v2/122-vb235v-mt7996-worker-teardown.patch',
          'sha256':sha(here/'122-vb235v-mt7996-worker-teardown.patch'),'additive_after_unchanged_120_121':True},
 'hardware_v2':{'performed':False,'COM3_SP3_SSH_used':False,'modules_installed':False,'NAND_written':False,
    'next':'Parent verifies complete synchronized fixture, cold boot, primary-only unbind/rebind without any kthread/NAPI/IRQ/WARN, then remaining M79 recovery/STA tests.'},
 'shared_tree_mutated_by_child':False,'commit_or_push_by_child':False,
 'delivery_status':'frozen-for-parent-integration'
}
(here.parents[1]/'findings/wifi-recovery-m79-v2.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'patch':report['patch'],'modules':modules},indent=2))
