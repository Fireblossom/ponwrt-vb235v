/* SPDX-License-Identifier: GPL-2.0-only */
/* Execute the actual selected QPHY C sequence against modeled register I/O. */
#include <assert.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint32_t u32;
#include "qphy-fields.h"
struct vb235v_qphy {
	u32 regs[3][1024];
	u32 seed, valid, term, imp, checks, ready_after;
	unsigned writes;
	void *dev;
};
static u32 *reg(struct vb235v_qphy *p, u32 base, u32 offset, u32 address)
{
	unsigned bank = base == QP_ANA_BASE ? 0 : base == QP_DIG_BASE ? 1 : 2;
	assert(base == QP_ANA_BASE || base == QP_DIG_BASE || base == QP_PMA_BASE);
	assert(address >= offset && address-offset <= 0xffc && !(address&3));
	return &p->regs[bank][(address-offset)/4];
}
static u32 read_reg(struct vb235v_qphy *p, u32 base, u32 offset, u32 address)
{
	u32 value = *reg(p,base,offset,address);
	if (base == QP_PMA_BASE && address-offset == 0x364) {
		u32 debug = p->regs[0][0x38/4] & (1u<<19);
		u32 state = p->checks/2 >= p->ready_after ? (debug ? 1 : 0x80) : 0;
		p->checks++;
		value = (value & ~(0xffu<<16)) | state<<16;
	}
	return value;
}
static void write_reg(struct vb235v_qphy *p,u32 base,u32 offset,u32 address,u32 value)
{
	/* Only PLL force/selection bits may change in this control register.
	 * This detects the original uninitialized local-variable write. */
	if (base == QP_PMA_BASE && address-offset == 0x31c)
		assert((value & ~0x30u) == (p->seed & ~0x30u));
	*reg(p,base,offset,address) = value;
	p->writes++;
}
static u32 efuse(struct vb235v_qphy *p,u32 bit,u32 width)
{
	if(bit==32 && width==1) return p->valid;
	if(bit==67 && width==2) return p->term;
	assert(bit==69 && width==5);
	return p->imp;
}
#define Reg_R(base,offset,address) read_reg(priv,base,offset,address)
#define Reg_W(base,offset,address,value) write_reg(priv,base,offset,address,value)
#define get_phy_efuse(bit,width) efuse(priv,bit,width)
#define udelay(x) ((void)(x))
#define mdelay(x) ((void)(x))
#define dev_dbg(...) ((void)0)
#include "qphy-sequence.inc"
int main(void)
{
	unsigned cases = 0;
	for (unsigned seed=0; seed<16; seed++)
	for (unsigned valid=0; valid<2; valid++)
	for (unsigned term=0; term<4; term++)
	for (unsigned imp=0; imp<32; imp+=31)
	for (unsigned ready=0; ready<3; ready++) {
		struct vb235v_qphy p = {0};
		p.seed = seed == 0 ? 0 : seed == 1 ? ~0u : 0x9e3779b9u*seed;
		for(unsigned b=0;b<3;b++) for(unsigned n=0;n<1024;n++) p.regs[b][n]=p.seed;
		p.valid=valid; p.term=term; p.imp=imp;
		p.ready_after=ready==0 ? 0 : ready==1 ? 3 : 999;
		PCIe_QPhy_Load_Efuse(&p);
		int result=pcie_QPhy_init(&p);
		assert(result == (ready==2 ? -ETIMEDOUT : 0));
		assert(((p.regs[2][0x320/4]>>5)&3) == (valid ? term : 1));
		assert(((p.regs[2][0x324/4]>>26)&31) == (valid ? imp : 1));
		assert((p.regs[2][0x318/4]&0x3000) == (ready==2 ? 0x2000 : 0));
		assert(p.writes > 30);
		cases++;
	}
	printf("{\"modeled_cases_passed\":%u,\"hardware_access\":false}\n",cases);
	return 0;
}
