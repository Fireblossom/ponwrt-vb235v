#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Freeze the explicit M83 source-only delivery list; never stage git files."""
import hashlib,json,re,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[3]
scopes=['research/vb235v/bringup/m83-combined-image-upgrade','research/vb235v/findings/combined-image-upgrade-m83.json','research/vb235v/findings/cpu-mini-final-fdt-review-m83.json']
paths=set(subprocess.check_output(['git','-C',str(REPO),'ls-files','--cached','--others','--exclude-standard','--',*scopes],text=True).splitlines())
inventory=str((HERE/'COMMIT_FILES.txt').relative_to(REPO)).replace('\\','/')
freeze=str((HERE/'source-freeze.json').relative_to(REPO)).replace('\\','/')
paths.update([inventory,freeze]);paths=sorted(paths)
(HERE/'COMMIT_FILES.txt').write_text('\n'.join(paths)+'\n',encoding='utf-8')
hashes={}
for name in paths:
 if name==freeze:continue
 path=REPO/name;assert path.is_file() and path.suffix in ['', '.py','.json','.md','.txt','.sh','.patch']
 data=path.read_bytes();data.decode('utf-8');assert b'\0' not in data
 assert not re.search(rb'-----BEGIN [A-Z ]*PRIVATE KEY-----',data),'Private material pattern in '+name
 hashes[name]=hashlib.sha256(data).hexdigest()
assert hashlib.sha256((HERE/'input-lock.json').read_bytes()).hexdigest()=='401039a61b803b2ab5c7c264916e8a4ad26b509b81cb30d78d062188b1bfcd81'
result={'schema':1,'revision':'M83-combined-v1','candidate_manifest_sha256':'91fd972ed13ea3df38d8f6355bd4a9718a1fc030033ea5ef7f44abc7ac9ed762','candidate_input_lock_sha256':'401039a61b803b2ab5c7c264916e8a4ad26b509b81cb30d78d062188b1bfcd81','source_sha256':hashes,'all_listed_files_UTF8_text':True,'private_archives_firmware_keys_credentials_included':False,'git_staged_by_this_script':False,'hardware_installation_acceptance':'pending'}
(HERE/'source-freeze.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'source_files_to_commit':len(paths),'source_hashes':len(hashes),'source_freeze_sha256':hashlib.sha256((HERE/'source-freeze.json').read_bytes()).hexdigest(),'no_git_staging':True,'private_blobs_included':False},indent=2))
