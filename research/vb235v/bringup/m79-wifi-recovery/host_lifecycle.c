/* SPDX-License-Identifier: GPL-2.0-only */
/* Mock kernel contracts around actual extracted patched driver functions. */
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#define BIT(n) (1UL << (n))
#define DMA_BIT_MASK(n) (~0ULL >> (64-(n)))
#define WRITE_ONCE(x,v) ((x)=(v))
#define ARRAY_SIZE(x) (sizeof(x)/sizeof((x)[0]))
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define to_pci_dev(p) ((p)->owner)
#define IS_ERR(p) ((intptr_t)(p)<0)
#define PTR_ERR(p) ((intptr_t)(p))
#define MT7996_DEVICE_ID_2 0x7996
#define MT7992_DEVICE_ID_2 0x7992
#define MT7990_DEVICE_ID_2 0x799b
#define MT76_STATE_INITIALIZED 0
#define MT_INT_MASK_CSR 1
#define MT_INT1_MASK_CSR 2
#define MT_PCIE_MAC_INT_ENABLE 3
#define MT_PCIE1_MAC_INT_ENABLE 4
#define PCI_IRQ_ALL_TYPES 7
#define IRQF_SHARED 1
#define KBUILD_MODNAME "mt7996e"
#define DL_FLAG_AUTOREMOVE_CONSUMER 1
#define EPROBE_DEFER 517
struct pci_dev;
struct device { struct pci_dev *owner; };
struct pci_dev { struct device dev; void *bus, *data; int irq, vectors, handlers; bool synchronized; };
struct pci_device_id { int device; };
struct napi { void *dev; bool enabled, listed; };
struct tasklet { bool killed; };
struct work { bool initialized, pending; int id; };
struct wed { bool active; struct pci_dev *pdev; };
struct mt7996_phy { unsigned long state; };
struct mt76_dev {
    int tx_worker;
    struct device *dev;
    struct { struct wed wed, wed_hif2; } mmio;
    struct napi napi[3], tx_napi;
    struct tasklet irq_tasklet;
};
struct mt7996_hif { struct device *dev; int irq; };
struct mt7996_dev {
    struct mt76_dev mt76;
    struct mt7996_phy mphy, phy;
    struct mt7996_hif *hif2;
    int pci_irq,hif2_irq;
    bool pci_irq_requested,hif2_irq_requested,pci_irq_vectors,hif2_irq_vectors;
    bool dma_started,mcu_started,removing;
    struct { bool hw_init_done; } recovery;
    struct work init_work,dump_work,reset_work,rc_work;
    struct { struct work work; } wed_rro;
};
static struct pci_dev primary, secondary;
static struct mt7996_hif hif;
static struct mt7996_dev *current;
static bool use_hif, use_wed[2], dma_detach, full_module;
static int fail_at,step,refs,allocs,frees,register_stage,cases;
static bool failed(void) { return ++step==fail_at; }
static struct pci_dev *irq_dev(int irq) { assert(irq==41 || irq==42); return irq==41?&primary:&secondary; }
static void clear_bit(int n,unsigned long *p) { *p &= ~BIT(n); }
static int pcim_enable_device(struct pci_dev *p) { (void)p;return failed()?-EIO:0; }
static int pcim_iomap_regions(struct pci_dev *p,int b,const char *n) { (void)p;(void)b;(void)n;return failed()?-EIO:0; }
static const char *pci_name(struct pci_dev *p) { (void)p;return "mock"; }
static void pci_set_master(struct pci_dev *p) { (void)p; }
static int dma_set_mask(struct device *p,uint64_t m) { (void)p;(void)m;return failed()?-EIO:0; }
static int dma_set_coherent_mask(struct device *p,uint64_t m) { (void)p;(void)m;return failed()?-EIO:0; }
static void mt76_pci_disable_aspm(struct pci_dev *p) { (void)p; }
static int mt7996_pci_hif2_probe(struct pci_dev *p) { (void)p;return 0; }
static void **pcim_iomap_table(struct pci_dev *p) { static void *bar[1];(void)p;return bar; }
static struct mt7996_dev *mt7996_mmio_probe(struct device *p,void *bar,int id) {
    (void)bar;(void)id;if(failed())return (void *)(intptr_t)-ENOMEM;
    current=calloc(1,sizeof(*current));assert(current);allocs++;
    current->mt76.dev=p;p->owner->data=&current->mt76;return current;
}
static void mt7996_wfsys_reset(struct mt7996_dev *d) { assert(d==current); }
static void *device_link_add(struct device *c,struct device *s,int f);
static struct mt7996_hif *mt7996_pci_init_hif2(struct pci_dev *p) {
    if(!use_hif)return NULL;
    if(!device_link_add(&p->dev,&secondary.dev,DL_FLAG_AUTOREMOVE_CONSUMER))return (void *)(intptr_t)-ENOMEM;
    if(failed())return (void *)(intptr_t)-EPROBE_DEFER;
    refs++;return &hif;
}
static void mt7996_put_hif2(struct mt7996_hif *p) { if(p){assert(refs==1);refs--;} }
static void *device_link_add(struct device *c,struct device *s,int f) { assert(c==&primary.dev&&s==&secondary.dev&&f==DL_FLAG_AUTOREMOVE_CONSUMER);return failed()?NULL:(void *)1; }
static uintptr_t pci_resource_start(struct pci_dev *p,int b) { (void)p;(void)b;return 0; }
static int pci_domain_nr(void *bus) { (void)bus;return 0; }
static void mt76_npu_init(struct mt76_dev *d,uintptr_t b,int n) { (void)d;(void)b;(void)n; }
static bool mtk_wed_device_active(struct wed *w) { return w->active; }
static void mtk_wed_device_irq_set_mask(struct wed *w,int mask) { assert(w->active&&mask==0); }
static int mt7996_mmio_wed_init(struct mt7996_dev *d,struct pci_dev *p,bool second,int *irq) {
    struct wed *w=second?&d->mt76.mmio.wed_hif2:&d->mt76.mmio.wed;
    if(failed())return -EIO;
    if(!use_wed[second])return 0;
    assert(!p->vectors);p->vectors=2;w->active=true;w->pdev=p;*irq=p->irq;return 1;
}
static void mtk_wed_device_detach(struct wed *w) { assert(w->active&&!w->pdev->handlers&&w->pdev->vectors==2);w->pdev->vectors=0;w->active=false; }
static int pci_alloc_irq_vectors(struct pci_dev *p,int a,int b,int flags) {
    (void)a;(void)b;(void)flags;if(failed())return -ENOMEM;
    assert(!p->vectors);p->vectors=1;return 1;
}
static int pci_irq_vector(struct pci_dev *p,int i) { assert(i==0&&p->vectors==1);return p->irq; }
static void pci_free_irq_vectors(struct pci_dev *p) { assert(!p->handlers&&p->vectors==1);p->vectors=0; }
static int mt7996_irq_handler(void) { return 0; }
static int devm_request_irq(struct device *p,int irq,int (*f)(void),int flags,const char *name,struct mt7996_dev *d) {
    (void)flags;(void)name;assert(p==&primary.dev&&f==mt7996_irq_handler&&d==current);
    if(failed())return -EIO;
    assert(irq_dev(irq)->vectors&&!irq_dev(irq)->handlers);irq_dev(irq)->handlers++;return 0;
}
static void synchronize_irq(int irq) { assert(irq_dev(irq)->handlers);irq_dev(irq)->synchronized=true; }
static void devm_free_irq(struct device *p,int irq,struct mt7996_dev *d) { assert(p==&primary.dev&&d==current&&irq_dev(irq)->handlers==1&&d->mt76.irq_tasklet.killed);irq_dev(irq)->handlers--; }
static void tasklet_kill(struct tasklet *t) { assert((!primary.handlers||primary.synchronized)&&(!secondary.handlers||secondary.synchronized));t->killed=true; }
static void mt76_wr(struct mt7996_dev *d,int reg,int v) { assert(d==current&&reg>=1&&reg<=4);(void)v; }
static void mt76_free_device(struct mt76_dev *d) {
    assert(d==&current->mt76&&!primary.handlers&&!secondary.handlers&&!primary.vectors&&!secondary.vectors&&refs==0&&d->irq_tasklet.killed);
    assert(!current->init_work.pending&&!current->dump_work.pending&&!current->reset_work.pending&&!current->rc_work.pending&&!current->wed_rro.work.pending);
    free(current);current=NULL;frees++;
}
static void *pci_get_drvdata(struct pci_dev *p) { return p->data; }
static void cancel_work_sync(struct work *w) {
    assert(w->initialized);w->pending=false;
    /* A running dump producer may enqueue reset before cancel completes. */
    if(w->id==2)current->reset_work.pending=true;
}
static struct mt7996_phy *mt7996_phy2(struct mt7996_dev *d) { (void)d;return NULL; }
static struct mt7996_phy *mt7996_phy3(struct mt7996_dev *d) { (void)d;return NULL; }
static void mt7996_unregister_phy(struct mt7996_phy *p) { (void)p; }
static void mt7996_unregister_thermal(struct mt7996_phy *p) { (void)p; }
static void mt7996_coredump_unregister(struct mt7996_dev *d) { (void)d; }
static void mt76_unregister_device(struct mt76_dev *d) { (void)d; }
static void mt7996_mcu_exit(struct mt7996_dev *d) {
    assert(d->removing&&!d->recovery.hw_init_done&&primary.handlers&&(!use_hif||secondary.handlers));
    assert(d->mt76.napi[0].enabled&&d->mt76.tx_napi.enabled);
}
static void napi_disable(struct napi *n) { assert(n->enabled);n->enabled=false; }
static void mt76_worker_disable(int *worker) { (void)worker; }
static void netif_napi_del(struct napi *n) { assert(!n->enabled&&n->listed);n->listed=false; }
static void mt7996_tx_token_put(struct mt7996_dev *d) { (void)d; }
static void mt7996_dma_cleanup(struct mt7996_dev *d) {
    assert(!primary.handlers&&!secondary.handlers&&d->mt76.irq_tasklet.killed);
    assert(!d->mt76.tx_napi.enabled&&!d->mt76.tx_napi.listed);
    for(int i=0;i<3;i++)assert(!d->mt76.napi[i].enabled);
    if(dma_detach) {
        if(d->mt76.mmio.wed.active)mtk_wed_device_detach(&d->mt76.mmio.wed);
        if(d->mt76.mmio.wed_hif2.active)mtk_wed_device_detach(&d->mt76.mmio.wed_hif2);
    }
    d->dma_started=false;
}
static void mt7996_wed_rro_free(struct mt7996_dev *d) { assert(!d->dma_started); }
static bool mt7996_has_hwrro(struct mt7996_dev *d) { (void)d;return true; }
static void mt7996_rro_msdu_page_map_free(struct mt7996_dev *d) { assert(!use_wed[0]&&!d->dma_started); }
static int mt7996_register_device(struct mt7996_dev *d) {
    struct work *works[]={&d->init_work,&d->dump_work,&d->reset_work,&d->rc_work,&d->wed_rro.work};
    for(int i=0;i<5;i++){works[i]->initialized=true;works[i]->pending=true;works[i]->id=i+1;}
    if(register_stage>0) {
        d->dma_started=true;
        for(int i=0;i<register_stage-1 && i<3;i++) d->mt76.napi[i]=(struct napi){(void *)1,true,true};
        if(register_stage>=4)d->mt76.tx_napi=(struct napi){(void *)1,true,true};
        if(register_stage>=5)d->mcu_started=true;
    }
    if(failed())return -EINVAL;
    d->recovery.hw_init_done=true;return 0;
}
/* Actual functions are inserted below, without rewriting their bodies. */
/* DRIVER_FUNCTIONS */
static void resources_empty(void) {
    assert(!current&&!refs&&allocs==frees&&!primary.vectors&&!secondary.vectors&&!primary.handlers&&!secondary.handlers);
}
int main(void) {
    struct pci_device_id id={0x7993};
    for(int h=0;h<2;h++)for(int w=0;w<4;w++)for(int detach=0;detach<2;detach++)
    for(int stage=0;stage<=5;stage++)for(int fail=0;fail<=14;fail++) {
        primary=(struct pci_dev){.irq=41};primary.dev.owner=&primary;
        secondary=(struct pci_dev){.irq=42};secondary.dev.owner=&secondary;
        hif=(struct mt7996_hif){.dev=&secondary.dev,.irq=42};
        use_hif=h;use_wed[0]=w&1;use_wed[1]=w&2;dma_detach=detach;
        register_stage=stage;fail_at=fail;step=refs=allocs=frees=0;
        int ret=mt7996_pci_probe(&primary,&id);
        if(!ret) {
            /* Source initializer success only occurs with the complete DMA/MCU stage. */
            mt7996_pci_remove(&primary);
            resources_empty();
            /* Primary-only rebind while HIF remains bound, then full module unload. */
            fail_at=0;step=0;register_stage=5;
            assert(mt7996_pci_probe(&primary,&id)==0);
            mt7996_pci_remove(&primary);
            full_module=true;
        }
        resources_empty();cases++;
    }
    assert(full_module);
    printf("PASS: %d actual-source probe/unwind/unbind/rebind scenarios; all IRQ/vector/ref/work ordering assertions held.\n",cases);
}
