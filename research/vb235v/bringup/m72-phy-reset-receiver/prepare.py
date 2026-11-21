# SPDX-License-Identifier: GPL-2.0-only
"""Apply the receiver correction after the verified M71 integrated sources."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'m71-dual-2p5g'))
from verify_sources import verify_sources

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('tree',type=Path);a=p.parse_args()
    tree=a.tree.resolve(strict=True)
    assert subprocess.check_output(['git','-C',str(tree),'rev-parse','HEAD'],text=True).strip()=='dcf140cb1d5d2c15c1d7c353c95c4c2a56629820'
    kernel=tree/'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/linux-6.18.60'
    hashes=json.loads((HERE/'source-hashes.json').read_text())
    relative,row=next(iter(hashes.items()))
    current=hashlib.sha256((kernel/relative).read_bytes()).hexdigest()
    if current==row['baseline']:
        verify_sources(tree)
        subprocess.run(['patch','-p1','--batch','--fuzz=0','-i',str(HERE/'pcs-ethernet-receiver.patch')],cwd=kernel,check=True)
    verify_sources(tree,{relative:row['candidate']})
    dest=tree/'target/linux/airoha/patches-6.18/961-vb235v-pcs-ethernet-receiver.patch'
    data=(HERE/'pcs-ethernet-receiver.patch').read_bytes()
    if dest.exists():assert dest.read_bytes()==data,'Different existing receiver correction'
    else:dest.write_bytes(data)
    print('M72 receiver source and all integrated prerequisites verified; correction persisted in target queue.')
if __name__=='__main__':main()
