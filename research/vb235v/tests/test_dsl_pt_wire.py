# SPDX-License-Identifier: GPL-2.0-only
import hashlib
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from dsl_pt_wire import decode_frame, decode_payload, encode_request


class DslPtWireTests(unittest.TestCase):
    def setUp(self):
        host = bytearray(192)
        struct.pack_into('>II', host, 4, 22, 1)
        host[16:20] = b'test'
        self.payload = encode_request(bytes(host))
        self.frame = bytes(12) + b'\xbe\xea' + self.payload

    def test_independent_offset_vector(self):
        self.assertEqual(len(self.payload), 204)
        self.assertEqual(self.payload[:28], bytes.fromhex(
            '75177517000100000000000000000000000000160000000100000000'))
        self.assertEqual(self.payload[28:32], b'test')
        decoded = decode_frame(self.frame)
        self.assertEqual(decoded['operation_word_be'], 22)
        self.assertIsNone(decoded['request_is_read_only'])

    def test_commands_and_addresses_hidden_by_default(self):
        decoded = decode_frame(self.frame)
        self.assertNotIn('command_ascii', decoded)
        self.assertNotIn('source_mac', decoded)
        self.assertEqual(decoded['command_sha256'], hashlib.sha256(self.payload[28:188]).hexdigest())
        self.assertEqual(decode_payload(self.payload, show_command=True)['command_ascii'], 'test')

    def test_vlan_framing_preserves_payload(self):
        for tags in [bytes.fromhex('81000001beea'), bytes.fromhex('88a8000281000001beea')]:
            frame = bytes(12) + tags + self.payload
            decoded = decode_frame(frame)
            self.assertEqual(decoded['command_sha256'], decode_payload(self.payload)['command_sha256'])

    def test_reject_wrong_channel_magic_version_and_lengths(self):
        for frame in [self.frame[:12] + b'\xbe\xed' + self.frame[14:], self.frame[:-1],
                      self.frame + bytes(4), self.frame[:14] + bytes(4) + self.frame[18:],
                      self.frame[:18] + b'\0\2' + self.frame[20:]]:
            with self.assertRaises(ValueError):
                decode_frame(frame)
        for size in (0, 191, 193):
            with self.assertRaises(ValueError):
                encode_request(bytes(size))


if __name__ == '__main__':
    unittest.main()
