# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

RESEARCH = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RESEARCH / 'tools'))
from audit_uart_bringup import check_config, check_dtb


class UartBringupTest(unittest.TestCase):
    def test_flash_or_concrete_reset_driver_fails_config_gate(self):
        fragment = (RESEARCH / 'bringup/uart-only.config').read_text()
        config = fragment.replace('CONFIG_INITRAMFS_SOURCE=""', 'CONFIG_INITRAMFS_SOURCE="/private/initramfs.list"') + '\nCONFIG_ARM64=y\n'
        self.assertTrue(check_config(config)['embedded_initramfs_configured'])
        with self.assertRaisesRegex(ValueError, 'MTD'):
            check_config(config.replace('CONFIG_MTD=n', 'CONFIG_MTD=y'))
        with self.assertRaisesRegex(ValueError, 'POWER_RESET_SYSCON'):
            check_config(config + 'CONFIG_POWER_RESET_SYSCON=y\n')

    def compile(self, source):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        source_path = Path(directory.name) / 'board.dts'
        output = Path(directory.name) / 'board.dtb'
        source_path.write_text(source)
        subprocess.run([shutil.which('dtc'), '-I', 'dts', '-O', 'dtb', '-o', str(output), str(source_path)],
                       check=True, capture_output=True)
        return output.read_bytes()

    @unittest.skipUnless(shutil.which('dtc'), 'dtc required for independent source compilation')
    def test_compiled_development_tree_passes(self):
        source = (RESEARCH / 'bringup/vb235v-uart-only.dts').read_text()
        self.assertTrue(check_dtb(self.compile(source))['no_storage_network_gpio_nodes'])

    @unittest.skipUnless(shutil.which('dtc'), 'dtc required for independent source compilation')
    def test_extra_storage_node_even_disabled_is_rejected(self):
        source = (RESEARCH / 'bringup/vb235v-uart-only.dts').read_text()
        left, right = source.rsplit('};', 1)
        modified = left + 'nand@1fa10000 { compatible = "spi-nand"; status = "disabled"; };\n};' + right
        with self.assertRaisesRegex(ValueError, 'DT nodes'):
            check_dtb(self.compile(modified))

    @unittest.skipUnless(shutil.which('dtc'), 'dtc required for independent source compilation')
    def test_changed_console_clock_is_rejected(self):
        source = (RESEARCH / 'bringup/vb235v-uart-only.dts').read_text()
        modified = re.sub(r'clock-frequency\s*=\s*<1843200>;', 'clock-frequency = <7372800>;', source)
        self.assertNotEqual(source, modified)
        with self.assertRaisesRegex(ValueError, 'clock-frequency'):
            check_dtb(self.compile(modified))


if __name__ == '__main__':
    unittest.main()
