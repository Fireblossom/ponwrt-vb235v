#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Real UCI CLI migration tests in disposable Linux roots; never device IO."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

p=argparse.ArgumentParser();p.add_argument('--uci',type=Path,required=True);a=p.parse_args()
HERE=Path(__file__).resolve().parent
NETWORK="""config interface 'loopback'
 option device 'lo'
 option proto 'static'
 option ipaddr '127.0.0.1/8'
config interface 'lan'
 option device 'lan-test'
 option proto 'static'
 option ipaddr '192.168.235.1'
 option netmask '255.255.255.0'
config globals 'globals'
 option ula_prefix 'fd00:1234::/48'
"""
DHCP="""config dhcp 'lan'
 option interface 'lan'
 option start '2'
 option limit '1'
 option leasetime '1h'
 list dhcp_option '3'
 list dhcp_option '6'
"""
FIREWALL="""config zone
 option name 'lan'
 option input 'ACCEPT'
 list network 'lan'
config zone
 option name 'wan'
 option input 'REJECT'
 list network 'wan'
"""
HTTP="""config uhttpd 'main'
 option home '/www'
 option ubus_prefix '/ubus'
 option cert '/etc/uhttpd.crt'
 option key '/etc/uhttpd.key'
 list listen_http '192.168.235.1:80'
"""
SSH="""config dropbear 'main'
 option Interface 'lan'
 option PasswordAuth 'off'
 option RootPasswordAuth 'off'
"""
checks=[]
with tempfile.TemporaryDirectory(prefix='m83-management-test-') as temp:
    base=Path(temp)
    def fixture(label):
        root=base/label;(root/'etc/config').mkdir(parents=True);(root/'tmp').mkdir()
        for name,data in [('network',NETWORK),('dhcp',DHCP),('firewall',FIREWALL),('uhttpd',HTTP),('dropbear',SSH)]:
            (root/'etc/config'/name).write_text(data)
        return root
    def uci(root,*args):return subprocess.check_output([str(a.uci),'-q','-c',str(root/'etc/config'),'-t',str(root/'tmp/delta'),*args],text=True).strip()
    def run(root,apply=False):
        env=dict(os.environ,PONWRT_M83_TEST_ROOT=str(root),PONWRT_M83_TEST_UCI=str(a.uci))
        result=subprocess.run(['sh',str(HERE/'management.sh'),'--apply' if apply else '--check'],env=env,capture_output=True,text=True)
        assert result.returncode==0,(result.stdout,result.stderr)
        return json.loads(result.stdout)
    def data(root):return {n:(root/'etc/config'/n).read_bytes() for n in ('network','dhcp','firewall','uhttpd','dropbear')}
    root=fixture('normal');original=data(root)
    assert run(root)['state']=='ready' and data(root)==original;checks.append('check mode does not write configuration')
    assert run(root,True)['state']=='configured'
    assert uci(root,'get','network.lan.device')=='br-lan'
    assert uci(root,'get','network.ponwrt_lan_bridge.ports')=='lan-test eth2'
    assert 'eth1' not in uci(root,'show','network')
    assert uci(root,'get','network.ponwrt_recovery.ipaddr')=='169.254.235.1'
    assert uci(root,'get','uhttpd.main.listen_https')=='192.168.235.1:443 169.254.235.1:443'
    assert uci(root,'get','uhttpd.main.redirect_https')=='1'
    assert uci(root,'get','dropbear.main.Interface')=='lan'
    assert all((root/'etc/config'/n).read_bytes()==original[n] for n in ('dhcp','firewall','dropbear'))
    checks.append('default migration bridges two intended ports, adds fallback/TLS, preserves DHCP and firewall')
    once=data(root);again=run(root,True);assert again['state']=='configured' and data(root)==once,(again,data(root)==once);checks.append('second application is byte-idempotent')
    cases=[('custom-ip','network',"option ipaddr '192.168.235.1'","option ipaddr '192.168.7.1'"),
           ('custom-gateway','network',"option device 'lan-test'","option device 'lan-test'\n option gateway '192.168.235.254'"),
           ('custom-lan-device','network',"option device 'lan-test'","option device 'eth1'"),
           ('eth2-wan','network',NETWORK,NETWORK+"config interface 'wan'\n option device 'eth2'\n option proto 'dhcp'\n"),
           ('existing-bridge','network',NETWORK,NETWORK+"config device\n option name 'br-lan'\n option type 'bridge'\n"),
           ('fallback-conflict','network',NETWORK,NETWORK+"config interface 'ponwrt_recovery'\n option proto 'dhcp'\n"),
           ('gateway-option','dhcp',"list dhcp_option '3'","list dhcp_option '3,192.168.235.1'"),
           ('dns-option','dhcp',"list dhcp_option '6'","list dhcp_option '6,192.168.235.1'"),
           ('large-pool','dhcp',"option limit '1'","option limit '100'"),
           ('custom-firewall','firewall',"option input 'ACCEPT'","option input 'REJECT'"),
           ('public-listener','uhttpd',"192.168.235.1:80","0.0.0.0:80"),
           ('custom-https','uhttpd',HTTP,HTTP+" list listen_https '0.0.0.0:443'\n"),
           ('custom-key','uhttpd',"option key '/etc/uhttpd.key'","option key '/etc/owner.key'"),
           ('disabled-auth','uhttpd',HTTP,HTTP+" option no_ubusauth '1'\n"),
           ('cors','uhttpd',HTTP,HTTP+" option ubus_cors '1'\n")]
    for label,name,old,new in cases:
        root=fixture(label);path=root/'etc/config'/name;path.write_text(path.read_text().replace(old,new));before=data(root)
        assert run(root,True)['state']=='skipped_custom',label
        assert data(root)==before,label
        checks.append('preserves '+label)
    root=fixture('development-listener');path=root/'etc/config/uhttpd';path.write_text(HTTP+" list listen_http '169.254.211.1:80'\n list listen_https '192.168.235.1:443'\n list listen_https '169.254.211.1:443'\n")
    assert run(root,True)['state']=='configured';assert '169.254.211.1' not in uci(root,'show','uhttpd');checks.append('known temporary link-local listener becomes persistent fallback')
    root=fixture('staged-owner-change');(root/'tmp/.uci').mkdir();(root/'tmp/.uci/network').write_text('owner edit\n');before=data(root)
    assert run(root,True)['state']=='skipped_custom' and data(root)==before;checks.append('uncommitted UCI edits block migration')
    # Reproduce real defaults ordering using exact M77 and M73 scripts in a
    # root-local command wrapper, then run M83 last. No system /sbin/uci used.
    root=fixture('fresh-order');wrappers=root/'bin';wrappers.mkdir()
    wrapper=wrappers/'uci';wrapper.write_text(f'#!/bin/sh\nexec "{a.uci}" -c "{root}/etc/config" -t "{root}/tmp/delta" "$@"\n');wrapper.chmod(0o755)
    env=dict(os.environ,PATH=str(wrappers)+':'+os.environ['PATH'])
    d77=(HERE.parent/'m77-dsl-diagnostics/overlay/etc/uci-defaults/99-ponwrt-diagnostics').read_text()
    # Remove only backup-list bookkeeping, which is outside this ordering case.
    d77=d77[:d77.index('for path in ')]+'exit 0\n'
    subprocess.run(['sh'],input=d77,env=env,text=True,check=True)
    assert '192.168.235.1:443' in uci(root,'get','uhttpd.main.listen_https')
    d73=(HERE.parent/'m73-persistent-system/99-vb235v-persistent').read_text();batch=d73.split("<<'EOF'\n",1)[1].split('\nEOF',1)[0]
    subprocess.run([str(a.uci),'-q','-c',str(root/'etc/config'),'-t',str(root/'tmp/delta'),'batch'],input=batch,text=True,check=True)
    assert subprocess.run([str(a.uci),'-q','-c',str(root/'etc/config'),'get','uhttpd.main.listen_https'],capture_output=True).returncode!=0
    assert run(root,True)['state']=='configured' and '192.168.235.1:443' in uci(root,'get','uhttpd.main.listen_https')
    checks.append('fresh M77 then M73 ordering reproduces lost HTTPS; M83 last restores it')
print(json.dumps({'passed':True,'real_uci_checks':checks},indent=2))
