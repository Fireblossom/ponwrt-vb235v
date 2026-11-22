#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Execute the exact init function with mocked procd/network discovery only."""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('derive',HERE/'derive-dropbear.py');derive=importlib.util.module_from_spec(spec);spec.loader.exec_module(derive)
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);a=p.parse_args()
original=a.source.read_text();candidate=derive.patched(original)
def body(text):return text[text.index('dropbear_instance()\n'):text.index('\nload_interfaces()')]
helpers='''
normalize_list() { printf '%s\\n' "$1" | xargs; }
logger() { :; }
warn_multiple_interfaces() { :; }
network_is_up() { return 0; }
network_get_device() { eval "$1=br-lan"; }
network_get_ipaddrs_all() { eval "$1=\\\"\\$MOCK_IPS\\\""; }
procd_open_instance() { :; }
procd_close_instance() { :; }
procd_set_param() { if [ "$1" = command ]; then shift; printf '%s\\0' "$@"; fi; }
procd_append_param() { if [ "$1" = command ]; then shift; printf '%s\\0' "$@"; fi; }
procd_add_mdns() { :; }
config_list_foreach() { :; }
enable=1; vrf=; BOOT=; DirectInterface=; Interface=; MOCK_IPS=; Port=22
PasswordAuth=0; GatewayPorts=0; LocalPortForward=0; RemotePortForward=0
ForceCommand=; RootPasswordAuth=0; RootLogin=1; rsakeyfile=; BannerFile=
IdleTimeout=0; MaxSessionDuration=0; SSHKeepAlive=300; MaxAuthTries=3
RecvWindowSize=0; mdns=0; NAME=dropbear; PROG=/usr/sbin/dropbear
'''
def command(text,interface,ips,boot='',direct=''):
    setup=f"Interface='{interface}'; MOCK_IPS='{ips}'; BOOT='{boot}'; DirectInterface='{direct}'\n"
    result=subprocess.run(['sh'],input=(helpers+body(text)+setup+'dropbear_instance test 0\n').encode(),capture_output=True)
    assert result.returncode==0,result.stderr
    return [x.decode() for x in result.stdout.split(b'\0') if x]
def ports(cmd):return [cmd[i+1] for i,v in enumerate(cmd) if v=='-p']
checks=[]
assert ports(command(original,'lan',''))==['22'];checks.append('baseline really falls back to wildcard when explicit LAN has no address')
assert command(candidate,'lan','')==[];checks.append('explicit LAN with no address produces no listener')
assert command(candidate,' ','')==[];checks.append('explicit whitespace-only interface does not become wildcard')
assert ports(command(candidate,'lan','192.168.235.1'))==['192.168.235.1:22'];checks.append('normal IPv4 listener retained')
assert ports(command(candidate,'lan','192.168.235.1 fd00::1'))==['192.168.235.1:22','fd00::1:22'];checks.append('normal IPv4 and IPv6 listeners retained')
assert ports(command(candidate,'',''))==['22'];checks.append('owner deliberately unspecified Interface retains existing behavior')
assert command(candidate,'lan','192.168.235.1',boot='1')==[];checks.append('existing boot skip and later interface trigger semantics retained')
cmd=command(candidate,'lan','',direct='lan');assert '-l' in cmd and 'br-lan' in cmd and ports(cmd)==['22'];checks.append('existing explicit device binding retained')
with tempfile.TemporaryDirectory(prefix='m83-fallback-ssh-') as temp:
    root=Path(temp);state=root/'state';key=root/'key';key.write_text('synthetic test key')
    source=(HERE/'ponwrt-recovery-ssh-m83').read_text()
    helpers2=helpers+'''ip() { printf '%s\\n' "$MOCK_IPS"; }
'''
    def fallback(marker,address,key_exists=True):
        state.write_text(marker)
        key.write_text('synthetic') if key_exists else key.unlink(missing_ok=True)
        setup=f"STATE='{state}'; KEY='{key}'; MOCK_IPS='{address}'\n"
        result=subprocess.run(['sh'],input=(helpers2+source+setup+'start_service\n').encode(),capture_output=True)
        assert result.returncode==0,result.stderr
        return [x.decode() for x in result.stdout.split(b'\0') if x]
    assert fallback('{"state":"configured"}','')==[];checks.append('fallback absent address never starts')
    assert fallback('{"state":"skipped_custom"}','inet 169.254.235.1/16')==[];checks.append('fallback unconfigured migration never starts')
    assert fallback('{"state":"configured"}','inet 169.254.235.1/16',False)==[];checks.append('fallback missing existing host key never starts')
    cmd=fallback('{"state":"configured"}','inet 169.254.235.1/16')
    assert ports(cmd)==['169.254.235.1:22'] and all(flag in cmd for flag in ('-s','-g','-j','-k','-r'))
    checks.append('fallback command uses literal link-local endpoint and existing key with password/forwarding disabled')
print(json.dumps({'passed':True,'checks':checks},indent=2))
