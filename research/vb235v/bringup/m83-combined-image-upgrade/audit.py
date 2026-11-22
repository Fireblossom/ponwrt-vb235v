#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Freeze and audit a built M83 candidate; no router or NAND access."""
import argparse,hashlib,importlib.util,json,os,re,shutil,stat,struct,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'tools'))
from fdt_board_inventory import parse
from inspect_vb235v_sysupgrade import inspect,image_data,kernel_bytes,text

def digest(data):return hashlib.sha256(data).hexdigest()
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def archive(data):
 files={};at=0
 while at<len(data):
  if data[at]==0:at+=1;continue
  assert data[at:at+6]==b'070701','Expected raw newc initramfs'
  fields=[int(data[at+6+i*8:at+14+i*8],16) for i in range(13)];at+=110
  mode,uid,gid,size,namesize=fields[1],fields[2],fields[3],fields[6],fields[11]
  name=data[at:at+namesize];assert name.endswith(b'\0');name=name[:-1].decode();at=(at+namesize+3)&~3
  blob=data[at:at+size];assert len(blob)==size;at=(at+size+3)&~3
  if name=='TRAILER!!!':continue
  name=name.removeprefix('./');assert not name.startswith('/') and '..' not in Path(name).parts
  if name in files:assert files[name]==(mode,blob),'Conflicting newc entry'
  files[name]=(mode,blob)
 return files
def symbol_offsets(readelf,elf):
 out=subprocess.check_output([str(readelf),'-sW',str(elf)],text=True)
 result={n:int(v,16) for v,n in re.findall(r'^\s*\d+:\s+([0-9a-fA-F]+)\s+\d+\s+\w+\s+\w+\s+\w+\s+\S+\s+(_text|__initramfs_start|__initramfs_size)\s*$',out,re.M)}
 assert len(result)==3;return {n:v-result['_text'] for n,v in result.items()}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('tree',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
 tree=a.tree.resolve();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
 lock=json.loads((HERE/'input-lock.json').read_text());subprocess.run(['python3',str(HERE/'prepare.py'),str(tree),'--check-only'],check=True,capture_output=True)
 kd=tree/'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v';kernel=kd/'linux-6.18.60'
 cross=tree/'staging_dir/toolchain-aarch64_cortex-a53_gcc-14.4.0_musl/bin/aarch64-openwrt-linux-musl-'
 config=(kernel/'.config').read_text()
 for key in ['SMP','ARM_VB235V_BOOT_VOLTAGE_CPUFREQ','CPU_FREQ_DEFAULT_GOV_PERFORMANCE','NET_AIROHA','NET_AIROHA_NPU','MTD_SPI_NAND','SPI_AIROHA_SNFI','INITRAMFS_COMPRESSION_NONE']:
  assert f'CONFIG_{key}=y\n' in config,'Missing builtin '+key
 assert '# CONFIG_ARM_AIROHA_SOC_CPUFREQ is not set\n' in config
 for path in ['drivers/cpufreq/vb235v-cpufreq.c','drivers/cpufreq/vb235v-cpufreq-contract.h']:
  assert (kernel/path).read_bytes()==(HERE.parent/'m81-cpu-integration'/Path(path).name).read_bytes()
 sources=module('m75audit',HERE.parent/'m75-en8811h-paged-status/verify_sources.py').verify_sources(tree)
 recovery=json.loads(subprocess.check_output(['python3',str(HERE.parent/'m79-wifi-recovery-v2/verify_sources.py'),str(kd/'mt76-2026.10.28~0936617d')],text=True))
 wifi=json.loads(subprocess.check_output(['python3',str(HERE.parent/'m82-wifi-acceleration/verify_default_off.py'),str(tree)],text=True))
 assert all(row['available'] for row in wifi['modules'].values()),'Wi-Fi modules absent from complete build'
 for elf in ['vmlinux.debug','vmlinux-initramfs.debug']:
  symbols=subprocess.check_output([str(cross)+'readelf','-sW',str(kd/elf)],text=True)
  assert 'vb235v_cpufreq_init' in symbols,'CPU driver absent from '+elf
 revision=lock['revision']+'\n';assert (tree/'files/etc/vb235v-system-revision').read_text()==revision
 target=tree/'bin/targets/airoha/vb235v';prefix='ponwrt-airoha-vb235v-tplink_vb235v'
 firmware=(target/(prefix+'-squashfs-sysupgrade.bin')).read_bytes();info=inspect(firmware)
 fit=firmware[:info['fit_bytes']];normal_nodes,_=parse(fit,max_bytes=16*1024*1024)
 normal_conf=normal_nodes['/configurations/'+text(normal_nodes['/configurations']['default'])]
 _,normal_dtb=image_data(normal_nodes,text(normal_conf['fdt']),'flat_dt')
 installer=(target/(prefix+'-initramfs-install.itb')).read_bytes();installer_nodes,_=parse(installer,max_bytes=56*1024*1024)
 conf=installer_nodes['/configurations/'+text(installer_nodes['/configurations']['default'])]
 assert conf.get('vb235v,ram-installer')==struct.pack('>I',1) and 'vb235v,firmware-image' not in conf
 assert normal_conf.get('vb235v,firmware-image')==struct.pack('>I',1)
 kp,compressed=image_data(installer_nodes,text(conf['kernel']),'kernel');_,dtb=image_data(installer_nodes,text(conf['fdt']),'flat_dt')
 raw,memory=kernel_bytes(compressed,text(kp['compression']));assert int.from_bytes(kp['load'],'big')==0x80200000 and 0x80200000+memory<0x84000000
 base_fit=HERE.parents[4]/'VB235v-PonWrt-Persistent-M75-v1/kernel.itb'
 # This path resolves outside the repository into the private workspace.
 base_nodes,_=parse(base_fit.read_bytes(),max_bytes=16*1024*1024)
 base_conf=base_nodes['/configurations/'+text(base_nodes['/configurations']['default'])]
 _,base_dtb=image_data(base_nodes,text(base_conf['fdt']),'flat_dt');base,_=parse(base_dtb)
 for candidate in [normal_dtb,dtb]:
  dt,_=parse(candidate);assert 'tplink,m78-boot-voltage-cpufreq' in dt['/']
  expected={k:v for k,v in base.items() if '/partitions/' in k or k.startswith('/reserved-memory')}
  assert {k:v for k,v in dt.items() if '/partitions/' in k or k.startswith('/reserved-memory')}==expected,'Protected partition/reservation DT changed'
  assert len([k for k in dt if re.fullmatch(r'/cpus/cpu@[01]',k)])==2
 assert b'rdinit=/init' in parse(dtb)[0]['/chosen']['bootargs']
 assert parse(normal_dtb)[0]['/chosen']==base['/chosen'],'Normal boot arguments changed'
 for forbidden in [b'ubi.mtd=',b'ubi.block=',b'rootfstype=',b'root=']:
  assert forbidden not in parse(dtb)[0]['/chosen']['bootargs'],'RAM installer automatic attachment argument'
 offsets=symbol_offsets(Path(str(cross)+'readelf'),kd/'vmlinux-initramfs.debug')
 n=struct.unpack_from('<Q',raw,offsets['__initramfs_size'])[0];assert 4096<n<len(raw)
 files=archive(raw[offsets['__initramfs_start']:offsets['__initramfs_start']+n]);assert 'init' in files
 # Extract the independently validated production SquashFS into a new private
 # output subdirectory; never mount it and never execute target contents.
 extract=out/'rootfs-inspected';attempt=1
 while extract.exists():attempt+=1;extract=out/('rootfs-inspected-r'+str(attempt))
 root=firmware[info['rootfs_offset']:info['rootfs_offset']+info['rootfs_bytes_used']]
 (out/'rootfs.squashfs').write_bytes(root)
 # Inspect all regular files and symlinks without privileged device creation
 # or xattr installation on the host. Device nodes remain in the audited cpio.
 subprocess.run([str(tree/'staging_dir/host/bin/unsquashfs4'),'-no-progress','-no-xattrs','-d',str(extract),'-excludes',str(out/'rootfs.squashfs'),'dev'],check=True,capture_output=True)
 expected_files={'etc/vb235v-system-revision':revision.encode(),
  'usr/libexec/ponwrt-management-m83':(HERE/'management.sh').read_bytes(),
  'etc/uci-defaults/99zz-ponwrt-management-m83':(HERE/'99zz-ponwrt-management-m83').read_bytes(),
  'etc/init.d/ponwrt-recovery-ssh-m83':(HERE/'ponwrt-recovery-ssh-m83').read_bytes(),
  'etc/config/ponwrt-dsl':(HERE.parent/'m77-dsl-runtime/ponwrt-dsl.config').read_bytes(),
  'etc/init.d/ponwrt-dsl':(HERE.parent/'m77-dsl-runtime/ponwrt-dsl.init').read_bytes(),
  'etc/init.d/dropbear':(tree/'package/network/services/dropbear/files/dropbear.init').read_bytes()}
 for name in ['cpu-observe.sh','cpu-cycle.sh']:
  expected_files['usr/libexec/vb235v-'+name.removesuffix('.sh')]=(HERE.parent/'m81-cpu-integration'/name).read_bytes()
 for name in ['www/index.html','www/assets/diagnostics.js','www/assets/diagnostics.css']:
  expected_files[name]=(HERE.parent/'m77-dsl-diagnostics'/name).read_bytes()
 for name,row in json.loads((HERE.parent/'m70-integrated-accel/private-inputs.json').read_text()).items():
  data=(tree/'files'/name).read_bytes();assert len(data)==row['bytes'] and digest(data)==row['sha256'];expected_files[name]=data
 for name,data in expected_files.items():
  assert (extract/name).read_bytes()==data,'Normal rootfs differs '+name
  assert files[name][1]==data,'Installer rootfs differs '+name
 for name in ['usr/libexec/rpcd/ponwrt.diagnostics','usr/sbin/ponwrt-setup','usr/sbin/ponwrt-dsl','usr/libexec/vb235v-cpu-smp-probe']:
  assert (extract/name).read_bytes().startswith(b'\x7fELF') and files[name][1].startswith(b'\x7fELF'),name
 assert b'[ "$(uci -q get ponwrt-dsl.main.enabled)" = 1 ] || return 0' in expected_files['etc/init.d/ponwrt-dsl'],'DSL init gate absent'
 for name in ['S95ponwrt-recovery-ssh-m83','K10ponwrt-recovery-ssh-m83']:
  path='etc/rc.d/'+name;assert os.readlink(extract/path)=='../init.d/ponwrt-recovery-ssh-m83'
  # Linux usr/gen_init_cpio includes a terminating NUL in symlink payloads.
  assert stat.S_ISLNK(files[path][0]) and files[path][1] in [b'../init.d/ponwrt-recovery-ssh-m83',b'../init.d/ponwrt-recovery-ssh-m83\0']
 artifacts={'sysupgrade.bin':firmware,'kernel.itb':fit,'installer.itb':installer,'rootfs.squashfs':root}
 for name in [prefix+'.manifest','config.buildinfo','version.buildinfo','profiles.json']:
  artifacts[name]=(target/name).read_bytes()
 artifacts['kernel.config']=(kernel/'.config').read_bytes();artifacts['build.config']=(tree/'.config').read_bytes()
 records={}
 for name,data in artifacts.items():
  (out/name).write_bytes(data);records[name]={'bytes':len(data),'sha256':digest(data)}
 result={'schema':1,'revision':lock['revision'],'artifact_sha256':records,'authored_input_lock':lock,
  'M75_protected_NAND_and_PHY_source_audit':sources,'M79_v2_source_audit':recovery,'M82_default_off_audit':wifi,
  'sysupgrade_format_audit':info,'installer':{'compressed_FIT_bytes':len(installer),'raw_kernel_bytes':len(raw),'kernel_memory_bytes':memory,'embedded_raw_newc_bytes':n,'root_entries':len(files)},
  'rootfs_expected_files_sha256':{name:digest(data) for name,data in expected_files.items()},
  'CPU':'M81 builtin, default performance, allow_transitions=N; hardware test pending',
  'wireless_NPU':'default off; software baseline and recovery qualified separately',
  'DSL':'packaged disabled; no physical DSL/PPP success claimed',
  'hardware_acceptance':{'installed':False,'written_volume_SHA_verified':False,'booted_revision_verified':False,'configuration_and_SSH_identity_preserved':False,'protected_full_readback_verified':False,'normal_and_rescue_paths_verified':False}}
 (out/'manifest.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'artifact_audit_passed':True,'revision':lock['revision'],'hardware_installed':False,'artifacts':records},indent=2))
if __name__=='__main__':main()
