# SPDX-License-Identifier: GPL-2.0-only
"""Summarize an already saved /proc/crypto listing; never performs cryptographic operations."""
import argparse
import json
from pathlib import Path
import re


def parse(text):
    entries = []
    for block in re.split(r'\n\s*\n', text.replace('\r', '')):
        fields = dict(re.findall(r'^([a-z_]+)\s*:\s*(.*?)\s*$', block, re.M))
        if 'name' not in fields or 'driver' not in fields:
            continue
        entries.append({key: fields[key] for key in ('name', 'driver', 'module', 'priority', 'selftest', 'type') if key in fields})
    return {'algorithms': entries, 'eip93': [e for e in entries if 'eip93' in e['driver']],
            'note': 'Registration and reported selftests do not measure offload use or throughput.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = parse(args.capture.read_text(encoding='utf-8', errors='replace'))
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2)
        output.write('\n')
    print(json.dumps({'registered': len(result['algorithms']), 'eip93_entries': len(result['eip93'])}))


if __name__ == '__main__':
    main()
