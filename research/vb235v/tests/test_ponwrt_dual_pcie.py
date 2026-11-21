import sys
from pathlib import Path
import shutil
import subprocess
import unittest
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE/'tools'))
from audit_ponwrt_dual_pcie import audit_dual_dtb, DUAL_BOARD
from audit_ponwrt_pcie import audit_pcie_dtb


@unittest.skipUnless(shutil.which('dtc'),'dtc required')
class DualPcieTests(unittest.TestCase):
    def setUp(self):
        self.source=(HERE/'bringup/m64-dual-pcie/an7583-tplink_vb235v-ram-dual-pcie.dts').read_text()

    def compile(self,text):
        args=['dtc','-@','-I','dts','-O','dtb']
        for directory in ('m63-ram-pcie','m58-ram-lan','m55-ponwrt-system/overlay/target/linux/airoha/dts'):
            args+=['-i',str(HERE/'bringup'/directory)]
        return subprocess.run(args,input=text.encode(),capture_output=True,check=True).stdout

    def test_exact_dual_controller_and_efuse(self):
        result=audit_dual_dtb(self.compile(self.source))
        self.assertEqual(result['board'],DUAL_BOARD)
        self.assertEqual(result['PCIe_controllers'],2)
        self.assertEqual(result['QPHY_efuse_cells'],3)
        self.assertEqual(result['storage_controllers'],0)

    def test_previous_gate_rejects_second_host(self):
        with self.assertRaises(ValueError):
            audit_pcie_dtb(self.compile(self.source))

    def test_reject_changed_aperture_phy_and_efuse_bits(self):
        for old,new in (('0x24000000','0x20000000'),('0x1fa5e000','0x1fa8e000'),
                        ('bits = <5 5>','bits = <4 5>'),('<0 40 4>','<0 39 4>')):
            with self.subTest(new=new),self.assertRaises(ValueError):
                audit_dual_dtb(self.compile(self.source.replace(old,new)))

    def test_reject_extra_storage_and_wlan_endpoint(self):
        for extra in ('/ { nand@1fa10000 { compatible="spi-nand"; }; };',
                      '&pcie1 { wifi@0 { reg=<0 0 0 0 0>; }; };'):
            with self.subTest(extra=extra),self.assertRaises(ValueError):
                audit_dual_dtb(self.compile(self.source+'\n'+extra))


if __name__=='__main__':
    unittest.main()
