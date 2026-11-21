#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Package host-built station tools/modules for an audited RAM kernel only."""
import argparse
import hashlib
import io
import json
import re
from pathlib import Path
import tarfile
from elf_inventory import inspect
from elf_dynamic_inventory import SharedObject
from elf_module_analysis import Module


class RuntimeELF(SharedObject):
    def __init__(self,path):
        Module.__init__(self,path,elf_types=(2,3))
        assert self.machine==183, 'Expected AArch64 runtime ELF'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('tree',type=Path)
    p.add_argument('--kernel-config',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    tree=a.tree.resolve()
    target=tree/'build_dir/target-aarch64_cortex-a53_musl'
    linux=target/'linux-airoha_vb235v/linux-6.18.60'
    assert (linux/'.config').read_bytes()==a.kernel_config.read_bytes(), 'Running image/kernel configuration differs'
    packages=[]
    for pattern in ('*/.pkgdir/*','*/*/.pkgdir/*','*/*/*/.pkgdir/*'):
        packages.extend(p for p in target.glob(pattern) if p.is_dir())
    modules={}
    for directory in packages:
        for path in directory.glob('lib/modules/6.18.60/*.ko'):
            name=path.stem.replace('-','_')
            if name in modules:
                assert path.read_bytes()==modules[name].read_bytes(), 'Ambiguous module '+name
            modules[name]=path
    builtin={Path(line).stem.replace('-','_') for line in (linux/'modules.builtin').read_text().splitlines()}
    ordered=[]
    metadata={}
    visiting=set()

    def add_module(name):
        name=name.replace('-','_')
        if name in metadata or name in builtin: return
        assert name not in visiting and name in modules, 'Unresolved/cyclic module '+name
        visiting.add(name)
        data=inspect(modules[name])
        assert data['elf_machine']==183
        assert data['modinfo'].get('vermagic')==['6.18.60 SMP mod_unload aarch64']
        for dep in data['modinfo'].get('depends',[''])[0].split(','):
            if dep: add_module(dep)
        visiting.remove(name)
        metadata[name]={'sha256':data['sha256'],'bytes':data['bytes'],'modinfo':data['modinfo']}
        ordered.append(name)
    add_module('mt7996e')
    assert b'VB235v private ART EEPROM loaded; reference fallback disabled' in modules['mt7996e'].read_bytes()
    payload={}
    for name in ordered:
        payload['lib/modules/6.18.60/'+modules[name].name]=modules[name].read_bytes()
    pkgindex={}
    for directory in packages:
        if directory.name in ('wpad-mbedtls','wpa-cli','iw','wireless-regdb','kmod-mt7990-firmware'):
            if directory.name in pkgindex:
                # wpa-cli can be staged by several TLS variants; choose the
                # same full-mbedtls build as wpad when available.
                if 'wpad-full-mbedtls' not in str(directory): continue
            pkgindex[directory.name]=directory
    for name in ('wpad-mbedtls','wpa-cli','iw','wireless-regdb','kmod-mt7990-firmware'):
        assert name in pkgindex, 'Missing station runtime package '+name
    binaries={
        'usr/sbin/wpad':pkgindex['wpad-mbedtls']/'usr/sbin/wpad',
        'usr/sbin/wpa_cli':pkgindex['wpa-cli']/'usr/sbin/wpa_cli',
        'usr/sbin/iw':pkgindex['iw']/'usr/sbin/iw',
    }
    libroot=tree/'staging_dir/target-aarch64_cortex-a53_musl/usr/lib'
    dependencies={}

    def add_elf(path,destination):
        if destination in payload: return
        elf=RuntimeELF(path)
        payload[destination]=path.read_bytes()
        dependencies[destination]=elf.dependencies()
        for name in elf.dependencies():
            assert re.fullmatch(r'[A-Za-z0-9_+-]+\.so(?:\.[0-9]+)*',name), 'Invalid library name'
            if name=='libc.so': continue
            library=libroot/name
            if not library.is_file():
                library=tree/'staging_dir/target-aarch64_cortex-a53_musl/root-airoha/lib'/name
            assert library.is_file(), 'Missing dynamic dependency '+name
            add_elf(library.resolve(),'usr/lib/'+name)
    for destination,path in binaries.items(): add_elf(path,destination)
    for name in ('wireless-regdb','kmod-mt7990-firmware'):
        directory=pkgindex[name]
        for path in directory.rglob('*'):
            if path.is_file() and not path.is_symlink() and path.relative_to(directory).parts[:2]==('lib','firmware'):
                payload[path.relative_to(directory).as_posix()]=path.read_bytes()
    report={'kernel_config_sha256':hashlib.sha256(a.kernel_config.read_bytes()).hexdigest(),
            'module_order':ordered,'modules':metadata,'dynamic_dependencies':dependencies,
            'files':{name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in sorted(payload.items())},
            'private_calibration_included':False,'WiFi_credentials_included':False,'radio_tested':False}
    a.output.mkdir(exist_ok=False)
    (a.output/'manifest.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
    with tarfile.open(a.output/'runtime.tar','w') as archive:
        for name,data in sorted(payload.items()):
            assert not name.startswith('/') and '..' not in Path(name).parts
            info=tarfile.TarInfo('m65-runtime/'+name)
            info.size=len(data); info.mode=0o755 if name in binaries else 0o644
            archive.addfile(info,io.BytesIO(data))
        for name in ('wpa_supplicant','hostapd'):
            info=tarfile.TarInfo('m65-runtime/usr/sbin/'+name)
            info.type=tarfile.SYMTYPE; info.linkname='wpad'; info.mode=0o755
            archive.addfile(info)
    print('Station runtime packaged: %d modules and %d files; no calibration or credentials.'%(len(ordered),len(payload)))


if __name__=='__main__':
    main()
