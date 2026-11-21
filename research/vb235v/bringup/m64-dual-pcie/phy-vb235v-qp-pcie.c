// SPDX-License-Identifier: GPL-2.0-only
/* VB235v port-1 PCIe QPHY RAM-development adapter.
 * Register initialization is selected from Airoha's AN7583 GPL source.
 */
#include <linux/bitfield.h>
#include <linux/delay.h>
#include <linux/io.h>
#include <linux/mfd/syscon.h>
#include <linux/module.h>
#include <linux/nvmem-consumer.h>
#include <linux/of.h>
#include <linux/phy/phy.h>
#include <linux/platform_device.h>
#include <linux/regmap.h>

#include "qphy-fields.h"

struct vb235v_qphy {
	struct device *dev;
	void __iomem *ana, *dig, *pma;
	struct regmap *scu;
	u32 efuse_valid, tx_term, rx_imp;
};

static void __iomem *vb235v_qphy_reg(struct vb235v_qphy *priv,
				   u32 base, u32 offset, u32 address)
{
	void __iomem *map;

	switch (base) {
	case QP_ANA_BASE: map = priv->ana; break;
	case QP_DIG_BASE: map = priv->dig; break;
	case QP_PMA_BASE: map = priv->pma; break;
	default: return NULL;
	}
	if (WARN_ON(address < offset || address - offset > 0xffc || address & 3))
		return NULL;
	return map + address - offset;
}

static u32 vb235v_qphy_read(struct vb235v_qphy *priv, u32 base, u32 offset, u32 address)
{
	void __iomem *reg = vb235v_qphy_reg(priv, base, offset, address);
	return reg ? readl(reg) : 0;
}

static void vb235v_qphy_write(struct vb235v_qphy *priv, u32 base, u32 offset, u32 address, u32 value)
{
	void __iomem *reg = vb235v_qphy_reg(priv, base, offset, address);
	if (reg)
		writel(value, reg);
}

static u32 vb235v_qphy_efuse(struct vb235v_qphy *priv, u32 bit, u32 width)
{
	if (bit == 32 && width == 1)
		return priv->efuse_valid;
	if (bit == 67 && width == 2)
		return priv->tx_term;
	if (bit == 69 && width == 5)
		return priv->rx_imp;
	WARN_ON_ONCE(1);
	return 0;
}

#define Reg_R(base, offset, address) vb235v_qphy_read(priv, base, offset, address)
#define Reg_W(base, offset, address, value) vb235v_qphy_write(priv, base, offset, address, value)
#define get_phy_efuse(bit, width) vb235v_qphy_efuse(priv, bit, width)
#include "qphy-sequence.inc"

static int vb235v_qphy_init(struct phy *phy)
{
	struct vb235v_qphy *priv = phy_get_drvdata(phy);
	int err;

	/* Port 0 is initialized separately. Never pulse its reset or PCIe HB here. */
	err = regmap_set_bits(priv->scu, 0x834, BIT(27));
	if (err)
		return err;
	msleep(100);
	err = regmap_clear_bits(priv->scu, 0x88, BIT(26));
	if (err)
		return err;
	usleep_range(1000, 2000);
	PCIe_QPhy_Load_Efuse(priv);
	err = pcie_QPhy_init(priv);
	if (err)
		return dev_err_probe(priv->dev, err, "QPHY calibration did not lock\n");
	msleep(30);
	err = regmap_clear_bits(priv->scu, 0x834, BIT(27));
	if (err)
		return err;
	err = regmap_set_bits(priv->scu, 0x88, BIT(26));
	if (err)
		return err;
	msleep(400);
	dev_info(priv->dev, "VB235v port-1 QPHY development initialization completed\n");
	return 0;
}

static int vb235v_qphy_exit(struct phy *phy)
{
	struct vb235v_qphy *priv = phy_get_drvdata(phy);
	int err;

	err = regmap_clear_bits(priv->scu, 0x88, BIT(26));
	if (err)
		return err;
	tx_pll_disable(priv);
	return regmap_set_bits(priv->scu, 0x834, BIT(27));
}

static const struct phy_ops vb235v_qphy_ops = {
	.init = vb235v_qphy_init,
	.exit = vb235v_qphy_exit,
	.owner = THIS_MODULE,
};

static int vb235v_qphy_probe(struct platform_device *pdev)
{
	struct device *dev = &pdev->dev;
	struct phy_provider *provider;
	struct vb235v_qphy *priv;
	struct phy *phy;
	int err;

	if (!of_machine_is_compatible("tplink,vb235v-ram-dual-pcie-development"))
		return -ENODEV;
	priv = devm_kzalloc(dev, sizeof(*priv), GFP_KERNEL);
	if (!priv)
		return -ENOMEM;
	priv->dev = dev;
	priv->ana = devm_platform_ioremap_resource_byname(pdev, "ana");
	if (IS_ERR(priv->ana))
		return PTR_ERR(priv->ana);
	priv->dig = devm_platform_ioremap_resource_byname(pdev, "dig");
	if (IS_ERR(priv->dig))
		return PTR_ERR(priv->dig);
	priv->pma = devm_platform_ioremap_resource_byname(pdev, "pma");
	if (IS_ERR(priv->pma))
		return PTR_ERR(priv->pma);
	priv->scu = syscon_regmap_lookup_by_phandle(dev->of_node, "airoha,scu");
	if (IS_ERR(priv->scu))
		return PTR_ERR(priv->scu);
	priv->scu = syscon_regmap_lookup_by_phandle(dev->of_node, "airoha,scu");
	if (IS_ERR(priv->scu))
		return PTR_ERR(priv->scu);
	err = nvmem_cell_read_variable_le_u32(dev, "pcie-valid", &priv->efuse_valid);
	if (err)
		return dev_err_probe(dev, err, "QPHY valid eFuse unavailable\n");
	err = nvmem_cell_read_variable_le_u32(dev, "tx-term", &priv->tx_term);
	if (err)
		return dev_err_probe(dev, err, "QPHY TX termination eFuse unavailable\n");
	err = nvmem_cell_read_variable_le_u32(dev, "rx-impedance", &priv->rx_imp);
	if (err)
		return dev_err_probe(dev, err, "QPHY RX impedance eFuse unavailable\n");
	if (priv->efuse_valid > 1 || priv->tx_term > 3 || priv->rx_imp > 31)
		return -EINVAL;
	phy = devm_phy_create(dev, dev->of_node, &vb235v_qphy_ops);
	if (IS_ERR(phy))
		return PTR_ERR(phy);
	phy_set_drvdata(phy, priv);
	provider = devm_of_phy_provider_register(dev, of_phy_simple_xlate);
	return PTR_ERR_OR_ZERO(provider);
}

static const struct of_device_id vb235v_qphy_match[] = {
	{ .compatible = "tplink,vb235v-qp-pcie-development" },
	{ }
};
MODULE_DEVICE_TABLE(of, vb235v_qphy_match);
static struct platform_driver vb235v_qphy_driver = {
	.probe = vb235v_qphy_probe,
	.driver = { .name = "vb235v-qp-pcie-development", .of_match_table = vb235v_qphy_match },
};
module_platform_driver(vb235v_qphy_driver);
MODULE_LICENSE("GPL");
