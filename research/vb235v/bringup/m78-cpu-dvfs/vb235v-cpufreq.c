// SPDX-License-Identifier: GPL-2.0-only
/* VB235v retained-BL31 CPU frequency bring-up. Boot voltage is held unchanged.
 * This deliberately does not claim OEM AVS/thermal parity.
 */
#define pr_fmt(fmt) KBUILD_MODNAME ": " fmt
#include <linux/arm-smccc.h>
#include <linux/cpufreq.h>
#include <linux/cpu.h>
#include <linux/errno.h>
#include <linux/io.h>
#include <linux/module.h>
#include <linux/mtd/mtd.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/slab.h>
#include <crypto/sha2.h>
#include "vb235v-cpufreq-contract.h"

static DEFINE_MUTEX(vb235v_cpu_lock);
static struct vb235v_cpu_state vb235v_cpu_state;
static unsigned long boot_frequency_mhz;
static void __iomem *cpu_mux_div;
static bool retained_bl31_verified;
static bool allow_transitions;
module_param(allow_transitions, bool, 0600);
MODULE_PARM_DESC(allow_transitions,
	"Enable manually supervised 500/1200 MHz transitions; default read-only");
module_param_named(faulted, vb235v_cpu_state.faulted, uint, 0400);
module_param(boot_frequency_mhz, ulong, 0400);
module_param_named(legacy_ack, vb235v_cpu_state.legacy_ack, uint, 0400);
module_param_named(last_status, vb235v_cpu_state.last_status, ulong, 0400);
module_param_named(last_mhz, vb235v_cpu_state.last_mhz, ulong, 0400);
module_param(retained_bl31_verified, bool, 0400);

static int vb235v_clock_ok(void *data)
{
	u32 value = readl(cpu_mux_div);

	/* GET only reports ARMPLL, not the CPU mux or divider. */
	return ((value >> 9) & 3) == 1 && ((value >> 17) & 0x1f) == 0;
}

static int vb235v_identity_ok(void *data)
{
	static const u8 expected[SHA256_DIGEST_SIZE] = {
		0xc1, 0x12, 0xe9, 0x88, 0x22, 0xae, 0xf6, 0x33,
		0x4f, 0x88, 0x61, 0x21, 0x2a, 0x1d, 0xa5, 0xfa,
		0x31, 0x58, 0xc0, 0xe3, 0xac, 0x60, 0xfa, 0x09,
		0xe4, 0x03, 0xab, 0xcc, 0xd7, 0x54, 0x72, 0x8f,
	};
	struct mtd_info *mtd;
	u8 digest[SHA256_DIGEST_SIZE];
	u8 *payload;
	size_t length = 0;
	int ret;

	if (retained_bl31_verified)
		return 1;
	/* This read is delayed until the first explicitly enabled SET, so MTD
	 * discovery order cannot turn read-only boot into a probe dependency.
	 * No MTD write/erase/unlock or automatic recovery is ever performed.
	 */
	mtd = get_mtd_device_nm("bootloader-protected");
	if (IS_ERR(mtd))
		return 0;
	if (!(mtd->flags & MTD_WRITEABLE) && mtd->size == 0xc0000) {
		payload = kvmalloc(56846, GFP_KERNEL);
		if (payload) {
			ret = mtd_read(mtd, 0x21800, 56846, &length, payload);
			if ((!ret || mtd_is_bitflip(ret)) && length == 56846) {
				sha256(payload, length, digest);
				retained_bl31_verified = !memcmp(digest, expected,
							  sizeof(expected));
			}
			kvfree(payload);
		}
	}
	put_mtd_device(mtd);
	if (!retained_bl31_verified)
		pr_err("retained read-only BL31 payload identity not established; no SET permitted\n");
	return retained_bl31_verified;
}

static unsigned long vb235v_get_mhz(void *data)
{
	struct arm_smccc_res res;

	arm_smccc_smc(VB235V_CPU_SMC, VB235V_CPU_GET, 0, 0, 0, 0, 0, 0, &res);
	return res.a0;
}

static unsigned long vb235v_set_state(void *data, unsigned int state)
{
	struct arm_smccc_res res;

	arm_smccc_smc(VB235V_CPU_SMC, VB235V_CPU_SET, 0, state,
		     0, 0, 0, 0, &res);
	return res.a0;
}

static const struct vb235v_cpu_ops vb235v_ops = {
	.get_mhz = vb235v_get_mhz,
	.set_state = vb235v_set_state,
	.identity_ok = vb235v_identity_ok,
	.clock_ok = vb235v_clock_ok,
};

static struct cpufreq_frequency_table vb235v_table[] = {
	{ .frequency = 500000 },
	{ .frequency = 1200000 },
	{ .frequency = CPUFREQ_TABLE_END },
};

static unsigned int vb235v_get(unsigned int cpu)
{
	unsigned int khz;

	mutex_lock(&vb235v_cpu_lock);
	vb235v_cpu_state.last_mhz = vb235v_get_mhz(NULL);
	khz = vb235v_cpu_decode(vb235v_cpu_state.last_mhz);
	if (!khz || !vb235v_clock_ok(NULL)) {
		vb235v_cpu_state.faulted = 1;
		khz = 0;
		pr_err_ratelimited("SMC frequency unknown; transitions latched off until reboot\n");
	}
	mutex_unlock(&vb235v_cpu_lock);
	return khz;
}

static int vb235v_target(struct cpufreq_policy *policy, unsigned int index)
{
	int ret;

	if (index >= ARRAY_SIZE(vb235v_table) - 1)
		return -EINVAL;
	mutex_lock(&vb235v_cpu_lock);
	ret = vb235v_cpu_transition(&vb235v_cpu_state,
		vb235v_table[index].frequency, READ_ONCE(allow_transitions),
		&vb235v_ops, NULL);
	if (vb235v_cpu_state.faulted)
		pr_err_ratelimited("transition/identity/mux failure: status=0x%lx GET=%lu MHz; no rollback, writes latched off until reboot\n",
			vb235v_cpu_state.last_status, vb235v_cpu_state.last_mhz);
	mutex_unlock(&vb235v_cpu_lock);
	return ret;
}

static int vb235v_policy_init(struct cpufreq_policy *policy)
{
	unsigned int observed_khz = vb235v_get(policy->cpu);

	if (!observed_khz || vb235v_cpu_state.faulted)
		return -EIO;
	/* Physical shared ARM clock domain, restricted to actual Linux CPUs.
	 * The six NPU processors and disabled OEM template CPUs are excluded.
	 */
	cpumask_copy(policy->cpus, cpu_possible_mask);
	policy->freq_table = vb235v_table;
	policy->cur = observed_khz;
	/* Unknown latency, not a fabricated measurement. Dynamic governors are
	 * separately refused by CPUFREQ_NO_AUTO_DYNAMIC_SWITCHING.
	 */
	policy->cpuinfo.transition_latency = 0;
	policy->shared_type = CPUFREQ_SHARED_TYPE_ALL;
	return 0;
}

static int vb235v_suspend(struct cpufreq_policy *policy)
{
	/* Voltage retention across system suspend has not been established. */
	mutex_lock(&vb235v_cpu_lock);
	vb235v_cpu_state.faulted = 1;
	mutex_unlock(&vb235v_cpu_lock);
	pr_warn("suspend invalidates boot-voltage admission; reboot required for transitions\n");
	return 0;
}

static struct cpufreq_driver vb235v_driver = {
	.name = "vb235v-smc",
	.flags = CPUFREQ_CONST_LOOPS | CPUFREQ_NO_AUTO_DYNAMIC_SWITCHING,
	.init = vb235v_policy_init,
	.verify = cpufreq_generic_frequency_table_verify,
	.target_index = vb235v_target,
	.get = vb235v_get,
	.suspend = vb235v_suspend,
};

static int __init vb235v_cpufreq_init(void)
{
	struct device_node *root;
	unsigned long mhz;
	bool opted_in;
	int ret;

	if (!of_machine_is_compatible("tplink,vb235v") ||
	    !of_machine_is_compatible("airoha,an7583") ||
	    num_possible_cpus() != 2)
		return -ENODEV;
	root = of_find_node_by_path("/");
	opted_in = of_property_read_bool(root, "tplink,m78-boot-voltage-cpufreq");
	of_node_put(root);
	if (!opted_in)
		return -ENODEV;
	mhz = vb235v_get_mhz(NULL); /* Sole admission query; no SET or AVS. */
	boot_frequency_mhz = mhz;
	ret = vb235v_cpu_admit(&vb235v_cpu_state, mhz);
	if (ret) {
		pr_err("boot SMC returned 0x%lx; require actual 1200 MHz, refusing frequency control\n", mhz);
		return ret;
	}
	pr_info("SMC reports boot %lu MHz; checking read-only CPU mux/divider\n", mhz);
	cpu_mux_div = ioremap(0x1efbe7c0, sizeof(u32));
	if (!cpu_mux_div)
		return -ENOMEM;
	if (!vb235v_clock_ok(NULL)) {
		pr_err("CPU mux/divider is not ARMPLL 1:1; refusing frequency control\n");
		ret = -ENODEV;
		goto unmap;
	}
	pr_info("SMC boot frequency %lu MHz; boot voltage held; transitions %s; AVS/thermal unimplemented\n",
		mhz, allow_transitions ? "enabled" : "disabled (read-only)");
	ret = cpufreq_register_driver(&vb235v_driver);
	if (!ret)
		return 0;
unmap:
	iounmap(cpu_mux_div);
	return ret;
}
module_init(vb235v_cpufreq_init);

static void __exit vb235v_cpufreq_exit(void)
{
	cpufreq_unregister_driver(&vb235v_driver);
	iounmap(cpu_mux_div);
}
module_exit(vb235v_cpufreq_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("VB235v boot-voltage-preserving SMC cpufreq development driver");
