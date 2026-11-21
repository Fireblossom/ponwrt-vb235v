"""Check native SPI-NAND policy hooks using actual functions and counted I/O."""
import argparse,re,subprocess,tempfile,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
s=(a.source/'drivers/mtd/nand/spi/core.c').read_text()
def extract(name):
 m=re.search(r'(?m)^(?:static )?int\s+'+name+r'\([^;]*?\)\s*\{',s);assert m
 i=m.end();depth=1
 while depth:depth+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[m.start():i]
f=extract('spinand_vb235v_program_check');mark=extract('spinand_markbad');write=extract('spinand_write_page');erase=extract('spinand_erase')
assert write.index('spinand_vb235v_program_check')<write.index('spinand_write_enable_op')
assert erase.index('vb_hybrid_check')<erase.index('spinand_select_target')
code=r'''
#include <stdio.h>
#include <stdlib.h>
#include <assert.h>
#include <string.h>
#include "vb235v-hybrid-policy.h"
#define MTD_OPS_RAW 2
#define MTD_OPS_PLACE_OOB 0
struct nand_pos {unsigned target,page,block;};
struct nand_device {int unused;};
struct nand_page_io_req {struct nand_pos pos;unsigned dataoffs,datalen,ooboffs,ooblen;union {const u8 *out;}oobbuf;int mode;};
struct spinand_device {struct vb_hybrid_policy vb235v_policy;bool vb235v_hybrid;struct nand_device nand;};
static unsigned selects,writes;static u8 captured[2];
static struct nand_device *spinand_to_nand(struct spinand_device *s){return &s->nand;}
static u64 nanddev_pos_to_offs(struct nand_device *n,const struct nand_pos *p){return p->block*VB_HYBRID_ERASE+p->page*4096ULL;}
static int spinand_select_target(struct spinand_device *s,unsigned target){selects++;return 0;}
'''+f+r'''
static int spinand_write_page(struct spinand_device *s,const struct nand_page_io_req *req){int r=spinand_vb235v_program_check(s,req);if(r)return r;assert(req->ooblen==2);captured[0]=req->oobbuf.out[0];captured[1]=req->oobbuf.out[1];writes++;return 0;}
'''+mark+r'''
int main(void){unsigned checks=0;struct spinand_device s={0};struct nand_page_io_req req={0};struct nand_pos pos={0};
s.vb235v_hybrid=true;s.vb235v_policy=(struct vb_hybrid_policy){true,true,false,true};req.datalen=4096;
for(unsigned b=0;b<2048;b++){req.pos.block=b;int r=spinand_vb235v_program_check(&s,&req);assert((r==0)==(b>=370&&b<689));checks++;}
req.pos.block=688;req.mode=MTD_OPS_RAW;assert(spinand_vb235v_program_check(&s,&req)==-EINVAL);checks++;
req.mode=0;req.dataoffs=1;assert(spinand_vb235v_program_check(&s,&req)==-EINVAL);checks++;
req.dataoffs=0;req.ooblen=2;assert(spinand_vb235v_program_check(&s,&req)==-EINVAL);checks++;
pos.block=688;assert(spinand_markbad(&s.nand,&pos)==0&&writes==1&&selects==1&&captured[0]==255&&captured[1]==0);checks++;
pos.block=0;assert(spinand_markbad(&s.nand,&pos)==-ERANGE&&writes==1&&selects==1);checks++;
pos.block=688;s.vb235v_policy.retirement_admitted=false;assert(spinand_markbad(&s.nand,&pos)==-EROFS&&writes==1&&selects==1);checks++;
s.vb235v_policy=(struct vb_hybrid_policy){0};req.ooblen=0;assert(spinand_vb235v_program_check(&s,&req)==-EROFS);checks++;
s.vb235v_hybrid=false;assert(spinand_vb235v_program_check(&s,&req)==0);checks++;
printf("{\"assertions\":%u,\"all_physical_blocks_checked\":2048,\"actual_program_and_retire_hooks\":true,\"reject_before_SPI_selection_or_WREN\":true,\"runtime_marker_0xff_0x00\":true,\"default_writes_denied\":true,\"asan_ubsan\":true}\n",checks);
}
'''
# nand_to_spinand in the actual function uses container_of semantics.
if 'bool ubi_test_only;' in (a.source/'include/linux/mtd/vb235v-hybrid-policy.h').read_text():
 code=code.replace('s.vb235v_hybrid=false;',r'''
s.vb235v_policy=(struct vb_hybrid_policy){.identity_verified=true,.writes_admitted=true,.retirement_admitted=true,.ubi_test_only=true};
for(unsigned b=0;b<2048;b++){req.pos.block=b;int r=spinand_vb235v_program_check(&s,&req);assert((r==0)==(b>=657&&b<689));checks++;}
pos.block=688;assert(spinand_markbad(&s.nand,&pos)==-EROFS&&writes==1&&selects==1);checks++;
s.vb235v_policy.scratch_only=true;req.pos.block=688;assert(spinand_vb235v_program_check(&s,&req)==-EINVAL);checks++;
s.vb235v_hybrid=false;''')
code=code.replace('static struct nand_device *spinand_to_nand', 'static struct spinand_device *nand_to_spinand(struct nand_device *n){return (struct spinand_device *)((char *)n-__builtin_offsetof(struct spinand_device,nand));}\nstatic struct nand_device *spinand_to_nand')
with tempfile.TemporaryDirectory() as td:
 d=Path(td);(d/'linux').mkdir();(d/'linux/types.h').write_text('#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint64_t u64;\n');(d/'vb235v-hybrid-policy.h').write_text((a.source/'include/linux/mtd/vb235v-hybrid-policy.h').read_text());(d/'test.c').write_text(code)
 subprocess.run(['cc','-O1','-g','-fsanitize=address,undefined','-I',str(d),str(d/'test.c'),'-o',str(d/'test')],check=True);r=subprocess.run([str(d/'test')],check=True,capture_output=True,text=True);a.output.write_text(json.dumps(json.loads(r.stdout),indent=2)+'\n');print(r.stdout,end='')
