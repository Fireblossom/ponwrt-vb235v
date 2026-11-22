#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Derive the small exact-input fail-closed listener patch, offline only."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path

def patched(data):
    old='\tlocal iface ndev ipaddrs\n'
    new=old+'\tlocal address_binding_requested=0\n\t[ -n "${Interface}" ] && address_binding_requested=1\n'
    assert data.count(old)==1
    data=data.replace(old,new,1)
    old='\tlocal pid_file="/var/run/${NAME}.${1}.pid"\n'
    new='''\t# An explicitly configured address interface must never fall back to
\t# a wildcard listener while it is down or has no suitable addresses.
\tif [ "$address_binding_requested" = 1 ] && [ -z "$iface" ] && [ -z "$ipaddrs" ]; then
\t\tlogger -t "${NAME}" -p daemon.notice "Configured interface has no address; skipping listener"
\t\treturn 0
\tfi

'''+old
    assert data.count(old)==1
    return data.replace(old,new,1)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();before=a.source.read_text();after=patched(before)
    a.output.mkdir(parents=True,exist_ok=True)
    patch=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/package/network/services/dropbear/files/dropbear.init',tofile='b/package/network/services/dropbear/files/dropbear.init'))
    (a.output/'dropbear-explicit-interface.patch').write_bytes(patch.encode())
    report={'path':'package/network/services/dropbear/files/dropbear.init','baseline':hashlib.sha256(before.encode()).hexdigest(),'candidate':hashlib.sha256(after.encode()).hexdigest(),'policy':'Explicit nonempty Interface without addresses skips listener; unspecified Interface and DirectInterface behavior unchanged.'}
    (a.output/'dropbear-hashes.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
    print(json.dumps(report,indent=2))
