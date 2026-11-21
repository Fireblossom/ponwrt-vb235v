# SPDX-License-Identifier: GPL-2.0-only
"""Replay the measured OEM PHY resets; inspect negotiation and raw paired data."""
import argparse,hashlib,json,re,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'m69-flow-cleanup'))
from fixture_session import Session
p=argparse.ArgumentParser(description=__doc__)
for name in ['connection','reset-module','status-module','pair-probe','output']:p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
s=Session(a.connection);unloaded=False
report={'complete':False,'flash_write_commands_sent':False,'bridges_created':False,'IP_addresses_added':False}
try:
    assert s.run('cat /tmp/sysinfo/board_name').strip()==b'tplink,vb235v-ram-multigig-development'
    assert not s.run('ls /sys/bus/gpio/devices').strip(),'Expected M71 RAM board without a GPIO consumer/driver'
    for port in ['eth1','eth2']:
        assert not int(s.run('cat /sys/class/net/'+port+'/flags').strip(),16)&1
        assert s.run('test ! -e /sys/class/net/'+port+'/master',check=False)[0]==0
        assert b'inet ' not in s.run('ip -4 addr show dev '+port)
    rows=[x.split() for x in s.run('cat /proc/modules').splitlines() if x.startswith(b'air_en8811h ')]
    assert len(rows)==1 and rows[0][2]==b'0'
    data=a.reset_module.read_bytes();s.put(data,'/tmp/vb235v_phy_hard_reset.ko')
    assert s.run('sha256sum /tmp/vb235v_phy_hard_reset.ko').split()[0].decode()==hashlib.sha256(data).hexdigest()
    s.run('rmmod vb235v_phy_detail',check=False)
    s.run('rmmod air_en8811h');unloaded=True
    s.run('insmod /tmp/vb235v_phy_hard_reset.ko',timeout=20)
    log=s.run('dmesg',limit=4*1024*1024);(a.output/'reset-private.log').write_bytes(log)
    lines=[x.decode() for x in log.splitlines() if b'M72_HARD_RESET' in x][-13:]
    for gpio,affected in [(35,15),(34,14)]:
        for addr in [14,15]:
            prefix='gpio='+str(gpio)+' phase=asserted addr='+str(addr)+' id='
            found=[line.split(prefix,1)[1].split()[0] for line in lines if prefix in line]
            assert found==['00000000' if addr==affected else '03a2a411'],'Reset mapping not reproduced'
    assert any('restored_mask=c current_mask=c' in line for line in lines)
    report.update(reset_mapping_verified=True,reset_samples=lines)
    s.run('rmmod vb235v_phy_hard_reset')
    s.run('insmod /lib/modules/6.18.60/air_en8811h.ko',timeout=90);unloaded=False
    pair=a.output/'paired'
    proc=subprocess.run([sys.executable,str(HERE.parent/'m71-dual-2p5g/port_fixture.py'),
        '--connection',str(a.connection.resolve()),'--probe',str(a.pair_probe.resolve()),
        '--status-module',str(a.status_module.resolve()),'--output',str(pair)],capture_output=True)
    (pair/'runner-private.log').write_bytes(proc.stdout+proc.stderr)
    report['paired_result']=json.loads((pair/'report.json').read_text())
    report['complete']=report['paired_result']['complete']
finally:
    try:
        s.run('rmmod vb235v_phy_detail',check=False);s.run('rmmod vb235v_phy_hard_reset',check=False)
        if unloaded:s.run('insmod /lib/modules/6.18.60/air_en8811h.ko',timeout=90)
        for addr in ['0e','0f']:
            s.run('test -L /sys/bus/mdio_bus/devices/1fb00000.system-controller:mdio-bus@c8-mii:'+addr+'/driver')
        report['native_module_restored']=True
        report['ports_restored_down']=all(not int(s.run('cat /sys/class/net/'+p+'/flags').strip(),16)&1 for p in ['eth1','eth2'])
    finally:s.close();(a.output/'report.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
