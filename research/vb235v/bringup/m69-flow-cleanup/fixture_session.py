# SPDX-License-Identifier: GPL-2.0-only
"""Pinned RAM-development SSH session, bound only to the isolated USB LAN."""
from pathlib import Path
import json, socket, struct, time
import paramiko


class Session:
    def __init__(self, connection):
        connection=Path(connection).resolve(strict=True)
        config=json.loads(connection.read_text(encoding='utf-8'))
        self.interface_index=config['Windows_interface_index']
        assert isinstance(self.interface_index,int) and 0<self.interface_index<65536
        assert config['host_key'][0]=='ssh-ed25519'
        keypath=Path(config['private_key'])
        if not keypath.is_absolute():keypath=connection.parent/keypath
        self.sock=socket.socket();self.sock.settimeout(15)
        self.bind_interface(self.sock);self.sock.bind(('192.168.235.2',0))
        self.sock.connect(('192.168.235.1',22))
        self.transport=paramiko.Transport(self.sock);self.transport.start_client(timeout=15)
        host=self.transport.get_remote_server_key()
        assert [host.get_name(),host.get_base64()]==config['host_key'],'SSH host pin mismatch'
        self.transport.auth_publickey('root',paramiko.Ed25519Key.from_private_key_file(str(keypath)))
        board=config.get('board','tplink,vb235v-ram-npu-development')
        assert board in ['tplink,vb235v-ram-npu-development','tplink,vb235v-ram-accel-development',
                         'tplink,vb235v-ram-multigig-development']
        assert self.run('id -u; uname -r; cat /tmp/sysinfo/board_name').splitlines()==[b'0',b'6.18.60',board.encode()]
        assert b'tmpfs / tmpfs' in self.run('cat /proc/mounts')

    def bind_interface(self,sock):
        # Windows IP_UNICAST_IF takes a network-byte-order interface index.
        import os
        assert os.name=='nt','This physical USB fixture currently supports Windows only'
        sock.setsockopt(socket.IPPROTO_IP,31,struct.pack('!I',self.interface_index))

    def run(self, command, timeout=30, limit=1024*1024, check=True):
        channel = self.transport.open_session(timeout=10)
        channel.settimeout(timeout)
        channel.exec_command(command)
        data, errors = bytearray(), bytearray()
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            while channel.recv_ready(): data.extend(channel.recv(65536))
            while channel.recv_stderr_ready(): errors.extend(channel.recv_stderr(65536))
            assert len(data)+len(errors) <= limit
            if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                code = channel.recv_exit_status()
                if check and code: raise RuntimeError('Native command failed, status '+str(code)+': '+errors.decode(errors='replace'))
                return bytes(data) if check else (code, bytes(data), bytes(errors))
            time.sleep(.01)
        channel.close()
        raise TimeoutError('Native SSH command timeout')

    def put(self, data, path, timeout=60):
        assert path.startswith('/tmp/') or path.startswith('/lib/firmware/')
        assert all(c.isalnum() or c in '/-_.+' for c in path)
        channel = self.transport.open_session(timeout=10)
        channel.settimeout(timeout)
        channel.exec_command('umask 077; cat > '+path)
        channel.sendall(data); channel.shutdown_write()
        deadline = time.monotonic()+timeout
        while not channel.exit_status_ready() and time.monotonic() < deadline: time.sleep(.01)
        assert channel.exit_status_ready() and channel.recv_exit_status() == 0
        channel.close()

    def close(self):
        self.transport.close(); self.sock.close()
