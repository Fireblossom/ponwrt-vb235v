# SPDX-License-Identifier: GPL-2.0-only
"""Bounded real-wire UDP hairpin NAT test on the isolated USB LAN."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,os,socket,struct,threading,time
from fixture_session import Session

source='192.168.235.2';router='192.168.235.1';virtual='192.168.235.99';port=8824
table='ponwrt_m68_test'
p=argparse.ArgumentParser();p.add_argument('--software',action='store_true');p.add_argument('--connection',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
out=args.output;out.mkdir(parents=True,exist_ok=True)
report={'started_utc':datetime.now(timezone.utc).isoformat(),'flash_write_commands_sent':False,'complete':False}
s=Session(args.connection)
server=client=None;stop=threading.Event();worker=None;old={};old_firewall={};created=False;alias=False;monitor=False
seen=[];errors=[]
def bound_socket():
    sock=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.bind_interface(sock)
    sock.bind((source,0));sock.settimeout(3)
    if hasattr(socket,'SIO_UDP_CONNRESET'):sock.ioctl(socket.SIO_UDP_CONNRESET,False)
    return sock
try:
    code,_,_=s.run('nft list table ip '+table,check=False);assert code!=0,'Test table already exists'
    assert virtual.encode() not in s.run('ip -4 addr show dev lan-test')
    code,_,_=s.run('nft list table netdev ponwrt_m68_cpu',check=False);assert code!=0
    for key in ['flow_offloading','flow_offloading_hw']:
        code,value,err=s.run('uci -q get firewall.@defaults[0].'+key,check=False)
        value=value.decode().strip();assert value in ['','0','1'];old_firewall[key]=value
    s.run("uci set firewall.@defaults[0].flow_offloading='0'; uci set firewall.@defaults[0].flow_offloading_hw='0'; uci commit firewall; /etc/init.d/firewall reload",timeout=45)
    assert b'flowtable' not in s.run('nft list flowtables')
    for key,path in [('forward','/proc/sys/net/ipv4/ip_forward'),('redirects','/proc/sys/net/ipv4/conf/lan-test/send_redirects')]:
        old[path]=s.run('cat '+path).strip().decode()
    s.run('echo 1 > /proc/sys/net/ipv4/ip_forward; echo 0 > /proc/sys/net/ipv4/conf/lan-test/send_redirects')
    s.run('ip addr add '+virtual+'/32 dev lan-test');alias=True
    cpu_rules='''table netdev ponwrt_m68_cpu {
 chain cpu_seen { type filter hook ingress device "lan-test" priority -100; policy accept;
  ip protocol udp udp dport 8824 counter comment "M68 request CPU ingress"
  ip protocol udp udp sport 8824 counter comment "M68 reply CPU ingress"
 }
}
'''
    s.put(cpu_rules.encode(),'/tmp/m68-cpu-seen.nft');s.run('nft -f /tmp/m68-cpu-seen.nft');monitor=True
    server=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    s.bind_interface(server);server.bind((source,port));server.settimeout(.2)
    if hasattr(socket,'SIO_UDP_CONNRESET'):server.ioctl(socket.SIO_UDP_CONNRESET,False)
    client=bound_socket();client_port=client.getsockname()[1]
    report['offload_requested']=not args.software
    offload='' if args.software else 'flags offload;'
    rules=f'''table ip {table} {{
 flowtable ft {{ hook ingress priority -10; devices = {{ lan-test }}; {offload} }}
 chain prepare_guard {{ type filter hook prerouting priority -300; policy accept;
  iifname "lan-test" ip saddr {source} ip daddr {router} udp sport {port} udp dport {client_port} udp length 28 counter notrack drop
 }}
 chain pre {{ type nat hook prerouting priority -100; policy accept;
  iifname "lan-test" ip daddr {virtual} udp dport {port} counter dnat to {source}:{port}
 }}
 chain post {{ type nat hook postrouting priority 100; policy accept;
  oifname "lan-test" ip saddr {source} ip daddr {source} udp dport {port} counter snat to {router}
 }}
 chain forward_path {{ type filter hook forward priority -10; policy accept;
  ct state established ct status dnat ip protocol udp flow add @ft counter
 }}
}}
'''
    s.put(rules.encode(),'/tmp/m68-flow.nft')
    code,data,err=s.run('nft -f /tmp/m68-flow.nft',timeout=45,check=False)
    (out/'nft-offload-add-private.log').write_bytes(data+err)
    assert code==0,'Hardware flowtable registration failed; inspect private error'
    created=True;report['flowtable_registered']=True
    (out/'ppe-config-after-add-private.log').write_bytes(s.run('cat /sys/kernel/debug/ppe/config',limit=1024*1024))
    server.sendto(b'M68_UDP_PATH_PREPARE',(router,client_port))
    def echo():
        while not stop.is_set():
            try:
                data,peer=server.recvfrom(1500)
                if peer[0]!=router:errors.append('Unexpected sender');continue
                seen.append(peer);server.sendto(data,peer)
            except socket.timeout:continue
            except OSError as error:
                if not stop.is_set():errors.append(str(error))
                break
    worker=threading.Thread(target=echo,daemon=True);worker.start()
    nonce=os.urandom(16);fixture=os.urandom(1168);digest=hashlib.sha256();started=time.monotonic()
    report['client_source_port']=client_port
    for seq in range(2000):
        packet=nonce+struct.pack('!I',seq)+fixture
        client.sendto(packet,(virtual,port))
        value,peer=client.recvfrom(1500)
        assert peer==(virtual,port) and value==packet,'NAT echo source or data mismatch'
        digest.update(value)
        if seq in [100,500,1500]:
            snap=s.run('cat /sys/kernel/debug/ppe/config /sys/kernel/debug/ppe/bind; nft list table netdev ponwrt_m68_cpu; cat /proc/net/nf_conntrack 2>/dev/null | grep "dport=8824"',limit=1024*1024,check=False)
            (out/('offload-live-'+str(seq)+'-private.log')).write_bytes(snap[1]+snap[2])
        time.sleep(.002)
    assert not errors and len(seen)==2000
    report.update(UDP_echo_packets=2000,UDP_payload_bytes=2000*(16+4+1168),UDP_echo_SHA256=digest.hexdigest(),
      every_datagram_verified=True,server_observed_NAT_source=router,client_observed_virtual_source=virtual,
      seconds=round(time.monotonic()-started,3))
    report['nft_counters']=s.run('nft list table ip '+table).decode()
    observed=s.run('nft list table netdev ponwrt_m68_cpu').decode()
    report['CPU_ingress_counter_packets']=list(map(int,__import__('re').findall(r'counter packets (\d+) bytes',observed)))
    (out/'cpu-ingress-counters-private.log').write_bytes(observed.encode())
    (out/'after-hairpin-dmesg-private.log').write_bytes(s.run('dmesg',limit=2*1024*1024))
    report['complete']=True
    print(json.dumps({k:v for k,v in report.items() if k not in ['nft_counters','started_utc']}),flush=True)
except BaseException as error:
    report['error']=str(error)
    report['server_received_packets']=len(seen);report['server_errors']=errors
    try:
        dump=s.run('nft list table ip '+table+'; cat /proc/net/nf_conntrack 2>/dev/null | grep "8824"; ip -4 addr show dev lan-test',check=False)
        (out/'hairpin-failure-network-private.log').write_bytes(dump[1]+dump[2])
    except Exception:pass
    try:(out/'hairpin-failure-dmesg-private.log').write_bytes(s.run('dmesg',limit=2*1024*1024))
    except Exception:pass
    raise
finally:
    stop.set()
    if worker:worker.join(timeout=1)
    if server:server.close()
    if client:client.close()
    if created:
        s.run('nft delete table ip '+table,timeout=45)
        for attempt in range(30):
            remaining=s.run('cat /sys/kernel/debug/ppe/bind').decode()
            if not any(' BND ' in line and ':'+str(client_port) in line for line in remaining.splitlines()):break
            time.sleep(.1)
        else:raise RuntimeError('Bound test PPE entries remained after flowtable deletion')
        report['fixture_PPE_entries_cleared_after_delete']=True
    if monitor:s.run('nft delete table netdev ponwrt_m68_cpu',check=False)
    if alias:s.run('ip addr del '+virtual+'/32 dev lan-test',check=False)
    for path,value in old.items():s.run('echo '+value+' > '+path,check=False)
    if old_firewall:
        for key,value in old_firewall.items():
            s.run('uci set firewall.@defaults[0].'+key+'='+value if value else 'uci -q delete firewall.@defaults[0].'+key,check=False)
        s.run('uci commit firewall; /etc/init.d/firewall reload',check=False,timeout=45)
    s.close();report['finished_utc']=datetime.now(timezone.utc).isoformat()
    (out/'hairpin-report.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
