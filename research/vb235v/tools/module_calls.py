# SPDX-License-Identifier: GPL-2.0-only
"""Recover relocation-backed direct AArch64 calls from a local .ko; no execution."""
import argparse
import hashlib
import json
from pathlib import Path

from elf_module_analysis import Module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifact', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    module = Module(args.artifact)
    edges = module.direct_call_edges()
    result = {'sha256': hashlib.sha256(module.data).hexdigest(), 'machine': module.machine, 'edges': edges,
              'limits': 'Only RELA-backed B/BL direct branches inside sized function symbols. Indirect calls, inline operations and branches without retained relocation records are absent.'}
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2)
        output.write('\n')
    print(json.dumps({'direct_call_edges': len(edges)}))


if __name__ == '__main__':
    main()
