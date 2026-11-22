#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Inspect actual AArch64 ELF parameter ops and query probe imports/SMC calls."""
import argparse, struct
from pathlib import Path

class Elf:
    def __init__(self,path):
        self.data = Path(path).read_bytes()
        h = struct.unpack_from('<16sHHIQQQIHHHHHH',self.data)
        assert h[0][:6] == b'\x7fELF\x02\x01' and h[2] == 183
        self.sections = [struct.unpack_from('<IIQQQQIIQQ',self.data,h[6]+i*h[11]) for i in range(h[12])]
        self.symbols = []
        self.relocations = {}
        for section in self.sections:
            if section[1] != 2: continue
            strings = self.section(section[6])
            for offset in range(section[4],section[4]+section[5],section[9]):
                s = struct.unpack_from('<IBBHQQ',self.data,offset)
                name = strings[s[0]:].split(b'\0',1)[0].decode()
                self.symbols.append((name,s[3],s[4],s[5]))
        for section in self.sections:
            if section[1] != 4: continue
            for offset in range(section[4],section[4]+section[5],section[9]):
                address, info, addend = struct.unpack_from('<QQq',self.data,offset)
                self.relocations[(section[7],address)] = (self.symbols[info>>32][0],addend,info&0xffffffff)
    def section(self,index):
        s = self.sections[index]
        return self.data[s[4]:s[4]+s[5]]
    def symbol(self,name):
        found = [s for s in self.symbols if s[0] == name]
        assert len(found) == 1, name
        return found[0]
    def ops(self,name,setter,getter):
        _, section, address, size = self.symbol(name)
        assert size == 32, 'unexpected kernel_param_ops layout'
        raw = self.section(section)[address:address+size]
        assert raw[:4] == bytes(4), 'unexpected parameter flags'
        for field,target in [(8,setter),(16,getter),(24,None)]:
            relocation = self.relocations.get((section,address+field))
            if target is None:
                assert raw[field:field+8] == bytes(8) and relocation is None, name+' has a setter'
            else:
                # Local text functions may be expressed as section+addend.
                symbol = self.symbol(target)
                assert relocation is not None
                if relocation[0] != target:
                    assert relocation[0] in ('','.text') and relocation[1] == symbol[2]

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('work',type=Path)
a = p.parse_args()
driver = Elf(a.work/'vb235v-cpufreq.o')
for kind in ('bool','uint','ulong'):
    driver.ops('vb235v_'+kind+'_ro_ops',None,'param_get_'+kind)
driver.ops('vb235v_preflight_ops',None,'vb235v_preflight_get')
driver.ops('vb235v_allow_ops','vb235v_allow_set','param_get_bool')
query = Elf(a.work/'vb235v-cpu-query.o')
imports = {s[0] for s in query.symbols if s[1] == 0 and s[0]}
allow = {'arm64_use_ng_mappings','__arm_smccc_smc','__cpu_possible_mask',
         '__ioremap_prot','iounmap','__num_online_cpus','of_machine_compatible_match',
         'param_ops_bool','param_ops_uint','param_ops_ulong','_printk','__sw_hweight64','__this_module'}
assert imports == allow, 'unexpected query imports: '+str(imports-allow)
smcs = [r for r in query.relocations.values() if r[0] == '__arm_smccc_smc' and r[2] == 283]
assert len(smcs) == 1, 'query must contain exactly one SMC call'
print('M81 actual ARM64 objects: internal state/preflight getter-only; only gated allow setter; query import allowlist and one SMC call PASS')
