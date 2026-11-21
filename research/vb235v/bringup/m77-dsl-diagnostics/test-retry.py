#!/usr/bin/env python3
"""Exercise the actual diagnostic client with root Unix peers and real runtime."""
import argparse
import array
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time

p=argparse.ArgumentParser()
p.add_argument('--include',type=Path)
p.add_argument('--json-library',default='-ljson-c')
p.add_argument('--runtime',type=Path,required=True)
p.add_argument('--sanitize',action='store_true')
args=p.parse_args()
assert os.geteuid()==0,'Run in an isolated root Linux/WSL test environment'
here=Path(__file__).resolve().parent
checks=[]
with tempfile.TemporaryDirectory(prefix='m77-retry-') as temp:
    root=Path(temp);run=root/'run';run.mkdir(mode=0o700);control=root/'control.sock';binary=root/'client'
    command=['cc','-O1','-g','-std=c11','-Wall','-Wextra','-Werror',
             f'-DRUN="{run}"',f'-DDSL_CONTROL="{control}"']
    if args.include:command+=['-I'+str(args.include)]
    if args.sanitize:command+=['-fsanitize=address,undefined','-fno-omit-frame-pointer']
    command += [str(here/'diagnostics.c'),args.json_library,'-o',str(binary)]
    subprocess.run(command,check=True)
    # A fresh collector cache must not extend the lifetime of old DSL proof.
    up=float(Path('/proc/uptime').read_text().split()[0])-0.01
    boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    cache={'schema':1,'system':{'boot_id':boot,'uptime_s':up},'internet':{'authenticated':True}}
    (run/'status.json').write_text(json.dumps(cache))
    dsl={'schema':1,'boot_id':boot,'generation':1,'updated_uptime_s':up-31,'state':'online',
         'line':{'showtime':True},'stages':[{'id':'ppp','state':'done'},{'id':'internet','state':'done'}],
         'internet':{'generation':1,'authenticated':True,'ipv4':True,'ipv6':False}}
    (run/'dsl-state.json').write_text(json.dumps(dsl))
    expired=json.loads(subprocess.check_output([str(binary),'call','status']))
    assert expired['dsl']['code']=='DSL_STATE_STALE' and expired['internet']['authenticated'] is False
    checks.append('fresh cache cannot extend expired underlying DSL evidence')
    dsl['updated_uptime_s']=up;(run/'dsl-state.json').write_text(json.dumps(dsl))
    fresh=json.loads(subprocess.check_output([str(binary),'call','status']))
    assert fresh['internet']['authenticated'] is True and fresh['internet']['ipv4'] is True
    checks.append('fresh complete current-generation proof remains readable')
    (run/'status.json').unlink();(run/'dsl-state.json').unlink()
    def client():
        result=subprocess.run([str(binary),'call','retry'],check=True,capture_output=True,timeout=5)
        assert not list(run.iterdir()),'Client must remove socket and temporary directory'
        return json.loads(result.stdout)
    assert client()['accepted'] is False;checks.append('absent controller rejected')
    def peer_case(reply,accepted=False,mode=0o600,rights=False):
        server=socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM);server.bind(str(control));os.chmod(control,mode)
        observations=[]
        def serve():
            server.settimeout(4)
            try:
                data,address=server.recvfrom(64)
                st=os.stat(address)
                observations.append(data==b'retry' and st.st_uid==0 and st.st_mode&0o777==0o600)
                if reply is None:time.sleep(2.3);return
                if rights:
                    fd=os.open('/dev/null',os.O_RDONLY)
                    try:server.sendmsg([reply],[(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[fd]))],0,address)
                    finally:os.close(fd)
                else:server.sendto(reply,address)
            except socket.timeout:pass
        thread=threading.Thread(target=serve);thread.start()
        try:
            result=client();assert result['accepted'] is accepted,(reply,result)
            if accepted:assert result['generation']==3
        finally:
            thread.join(timeout=5);assert not thread.is_alive();server.close();control.unlink()
        if mode==0o600:assert observations==[True]
        else:assert not observations
    peer_case(b'ACK 3',True);checks.append('named root0600 client accepts positive generation ACK')
    for reply in [b'NACK',b'JUNK3',b'ACK 0',b'ACK -1',b'ACK +3',b'ACK 3\x00extra',b'ACK 3\n',b'ACK 999999999999999999999999999']:
        peer_case(reply);checks.append('malformed or negative acknowledgement rejected: '+repr(reply))
    peer_case(b'ACK 3',rights=True);checks.append('unexpected received descriptor rejected and closed')
    peer_case(b'ACK 3',mode=0o666);checks.append('unsafe controller socket mode rejected before sending')
    peer_case(None);checks.append('missing ACK times out once without automatic resend')
    state=root/'state';firmware=root/'firmware';firmware.mkdir(mode=0o700)
    runtime=subprocess.Popen([str(args.runtime),'--state-dir',str(state),'--control-path',str(control),'--firmware-dir',str(firmware)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            if runtime.poll() is not None:raise RuntimeError('runtime exited during isolated startup')
            if control.exists() and (state/'dsl-state.json').exists():
                status=json.loads((state/'dsl-state.json').read_text())
                if status['can_retry']:break
            time.sleep(.02)
        else:raise AssertionError('runtime did not publish retryable state')
        before=status['generation'];result=client()
        assert result['accepted'] is True and result['generation']==before+1
        observed=json.loads((state/'dsl-state.json').read_text())
        assert observed['generation']==result['generation']
        assert observed['internet']['authenticated'] is False
        checks.append('real supervisor ACK matches durable new generation, without claiming Internet')
    finally:
        runtime.terminate();runtime.communicate(timeout=5)
print(json.dumps({'passed':True,'checks':checks},indent=2))
