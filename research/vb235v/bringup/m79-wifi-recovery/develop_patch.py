#!/usr/bin/env python3
"""Generate the reviewable patch from the exact prepared M75 mt76 baseline.

Development helper: only writes the explicitly supplied isolated work directory
and this directory's patch/baseline-hashes files. It never edits build inputs.
"""
import difflib
import hashlib
import json
from pathlib import Path
import sys

src, dst = map(Path, sys.argv[1:3])
assert src.resolve() != dst.resolve()
here = Path(__file__).resolve().parent
names = ['mt7996/pci.c', 'mt7996/init.c', 'mt7996/mt7996.h', 'mt7996/mac.c', 'mt7996/coredump.c', 'dma.c']
original = {n: (src / n).read_text() for n in names}
texts = dict(original)

def replace(name, old, new):
    assert texts[name].count(old) == 1, (name, old[:100], texts[name].count(old))
    texts[name] = texts[name].replace(old, new)

replace('mt7996/mt7996.h', '\tstruct mt7996_hif *hif2;\n', '''\tstruct mt7996_hif *hif2;
\t/* Resources owned by the primary, even when allocated on HIF2. */
\tint pci_irq, hif2_irq;
\tbool pci_irq_requested, hif2_irq_requested;
\tbool pci_irq_vectors, hif2_irq_vectors;
\tbool dma_started, mcu_started, removing;
''')
replace('mt7996/mt7996.h', 'void mt7996_unregister_device(struct mt7996_dev *dev);', 'void mt7996_unregister_device(struct mt7996_dev *dev);\nvoid mt7996_pci_quiesce(struct mt7996_dev *dev);')
replace('mt7996/pci.c', 'static struct mt7996_hif *mt7996_pci_get_hif2(u32 idx)', 'static struct mt7996_hif *mt7996_pci_get_hif2(u32 idx, struct device *supplier)')
replace('mt7996/pci.c', '\tlist_for_each_entry(hif, &hif_list, list) {', '\tlist_for_each_entry(hif, &hif_list, list) {\n\t\tif (hif->dev != supplier)\n\t\t\tcontinue;\n')
replace('mt7996/pci.c', '\tstruct pci_dev *tmp_pdev;\n', '\tstruct pci_dev *tmp_pdev;\n\tstruct device_link *link;\n\tstruct mt7996_hif *hif;\n')
replace('mt7996/pci.c', '\tpci_dev_put(tmp_pdev);\n', '''\t/* Establish the dependency before looking at secondary devm state. A
\t * mere get_device() does not keep that driver's HIF/BAR resources alive.
\t * The core waits for a CONSUMER_PROBE link before unbinding a supplier.
\t */
\tlink = device_link_add(&pdev->dev, &tmp_pdev->dev,
\t\t\t       DL_FLAG_AUTOREMOVE_CONSUMER);
\tif (!link) {
\t\tpci_dev_put(tmp_pdev);
\t\treturn ERR_PTR(-ENOMEM);
\t}
\tif (READ_ONCE(link->status) != DL_STATE_CONSUMER_PROBE) {
\t\tpci_dev_put(tmp_pdev);
\t\treturn ERR_PTR(-EPROBE_DEFER);
\t}
''')
replace('mt7996/pci.c', '\treturn mt7996_pci_get_hif2(hif_idx);', '''\thif = mt7996_pci_get_hif2(hif_idx, &tmp_pdev->dev);
\tpci_dev_put(tmp_pdev);
\treturn hif ? hif : ERR_PTR(-EPROBE_DEFER);''')
replace('mt7996/mac.c', '\tif (!dev->recovery.hw_init_done)\n\t\treturn;\n', '\tif (READ_ONCE(dev->removing) || !dev->recovery.hw_init_done)\n\t\treturn;\n')
for work in ['reset_work', 'dump_work']:
    line = '\tdev = container_of(work, struct mt7996_dev, '+work+');\n'
    replace('mt7996/mac.c', line, line+'\tif (READ_ONCE(dev->removing))\n\t\treturn;\n')
replace('mt7996/coredump.c', 'void mt7996_coredump_unregister(struct mt7996_dev *dev)\n{', 'void mt7996_coredump_unregister(struct mt7996_dev *dev)\n{\n\tif (!dev->coredump.crash_data)\n\t\treturn;\n')

replace('mt7996/pci.c', 'static int mt7996_pci_probe(struct pci_dev *pdev,', '''/* Keep dev and both BAR mappings alive until all interrupt consumers stop. */
void mt7996_pci_quiesce(struct mt7996_dev *dev)
{
\tstruct mt76_dev *mdev = &dev->mt76;

\tWRITE_ONCE(dev->removing, true);
\tclear_bit(MT76_STATE_INITIALIZED, &dev->mphy.state);
\tmt76_wr(dev, MT_INT_MASK_CSR, 0);
\tif (dev->hif2)
\t\tmt76_wr(dev, MT_INT1_MASK_CSR, 0);
\tif (mtk_wed_device_active(&mdev->mmio.wed))
\t\tmtk_wed_device_irq_set_mask(&mdev->mmio.wed, 0);
\tif (mtk_wed_device_active(&mdev->mmio.wed_hif2))
\t\tmtk_wed_device_irq_set_mask(&mdev->mmio.wed_hif2, 0);

\t/* Drain handlers which saw INITIALIZED before it was cleared, then their
\t * tasklet. Later handlers see it clear and cannot schedule a new tasklet.
\t */
\tif (dev->hif2_irq_requested)
\t\tsynchronize_irq(dev->hif2_irq);
\tif (dev->pci_irq_requested)
\t\tsynchronize_irq(dev->pci_irq);
\ttasklet_kill(&mdev->irq_tasklet);
\t/* A final tasklet may have re-enabled a mask while it was draining. */
\tmt76_wr(dev, MT_INT_MASK_CSR, 0);
\tif (dev->hif2)
\t\tmt76_wr(dev, MT_INT1_MASK_CSR, 0);
\tif (mtk_wed_device_active(&mdev->mmio.wed))
\t\tmtk_wed_device_irq_set_mask(&mdev->mmio.wed, 0);
\tif (mtk_wed_device_active(&mdev->mmio.wed_hif2))
\t\tmtk_wed_device_irq_set_mask(&mdev->mmio.wed_hif2, 0);

\tif (dev->hif2_irq_requested) {
\t\tdevm_free_irq(mdev->dev, dev->hif2_irq, dev);
\t\tdev->hif2_irq_requested = false;
\t}
\tif (dev->pci_irq_requested) {
\t\tdevm_free_irq(mdev->dev, dev->pci_irq, dev);
\t\tdev->pci_irq_requested = false;
\t}
}

static void mt7996_pci_release(struct pci_dev *pdev, struct mt7996_dev *dev)
{
\tstruct mt76_dev *mdev = &dev->mt76;

\tmt7996_pci_quiesce(dev);
\t/* DMA cleanup may already have detached WED. Never free WED-owned vectors. */
\tif (mtk_wed_device_active(&mdev->mmio.wed_hif2))
\t\tmtk_wed_device_detach(&mdev->mmio.wed_hif2);
\tif (dev->hif2_irq_vectors) {
\t\tpci_free_irq_vectors(to_pci_dev(dev->hif2->dev));
\t\tdev->hif2_irq_vectors = false;
\t}
\tif (mtk_wed_device_active(&mdev->mmio.wed))
\t\tmtk_wed_device_detach(&mdev->mmio.wed);
\tif (dev->pci_irq_vectors) {
\t\tpci_free_irq_vectors(pdev);
\t\tdev->pci_irq_vectors = false;
\t}
\tmt7996_put_hif2(dev->hif2);
\tmt76_free_device(mdev);
}

static int mt7996_pci_probe(struct pci_dev *pdev,''')
replace('mt7996/pci.c', '\tdev->hif2 = hif2;\n', '''\tif (IS_ERR(hif2)) {
\t\tret = PTR_ERR(hif2);
\t\tgoto release;
\t}
\tdev->hif2 = hif2;
''')
# Replace all old asymmetric labels with the single resource ledger unwind.
start = texts['mt7996/pci.c'].index('\tret = mt7996_mmio_wed_init(dev, pdev, false, &irq);')
end = texts['mt7996/pci.c'].index('\nstatic void mt7996_hif_remove', start)
texts['mt7996/pci.c'] = texts['mt7996/pci.c'][:start] + '''\tret = mt7996_mmio_wed_init(dev, pdev, false, &irq);
\tif (ret < 0)
\t\tgoto release;
\tif (!ret) {
\t\tret = pci_alloc_irq_vectors(pdev, 1, 1, PCI_IRQ_ALL_TYPES);
\t\tif (ret < 0)
\t\t\tgoto release;
\t\tdev->pci_irq_vectors = true;
\t\tirq = pci_irq_vector(pdev, 0);
\t}
\tdev->pci_irq = irq;
\tret = devm_request_irq(mdev->dev, irq, mt7996_irq_handler,
\t\t\t       IRQF_SHARED, KBUILD_MODNAME, dev);
\tif (ret)
\t\tgoto release;
\tdev->pci_irq_requested = true;

\tmt76_wr(dev, MT_INT_MASK_CSR, 0);
\tmt76_wr(dev, MT_PCIE_MAC_INT_ENABLE, 0xff);

\tif (hif2) {
\t\thif2_dev = to_pci_dev(hif2->dev);
\t\tret = mt7996_mmio_wed_init(dev, hif2_dev, true, &hif2_irq);
\t\tif (ret < 0)
\t\t\tgoto release;
\t\tif (!ret) {
\t\t\tret = pci_alloc_irq_vectors(hif2_dev, 1, 1, PCI_IRQ_ALL_TYPES);
\t\t\tif (ret < 0)
\t\t\t\tgoto release;
\t\t\tdev->hif2_irq_vectors = true;
\t\t\thif2_irq = pci_irq_vector(hif2_dev, 0);
\t\t\thif2->irq = hif2_irq;
\t\t}
\t\tdev->hif2_irq = hif2_irq;
\t\tret = devm_request_irq(mdev->dev, hif2_irq, mt7996_irq_handler,
\t\t\t\t       IRQF_SHARED, KBUILD_MODNAME "-hif", dev);
\t\tif (ret)
\t\t\tgoto release;
\t\tdev->hif2_irq_requested = true;
\t\tmt76_wr(dev, MT_INT1_MASK_CSR, 0);
\t\tmt76_wr(dev, MT_PCIE1_MAC_INT_ENABLE, 0xff);
\t}

\tret = mt7996_register_device(dev);
\tif (ret) {
\t\tmt7996_unregister_device(dev);
\t\tgoto release;
\t}
\treturn 0;

release:
\tmt7996_pci_release(pdev, dev);
\treturn ret;
}
''' + texts['mt7996/pci.c'][end:]
replace('mt7996/pci.c', '\tlist_del(&hif->list);', '\tspin_lock_bh(&hif_lock);\n\tlist_del(&hif->list);\n\tspin_unlock_bh(&hif_lock);')
replace('mt7996/pci.c', '\tmt7996_put_hif2(dev->hif2);\n\tmt7996_unregister_device(dev);', '\tmt7996_unregister_device(dev);\n\tmt7996_pci_release(pdev, dev);')

replace('mt7996/init.c', '\tret = mt7996_dma_init(dev);', '\tdev->dma_started = true;\n\tret = mt7996_dma_init(dev);')
replace('mt7996/init.c', '\tret = mt7996_mcu_init(dev);', '\tdev->mcu_started = true;\n\tret = mt7996_mcu_init(dev);')
replace('mt7996/init.c', '\tspin_lock_init(&dev->wed_rro.lock);\n', '''\tspin_lock_init(&dev->wed_rro.lock);
\t/* Failure unwind may run before rro_hw_init reaches these lists. */
\tINIT_LIST_HEAD(&dev->wed_rro.page_cache);
\tfor (idx = 0; idx < ARRAY_SIZE(dev->wed_rro.page_map); idx++)
\t\tINIT_LIST_HEAD(&dev->wed_rro.page_map[idx]);
''')
start = texts['mt7996/init.c'].index('void mt7996_unregister_device(struct mt7996_dev *dev)')
texts['mt7996/init.c'] = texts['mt7996/init.c'][:start] + '''/* Also used for register_device failures; all works are initialized before it. */
void mt7996_unregister_device(struct mt7996_dev *dev)
{
\tbool wed_active = mtk_wed_device_active(&dev->mt76.mmio.wed);
\tint i;

\tWRITE_ONCE(dev->removing, true);
\tdev->recovery.hw_init_done = false;
\tcancel_work_sync(&dev->init_work);
\tcancel_work_sync(&dev->dump_work);
\tcancel_work_sync(&dev->wed_rro.work);
\tcancel_work_sync(&dev->reset_work);
\tcancel_work_sync(&dev->rc_work);
\tmt7996_unregister_phy(mt7996_phy3(dev));
\tmt7996_unregister_phy(mt7996_phy2(dev));
\tmt7996_unregister_thermal(&dev->phy);
\tmt7996_coredump_unregister(dev);
\tmt76_unregister_device(&dev->mt76);
\tif (dev->mcu_started)
\t\tmt7996_mcu_exit(dev);

\t/* MCU commands need IRQ/NAPI until exit. Stop pollers before IRQ release. */
\tmt76_worker_disable(&dev->mt76.tx_worker);
\tfor (i = 0; i < ARRAY_SIZE(dev->mt76.napi); i++) {
\t\tif (dev->mt76.napi[i].dev)
\t\t\tnapi_disable(&dev->mt76.napi[i]);
\t}
\tif (dev->mt76.tx_napi.dev) {
\t\tnapi_disable(&dev->mt76.tx_napi);
\t\tnetif_napi_del(&dev->mt76.tx_napi);
\t}
\tmt7996_pci_quiesce(dev);
\t/* Drain a producer which had passed the removing check before teardown. */
\tcancel_work_sync(&dev->dump_work);
\tcancel_work_sync(&dev->reset_work);
\tmt7996_tx_token_put(dev);
\tif (dev->dma_started)
\t\tmt7996_dma_cleanup(dev);
\tmt7996_wed_rro_free(dev);
\tif (mt7996_has_hwrro(dev) && !wed_active)
\t\tmt7996_rro_msdu_page_map_free(dev);
}
'''
# Partial DMA init can return before allocating/enabling either NAPI object.
replace('dma.c', '\t\tfree_netdev(dev->napi_dev);\n\t\treturn -ENOMEM;', '\t\tfree_netdev(dev->napi_dev);\n\t\tdev->napi_dev = NULL;\n\t\treturn -ENOMEM;')
replace('dma.c', '\tnapi_disable(&dev->tx_napi);\n\tnetif_napi_del(&dev->tx_napi);', '\tif (test_bit(NAPI_STATE_LISTED, &dev->tx_napi.state)) {\n\t\tnapi_disable(&dev->tx_napi);\n\t\tnetif_napi_del(&dev->tx_napi);\n\t}')
replace('dma.c', '\t\tnetif_napi_del(&dev->napi[i]);', '\t\tif (dev->napi[i].dev)\n\t\t\tnetif_napi_del(&dev->napi[i]);')

patch = []
for name in names:
    path = dst / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(texts[name])
    patch.extend(difflib.unified_diff(original[name].splitlines(True), texts[name].splitlines(True), fromfile='a/'+name, tofile='b/'+name))
(here/'121-vb235v-mt7996-pci-recovery.patch').write_text('''Subject: [PATCH] wifi: mt7996: unwind primary and HIF2 resources together

HIF2 vectors belong to its secondary PCI devres owner, so primary-only
unbind leaves MSI enabled. Release owned handlers and native vectors on
both success and failed probe, with a supplier link pinning HIF2's driver.
Drain recovery, init, poll and IRQ work before freeing device/DMA state.
Keep the private ART calibration rejection policy unchanged.

Target: pinned mt76 baseline documented in README, Linux 6.18.60.
Hardware regression is required; no CVE or remote exploit is claimed.

---
'''+''.join(patch))
(here/'baseline-hashes.json').write_text(json.dumps({n: hashlib.sha256(original[n].encode()).hexdigest() for n in names}, indent=2)+'\n')
(here/'patched-hashes.json').write_text(json.dumps({**{n: hashlib.sha256(texts[n].encode()).hexdigest() for n in names}, 'mt7996/eeprom.c': hashlib.sha256((src/'mt7996/eeprom.c').read_bytes()).hexdigest()}, indent=2)+'\n')
