# SPDX-License-Identifier: GPL-2.0-only
"""Offline transfer-integrity and resume regression tests, with a fake stock shell."""
import base64
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import collect_stock_modules as collector


class FakeShell:
    def __init__(self, data=b'module bytes'):
        self.path = '/lib/modules/example.ko'
        self.data = data
        self.transfers = 0
        self.digest_reads = 0
        self.mutate = False

    def run(self, command, **kwargs):
        if command == '/bin/busybox cat /proc/self/status':
            return b'\nUid:\t0\t0\t0\t0\n'
        if command == '/bin/busybox cat /proc/modules':
            return b'example 100 0 - Live 0x0000\n'
        if command.startswith('/bin/busybox cat /proc/'):
            return b'private proc data\n'
        if command == '/bin/busybox find /lib/modules':
            return self.path.encode() + b'\n'
        if command.startswith('p='):
            return b''
        if command.startswith('test -f'):
            return b'\nTP_REGULAR\n'
        if command.startswith('/bin/busybox wc'):
            return str(len(self.data)).encode() + b'\n'
        digest = hashlib.sha256(self.data).hexdigest()
        if command.startswith('/usr/sbin/openssl dgst'):
            self.digest_reads += 1
            if self.mutate and self.digest_reads > 1:
                digest = '0' * 64
            return f'SHA256({self.path})= {digest}\n'.encode()
        if 'base64 -in' in command:
            self.transfers += 1
            return (b'\nTP_B64_BEGIN\n' + base64.b64encode(self.data)
                    + b'\nTP_B64_END\n' + f'SHA256({self.path})= {digest}\n'.encode())
        raise AssertionError(command)


class StockCollectionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def output(self, name):
        result = self.root / name
        result.mkdir()
        return result

    def test_paths_reject_traversal_and_shell_metacharacters(self):
        for path in ('/lib/modules/../secret.ko', '/lib/modules/a;id.ko',
                     '/lib/modules//a.ko', '/tmp/a.ko', '/lib/modules/./a.ko'):
            with self.subTest(path=path), self.assertRaises(ValueError):
                collector.module_relative(path)

    def test_transfer_rejects_truncation_corruption_and_wrong_size(self):
        digest = hashlib.sha256(b'abc').hexdigest()
        valid = b'\nTP_B64_BEGIN\nYWJj\nTP_B64_END\n'
        self.assertEqual(collector.decode_transfer(valid, 3, digest)[0], b'abc')
        for reply, size in ((valid[:-10], 3), (valid.replace(b'YWJj', b'YWJk'), 3), (valid, 4)):
            with self.subTest(reply=reply, size=size), self.assertRaises(ValueError):
                collector.decode_transfer(reply, size, digest)

    def test_completed_resume_is_rehashed_locally_and_on_device(self):
        first = self.output('first')
        collector.collect(FakeShell(), first)
        second = self.output('second')
        shell = FakeShell()
        collector.collect(shell, second, first)
        manifest = json.loads((second / 'manifest.json').read_text())
        self.assertTrue(manifest['complete'])
        self.assertTrue(manifest['files'][0]['reused'])
        self.assertEqual(shell.transfers, 0)
        self.assertEqual(shell.digest_reads, 2)
        (first / 'modules/example.ko').write_bytes(b'bad artifact')
        shell = FakeShell()
        collector.collect(shell, self.output('third'), first)
        self.assertEqual(shell.transfers, 1)

    def test_device_change_during_reuse_does_not_checkpoint_the_file(self):
        first = self.output('before')
        collector.collect(FakeShell(), first)
        shell = FakeShell()
        shell.mutate = True
        after = self.output('after')
        with self.assertRaises(RuntimeError):
            collector.collect(shell, after, first)
        self.assertEqual(json.loads((after / 'manifest.json').read_text())['files'], [])

    def test_exact_oversize_is_recorded_without_transfer(self):
        shell = FakeShell()
        output = self.output('limited')
        with patch.object(collector, 'MAX_FILE', 4):
            collector.collect(shell, output)
        manifest = json.loads((output / 'manifest.json').read_text())
        self.assertEqual(manifest['sizes'][shell.path], len(shell.data))
        self.assertFalse(manifest['complete'])
        self.assertEqual(shell.transfers, 0)


if __name__ == '__main__':
    unittest.main()
