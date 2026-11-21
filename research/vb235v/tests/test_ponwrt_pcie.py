import sys
from pathlib import Path
import shutil
import subprocess
import unittest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / 'tools'))
from audit_ponwrt_pcie import audit_pcie_dtb, PCIE_BOARD
from audit_ponwrt_lan import audit_lan_dtb


@unittest.skipUnless(shutil.which('dtc'), 'dtc required')
class PcieRamTests(unittest.TestCase):
    def compile(self, text):
        args = ['dtc', '-@', '-I', 'dts', '-O', 'dtb']
        for directory in ('m58-ram-lan', 'm55-ponwrt-system/overlay/target/linux/airoha/dts'):
            args += ['-i', str(HERE / 'bringup' / directory)]
        return subprocess.run(args, input=text.encode(), check=True, capture_output=True).stdout

    def setUp(self):
        self.source = (HERE / 'bringup/m63-ram-pcie/an7583-tplink_vb235v-ram-pcie.dts').read_text()

    def test_exact_one_lane_and_no_storage(self):
        result = audit_pcie_dtb(self.compile(self.source))
        self.assertEqual(result['board'], PCIE_BOARD)
        self.assertEqual(result['PCIe_controllers'], 1)
        self.assertEqual(result['PCIe_lanes'], 1)
        self.assertEqual(result['storage_controllers'], 0)

    def test_previous_lan_gate_rejects_new_peripherals(self):
        with self.assertRaises(ValueError):
            audit_lan_dtb(self.compile(self.source))

    def test_wrong_aperture_phy_reset_irq_and_extra_lane_rejected(self):
        for old, new in (('0x20000000', '0x30000000'), ('0x1fc7f000', '0x1fa7f000'),
                         ('<&scuclk 44>', '<&scuclk 45>'), ('<0 39 4>', '<0 40 4>'),
                         ('num-lanes = <1>', 'num-lanes = <2>')):
            with self.subTest(new=new), self.assertRaises(ValueError):
                audit_pcie_dtb(self.compile(self.source.replace(old, new)))

    def test_extra_device_or_wlan_child_rejected(self):
        for extra in ('/ { nand@1fa10000 { compatible="spi-nand"; }; };',
                      '&pcie0 { wifi@0 { reg=<0 0 0 0 0>; }; };'):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                audit_pcie_dtb(self.compile(self.source + '\n' + extra))


if __name__ == '__main__':
    unittest.main()
