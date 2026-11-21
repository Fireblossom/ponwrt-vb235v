# SPDX-License-Identifier: GPL-2.0-only
"""Preserve the verified M63/M64 host and QPHY sources across kernel recreation."""
import hashlib,json,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
def install(source,dest):
    data=source.read_bytes();dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():
        assert dest.read_bytes()==data,'Different existing PCIe source: '+str(dest)
        return
    dest.write_bytes(data)
def preserve_pcie(tree,kernel):
    for folder,source,manifest,patch,dest in [
     ('m63-ram-pcie','pcie-mediatek-gen3.c','host-source-hashes.json','985-vb235v-ram-pcie-host-development.patch','956-vb235v-pcie0.patch'),
     ('m64-dual-pcie','pcie-mediatek.c','second-host-source-hashes.json','986-vb235v-ram-second-pcie-host.patch','957-vb235v-pcie1.patch')]:
        base=HERE.parent/folder;path=kernel/'drivers/pci/controller'/source;expected=json.loads((base/manifest).read_text())
        if hashlib.sha256(path.read_bytes()).hexdigest()==expected['baseline']:
            subprocess.run(['patch','-p1','--batch','--fuzz=0','-i',str(base/patch)],cwd=kernel,check=True)
        assert hashlib.sha256(path.read_bytes()).hexdigest()==expected['candidate'],'PCIe prerequisite differs: '+source
        install(base/patch,tree/'target/linux/airoha/patches-6.18'/dest)
    for name in ['phy-vb235v-qp-pcie.c','qphy-fields.h','qphy-sequence.inc']:
        source=HERE.parent/'m64-dual-pcie'/name
        install(source,kernel/'drivers/phy/airoha'/name)
        install(source,tree/'target/linux/airoha/files/drivers/phy/airoha'/name)
    makefile=kernel/'drivers/phy/airoha/Makefile';include=b'\nobj-y += phy-vb235v-qp-pcie.o\n'
    if include not in makefile.read_bytes():makefile.write_bytes(makefile.read_bytes()+include)
    install(HERE/'qphy-makefile.patch',tree/'target/linux/airoha/patches-6.18/958-vb235v-qphy.patch')
