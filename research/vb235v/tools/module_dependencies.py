# SPDX-License-Identifier: GPL-2.0-only
"""Map imports to inspected module exports; unresolved names may be built into the kernel."""
import argparse
from collections import defaultdict
import json
from pathlib import Path, PurePosixPath


def build(artifacts):
    providers = defaultdict(set)
    modules = {}
    for artifact in artifacts:
        if 'error' in artifact:
            continue
        name = PurePosixPath(artifact['path']).stem
        if name in modules:
            raise ValueError('Duplicate module name; choose one build variant: ' + name)
        modules[name] = artifact
        for symbol in artifact['exported_symbols']:
            providers[symbol].add(name)
    edges = defaultdict(list)
    unresolved, ambiguous = {}, {}
    for name, artifact in modules.items():
        missing = []
        multiple = {}
        for symbol in artifact['undefined_symbols']:
            matches = providers.get(symbol, set()) - {name}
            if len(matches) == 1:
                edges[(name, next(iter(matches)))].append(symbol)
            elif matches:
                multiple[symbol] = sorted(matches)
            else:
                missing.append(symbol)
        unresolved[name] = missing
        if multiple:
            ambiguous[name] = multiple
    return {'modules': sorted(modules),
            'edges': [{'consumer': a, 'provider': b, 'symbols': sorted(symbols)} for (a, b), symbols in sorted(edges.items())],
            'outside_inspected_module_set': unresolved, 'ambiguous_providers': ambiguous,
            'note': 'A symbol outside this inspected set is not proof of a missing implementation; it may be built into Linux or another module.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('inventory', type=Path)
    parser.add_argument('--select', help='comma-separated module basenames, for one consistent build/variant set')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    artifacts = json.loads(args.inventory.read_text())['artifacts']
    if args.select:
        selection = set(args.select.split(','))
        artifacts = [a for a in artifacts if PurePosixPath(a['path']).stem in selection]
    result = build(artifacts)
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2)
        output.write('\n')
    print(json.dumps({'modules': len(result['modules']), 'dependency_edges': len(result['edges'])}))


if __name__ == '__main__':
    main()
