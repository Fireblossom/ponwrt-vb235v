# SPDX-License-Identifier: GPL-2.0-only
"""Compare private on-disk NPU firmware with reference files; never execute either."""
import argparse
import hashlib
import json
from pathlib import Path
import re

NAMES = ('npu_rv32.bin', 'npu_data.bin')


def compare_bytes(actual, reference):
    shared = min(len(actual), len(reference))
    return {'actual_bytes': len(actual), 'actual_sha256': hashlib.sha256(actual).hexdigest(),
            'reference_bytes': len(reference), 'reference_sha256': hashlib.sha256(reference).hexdigest(),
            'byte_exact': actual == reference,
            'different_positions_within_shared_length': sum(a != b for a, b in zip(actual, reference)),
            'shared_length': shared, 'actual_minus_reference_length': len(actual) - len(reference)}


def bounded_read(path, maximum):
    if not path.is_file() or path.is_symlink() or not 0 < path.stat().st_size <= maximum:
        raise ValueError('Expected a bounded regular nonsymlink artifact')
    return path.read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('actual_directory', type=Path)
    parser.add_argument('reference_directory', type=Path)
    parser.add_argument('--module', type=Path, required=True, help='saved stock npu.ko, for path-string corroboration')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    module = bounded_read(args.module, 64 * 1024 * 1024)
    paths = sorted({path.decode('ascii') for path in re.findall(rb'/userfs/npu_[A-Za-z0-9_.-]+\.bin', module)})
    expected = ['/userfs/' + name for name in NAMES]
    if paths != sorted(expected):
        raise ValueError('Stock module does not name exactly the expected two firmware paths')
    result = {'classification': 'on-disk firmware file identity, not a live instruction-memory attestation',
              'stock_module_sha256': hashlib.sha256(module).hexdigest(), 'module_path_strings': paths,
              'files': [{'file': name, **compare_bytes(bounded_read(args.actual_directory / name, 1024 * 1024),
                                                       bounded_read(args.reference_directory / name, 1024 * 1024))}
                        for name in NAMES],
              'limitations': ['Matching module path strings do not prove which bytes were loaded or are executing.',
                             'Byte differences do not identify command compatibility, features, or which build is newer.',
                             'No firmware bytes or extracted strings beyond the two fixed paths are emitted.']}
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({row['file']: {'bytes': row['actual_bytes'], 'matches_reference': row['byte_exact']}
                      for row in result['files']}))


if __name__ == '__main__':
    main()
