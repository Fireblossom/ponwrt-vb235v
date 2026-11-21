# SPDX-License-Identifier: GPL-2.0-only
"""Run two-core memory work and verified crypto while fw4 forwards real-wire TCP."""
import argparse,hashlib,json,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'m69-flow-cleanup'))
from fixture_session import Session
p=argparse.ArgumentParser(description=__doc__)
for name in ['connection','smp-probe','crypto-probe','output']:p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
s=Session(a.connection)
report={'complete':False,'flash_write_commands_sent':False}
try:
    assert s.run('cat /tmp/sysinfo/board_name').strip()==b'tplink,vb235v-ram-multigig-development'
    for path,target in [(a.smp_probe,'/tmp/vb235v-smp-probe'),(a.crypto_probe,'/tmp/vb235v_crypto_probe.ko')]:
        data=path.read_bytes();s.put(data,target)
        assert s.run('sha256sum '+target).split()[0].decode()==hashlib.sha256(data).hexdigest()
    s.run('chmod 700 /tmp/vb235v-smp-probe')
    loaded=s.run('cat /proc/modules')
    if any(line.startswith(b'vb235v_crypto_probe ') for line in loaded.splitlines()):s.run('rmmod vb235v_crypto_probe')
    s.run('(for i in $(seq 1 12); do /tmp/vb235v-smp-probe || exit 1; done; echo M71_SMP_COMPLETE) > /tmp/m71-smp-joint.log 2>&1 < /dev/null &')
    s.run('(for i in $(seq 1 40); do insmod /tmp/vb235v_crypto_probe.ko && rmmod vb235v_crypto_probe || exit 1; echo CRYPTO_RUN_PASSED=$i; done; echo M71_CRYPTO_COMPLETE) > /tmp/m71-crypto-joint.log 2>&1 < /dev/null &')
    subprocess.run([sys.executable,str(HERE.parent/'m69-flow-cleanup/run_suite.py'),'--connection',str(a.connection.resolve()),
                    '--output',str(a.output/'fw4-suite'),'--fw4-only'],check=True)
    deadline=time.monotonic()+180
    while time.monotonic()<deadline:
        smp=s.run('cat /tmp/m71-smp-joint.log').decode();crypto=s.run('cat /tmp/m71-crypto-joint.log').decode()
        if 'M71_SMP_COMPLETE' in smp and 'M71_CRYPTO_COMPLETE' in crypto:break
        time.sleep(1)
    else:raise RuntimeError('Bounded concurrent workers did not complete')
    rows=[json.loads(line) for line in smp.splitlines() if line.startswith('{')]
    assert len(rows)==12 and all(row['errors']==0 and row['cpu_mask']==3 and row['checksum']=='3fd3420cdc24990e' for row in rows)
    assert [line for line in crypto.splitlines() if line.startswith('CRYPTO_RUN_PASSED=')]==['CRYPTO_RUN_PASSED='+str(i) for i in range(1,41)]
    assert s.run('cat /sys/devices/system/cpu/online').strip()==b'0-1'
    report.update(complete=True,SMP_runs=rows,crypto_runs=40,crypto_cases_per_run=34,crypto_negative_checks_per_run=48,
                  fw4_upload_download_passed=True,two_CPUs_online_after_tests=True)
    print('Concurrent two-core memory, 40 crypto oracle rounds and fw4 hardware upload/download passed.',flush=True)
except BaseException as error:
    report['error']=str(error);raise
finally:
    try:
        for name in ['smp','crypto']:
            code,data,err=s.run('cat /tmp/m71-'+name+'-joint.log',check=False)
            (a.output/(name+'-private.log')).write_bytes(data+err)
    finally:
        s.close();(a.output/'report.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
