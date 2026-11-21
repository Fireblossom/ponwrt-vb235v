# SPDX-License-Identifier: GPL-2.0-only
import argparse,importlib.util,json
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('m71_sources',HERE.parent/'m71-dual-2p5g/verify_sources.py')
m71=importlib.util.module_from_spec(spec);spec.loader.exec_module(m71)
def verify_sources(tree):
    hashes=json.loads((HERE/'source-hashes.json').read_text())
    return m71.verify_sources(tree,{name:row['candidate'] for name,row in hashes.items()})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('tree',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.write_bytes((json.dumps(verify_sources(a.tree),indent=2)+'\n').encode())
    print('M72 receiver and all 14 integrated source hashes verified.')
