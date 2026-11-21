/* SPDX-License-Identifier: GPL-2.0-only
 * Copyright (c) 2024 AIROHA Inc
 * Selected AN7583 QPHY initialization; development adaptations documented.
 */
static void PCIe_QPhy_Load_Efuse(struct vb235v_qphy *priv)
{
	rg_type_t(qp_pma_top_REG_INTF_CTRL_8) fw_INTF_CTRL_8;
	rg_type_t(qp_pma_top_REG_INTF_CTRL_9) fw_INTF_CTRL_9;

	int tx_term_sel_force, rx_imp_sel_force;
//*******  Load Efuse

	tx_term_sel_force = (get_phy_efuse(SerDes_QP_PCIe_efuse_valid_LSB, 1) == 1) ? get_phy_efuse(RG_QP_PCIE_TX_TERM_SEL_LSB, 2) : 0x1;
	rx_imp_sel_force = (get_phy_efuse(SerDes_QP_PCIe_efuse_valid_LSB, 1) == 1) ? get_phy_efuse(RG_QP_PCIE_RX_IMP_SEL_LSB, 5) : 0x1;

	fw_INTF_CTRL_8.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_INTF_CTRL_8);
	fw_INTF_CTRL_8.hal.rg_da_qp_tx_term_sel_force = (tx_term_sel_force == -1) ? 0x1 : tx_term_sel_force;
	fw_INTF_CTRL_8.hal.rg_da_qp_tx_term_sel_sel = 0x1;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_INTF_CTRL_8, fw_INTF_CTRL_8.dat.value); //write addr: 0x1FA5E320 = 0xA0

	fw_INTF_CTRL_9.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_INTF_CTRL_9);
	fw_INTF_CTRL_9.hal.rg_da_qp_rx_imp_sel_force = (rx_imp_sel_force == -1) ? 0x10 : rx_imp_sel_force;
	fw_INTF_CTRL_9.hal.rg_da_qp_rx_imp_sel_sel = 0x1;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_INTF_CTRL_9, fw_INTF_CTRL_9.dat.value); //write addr: 0x1FA5E324 = 0xC0E00000

}

static void pcie_QPhy_init_original(struct vb235v_qphy *priv)
{
	u32 tmp;
	rg_type_t(qp_pma_top_REG_RX_CTRL_36) fw_RX_CTRL_36;
	rg_type_t(REG_RG_QP_BGR_EN) fw_RG_QP_BGR_EN;
	rg_type_t(REG_RG_QP_PLL_IPLL_DIG_PWR_SEL) fw_RG_QP_PLL_IPLL_DIG_PWR_SEL;
	rg_type_t(qp_pma_top_REG_PLL_CTRL_4) fw_PLL_CTRL_4;
	rg_type_t(qp_dig_csr_REG_QP_CK_RST_CTRL_7) fw_QP_CK_RST_CTRL_7;
	rg_type_t(qp_pma_top_REG_PLL_CTRL_2) fw_PLL_CTRL_2;
	rg_type_t(qp_pma_top_REG_PLL_CTRL_3) fw_PLL_CTRL_3;
	rg_type_t(qp_pma_top_REG_PLL_CTRL_1) fw_PLL_CTRL_1;
	rg_type_t(qp_pma_top_REG_SS_LCPLL_TDC_PCW_1) fw_SS_LCPLL_TDC_PCW_1;
	rg_type_t(qp_pma_top_REG_SS_LCPLL_PWCTL_SETTING_2) fw_SS_LCPLL_PWCTL_SETTING_2;
	rg_type_t(qp_pma_top_REG_SS_LCPLL_TDC_FLT_2) fw_SS_LCPLL_TDC_FLT_2;
	rg_type_t(REG_RG_QP_CDR_LPF_MJV_LIM) fw_RG_QP_CDR_LPF_MJV_LIM;
	rg_type_t(REG_RG_QP_RXAFE_RESERVE) fw_RG_QP_RXAFE_RESERVE;
	rg_type_t(REG_RG_QP_CDR_PR_CKREF_DIV1) fw_RG_QP_CDR_PR_CKREF_DIV1;
	rg_type_t(REG_RG_QP_CDR_FORCE_IBANDLPF_R_OFF) fw_RG_QP_CDR_FORCE_IBANDLPF_R_OFF;
	rg_type_t(REG_RG_QP_CDR_PR_KBAND_DIV_PCIE) fw_RG_QP_CDR_PR_KBAND_DIV_PCIE;
	rg_type_t(qp_pma_top_REG_RX_CTRL_46) fw_RX_CTRL_46;
	rg_type_t(qp_pma_top_REG_RX_CTRL_11) fw_RX_CTRL_11;
	rg_type_t(qp_pma_top_REG_RX_DLY_0) fw_RX_DLY_0;
	rg_type_t(qp_pma_top_REG_RX_CTRL_10) fw_RX_CTRL_10;
	rg_type_t(REG_RG_QP_PLL_SDM_ORD) fw_RG_QP_PLL_SDM_ORD;
	rg_type_t(qp_pma_top_REG_PLL_CK_CTRL_0) fw_PLL_CK_CTRL_0;
	rg_type_t(REG_RG_PCIE_CLKDRV_IMPSEL) fw_RG_PCIE_CLKDRV_IMPSEL;
	rg_type_t(qp_pma_top_REG_QP_TX_DA_CTRL_3) fw_QP_TX_DA_CTRL_3;
	rg_type_t(qp_dig_csr_REG_QP_CK_RST_CTRL_3) fw_QP_CK_RST_CTRL_3;
	rg_type_t(qp_pma_top_REG_QP_TX_DA_CTRL_0) fw_QP_TX_DA_CTRL_0;
	rg_type_t(REG_RG_QP_RXLBTX_EN) fw_RG_QP_RXLBTX_EN;
	rg_type_t(qp_pma_top_REG_PLL_CK_CTRL_2) fw_PLL_CK_CTRL_2;
	rg_type_t(qp_pma_top_REG_RX_CTRL_5) fw_RX_CTRL_5;
	rg_type_t(qp_pma_top_REG_RX_CTRL_6) fw_RX_CTRL_6;
	rg_type_t(qp_pma_top_REG_RX_CTRL_7) fw_RX_CTRL_7;
	rg_type_t(qp_pma_top_REG_RX_CTRL_2) fw_RX_CTRL_2;
	rg_type_t(qp_pma_top_REG_RX_CTRL_45) fw_RX_CTRL_45;
	rg_type_t(qp_pma_top_REG_RX_CTRL_50) fw_RX_CTRL_50;
	rg_type_t(REG_RG_QP_TX_MODE_16B_EN) fw_RG_QP_TX_MODE_16B_EN;
	rg_type_t(qp_pma_top_REG_PON_RXFEDIG_CTRL_0) fw_PON_RXFEDIG_CTRL_0;
	rg_type_t(qp_pma_top_REG_PLL_CTRL_0) fw_PLL_CTRL_0;


	udelay(1);
	fw_RX_CTRL_36.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_RX_CTRL_36);
	fw_RX_CTRL_36.hal.rg_qp_pcie_usb_system = 0x1;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_RX_CTRL_36, fw_RX_CTRL_36.dat.value); //write addr: 0x1FA5E6B8 = 0x41E1100

	fw_RG_QP_BGR_EN.dat.value = Reg_R(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_BGR_EN);
	fw_RG_QP_BGR_EN.hal.RG_QP_BG_DIV = 0x1;
	Reg_W(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_BGR_EN, fw_RG_QP_BGR_EN.dat.value); //write addr: 0x1FA5F030 = 0x2AA0004

	fw_RG_QP_PLL_IPLL_DIG_PWR_SEL.dat.value = Reg_R(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_PLL_IPLL_DIG_PWR_SEL);
	fw_RG_QP_PLL_IPLL_DIG_PWR_SEL.hal.RG_QP_PLL_PREDIV = 0x1;
	Reg_W(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_PLL_IPLL_DIG_PWR_SEL, fw_RG_QP_PLL_IPLL_DIG_PWR_SEL.dat.value); //write addr: 0x1FA5F03C = 0x122802A2

	fw_PLL_CTRL_4.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_4);
	fw_PLL_CTRL_4.hal.rg_da_qp_pll_icolp_en_intf = 0x0;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_4, fw_PLL_CTRL_4.dat.value); //write addr: 0x1FA5E410 = 0x0

	fw_QP_CK_RST_CTRL_7.dat.value = Reg_R(QP_DIG_BASE, QP_DIG_OFFSET, _qp_dig_csr_QP_CK_RST_CTRL_7);
	fw_QP_CK_RST_CTRL_7.hal.rg_multi_phy_usb5_en = 0x0;
	fw_QP_CK_RST_CTRL_7.hal.rg_multi_phy_usb2p5_en = 0x0;
	fw_QP_CK_RST_CTRL_7.hal.rg_multi_phy_usb_mode_en = 0x1;
	Reg_W(QP_DIG_BASE, QP_DIG_OFFSET, _qp_dig_csr_QP_CK_RST_CTRL_7, fw_QP_CK_RST_CTRL_7.dat.value); //write addr: 0x1FA5A340 = 0x1000000

	fw_QP_CK_RST_CTRL_7.hal.rg_multi_phy_usb5_en = 0x1;
	fw_QP_CK_RST_CTRL_7.hal.rg_multi_phy_usb2p5_en = 0x1;
	Reg_W(QP_DIG_BASE, QP_DIG_OFFSET, _qp_dig_csr_QP_CK_RST_CTRL_7, fw_QP_CK_RST_CTRL_7.dat.value); //write addr: 0x1FA5A340 = 0x7000000

	fw_PLL_CTRL_2.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_2);
	fw_PLL_CTRL_2.hal.rg_da_qp_pll_pck_sel_intf = 0x1;
	fw_PLL_CTRL_2.hal.rg_da_qp_pll_ir_intf = 0x4;
	fw_PLL_CTRL_2.hal.rg_da_qp_pll_fbksel_intf = 0x0;
	fw_PLL_CTRL_2.hal.rg_da_qp_pll_kband_prediv_intf = 0x0;
	fw_PLL_CTRL_2.hal.rg_da_qp_pll_bc_intf = 0x3;
	fw_PLL_CTRL_2.hal.rg_da_qp_pll_bpa_intf = 0x5;
	fw_PLL_CTRL_2.hal.rg_da_qp_pll_bpb_intf = 0x1;
	fw_PLL_CTRL_2.hal.rg_da_qp_pll_icoiq_en_intf = 0x1;
	fw_PLL_CTRL_2.hal.rg_da_qp_pll_phy_ck_en_intf = 0x0;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_2, fw_PLL_CTRL_2.dat.value); //write addr: 0x1FA5E408 = 0x21444357

	fw_PLL_CTRL_4.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_4);
	fw_PLL_CTRL_4.hal.rg_da_qp_pll_sdm_hren_intf = 0x1;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_4, fw_PLL_CTRL_4.dat.value); //write addr: 0x1FA5E410 = 0x8

	fw_PLL_CTRL_2.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_2);
	fw_PLL_CTRL_2.hal.rg_da_qp_pll_sdm_ifm_intf = 0x1;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_2, fw_PLL_CTRL_2.dat.value); //write addr: 0x1FA5E408 = 0x61444357

	fw_PLL_CTRL_3.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_3);
	fw_PLL_CTRL_3.hal.rg_da_qp_pll_ssc_delta_intf = 0x1FD;
	fw_PLL_CTRL_3.hal.rg_da_qp_pll_ssc_period_intf = 0x19C;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_3, fw_PLL_CTRL_3.dat.value); //write addr: 0x1FA5E40C = 0x19C01FD

	fw_PLL_CTRL_1.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_1);
	fw_PLL_CTRL_1.hal.rg_qp_pll_ssc_en = 0x1;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_1, fw_PLL_CTRL_1.dat.value); //write addr: 0x1FA5E404 = 0x5F0109C4

	fw_SS_LCPLL_TDC_PCW_1.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_SS_LCPLL_TDC_PCW_1);
	fw_SS_LCPLL_TDC_PCW_1.hal.rg_lcpll_pon_hrdds_pcw_ncpo_gpon = 0x48000000;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_SS_LCPLL_TDC_PCW_1, fw_SS_LCPLL_TDC_PCW_1.dat.value); //write addr: 0x1FA5E248 = 0x48000000

	fw_SS_LCPLL_PWCTL_SETTING_2.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_SS_LCPLL_PWCTL_SETTING_2);
	fw_SS_LCPLL_PWCTL_SETTING_2.hal.rg_ncpo_ana_msb = 0x1;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_SS_LCPLL_PWCTL_SETTING_2, fw_SS_LCPLL_PWCTL_SETTING_2.dat.value); //write addr: 0x1FA5E208 = 0x1000A

	fw_SS_LCPLL_TDC_FLT_2.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_SS_LCPLL_TDC_FLT_2);
	fw_SS_LCPLL_TDC_FLT_2.hal.rg_lcpll_ncpo_value = 0x48000000;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_SS_LCPLL_TDC_FLT_2, fw_SS_LCPLL_TDC_FLT_2.dat.value); //write addr: 0x1FA5E230 = 0x48000000

	fw_RG_QP_CDR_LPF_MJV_LIM.dat.value = Reg_R(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_CDR_LPF_MJV_LIM);
	fw_RG_QP_CDR_LPF_MJV_LIM.hal.RG_QP_CDR_LPF_RATIO = 0x1;
	Reg_W(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_CDR_LPF_MJV_LIM, fw_RG_QP_CDR_LPF_MJV_LIM.dat.value); //write addr: 0x1FA5F00C = 0x14

	fw_RG_QP_RXAFE_RESERVE.dat.value = Reg_R(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_RXAFE_RESERVE);
	fw_RG_QP_RXAFE_RESERVE.hal.RG_QP_CDR_PD_10B_EN = 0x1;
	Reg_W(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_RXAFE_RESERVE, fw_RG_QP_RXAFE_RESERVE.dat.value); //write addr: 0x1FA5F004 = 0xE00

	fw_RG_QP_CDR_PR_CKREF_DIV1.dat.value = Reg_R(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_CDR_PR_CKREF_DIV1);
	fw_RG_QP_CDR_PR_CKREF_DIV1.hal.RG_QP_CDR_PR_DAC_BAND = 0xC;
	Reg_W(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_CDR_PR_CKREF_DIV1, fw_RG_QP_CDR_PR_CKREF_DIV1.dat.value); //write addr: 0x1FA5F018 = 0x4000C00

	fw_RG_QP_CDR_FORCE_IBANDLPF_R_OFF.dat.value = Reg_R(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_CDR_FORCE_IBANDLPF_R_OFF);
	fw_RG_QP_CDR_FORCE_IBANDLPF_R_OFF.hal.RG_QP_CDR_PHYCK_RSTB = 0x0;
	Reg_W(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_CDR_FORCE_IBANDLPF_R_OFF, fw_RG_QP_CDR_FORCE_IBANDLPF_R_OFF.dat.value); //write addr: 0x1FA5F020 = 0x1020840

	fw_RG_QP_CDR_PR_KBAND_DIV_PCIE.dat.value = Reg_R(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_CDR_PR_KBAND_DIV_PCIE);
	fw_RG_QP_CDR_PR_KBAND_DIV_PCIE.hal.RG_QP_CDR_PR_XFICK_EN = 0x0;
	fw_RG_QP_CDR_PR_KBAND_DIV_PCIE.hal.RG_QP_CDR_PR_KBAND_PCIE_MODE = 0x1;
	Reg_W(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_CDR_PR_KBAND_DIV_PCIE, fw_RG_QP_CDR_PR_KBAND_DIV_PCIE.dat.value); //write addr: 0x1FA5F01C = 0x18000059

	fw_RG_QP_CDR_PR_CKREF_DIV1.dat.value = Reg_R(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_CDR_PR_CKREF_DIV1);
	fw_RG_QP_CDR_PR_CKREF_DIV1.hal.RG_QP_CDR_PR_KBAND_DIV = 0x3;
	Reg_W(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_CDR_PR_CKREF_DIV1, fw_RG_QP_CDR_PR_CKREF_DIV1.dat.value); //write addr: 0x1FA5F018 = 0x3000C00

	fw_RG_QP_CDR_PR_KBAND_DIV_PCIE.dat.value = Reg_R(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_CDR_PR_KBAND_DIV_PCIE);
	fw_RG_QP_CDR_PR_KBAND_DIV_PCIE.hal.RG_QP_CDR_PR_KBAND_DIV_PCIE = 0x19;
	Reg_W(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_CDR_PR_KBAND_DIV_PCIE, fw_RG_QP_CDR_PR_KBAND_DIV_PCIE.dat.value); //write addr: 0x1FA5F01C = 0x18000059

	fw_RX_CTRL_46.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_RX_CTRL_46);
	fw_RX_CTRL_46.hal.rg_qp_pcie_usb_bypass_eq_p1_to_p0_en = 0x1;
	fw_RX_CTRL_46.hal.rg_reback_p0_lck2ref_en = 0x1;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_RX_CTRL_46, fw_RX_CTRL_46.dat.value); //write addr: 0x1FA5E6E0 = 0xC360000

	fw_RX_CTRL_11.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_RX_CTRL_11);
	fw_RX_CTRL_11.hal.rg_qp_force_sigdet_5g = 0x1;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_RX_CTRL_11, fw_RX_CTRL_11.dat.value); //write addr: 0x1FA5E654 = 0x2680050

	fw_RX_CTRL_36.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_RX_CTRL_36);
	fw_RX_CTRL_36.hal.rg_qp_lck2data_dly_time = 0x2;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_RX_CTRL_36, fw_RX_CTRL_36.dat.value); //write addr: 0x1FA5E6B8 = 0x4021100

	fw_RG_QP_RXAFE_RESERVE.dat.value = Reg_R(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_RXAFE_RESERVE);
	fw_RG_QP_RXAFE_RESERVE.hal.RG_QP_CDR_PD_EDGE_DIS = 0x0;
	Reg_W(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_RXAFE_RESERVE, fw_RG_QP_RXAFE_RESERVE.dat.value); //write addr: 0x1FA5F004 = 0xA00

	fw_RX_DLY_0.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_RX_DLY_0);
	fw_RX_DLY_0.hal.rg_qp_rx_pi_cal_en_h_dly = 0x10;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_RX_DLY_0, fw_RX_DLY_0.dat.value); //write addr: 0x1FA5E614 = 0xF10

	fw_RX_CTRL_10.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_RX_CTRL_10);
	fw_RX_CTRL_10.hal.rg_qp_crsdet_rstb = 0x1;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_RX_CTRL_10, fw_RX_CTRL_10.dat.value); //write addr: 0x1FA5E650 = 0x534A602

	fw_RG_QP_PLL_SDM_ORD.dat.value = Reg_R(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_PLL_SDM_ORD);
	fw_RG_QP_PLL_SDM_ORD.hal.RG_QP_PLL_SSC_PHASE_INI = 0x1;
	fw_RG_QP_PLL_SDM_ORD.hal.RG_QP_PLL_SSC_TRI_EN = 0x1;
	Reg_W(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_PLL_SDM_ORD, fw_RG_QP_PLL_SDM_ORD.dat.value); //write addr: 0x1FA5F040 = 0x1B

	fw_PLL_CK_CTRL_0.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CK_CTRL_0);
	fw_PLL_CK_CTRL_0.hal.rg_da_pcie_clkrx_en_intf = 0x0;
	fw_PLL_CK_CTRL_0.hal.rg_da_pcie_clktx_en_intf = 0x1;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CK_CTRL_0, fw_PLL_CK_CTRL_0.dat.value); //write addr: 0x1FA5E414 = 0x61

	fw_RG_PCIE_CLKDRV_IMPSEL.dat.value = Reg_R(QP_ANA_BASE, QP_ANA_OFFSET, _RG_PCIE_CLKDRV_IMPSEL);
	fw_RG_PCIE_CLKDRV_IMPSEL.hal.RG_PCIE_CLKDRV_HZ = 0x0;
	fw_RG_PCIE_CLKDRV_IMPSEL.hal.RG_PCIE_CLKDRV_AMP = 0x4;
	fw_RG_PCIE_CLKDRV_IMPSEL.hal.RG_PCIE_CLKDRV_FORCEIN = 0x1;
	fw_RG_PCIE_CLKDRV_IMPSEL.hal.RG_PCIE_CLKDRV_IMPSEL = 0x12;
	fw_RG_PCIE_CLKDRV_IMPSEL.hal.RG_PCIE_CLKDRV_RP = 0xC;
	Reg_W(QP_ANA_BASE, QP_ANA_OFFSET, _RG_PCIE_CLKDRV_IMPSEL, fw_RG_PCIE_CLKDRV_IMPSEL.dat.value); //write addr: 0x1FA5F034 = 0xA8801812

	fw_QP_TX_DA_CTRL_3.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_QP_TX_DA_CTRL_3);
	fw_QP_TX_DA_CTRL_3.hal.rg_tx_data_rate_sel = 0x1;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_QP_TX_DA_CTRL_3, fw_QP_TX_DA_CTRL_3.dat.value); //write addr: 0x1FA5E00C = 0x90000100

	fw_QP_CK_RST_CTRL_3.dat.value = Reg_R(QP_DIG_BASE, QP_DIG_OFFSET, _qp_dig_csr_QP_CK_RST_CTRL_3);
	fw_QP_CK_RST_CTRL_3.hal.rg_us_ck_div_sel = 0x1;
	fw_QP_CK_RST_CTRL_3.hal.rg_ns_ck_div_sel = 0x1;
	Reg_W(QP_DIG_BASE, QP_DIG_OFFSET, _qp_dig_csr_QP_CK_RST_CTRL_3, fw_QP_CK_RST_CTRL_3.dat.value); //write addr: 0x1FA5A30C = 0x3400000

	fw_QP_TX_DA_CTRL_0.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_QP_TX_DA_CTRL_0);
	fw_QP_TX_DA_CTRL_0.hal.rg_rxdet_en_window = 0xA;
	fw_QP_TX_DA_CTRL_0.hal.rg_rxdet_rd_wait_timer = 0x4;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_QP_TX_DA_CTRL_0, fw_QP_TX_DA_CTRL_0.dat.value); //write addr: 0x1FA5E000 = 0x873C40A0

	fw_RG_QP_RXLBTX_EN.dat.value = Reg_R(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_RXLBTX_EN);
	fw_RG_QP_RXLBTX_EN.hal.RG_QP_TX_RXDET_METHOD = 0x0;
	fw_RG_QP_RXLBTX_EN.hal.RG_QP_TX_DMEDGEGEN_EN = 0x1;
	Reg_W(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_RXLBTX_EN, fw_RG_QP_RXLBTX_EN.dat.value); //write addr: 0x1FA5F02C = 0x8840010

	fw_PLL_CK_CTRL_2.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CK_CTRL_2);
	fw_PLL_CK_CTRL_2.hal.rg_pcie_mode_pll_auto_en = 0x1;
	fw_PLL_CK_CTRL_2.hal.rg_pcie_mode_pll_auto_on_en = 0x1;
	fw_PLL_CK_CTRL_2.hal.rg_pcie_mode_pll_auto_off_en = 0x1;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CK_CTRL_2, fw_PLL_CK_CTRL_2.dat.value); //write addr: 0x1FA5E41C = 0x7

	fw_RX_CTRL_5.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_RX_CTRL_5);
	fw_RX_CTRL_5.hal.rg_fredet_chk_cycle = 0x28;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_RX_CTRL_5, fw_RX_CTRL_5.dat.value); //write addr: 0x1FA5E63C = 0xA010

	fw_RX_CTRL_6.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_RX_CTRL_6);
	fw_RX_CTRL_6.hal.rg_fredet_golden_cycle = 0x64;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_RX_CTRL_6, fw_RX_CTRL_6.dat.value); //write addr: 0x1FA5E640 = 0x64

	fw_RX_CTRL_7.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_RX_CTRL_7);
	fw_RX_CTRL_7.hal.rg_fredet_tolerate_cycle = 0x2710;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_RX_CTRL_7, fw_RX_CTRL_7.dat.value); //write addr: 0x1FA5E644 = 0x2710

	fw_RX_CTRL_2.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_RX_CTRL_2);
	fw_RX_CTRL_2.hal.rg_qp_rx_eq_en_h_dly = 0x9C4;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_RX_CTRL_2, fw_RX_CTRL_2.dat.value); //write addr: 0x1FA5E630 = 0x9C40000

	fw_RX_CTRL_45.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_RX_CTRL_45);
	fw_RX_CTRL_45.hal.rg_qp_eq_en_dly = 0x9C4;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_RX_CTRL_45, fw_RX_CTRL_45.dat.value); //write addr: 0x1FA5E6DC = 0x254A09C4

	fw_RX_CTRL_50.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_RX_CTRL_50);
	fw_RX_CTRL_50.hal.rg_qp_rx_eq_en_h_dly_short = 0x9C4;
	fw_RX_CTRL_50.hal.rg_qp_eq_en_dly_short = 0x9C4;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_RX_CTRL_50, fw_RX_CTRL_50.dat.value); //write addr: 0x1FA5E6F0 = 0x13889C4

	fw_RG_QP_TX_MODE_16B_EN.dat.value = Reg_R(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_TX_MODE_16B_EN);
	tmp = fw_RG_QP_TX_MODE_16B_EN.hal.RG_QP_TX_RESERVE;
	tmp = (0x1<<8) | (tmp & (~(0x1<<8)));
	fw_RG_QP_TX_MODE_16B_EN.hal.RG_QP_TX_RESERVE = tmp;
	Reg_W(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_TX_MODE_16B_EN, fw_RG_QP_TX_MODE_16B_EN.dat.value); //write addr: 0x1FA5F028 = 0x1000000

	fw_PON_RXFEDIG_CTRL_0.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PON_RXFEDIG_CTRL_0);
	fw_PON_RXFEDIG_CTRL_0.hal.RG_QP_EQ_RX500M_CK_SEL = 0x0;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PON_RXFEDIG_CTRL_0, fw_PON_RXFEDIG_CTRL_0.dat.value); //write addr: 0x1FA5E100 = 0x2000409

	fw_PLL_CTRL_0.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_0);
	fw_PLL_CTRL_0.hal.rg_phya_auto_init = 0x1;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_0, fw_PLL_CTRL_0.dat.value); //write addr: 0x1FA5E400 = 0x60001



}

static int PCIe_QPhy_check_kband(struct vb235v_qphy *priv)
{
	unsigned int tmpvalue1 = 0, tmpvalue2 = 0, tmpdata = 0;

	rg_type_t(qp_pma_top_REG_PLL_CTRL_4) fw_PLL_CTRL_4;
	rg_type_t(REG_RG_QP_BGR_EN) fw_RG_QP_BGR_EN;
	rg_type_t(REG_RG_QP_PLL_IPLL_DIG_PWR_SEL) fw_RG_QP_PLL_IPLL_DIG_PWR_SEL;
	rg_type_t(qp_pma_top_REG_PLL_CTRL_2) fw_PLL_CTRL_2;
	rg_type_t(qp_pma_top_REG_INTF_CTRL_8) fw_INTF_CTRL_8;
	rg_type_t(REG_RG_QP_TDC_FT_CK_EN) fw_RG_QP_TDC_FT_CK_EN;
	rg_type_t(qp_pma_top_REG_INTF_STS_9) fw_INTF_STS_9;
	mdelay(50);

	fw_PLL_CTRL_4.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_4);
	fw_PLL_CTRL_4.hal.rg_da_qp_pll_icolp_en_intf = 0x0;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_4, fw_PLL_CTRL_4.dat.value); //write addr: 0x1FA5E410 = 0x0

	fw_RG_QP_BGR_EN.dat.value = Reg_R(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_BGR_EN);
	fw_RG_QP_BGR_EN.hal.RG_QP_BIAS_V2V_CAL = 0x15;
	Reg_W(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_BGR_EN, fw_RG_QP_BGR_EN.dat.value); //write addr: 0x1FA5F030 = 0x2AA0000

	fw_RG_QP_PLL_IPLL_DIG_PWR_SEL.dat.value = Reg_R(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_PLL_IPLL_DIG_PWR_SEL);
	fw_RG_QP_PLL_IPLL_DIG_PWR_SEL.hal.RG_QP_PLL_LDOLPF_VSEL = 0x1;
	fw_RG_QP_PLL_IPLL_DIG_PWR_SEL.hal.RG_QP_PLL_OSCAL_ENB = 0x1;
	Reg_W(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_PLL_IPLL_DIG_PWR_SEL, fw_RG_QP_PLL_IPLL_DIG_PWR_SEL.dat.value); //write addr: 0x1FA5F03C = 0x102B42A2

	fw_PLL_CTRL_2.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_2);
	fw_PLL_CTRL_2.hal.rg_da_qp_pll_rico_sel_intf = 0x1;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_2, fw_PLL_CTRL_2.dat.value); //write addr: 0x1FA5E408 = 0x21170305

	fw_INTF_CTRL_8.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_INTF_CTRL_8);
	fw_INTF_CTRL_8.hal.rg_da_qp_xtal_ext_en_force = 0x0;
	fw_INTF_CTRL_8.hal.rg_da_qp_xtal_ext_en_sel = 0x0;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_INTF_CTRL_8, fw_INTF_CTRL_8.dat.value); //write addr: 0x1FA5E320 = 0x0

	fw_PLL_CTRL_2.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_2);
	fw_PLL_CTRL_2.hal.rg_da_qp_pll_icoiq_en_intf = 0x0;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_2, fw_PLL_CTRL_2.dat.value); //write addr: 0x1FA5E408 = 0x21170305

	fw_RG_QP_TDC_FT_CK_EN.dat.value = Reg_R(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_TDC_FT_CK_EN);
	fw_RG_QP_TDC_FT_CK_EN.hal.RG_QP_PLL_DEBUG_SEL = 0x0;
	Reg_W(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_TDC_FT_CK_EN, fw_RG_QP_TDC_FT_CK_EN.dat.value); //write addr: 0x1FA5F038 = 0x80040100

	mdelay(5);
	fw_INTF_STS_9.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET,  _qp_pma_top_INTF_STS_9);
	dev_dbg(priv->dev, "ro_ad_qp_pll_vcocal_state_intf: 0x%x;\n", fw_INTF_STS_9.hal.ro_ad_qp_pll_vcocal_state_intf); //read addr: 0x1FA5E364 [23:16]
    tmpvalue1 = fw_INTF_STS_9.hal.ro_ad_qp_pll_vcocal_state_intf;

	fw_RG_QP_TDC_FT_CK_EN.hal.RG_QP_PLL_DEBUG_SEL = 0x1;
	Reg_W(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_TDC_FT_CK_EN, fw_RG_QP_TDC_FT_CK_EN.dat.value); //write addr: 0x1FA5F038 = 0x800C0100

	mdelay(5);
	fw_INTF_STS_9.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET,  _qp_pma_top_INTF_STS_9);
	dev_dbg(priv->dev, "ro_ad_qp_pll_vcocal_state_intf: 0x%x;\n", fw_INTF_STS_9.hal.ro_ad_qp_pll_vcocal_state_intf); //read addr: 0x1FA5E364 [23:16]
    tmpvalue2 = fw_INTF_STS_9.hal.ro_ad_qp_pll_vcocal_state_intf;

	tmpdata = (tmpvalue1 << 4) | tmpvalue2;
    if(0 != (tmpdata & 0x800) && (0xFFF != tmpdata))
    {
        return 0;
    }
    //KBAND_DONE = 0 or KBAND_Code = 0xFFF
    return 1;
}

static void tx_pll_disable(struct vb235v_qphy *priv)
{
	rg_type_t(qp_pma_top_REG_INTF_CTRL_6) fw_INTF_CTRL_6;
	rg_type_t(qp_pma_top_REG_PLL_CK_CTRL_1) fw_PLL_CK_CTRL_1;
	rg_type_t(qp_pma_top_REG_PLL_CTRL_0) fw_PLL_CTRL_0;
	rg_type_t(qp_pma_top_REG_INTF_CTRL_7) fw_INTF_CTRL_7;

	//TX Force Disable
	fw_INTF_CTRL_6.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_INTF_CTRL_6);
	fw_INTF_CTRL_6.hal.rg_da_qp_tx_data_en_force = 0x0;
	fw_INTF_CTRL_6.hal.rg_da_qp_tx_data_en_sel = 0x1;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_INTF_CTRL_6, fw_INTF_CTRL_6.dat.value); //write addr: 0x1FA5E318 = 0x2000

	//PLL Force Unstable
	fw_PLL_CK_CTRL_1.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CK_CTRL_1);
	fw_PLL_CK_CTRL_1.hal.rg_pll_force_unstable = 0x1;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CK_CTRL_1, fw_PLL_CK_CTRL_1.dat.value); //write addr: 0x1FA5E418 = 0x80107

	//PLL Disable
	fw_PLL_CTRL_0.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_0);
	fw_PLL_CTRL_0.hal.rg_phya_auto_init = 0x0;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_0, fw_PLL_CTRL_0.dat.value); //write addr: 0x1FA5E400 = 0x60000
	mdelay(1);
	fw_PLL_CTRL_0.hal.rg_phya_auto_init = 0x1;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_0, fw_PLL_CTRL_0.dat.value); //write addr: 0x1FA5E400 = 0x60001

	fw_INTF_CTRL_7.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_INTF_CTRL_7);
	fw_INTF_CTRL_7.hal.rg_da_qp_pll_en_force = 0x0;
	fw_INTF_CTRL_7.hal.rg_da_qp_pll_en_sel = 0x1;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_INTF_CTRL_7, fw_INTF_CTRL_7.dat.value); //write addr: 0x1FA5E31C = 0x20
}

static void tx_pll_enable(struct vb235v_qphy *priv)
{
	rg_type_t(REG_RG_QP_PLL_IPLL_DIG_PWR_SEL) fw_RG_QP_PLL_IPLL_DIG_PWR_SEL;
	rg_type_t(qp_pma_top_REG_INTF_CTRL_7) fw_INTF_CTRL_7;
	rg_type_t(qp_pma_top_REG_PLL_CK_CTRL_1) fw_PLL_CK_CTRL_1;
	rg_type_t(qp_pma_top_REG_INTF_CTRL_6) fw_INTF_CTRL_6;

	// PLL Reset to default
	fw_RG_QP_PLL_IPLL_DIG_PWR_SEL.dat.value = Reg_R(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_PLL_IPLL_DIG_PWR_SEL);
	fw_RG_QP_PLL_IPLL_DIG_PWR_SEL.hal.RG_QP_PLL_MONVC_EN = 0x0;
	fw_RG_QP_PLL_IPLL_DIG_PWR_SEL.hal.RG_QP_PLL_MON_LDO_SEL = 0x0;
	Reg_W(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_PLL_IPLL_DIG_PWR_SEL, fw_RG_QP_PLL_IPLL_DIG_PWR_SEL.dat.value); //write addr: 0x1FA5F03C = 0x102802A2

	fw_INTF_CTRL_7.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_INTF_CTRL_7);
	fw_INTF_CTRL_7.hal.rg_da_qp_pll_en_sel = 0x0;
	fw_INTF_CTRL_7.hal.rg_da_qp_pll_en_force = 0x0;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_INTF_CTRL_7, fw_INTF_CTRL_7.dat.value); //write addr: 0x1FA5E31C = 0x0

	//PLL Force stable
	fw_PLL_CK_CTRL_1.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CK_CTRL_1);
	fw_PLL_CK_CTRL_1.hal.rg_pll_force_unstable = 0x1;
	fw_PLL_CK_CTRL_1.hal.rg_pll_force_stable = 0x1;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CK_CTRL_1, fw_PLL_CK_CTRL_1.dat.value); //write addr: 0x1FA5E418 = 0xC0107

	fw_PLL_CK_CTRL_1.hal.rg_pll_force_unstable = 0x0;
	fw_PLL_CK_CTRL_1.hal.rg_pll_force_stable = 0x0;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CK_CTRL_1, fw_PLL_CK_CTRL_1.dat.value); //write addr: 0x1FA5E418 = 0x107

	//TX Force Enable
	fw_INTF_CTRL_6.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_INTF_CTRL_6);
	fw_INTF_CTRL_6.hal.rg_da_qp_tx_data_en_force = 0x1;
	fw_INTF_CTRL_6.hal.rg_da_qp_tx_data_en_sel = 0x0;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_INTF_CTRL_6, fw_INTF_CTRL_6.dat.value); //write addr: 0x1FA5E318 = 0x1000

	fw_INTF_CTRL_6.hal.rg_da_qp_tx_data_en_force = 0x0;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_INTF_CTRL_6, fw_INTF_CTRL_6.dat.value); //write addr: 0x1FA5E318 = 0x0


}

static int PCIe_QPhy_pll_kband_flow(struct vb235v_qphy *priv)
{
	rg_type_t(qp_pma_top_REG_INTF_CTRL_7) fw_INTF_CTRL_7;

    tx_pll_disable(priv);
	pcie_QPhy_init_original(priv);

	fw_INTF_CTRL_7.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_INTF_CTRL_7);
	//Select PLL_EN to Force mode
	// rg_type_t(qp_pma_top_REG_INTF_CTRL_7) fw_INTF_CTRL_7;
	fw_INTF_CTRL_7.hal.rg_da_qp_pll_en_force = 0x1;
	fw_INTF_CTRL_7.hal.rg_da_qp_pll_en_sel = 0x1;
	Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_INTF_CTRL_7, fw_INTF_CTRL_7.dat.value); //write addr: 0x1FA5E31C = 0x30

	dev_dbg(priv->dev, "/*********************** PCIe QPhy Check Kband First.*********************** /\n");
    return PCIe_QPhy_check_kband(priv);
}

static int pcie_QPhy_init(struct vb235v_qphy *priv)
{
    int i = 0;
	rg_type_t(qp_pma_top_REG_INTF_CTRL_7) fw_INTF_CTRL_7;
	rg_type_t(qp_pma_top_REG_PLL_CTRL_4) fw_PLL_CTRL_4;
	rg_type_t(REG_RG_QP_BGR_EN) fw_RG_QP_BGR_EN;
	rg_type_t(REG_RG_QP_PLL_IPLL_DIG_PWR_SEL) fw_RG_QP_PLL_IPLL_DIG_PWR_SEL;
	rg_type_t(qp_pma_top_REG_PLL_CTRL_2) fw_PLL_CTRL_2;
	rg_type_t(qp_pma_top_REG_INTF_CTRL_8) fw_INTF_CTRL_8;

	//--- Part1 ---//
	if(1 == PCIe_QPhy_pll_kband_flow(priv))
	{
		dev_dbg(priv->dev, "/*********************** PCIe QPhy Kband Retry Start.*********************** /\n");
		for(i = 0; i < 50; i++)
		{
			dev_dbg(priv->dev, "Retry %d\n",i);
			//--- Part2 ---//

			//PLL Disable
			fw_INTF_CTRL_7.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_INTF_CTRL_7);
			fw_INTF_CTRL_7.hal.rg_da_qp_pll_en_force = 0x0;
			fw_INTF_CTRL_7.hal.rg_da_qp_pll_en_sel = 0x1;
			Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_INTF_CTRL_7, fw_INTF_CTRL_7.dat.value); //write addr: 0x1FA5E31C = 0x20

			//PLL Config for CPR
			fw_PLL_CTRL_4.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_4);
			fw_PLL_CTRL_4.hal.rg_da_qp_pll_icolp_en_intf = 0x1;
			Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_4, fw_PLL_CTRL_4.dat.value); //write addr: 0x1FA5E410 = 0x4

			fw_RG_QP_BGR_EN.dat.value = Reg_R(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_BGR_EN);
			fw_RG_QP_BGR_EN.hal.RG_QP_BIAS_V2V_CAL = 0x0;
			Reg_W(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_BGR_EN, fw_RG_QP_BGR_EN.dat.value); //write addr: 0x1FA5F030 = 0xA0000

			fw_RG_QP_PLL_IPLL_DIG_PWR_SEL.dat.value = Reg_R(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_PLL_IPLL_DIG_PWR_SEL);
			fw_RG_QP_PLL_IPLL_DIG_PWR_SEL.hal.RG_QP_PLL_LDOLPF_VSEL = 0x3;
			fw_RG_QP_PLL_IPLL_DIG_PWR_SEL.hal.RG_QP_PLL_OSCAL_ENB = 0x0;
			Reg_W(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_PLL_IPLL_DIG_PWR_SEL, fw_RG_QP_PLL_IPLL_DIG_PWR_SEL.dat.value); //write addr: 0x1FA5F03C = 0x102002E2

			fw_PLL_CTRL_2.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_2);
			fw_PLL_CTRL_2.hal.rg_da_qp_pll_rico_sel_intf = 0x0;
			Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_2, fw_PLL_CTRL_2.dat.value); //write addr: 0x1FA5E408 = 0x1170305

			fw_INTF_CTRL_8.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_INTF_CTRL_8);
			fw_INTF_CTRL_8.hal.rg_da_qp_xtal_ext_en_force = 0x3;
			fw_INTF_CTRL_8.hal.rg_da_qp_xtal_ext_en_sel = 0x1;
			Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_INTF_CTRL_8, fw_INTF_CTRL_8.dat.value); //write addr: 0x1FA5E320 = 0x3800

			fw_PLL_CTRL_2.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_2);
			fw_PLL_CTRL_2.hal.rg_da_qp_pll_icoiq_en_intf = 0x0;
			Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_PLL_CTRL_2, fw_PLL_CTRL_2.dat.value); //write addr: 0x1FA5E408 = 0x1170305

			fw_RG_QP_PLL_IPLL_DIG_PWR_SEL.dat.value = Reg_R(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_PLL_IPLL_DIG_PWR_SEL);
			fw_RG_QP_PLL_IPLL_DIG_PWR_SEL.hal.RG_QP_PLL_MONVC_EN = 0x1;
			fw_RG_QP_PLL_IPLL_DIG_PWR_SEL.hal.RG_QP_PLL_MON_LDO_SEL = 0x3;
			Reg_W(QP_ANA_BASE, QP_ANA_OFFSET, _RG_QP_PLL_IPLL_DIG_PWR_SEL, fw_RG_QP_PLL_IPLL_DIG_PWR_SEL.dat.value); //write addr: 0x1FA5F03C = 0x102342E2

			//PLL Enable
			fw_INTF_CTRL_7.dat.value = Reg_R(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_INTF_CTRL_7);
			fw_INTF_CTRL_7.hal.rg_da_qp_pll_en_force = 0x1;
			fw_INTF_CTRL_7.hal.rg_da_qp_pll_en_sel = 0x1;
			Reg_W(QP_PMA_BASE, QP_PMA_OFFSET, _qp_pma_top_INTF_CTRL_7, fw_INTF_CTRL_7.dat.value); //write addr: 0x1FA5E31C = 0x30
			//--- End of Check Kband Code Flow ---//
			if(0 == PCIe_QPhy_check_kband(priv))
			{
				break;
			}
		}
	}
	if (i == 50)
		return -ETIMEDOUT;
	//--- Part3 ---//
	tx_pll_enable(priv);

	return 0;
}
