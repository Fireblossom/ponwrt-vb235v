#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Independent archive/FIT checks for the offline RAM experiment."""
import argparse, hashlib, json, stat, struct, sys, zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'tools'))
from fdt_board_inventory import parse
from inspect_vb235v_sysupgrade import image_data,inspect,text

def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args()
    raw=(a.directory/'cpu-mini.itb').read_bytes();report=json.loads((a.directory/'manifest.json').read_text())
    assert hashlib.sha256(raw).hexdigest()==report['mini_fit_sha256']
    nodes,_=parse(raw,max_bytes=16*1024*1024);conf=nodes['/configurations/'+text(nodes['/configurations']['default'])]
    _,cp=image_data(nodes,text(conf['ramdisk']),'ramdisk')
    _,dtb=image_data(nodes,text(conf['fdt']),'flat_dt');dt,_=parse(dtb)
    assert b'rdinit=/init' in dt['/chosen']['bootargs']
    assert b'ubi.mtd=' not in dt['/chosen']['bootargs'] and b'rootfstype=' not in dt['/chosen']['bootargs']
    files={};at=0
    while True:
        assert cp[at:at+6]==b'070701'
        fields=[int(cp[at+6+i*8:at+14+i*8],16) for i in range(13)];at+=110
        ino,mode,uid,gid,nlink,mtime,size,devmajor,devminor,rmajor,rminor,namesize,check=fields
        name=cp[at:at+namesize];assert name.endswith(b'\0');name=name[:-1].decode();at=(at+namesize+3)&~3
        data=cp[at:at+size];assert len(data)==size;at=(at+size+3)&~3
        assert name not in files and not name.startswith('/') and '..' not in Path(name).parts
        assert uid==gid==mtime==check==0
        if name=='TRAILER!!!':break
        files[name]=(mode,data,rmajor,rminor)
    assert not any(cp[at:]) and len(cp)%512==0
    assert set(files)==set(report['files'])
    for name,(mode,data,_,_) in files.items():
        row=report['files'][name]
        assert row=={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'mode':oct(mode)}
        for parent in list(Path(name).parents)[:-1]:assert stat.S_ISDIR(files[parent.as_posix()][0])
        if stat.S_ISLNK(mode):
            target=Path(name).parent/data.decode();assert target.as_posix() in files,(name,target)
    assert files['dev/console']==(0o020600,b'',5,1)
    assert files['init'][1]==(HERE/'mini-init').read_bytes()
    assert hashlib.sha256(files['lib/modules/6.18.60/vb235v-cpufreq.ko'][1]).hexdigest()=='e55f925a7664966b5741efd1d4c70f3db411c27e58114ee73a3825c11122cc9e'
    # The production parser must reject the original mini and even a mini with
    # a syntactically valid, board-matching fwtool metadata trailer appended.
    reasons=[]
    meta=json.dumps({'metadata_version':'1.1','compat_version':'1.0','supported_devices':['tplink,vb235v']}).encode()
    body=raw+bytes(8)+meta
    framed=body+struct.pack('>IIB3sI',0x46577830,(~zlib.crc32(body))&0xffffffff,1,bytes(3),len(meta)+24)
    for candidate in (raw,framed):
        try:inspect(candidate)
        except ValueError as error:reasons.append(str(error))
        else:raise AssertionError('RAM-only mini admitted for sysupgrade')
    assert reasons==['Missing fwtool metadata','Ambiguous initramfs/firmware/loadables configuration'],reasons
    output={'FIT_and_cpio_integrity':True,'cpio_entries':len(files),'safe_bootargs':True,'CPU_module_exact':True,'sysupgrade_rejected':reasons,'hardware_booted':False}
    (a.directory/'host-checks.json').write_text(json.dumps(output,indent=2)+'\n');print(json.dumps(output,indent=2))
if __name__=='__main__':main()
