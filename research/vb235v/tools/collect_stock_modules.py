# SPDX-License-Identifier: GPL-2.0-only
"""Bounded, read-only collection from the stock shell; requires host-side Paramiko.

Keep output, credentials and pinned host keys outside the public checkout.
Resume reuses only complete files whose local and current device hashes agree.
It does not resume a partially transferred file or execute vendor objects.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import socket
import struct
import time
import uuid

MIB = 1024 * 1024
MAX_FILE = 32 * MIB
MAX_TOTAL = 96 * MIB
MAX_FILES = 128


def module_relative(path):
    if not re.fullmatch(r'/lib/modules/[A-Za-z0-9_./+-]+\.ko', path):
        raise ValueError('Invalid module path')
    relative = PurePosixPath(path).relative_to('/lib/modules')
    if '..' in relative.parts or str(relative) != path[len('/lib/modules/'):]:
        raise ValueError('Noncanonical module path')
    return relative


def parse_size(reply):
    matches = re.findall(rb'^\s*(\d+)\s*$', reply, re.M)
    if len(matches) != 1:
        raise ValueError('File size not uniquely parsed')
    return int(matches[0])


def parse_digest(reply, path):
    matches = re.findall(rb'SHA256\(' + re.escape(path.encode('ascii'))
                         + rb'\)= ([0-9a-f]{64})(?![0-9a-f])', reply)
    if len(matches) != 1:
        raise ValueError('Device digest not uniquely parsed')
    return matches[0].decode('ascii')


def decode_transfer(reply, size, digest):
    before, sep, rest = reply.partition(b'\nTP_B64_BEGIN\n')
    encoded, end, after = rest.partition(b'\nTP_B64_END\n')
    if not sep or not end:
        raise ValueError('Incomplete transfer framing')
    data = base64.b64decode(encoded.replace(b'\n', b''), validate=True)
    if len(data) != size or hashlib.sha256(data).hexdigest() != digest:
        raise ValueError('Transferred bytes differ from device size/digest')
    return data, after


class Shell:
    def __init__(self, channel):
        self.channel = channel

    def run(self, command, budget=16 * MIB, timeout=60):
        marker = 'TP_' + uuid.uuid4().hex[:12]
        line = command + ";printf '\\n" + marker + "\\n'"
        if len(line.encode('ascii')) > 235:
            raise ValueError('Command exceeds stock edited-input limit')
        self.channel.sendall((line + '\n').encode('ascii'))
        data = bytearray()
        end = time.monotonic() + timeout
        needle = ('\n' + marker + '\n').encode('ascii')
        while time.monotonic() < end:
            if self.channel.recv_ready():
                chunk = self.channel.recv(65536)
                if not chunk:
                    break
                data.extend(chunk)
                if len(data) > budget:
                    raise ValueError('Response exceeds explicit byte budget')
                # Avoid rescanning/copying the complete base64 body per packet.
                if needle in bytes(data[-256:]).replace(b'\r', b''):
                    return bytes(data).replace(b'\r', b'')
            elif self.channel.closed:
                break
            else:
                time.sleep(.01)
        raise RuntimeError('Incomplete SSH response; no artifact accepted')


def checkpoint(output, manifest):
    manifest['total_bytes'] = sum(row['bytes'] for row in manifest['files'])
    pending = output / 'manifest.json.part'
    pending.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    pending.replace(output / 'manifest.json')


def collect(shell, output, resume=None):
    root = shell.run('/bin/busybox cat /proc/self/status')
    if not re.search(rb'(?:^|\n)Uid:\s+0\s+0\s+0\s+0\n', root):
        raise RuntimeError('UID 0 not confirmed')
    proc = {}
    for name in ('modules', 'version', 'kallsyms', 'mtd', 'iomem', 'crypto'):
        proc[name] = shell.run('/bin/busybox cat /proc/' + name)
        (output / (name + '.txt')).write_bytes(proc[name])
    loaded = set(re.findall(rb'^([A-Za-z0-9_]+)\s+\d+\s+\d+\s+.*\bLive\b', proc['modules'], re.M))
    if not loaded:
        raise RuntimeError('Loaded module list not parsed')
    found = shell.run('/bin/busybox find /lib/modules')
    (output / 'module-paths.txt').write_bytes(found)
    paths = set()
    for line in found.decode('ascii', 'replace').splitlines():
        if not line.startswith('/lib/modules/') or not line.endswith('.ko'):
            continue
        relative = module_relative(line)
        if relative.stem.replace('-', '_').encode() in loaded:
            paths.add(line)
    if not paths:
        raise RuntimeError('No loaded module files located')
    prior = {}
    if resume:
        previous = json.loads((resume / 'manifest.json').read_text(encoding='utf-8'))
        for row in previous['files']:
            relative = module_relative(row['device_path'])
            if row['relative_path'] != relative.as_posix() or row['device_path'] in prior:
                raise ValueError('Invalid/duplicate resume manifest path')
            prior[row['device_path']] = row
    manifest = {'collected_at': datetime.now(timezone.utc).isoformat(), 'read_only': True,
                'module_count': len(loaded), 'candidate_files': len(paths),
                'limits': {'file_bytes': MAX_FILE, 'total_bytes': MAX_TOTAL, 'files': MAX_FILES},
                'files': [], 'skipped': [], 'sizes': {}, 'complete': False,
                'proc_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in proc.items()}}
    checkpoint(output, manifest)
    for path in sorted(paths):
        relative = module_relative(path)
        shell.run('p=' + path)
        regular = shell.run('test -f "$p" && test ! -L "$p" && echo TP_REGULAR')
        if b'\nTP_REGULAR\n' not in regular:
            manifest['skipped'].append({'path': path, 'reason': 'not a regular nonsymlink file'})
            checkpoint(output, manifest)
            continue
        size = parse_size(shell.run('/bin/busybox wc -c < "$p"'))
        manifest['sizes'][path] = size
        checkpoint(output, manifest)
        if not 0 < size <= MAX_FILE or len(manifest['files']) >= MAX_FILES or manifest['total_bytes'] + size > MAX_TOTAL:
            manifest['skipped'].append({'path': path, 'reason': 'explicit collection budget', 'bytes': size})
            checkpoint(output, manifest)
            continue
        first = parse_digest(shell.run('/usr/sbin/openssl dgst -sha256 "$p"'), path)
        destination = output / 'modules' / Path(*relative.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        reused = False
        old = prior.get(path)
        if old and old['bytes'] == size and old['sha256'] == first:
            source = resume / 'modules' / Path(*relative.parts)
            if source.is_file() and not source.is_symlink() and source.stat().st_size == size:
                if hashlib.sha256(source.read_bytes()).hexdigest() == first:
                    shutil.copyfile(source, destination)
                    reused = True
        if not reused:
            command = ('printf "\\nTP_B64_BEGIN\\n";/usr/sbin/openssl base64 -in "$p";'
                       'printf "\\nTP_B64_END\\n";/usr/sbin/openssl dgst -sha256 "$p"')
            reply = shell.run(command, budget=2 * size + 65536, timeout=180)
            data, after = decode_transfer(reply, size, first)
            if parse_digest(after, path) != first:
                raise RuntimeError('Device file changed during transfer')
            with destination.open('xb') as artifact:
                artifact.write(data)
        else:
            if parse_digest(shell.run('/usr/sbin/openssl dgst -sha256 "$p"'), path) != first:
                raise RuntimeError('Device file changed during reuse verification')
        if destination.stat().st_size != size or hashlib.sha256(destination.read_bytes()).hexdigest() != first:
            raise RuntimeError('Local artifact readback failed')
        manifest['files'].append({'device_path': path, 'relative_path': relative.as_posix(),
                                  'bytes': size, 'sha256': first, 'reused': reused,
                                  'device_before_after_and_local_match': True})
        checkpoint(output, manifest)
        print(('REVALIDATED: ' if reused else 'COLLECTED: ') + relative.as_posix() + f' ({size} bytes)', flush=True)
    after_modules = shell.run('/bin/busybox cat /proc/modules')
    (output / 'modules-after.txt').write_bytes(after_modules)
    # Addresses/reference counts can change; compare loaded names instead.
    after_loaded = set(re.findall(rb'^([A-Za-z0-9_]+)\s+\d+\s+\d+\s+.*\bLive\b', after_modules, re.M))
    captured = {PurePosixPath(row['relative_path']).stem.replace('-', '_').encode() for row in manifest['files']}
    manifest['loaded_names_stable'] = loaded == after_loaded
    manifest['loaded_without_artifact'] = sorted(name.decode() for name in loaded - captured)
    manifest['complete'] = not manifest['skipped'] and not manifest['loaded_without_artifact'] and loaded == after_loaded
    checkpoint(output, manifest)
    print(json.dumps({key: manifest[key] for key in ('module_count', 'total_bytes', 'complete', 'loaded_without_artifact')}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credentials', type=Path, required=True, help='private JSON: username, password, port')
    parser.add_argument('--host-keys', type=Path, required=True, help='private JSON: host OpenSSH public key')
    parser.add_argument('--host', default='192.168.1.1')
    parser.add_argument('--source', required=True)
    parser.add_argument('--interface', type=int, required=True, help='current Windows USB interface index')
    parser.add_argument('--output', type=Path, required=True, help='new private directory')
    parser.add_argument('--resume', type=Path, help='previous evidence directory with completed manifest entries')
    args = parser.parse_args()
    import paramiko
    credential = json.loads(args.credentials.read_text(encoding='utf-8'))
    pin = json.loads(args.host_keys.read_text(encoding='utf-8'))['host'].split()
    args.output.mkdir(parents=True, exist_ok=False)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    transport = None
    try:
        sock.settimeout(12)
        sock.setsockopt(socket.IPPROTO_IP, 31, struct.pack('!I', args.interface))
        sock.bind((args.source, 0))
        sock.connect((args.host, credential['port']))
        transport = paramiko.Transport(sock)
        transport.start_client(timeout=12)
        key = transport.get_remote_server_key()
        if key.get_name() != pin[0] or key.get_base64() != pin[1]:
            raise RuntimeError('Pinned host key mismatch; no password sent')
        transport.auth_password(credential['username'], credential['password'])
        channel = transport.open_session(timeout=12)
        channel.get_pty(term='vt100', width=240, height=40)
        channel.invoke_shell()
        collect(Shell(channel), args.output, args.resume)
        channel.sendall(b'exit\n')
    finally:
        if transport:
            transport.close()
        sock.close()


if __name__ == '__main__':
    main()
