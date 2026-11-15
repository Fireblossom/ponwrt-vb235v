# SPDX-License-Identifier: GPL-2.0-only
"""Compare all executable ELF sections and symbolic relocations, without loading modules."""
import argparse
import hashlib
import json
from pathlib import Path

from elf_module_analysis import Module


def compare(left, right):
    a, b = Module(left), Module(right)
    first, second = a.section_signatures(), b.section_signatures()
    names = set(first) | set(second)
    executable = {n for n in names if first.get(n, {}).get('flags', 0) & 4 or second.get(n, {}).get('flags', 0) & 4}
    matches = sorted(n for n in names if first.get(n) == second.get(n))
    changed = sorted(names-set(matches))
    executable_changes = sorted(executable-set(matches))
    canonical_first, canonical_second = a.canonical_relocations(), b.canonical_relocations()
    return {'left_sha256': hashlib.sha256(a.data).hexdigest(), 'right_sha256': hashlib.sha256(b.data).hexdigest(),
            'whole_artifact_equal': a.data == b.data, 'machine_equal': a.machine == b.machine,
            'executable_sections': len(executable), 'changed_executable_sections': executable_changes,
            'all_executable_section_bytes_equal': bool(executable) and not executable_changes,
            'equal_section_count': len(matches), 'changed_sections': changed,
            'canonical_relocations_equal': canonical_first == canonical_second,
            'left_relocations': len(canonical_first), 'right_relocations': len(canonical_second),
            'limits': 'This compares unrelocated bytes and recorded RELA entries. It does not prove runtime ABI, behavior or kernel compatibility.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('left', type=Path)
    parser.add_argument('right', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.left, args.right)
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2)
        output.write('\n')
    print(json.dumps({key: result[key] for key in ('whole_artifact_equal', 'all_executable_section_bytes_equal', 'canonical_relocations_equal')}))


if __name__ == '__main__':
    main()
