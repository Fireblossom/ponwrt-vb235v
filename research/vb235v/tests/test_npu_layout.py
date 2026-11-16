# SPDX-License-Identifier: GPL-2.0-only
"""Compile the actual added C helper and check independent stock-layout vectors."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from fdt_board_inventory import cells, parse


class NpuLayoutTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cc'), 'host C compiler required')
    def test_actual_patched_helper_matches_vectors_and_rejects_invalid_cores(self):
        patch = (ROOT / 'bringup/950-vb235v-npu-layout-development.patch').read_text()
        marker = 'diff --git a/drivers/net/ethernet/airoha/airoha_npu_layout.h b/drivers/net/ethernet/airoha/airoha_npu_layout.h\n'
        section = patch.split(marker, 1)[1].split('diff --git ', 1)[0]
        header = ''.join(line[1:] for line in section.splitlines(True) if line.startswith('+') and not line.startswith('+++'))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'linux').mkdir()
            (root / 'linux/bits.h').write_text('#define BIT(nr) (1UL << (nr))\n')
            (root / 'linux/types.h').write_text('#include <stdint.h>\n#include <stdbool.h>\ntypedef uint32_t u32;\n')
            (root / 'linux/errno.h').write_text('#define EINVAL 22\n')
            (root / 'layout.h').write_text(header)
            source = r'''
#include <assert.h>
#include <string.h>
#include "layout.h"
int main(void)
{
    struct airoha_npu_wdt_regs got, before;
    const unsigned int offsets[] = {0x310100, 0x310100, 0x310100,
                                    0x310100, 0x310200, 0x310200};
    const unsigned int irq[] = {0x200000, 0x400000, 0x800000,
                                0x1000000, 0x200000, 0x400000};
    const unsigned int enable[] = {0x2000000, 0x4000000, 0x8000000,
                                   0x10000000, 0x2000000, 0x4000000};
    unsigned int i;
    assert(airoha_npu_core_mask(&airoha_npu_v2p_layout) == 0x3f);
    assert(airoha_npu_core_mask(&airoha_npu_legacy_layout) == 0xff);
    assert(airoha_npu_v2p_layout.sram_size == 0x20000);
    assert(airoha_npu_legacy_layout.sram_size == 0x40000);
    for (i = 0; i < 6; i++) {
        assert(!airoha_npu_wdt_regs(&airoha_npu_v2p_layout, i, &got));
        assert(got.offset == offsets[i]);
        assert(got.irq_mask == irq[i]);
        assert(got.enable_mask == enable[i]);
        assert(got.preserve_mask == 0x1e0001ef);
    }
    assert(!airoha_npu_wdt_regs(&airoha_npu_legacy_layout, 7, &got));
    assert(got.offset == 0x310800 && got.irq_mask == 0x200000);
    assert(got.enable_mask == 0x2000000 && got.preserve_mask == 0x02000027);
    before = got;
    assert(airoha_npu_wdt_regs(&airoha_npu_v2p_layout, 6, &got) == -EINVAL);
    assert(!memcmp(&got, &before, sizeof(got)));
    assert(airoha_npu_wdt_regs(&airoha_npu_legacy_layout, 8, &got) == -EINVAL);
    assert(airoha_npu_wdt_regs(0, 0, &got) == -EINVAL);
    return 0;
}
'''
            (root / 'test.c').write_text(source)
            binary = root / 'test'
            subprocess.run([shutil.which('cc'), '-std=c11', '-Wall', '-Wextra', '-Werror', '-I', str(root),
                            str(root / 'test.c'), '-o', str(binary)], check=True, capture_output=True)
            subprocess.run([str(binary)], check=True, timeout=5)

    @unittest.skipUnless(shutil.which('dtc'), 'dtc required')
    def test_development_overlay_is_disabled_and_matches_observed_irq_roles(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'layout.dtbo'
            subprocess.run([shutil.which('dtc'), '-@', '-I', 'dts', '-O', 'dtb', '-o', str(target),
                            str(ROOT / 'bringup/vb235v-npu-layout-disabled.dtso')], check=True, capture_output=True)
            nodes, _ = parse(target.read_bytes())
        self.assertEqual(set(nodes), {'/', '/fragment@0', '/fragment@0/__overlay__'})
        props = nodes['/fragment@0/__overlay__']
        self.assertEqual(set(props), {'airoha,npu-layout', 'interrupts', 'status'})
        self.assertEqual(props['status'], b'disabled\0')
        self.assertEqual(props['airoha,npu-layout'], b'an7583-v2p\0')
        facts = json.loads((ROOT / 'findings/npu-ponwrt-contract.json').read_text())['irq_contract']
        expected = [facts['stock_full_dt_spi_selectors'][6]] + facts['stock_registered_watchdog_selectors'] + facts['stock_full_dt_spi_selectors'][:6]
        tuples = cells(props['interrupts'])
        self.assertEqual(tuples[1::3], expected)
        self.assertEqual(tuples[0::3], [0] * 13)
        self.assertEqual(tuples[2::3], [4] * 13)


if __name__ == '__main__':
    unittest.main()
