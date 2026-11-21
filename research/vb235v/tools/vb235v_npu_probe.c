// SPDX-License-Identifier: GPL-2.0-only
/* Development-only bounded NPU status reads and one existing GET_INFO request. */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>
#include <linux/regmap.h>
#include <linux/soc/airoha/airoha_offload.h>
static int __init vb235v_npu_probe_init(void)
{
	struct device_node *np;
	struct platform_device *eth;
	struct airoha_npu *npu;
	u32 boot=0,heap=0,sram=0,ctrl=0,info=0;
	int ret;
	if(!of_machine_is_compatible("tplink,vb235v-ram-npu-development")) return -ENODEV;
	np=of_find_compatible_node(NULL,NULL,"airoha,an7583-eth");
	if(!np) return -ENODEV;
	eth=of_find_device_by_node(np);of_node_put(np);
	if(!eth) return -ENODEV;
	npu=airoha_npu_get(&eth->dev);
	if(IS_ERR(npu)) {put_device(&eth->dev);return PTR_ERR(npu);}
	regmap_read(npu->regmap,0x306004,&boot);
	regmap_read(npu->regmap,0x30c168,&heap);
	regmap_read(npu->regmap,0x30c16c,&sram);
	regmap_read(npu->regmap,0x30c03c,&ctrl);
	pr_info("M68_NPU_STATUS boot=%08x heap=%08x sram=%08x prior_mbox=%08x\n",boot,heap,sram,ctrl);
	for(unsigned int core=0;core<6;core++) {
		u32 pc=0;
		regmap_read(npu->regmap,0x305000+core*0x100,&pc);
		pr_info("M68_NPU_CORE core=%u pc=%08x\n",core,pc);
	}
	ret=npu->ops.wlan_get_msg(npu,0,WLAN_FUNC_GET_WAIT_NPU_INFO,&info,sizeof(info),GFP_KERNEL);
	regmap_read(npu->regmap,0x30c03c,&ctrl);
	pr_info("M68_NPU_GET_INFO ret=%d info=%08x mbox=%08x\n",ret,info,ctrl);
	airoha_npu_put(npu);put_device(&eth->dev);
	return 0;
}
static void __exit vb235v_npu_probe_exit(void) {}
module_init(vb235v_npu_probe_init);
module_exit(vb235v_npu_probe_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("VB235v RAM-only bounded NPU diagnostic");
