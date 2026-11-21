# SPDX-License-Identifier: GPL-2.0-only
"""Validate native integrated netifd station mode using private owner credentials."""
from pathlib import Path
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import argparse,hashlib,ipaddress,json,os,re,sys,threading,time
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'m69-flow-cleanup'))
from fixture_session import Session
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--connection',type=Path,required=True)
p.add_argument('--credentials',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
out=a.output;out.mkdir(parents=True,exist_ok=False)
private=json.loads(a.credentials.read_text(encoding='utf-8'))
assert sorted(row['band'] for row in private['networks'])==['2g','5g']
payload=os.urandom(8*1024*1024);expected=hashlib.sha256(payload).hexdigest();allowed=set()
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        if self.path!='/m65-random-data.bin' or self.client_address[0] not in allowed:
            self.send_error(403); return
        self.send_response(200)
        self.send_header('Content-Length',str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
    def do_POST(self):
        if self.path!='/m65-upload' or self.client_address[0] not in allowed:
            self.send_error(403); return
        if self.headers.get('Transfer-Encoding','').lower()=='chunked':
            chunks=[];size=0
            while True:
                line=self.rfile.readline(129)
                if len(line)>128 or not re.fullmatch(rb'[0-9A-Fa-f]+\r\n',line):
                    self.send_error(400); return
                count=int(line.strip(),16)
                if count==0:
                    if self.rfile.readline(3)!=b'\r\n': self.send_error(400);return
                    break
                if count>len(payload)-size: self.send_error(400);return
                part=self.rfile.read(count)
                if len(part)!=count or self.rfile.read(2)!=b'\r\n': self.send_error(400);return
                chunks.append(part);size+=count
            data=b''.join(chunks)
        else:
            size=int(self.headers.get('Content-Length','0'))
            if size!=len(payload): self.send_error(400); return
            data=self.rfile.read(size)
        if len(data)!=len(payload) or hashlib.sha256(data).hexdigest()!=expected:
            self.send_error(400); return
        body=(expected+'\n').encode()
        self.send_response(200)
        self.send_header('Content-Length',str(len(body)))
        self.end_headers(); self.wfile.write(body)

server=ThreadingHTTPServer(('192.168.123.25',8823),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
s=Session(a.connection)
report={'started_utc':datetime.now(timezone.utc).isoformat(),'complete':False,'flash_write_commands_sent':False,
 'native_integrated_userspace_only':True,'netifd_managed_station':True,'credentials_published':False,'networks':[]}
saved={name:s.run('cat /etc/config/'+name) for name in ['wireless','network']}
try:
    assert b'type AP' not in s.run('iw dev'),'Unexpected active AP before station test'
    for name,data in saved.items():s.put(data,'/tmp/m70-restore-'+name)
    for network in sorted(private['networks'],key=lambda row:row['band']):
        band=network['band'];radio='radio1' if band.startswith('5') else 'radio0';other='radio0' if radio=='radio1' else 'radio1'
        assert re.fullmatch(r'[A-Za-z0-9 _.-]{1,32}',network['ssid'])
        psk=hashlib.pbkdf2_hmac('sha1',private['password'].encode(),network['ssid'].encode(),4096,32).hex()
        section='sta_test_'+band
        config=f'''delete wireless.sta_test_2g
delete wireless.sta_test_5g
set network.sta_test=interface
set network.sta_test.proto='dhcp'
set network.sta_test.defaultroute='0'
set network.sta_test.peerdns='0'
set wireless.{radio}.disabled='0'
set wireless.{other}.disabled='1'
set wireless.{radio}.channel='auto'
set wireless.{radio}.country='DE'
set wireless.{section}=wifi-iface
set wireless.{section}.device='{radio}'
set wireless.{section}.mode='sta'
set wireless.{section}.network='sta_test'
set wireless.{section}.ssid='{network['ssid']}'
set wireless.{section}.encryption='psk2'
set wireless.{section}.key='{psk}'
commit network
commit wireless
'''
        s.run('wifi down; ifdown sta_test',check=False)
        for attempt in range(30):
            if not s.run('iw dev').strip():break
            time.sleep(.5)
        else:raise RuntimeError('Previous wireless interface did not stop')
        s.put(config.encode(),'/tmp/m70-station-uci')
        s.run('uci batch < /tmp/m70-station-uci; ubus call network reload; ifup sta_test; wifi up',timeout=45)
        deadline=time.monotonic()+75;status={}
        while time.monotonic()<deadline:
            code,data,err=s.run('ubus call network.interface.sta_test status',check=False)
            if code==0:
                status=json.loads(data)
                if status.get('up') and status.get('ipv4-address'):break
            time.sleep(1)
        assert status.get('up') and status.get('ipv4-address'),'Managed station DHCP incomplete on '+band
        iface=status['l3_device'];assert re.fullmatch(r'[A-Za-z0-9_.-]{1,15}',iface) and iface!='lan-test'
        info=s.run('iw dev '+iface+' info');assert b'type managed' in info
        link=s.run('iw dev '+iface+' link');assert ('SSID: '+network['ssid']).encode() in link
        frequency=int(re.search(rb'freq:\s*(\d+)',link)[1]);assert (frequency>=5000)==band.startswith('5')
        address=str(ipaddress.IPv4Address(status['ipv4-address'][0]['address']))
        allowed.add(address)
        route=s.run('ip route get 192.168.123.25');assert ('dev '+iface).encode() in route
        before=[int(s.run('cat /sys/class/net/'+iface+'/statistics/'+direction+'_bytes')) for direction in ['rx','tx']]
        started=time.monotonic()
        s.run('wget -q -T 20 -O /tmp/m65-wifi-data.bin http://192.168.123.25:8823/m65-random-data.bin',timeout=35)
        assert s.run('sha256sum /tmp/m65-wifi-data.bin').split()[0].decode()==expected
        s.run('wget -q -T 20 --post-file=/tmp/m65-wifi-data.bin -O /tmp/m70-upload-receipt http://192.168.123.25:8823/m65-upload',timeout=35)
        assert s.run('cat /tmp/m70-upload-receipt').strip().decode()==expected
        after=[int(s.run('cat /sys/class/net/'+iface+'/statistics/'+direction+'_bytes')) for direction in ['rx','tx']]
        assert all(a-b>=len(payload) for a,b in zip(after,before))
        result={'band':band,'authenticated':True,'DHCP_address_obtained':True,'frequency_MHz':frequency,
         'TCP_download_bytes':len(payload),'TCP_upload_bytes':len(payload),'both_SHA256_matched':True,
         'RX_TX_bytes_increased':[a-b for a,b in zip(after,before)],'seconds':round(time.monotonic()-started,3)}
        report['networks'].append(result);print(json.dumps(result),flush=True)
        (out/('station-'+band+'-private.log')).write_bytes(s.run('iw dev '+iface+' station dump'))
        s.run('wifi down; ifdown sta_test',timeout=30)
    report['complete']=len(report['networks'])==2
except BaseException as error:
    report['error']=str(error)
    try:(out/'failure-private.log').write_bytes(s.run('logread; iw dev; ubus call network.wireless status; uci show wireless',limit=3*1024*1024))
    except Exception:pass
    raise
finally:
    try:
        s.run('wifi down; ifdown sta_test',check=False)
        for name in saved:s.run('cat /tmp/m70-restore-'+name+' > /etc/config/'+name)
        s.run('ubus call network reload; wifi down',timeout=45)
    finally:
        s.close();server.shutdown();server.server_close()
        report['finished_utc']=datetime.now(timezone.utc).isoformat()
        (out/'report.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
