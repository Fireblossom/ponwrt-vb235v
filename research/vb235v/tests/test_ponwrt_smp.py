import sys
from pathlib import Path
import shutil
import subprocess
import unittest
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE/'tools'))
from audit_ponwrt_smp import audit_smp_dtb
from audit_ponwrt_dual_pcie import audit_dual_dtb

@unittest.skipUnless(shutil.which('dtc'),'dtc required')
class SmpTests(unittest.TestCase):
    def setUp(self):
        self.source=(HERE/'bringup/m67-smp/an7583-tplink_vb235v-ram-smp.dts').read_text()
    def compile(self,source):
        args=['dtc','-@','-I','dts','-O','dtb']
        for directory in ['m64-dual-pcie','m63-ram-pcie','m58-ram-lan','m55-ponwrt-system/overlay/target/linux/airoha/dts']:
            args+=['-i',str(HERE/'bringup'/directory)]
        return subprocess.run(args,input=source.encode(),capture_output=True,check=True).stdout
    def test_two_psci_cpus_preserve_ram_resources(self):
        r=audit_smp_dtb(self.compile(self.source))
        self.assertEqual(r['CPU_MPIDRs'],[0,1])
        self.assertEqual(r['PCIe_controllers'],2)
        self.assertEqual(r['storage_controllers'],0)
    def test_previous_gate_rejects_smp(self):
        with self.assertRaises(ValueError):audit_dual_dtb(self.compile(self.source))
    def test_reject_duplicate_mpidr_or_wrong_start_method(self):
        for a,b in [('reg = <1>','reg = <0>'),('enable-method = "psci"','enable-method = "spin-table"')]:
            with self.subTest(b=b),self.assertRaises(ValueError):audit_smp_dtb(self.compile(self.source.replace(a,b)))
    def test_reject_wrong_cluster_mapping(self):
        with self.assertRaises(ValueError):audit_smp_dtb(self.compile(self.source.replace('core1 { cpu = <&cpu1>','core1 { cpu = <&cpu0>')))
    def test_reject_extra_cpu_and_storage(self):
        for extra in ['cpus { cpu@4 { device_type="cpu"; compatible="arm,cortex-a53"; reg=<4>; enable-method="psci"; }; };',
                      'nand@1fa10000 { compatible="econet,ecnt-nand"; };']:
            with self.subTest(extra=extra),self.assertRaises(ValueError):audit_smp_dtb(self.compile(self.source+'\n/ { '+extra+' };'))

if __name__=='__main__':unittest.main()
