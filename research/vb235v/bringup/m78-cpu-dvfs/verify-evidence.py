#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Check local OEM proof chain without exporting firmware or private DT."""
import argparse, hashlib, importlib.util, lzma, struct, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('workspace', type=Path)
a = p.parse_args()
base = a.workspace/'offline-analysis'
boot = (base/'m29-hardware/bootloader-before.bin').read_bytes()
assert hashlib.sha256(boot).hexdigest() == '775d71e22ae10197e11493f71c99f92ec3470b9e1bccbcb1e046404d141af441'
payload = boot[0x21800:0x2f60e]
assert len(payload) == 56846
assert hashlib.sha256(payload).hexdigest() == 'c112e98822aef6334f8861212a1da5fa3158c0e3ac60fa09e403abccd754728f'
bl31 = lzma.decompress(payload)
assert bl31 == (base/'stock-bl31-decompressed.bin').read_bytes()
assert hashlib.sha256(bl31).hexdigest() == 'b14982e68559230f2bf4bf65a5ffa6ec36e8c17eb99d2519f5d38fe666d5b15f'
# Branch target passes desired state to actual PLL routine then overrides its
# result with -2 unconditionally. Exact instructions, not symbol/name guesses.
assert struct.unpack('<4I', bl31[0x4ef0:0x4f00]) == (0x2a1503e0, 0x97fffd3c, 0x92800020, 0x17fffff0)
spec = importlib.util.spec_from_file_location('fdtinventory', HERE.parent.parent/'tools/fdt_board_inventory.py')
fdt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fdt)
dt = (base/'live-board-evidence/20261116T002156Z/stock.dtb').read_bytes()
assert hashlib.sha256(dt).hexdigest() == '387f309fea8a488c5de92fdea1632a07933316e32fc94013755342e6934c3a4a'
nodes, _ = fdt.parse(dt)
hz = {n: int.from_bytes(v['opp-hz'], 'big') for n, v in nodes.items() if n.startswith('/opp-table/') and 'opp-hz' in v}
assert sorted(hz.values()) == [500000000, 1200000000]
assert 'opp-shared' in nodes['/opp-table']
image = (base/'kernel@1-decompressed.bin').read_bytes()
assert hashlib.sha256(image).hexdigest() == '1cdf83a09fd62d4b46c0a89ed1a422bdf1a783addab5c30c3d72862cd189f5de'
assert image[56:60] == b'ARMd'
assert int.from_bytes(image[8:16], 'little') == 0x88000
print('M78 exact OEM kernel/DT/bootloader→BL31 fingerprints, BL31 legacy -2 instructions and actual OPP values PASS')
