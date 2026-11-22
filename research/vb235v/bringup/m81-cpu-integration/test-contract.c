/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include "vb235v-cpufreq-contract.h"
struct fake {
	unsigned long mhz, status;
	unsigned int gets, sets, state, fail_after;
	unsigned int identity, clock_bad_after, clocks;
};
static int identity(void *p) { return ((struct fake *)p)->identity; }
static int clock_ok(void *p)
{
	struct fake *f = p;
	f->clocks++;
	return !f->clock_bad_after || f->clocks < f->clock_bad_after;
}
static unsigned long get(void *p)
{
	struct fake *f = p;
	f->gets++;
	return f->fail_after && f->gets >= f->fail_after ? ~0UL : f->mhz;
}
static unsigned long set(void *p, unsigned int state)
{
	struct fake *f = p;
	f->sets++;
	f->state = state;
	if (!f->status || f->status == (unsigned long)-2 || f->status == 0xfffffffeUL)
		f->mhz = 500 + state * 50;
	return f->status;
}
static unsigned long wrong_get(void *p) { (void)p; return 1200; }
int main(void)
{
	struct vb235v_cpu_state s;
	struct fake f = { .mhz = 1200, .identity = 1 };
	const struct vb235v_cpu_ops ops = { get, set, identity, clock_ok };
	const struct vb235v_cpu_ops wrong = { wrong_get, set, identity, clock_ok };
	unsigned long bad[] = { 0, 500, 800, 1200000, ~0UL, 0xffffffffUL };
	unsigned int i;
	for (i = 0; i < sizeof(bad)/sizeof(bad[0]); i++) {
		assert(vb235v_cpu_admit(&s, bad[i]) == -ENODEV);
		assert(vb235v_cpu_transition(&s, 500000, 1, &ops, &f) == -EIO);
		assert(!f.sets);
	}
	assert(!vb235v_cpu_admit(&s, 1200));
	assert(!vb235v_cpu_enable_check(&s, 0, &ops, &f));
	assert(!f.sets && !s.set_count); /* Read-only pre-arm must never SET. */
	assert(vb235v_cpu_enable_check(&s, 1, &ops, &f) == -EBUSY);
	assert(!s.faulted && !f.sets);
	assert(!vb235v_cpu_transition(&s, 1200000, 0, &ops, &f));
	assert(!f.sets);
	assert(vb235v_cpu_transition(&s, 500000, 0, &ops, &f) == -EPERM);
	assert(vb235v_cpu_transition(&s, 750000, 1, &ops, &f) == -EINVAL);
	assert(!f.sets);
	assert(!vb235v_cpu_transition(&s, 500000, 1, &ops, &f));
	assert(f.state == 0 && f.mhz == 500 && f.sets == 1);
	assert(!vb235v_cpu_transition(&s, 1200000, 1, &ops, &f));
	assert(f.state == 14 && f.mhz == 1200 && f.sets == 2);
	assert(s.set_count == 2);
	f.status = ~0UL;
	assert(vb235v_cpu_transition(&s, 500000, 1, &ops, &f) == -EIO);
	assert(s.faulted && f.sets == 3);
	assert(vb235v_cpu_transition(&s, 1200000, 1, &ops, &f) == -EIO);
	assert(f.sets == 3); /* No automatic SET retry or rollback. */
	assert(!vb235v_cpu_admit(&s, 1200)); f.status = 0;
	assert(vb235v_cpu_transition(&s, 500000, 1, &wrong, &f) == -EIO);
	assert(s.faulted && f.sets == 4); /* Successful SET with wrong readback. */
	assert(!vb235v_cpu_admit(&s, 1200)); f.mhz = 1200; f.gets = 0; f.fail_after = 2;
	assert(vb235v_cpu_transition(&s, 500000, 1, &ops, &f) == -EIO);
	assert(s.faulted && f.sets == 5); /* Readback unknown. */
	assert(!vb235v_cpu_admit(&s, 1200)); f.gets = 0; f.fail_after = 1;
	assert(vb235v_cpu_transition(&s, 500000, 1, &ops, &f) == -EIO);
	assert(s.faulted && f.sets == 5); /* Preflight unknown, no SET. */
	assert(!vb235v_cpu_decode(1200000));
	assert(!vb235v_cpu_decode(~0UL));
	f = (struct fake){ .mhz = 1200, .identity = 0 };
	assert(!vb235v_cpu_admit(&s, 1200));
	assert(vb235v_cpu_transition(&s, 500000, 1, &ops, &f) == -EIO);
	assert(s.faulted && !f.sets); /* Wrong BL31 identity cannot emit SET. */
	f = (struct fake){ .mhz = 1200, .identity = 1, .status = (unsigned long)-2 };
	assert(!vb235v_cpu_admit(&s, 1200));
	assert(!vb235v_cpu_transition(&s, 500000, 1, &ops, &f));
	assert(s.legacy_ack == 1 && f.state == 0);
	f.status = 0xfffffffeUL;
	assert(!vb235v_cpu_transition(&s, 1200000, 1, &ops, &f));
	assert(s.legacy_ack == 2 && f.state == 14);
	assert(vb235v_cpu_transition(&s, 500000, 1, &wrong, &f) == -EIO);
	assert(s.faulted && s.legacy_ack == 3 && s.last_mhz == 1200);
	f = (struct fake){ .mhz = 1200, .identity = 1, .clock_bad_after = 1 };
	assert(!vb235v_cpu_admit(&s, 1200));
	assert(vb235v_cpu_transition(&s, 500000, 1, &ops, &f) == -EIO);
	assert(s.faulted && !f.sets); /* Wrong mux/divider preflight. */
	f = (struct fake){ .mhz = 1200, .identity = 1, .clock_bad_after = 2, .status = (unsigned long)-2 };
	assert(!vb235v_cpu_admit(&s, 1200));
	assert(vb235v_cpu_transition(&s, 500000, 1, &ops, &f) == -EIO);
	assert(s.faulted && f.sets == 1 && s.last_mhz == 500); /* PLL GET matches, CPU mux does not. */
	f = (struct fake){ .mhz = 1200, .identity = 0 };
	assert(!vb235v_cpu_admit(&s, 1200));
	assert(vb235v_cpu_enable_check(&s, 0, &ops, &f) == -EIO);
	assert(s.faulted && !f.sets && !s.set_count);
	f = (struct fake){ .mhz = 0xffffffffUL, .identity = 1 };
	assert(!vb235v_cpu_admit(&s, 1200));
	assert(vb235v_cpu_enable_check(&s, 0, &ops, &f) == -EIO);
	assert(s.faulted && !f.sets && !s.set_count);
	puts("M81 transition/pre-arm contract: no query SETs, shared-SCU refusal, state0/14, exact identity, legacy ACK, readback and fault latch PASS");
	return 0;
}
