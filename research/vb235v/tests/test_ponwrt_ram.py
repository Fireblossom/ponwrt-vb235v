# SPDX-License-Identifier: GPL-2.0-only
import os
import lzma
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'tools'))
from audit_ponwrt_ram import audit_dtb, audit_fit


class PonWrtRamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dtc = shutil.which('dtc')
        cls.mkimage = os.environ.get('VB235V_MKIMAGE') or shutil.which('mkimage')
        if not cls.dtc:
            raise unittest.SkipTest('DTC required for compiled device-tree validation')
        cls.source = (BASE / 'bringup/m55-ponwrt-system/overlay/target/linux/airoha/dts/an7583-tplink_vb235v-ram.dts').read_text()

    def compile_dtb(self, source, symbols=False):
        result = subprocess.run([self.dtc, *(['-@'] if symbols else []), '-I', 'dts', '-O', 'dtb'], input=source.encode(),
                                capture_output=True, check=True)
        return result.stdout

    def test_real_compiled_board_and_protected_reservations(self):
        result = audit_dtb(self.compile_dtb(self.source))
        self.assertEqual(result['storage_controllers'], 0)
        self.assertEqual(result['dt_nodes'], 16)

    def test_allow_only_exact_compiler_symbol_metadata(self):
        result = audit_dtb(self.compile_dtb(self.source, symbols=True))
        self.assertTrue(result['compiler_symbol_metadata'])
        self.assertEqual(result['dt_nodes'], 17)
        with self.assertRaisesRegex(ValueError, 'symbol metadata'):
            audit_dtb(self.compile_dtb(self.source.replace('uart0:', 'extra: uart0:'), symbols=True))

    def test_reject_even_disabled_storage_node(self):
        changed = self.source + '\n/ { nand@1fa10000 { compatible="spi-nand"; status="disabled"; }; };\n'
        with self.assertRaisesRegex(ValueError, 'Unexpected DT node'):
            audit_dtb(self.compile_dtb(changed))

    def test_reject_wrong_uart_or_reservation_or_bootargs(self):
        for old, new in [('1843200', '7372800'), ('0x100000>', '0xa00000>'),
                         ('rdinit=/init', 'ubi.mtd=system rdinit=/init')]:
            with self.subTest(change=new), self.assertRaises(ValueError):
                audit_dtb(self.compile_dtb(self.source.replace(old, new)))

    def make_fit(self, memory_bytes=0x1000000, extra_image='', configuration=''):
        if not self.mkimage:
            self.skipTest('mkimage required for real FIT framing')
        with tempfile.TemporaryDirectory() as temporary:
            t = Path(temporary)
            (t / 'board.dtb').write_bytes(self.compile_dtb(self.source))
            # Host-only framing fixture: deliberately never a bootable kernel.
            image = bytearray(4096)
            image[56:60] = b'ARMd'
            struct.pack_into('<Q', image, 16, memory_bytes)
            (t / 'Image').write_bytes(image)
            its = '''/dts-v1/;
/ { description="OFFLINE TEST ONLY"; #address-cells=<1>;
 images {
  kernel { data=/incbin/("Image"); type="kernel"; arch="arm64"; os="linux";
   compression="none"; load=<0x80200000>; entry=<0x80200000>; hash-1 { algo="sha256"; }; };
  fdt { data=/incbin/("board.dtb"); type="flat_dt"; arch="arm64";
   compression="none"; hash-1 { algo="sha256"; }; };
  EXTRA_IMAGE
 };
 configurations { default="conf"; conf { kernel="kernel"; fdt="fdt"; CONFIGURATION }; };
};
'''.replace('EXTRA_IMAGE', extra_image).replace('CONFIGURATION', configuration)
            (t / 'image.its').write_text(its)
            subprocess.run([self.mkimage, '-f', 'image.its', 'image.itb'], cwd=t,
                           capture_output=True, check=True)
            return (t / 'image.itb').read_bytes()

    def test_actual_mkimage_hashes_and_memory_admission(self):
        report = audit_fit(self.make_fit())
        self.assertTrue(report['fit_payload_hashes_verified'])
        self.assertFalse(report['userspace_contents_verified'])
        self.assertFalse(report['hardware_boot_validated'])
        with self.assertRaisesRegex(ValueError, 'reservation'):
            audit_fit(self.make_fit(memory_bytes=0x4000000))
        with self.assertRaisesRegex(ValueError, 'declared memory size'):
            audit_fit(self.make_fit(memory_bytes=1024))

    def test_reject_corrupt_payload_and_extra_payload_roles(self):
        value = bytearray(self.make_fit())
        location = value.find(b'ARMd')
        self.assertGreater(location, 0)
        value[location] ^= 1
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            audit_fit(bytes(value))
        with self.assertRaisesRegex(ValueError, 'extra FIT payload'):
            audit_fit(self.make_fit(configuration='ramdisk="fdt";'))

    def test_actual_board_fit_generation_step(self):
        if not self.mkimage:
            self.skipTest('mkimage required')
        script = BASE / 'bringup/m55-ponwrt-system/overlay/target/linux/airoha/image/mkits-vb235v.py'
        with tempfile.TemporaryDirectory(prefix='vb235v-fit-build-') as temporary:
            t = Path(temporary)
            image = bytearray(4096)
            image[56:60] = b'ARMd'
            struct.pack_into('<Q', image, 16, 0x100000)
            (t / 'kernel.lzma').write_bytes(lzma.compress(image, format=lzma.FORMAT_ALONE))
            (t / 'board.dtb').write_bytes(self.compile_dtb(self.source))
            subprocess.run([sys.executable, str(script), str(t / 'kernel.lzma'),
                            str(t / 'board.dtb'), str(t / 'image.its')], check=True,
                           capture_output=True)
            subprocess.run([self.mkimage, '-f', 'image.its', 'image.itb'], cwd=t,
                           check=True, capture_output=True)
            report = audit_fit((t / 'image.itb').read_bytes())
            self.assertTrue(report['fit_payload_hashes_verified'])
            self.assertEqual(report['kernel_uncompressed_bytes'], 4096)


if __name__ == '__main__':
    unittest.main()
