#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Apply the development-only private-calibration guard to prepared mt76."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('tree',type=Path)
    a=p.parse_args()
    tree=a.tree.resolve(strict=True)
    assert subprocess.check_output(['git','-C',str(tree),'rev-parse','HEAD'],text=True).strip()=='dcf140cb1d5d2c15c1d7c353c95c4c2a56629820'
    mt76=tree/'build_dir/target-aarch64_cortex-a53_musl/linux-airoha_vb235v/mt76-2026.10.28~0936617d'
    source=mt76/'mt7996/eeprom.c'
    hashes=json.loads((HERE/'source-hashes.json').read_text())
    digest=hashlib.sha256(source.read_bytes()).hexdigest()
    if digest==hashes['baseline']:
        subprocess.run(['patch','-p1','--fuzz=0','--batch','-i',str(HERE/'mt76-vb235v-private-calibration.patch')],cwd=mt76,check=True)
        assert hashlib.sha256(source.read_bytes()).hexdigest()==hashes['candidate']
        for stamp in mt76.glob('.built*'):
            assert stamp.is_file()
            stamp.unlink()
    elif digest!=hashes['candidate']:
        raise ValueError('Unexpected prepared mt76 EEPROM source')
    print('M65 calibration guard prepared; private input not included.')

if __name__=='__main__':main()
