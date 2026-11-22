// SPDX-License-Identifier: GPL-2.0-only
/* One-shot M81 observation on the existing M75 kernel. No cpufreq registration,
 * SET SMC, MMIO write, DT mutation, voltage operation, or MTD access exists.
 */
#define pr_fmt(fmt) KBUILD_MODNAME ": " fmt
#include <linux/arm-smccc.h>
#include <linux/cpu.h>
#include <linux/errno.h>
#include <linux/io.h>
#include <linux/module.h>
#include <linux/of.h>

static unsigned long smc_mhz;
static unsigned int mux_div_raw;
static unsigned int possible_cpus;
static unsigned int online_cpus;
static bool armpll_div1;
module_param(smc_mhz, ulong, 0400);
module_param(mux_div_raw, uint, 0400);
module_param(possible_cpus, uint, 0400);
module_param(online_cpus, uint, 0400);
module_param(armpll_div1, bool, 0400);

static int __init vb235v_cpu_query_init(void)
{
	struct arm_smccc_res result;
	void __iomem *mux;

	if (!of_machine_is_compatible("tplink,vb235v") ||
	    !of_machine_is_compatible("airoha,an7583"))
		return -ENODEV;
	possible_cpus = num_possible_cpus();
	online_cpus = num_online_cpus();
	if (possible_cpus != 2 || online_cpus != 2)
		return -ENODEV;
	arm_smccc_smc(0x82000301U, 0xddddddd2U, 0, 0, 0, 0, 0, 0,
		     &result);
	smc_mhz = result.a0;
	pr_info("READ ONLY: possible=%u online=%u SMC GET raw=0x%lx MHz=%lu; no SET issued\n",
		possible_cpus, online_cpus, smc_mhz, smc_mhz);
	if (smc_mhz != 500 && smc_mhz != 1200)
		return -EIO; /* Unknown GET must not lead to further probing. */
	mux = ioremap(0x1efbe7c0, sizeof(u32));
	if (!mux)
		return -ENOMEM;
	mux_div_raw = readl(mux);
	iounmap(mux);
	armpll_div1 = ((mux_div_raw >> 9) & 3) == 1 &&
		      ((mux_div_raw >> 17) & 0x1f) == 0;
	pr_info("READ ONLY: MCUCFG[0x1efbe7c0]=0x%08x source=%u divider_code=%u ARMPLL_1to1=%u; no MMIO writes\n",
		mux_div_raw, (mux_div_raw >> 9) & 3,
		(mux_div_raw >> 17) & 0x1f, armpll_div1);
	return 0; /* A mux mismatch is evidence, never permission to correct it. */
}
module_init(vb235v_cpu_query_init);

static void __exit vb235v_cpu_query_exit(void)
{
	pr_info("one-shot read-only observation removed; no hardware state changed\n");
}
module_exit(vb235v_cpu_query_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("VB235v one-shot SMC GET and CPU mux read-only observation");
