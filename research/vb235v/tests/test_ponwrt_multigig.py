# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import shutil,subprocess,sys,unittest
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE/'tools'))
from audit_ponwrt_multigig import audit_multigig_dtb
from audit_ponwrt_accel import audit_accel_dtb
@unittest.skipUnless(shutil.which('dtc'),'dtc required')
class MultigigRamTests(unittest.TestCase):
    def setUp(self):self.source=(HERE/'bringup/m71-dual-2p5g/an7583-tplink_vb235v-ram-multigig.dts').read_text()
    def compile(self,source):
        args=['dtc','-@','-I','dts','-O','dtb']
        for name in ['m71-dual-2p5g','m70-integrated-accel','m68-npu','m67-smp','m64-dual-pcie','m63-ram-pcie','m58-ram-lan','m55-ponwrt-system/overlay/target/linux/airoha/dts']:
            args+=['-i',str(HERE/'bringup'/name)]
        return subprocess.run(args,input=source.encode(),capture_output=True,check=True).stdout
    def test_exact_two_phy_two_pcs_and_three_mac_paths(self):
        report=audit_multigig_dtb(self.compile(self.source))
        self.assertEqual(report['external_PHY_nodes'],2)
        self.assertEqual(report['PCS_nodes'],2)
        self.assertEqual(report['CPU_count'],2)
        self.assertEqual(report['storage_controllers'],0)
    def test_prior_gate_rejects_new_resources(self):
        with self.assertRaises(ValueError):audit_accel_dtb(self.compile(self.source))
    def test_reject_phy_swap_reset_or_rate_change(self):
        for old,new in [('<14>','<13>'),('<&scuclk 48>','<&scuclk 47>'),('pon-ethernet-mode = "2500base-x"','pon-ethernet-mode = "xfi"'),
                        ('max-speed = <2500>;', 'max-speed = <2500>; airoha,pnswap-rx;'),('max-speed = <2500>;', 'max-speed = <2500>; airoha,pnswap-tx;')]:
            with self.subTest(new=new),self.assertRaises(ValueError):audit_multigig_dtb(self.compile(self.source.replace(old,new)))
    def test_reject_extra_phy_or_switch_port(self):
        for extra in ['&mdio0 { ethernet-phy@d {reg=<13>;}; };','&{/switch@1fb58000/ports} { port@4 {reg=<4>;}; };']:
            with self.assertRaises(ValueError):audit_multigig_dtb(self.compile(self.source+'\n'+extra))
if __name__=='__main__':unittest.main()
