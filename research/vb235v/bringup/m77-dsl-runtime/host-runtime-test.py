#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Isolated Linux/root supervisor checks; refuses a host with a DSL provider."""
import argparse
import array
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import subprocess
import tempfile
import time

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('binary',type=Path)
p.add_argument('--firmware-source',type=Path)
a=p.parse_args()
if os.geteuid()!=0 or Path('/dev/ponwrt-dsl').exists():
    raise SystemExit('Requires root on an isolated build host without a DSL provider')
binary=str(a.binary.resolve())
checks=0
def check(value):
    global checks
    checks+=1
    assert value
with tempfile.TemporaryDirectory(prefix='ponwrt-m77-runtime-') as tmp:
    root=Path(tmp)
    state=root/'state'
    control=root/'control.sock'
    missing=root/'missing'
    args=[binary,'--state-dir',str(state),'--control-path',str(control),'--firmware-dir',str(missing)]
    def load():
        data=json.loads((state/'dsl-state.json').read_text())
        check(data['schema']==1 and data['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip())
        check(data['line']['showtime'] is False)
        check(all(data['internet'][k] is False for k in ['authenticated','ipv4','ipv6']))
        check(data['internet']['generation']==data['generation'])
        check(stat.S_IMODE((state/'dsl-state.json').stat().st_mode)==0o600)
        check(stat.S_IMODE(state.stat().st_mode)==0o700)
        check((state/'dsl-state.json').is_file())
        return data
    check(subprocess.run(args+['--once'],capture_output=True).returncode==1)
    check(load()['generation']==1)
    check(load()['code']=='INPUTS_MISSING_OR_MISMATCH')
    check(subprocess.run(args+['--once'],capture_output=True).returncode==1)
    check(load()['generation']==2)
    proc=subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    try:
        deadline=time.monotonic()+5
        while not control.exists() and time.monotonic()<deadline:
            time.sleep(.01)
        check(control.exists())
        check(stat.S_IMODE(control.stat().st_mode)==0o600)
        while load()['generation']!=3 and time.monotonic()<deadline:
            time.sleep(.01)
        check(load()['generation']==3)
        check(subprocess.run(args+['--once'],capture_output=True).returncode==1)
        check(load()['generation']==3)
        with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as client:
            client.bind(str(root/'root-client.sock'))
            client.settimeout(3)
            client.sendto(b'force',str(control))
            check(client.recv(80)==b'NACK')
            check(load()['generation']==3)
            # Unexpected ancillary FDs must be rejected and closed, not leaked.
            before_fds=len(list(Path(f'/proc/{proc.pid}/fd').iterdir()))
            with open('/dev/null','rb') as handle:
                client.sendmsg([b'retry'],[(socket.SOL_SOCKET,socket.SCM_RIGHTS,array.array('i',[handle.fileno()]))],0,str(control))
                check(client.recv(80)==b'NACK')
            check(load()['generation']==3)
            check(len(list(Path(f'/proc/{proc.pid}/fd').iterdir()))==before_fds)
            client.sendto(b'retry',str(control))
            check(client.recv(80)==b'ACK 4')
            deadline=time.monotonic()+3
            while load()['state']=='running' and time.monotonic()<deadline:
                time.sleep(.01)
            check(load()['generation']==4)
            check(load()['state']=='blocked')
        # Temporarily widen only this disposable socket's mode to verify that
        # SCM_CREDENTIALS still rejects a non-root sender independently of DAC.
        root.chmod(0o755)
        control.chmod(0o666)
        unpriv=root/'unpriv'
        unpriv.mkdir(mode=0o700)
        os.chown(unpriv,65534,65534)
        pid=os.fork()
        if pid==0:
            try:
                os.setgid(65534)
                os.setuid(65534)
                with socket.socket(socket.AF_UNIX,socket.SOCK_DGRAM) as client:
                    client.bind(str(unpriv/'client.sock'))
                    client.settimeout(3)
                    client.sendto(b'retry',str(control))
                    os._exit(0 if client.recv(80)==b'NACK' else 1)
            except Exception:
                os._exit(2)
        _,exit_status=os.waitpid(pid,0)
        check(os.waitstatus_to_exitcode(exit_status)==0)
        control.chmod(0o600)
        check(load()['generation']==4)
        before=load()['updated_uptime_s']
        deadline=time.monotonic()+7
        while load()['updated_uptime_s']==before and time.monotonic()<deadline:
            time.sleep(.2)
        check(load()['updated_uptime_s']>before)
    finally:
        proc.terminate()
        _,stderr=proc.communicate(timeout=5)
        check(proc.returncode==0 and not stderr)
    check(load()['state']=='stopped' and load()['can_retry'] is False)
    check(not (state/'.dsl-state.new').exists())
    if a.firmware_source:
        firmware=root/'firmware'
        firmware.mkdir(mode=0o700)
        for name in ['ddr_cal.bin','iNIC.bin','tclinux.bin']:
            q=firmware/name
            shutil.copyfile(a.firmware_source/name,q)
            q.chmod(0o600)
        good=args[:-1]+[str(firmware)]
        check(subprocess.run(good+['--once'],capture_output=True).returncode==1)
        data=load()
        check(data['generation']==5 and data['code']=='OWNER_PROVIDER_UNBOUND')
        check(data['stages'][0]['state']=='done')
        # Tamper with a same-size pinned input; later stages must not run.
        q=firmware/'iNIC.bin'
        b=bytearray(q.read_bytes());b[0]^=1;q.write_bytes(b)
        check(subprocess.run(good+['--once'],capture_output=True).returncode==1)
        data=load()
        check(data['generation']==6 and data['code']=='INPUTS_MISSING_OR_MISMATCH')
        check(data['stages'][1]['state']=='pending')
print(json.dumps({'supervisor_checks_passed':checks,'hardware_operations':0,'real_private_manifest_checked':bool(a.firmware_source)}))
