#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read-only inspector for FIT + 128-KiB padding + SquashFS + fwtool metadata.

This is an offline development tool. It does not authorize an installation,
verify a signing key, mount a filesystem or prove board driver compatibility.
"""
import argparse, hashlib, json, lzma, math, re, struct, zlib
from pathlib import Path
from fdt_board_inventory import parse

BOARD='tplink,vb235v'
MAX_IMAGE=0x3800000

def require(test,message):
    if not test:
        raise ValueError(message)

def envelope(data):
    require(25<=len(data)<=0x5000000,'Image length outside recovery upload bounds')
    cursor=len(data);meta=None;signature=None;layers=0
    while cursor>=16 and data[cursor-16:cursor-12]==b'FWx0':
        layers+=1;require(layers<=2,'Too many fwtool layers')
        magic,crc,kind,pad,size=struct.unpack('>IIB3sI',data[cursor-16:cursor])
        require(16<=size<=cursor and pad==bytes(3),'Invalid fwtool size/reserved bytes')
        require(crc==((~zlib.crc32(data[:cursor-16]))&0xffffffff),'fwtool CRC mismatch')
        start=cursor-size;n=size-16
        if kind==0:
            require(signature is None and meta is None and 0<n<=1024,'Invalid signature framing/order')
            signature=(start,n)
        elif kind==1:
            require(meta is None and 8<n<=8+30*1024,'Invalid metadata framing')
            require(data[start:start+8]==bytes(8),'Unsupported metadata version/flags')
            meta=(start+8,n-8)
        else:
            raise ValueError('Unsupported fwtool layer type')
        cursor=start
    require(meta is not None,'Missing fwtool metadata')
    return cursor,meta,signature

def json_object(pairs):
    result={}
    for key,value in pairs:
        require(key not in result,'Duplicate JSON key')
        result[key]=value
    return result

def metadata(data):
    def invalid_constant(value):raise ValueError('Non-JSON numeric constant')
    value=json.loads(data.decode('utf8'),object_pairs_hook=json_object,parse_constant=invalid_constant)
    require(type(value) is dict,'Metadata must be an object')
    require(value.get('metadata_version')=='1.1','Unsupported metadata schema')
    require(value.get('compat_version','1.0')=='1.0','Unsupported compatibility version')
    devices=value.get('supported_devices')
    require(type(devices) is list and 0<len(devices)<=64,'Missing/oversized supported_devices')
    require(all(type(x) is str and re.fullmatch(r'[A-Za-z0-9,._+-]{1,128}',x) for x in devices),'Invalid supported device identifier')
    require(len(set(devices))==len(devices) and BOARD in devices,'Wrong or duplicate supported board')
    return value

def text(value):
    require(type(value) is bytes and value.endswith(b'\0') and b'\0' not in value[:-1],'Invalid FIT string')
    return value[:-1].decode('ascii')

def number(value):
    require(type(value) is bytes and len(value) in [4,8],'Invalid FIT address')
    return int.from_bytes(value,'big')

def image_data(nodes,name,kind):
    path='/images/'+name;props=nodes.get(path)
    require(type(props) is dict,'Missing referenced FIT image')
    require('data' in props and not {'data-offset','data-position','data-size'}&props.keys(),'External FIT data is unsupported')
    require(text(props.get('type'))==kind and text(props.get('arch'))=='arm64','Wrong FIT image type/architecture')
    blob=props['data'];require(bool(blob),'Empty FIT image data')
    hashes=[p for p in nodes if p.startswith(path+'/') and '/' not in p[len(path)+1:]]
    require(0<len(hashes)<=4,'Missing/oversized FIT hash list')
    for child in hashes:
        require(child.rsplit('/',1)[1].startswith('hash'),'Unsupported FIT image child/signature')
        require(text(nodes[child].get('algo'))=='sha256','Non-SHA256 FIT hash')
        require(nodes[child].get('value')==hashlib.sha256(blob).digest(),'FIT image hash mismatch')
    return props,blob

def kernel_bytes(blob,compression):
    limit=64*1024*1024
    if compression=='none':result=blob
    elif compression=='lzma':
        dec=lzma.LZMADecompressor(format=lzma.FORMAT_ALONE,memlimit=64*1024*1024)
        result=dec.decompress(blob,max_length=limit+1)
        require(dec.eof and not dec.unused_data,'Incomplete/trailing/oversized LZMA stream')
    elif compression=='gzip':
        dec=zlib.decompressobj(31);result=dec.decompress(blob,limit+1)
        require(dec.eof and not dec.unused_data and not dec.unconsumed_tail,'Incomplete/trailing/oversized gzip stream')
    else:raise ValueError('Unsupported kernel compression')
    require(64<=len(result)<=limit and result[56:60]==b'ARMd','Not a bounded ARM64 Linux Image')
    memory_bytes=struct.unpack_from('<Q',result,16)[0] or len(result)
    require(64<=memory_bytes<=128*1024*1024,'Invalid ARM64 Image memory size')
    return result,memory_bytes

def inspect(data,expected_sha256=None):
    require(len(data)<=MAX_IMAGE,'Complete firmware exceeds the hybrid firmware budget')
    sha=hashlib.sha256(data).hexdigest()
    if expected_sha256 is not None:
        require(bool(re.fullmatch('[0-9a-fA-F]{64}',expected_sha256)) and sha==expected_sha256.lower(),'Whole-image SHA256 mismatch')
    payload_end,(meta_at,meta_len),signature=envelope(data)
    meta=metadata(data[meta_at:meta_at+meta_len])
    require(payload_end>=40 and data[:4]==b'\xd0\x0d\xfe\xed','Payload is not a FIT')
    fit_size=struct.unpack_from('>I',data,4)[0]
    require(40<=fit_size<=payload_end,'FIT length outside payload')
    fit=data[:fit_size];nodes,_=parse(fit,max_bytes=MAX_IMAGE)
    confs=nodes.get('/configurations');require(type(confs) is dict,'Missing FIT configurations')
    config_name=text(confs.get('default'));conf_path='/configurations/'+config_name
    config=nodes.get(conf_path);require(type(config) is dict,'Missing default FIT configuration')
    require(not any('vb235v,recovery-core' in n for n in nodes.values()),'Recovery U-Boot is not a PonWrt sysupgrade kernel')
    require(not {'ramdisk','loadables','firmware'}&config.keys(),'Ambiguous initramfs/firmware/loadables configuration')
    configurations=[p for p in nodes if p.startswith('/configurations/') and '/' not in p[len('/configurations/'):]]
    require(configurations==[conf_path],'Multiple FIT configurations are not admitted by this inspector')
    kname=text(config.get('kernel'));dname=text(config.get('fdt'));require(kname!=dname,'Overlapping kernel/FDT roles')
    images=[p for p in nodes if p.startswith('/images/') and '/' not in p[len('/images/'):]]
    require(set(images)=={'/images/'+kname,'/images/'+dname},'Unexpected FIT images')
    kp,kblob=image_data(nodes,kname,'kernel');dp,dtb=image_data(nodes,dname,'flat_dt')
    require(text(kp.get('os'))=='linux' and text(dp.get('compression'))=='none','Unsupported kernel OS/FDT compression')
    kernel,memory_bytes=kernel_bytes(kblob,text(kp.get('compression')))
    load=number(kp.get('load'));entry=number(kp['entry']) if 'entry' in kp else load
    require(0x80050000<=load<0x9f000000 and load+memory_bytes<=0x9f000000 and load<=entry<load+memory_bytes,'Kernel load/entry violates the bounded RAM window')
    dt,_=parse(dtb);compatible=dt.get('/',{}).get('compatible',b'')
    require(compatible.endswith(b'\0') and BOARD.encode() in compatible[:-1].split(b'\0'),'Wrong DTB board compatibility')
    root_at=(fit_size+0x1ffff)&~0x1ffff
    require(root_at+96<=payload_end,'Missing aligned rootfs')
    require(all(x in [0,255] for x in data[fit_size:root_at]),'Unexpected bytes between FIT and rootfs')
    sb=data[root_at:root_at+96]
    magic,inodes,time,block,fragments,compression,block_log,flags,ids,major,minor=struct.unpack_from('<5I6H',sb)
    require(magic==0x73717368 and (major,minor)==(4,0),'Missing/unsupported SquashFS superblock')
    require(inodes>0 and 4096<=block<=1048576 and block&(block-1)==0 and block_log==block.bit_length()-1,'Invalid SquashFS block geometry')
    require(compression==4,'This candidate accepts XZ SquashFS only')
    used=struct.unpack_from('<Q',sb,40)[0]
    require(96<=used<=payload_end-root_at,'SquashFS size outside image')
    for offset in [48,56,64,72,80,88]:
        address=struct.unpack_from('<Q',sb,offset)[0]
        require(address==0xffffffffffffffff and offset in [56,80,88] or 96<=address<used,'SquashFS table outside filesystem')
    require(payload_end-(root_at+used)<=0x40004,'Excessive rootfs tail padding')
    return {'format':'FIT + 128KiB-aligned XZ SquashFS + fwtool metadata','board':BOARD,
      'whole_image_SHA256':sha,'expected_SHA256_checked':expected_sha256 is not None,'image_bytes':len(data),
      'fit_bytes':fit_size,'fit_SHA256':hashlib.sha256(fit).hexdigest(),'kernel_data_SHA256_verified':True,
      'kernel_uncompressed_bytes':len(kernel),'kernel_load':load,'kernel_entry':entry,
      'DTB_SHA256_verified':True,'rootfs_offset':root_at,'rootfs_bytes_used':used,'rootfs_compression':'xz',
      'rootfs_SHA256':hashlib.sha256(data[root_at:root_at+used]).hexdigest(),'rootfs_tail_padding_bytes':payload_end-root_at-used,
      'metadata_schema':meta['metadata_version'],'metadata_board_matches':True,'fwtool_CRC_verified':True,
      'signature_present':signature is not None,'signature_cryptographically_verified':False,
      'upgrade_authorized':False,'filesystem_mounted_or_verified':False,'hardware_compatibility_proven':False,
      'NAND_operations':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('image',type=Path)
    p.add_argument('--expected-sha256');p.add_argument('--output',type=Path);a=p.parse_args()
    require(a.image.stat().st_size<=MAX_IMAGE,'Image too large')
    report=inspect(a.image.read_bytes(),a.expected_sha256);result=json.dumps(report,indent=2)
    if a.output:a.output.write_text(result+'\n')
    print(result)
