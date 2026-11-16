# SPDX-License-Identifier: GPL-2.0-only
"""Validate the development PON PCS binding with disabled synthetic examples."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binding', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    consumer = args.binding.parents[2] / 'nvmem/nvmem-consumer.yaml'
    if not consumer.is_file():
        raise ValueError('Kernel NVMEM consumer schema is required')
    tools = {n:shutil.which(n) for n in ('dtc','dt-doc-validate','dt-mk-schema','dt-validate')}
    if not all(tools.values()):
        raise ValueError('Host dtc/dtschema tools are required')
    meta = subprocess.run([tools['dt-doc-validate'],str(args.binding)],capture_output=True,text=True)
    if meta.returncode or meta.stdout.strip() or meta.stderr.strip():
        raise RuntimeError('Binding meta-schema failed: '+meta.stdout+meta.stderr)
    cases = [('default_optical',None,'airoha,an7583-pcs-pon',8,True),
             ('ethernet_usxgmii','"usxgmii"','airoha,an7583-pcs-pon',8,True),
             ('unsupported_mode','"sgmii"','airoha,an7583-pcs-pon',8,False),
             ('wrong_soc','"usxgmii"','airoha,an7581-pcs-pon',8,False),
             ('wrong_block','"usxgmii"','airoha,an7583-pcs-eth',8,False),
             ('multiple_strings','"usxgmii", "extra"','airoha,an7583-pcs-pon',8,False),
             ('missing_window','"usxgmii"','airoha,an7583-pcs-pon',7,False)]
    regs = [(0x1fa08000,0x1000),(0x1fa80000,0x60),(0x1fa80a00,0x164),
            (0x1fa84000,0x450),(0x1fa85900,0x338),(0x1fa86000,0x300),
            (0x1fa8f000,0x1000),(0x1fa8e000,0x1000)]
    outcomes = []
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        made = subprocess.run([tools['dt-mk-schema'],'-j',str(args.binding),str(consumer)],capture_output=True,text=True)
        if made.returncode or made.stderr.strip():
            raise RuntimeError('Binding schema compilation failed: '+made.stderr)
        schema = root/'schema.json'
        schema.write_text(made.stdout)
        for name, mode, compatible, windows, expected in cases:
            reg = ', '.join('<0 0x%x 0 0x%x>' % pair for pair in regs[:windows])
            property_text = 'airoha,pon-ethernet-mode = '+mode+';' if mode else ''
            source = '''/dts-v1/;
/ {
    model = "Synthetic disabled PCS schema check";
    compatible = "test,pcs-schema";
    #address-cells = <2>;
    #size-cells = <2>;
    scu: reset-controller@1fa20000 {
        compatible = "test,reset-controller";
        reg = <0 0x1fa20000 0 0x1000>;
        #reset-cells = <1>;
    };
    nvmem@1fbf2000 {
        compatible = "test,nvmem";
        reg = <0 0x1fbf2000 0 0x400>;
        #address-cells = <1>;
        #size-cells = <1>;
        valid: valid@0 { reg = <0 1>; };
        tx: trim@1 { reg = <1 1>; };
        rx: trim@2 { reg = <2 1>; };
    };
    pcs@1fa08000 {
        compatible = "%s";
        reg = %s;
        reg-names = "pcs_mac", "hsgmii_an", "hsgmii_pcs", "multi_sgmii",
                    "usxgmii", "hsgmii_rate_adp", "pcs_ana", "pcs_pma";
        resets = <&scu 1>, <&scu 2>, <&scu 3>;
        reset-names = "mac", "phy", "xfi";
        nvmem-cells = <&valid>, <&tx>, <&rx>;
        nvmem-cell-names = "pon-impedance-valid", "pon-tx-term", "pon-rx-impedance";
        airoha,scu = <&scu>;
        #pcs-cells = <0>;
        %s
        status = "disabled";
    };
};
''' % (compatible,reg,property_text)
            dts,dtb = root/(name+'.dts'),root/(name+'.dtb')
            dts.write_text(source)
            subprocess.run([tools['dtc'],'-I','dts','-O','dtb','-o',str(dtb),str(dts)],
                           check=True,capture_output=True)
            validated = subprocess.run([tools['dt-validate'],'-s',str(schema),'-l','airoha,an7583-pcs-pon',str(dtb)],
                                        capture_output=True,text=True)
            accepted = not validated.returncode and not validated.stdout.strip() and not validated.stderr.strip()
            if accepted != expected:
                raise RuntimeError('Unexpected schema result for '+name+': '+validated.stdout+validated.stderr)
            outcomes.append({'case':name,'expected_accepted':expected,'observed_accepted':accepted})
    report = {'binding_sha256':hashlib.sha256(args.binding.read_bytes()).hexdigest(),
              'nvmem_consumer_schema_sha256':hashlib.sha256(consumer.read_bytes()).hexdigest(),
              'meta_schema_passed':True,'cases':outcomes,'hardware_access':False}
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(report,stream,indent=2)
        stream.write('\n')
    print('PCS binding: two valid examples accepted; five invalid examples rejected')


if __name__ == '__main__':
    main()
