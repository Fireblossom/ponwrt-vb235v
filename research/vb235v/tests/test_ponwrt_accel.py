# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import shutil,subprocess,sys,unittest
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE/'tools'))
from audit_ponwrt_accel import audit_accel_dtb
from audit_ponwrt_npu import audit_npu_dtb

@unittest.skipUnless(shutil.which('dtc'),'dtc required')
class AccelerationRamTests(unittest.TestCase):
    def setUp(self):self.source=(HERE/'bringup/m70-integrated-accel/an7583-tplink_vb235v-ram-accel.dts').read_text()
    def compile(self,source):
        args=['dtc','-@','-I','dts','-O','dtb']
        for name in ['m70-integrated-accel','m68-npu','m67-smp','m64-dual-pcie','m63-ram-pcie','m58-ram-lan','m55-ponwrt-system/overlay/target/linux/airoha/dts']:
            args+=['-i',str(HERE/'bringup'/name)]
        return subprocess.run(args,input=source.encode(),capture_output=True,check=True).stdout
    def test_exact_crypto_and_empty_discovery_bus_keep_storage_excluded(self):
        result=audit_accel_dtb(self.compile(self.source))
        self.assertEqual(result['CPU_count'],2)
        self.assertEqual(result['NPU_processing_cores'],6)
        self.assertEqual(result['storage_controllers'],0)
    def test_old_gate_rejects_additional_peripherals(self):
        with self.assertRaises(ValueError):audit_npu_dtb(self.compile(self.source))
    def test_reject_wrong_crypto_irq_address_or_mdio_clock(self):
        for old,new in [('<0 44 4>','<0 45 4>'),('0x1fb70000 0','0x1fb71000 0'),('<&scuclk 9>','<&scuclk 8>')]:
            with self.subTest(new=new),self.assertRaises(ValueError):audit_accel_dtb(self.compile(self.source.replace(old,new)))
    def test_no_external_phy_or_extra_storage_admitted(self):
        for extra in ['&mdio0 { ethernet-phy@e {reg=<14>;}; };',
                      '/ { nand@1fa10000 {compatible="spi-nand";}; };']:
            with self.assertRaises(ValueError):audit_accel_dtb(self.compile(self.source+'\n'+extra))

if __name__=='__main__':unittest.main()
