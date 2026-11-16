# SPDX-License-Identifier: GPL-2.0-only
"""Compile the reference SoC DTS and apply the disabled PCS overlay offline."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

from fdt_board_inventory import parse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference-dts',type=Path,required=True)
    parser.add_argument('--kernel-include',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    commands = {n:shutil.which(n) for n in ('cpp','dtc','fdtoverlay')}
    if not all(commands.values()):
        raise ValueError('cpp/dtc/fdtoverlay are required')
    ref = args.reference_dts/'an7583.dtsi'
    if hashlib.sha256(ref.read_bytes()).hexdigest() != '372c8befa091ad1d725eab2056d767fa304d99f4a7735e6bce503a5c4b9fa227':
        raise ValueError('Reference DTS differs from the reviewed pinned version')
    overlay = Path(__file__).resolve().parents[1]/'bringup/vb235v-pcs-ethernet-disabled.dtso'
    warnings = {}
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root/'base.dts').write_text('/dts-v1/;\n#include "an7583.dtsi"\n/ { model="Offline PCS overlay check"; compatible="test,pcs-overlay", "airoha,an7583"; };\n')
        with (root/'base.preprocessed.dts').open('wb') as stream:
            subprocess.run([commands['cpp'],'-nostdinc','-undef','-D__DTS__','-x','assembler-with-cpp',
                            '-I',str(args.reference_dts),'-I',str(args.kernel_include),str(root/'base.dts')],check=True,stdout=stream)
        for name, source in (('base',root/'base.preprocessed.dts'),('profile',overlay)):
            result = subprocess.run([commands['dtc'],'-@','-I','dts','-O','dtb','-o',str(root/(name+'.dtb')),str(source)],capture_output=True,text=True)
            if result.returncode:
                raise RuntimeError('DTC failed: '+result.stderr[:2000])
            warnings[name] = len(result.stderr.splitlines())
        subprocess.run([commands['fdtoverlay'],'-i',str(root/'base.dtb'),'-o',str(root/'applied.dtb'),str(root/'profile.dtb')],check=True)
        before,_ = parse((root/'base.dtb').read_bytes())
        after,_ = parse((root/'applied.dtb').read_bytes())
    if set(before) != set(after):
        raise ValueError('Overlay changed the node inventory')
    changed = {(path,key) for path in before for key in set(before[path]) | set(after[path])
               if before[path].get(key) != after[path].get(key)}
    expected = {('/soc/pcs@1fa08000','airoha,pon-ethernet-mode'),('/soc/pcs@1fa08000','status'),
                ('/soc/ethernet@1fb50000/ethernet@2','phy-mode')}
    if changed != expected:
        raise ValueError('Unexpected overlay property changes')
    disabled = ('/soc/pcs@1fa08000','/soc/ethernet@1fb50000/ethernet@2',
                '/soc/ethernet@1fb50000','/soc/npu@1e900000')
    if any(after[path].get('status') != b'disabled\0' for path in disabled):
        raise ValueError('Development overlay enables a controlled node')
    report = {'reference_dtsi_sha256':hashlib.sha256(ref.read_bytes()).hexdigest(),
              'overlay_sha256':hashlib.sha256(overlay.read_bytes()).hexdigest(),
              'full_reference_dtb_nodes':len(before),'overlay_applied':True,
              'changed_properties':[{'path':p,'property':k} for p,k in sorted(changed)],
              'dtc_diagnostic_line_counts':warnings,
              'pcs_mac_parent_ethernet_and_npu_disabled':True,'hardware_access':False}
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(report,stream,indent=2)
        stream.write('\n')
    print('Overlay applied to full '+str(len(before))+'-node reference; PCS/MAC/Ethernet/NPU remain disabled')


if __name__ == '__main__':
    main()
