#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Physical-LAN software controls and repeated hardware flowtable lifecycle tests."""
import argparse,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--connection',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--repeat-pairs',type=int,default=4)
    p.add_argument('--fw4-only',action='store_true')
    a=p.parse_args();assert 1<=a.repeat_pairs<=20
    connection=a.connection.resolve(strict=True);a.output.mkdir(parents=True,exist_ok=True)
    cases=[('udp-software','udp_fixture.py',['--software'],'hairpin-report.json'),
           ('udp-hardware','udp_fixture.py',[],'hairpin-report.json'),
           ('tcp-download-software','tcp_fixture.py',['--software'],'tcp-report.json'),
           ('tcp-download-hardware','tcp_fixture.py',[],'tcp-report.json'),
           ('tcp-upload-software','tcp_fixture.py',['--software','--upload'],'tcp-upload-report.json'),
           ('tcp-upload-hardware','tcp_fixture.py',['--upload'],'tcp-upload-report.json')]
    for i in range(a.repeat_pairs):
        cases += [(f'repeat-{i+1}-upload-hardware','tcp_fixture.py',['--upload'],'tcp-upload-report.json'),
                  (f'repeat-{i+1}-download-hardware','tcp_fixture.py',[],'tcp-report.json')]
    fw4_cases=[('fw4-upload-hardware','tcp_fixture.py',['--upload','--fw4'],'tcp-upload-report.json'),
               ('fw4-download-hardware','tcp_fixture.py',['--fw4'],'tcp-report.json')]
    cases=fw4_cases if a.fw4_only else cases+fw4_cases
    results=[]
    for name,script,args,report_name in cases:
        out=a.output/name;out.mkdir(exist_ok=False)
        result=subprocess.run([sys.executable,str(HERE/script),'--connection',str(connection),'--output',str(out),*args],capture_output=True)
        (out/'runner-private.log').write_bytes(result.stdout+result.stderr)
        assert result.returncode==0,name+' failed; inspect private runner log'
        report=json.loads((out/report_name).read_text(encoding='utf-8'));report.pop('nft_counters',None)
        assert report['complete'] and report['fixture_PPE_entries_cleared_after_delete']
        logs=[file.read_text(encoding='utf-8') for file in out.glob('*live-*-private.log')]
        source_port=report['client_source_port'];port=8824 if script=='udp_fixture.py' else 8825
        current=[line for log in logs for line in log.splitlines() if f'sport={source_port} dport={port}' in line]
        report['live_HW_OFFLOAD_observed']=any('[HW_OFFLOAD]' in line for line in current)
        entries={line.split()[0] for log in logs for line in log.splitlines() if ' BND ' in line and ':'+str(source_port) in line}
        report['live_bound_PPE_entries']=len(entries)
        report['live_NPU_attached']=any('npu_attached: 1' in log for log in logs)
        packets=report['CPU_ingress_counter_packets']
        if name.endswith('hardware'):
            assert report['live_HW_OFFLOAD_observed'] and len(entries)>=2 and report['live_NPU_attached'],name+' hardware indicators absent'
            assert sum(packets)<256,name+' failed to bypass the pre-flowtable CPU hook'
        else:
            assert not report['live_HW_OFFLOAD_observed'] and sum(packets)>3000,name+' invalid software control'
        (out/'validated-report.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
        results.append({'case':name,**report})
        print(name+' passed: CPU ingress '+str(packets)+'; fixture hardware entries cleared',flush=True)
    (a.output/'suite-report.json').write_bytes((json.dumps({'complete':True,'single_flowtable_control':True,'results':results},indent=2)+'\n').encode())
    print('All software/hardware integrity and repeated cleanup controls passed.',flush=True)
if __name__=='__main__':main()
