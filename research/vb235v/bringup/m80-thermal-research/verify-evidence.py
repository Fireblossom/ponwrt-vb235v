#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Verify the exact OEM temperature model and preserve frozen M78 sources."""
import argparse, hashlib, importlib.util, json, struct, sys
from pathlib import Path
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('workspace', type=Path)
a = p.parse_args()
b = (a.workspace/'offline-analysis/kernel@1-decompressed.bin').read_bytes()
assert hashlib.sha256(b).hexdigest() == '1cdf83a09fd62d4b46c0a89ed1a422bdf1a783addab5c30c3d72862cd189f5de'
base = 0xffffffc010088000
def u32(va): return struct.unpack_from('<I', b, va-base)[0]
assert struct.unpack_from('<3I', b, 0xffffffc010859970-base) == (973,995,1035)
assert struct.unpack_from('<3I', b, 0xffffffc010859980-base) == (7440,7620,8390)
signature = struct.pack('<QQ', 0xffffffc010577fe0, 0xffffffc010577eb0)
assert b.count(signature) == 1
o = b.index(signature)
assert struct.unpack_from('<6I', b, o+16) == (0xf20,0xf24,0xf28,1,3,0)
assert u32(base+o+40) == 1
sensor_ptr = struct.unpack_from('<Q', b, o+48)[0]
assert struct.unpack_from('<3I', b, sensor_ptr-base) == (0,5,6)
# AN7583 init marks temperature EFUSE invalid and installs constant offsets.
assert u32(0xffffffc010577ff0) == 0xb9004c1f
assert u32(0xffffffc010578010) == 0xd28024c4  # 294
assert u32(0xffffffc01057801c) == 0xf2c02544  # 298 in upper word
assert u32(0xffffffc010578020) == 0x52802b03  # 344
# Three diode phases are requested in exact order Zero, D0, D1.
assert u32(0xffffffc010577eb8) == 0x52800021
assert u32(0xffffffc010577f24) == 0x52800001
assert u32(0xffffffc010577f3c) == 0x52800041
# Actual EFUSE read ABI, distinct from CPU-frequency and PHY-load SMCs.
assert u32(0xffffffc0100c8b7c) == 0xd2800020
assert u32(0xffffffc0100c8b80) == 0xf2b04000
assert u32(0xffffffc0100c8b9c) == 0xd288aa41
assert u32(0xffffffc0100c8ba8) == 0xf2a88821
assert u32(0xffffffc0100c8ba4) == 0xd2802003
report = json.loads((HERE.parent.parent/'findings/cpu-dvfs-original-and-native-m78.json').read_text())
for name, digest in report['implementation']['source_sha256'].items():
    assert hashlib.sha256((HERE.parent/'m78-cpu-dvfs'/name).read_bytes()).hexdigest() == digest, 'M78 frozen source changed: '+name
print('M80 exact OEM BGP selection, three-point constants/phases, non-EFUSE init, readout EFUSE ABI and unchanged M78 fingerprints PASS')
