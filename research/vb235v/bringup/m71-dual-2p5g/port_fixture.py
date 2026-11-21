# SPDX-License-Identifier: GPL-2.0-only
"""Validate two physical 2.5G ports connected by the owner's separate cable."""
import argparse,hashlib,json,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'m69-flow-cleanup'))
from fixture_session import Session
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--connection',type=Path,required=True)
p.add_argument('--probe',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--status-module',type=Path)
a=p.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=False)
s=Session(a.connection);ports=['eth1','eth2'];report={'complete':False,'flash_write_commands_sent':False,'bridges_created':False,'IP_addresses_added':False}
restore=[]
def counts(port):
    names=['rx_packets','tx_packets','rx_bytes','tx_bytes','rx_errors','tx_errors','rx_crc_errors','rx_dropped','tx_dropped']
    return {name:int(s.run('cat /sys/class/net/'+port+'/statistics/'+name)) for name in names}
try:
    assert s.run('cat /tmp/sysinfo/board_name').strip()==b'tplink,vb235v-ram-multigig-development'
    assert s.run('cat /sys/class/net/lan-test/carrier').strip()==b'1'
    for port in ports:
        flags=int(s.run('cat /sys/class/net/'+port+'/flags').strip(),16)
        assert not flags&1,'Fixture requires initially down unused ports'
        assert not s.run('ip -4 addr show dev '+port).count(b'inet ')
        assert s.run('test ! -e /sys/class/net/'+port+'/master',check=False)[0]==0,'Port is already enslaved'
        restore.append(port);s.run('ip link set dev '+port+' up')
    for attempt in range(60):
        if all(s.run('cat /sys/class/net/'+port+'/carrier').strip()==b'1' and
               s.run('cat /sys/class/net/'+port+'/speed').strip()==b'2500' for port in ports):break
        time.sleep(1)
    else:raise RuntimeError('Both physical ports did not reach stable 2500 Mbps')
    report['ports']={}
    for port in ports:
        speed=int(s.run('cat /sys/class/net/'+port+'/speed'));duplex=s.run('cat /sys/class/net/'+port+'/duplex').strip().decode()
        assert speed==2500 and duplex=='full','Physical link was not 2500/full'
        report['ports'][port]={'speed_Mbps':speed,'duplex':duplex,'counters_before':counts(port)}
        (out/(port+'-ethtool-private.log')).write_bytes(s.run('ethtool '+port+'; ethtool -i '+port+'; ethtool -S '+port,check=False)[1])
    data=a.probe.read_bytes();s.put(data,'/tmp/vb235v-port-pair-probe')
    assert s.run('sha256sum /tmp/vb235v-port-pair-probe').split()[0].decode()==hashlib.sha256(data).hexdigest()
    s.run('chmod 700 /tmp/vb235v-port-pair-probe')
    result=json.loads(s.run('/tmp/vb235v-port-pair-probe eth1 eth2',timeout=120))
    assert result['complete'] and result['round_trips']==10000 and result['all_frame_bytes_verified']
    report['wire_test']=result
    for port in ports:
        after=counts(port);before=report['ports'][port]['counters_before'];report['ports'][port]['counters_after']=after
        for name in ['rx_packets','tx_packets']:assert after[name]-before[name]>=10000
        for name in ['rx_errors','tx_errors','rx_crc_errors']:assert after[name]==before[name],port+' '+name+' increased'
    assert s.run('cat /sys/class/net/lan-test/carrier').strip()==b'1'
    assert s.run('cat /sys/devices/system/cpu/online').strip()==b'0-1'
    report['management_and_two_CPUs_remained_online']=True;report['complete']=True
    print(json.dumps(result),flush=True)
except BaseException as error:
    report['error']=str(error)
    if a.status_module:
        try:
            data=a.status_module.read_bytes();s.put(data,'/tmp/vb235v_phy_status.ko')
            assert s.run('sha256sum /tmp/vb235v_phy_status.ko').split()[0].decode()==hashlib.sha256(data).hexdigest()
            s.run('rmmod vb235v_phy_status',check=False);s.run('insmod /tmp/vb235v_phy_status.ko')
        except Exception:pass
    try:
        code,data,err=s.run('dmesg; ip link show; ethtool eth1; ethtool eth2',limit=4*1024*1024,check=False)
        (out/'failure-private.log').write_bytes(data+err)
    except Exception:pass
    raise
finally:
    try:
        for port in reversed(restore):s.run('ip link set dev '+port+' down',check=False)
        report['ports_restored_down']=all(not int(s.run('cat /sys/class/net/'+port+'/flags').strip(),16)&1 for port in restore)
    finally:
        s.close();(out/'report.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
