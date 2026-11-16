# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from uart_artifact_inventory import check_cpio, check_image, check_init


def archive(init=b'own-init', console_minor=1):
    result = bytearray()
    for name, mode, data, major, minor in (
            ('dev', 0o40755, b'', 0, 0), ('dev/console', 0o20600, b'', 5, console_minor),
            ('init', 0o100755, init, 0, 0), ('TRAILER!!!', 0, b'', 0, 0)):
        encoded = name.encode() + b'\0'
        fields = [1, mode, 0, 0, 1, 0, len(data), 0, 0, major, minor, len(encoded), 0]
        result += b'070701' + ''.join(f'{value:08x}' for value in fields).encode() + encoded
        result += bytes((-len(result)) % 4)
        result += data
        result += bytes((-len(result)) % 4)
    return bytes(result)


class UartArtifactTest(unittest.TestCase):
    def test_embedded_init_identity_and_console_number_are_enforced(self):
        self.assertTrue(check_cpio(archive(), b'own-init')['embedded_init_matches'])
        for data, init in ((archive(), b'other-init'), (archive(console_minor=2), b'own-init'), (archive()[:-1], b'own-init')):
            with self.assertRaises(ValueError):
                check_cpio(data, init)

    def test_arm64_image_header_is_not_accepted_as_elf_or_arbitrary_data(self):
        image = struct.pack('<IIQQQQQQII', 0, 0, 0x80000, 4096, 0, 0, 0, 0, 0x644d5241, 0)
        self.assertTrue(check_image(image)['arm64_magic_valid'])
        with self.assertRaises(ValueError):
            check_image(bytes(64))
        with self.assertRaises(ValueError):
            check_init(image)


if __name__ == '__main__':
    unittest.main()
