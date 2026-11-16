# SPDX-License-Identifier: GPL-2.0-only
"""Compile disabled synthetic nodes and exercise the applied DT binding schema.

Requires dtc and dtschema host tools. No hardware access or kernel execution.
"""
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
    commands = {name: shutil.which(name) for name in ('dtc', 'dt-doc-validate', 'dt-mk-schema', 'dt-validate')}
    if not all(commands.values()):
        raise ValueError('Missing dtc/dtschema host tool')
    result = subprocess.run([commands['dt-doc-validate'], str(args.binding)], capture_output=True, text=True)
    if result.returncode or result.stdout.strip() or result.stderr.strip():
        raise RuntimeError('Binding meta-schema validation failed: ' + result.stdout + result.stderr)
    legacy = [125, 103, 109, 113, 117, 134, 135, 136, 137, 118, 119, 120, 121, 122, 123]
    v2p = [125, 134, 135, 136, 137, 109, 110, 118, 119, 120, 121, 122, 123]
    cases = [('legacy_default', None, legacy, 'airoha,en7581-npu', True),
             ('v2p_six_core', 'an7583-v2p', v2p, 'airoha,an7583-npu', True),
             ('v2p_wrong_irq_count', 'an7583-v2p', legacy, 'airoha,an7583-npu', False),
             ('legacy_wrong_irq_count', None, v2p, 'airoha,en7581-npu', False),
             ('v2p_wrong_compatible', 'an7583-v2p', v2p, 'airoha,en7581-npu', False)]
    outcomes = []
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        schema = root / 'schema.json'
        compiled = subprocess.run([commands['dt-mk-schema'], '-j', str(args.binding)], capture_output=True, text=True)
        if compiled.returncode or compiled.stderr.strip():
            raise RuntimeError('Schema compilation failed: ' + compiled.stderr)
        schema.write_text(compiled.stdout)
        for name, profile, irqs, compatible, expected in cases:
            tuple_text = ', '.join('<0 %d 4>' % irq for irq in irqs)
            profile_text = 'airoha,npu-layout = "%s";' % profile if profile else ''
            source = '''/dts-v1/;
/ {
    model = "Synthetic disabled NPU schema test";
    compatible = "test,npu-schema";
    #address-cells = <2>;
    #size-cells = <2>;
    gic: interrupt-controller@9000000 {
        compatible = "arm,gic-v3";
        reg = <0 0x9000000 0 0x20000>;
        interrupt-controller;
        #interrupt-cells = <3>;
    };
    reserved-memory {
        #address-cells = <2>;
        #size-cells = <2>;
        ranges;
        firmware: binary@84000000 {
            reg = <0 0x84000000 0 0xa00000>;
            no-map;
        };
    };
    npu@1e900000 {
        compatible = "%s";
        reg = <0 0x1e900000 0 0x313000>;
        interrupt-parent = <&gic>;
        interrupts = %s;
        memory-region = <&firmware>;
        memory-region-names = "binary";
        %s
        status = "disabled";
    };
};
''' % (compatible, tuple_text, profile_text)
            dts = root / (name + '.dts')
            dtb = root / (name + '.dtb')
            dts.write_text(source)
            subprocess.run([commands['dtc'], '-I', 'dts', '-O', 'dtb', '-o', str(dtb), str(dts)],
                           check=True, capture_output=True)
            checked = subprocess.run([commands['dt-validate'], '-s', str(schema), '-l', 'airoha,en7581-npu', str(dtb)],
                                     capture_output=True, text=True)
            accepted = not checked.returncode and not checked.stdout.strip() and not checked.stderr.strip()
            if accepted != expected:
                raise RuntimeError('Unexpected schema outcome for ' + name + ': ' + checked.stdout + checked.stderr)
            outcomes.append({'case': name, 'expected_accepted': expected, 'observed_accepted': accepted})
    report = {'binding_sha256': hashlib.sha256(args.binding.read_bytes()).hexdigest(),
              'binding_meta_schema_passed': True, 'cases': outcomes, 'hardware_actions': False}
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print('DT binding: two valid samples accepted; three invalid samples rejected')


if __name__ == '__main__':
    main()
