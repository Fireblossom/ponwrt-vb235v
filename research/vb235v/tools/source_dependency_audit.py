# SPDX-License-Identifier: GPL-2.0-only
"""Index textual #include dependencies without preprocessing or executing sources."""
import argparse
from collections import defaultdict, Counter
import hashlib
import json
from pathlib import Path, PurePosixPath
import posixpath
import re


def audit(index, manifest, source_root, contains):
    names = set()
    basenames = defaultdict(list)
    with index.open(encoding='utf-8') as source:
        for line in source:
            entry = json.loads(line)
            if entry['type'] == '0':
                names.add(entry['name'])
                basenames[PurePosixPath(entry['name']).name].append(entry['name'])
    references = []
    sources = []
    for entry in json.loads(manifest.read_text(encoding='utf-8')):
        name = entry['archive_path']
        path = PurePosixPath(name)
        if path.is_absolute() or '..' in path.parts or any(':' in p for p in path.parts):
            raise ValueError('Unsafe source manifest path')
        if contains not in name or path.suffix not in ('.c', '.h'):
            continue
        data = source_root.joinpath(*path.parts).read_bytes()
        if hashlib.sha256(data).hexdigest() != entry['sha256']:
            raise ValueError('Source hash differs: ' + name)
        sources.append(entry)
        for number, line in enumerate(data.decode('utf-8', 'replace').splitlines(), 1):
            match = re.match(r'\s*#\s*include\s*([<"])([^>"]+)[>"]', line)
            if not match:
                continue
            delimiter, dependency = match.groups()
            local = posixpath.normpath(str(path.parent / dependency))
            candidates = basenames.get(PurePosixPath(dependency).name, [])
            if delimiter == '"' and local in names:
                state = 'relative-path-present'
                candidates = [local]
            elif candidates:
                state = 'basename-candidates-only'
            else:
                state = 'not-found-by-filename'
            references.append({'source': name, 'line': number, 'include': dependency,
                               'kind': 'system' if delimiter == '<' else 'quoted',
                               'state': state, 'candidate_count': len(candidates),
                               'candidates': sorted(candidates)[:5]})
    return {'conditional_preprocessing_performed': False,
            'note': 'Filename availability is not include-path resolution, ABI compatibility or build success.',
            'sources': sources, 'counts': dict(Counter(r['state'] for r in references)),
            'includes': references}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--contains', default='')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.index, args.manifest, args.source_root, args.contains)
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2)
        output.write('\n')
    print(json.dumps({'source_files': len(result['sources']), 'include_counts': result['counts']}))


if __name__ == '__main__':
    main()
