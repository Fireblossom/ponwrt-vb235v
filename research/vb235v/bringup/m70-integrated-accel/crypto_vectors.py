#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Generate synthetic large-request EIP93 oracles with host cryptography/hashlib."""
import argparse,hashlib,hmac,json
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes

def fixture(n):return bytes((i*13+i//17+0x5a)&255 for i in range(n))
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True);rows=[];iv=bytes(range(0x30,0x40));auth=bytes(range(0x80,0xb0))
    for mode in ['ecb','cbc','ctr']:
        for keylen in [16,24,32]:
            n=4097 if mode=='ctr' else 4096
            m={'ecb':modes.ECB(),'cbc':modes.CBC(iv),'ctr':modes.CTR(iv)}[mode]
            op=Cipher(algorithms.AES(bytes(range(keylen))),m).encryptor()
            cipher=op.update(fixture(n))+op.finalize()
            rows.append({'kind':0,'driver':mode+'(aes-eip93)','keylen':keylen,'bytes':n,'sha256':hashlib.sha256(cipher).hexdigest()})
    for keylen in [16,32]:
        op=Cipher(algorithms.AES(bytes(range(keylen))),modes.CBC(iv)).encryptor()
        cipher=op.update(fixture(4096))+op.finalize();aad=bytes(range(32))
        for authsize in [12,16,32]:
            tag=hmac.digest(auth,aad+cipher,'sha256')[:authsize]
            rows.append({'kind':1,'driver':'authenc(hmac(sha256-eip93),cbc(aes-eip93))','keylen':keylen,'bytes':4096,'authsize':authsize,'sha256':hashlib.sha256(aad+cipher+tag).hexdigest()})
    for driver,key in [('sha256-eip93',None),('hmac(sha256-eip93)',auth)]:
        digest=hashlib.sha256(fixture(8193)).hexdigest() if key is None else hmac.digest(key,fixture(8193),'sha256').hex()
        rows.append({'kind':2 if key is None else 3,'driver':driver,'keylen':0,'bytes':8193,'sha256':digest})
    header='/* Generated synthetic host oracles; no device secrets. */\nstatic const struct vector vectors[] = {\n'
    for row in rows:
        digest=','.join('0x'+row['sha256'][i:i+2] for i in range(0,64,2))
        header+=' {"'+row['driver']+'",'+str(row['kind'])+','+str(row['keylen'])+','+str(row['bytes'])+','+str(row.get('authsize',0))+',{'+digest+'}},\n'
    header+='};\n';(a.output/'crypto-vectors.h').write_bytes(header.encode())
    (a.output/'crypto-vectors.json').write_bytes((json.dumps(rows,indent=2)+'\n').encode())
    print('Generated',len(rows),'synthetic large-request crypto oracles.')
if __name__=='__main__':main()
