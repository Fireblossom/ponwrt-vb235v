# SPDX-License-Identifier: GPL-2.0-only
"""Join saved kallsyms definitions and ELF imports without publishing live addresses.

Kallsyms identifies runtime symbol providers, not exported ABI compatibility.
An optional archived Module.symvers supplies separate build-time export evidence.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path, PurePosixPath
import re


def parse_kallsyms(text):
    definitions = defaultdict(set)
    pattern = re.compile(r'^[0-9a-fA-F]{8,16}\s+([A-Za-z?])\s+(\S+)(?:\s+\[([A-Za-z0-9_]+)\])?\s*$')
    for line in text.splitlines():
        match = pattern.fullmatch(line)
        if not match:
            continue  # Shell echo, framing markers and prompts are not symbols.
        kind, name, module = match.groups()
        if kind.upper() == 'U':
            continue
        definitions[name].add((kind, module or 'vmlinux'))
    if not definitions:
        raise ValueError('No kallsyms definitions parsed')
    return definitions


def parse_symvers(text):
    exports = defaultdict(set)
    for line in text.splitlines():
        fields = line.split()
        if len(fields) >= 4 and re.fullmatch(r'0x[0-9a-fA-F]{8}', fields[0]) and fields[3].startswith('EXPORT_SYMBOL'):
            exports[fields[1]].add((fields[2], fields[3]))
    if not exports:
        raise ValueError('No archived build exports parsed')
    return exports


def correlate(artifacts, definitions, archived_exports=None, consumers=None):
    module_exports = defaultdict(set)
    unique = {}
    for artifact in artifacts:
        if 'error' in artifact:
            raise ValueError('Inventory contains an unparsed artifact')
        name = PurePosixPath(artifact['path']).stem
        if name in unique:
            if artifact['sha256'] != unique[name]['sha256']:
                raise ValueError('Conflicting module builds: ' + name)
            continue
        unique[name] = artifact
        for symbol in artifact['exported_symbols']:
            module_exports[symbol].add(name)
    if consumers and set(consumers) - unique.keys():
        raise ValueError('Requested consumer missing from inventory')
    result = {}
    for name, artifact in sorted(unique.items()):
        if consumers and name not in consumers:
            continue
        rows = []
        for symbol in artifact['undefined_symbols']:
            observed = sorted(definitions.get(symbol, set()))
            candidates = sorted(module_exports.get(symbol, set()) - {name})
            rows.append({'symbol': symbol,
                         'module_export_candidates': candidates,
                         'live_definitions': [{'type': kind, 'provider': provider} for kind, provider in observed],
                         'archived_build_exports': [{'provider': owner, 'export': kind}
                                                    for owner, kind in sorted((archived_exports or {}).get(symbol, set()))]})
        result[name] = {'sha256': artifact['sha256'], 'imports': rows,
                        'not_observed_in_live_symbols': [row['symbol'] for row in rows if not row['live_definitions']],
                        'only_live_vmlinux_provider': [row['symbol'] for row in rows
                                                      if {d['provider'] for d in row['live_definitions']} == {'vmlinux'}]}
    return {'consumers': result, 'includes_live_addresses': False,
            'limitations': 'Runtime definitions, archived exports, and module export candidates are distinct evidence; none certifies ABI or function execution.'}


def bounded_read(path):
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('Input exceeds 16 MiB limit')
    return path.read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inventory', type=Path)
    parser.add_argument('kallsyms', type=Path)
    parser.add_argument('--symvers', type=Path)
    parser.add_argument('--consumers', help='comma-separated module basenames')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    inventory, kallsyms = bounded_read(args.inventory), bounded_read(args.kallsyms)
    symvers = bounded_read(args.symvers) if args.symvers else None
    result = correlate(json.loads(inventory)['artifacts'], parse_kallsyms(kallsyms.decode('ascii')),
                       parse_symvers(symvers.decode('ascii')) if symvers is not None else None,
                       args.consumers.split(',') if args.consumers else None)
    result['input_sha256'] = {'inventory': hashlib.sha256(inventory).hexdigest(),
                              'kallsyms': hashlib.sha256(kallsyms).hexdigest(),
                              'archived_symvers': hashlib.sha256(symvers).hexdigest() if symvers is not None else None}
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({name: {'imports': len(row['imports']), 'vmlinux': len(row['only_live_vmlinux_provider']),
                             'not_observed': len(row['not_observed_in_live_symbols'])}
                      for name, row in result['consumers'].items()}))


if __name__ == '__main__':
    main()
