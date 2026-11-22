#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Capture/verify the *persistent* system's private sysupgrade archive.

Requires coordinator device lease when capture() is called. Importing and
inspect_archive() are offline. Never publish the archive or its raw contents.
"""
import argparse,hashlib,io,json,shlex,tarfile,time
from pathlib import Path,PurePosixPath
from m83_session import PinnedManagementSession,WORKSPACE,discover
REQUIRED=['etc/config/'+name for name in ['network','dhcp','firewall','system','dropbear','uhttpd','wireless','rpcd']]+['etc/passwd','etc/group','etc/shadow','etc/dropbear/authorized_keys','etc/dropbear/dropbear_ed25519_host_key','etc/uhttpd.crt','etc/uhttpd.key']
def sha(data):return hashlib.sha256(data).hexdigest()
def inspect_archive(data,expected):
 assert 1<=len(data)<=8*1024*1024 and data[:2]==b'\x1f\x8b'
 assert set(REQUIRED)<=set(expected),'Required persistent identity/configuration snapshot missing'
 files={};total=0
 with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
  for member in archive:
   name=member.name.removeprefix('./');p=PurePosixPath(name)
   assert name and not p.is_absolute() and '..' not in p.parts and str(p)==name.rstrip('/'),'Unsafe archive path'
   assert p.parts[0] not in ['dev','proc','sys','tmp','run','overlay','rom','mnt']
   assert name not in files,'Duplicate archive member'
   assert member.isfile() or member.isdir() or member.issym(),'Special or hardlink archive member'
   if member.issym():
    target=PurePosixPath(member.linkname);assert not target.is_absolute() and '..' not in (p.parent/target).parts,'Unsafe symlink'
   total+=member.size;assert total<=32*1024*1024
   if member.isfile():
    blob=archive.extractfile(member).read();assert len(blob)==member.size
    files[name]={'sha256':sha(blob),'bytes':len(blob),'mode':oct(member.mode),'type':'regular'}
   else:files[name]={'type':'directory' if member.isdir() else 'symlink'}
 for name,digest in expected.items():
  assert files.get(name,{}).get('type')=='regular','Required archive entry absent or not regular: '+name
  assert files[name]['sha256']==digest,'Archive content differs from persistent snapshot: '+name
 return {'archive_bytes':len(data),'archive_sha256':sha(data),'regular_file_SHA256':{name:row['sha256'] for name,row in files.items() if row['type']=='regular'},'all_required_config_and_identity_files_present':True,'wireless_UCI_preserved':True,'SSH_TLS_shadow_rpcd_preserved':True,'extracted_to_host':False}
def capture(session,output,expected_revision):
 private=(WORKSPACE/'router-root-ssh').resolve();output=output.resolve()
 assert output.is_relative_to(private) and not output.exists(),'Backup must use a new directory under router-root-ssh'
 mounts=session.run('cat /proc/mounts');assert b' /rom squashfs ro,' in mounts and b' /overlay ubifs rw,' in mounts
 assert b'rdinit=/init' not in session.run('cat /proc/cmdline'),'Refusing to back up RAM defaults as persistent config'
 assert session.run('cat /etc/vb235v-system-revision').decode().strip()==expected_revision
 required=list(REQUIRED)
 for name in ['etc/dropbear/dropbear_rsa_host_key','etc/dropbear/dropbear_ecdsa_host_key','root/.ssh/authorized_keys']:
  if session.run('test -f /'+name,check=False)[0]==0:required.append(name)
 owner_files=session.run('[ ! -d /etc/ponwrt ] || find /etc/ponwrt -type f').decode().splitlines()
 for name in owner_files:
  assert name.startswith('/etc/ponwrt/') and '\n' not in name and '..' not in PurePosixPath(name).parts
  required.append(name[1:])
 token_exists=session.run('test -e /etc/ponwrt/setup.token',check=False)[0]==0
 if token_exists:required.append('etc/ponwrt/setup.token')
 required=sorted(set(required));backup_options=''
 keep=session.run('sysupgrade -l',timeout=60).decode().splitlines()
 if not {'/'+name for name in required}<=set(keep):
  # Standard -c adds changed /etc files without editing persistent keep.d or
  # sysupgrade.conf. -k only records installed packages; it cannot fix this.
  backup_options='-c '
  keep=session.run('sysupgrade -c -l',timeout=60).decode().splitlines()
 assert {'/'+name for name in required}<=set(keep),'Standard keep strategy still omits required configuration or owner identity'
 def hashes():
  raw=session.run('sha256sum '+' '.join(shlex.quote('/'+name) for name in required)).decode().splitlines()
  result={}
  for row in raw:
   digest,path=row.split(None,1);assert len(digest)==64 and path.startswith('/');result[path[1:]]=digest
  assert set(result)==set(required);return result
 before=hashes();remote='/tmp/m83-preserve-'+str(int(time.time()))+'.tgz'
 session.run('test ! -e '+remote)
 log=session.run('umask 077; sysupgrade '+backup_options+'-b '+remote,timeout=120)
 data=session.run('cat '+remote,timeout=120,limit=8*1024*1024)
 assert session.run('sha256sum '+remote).split()[0].decode()==sha(data)
 assert hashes()==before,'Persistent configuration changed during backup'
 receipt=inspect_archive(data,before);receipt.update(persistent_revision=expected_revision,source_bound_session=session.candidate,flash_write_commands_sent=False,standard_backup_options=backup_options.strip(),owner_setup_token_existed=token_exists,owner_setup_token_in_keep=('/etc/ponwrt/setup.token' in keep) if token_exists else None,all_etc_ponwrt_regular_files_included=owner_files,expected_live_file_SHA256=before)
 output.mkdir(mode=0o700);(output/'preserve.tgz').write_bytes(data);(output/'capture-private.log').write_bytes(log)
 (output/'receipt-private.json').write_text(json.dumps(receipt,indent=2)+'\n')
 return receipt
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--expected-revision',default='M75-phy-page-v1');p.add_argument('--target',required=True);a=p.parse_args()
 options=[row for row in discover() if row['target_address']==a.target];assert len(options)==1
 session=PinnedManagementSession(options[0])
 try:r=capture(session,a.output,a.expected_revision);print(json.dumps({key:r[key] for key in ['archive_bytes','archive_sha256','all_required_config_and_identity_files_present','flash_write_commands_sent']},indent=2))
 finally:session.close()
if __name__=='__main__':main()
