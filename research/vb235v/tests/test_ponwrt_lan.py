# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / 'tools'))
from audit_ponwrt_lan import audit_lan_dtb, audit_lan_config, LAN_BOARD
from audit_ponwrt_ram import audit_dtb


class PonWrtLanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dtc = shutil.which('dtc')
        if not cls.dtc:
            raise unittest.SkipTest('Real DTC required')
        cls.source = (BASE / 'bringup/m58-ram-lan/an7583-tplink_vb235v-ram-lan.dts').read_text()

    def compile(self, source):
        result = subprocess.run([self.dtc, '-@', '-I', 'dts', '-O', 'dtb', '-i',
            str(BASE / 'bringup/m55-ponwrt-system/overlay/target/linux/airoha/dts')],
            input=source.encode(), check=True, capture_output=True)
        return result.stdout

    def test_single_reviewed_port_and_inherited_RAM_boundaries(self):
        result = audit_lan_dtb(self.compile(self.source))
        self.assertEqual(result['board'], LAN_BOARD)
        self.assertEqual(result['admitted_switch_ports'], [3, 6])
        self.assertEqual(result['test_PHY_address'], 11)
        self.assertEqual(result['storage_controllers'], 0)

    def test_original_controller_free_gate_still_rejects_LAN(self):
        with self.assertRaises(ValueError):
            audit_dtb(self.compile(self.source))

    def test_reject_unreviewed_devices(self):
        for extra in ('nand@1fa10000 { compatible="spi-nand"; status="disabled"; };',
                      'pcie@20000000 { compatible="airoha,an7583-pcie"; };',
                      'npu@1e900000 { compatible="airoha,an7583-npu"; };'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                audit_lan_dtb(self.compile(self.source + '\n/ { ' + extra + ' };\n'))

    def test_reject_resource_or_PHY_changes(self):
        for old, new in [('reg = <11>', 'reg = <12>'), ('0x1fb54000', '0x1fa10000'),
                         ('<0 209 4>', '<0 208 4>'), ('<&scuclk 42>', '<&scuclk 43>')]:
            with self.subTest(change=new), self.assertRaises(ValueError):
                audit_lan_dtb(self.compile(self.source.replace(old, new)))

    def test_native_LAN_does_not_bypass_storage_config_gate(self):
        required = ['ARM64', 'SERIAL_OF_PLATFORM', 'BLK_DEV_INITRD', 'PROC_FS', 'SYSFS', 'TMPFS',
                    'NET_AIROHA', 'NET_AIROHA_NPU', 'NET_DSA', 'NET_DSA_MT7530',
                    'NET_DSA_MT7530_MMIO', 'MEDIATEK_GE_SOC_PHY']
        content = ''.join('CONFIG_' + name + '=y\n' for name in required)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'config'
            path.write_text(content)
            self.assertTrue(audit_lan_config(path))
            path.write_text(content + 'CONFIG_MTD_NAND_MTK_BMT=y\n')
            with self.assertRaisesRegex(ValueError, 'MTD_NAND_MTK_BMT'):
                audit_lan_config(path)


if __name__ == '__main__':
    unittest.main()
