#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build a CPU test RAM FIT from a frozen normal kernel and minimal RAM root.

Offline only: no device, shared build-tree mutation, UART or flash command.
The result deliberately has a ramdisk and is not accepted by sysupgrade.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'tools'))
from fdt_board_inventory import parse
from inspect_vb235v_sysupgrade import image_data,kernel_bytes,text,number

BOOTARGS='console=ttyS0,115200n8 earlycon=uart8250,mmio32,0x1fbf0000,115200n8 rdinit=/init cpufreq.default_governor=performance loglevel=7 panic=0'
M75_FIT_SHA='3c1528eeb4cb4ea2e8494d39a61873cf6ed605445dd803e1a138118b632e42cc'
CPU_OPTIN='tplink,m78-boot-voltage-cpufreq'
def sha(data):return hashlib.sha256(data).hexdigest()
def patch_bootargs(data,add_cpu_optin=False):
    h=list(struct.unpack_from('>10I',data));_,total,off,strings,_,_,_,_,ssize,tsize=h
    assert total==len(data) and off+tsize<=strings and strings+ssize<=total
    table=data[strings:strings+ssize];out=bytearray();at=off;stack=[];changed=0;optin_name=len(table)
    if add_cpu_optin:table+=CPU_OPTIN.encode()+b'\0'
    while at<off+tsize:
        start=at;token=struct.unpack_from('>I',data,at)[0];at+=4
        if token==1:
            end=data.index(0,at);name=data[at:end].decode();at=(end+4)&~3;stack.append(name)
            if len(stack)==1 and add_cpu_optin:
                out+=data[start:at]+struct.pack('>III',3,0,optin_name);continue
        elif token==2:stack.pop()
        elif token==3:
            length,nameoff=struct.unpack_from('>II',data,at);at+=8
            end=table.index(0,nameoff);name=table[nameoff:end].decode();value=data[at:at+length];at=(at+length+3)&~3
            if '/'.join(stack)=='/chosen' and name=='bootargs':
                value=BOOTARGS.encode()+b'\0';out+=struct.pack('>III',3,len(value),nameoff)+value
                out+=b'\0'*((-len(out))&3);changed+=1;continue
        elif token==4:pass
        elif token==9:
            out+=data[start:at];break
        else:raise ValueError('Invalid FDT token')
        out+=data[start:at]
    assert changed==1
    h[3]=off+len(out);h[9]=len(out);h[1]=h[3]+len(table);h[8]=len(table)
    result=bytearray(data[:off]+out+table);struct.pack_into('>10I',result,0,*h)
    before,_=parse(data);after,_=parse(bytes(result))
    assert set(before)==set(after)
    for key in before:
        expected=dict(before[key])
        if key=='/chosen':expected['bootargs']=BOOTARGS.encode()+b'\0'
        if key=='/' and add_cpu_optin:
            assert CPU_OPTIN not in expected
            expected[CPU_OPTIN]=b''
        assert after[key]==expected,'Unexpected DT mutation '+key
    return bytes(result)

def property_offsets(data):
    h=struct.unpack_from('>10I',data);at=h[2];end=at+h[9];table=data[h[3]:h[3]+h[8]];stack=[];result={}
    while at<end:
        token=struct.unpack_from('>I',data,at)[0];at+=4
        if token==1:
            n=data.index(0,at);stack.append(data[at:n].decode());at=(n+4)&~3
        elif token==2:stack.pop()
        elif token==3:
            length,nameoff=struct.unpack_from('>II',data,at);at+=8
            name=table[nameoff:table.index(0,nameoff)].decode();result[('/'.join(stack),name)]=(at,length);at=(at+length+3)&~3
        elif token==4:pass
        elif token==9:break
        else:raise ValueError('Invalid FIT token')
    return result

def memory_audit(dtb,fit,memory):
    nodes,_=parse(dtb);reserved=[]
    address_cells=int.from_bytes(nodes['/reserved-memory']['#address-cells'],'big')
    size_cells=int.from_bytes(nodes['/reserved-memory']['#size-cells'],'big')
    assert (address_cells,size_cells)==(2,2)
    for name,props in nodes.items():
        if name.startswith('/reserved-memory/') and 'reg' in props:
            reg=props['reg'];assert len(reg)%16==0
            for at in range(0,len(reg),16):
                start,size=struct.unpack_from('>QQ',reg,at);assert size>0
                reserved.append({'name':name,'start':start,'end':start+size})
    regions=[{'name':'kernel maximum decompressed memory','start':0x80200000,'end':0x80200000+memory},
             {'name':'FIT upload cache','start':0x90000000,'end':0x90000000+len(fit)},
             {'name':'one-shot recovery handoff page','start':0x97ff0000,'end':0x97ff1000}]
    def disjoint(a,b):return a['end']<=b['start'] or b['end']<=a['start']
    for i,region in enumerate(regions):
        assert 0x80000000<=region['start']<region['end']<=0xa0000000
        assert all(disjoint(region,other) for other in regions[i+1:])
        assert all(disjoint(region,other) for other in reserved),'RAM candidate overlaps a DT reservation'
    offsets=property_offsets(fit)
    location={}
    for kind in ('kernel','fdt','ramdisk'):
        at,size=offsets[('/images/'+kind,'data')]
        location[kind]={'start':0x90000000+at,'end':0x90000000+at+size,'bytes':size}
        assert location[kind]['end']<=regions[1]['end']
    return {'regions':regions,'DT_reserved_memory':reserved,'FIT_inline_payloads':location,
            'static_known_regions_disjoint':True,
            'LMB_relocation_hardware_observed':False,
            'boot_gate':'Capture bdinfo/LMB and staged bootm initrd/FDT relocation bounds before final go; refuse any overlap with kernel, DT reservations, recovery handoff page or resident U-Boot.'}

def cpio(entries):
    out=bytearray();ino=1
    ordered=sorted(entries.items(),key=lambda row:(not stat.S_ISDIR(row[1][0]),len(Path(row[0]).parts),row[0]))
    for name,(mode,payload,major,minor) in [*ordered,('TRAILER!!!',(0,b'',0,0))]:
        encoded=name.encode()+b'\0'
        fields=[ino,mode,0,0,1,0,len(payload),0,0,major,minor,len(encoded),0]
        out+=b'070701'+''.join(f'{v:08x}' for v in fields).encode()+encoded
        out+=b'\0'*((-len(out))&3);out+=payload;out+=b'\0'*((-len(out))&3);ino+=1
    out+=b'\0'*((-len(out))&511);return bytes(out)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--normal-fit',type=Path,required=True)
    p.add_argument('--sha256',required=True)
    p.add_argument('--rootfs',type=Path,required=True)
    p.add_argument('--private-overlay',type=Path,required=True)
    p.add_argument('--cpu-tools',type=Path,required=True)
    p.add_argument('--readelf',type=Path,required=True)
    p.add_argument('--strip',type=Path,required=True)
    p.add_argument('--normal-elf',type=Path,required=True)
    p.add_argument('--m75-module-experiment',action='store_true')
    p.add_argument('--cpu-module',type=Path)
    p.add_argument('--cpu-module-sha256')
    p.add_argument('--mkimage',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();raw=a.normal_fit.read_bytes();assert sha(raw)==a.sha256
    nodes,_=parse(raw,max_bytes=56*1024*1024)
    config=nodes['/configurations/'+text(nodes['/configurations']['default'])]
    assert not {'ramdisk','loadables','firmware'}&config.keys()
    kp,kernel=image_data(nodes,text(config['kernel']),'kernel');_,dtb=image_data(nodes,text(config['fdt']),'flat_dt')
    assert text(kp['compression'])=='lzma' and number(kp['load'])==number(kp['entry'])==0x80200000
    image,memory=kernel_bytes(kernel,'lzma');assert 0x80200000+memory<=0x84000000
    symbols=subprocess.check_output([str(a.readelf),'-sW',str(a.normal_elf)],text=True)
    names={name:int(value,16) for value,name in re.findall(r'^\s*\d+:\s+([a-fA-F0-9]+)\s+\d+\s+\w+\s+\w+\s+\w+\s+\S+\s+(_text|__initramfs_size)\s*$',symbols,re.M)}
    assert set(names)=={'_text','__initramfs_size'}
    size_offset=names['__initramfs_size']-names['_text'];assert 0<=size_offset<=len(image)-8
    assert struct.unpack_from('<Q',image,size_offset)[0]<=4096,'Normal kernel already embeds a populated root'
    dt,_=parse(dtb);assert b'tplink,vb235v\0' in dt['/']['compatible']
    if a.m75_module_experiment:
        assert sha(raw)==M75_FIT_SHA and CPU_OPTIN not in dt['/']
        assert a.cpu_module and a.cpu_module_sha256 and sha(a.cpu_module.read_bytes())==a.cpu_module_sha256
    else:
        assert CPU_OPTIN in dt['/'],'CPU policy opt-in absent'
        assert not a.cpu_module and not a.cpu_module_sha256
    entries={};manifest={}
    def add(name,data,mode=0o100644):
        assert not name.startswith('/') and '..' not in Path(name).parts
        if name in entries:
            assert entries[name]==(mode,data,0,0),'Different duplicate root path '+name
            return
        for parent in list(Path(name).parents)[:-1]:entries.setdefault(parent.as_posix(),(0o040755,b'',0,0))
        entries[name]=(mode,data,0,0);manifest[name]={'bytes':len(data),'sha256':sha(data),'mode':oct(mode)}
    def root_resolve(name):
        base=a.rootfs.resolve();path=base/name
        if not path.exists() and not path.is_symlink():base=a.private_overlay.resolve();path=base/name
        for _ in range(40):
            assert path.is_relative_to(base),'Rootfs symlink escapes root'
            if not path.is_symlink():assert path.is_file(),str(path);return path
            target=Path(os.readlink(path))
            path=Path(os.path.normpath(str(base/str(target).lstrip('/') if target.is_absolute() else path.parent/target)))
        raise ValueError('Rootfs symlink loop')
    def from_root(name):
        resolved=root_resolve(name)
        add(name,resolved.read_bytes(),0o100755 if resolved.stat().st_mode&0o111 else 0o100644)
        return resolved
    busybox=from_root('bin/busybox')
    def dependencies(binary):
        dynamic=subprocess.check_output([str(a.readelf),'-d',str(binary)],text=True)
        program=subprocess.check_output([str(a.readelf),'-l',str(binary)],text=True)
        interpreter=re.search(r'Requesting program interpreter: ([^\]]+)',program)
        if interpreter:
            loader=interpreter[1].lstrip('/');from_root(loader)
        for name in re.findall(r'\(NEEDED\).*\[([^\]]+)\]',dynamic):
            if name=='libc.so' and interpreter:
                entries['lib/libc.so']=(0o120777,Path(loader).name.encode(),0,0)
            else:
                candidates=[str(Path(base)/name) for base in ('lib','usr/lib') if (a.rootfs/base/name).exists() or (a.rootfs/base/name).is_symlink()]
                assert len(candidates)==1,'Unresolved/ambiguous dynamic dependency '+name
                if candidates[0] not in entries:
                    child=from_root(candidates[0]);dependencies(child)
    dependencies(busybox)
    for applet in ('sh','mount','cat','ls','dmesg','insmod','rmmod','ip','ping','sha256sum','timeout','uname','xargs','cut','date','grep','id','mkdir','rmdir','sync','sleep'):
        candidates=[Path(base)/applet for base in ('bin','sbin','usr/bin','usr/sbin') if (a.rootfs/base/applet).exists() or (a.rootfs/base/applet).is_symlink()]
        if not candidates and applet in ('insmod','rmmod'):candidates=[Path('sbin/kmodloader')]
        assert candidates,'Applet/tool absent from same rootfs: '+applet
        path=root_resolve(candidates[0])
        if path==busybox:
            entries['bin/'+applet]=(0o120777,b'busybox',0,0)
        else:
            add('bin/'+applet,path.read_bytes(),0o100755);dependencies(path)
    add('init',(HERE/'mini-init').read_bytes(),0o100755)
    for directory in ('proc','sys','dev','tmp','run'):entries.setdefault(directory,(0o040755,b'',0,0))
    entries['dev/console']=(0o020600,b'',5,1)
    for name in ('vb235v-cpu-observe','vb235v-cpu-cycle','vb235v-cpu-smp-probe'):
        path=a.cpu_tools/name;assert path.is_file();add('usr/libexec/'+name,path.read_bytes(),0o100755)
    if a.cpu_module:
        module=a.cpu_module.read_bytes();assert b'vermagic=6.18.60 SMP mod_unload aarch64' in module
        add('lib/modules/6.18.60/vb235v-cpufreq.ko',module)
        if path.read_bytes().startswith(b'\x7fELF'):dependencies(path)
    for name in ('lib/firmware/vb235v/stock-npu-rv32.bin','lib/firmware/vb235v/stock-npu-data.bin','lib/modules/6.18.60/air_en8811h.ko'):
        from_root(name)
    for name,row in json.loads((HERE.parent/'m70-integrated-accel/private-inputs.json').read_text()).items():
        if name in entries:assert len(entries[name][1])==row['bytes'] and sha(entries[name][1])==row['sha256'],'Private NPU firmware differs'
    phy=entries['lib/modules/6.18.60/air_en8811h.ko'][1]
    # The exact M75 staged module predates MODULE_FIRMWARE metadata. Its
    # request_firmware_direct path literals are still present and are audited.
    firmware=[field for field in phy.split(b'\0') if field.startswith(b'airoha/EthMD32.')]
    assert set(firmware)=={b'airoha/EthMD32.dm.bin',b'airoha/EthMD32.DSP.bin'}
    for name in firmware:from_root('lib/firmware/'+name.decode())
    assert not any('mt799' in name or name.endswith('/sysupgrade') for name in entries)
    # Staging ELF files contain megabytes of debug data. Remove only debug
    # sections in private copies; preserve the exact experimental CPU/PHY ko.
    derivatives={}
    with tempfile.TemporaryDirectory(prefix='m83-mini-strip-') as temporary:
        for name,(mode,data,major,minor) in list(entries.items()):
            if not data.startswith(b'\x7fELF') or name.endswith('.ko'):continue
            path=Path(temporary)/'elf';path.write_bytes(data)
            subprocess.run([str(a.strip),'--strip-debug',str(path)],check=True,capture_output=True)
            stripped=path.read_bytes();assert stripped.startswith(b'\x7fELF') and len(stripped)<=len(data)
            derivatives[name]={'input_bytes':len(data),'input_sha256':sha(data),'output_bytes':len(stripped),'output_sha256':sha(stripped),'operation':'strip-debug only'}
            entries[name]=(mode,stripped,major,minor)
    # Recompute after dependency symlink replacement and isolated stripping.
    manifest={name:{'bytes':len(data),'sha256':sha(data),'mode':oct(mode)} for name,(mode,data,_,_) in entries.items()}
    ramdisk=cpio(entries);a.output.mkdir(parents=True,exist_ok=False)
    mini_dtb=patch_bootargs(dtb,a.m75_module_experiment)
    (a.output/'kernel.lzma').write_bytes(kernel);(a.output/'board.dtb').write_bytes(mini_dtb);(a.output/'root.cpio').write_bytes(ramdisk)
    its='''/dts-v1/;
/ { description = "VB235v CPU-only RAM test; not a sysupgrade image"; #address-cells = <1>;
 images {
  kernel { data = /incbin/("kernel.lzma"); type = "kernel"; arch = "arm64"; os = "linux"; compression = "lzma"; load = <0x80200000>; entry = <0x80200000>; hash-1 { algo = "sha256"; }; };
  fdt { data = /incbin/("board.dtb"); type = "flat_dt"; arch = "arm64"; compression = "none"; hash-1 { algo = "sha256"; }; };
  ramdisk { data = /incbin/("root.cpio"); type = "ramdisk"; arch = "arm64"; os = "linux"; compression = "none"; hash-1 { algo = "sha256"; }; };
 };
 configurations { default = "cpu-mini"; cpu-mini { kernel = "kernel"; fdt = "fdt"; ramdisk = "ramdisk"; }; };
};
'''
    (a.output/'mini.its').write_text(its)
    subprocess.run([str(a.mkimage),'-f','mini.its','cpu-mini.itb'],cwd=a.output,check=True,capture_output=True)
    fit=(a.output/'cpu-mini.itb').read_bytes();assert len(fit)<16*1024*1024
    result={'schema':1,'purpose':'CPU-only RAM test; never pass to sysupgrade','normal_fit_sha256':sha(raw),'normal_kernel_payload_bytes':len(kernel),'decompressed_kernel_bytes':len(image),'kernel_memory_bytes':memory,'ramdisk_bytes':len(ramdisk),'mini_fit_bytes':len(fit),'mini_fit_sha256':sha(fit),'serial_115200_8N1_minimum_seconds':len(fit)*10/115200,'upload_address':'0x90000000','kernel_load_address':'0x80200000','hardware_booted':False,'DT_changes':['chosen.bootargs']+(['root.M78_cpu_optin'] if a.m75_module_experiment else []),'experimental_M75_kernel_plus_M81_module':a.m75_module_experiment,'memory_audit':memory_audit(mini_dtb,fit,memory),'files':manifest}
    result['isolated_ELF_derivatives']=derivatives
    (a.output/'manifest.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('mini_fit_bytes','mini_fit_sha256','serial_115200_8N1_minimum_seconds','hardware_booted')},indent=2))
if __name__=='__main__':main()
