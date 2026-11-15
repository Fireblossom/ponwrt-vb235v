# SPDX-License-Identifier: GPL-2.0-only
"""Classify archive-index paths without extracting or executing vendor files."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

SOURCE = ('.c', '.h', '.S', '.rs')


def classify(name):
    n = name.lower()
    if re.search(r'/(?:ltq-|lantiq/)', n):
        return 'unrelated-lantiq-reference'
    if '/mt_wifi7/' in n or '/mt_wifi_osal/' in n or '/mt_hwifi/' in n or 'mt7993' in n:
        return 'wifi'
    if re.search(r'/(?:voip_driver|voip_app|release_voip_bsp|proslic|slic3)(?:/|$)', n):
        return 'voice'
    if re.search(r'(?:tcadsl|tcvdsl|/xdsl/|/adsl/|/vdsl/|dsl_driver|dslapi)', n):
        return 'dsl'
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('index', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    entries = []
    with args.index.open(encoding='utf-8') as source:
        for line in source:
            row = json.loads(line)
            track = classify(row['name'])
            if track is None or row['type'] != '0':
                continue
            entries.append({'archive_path': row['name'], 'bytes': row['size'],
                            'track': track, 'source_extension': row['name'].endswith(SOURCE)})
    counts = Counter(e['track'] for e in entries)
    result = {'note': 'Filename inventory only; duplicates and unused packages may be present.',
              'counts': dict(counts), 'entries': entries}
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2)
        output.write('\n')
    print(json.dumps({'counts': dict(counts), 'output': str(args.output)}))


if __name__ == '__main__':
    main()
