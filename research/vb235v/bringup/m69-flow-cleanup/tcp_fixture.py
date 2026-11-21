# SPDX-License-Identifier: GPL-2.0-only
"""Real-wire TCP hairpin NAT baseline/offload integrity on isolated USB LAN."""
from pathlib import Path
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import argparse,hashlib,http.client,json,os,re,socket,struct,threading,time
from fixture_session import Session

p=argparse.ArgumentParser();p.add_argument('--software',action='store_true');p.add_argument('--upload',action='store_true');p.add_argument('--fw4',action='store_true');p.add_argument('--connection',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
assert not (args.fw4 and args.software)
out=args.output;out.mkdir(parents=True,exist_ok=True)
source='192.168.235.2';router='192.168.235.1';virtual='192.168.235.99';port=8825;table='ponwrt_m68_tcp'
report={'started_utc':datetime.now(timezone.utc).isoformat(),'flash_write_commands_sent':False,'complete':False,'offload_requested':not args.software,'default_fw4_flowtable':args.fw4}
s=Session(args.connection)
old={};old_firewall={};alias=False;created=False;monitor=False;server=None;thread=None;client=None
payload=os.urandom(32*1024*1024);expected=hashlib.sha256(payload).hexdigest();peers=[]
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*unused):pass
    def do_GET(self):
        if self.path!='/m68-random.bin' or self.client_address[0]!=router:
            self.send_error(403);return
        peers.append(self.client_address)
        self.send_response(200);self.send_header('Content-Length',str(len(payload)));self.end_headers()
        try:
            for start in range(0,len(payload),65536):self.wfile.write(payload[start:start+65536])
        except (BrokenPipeError,ConnectionResetError):pass
    def do_POST(self):
        if self.path!='/m68-random.bin' or self.client_address[0]!=router or int(self.headers.get('Content-Length','0'))!=len(payload):
            self.send_error(403);return
        peers.append(self.client_address);remaining=len(payload);digest=hashlib.sha256()
        while remaining:
            block=self.rfile.read(min(65536,remaining))
            if not block:return
            digest.update(block);remaining-=len(block)
        result=json.dumps({'bytes':len(payload),'sha256':digest.hexdigest()}).encode()
        self.send_response(200);self.send_header('Content-Length',str(len(result)));self.end_headers();self.wfile.write(result)
try:
    for family in ['ip','netdev']:
        code,_,_=s.run('nft list table '+family+' '+table,check=False);assert code!=0
    for key in ['flow_offloading','flow_offloading_hw']:
        code,value,err=s.run('uci -q get firewall.@defaults[0].'+key,check=False)
        value=value.decode().strip();assert value in ['','0','1'];old_firewall[key]=value
    enabled='1' if args.fw4 else '0'
    for key in ['flow_offloading','flow_offloading_hw']:s.run('uci set firewall.@defaults[0].'+key+'='+enabled)
    s.run('uci commit firewall; /etc/init.d/firewall reload',timeout=45)
    tables=s.run('nft list flowtables')
    assert (b'flowtable' in tables)==args.fw4
    if args.fw4:assert b'flags offload' in tables and tables.count(b'flowtable')==1
    for path in ['/proc/sys/net/ipv4/ip_forward','/proc/sys/net/ipv4/conf/lan-test/send_redirects']:
        old[path]=s.run('cat '+path).strip().decode()
    s.run('echo 1 > /proc/sys/net/ipv4/ip_forward; echo 0 > /proc/sys/net/ipv4/conf/lan-test/send_redirects')
    s.run('ip addr add '+virtual+'/32 dev lan-test');alias=True
    flags='' if args.software else 'flags offload;'
    flowtable='' if args.fw4 else f'flowtable ft {{ hook ingress priority -10; devices = {{ lan-test }}; {flags} }}'
    forward='' if args.fw4 else '''chain forward_path { type filter hook forward priority -10; policy accept;
  ct state established ct status dnat ip protocol tcp flow add @ft counter
 }'''
    nft=f'''table netdev {table} {{
 chain cpu_seen {{ type filter hook ingress device "lan-test" priority -100; policy accept;
  ip protocol tcp tcp dport {port} counter
  ip protocol tcp tcp sport {port} counter
 }}
}}
table ip {table} {{
 {flowtable}
 chain pre {{ type nat hook prerouting priority -100; policy accept;
  iifname "lan-test" ip daddr {virtual} tcp dport {port} counter dnat to {source}:{port}
 }}
 chain post {{ type nat hook postrouting priority 100; policy accept;
  oifname "lan-test" ip saddr {source} ip daddr {source} tcp dport {port} counter snat to {router}
 }}
 {forward}
}}
'''
    s.put(nft.encode(),'/tmp/m68-tcp.nft')
    s.run('nft -f /tmp/m68-tcp.nft',timeout=45);created=True;monitor=True
    server=ThreadingHTTPServer((source,port),Handler);server.daemon_threads=True
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    client=socket.socket();s.bind_interface(client);client.bind((source,0));client.settimeout(15)
    report['client_source_port']=client.getsockname()[1]
    started=time.monotonic();client.connect((virtual,port))
    if args.upload:
        header=('POST /m68-random.bin HTTP/1.0\r\nHost: m68-isolated-test\r\nConnection: close\r\nContent-Length: '+str(len(payload))+'\r\n\r\n').encode()
        client.sendall(header)
        for start in range(0,len(payload),65536):
            client.sendall(payload[start:start+65536])
            if start in [8*1024*1024,16*1024*1024,24*1024*1024]:
                code,data,err=s.run('cat /sys/kernel/debug/ppe/config /sys/kernel/debug/ppe/bind; cat /sys/kernel/debug/ppe/entries | grep ":'+str(client.getsockname()[1])+'"; nft list table netdev '+table+'; cat /proc/net/nf_conntrack | grep "dport=8825"',check=False,limit=1024*1024)
                (out/('tcp-upload-live-'+str(start)+'-private.log')).write_bytes(data+err)
    else:client.sendall(b'GET /m68-random.bin HTTP/1.0\r\nHost: m68-isolated-test\r\nConnection: close\r\n\r\n')
    response=http.client.HTTPResponse(client);response.begin();assert response.status==200
    got=0;digest=hashlib.sha256();next_snapshot=8*1024*1024
    while not args.upload:
        block=response.read(65536)
        if not block:break
        digest.update(block);got+=len(block)
        if got>=next_snapshot:
            code,data,err=s.run('cat /sys/kernel/debug/ppe/config /sys/kernel/debug/ppe/bind; nft list table netdev '+table+'; cat /proc/net/nf_conntrack | grep "dport=8825"',check=False,limit=1024*1024)
            (out/('tcp-live-'+str(next_snapshot)+'-private.log')).write_bytes(data+err)
            next_snapshot+=8*1024*1024
    if args.upload:
        answer=json.loads(response.read());assert answer=={'bytes':len(payload),'sha256':expected}
        report.update(TCP_upload_bytes=len(payload),TCP_upload_SHA256_matched=True,TCP_upload_seconds=round(time.monotonic()-started,3))
    else:
        assert got==len(payload) and digest.hexdigest()==expected
        report.update(TCP_download_bytes=got,TCP_download_SHA256_matched=True,TCP_download_seconds=round(time.monotonic()-started,3))
    assert len(peers)==1
    report.update(server_observed_NAT_source=peers[0][0],client_observed_virtual_source=virtual)
    observed=s.run('nft list table netdev '+table).decode()
    report['CPU_ingress_counter_packets']=list(map(int,re.findall(r'counter packets (\d+) bytes',observed)))
    report['complete']=True
    print(json.dumps({k:v for k,v in report.items() if k!='started_utc'}),flush=True)
except BaseException as error:
    report['error']=str(error);report['server_connections']=len(peers)
    try:
        code,data,err=s.run('nft list table ip '+table+'; cat /proc/net/nf_conntrack | grep "8825"',check=False)
        (out/'tcp-failure-private.log').write_bytes(data+err)
    except Exception:pass
    raise
finally:
    if client:client.close()
    if server:server.shutdown();server.server_close()
    if thread:thread.join(timeout=2)
    if created:
        s.run('nft delete table ip '+table,timeout=45)
        if args.fw4:s.run('/etc/init.d/firewall reload',timeout=45)
        for attempt in range(30):
            remaining=s.run('cat /sys/kernel/debug/ppe/bind').decode()
            if not any(' BND ' in line and ':'+str(report['client_source_port']) in line for line in remaining.splitlines()):break
            time.sleep(.1)
        else:raise RuntimeError('Bound test PPE entries remained after flowtable deletion')
        report['fixture_PPE_entries_cleared_after_delete']=True
    if monitor:s.run('nft delete table netdev '+table,check=False)
    if alias:s.run('ip addr del '+virtual+'/32 dev lan-test',check=False)
    for path,value in old.items():s.run('echo '+value+' > '+path,check=False)
    if old_firewall:
        for key,value in old_firewall.items():
            s.run('uci set firewall.@defaults[0].'+key+'='+value if value else 'uci -q delete firewall.@defaults[0].'+key,check=False)
        s.run('uci commit firewall; /etc/init.d/firewall reload',check=False,timeout=45)
    s.close();report['finished_utc']=datetime.now(timezone.utc).isoformat()
    (out/('tcp-upload-report.json' if args.upload else 'tcp-report.json')).write_bytes((json.dumps(report,indent=2)+'\n').encode())
