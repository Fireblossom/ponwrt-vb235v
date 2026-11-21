# SPDX-License-Identifier: GPL-2.0-only
"""Read both EN8811H firmware/polarity states using bounded page-window access."""
import argparse,hashlib,json,re,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'m69-flow-cleanup'))
from fixture_session import Session
p=argparse.ArgumentParser(description=__doc__)
for name in ['connection','module','output']:p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
s=Session(a.connection);changed=[]
report={'complete':False,'flash_write_commands_sent':False,'PHY_data_registers_written':False}
try:
    assert s.run('cat /tmp/sysinfo/board_name').strip()==b'tplink,vb235v-ram-multigig-development'
    for port in ['eth1','eth2']:
        assert not int(s.run('cat /sys/class/net/'+port+'/flags').strip(),16)&1
        s.run('test ! -e /sys/class/net/'+port+'/master')
    for port in ['eth1','eth2']:
        changed.append(port);s.run('ip link set dev '+port+' up')
    time.sleep(10)
    data=a.module.read_bytes();s.put(data,'/tmp/vb235v_phy_status.ko')
    assert s.run('sha256sum /tmp/vb235v_phy_status.ko').split()[0].decode()==hashlib.sha256(data).hexdigest()
    s.run('rmmod vb235v_phy_status',check=False);s.run('insmod /tmp/vb235v_phy_status.ko')
    log=s.run('dmesg',limit=4*1024*1024);(a.output/'dmesg-private.log').write_bytes(log)
    lines=[line.decode() for line in log.splitlines() if b'M71_PHY_STATUS' in line][-2:]
    assert len(lines)==2
    for index,line in enumerate(lines):
        fields=dict(re.findall(r'(\w+)=([0-9a-f]+)',line))
        assert int(fields['addr'])==14+index and fields['ret']=='0'
        assert int(fields['polarity'],16)&3==1 and int(fields['ready'],16)==2
    report.update(complete=True,status=lines,original_and_native_polarity_low_bits_match=True,
                  carriers={port:int(s.run('cat /sys/class/net/'+port+'/carrier')) for port in changed})
    print('\n'.join(lines),flush=True)
finally:
    try:
        for port in reversed(changed):s.run('ip link set dev '+port+' down',check=False)
        report['ports_restored_down']=all(not int(s.run('cat /sys/class/net/'+port+'/flags').strip(),16)&1 for port in changed)
    finally:
        s.close();(a.output/'report.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
