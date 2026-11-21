#!/usr/bin/env python3
"""Collect offline evidence; read-only against shared inputs and hardware."""
from datetime import datetime, timezone
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
project=repo.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for src,dest in [('compile-logs/report.json','offline-compile-report.json'),
                 ('host-test/report.json','host-test-report.json'),
                 ('calibration-test/report.json','calibration-test-report.json'),
                 ('optional-compile/report.json','optional-compile-report.json'),
                 ('delivery-test/report.json','delivery-validation.json'),
                 ('delivery-test/prepared-source-report.json','prepared-source-report.json')]:
    shutil.copyfile(work/src,here/dest)
compile_report=json.loads((here/'offline-compile-report.json').read_text())
assert compile_report['status']=='compile-link-passed'
source=Path(compile_report['source_tree_read_only'])
toolchain=source.parents[3]/'staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin'
modules={}
for module,digest in compile_report['modules'].items():
    path=work/'mt76'/module
    assert sha(path)==digest
    meta=subprocess.check_output([str(toolchain/'aarch64-openwrt-linux-musl-readelf'),'-p','.modinfo',str(path)],text=True)
    vermagic=re.search(r'vermagic=([^\n]+)',meta).group(1).strip()
    assert vermagic.startswith('6.18.60 ')
    modules[module]={'path':str(path),'sha256':digest,'vermagic':vermagic,'installable_release':False}

live=project/'offline-analysis/live-driver-evidence/20261115T235533Z/modules/5.4.55'
vendor={n:sha(live/n) for n in ['mtk_pci.ko','mt_wifi.ko','mt7993.ko']}
asm=subprocess.check_output([str(toolchain/'aarch64-openwrt-linux-musl-objdump'),'-dr',str(live/'mtk_pci.ko')],text=True)
lines=asm.splitlines();selected=set()
for i,line in enumerate(lines):
    if re.search(r'R_AARCH64_(CALL26|JUMP26)\s+(free_irq|pci_free_irq_vectors)\b',line):
        selected.update(range(max(0,i-6),min(len(lines),i+9)))
(here/'vendor-irq-relocations.txt').write_text('\n'.join(lines[i] for i in sorted(selected))+'\n')
kernel=source.parent/'linux-6.18.60'
report={
 'schema':1,'milestone':'M79','frozen_utc':datetime.now(timezone.utc).isoformat(),
 'classification':'confirmed-resource-lifecycle-defects-repaired-offline; hardware-regression-pending',
 'security_claim':'No demonstrated remote exploit or assigned CVE; not a complete Wi-Fi security audit.',
 'baseline':{'mt76_commit':'0936617dc529ff9da0385221d3fa6de732231177','linux':'6.18.60',
             'installed_parent_baseline':'M75-phy-page-v1','repo_baseline_head':'94f34fb6',
             'linux_msi_source_sha256':sha(kernel/'drivers/pci/msi/msi.c'),
             'linux_device_link_source_sha256':sha(kernel/'drivers/base/core.c')},
 'confirmed_findings':[
   {'id':'HIF2-MSI-owner','evidence':'Primary-only removal leaves secondary-owned pcim MSI action unreleased; rebind log says MSI already enabled.',
    'repair':'Explicit native-vector ledger for both devices, released by the primary after both handlers stop.'},
   {'id':'IRQ-device-lifetime','evidence':'Pinned remove frees mt76 device while primary-owned devm IRQ callbacks still reference it.',
    'repair':'Mask, synchronize IRQs, drain tasklet, mask again and free handlers before DMA/device memory; never infer vector ownership from post-detach WED active state.'},
   {'id':'failed-register-unwind','evidence':'DMA and firmware initialize before guarded EEPROM rejection; failed registration previously only freed mt76 device.',
    'repair':'Stage-aware unregister for errors, MCU exit with service still available, NAPI/worker stop, complete resource cleanup.'},
   {'id':'async-work-lifetime','evidence':'Normal remove did not cancel init_work or close recovery admission; observed reset/scan warning is consistent with teardown work, but not a unique root cause proof.',
    'repair':'Removal admission gate plus reset/dump worker entry guards; cancel init/dump/reset/RRO/RC work and drain after IRQ quiescence.'},
   {'id':'secondary-lifetime','evidence':'get_device pins device object, not secondary devm HIF/BAR memory.',
    'repair':'Managed supplier link before HIF lookup, require CONSUMER_PROBE state, defer unavailable supplier, filter linked supplier in HIF list and lock list deletion.'},
   {'id':'partial-error-cleanup','repair':'Initialize RRO list heads before init failures; tolerate uncreated NAPI and clear dummy-netdev pointer after allocation failure; coredump unregister tolerates NULL.'}],
 'calibration':{'changed':False,'private_guard_patch_sha256':'753ddae900ba240fd7116f95b23f7c7395099ce6ca67237b2a4ead15980d0dae',
                'source_sha256':json.loads((here/'patched-hashes.json').read_text())['mt7996/eeprom.c'],
                'size_gate_bytes':7680,'rejects_missing_wrong_size_chip_or_capabilities':True,'reference_fallback_enabled':False,
                'synthetic_boundary_cases':94,'limitation':'Header/config checks are not cryptographic/full-RF-table authentication; preserve private full-file integrity gates.'},
 'vendor_comparison':{'exact_live_binary_sha256':vendor,
    'live_irq_evidence':'mtk_pci text relocations free_irq@0x2284 -> pci_free_irq_vectors@0x229c and @0x4584 -> @0x459c; local function names stripped.',
    'gpl_bsp_pci_dma_c_sha256':'8d39d1bf6dc1015472aff28bccb2030d58702bf3721d234b62c585d4234367a5',
    'gpl_bsp_vs_live':'Function-level source corroboration only, not proven byte-identical.',
    'original_WM_build':'20260421124444','native_negative_test_WM_build':'20260720165918','post_driver_link_rates':'Both measured 5 GT/s x1 by M66.'},
 'validation':{'host_actual_source_scenarios':1440,'host_sanitizers':['ASan','UBSan'],
    'regression_mutations_detected':['HIF2-vector-leak','handler-after-free','reset-work-after-free'],
    'compile_units':len(compile_report['compiled_units']),'linked_modules':modules,
    'optional_compile':'12 changed-unit builds across WED, NPU, WED+NPU synthetic configs passed; no optional backend qualification.',
    'fresh_patch_fixture_and_prepared_hashes':'passed','prepare_idempotence_and_fail_closed_prerequisite':'passed',
    'checkpatch':'0 errors / 0 warnings / 0 checks; --strict --no-signoff',
    'limitations':compile_report['limitations']+['Mock kernel/firmware/DMA contracts; no live module unload, PCI-core supplier actions, hardware timings or complete partial-DMA fault injection.']},
 'hardware':{'performed':False,'COM3_SP3_SSH_used':False,'modules_installed':False,'NAND_written':False,
             'acceptance_plan':'bringup/m79-wifi-recovery/README.md#parent-only-hardware-acceptance-sequence'},
 'remaining':[
   'Parent must build final integrated image with fresh modpost; compile-check modules are not release artifacts.',
   'Primary-only unbind/rebind, invalid-input rejection then valid recovery, full stack unload, secondary-only supplier unbind and reverse probe order need real tests.',
   'STA 5 GHz / 2.4 GHz reconnect and bidirectional integrity after reload remain parent hardware validation; credentials stay private.',
   'MT7990 fresh-probe wfsys_reset skips hardware reset unless hw_full_reset is set; no register changes guessed; valid rebind firmware state remains acceptance requirement.',
   'Shared root-port reset/QPHY ordering is unchanged and still needs independent qualification.',
   'Wi-Fi WED/NPU callback, DMA concurrency and actual offload must be tested only with a complete matching enabled backend.',
   'No complete audit of radio firmware binaries, over-the-air parsing, multi-adapter hif_idx concurrency, WPA/hostapd/wpa_supplicant or all optional backends is claimed.'],
 'patch':{'path':'bringup/m79-wifi-recovery/121-vb235v-mt7996-pci-recovery.patch','sha256':sha(here/'121-vb235v-mt7996-pci-recovery.patch'),
          'touches':['mt7996/pci.c','mt7996/init.c','mt7996/mt7996.h','mt7996/mac.c','mt7996/coredump.c','dma.c']},
 'delivery_status':'frozen-for-parent-integration-no-commit-no-push'
}
(here.parents[1]/'findings/wifi-recovery-m79.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'patch':report['patch'],'modules':modules,'finding':str(here.parents[1]/'findings/wifi-recovery-m79.json')},indent=2))
