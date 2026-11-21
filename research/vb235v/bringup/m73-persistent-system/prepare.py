#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Prepare the guarded persistent development profile after M72 source audit."""
import argparse,hashlib,importlib.util,json,re,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent

def install(source,target,executable=False):
 data=source.read_bytes();target.parent.mkdir(parents=True,exist_ok=True)
 if target.exists():assert target.read_bytes()==data,'Different existing file: '+str(target)
 else:target.write_bytes(data)
 if executable:target.chmod(0o755)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('tree',type=Path);p.add_argument('--revision',default='M73-install-v1');a=p.parse_args()
 assert re.fullmatch(r'M73-[A-Za-z0-9_.-]{1,48}',a.revision)
 tree=a.tree.resolve(strict=True)
 assert subprocess.check_output(['git','-C',str(tree),'rev-parse','HEAD'],text=True).strip()=='dcf140cb1d5d2c15c1d7c353c95c4c2a56629820'
 kernel=tree/'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60'
 spec=importlib.util.spec_from_file_location('m72_verify',HERE.parent/'m72-phy-reset-receiver/verify_sources.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.verify_sources(tree)
 hashes=json.loads((HERE/'source-hashes.json').read_text());actual={name:hashlib.sha256((kernel/name).read_bytes()).hexdigest() for name in hashes}
 if all(actual[name]==row['baseline'] for name,row in hashes.items()):subprocess.run(['patch','-p1','--batch','--fuzz=0','-i',str(HERE/'persistent-nand.patch')],cwd=kernel,check=True)
 assert all(hashlib.sha256((kernel/name).read_bytes()).hexdigest()==row['candidate'] for name,row in hashes.items())
 assert (kernel/'drivers/mtd/nand/spi/Makefile').read_bytes().count(b'spinand-objs += vb235v-map.o')==1
 for name in ['vb235v-map.c','vb235v-map.h','vb235v-system-admit.h','vb235v-system-anchors.h']:
  relative='drivers/mtd/nand/spi/'+name
  install(HERE/name,kernel/relative);install(HERE/name,tree/'target/linux/airoha/files'/relative)
 for dest in [kernel/'include/linux/mtd/vb235v-hybrid-policy.h',tree/'target/linux/airoha/files/include/linux/mtd/vb235v-hybrid-policy.h']:install(HERE/'vb235v-hybrid-policy.h',dest)
 install(HERE/'persistent-nand.patch',tree/'target/linux/airoha/patches-6.18/962-vb235v-persistent-nand.patch')
 for name in ['an7583-tplink_vb235v.dts','an7583-tplink_vb235v-install-ram.dts']:install(HERE/name,tree/'target/linux/airoha/dts'/name)
 install(HERE/'image.mk',tree/'target/linux/airoha/image/vb235v-persistent.mk')
 install(HERE/'mkits-vb235v-system.py',tree/'target/linux/airoha/image/mkits-vb235v-system.py')
 target=tree/'target/linux/airoha/vb235v/base-files/etc/uci-defaults/99-vb235v-persistent'
 prior=(HERE.parent/'m71-dual-2p5g/99-vb235v-ram-multigig').read_bytes().replace(b'tplink,vb235v-ram-multigig-development',b'tplink,vb235v')
 if target.exists() and target.read_bytes()==prior:target.write_bytes((HERE/'99-vb235v-persistent').read_bytes())
 install(HERE/'99-vb235v-persistent',target,True)
 install(HERE/'81_vb235v_preserve_config',tree/'target/linux/airoha/vb235v/base-files/lib/preinit/81_vb235v_preserve_config')
 target=tree/'target/linux/airoha/vb235v/base-files/lib/upgrade/platform.sh'
 baseline=HERE.parent/'m55-ponwrt-system/overlay/target/linux/airoha/vb235v/base-files/lib/upgrade/platform.sh'
 current=(HERE/'platform.sh').read_bytes()
 assert target.read_bytes() in [baseline.read_bytes(),current,current.replace(b' /bin/mktemp',b'')]
 target.write_bytes((HERE/'platform.sh').read_bytes())
 for relative,line in [('target/linux/airoha/image/vb235v.mk','include $(TOPDIR)/target/linux/airoha/image/vb235v-persistent.mk'),('target/linux/airoha/vb235v/target.mk','FEATURES += nand')]:
  dest=tree/relative;data=dest.read_text()
  if line not in data.splitlines():dest.write_bytes((data+'\n'+line+'\n').encode())
 cfg=tree/'target/linux/airoha/vb235v/config-6.18';data=cfg.read_text()
 values={key:'y' for key in ['MTD','MTD_SPI_NAND','MTD_NAND_ECC_MEDIATEK','SPI_AIROHA_SNFI','MTD_UBI','MTD_UBI_BLOCK','UBIFS_FS','SQUASHFS','SQUASHFS_XZ','CRYPTO_LIB_SHA256']}
 values.update(MTD_UBI_BEB_LIMIT='20',MTD_NAND_MTK_BMT=None,MTD_UBI_FASTMAP=None)
 for key,value in values.items():
  symbol='CONFIG_'+key;data=re.sub(r'^(?:# )?'+symbol+r'(?:=.*| is not set)\n','',data,flags=re.M)+(symbol+'='+value if value else '# '+symbol+' is not set')+'\n'
 cfg.write_bytes(data.encode())
 cfg=tree/'.config';data=cfg.read_text().replace('CONFIG_TARGET_airoha_vb235v_DEVICE_tplink_vb235v-ram-multigig=y','CONFIG_TARGET_airoha_vb235v_DEVICE_tplink_vb235v=y')
 assert 'CONFIG_TARGET_airoha_vb235v_DEVICE_tplink_vb235v=y' in data
 for symbol in ['CONFIG_TARGET_ROOTFS_SQUASHFS','CONFIG_TARGET_ROOTFS_INITRAMFS','CONFIG_PACKAGE_ubi-utils','CONFIG_PACKAGE_nand-utils','CONFIG_PACKAGE_fwtool','CONFIG_PACKAGE_fstools']:
  data=re.sub(r'^(?:# )?'+re.escape(symbol)+r'(?:=.*| is not set)\n','',data,flags=re.M)+symbol+'=y\n'
 cfg.write_bytes(data.encode())
 dest=tree/'files/etc/vb235v-system-revision';dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes((a.revision+'\n').encode())
 print('M73 native guard, persistent profile and upgrade backend prepared; no device accessed.')
if __name__=='__main__':main()
