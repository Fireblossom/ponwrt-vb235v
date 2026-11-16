# SPDX-License-Identifier: GPL-2.0-only
"""Compile and inspect the disabled development PCS overlay."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from fdt_board_inventory import parse
from check_pcs_profile import source


class PcsOverlayTest(unittest.TestCase):
    def test_unreviewed_c_source_is_rejected_before_host_compilation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'unreviewed.c'
            path.write_text('int arbitrary_function(void) { return 0; }\n')
            with self.assertRaisesRegex(ValueError,'outside the reviewed M18 snapshot'):
                source(path,'candidate')

    @unittest.skipUnless(shutil.which('dtc'),'host dtc required')
    def test_profile_and_mac_are_disabled_without_other_resource_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory)/'profile.dtbo'
            subprocess.run([shutil.which('dtc'),'-@','-I','dts','-O','dtb','-o',str(target),
                            str(ROOT/'bringup/vb235v-pcs-ethernet-disabled.dtso')],check=True,capture_output=True)
            nodes,_ = parse(target.read_bytes())
        self.assertEqual(set(nodes),{'/','/fragment@0','/fragment@0/__overlay__',
                                     '/fragment@1','/fragment@1/__overlay__'})
        self.assertEqual(nodes['/fragment@0']['target-path'],b'/soc/pcs@1fa08000\0')
        self.assertEqual(nodes['/fragment@1']['target-path'],b'/soc/ethernet@1fb50000/ethernet@2\0')
        self.assertEqual(nodes['/fragment@0/__overlay__'],
                         {'airoha,pon-ethernet-mode':b'usxgmii\0','status':b'disabled\0'})
        self.assertEqual(nodes['/fragment@1/__overlay__'],
                         {'phy-mode':b'usxgmii\0','status':b'disabled\0'})


if __name__ == '__main__':
    unittest.main()
