import sys
from pathlib import Path
import shutil
import subprocess
import unittest
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE/'tools'))
from audit_ponwrt_npu import audit_npu_dtb
from audit_ponwrt_smp import audit_smp_dtb
@unittest.skipUnless(shutil.which('dtc'),'dtc required')
class NpuRamTests(unittest.TestCase):
    def setUp(self):self.source=(HERE/'bringup/m68-npu/an7583-tplink_vb235v-ram-npu.dts').read_text()
    def compile(self,s):
        args=['dtc','-@','-I','dts','-O','dtb']
        for d in ['m67-smp','m64-dual-pcie','m63-ram-pcie','m58-ram-lan','m55-ponwrt-system/overlay/target/linux/airoha/dts']:
            args+=['-i',str(HERE/'bringup'/d)]
        return subprocess.run(args,input=s.encode(),capture_output=True,check=True).stdout
    def test_exact_six_npu_cores_two_arm_cpus_and_reservation(self):
        r=audit_npu_dtb(self.compile(self.source))
        self.assertEqual(r['CPU_count'],2)
        self.assertEqual(r['NPU_processing_cores'],6)
        self.assertEqual(r['NPU_reserved_bytes'],10*1024*1024)
        self.assertEqual(r['storage_controllers'],0)
    def test_smp_gate_rejects_new_hardware(self):
        with self.assertRaises(ValueError):audit_smp_dtb(self.compile(self.source))
    def test_reject_wrong_interrupt_layout_or_code_heap(self):
        for a,b in [('<0 134 4>','<0 103 4>'),('0 0xa00000','0 0x100000'),('an7583-v2p','legacy')]:
            with self.subTest(b=b),self.assertRaises(ValueError):audit_npu_dtb(self.compile(self.source.replace(a,b)))
    def test_reject_firmware_fallback_or_extra_device(self):
        for s in [self.source.replace('vb235v/stock-npu-rv32.bin','airoha/an7583_npu_rv32.bin'),
                  self.source+'\n/ { nand@1fa10000 {compatible="econet,ecnt-nand";}; };']:
            with self.assertRaises(ValueError):audit_npu_dtb(self.compile(s))
if __name__=='__main__':unittest.main()
