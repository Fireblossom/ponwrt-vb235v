/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef VB235V_CPUFREQ_CONTRACT_H
#define VB235V_CPUFREQ_CONTRACT_H

/* Units are MHz at the retained OEM BL31 boundary, kHz at cpufreq. */
#define VB235V_CPU_SMC 0x82000301U
#define VB235V_CPU_SET 0xddddddd1U
#define VB235V_CPU_GET 0xddddddd2U

struct vb235v_cpu_state {
	unsigned int admitted;
	unsigned int faulted;
	unsigned int legacy_ack;
	unsigned long last_status;
	unsigned long last_mhz;
};

struct vb235v_cpu_ops {
	unsigned long (*get_mhz)(void *data);
	unsigned long (*set_state)(void *data, unsigned int state);
	int (*identity_ok)(void *data);
	int (*clock_ok)(void *data);
};

static inline unsigned int vb235v_cpu_decode(unsigned long mhz)
{
	return mhz == 500 || mhz == 1200 ? (unsigned int)mhz * 1000 : 0;
}

static inline int vb235v_cpu_admit(struct vb235v_cpu_state *s,
				 unsigned long boot_mhz)
{
	s->admitted = boot_mhz == 1200;
	s->faulted = !s->admitted;
	s->legacy_ack = 0;
	s->last_status = 0;
	s->last_mhz = boot_mhz;
	return s->admitted ? 0 : -ENODEV;
}

/* Caller serializes all access, including the observational get callback.
 * No voltage, PLL MMIO, retry, or speculative recovery is permitted here.
 */
static inline int vb235v_cpu_transition(struct vb235v_cpu_state *s,
	unsigned int target_khz, int enabled, const struct vb235v_cpu_ops *ops,
	void *data)
{
	unsigned int before, after, state;
	unsigned long status;

	if (!s->admitted || s->faulted)
		return -EIO;
	if (target_khz != 500000 && target_khz != 1200000)
		return -EINVAL;
	s->last_mhz = ops->get_mhz(data);
	before = vb235v_cpu_decode(s->last_mhz);
	if (!before || !ops->clock_ok(data)) {
		s->faulted = 1;
		return -EIO;
	}
	if (before == target_khz)
		return 0; /* Read-only boot never emits SET, even for performance. */
	if (!enabled)
		return -EPERM;
	if (!ops->identity_ok(data)) {
		s->faulted = 1;
		return -EIO;
	}
	state = (target_khz - 500000) / 50000;
	status = ops->set_state(data, state);
	s->last_status = status;
	s->last_mhz = ops->get_mhz(data);
	after = vb235v_cpu_decode(s->last_mhz);
	/* Exact retained BL31 discards the PLL routine's result and always
	 * returns -2. This is no success status: GET + mux/divider prove it.
	 * SMC32 implementations may zero-extend or sign-extend the same -2.
	 */
	if (status == (unsigned long)-2 || status == 0xfffffffeUL)
		s->legacy_ack++;
	else if (status) {
		s->faulted = 1;
		return -EIO;
	}
	if (after != target_khz || !ops->clock_ok(data)) {
		s->faulted = 1;
		return -EIO; /* Freeze writes until reboot; no unverified rollback. */
	}
	return 0;
}
#endif
