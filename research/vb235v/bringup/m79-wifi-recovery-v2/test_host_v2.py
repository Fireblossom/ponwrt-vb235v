#!/usr/bin/env python3
"""Real helper + real common cleanup model, including non-idempotent park."""
import hashlib
import json
from pathlib import Path
import re
import resource
import subprocess
import sys

v1src,src,out=map(Path,sys.argv[1:4])
here=Path(__file__).resolve().parent
out.mkdir(parents=True,exist_ok=True)
resource.setrlimit(resource.RLIMIT_CORE,(0,0))

def function(root,path,name):
    text=(root/path).read_text()
    match=re.search(r'^(?:static )?(?:inline )?(?:void|int) '+name+r'\([^;]+?\)\n\{',text,re.M)
    assert match,(path,name)
    end=match.end();depth=1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[match.start():end]+'\n'

base=(here.parent/'m79-wifi-recovery/host_lifecycle.c').read_text()
base=base.replace('#define EPROBE_DEFER 517','#define EPROBE_DEFER 517\n#define NAPI_STATE_LISTED 0\n#define mt76_for_each_q_rx(d,i) for ((i)=0;(i)<3;(i)++) if ((d)->q_rx[i].ndesc)')
base=base.replace('struct napi { void *dev; bool enabled, listed; };','''struct napi { void *dev; bool enabled, listed; unsigned long state; };
struct task_struct { bool should_park, exiting; };
struct mt76_worker { struct task_struct *task; unsigned long state; };
struct mt76_queue { int ndesc; void *page_pool; };
struct mt76_phy { struct mt76_queue *q_tx[2]; };
static int live_workers,park_calls,stop_calls;
static inline bool test_bit(int bit,const unsigned long *value) {return (*value & BIT(bit))!=0;}
static int kthread_park(struct task_struct *task) {
    assert(!task->exiting);
    if(task->should_park){fprintf(stderr,"WARNING: kthread_park: KTHREAD_SHOULD_PARK already set (v1 live failure); prior successful park calls=%d\\n",park_calls);abort();}
    task->should_park=true;park_calls++;return 0;
}
static int kthread_stop(struct task_struct *task) {
    assert(!task->exiting);task->exiting=true;task->should_park=false;
    live_workers--;stop_calls++;free(task);return 0;
}
''')
base=base.replace('    int tx_worker;','''    struct mt76_worker tx_worker;
    struct mt76_phy *phys[3];
    struct mt76_queue *q_mcu[2],q_rx[3];
    void *napi_dev,*tx_napi_dev;
    void *wq,*hw;''')
helpers='\n'.join(function(src,'util.h',n) for n in ['mt76_worker_disable','mt76_worker_teardown'])
base=base.replace('static struct pci_dev primary, secondary;',helpers+'\nstatic struct pci_dev primary, secondary;')
base=base.replace('    current->mt76.dev=p;p->owner->data=&current->mt76;return current;', '    current->mt76.dev=p;current->mt76.hw=current;p->owner->data=&current->mt76;return current;')
base=base.replace('static void mt76_free_device(struct mt76_dev *d) {','static void ieee80211_free_hw(void *hw) {\n    struct mt76_dev *d=&current->mt76;assert(hw==current&&!d->tx_worker.task&&live_workers==0);')
base=base.replace('static void mt76_worker_disable(int *worker) { (void)worker; }','')
base=base.replace('static void netif_napi_del(struct napi *n) { assert(!n->enabled&&n->listed);n->listed=false; }','static void netif_napi_del(struct napi *n) { assert(!n->enabled&&n->listed);n->listed=false;n->state&=~BIT(NAPI_STATE_LISTED); }')
start=base.index('static void mt7996_dma_cleanup(')
end=base.index('static void mt7996_wed_rro_free(',start)
base=base[:start]+'''static void mt76_dma_tx_cleanup(struct mt76_dev *d,struct mt76_queue *q,bool flush) {(void)d;(void)q;assert(flush);}
static void mt76_dma_rx_cleanup(struct mt76_dev *d,struct mt76_queue *q) {(void)d;(void)q;}
static void page_pool_destroy(void *p) {(void)p;}
static void mt76_free_pending_txwi(struct mt76_dev *d) {(void)d;}
static void mt76_free_pending_rxwi(struct mt76_dev *d) {(void)d;}
static void free_netdev(void *p) {(void)p;}
static void destroy_workqueue(void *p) {(void)p;}
static void mt76_npu_deinit(struct mt76_dev *d) {(void)d;}
'''+function(src,'mac80211.c','mt76_free_device')+function(src,'dma.c','mt76_dma_cleanup')+'''static void mt7996_dma_cleanup(struct mt7996_dev *d) {
    assert(!primary.handlers&&!secondary.handlers&&d->mt76.irq_tasklet.killed);
    assert(!d->mt76.tx_worker.task||d->mt76.tx_worker.task->should_park);
    mt76_dma_cleanup(&d->mt76);
    d->dma_started=false;
}
'''+base[end:]
# Every stage with queues exercises cleanup even before NAPI exists.
base=base.replace('        d->dma_started=true;','        d->dma_started=true;\n        for(int q=0;q<3;q++)d->mt76.q_rx[q].ndesc=1;')
base=base.replace('(struct napi){(void *)1,true,true}', '(struct napi){(void *)1,true,true,BIT(NAPI_STATE_LISTED)}')
base=base.replace('    if(failed())return -EINVAL;', '''    if(register_stage>=4) {
        d->mt76.tx_worker.task=calloc(1,sizeof(struct task_struct));assert(d->mt76.tx_worker.task);
        d->mt76.tx_worker.task->should_park=dma_detach;live_workers++;
    }
    if(failed())return -EINVAL;''')
base=base.replace('    printf("PASS: %d actual-source probe/unwind/unbind/rebind scenarios; all IRQ/vector/ref/work ordering assertions held.\\n",cases);','    assert(live_workers==0&&stop_calls>0&&park_calls==0);\n    printf("PASS: %d actual-source scenarios, worker stop/free idempotence and NAPI disable/delete ownership held; park=%d stop=%d.\\n",cases,park_calls,stop_calls);')
# A surviving worker must fail before any primary handler can be removed.
base=base.replace('static void devm_free_irq(struct device *p,int irq,struct mt7996_dev *d) { assert(', 'static void devm_free_irq(struct device *p,int irq,struct mt7996_dev *d) { assert(!d->mt76.tx_worker.task||d->mt76.tx_worker.task->should_park);assert(')

names=['mt7996_pci_quiesce','mt7996_unregister_device','mt7996_pci_release','mt7996_pci_probe','mt7996_pci_remove']
def driver(root):
    return '\n'.join(function(root,'mt7996/init.c' if n=='mt7996_unregister_device' else 'mt7996/pci.c',n) for n in names)
c=base.replace('/* DRIVER_FUNCTIONS */',driver(src))
cmd=['gcc','-std=gnu11','-g','-O1','-Wall','-Wextra','-Werror','-Wno-sign-compare','-Wno-unused-variable',
     '-fsanitize=address,undefined','-fno-omit-frame-pointer']
def run(name,code):
    path=out/(name+'.c');path.write_text(code)
    binary=out/name
    subprocess.run(cmd+[str(path),'-o',str(binary)],check=True)
    return subprocess.run([str(binary)],capture_output=True,text=True)
good=run('v2',c)
assert good.returncode==0,good.stderr
print(good.stdout,end='')
old=base.replace('/* DRIVER_FUNCTIONS */',driver(v1src))
repro=run('v1-real-park-regression',old)
assert repro.returncode!=0 and 'KTHREAD_SHOULD_PARK already set' in repro.stderr and 'prior successful park calls=1' in repro.stderr,repro.stderr
print('PASS: frozen v1 reproduces exact non-idempotent kthread_park warning')
mutations={}
for name,needle in {
    'tx-napi-double-disable':'if (test_bit(NAPI_STATE_LISTED, &dev->tx_napi.state))',
    'rx-napi-double-disable':'if (dev->napi[i].dev)\n\t\t\tnetif_napi_del(&dev->napi[i]);',
}.items():
    assert needle in c
    replacement='if (dev->tx_napi.dev)' if name.startswith('tx') else 'if (dev->napi[i].dev) {\n\t\t\tnapi_disable(&dev->napi[i]);\n\t\t\tnetif_napi_del(&dev->napi[i]);\n\t\t}'
    bad=run('mutation-'+name,c.replace(needle,replacement))
    assert bad.returncode!=0 and 'n->enabled' in bad.stderr,bad.stderr
    mutations[name]={'detected':True,'returncode':bad.returncode,'stderr_tail':bad.stderr[-1000:]}
    print('PASS: duplicate NAPI stop mutation detected:',name)
for name,needle in {
    'hif2-vector-leak':'pci_free_irq_vectors(to_pci_dev(dev->hif2->dev));',
    'handler-after-free':'devm_free_irq(mdev->dev, dev->pci_irq, dev);',
    'reset-work-after-free':'cancel_work_sync(&dev->reset_work);',
}.items():
    assert needle in c
    bad=run('mutation-'+name,c.replace(needle,'(void)0;'))
    assert bad.returncode!=0 and 'Assertion' in bad.stderr,bad.stderr
    mutations[name]={'detected':True,'returncode':bad.returncode,'stderr_tail':bad.stderr[-1000:]}
    print('PASS: original lifecycle regression mutation detected:',name)
report={'status':'passed','stdout':good.stdout.strip(),'real_functions':['util.h: mt76_worker_disable/teardown','dma.c: mt76_dma_cleanup','mac80211.c: mt76_free_device']+names,
        'v1_regression':{'reproduced':True,'returncode':repro.returncode,'stderr_tail':repro.stderr[-1000:]},
        'mutations':mutations,'test_source_sha256':hashlib.sha256(c.encode()).hexdigest(),
        'limitations':['Kernel scheduling/DMA hardware mocked; kthread park stop and NAPI enabled/listed contract explicitly modeled.']}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
