/* SPDX-License-Identifier: GPL-2.0-only
 * Selected register definitions from Airoha's 2024 AN7583 GPL headers.
 * This file contains only fields used by the port-1 development sequence.
 */
#ifndef VB235V_QPHY_FIELDS_H
#define VB235V_QPHY_FIELDS_H
typedef unsigned int FIELD;
#define rg_type_t(type) union { type hal; struct { u32 value; } dat; }
typedef struct
{


        FIELD RG_PCIE_CLKDRV_IMPSEL     : 5;
        FIELD rsv_5                     : 4;
        FIELD RG_PCIE_CLKDRV_RP         : 5;
        FIELD RG_PCIE_CLKDRV_HZ         : 1;
        FIELD rsv_15                    : 1;
        FIELD RG_PCIE_CLKDRV_OFFSET     : 3;
        FIELD RG_PCIE_CLKDRV_SLEW       : 2;
        FIELD RG_PCIE_CLKDRV_DUTY       : 2;
        FIELD RG_PCIE_CLKDRV_FORCEIN    : 2;
        FIELD RG_PCIE_CLKDRV_AMP        : 3;
        FIELD rsv_28                    : 1;
        FIELD RG_PCIE_CLKDET_VTH        : 2;
        FIELD RG_QP_TDC_AUTOEN          : 1;


} REG_RG_PCIE_CLKDRV_IMPSEL, *PREG_RG_PCIE_CLKDRV_IMPSEL;

typedef struct
{


        FIELD RG_QP_BGR_EN              : 1;
        FIELD RG_QP_CHPEN               : 1;
        FIELD RG_QP_BG_DIV              : 2;
        FIELD RG_QP_MPX_EN              : 1;
        FIELD rsv_5                     : 4;
        FIELD RG_QP_MPX_SEL             : 5;
        FIELD rsv_14                    : 3;
        FIELD RG_QP_VRT_VREF_SEL        : 4;
        FIELD RG_QP_BIAS_V2V_CAL        : 6;
        FIELD RG_QP_BG_MONEN            : 1;
        FIELD rsv_28                    : 4;


} REG_RG_QP_BGR_EN, *PREG_RG_QP_BGR_EN;

typedef struct
{


        FIELD RG_QP_CDR_FORCE_IBANDLPF_R_OFF : 1;
        FIELD RG_QP_CDR_PICAL_INV       : 1;
        FIELD RG_QP_CDR_PICAL_SEL       : 1;
        FIELD RG_QP_CDR_PIEYEBD4_SEL    : 1;
        FIELD RG_QP_CDR_PIEYE_XOR_EN    : 1;
        FIELD RG_QP_CDR_PI_CK_INV       : 1;
        FIELD RG_QP_CDR_PHYCK_DIV       : 7;
        FIELD RG_QP_CDR_PHYCK_RSTB      : 1;
        FIELD rsv_14                    : 2;
        FIELD RG_QP_CDR_PHYCK_SEL       : 2;
        FIELD rsv_18                    : 2;
        FIELD RG_QP_RX_MPX_SEL          : 3;
        FIELD rsv_23                    : 1;
        FIELD RG_QP_CDR_REFCK_DIV2_EN   : 1;
        FIELD RG_QP_RX_D0_LL_RESERVED   : 6;
        FIELD rsv_31                    : 1;


} REG_RG_QP_CDR_FORCE_IBANDLPF_R_OFF, *PREG_RG_QP_CDR_FORCE_IBANDLPF_R_OFF;

typedef struct
{


        FIELD RG_QP_CDR_LPF_MJV_LIM     : 4;
        FIELD RG_QP_CDR_LPF_RATIO       : 2;
        FIELD rsv_6                     : 26;


} REG_RG_QP_CDR_LPF_MJV_LIM, *PREG_RG_QP_CDR_LPF_MJV_LIM;

typedef struct
{


        FIELD RG_QP_CDR_PR_CKREF_DIV1   : 2;
        FIELD RG_QP_CDR_PR_CKREF_DIV    : 2;
        FIELD RG_QP_CDR_PR_CORSIG_OPT   : 2;
        FIELD RG_QP_CDR_PR_COR_HBW_EN   : 1;
        FIELD rsv_7                     : 1;
        FIELD RG_QP_CDR_PR_DAC_BAND     : 5;
        FIELD RG_QP_CDR_PR_DCMON_EN     : 1;
        FIELD rsv_14                    : 2;
        FIELD RG_QP_CDR_PR_DCMON_SEL    : 3;
        FIELD RG_QP_CDR_PR_INJ_FORCE_OFF : 1;
        FIELD RG_QP_CDR_PR_INJ_FORCE_ON : 1;
        FIELD rsv_21                    : 3;
        FIELD RG_QP_CDR_PR_KBAND_DIV    : 3;
        FIELD rsv_27                    : 5;


} REG_RG_QP_CDR_PR_CKREF_DIV1, *PREG_RG_QP_CDR_PR_CKREF_DIV1;

typedef struct
{


        FIELD RG_QP_CDR_PR_KBAND_DIV_PCIE : 6;
        FIELD RG_QP_CDR_PR_KBAND_PCIE_MODE : 1;
        FIELD RG_QP_CDR_PR_LDO_FORCE_ON : 1;
        FIELD RG_QP_CDR_PR_MONCK_EN     : 1;
        FIELD rsv_9                     : 3;
        FIELD RG_QP_CDR_PR_MONCK_MUX    : 3;
        FIELD RG_QP_CDR_PR_MONPI_EN     : 1;
        FIELD RG_QP_CDR_PR_MONPR_EN     : 1;
        FIELD RG_QP_CDR_PR_RSTB_BYPASS  : 1;
        FIELD RG_QP_CDR_PR_RST_DLY      : 2;
        FIELD RG_QP_CDR_PR_TDC_REF_SEL  : 2;
        FIELD rsv_22                    : 2;
        FIELD RG_QP_CDR_PR_VCOADC_OS    : 4;
        FIELD RG_QP_CDR_PR_VREG_CKBUF_VAL : 2;
        FIELD RG_QP_CDR_PR_XFICK_EN     : 1;
        FIELD RG_QP_CDR_FORCE_IBANDLPF_C_OFF : 1;


} REG_RG_QP_CDR_PR_KBAND_DIV_PCIE, *PREG_RG_QP_CDR_PR_KBAND_DIV_PCIE;

typedef struct
{


        FIELD RG_QP_PLL_IPLL_DIG_PWR_SEL : 1;
        FIELD RG_QP_PLL_KBAND_KFC       : 2;
        FIELD RG_QP_PLL_KBAND_MEAS_EN   : 1;
        FIELD RG_QP_PLL_LOAD_EN         : 1;
        FIELD RG_QP_PLL_LDOLPF_VSEL     : 2;
        FIELD RG_QP_PLL_LDOPFD_VSEL     : 2;
        FIELD RG_QP_PLL_LDOVCO_VSEL     : 2;
        FIELD RG_QP_PLL_MONCK_DIV4_EN   : 1;
        FIELD RG_QP_PLL_MONCK_EN        : 1;
        FIELD RG_QP_PLL_MONREF_EN       : 1;
        FIELD RG_QP_PLL_MONVC_EN        : 1;
        FIELD rsv_15                    : 1;
        FIELD RG_QP_PLL_MON_LDO_SEL     : 3;
        FIELD RG_QP_PLL_OSCAL_ENB       : 1;
        FIELD rsv_20                    : 1;
        FIELD RG_QP_PLL_POSTDIV         : 2;
        FIELD rsv_23                    : 2;
        FIELD RG_QP_PLL_PREDIV          : 2;
        FIELD RG_QP_PLL_RLP_SEL         : 1;
        FIELD RG_QP_PLL_TCL_EN          : 1;
        FIELD RG_QP_PLL_SDM_DI_LS       : 2;
        FIELD rsv_31                    : 1;


} REG_RG_QP_PLL_IPLL_DIG_PWR_SEL, *PREG_RG_QP_PLL_IPLL_DIG_PWR_SEL;

typedef struct
{


        FIELD RG_QP_PLL_SDM_ORD         : 2;
        FIELD RG_QP_PLL_SDM_OUT         : 1;
        FIELD RG_QP_PLL_SSC_PHASE_INI   : 1;
        FIELD RG_QP_PLL_SSC_TRI_EN      : 1;
        FIELD RG_QP_PLL_POST_MONCK_EN   : 1;
        FIELD rsv_6                     : 3;
        FIELD RG_QP_PLL_POST_MONCK_SEL  : 2;
        FIELD RG_QP_PLL_FREQ_MEAS_EN    : 1;
        FIELD rsv_12                    : 20;


} REG_RG_QP_PLL_SDM_ORD, *PREG_RG_QP_PLL_SDM_ORD;

typedef struct
{


        FIELD RG_QP_RXAFE_RESERVE       : 8;
        FIELD RG_QP_RX_DAC_MEAS_EN      : 1;
        FIELD RG_QP_RX_VCMHPFSEL        : 1;
        FIELD RG_QP_CDR_PD_EDGE_DIS     : 1;
        FIELD RG_QP_CDR_PD_10B_EN       : 1;
        FIELD rsv_12                    : 20;


} REG_RG_QP_RXAFE_RESERVE, *PREG_RG_QP_RXAFE_RESERVE;

typedef struct
{


        FIELD RG_QP_RXLBTX_EN           : 1;
        FIELD RG_QP_TX250MCK_INVB       : 1;
        FIELD RG_QP_TX_CHGPLR_CN1       : 1;
        FIELD RG_QP_TX_CHGPLR_C1        : 1;
        FIELD RG_QP_TX_CHGPLR_C2        : 1;
        FIELD RG_QP_TX_SR_REDUCTION     : 3;
        FIELD RG_QP_TX_INT_EN           : 1;
        FIELD rsv_9                     : 7;
        FIELD RG_QP_TX_TERMCAL_VREF_H   : 3;
        FIELD rsv_19                    : 2;
        FIELD RG_QP_TX_TERMCAL_VREF_L   : 3;
        FIELD RG_QP_TX_TERMCAL_SELPN    : 1;
        FIELD RG_QP_TX_RXDET_METHOD     : 1;
        FIELD RG_QP_TX_AUTOZERO_EN      : 1;
        FIELD RG_QP_TX_DMEDGEGEN_EN     : 1;
        FIELD rsv_28                    : 4;


} REG_RG_QP_RXLBTX_EN, *PREG_RG_QP_RXLBTX_EN;

typedef struct
{


        FIELD RG_QP_TDC_FT_CK_EN        : 1;
        FIELD RG_QP_TDC_MON_CK_EN       : 1;
        FIELD rsv_2                     : 3;
        FIELD RG_QP_PLL_MONCK_SEL       : 3;
        FIELD RG_VUSB10_ON              : 1;
        FIELD RG_QP_XTAL_TOP_RESERVE0   : 8;
        FIELD RG_QP_PLL_RST_DLY         : 2;
        FIELD RG_QP_PLL_DEBUG_SEL       : 1;
        FIELD rsv_20                    : 1;
        FIELD RG_QP_PLL_IBAND           : 11;


} REG_RG_QP_TDC_FT_CK_EN, *PREG_RG_QP_TDC_FT_CK_EN;

typedef struct
{


        FIELD RG_QP_TX_MODE_16B_EN      : 1;
        FIELD RG_QP_TXLBRX_EN           : 1;
        FIELD RG_QP_TX_VLMON_EN         : 1;
        FIELD RG_QP_TX_VLMON_SEL        : 3;
        FIELD RG_QP_TX_CKMON_EN         : 1;
        FIELD rsv_7                     : 2;
        FIELD RG_QP_TX_CKMON_SEL        : 4;
        FIELD rsv_13                    : 3;
        FIELD RG_QP_TX_RESERVE          : 16;


} REG_RG_QP_TX_MODE_16B_EN, *PREG_RG_QP_TX_MODE_16B_EN;

typedef struct
{


        FIELD rg_force_pma_rx_eq_ck_en  : 1;
        FIELD rg_force_tdc_ftck_en      : 1;
        FIELD rg_force_tdc_sync_ck_en   : 1;
        FIELD rg_force_cdr_pr_fll_dig_clk_en : 1;
        FIELD rg_force_cdr_pr_fbk_ck_en : 1;
        FIELD rsv_5                     : 11;
        FIELD rg_tdc_ftck_inv           : 1;
        FIELD rg_tdc_sync_ck_inv        : 1;
        FIELD rg_cdr_pr_fll_dig_clk_inv : 1;
        FIELD rg_cdr_pr_fbk_ck_inv      : 1;
        FIELD rg_pll_dig_fbk_ck_inv     : 1;
        FIELD rg_pll_dig_ref_ck_inv     : 1;
        FIELD rg_ns_clk_z_inv           : 1;
        FIELD rg_pma_tx_osr_short_ck_inv : 1;
        FIELD rg_us_ck_div_sel          : 1;
        FIELD rg_ns_ck_div_sel          : 1;
        FIELD rsv_26                    : 6;


} qp_dig_csr_REG_QP_CK_RST_CTRL_3, *Pqp_dig_csr_REG_QP_CK_RST_CTRL_3;

typedef struct
{


        FIELD rg_usb5_tx_clk_inv        : 1;
        FIELD rg_usb5_rx_clk_inv        : 1;
        FIELD rg_usb2p5_tx_clk_inv      : 1;
        FIELD rg_usb2p5_rx_clk_inv      : 1;
        FIELD rsv_4                     : 4;
        FIELD rg_usb5_phy_tx_ck_en_force_sel : 1;
        FIELD rg_usb5_phy_rx_ck_en_force_sel : 1;
        FIELD rg_usb2p5_phy_tx_ck_en_force_sel : 1;
        FIELD rg_usb2p5_phy_rx_ck_en_force_sel : 1;
        FIELD rsv_12                    : 4;
        FIELD rg_force_usb5_tx_clk_en   : 1;
        FIELD rg_force_usb5_rx_clk_en   : 1;
        FIELD rg_force_usb2p5_tx_clk_en : 1;
        FIELD rg_force_usb2p5_rx_clk_en : 1;
        FIELD rg_force_pll_dig_fbk_ck_en : 1;
        FIELD rg_force_pll_dig_ref_ck_en : 1;
        FIELD rsv_22                    : 2;
        FIELD rg_multi_phy_usb_mode_en  : 1;
        FIELD rg_multi_phy_usb5_en      : 1;
        FIELD rg_multi_phy_usb2p5_en    : 1;
        FIELD rg_pma_tx_osr_norm_usb_mode_sel : 1;
        FIELD rg_pma_tx_norm_usb_mode_sel : 1;
        FIELD rg_pma_rx_eq_usb_mode_sel : 1;
        FIELD rsv_30                    : 2;


} qp_dig_csr_REG_QP_CK_RST_CTRL_7, *Pqp_dig_csr_REG_QP_CK_RST_CTRL_7;

typedef struct
{


        FIELD rg_da_qp_cdr_pr_pieye_pwdb_force : 1;
        FIELD rg_da_qp_cdr_pr_pieye_pwdb_sel : 1;
        FIELD rg_da_qp_cdr_pd_pwdb_force : 1;
        FIELD rg_da_qp_cdr_pd_pwdb_sel  : 1;
        FIELD rg_da_qp_tx_term_vref_sel_force : 1;
        FIELD rg_da_qp_tx_term_vref_sel_sel : 1;
        FIELD rg_da_qp_tx_drv_en_force  : 1;
        FIELD rg_da_qp_tx_drv_en_sel    : 1;
        FIELD rg_da_qp_tx_impcalib_en_force : 1;
        FIELD rg_da_qp_tx_impcalib_en_sel : 1;
        FIELD rg_da_qp_rxdet_en_force   : 1;
        FIELD rg_da_qp_rxdet_en_sel     : 1;
        FIELD rg_da_qp_tx_data_en_force : 1;
        FIELD rg_da_qp_tx_data_en_sel   : 1;
        FIELD rg_da_qp_tx_ser_en_force  : 1;
        FIELD rg_da_qp_tx_ser_en_sel    : 1;
        FIELD rg_da_qp_tx_eidle_lp_en_force : 1;
        FIELD rg_da_qp_tx_eidle_lp_en_sel : 1;
        FIELD rg_da_qp_tx_lfps_en_force : 1;
        FIELD rg_da_qp_tx_lfps_en_sel   : 1;
        FIELD rg_da_qp_tx_lfps_force    : 1;
        FIELD rg_da_qp_tx_lfps_sel      : 1;
        FIELD rg_da_qp_bias_en_force    : 1;
        FIELD rg_da_qp_bias_en_sel      : 1;
        FIELD rg_da_qp_bg_lpf_en_force  : 1;
        FIELD rg_da_qp_bg_lpf_en_sel    : 1;
        FIELD rg_da_pcie_clkrx_en_force : 1;
        FIELD rg_da_pcie_clkrx_en_sel   : 1;
        FIELD rg_da_pcie_clktx_en_force : 1;
        FIELD rg_da_pcie_clktx_en_sel   : 1;
        FIELD rg_da_qp_xtal_rx_en_force : 1;
        FIELD rg_da_qp_xtal_rx_en_sel   : 1;


} qp_pma_top_REG_INTF_CTRL_6, *Pqp_pma_top_REG_INTF_CTRL_6;

typedef struct
{


        FIELD rg_da_pcie_ckdet_en_force : 1;
        FIELD rg_da_pcie_ckdet_en_sel   : 1;
        FIELD rg_da_qp_pll_sdm_di_en_force : 1;
        FIELD rg_da_qp_pll_sdm_di_en_sel : 1;
        FIELD rg_da_qp_pll_en_force     : 1;
        FIELD rg_da_qp_pll_en_sel       : 1;
        FIELD rg_da_qp_pll_icoiq_en_force : 1;
        FIELD rg_da_qp_pll_icoiq_en_sel : 1;
        FIELD rg_da_qp_pll_pck_sel_force : 1;
        FIELD rg_da_qp_pll_pck_sel_sel  : 1;
        FIELD rg_da_qp_pll_pfd_offset_en_force : 1;
        FIELD rg_da_qp_pll_pfd_offset_en_sel : 1;
        FIELD rg_da_qp_pll_phy_ck_en_force : 1;
        FIELD rg_da_qp_pll_phy_ck_en_sel : 1;
        FIELD rg_da_qp_pll_postdiv_en_force : 1;
        FIELD rg_da_qp_pll_postdiv_en_sel : 1;
        FIELD rg_da_qp_pll_rico_sel_force : 1;
        FIELD rg_da_qp_pll_rico_sel_sel : 1;
        FIELD rg_da_qp_pll_sdm_chg_force : 1;
        FIELD rg_da_qp_pll_sdm_chg_sel  : 1;
        FIELD rg_da_qp_pll_sdm_ifm_force : 1;
        FIELD rg_da_qp_pll_sdm_ifm_sel  : 1;
        FIELD rg_da_qp_pll_ssc_en_force : 1;
        FIELD rg_da_qp_pll_ssc_en_sel   : 1;
        FIELD rg_da_qp_pll_icolp_en_force : 1;
        FIELD rg_da_qp_pll_icolp_en_sel : 1;
        FIELD rg_da_qp_pll_tdc_txck_sel_force : 1;
        FIELD rg_da_qp_pll_tdc_txck_sel_sel : 1;
        FIELD rg_da_qp_tdc_cal_bw_force : 1;
        FIELD rg_da_qp_tdc_cal_bw_sel   : 1;
        FIELD rg_da_qp_tdc_cal_offset_force : 1;
        FIELD rg_da_qp_tdc_cal_offset_sel : 1;


} qp_pma_top_REG_INTF_CTRL_7, *Pqp_pma_top_REG_INTF_CTRL_7;

typedef struct
{


        FIELD rg_da_qp_tdc_en_force     : 1;
        FIELD rg_da_qp_tdc_en_sel       : 1;
        FIELD rg_da_qp_lfps_deglitch_force : 2;
        FIELD rg_da_qp_lfps_deglitch_sel : 1;
        FIELD rg_da_qp_tx_term_sel_force : 2;
        FIELD rg_da_qp_tx_term_sel_sel  : 1;
        FIELD rg_da_qp_tx_dem_force     : 2;
        FIELD rg_da_qp_tx_dem_sel       : 1;
        FIELD rg_da_qp_xtal_ext_en_force : 2;
        FIELD rg_da_qp_xtal_ext_en_sel  : 1;
        FIELD rg_da_qp_pll_bc_force     : 2;
        FIELD rg_da_qp_pll_bc_sel       : 1;
        FIELD rg_da_qp_pll_bpb_force    : 2;
        FIELD rg_da_qp_pll_bpb_sel      : 1;
        FIELD rg_da_qp_pll_fbksel_force : 2;
        FIELD rg_da_qp_pll_fbksel_sel   : 1;
        FIELD rg_da_qp_pll_kband_prediv_force : 2;
        FIELD rg_da_qp_pll_kband_prediv_sel : 1;
        FIELD rg_da_qp_pll_pfd_offset_force : 2;
        FIELD rg_da_qp_pll_pfd_offset_sel : 1;
        FIELD rg_da_qp_pll_sdm_hren_force : 2;
        FIELD rg_da_qp_pll_sdm_hren_sel : 1;


} qp_pma_top_REG_INTF_CTRL_8, *Pqp_pma_top_REG_INTF_CTRL_8;

typedef struct
{


        FIELD rg_da_qp_pll_ssc_dir_dly_force : 2;
        FIELD rg_da_qp_pll_ssc_dir_dly_sel : 1;
        FIELD rsv_3                     : 1;
        FIELD rg_da_qp_tx_fir_cn1_force : 3;
        FIELD rg_da_qp_tx_fir_cn1_sel   : 1;
        FIELD rg_da_qp_pll_bpa_force    : 3;
        FIELD rg_da_qp_pll_bpa_sel      : 1;
        FIELD rg_da_qp_pll_br_force     : 3;
        FIELD rg_da_qp_pll_br_sel       : 1;
        FIELD rg_da_qp_rx_dcleq_force   : 4;
        FIELD rg_da_qp_rx_dcleq_sel     : 1;
        FIELD rg_da_qp_pll_ir_force     : 4;
        FIELD rg_da_qp_pll_ir_sel       : 1;
        FIELD rg_da_qp_rx_imp_sel_force : 5;
        FIELD rg_da_qp_rx_imp_sel_sel   : 1;


} qp_pma_top_REG_INTF_CTRL_9, *Pqp_pma_top_REG_INTF_CTRL_9;

typedef struct
{


        FIELD ro_ad_qp_sigdet_out_intf  : 1;
        FIELD ro_ad_qp_sigdet_cal_out_intf : 1;
        FIELD ro_ad_qp_rx_lfps_intf     : 1;
        FIELD ro_ad_qp_crsdet_out_intf  : 1;
        FIELD ro_ad_qp_crsdet_lthout_intf : 1;
        FIELD ro_ad_qp_cdr_pi_pderr_intf : 1;
        FIELD ro_ad_qp_cdr_lpf_oneshot_trig_intf : 1;
        FIELD ro_ad_qp_cdr_pr_fll_dig_rstb_intf : 1;
        FIELD ro_ad_qp_cdr_pr_vco_overspeed_intf : 1;
        FIELD ro_ad_qp_termcal_dir_intf : 1;
        FIELD ro_ad_qp_tx_cmdet_intf    : 1;
        FIELD ro_ad_pcie_ckdet_out_intf : 1;
        FIELD ro_ad_qp_pll_ssc_dir_intf : 1;
        FIELD ro_ad_qp_pll_ssc_en_intf  : 1;
        FIELD ro_ad_qp_tdc_leadlag_intf : 1;
        FIELD rsv_15                    : 1;
        FIELD ro_ad_qp_pll_vcocal_state_intf : 8;
        FIELD ro_ad_qp_tdc_c_intf       : 8;


} qp_pma_top_REG_INTF_STS_9, *Pqp_pma_top_REG_INTF_STS_9;

typedef struct
{


        FIELD rg_da_qp_xtal_ext_en_intf : 2;
        FIELD rsv_2                     : 2;
        FIELD rg_da_pcie_clkrx_en_intf  : 1;
        FIELD rg_da_pcie_clktx_en_intf  : 1;
        FIELD rg_da_qp_xtal_rx_en_intf  : 1;
        FIELD rg_da_pcie_ckdet_en_intf  : 1;
        FIELD rg_da_qp_pll_sdm_di_en_intf : 1;
        FIELD rg_da_qp_pll_tdc_txck_sel_intf : 1;
        FIELD rsv_10                    : 22;


} qp_pma_top_REG_PLL_CK_CTRL_0, *Pqp_pma_top_REG_PLL_CK_CTRL_0;

typedef struct
{


        FIELD rg_pll_stabel_cnt         : 8;
        FIELD rg_pll_cplt_stabel_cnt    : 8;
        FIELD rg_pll_cplt_force_on      : 1;
        FIELD rg_pll_cplt_force_off     : 1;
        FIELD rg_pll_force_stable       : 1;
        FIELD rg_pll_force_unstable     : 1;
        FIELD rg_pll_stable_source_sel  : 1;
        FIELD rsv_21                    : 11;


} qp_pma_top_REG_PLL_CK_CTRL_1, *Pqp_pma_top_REG_PLL_CK_CTRL_1;

typedef struct
{


        FIELD rg_pcie_mode_pll_auto_en  : 1;
        FIELD rg_pcie_mode_pll_auto_on_en : 1;
        FIELD rg_pcie_mode_pll_auto_off_en : 1;
        FIELD rsv_3                     : 29;


} qp_pma_top_REG_PLL_CK_CTRL_2, *Pqp_pma_top_REG_PLL_CK_CTRL_2;

typedef struct
{


        FIELD rg_phya_auto_init         : 1;
        FIELD rg_phya_pwd_mux           : 1;
        FIELD rg_phya_pwd               : 1;
        FIELD rsv_3                     : 1;
        FIELD rg_tx_disable_mux         : 1;
        FIELD rg_tx_disable             : 1;
        FIELD rg_rx_pwd_mux             : 1;
        FIELD rg_rx_pwd                 : 1;
        FIELD rg_force_da_pll_en        : 1;
        FIELD rg_da_pll_en              : 1;
        FIELD rg_da_pll_en_mux          : 1;
        FIELD rsv_11                    : 5;
        FIELD rg_da_pll_en_dly_cnt      : 8;
        FIELD rsv_24                    : 8;


} qp_pma_top_REG_PLL_CTRL_0, *Pqp_pma_top_REG_PLL_CTRL_0;

typedef struct
{


        FIELD rg_lpf_en_to_ssc_dly_cnt  : 16;
        FIELD rg_bias_pwd_to_bg_lpf_en_dly : 5;
        FIELD rsv_21                    : 3;
        FIELD rg_syspll_pwd_to_syspll_ready_dly : 4;
        FIELD rg_pll_autok_vco_to_pll_bias_lpf_en_dly : 2;
        FIELD rg_qp_pll_ssc_en          : 1;
        FIELD rsv_31                    : 1;


} qp_pma_top_REG_PLL_CTRL_1, *Pqp_pma_top_REG_PLL_CTRL_1;

typedef struct
{


        FIELD rg_da_qp_pll_bc_intf      : 2;
        FIELD rg_da_qp_pll_bpa_intf     : 3;
        FIELD rsv_5                     : 1;
        FIELD rg_da_qp_pll_bpb_intf     : 2;
        FIELD rg_da_qp_pll_br_intf      : 3;
        FIELD rsv_11                    : 1;
        FIELD rg_da_qp_pll_fbksel_intf  : 2;
        FIELD rg_da_qp_pll_icoiq_en_intf : 1;
        FIELD rsv_15                    : 1;
        FIELD rg_da_qp_pll_ir_intf      : 4;
        FIELD rg_da_qp_pll_kband_prediv_intf : 2;
        FIELD rg_da_qp_pll_pck_sel_intf : 1;
        FIELD rsv_23                    : 1;
        FIELD rg_da_qp_pll_pfd_offset_intf : 2;
        FIELD rg_da_qp_pll_pfd_offset_en_intf : 1;
        FIELD rg_da_qp_pll_phy_ck_en_intf : 1;
        FIELD rg_da_qp_pll_postdiv_en_intf : 1;
        FIELD rg_da_qp_pll_rico_sel_intf : 1;
        FIELD rg_da_qp_pll_sdm_ifm_intf : 1;
        FIELD rsv_31                    : 1;


} qp_pma_top_REG_PLL_CTRL_2, *Pqp_pma_top_REG_PLL_CTRL_2;

typedef struct
{


        FIELD rg_da_qp_pll_ssc_delta_intf : 16;
        FIELD rg_da_qp_pll_ssc_period_intf : 16;


} qp_pma_top_REG_PLL_CTRL_3, *Pqp_pma_top_REG_PLL_CTRL_3;

typedef struct
{


        FIELD rg_da_qp_pll_ssc_dir_dly_intf : 2;
        FIELD rg_da_qp_pll_icolp_en_intf : 1;
        FIELD rg_da_qp_pll_sdm_hren_intf : 2;
        FIELD rsv_5                     : 27;


} qp_pma_top_REG_PLL_CTRL_4, *Pqp_pma_top_REG_PLL_CTRL_4;

typedef struct
{


        FIELD RG_QP_EQ_ALGRTHM_SEL      : 1;
        FIELD RG_QP_EQ_CHK_EYE_H        : 1;
        FIELD RG_QP_EQ_DFEXEN_SEL       : 1;
        FIELD RG_QP_EQ_DFEX_DIS         : 1;
        FIELD RG_QP_EQ_DFEX_EN          : 1;
        FIELD RG_QP_EQ_DFEX_RST         : 1;
        FIELD RG_QP_EQ_DFEYEN_STOP_DIS  : 1;
        FIELD RG_QP_EQ_DFE_TOG          : 1;
        FIELD RG_QP_EQ_EYE_CNT_EN       : 1;
        FIELD RG_QP_EQ_EYE_MON_EN       : 1;
        FIELD RG_QP_EQ_GATED_RXD_B      : 1;
        FIELD RG_QP_EQ_PILPO_ROUT       : 1;
        FIELD RG_QP_EQ_RX500M_CK_SEL    : 1;
        FIELD RG_QP_EQ_STOPTIME         : 1;
        FIELD RG_QP_EQ_TRI_DET_EN       : 1;
        FIELD RG_SSUSB_FORCE_RX_FR_MODE : 1;
        FIELD RG_SSUSB_RX_FR_MODE       : 1;
        FIELD rsv_17                    : 7;
        FIELD RG_SSUSB_RX_DFE_EN        : 1;
        FIELD RG_SSUSB_RX_DFE_RST       : 1;
        FIELD rsv_26                    : 6;


} qp_pma_top_REG_PON_RXFEDIG_CTRL_0, *Pqp_pma_top_REG_PON_RXFEDIG_CTRL_0;

typedef struct
{


        FIELD rg_fval_tx_eidle_lp_off   : 1;
        FIELD rg_force_rx_det_ctrl      : 1;
        FIELD rg_fval_rx_det_en         : 1;
        FIELD rg_tx_rxdet_en            : 1;
        FIELD rg_rxdet_en_window        : 6;
        FIELD rg_force_qp_tx_reserve    : 1;
        FIELD rg_rxdet_mask_clr         : 1;
        FIELD rg_rxdet_rd_wait_timer    : 4;
        FIELD rg_impcalib_en            : 1;
        FIELD rg_force_tx_calib_en      : 1;
        FIELD rg_termcal_vsel_timer     : 6;
        FIELD rg_tx_termcal_count       : 3;
        FIELD rg_fval_tx_impcalib_en    : 1;
        FIELD rg_fval_tx_term_sel       : 2;
        FIELD rg_fval_tx_term_vref_sel  : 1;
        FIELD rg_ssusb_tx_eidle_sel     : 1;


} qp_pma_top_REG_QP_TX_DA_CTRL_0, *Pqp_pma_top_REG_QP_TX_DA_CTRL_0;

typedef struct
{


        FIELD rg_tx_data_test_mode      : 1;
        FIELD rg_test_tx_lfps_en        : 1;
        FIELD rg_test_tx_data_en        : 1;
        FIELD rg_test_tx_cp8            : 1;
        FIELD rg_test_tx_lfps_type      : 3;
        FIELD rsv_7                     : 1;
        FIELD rg_test_tx_data_count     : 9;
        FIELD rsv_17                    : 7;
        FIELD rg_qphy_redun_sel         : 2;
        FIELD rg_force_tphy_mode        : 1;
        FIELD rsv_27                    : 1;
        FIELD rg_tx_data_rate_sel       : 3;
        FIELD rg_ssusb_tx_ser_en_sel    : 1;


} qp_pma_top_REG_QP_TX_DA_CTRL_3, *Pqp_pma_top_REG_QP_TX_DA_CTRL_3;

typedef struct
{


        FIELD rg_qp_crsdet_en           : 1;
        FIELD rg_qp_crsdet_rstb         : 1;
        FIELD rg_qp_rx_scan             : 1;
        FIELD rg_force_eq_en_sel        : 1;
        FIELD rg_force_eq_en            : 1;
        FIELD rg_force_cdr_lck2ref_pre_sel : 1;
        FIELD rg_force_cdr_lck2ref_pre  : 1;
        FIELD rg_qp_cdr_settle_rdy_cnt_pre_time : 11;
        FIELD rg_qp_cdr_settle_rdy_cnt_time : 11;
        FIELD rg_force_cdr_settle_ok_sel : 1;
        FIELD rg_force_cdr_settle_ok    : 1;
        FIELD rsv_31                    : 1;


} qp_pma_top_REG_RX_CTRL_10, *Pqp_pma_top_REG_RX_CTRL_10;

typedef struct
{


        FIELD rg_force_freq_lock_sel    : 1;
        FIELD rg_force_freq_lock        : 1;
        FIELD rg_force_saos_rdy_sel     : 1;
        FIELD rg_force_saos_rdy         : 1;
        FIELD rg_qp_eq_rstep1           : 2;
        FIELD rg_qp_eq_rstep2           : 2;
        FIELD rg_qp_force_eq_rdy_sel    : 1;
        FIELD rg_qp_force_eq_rdy        : 1;
        FIELD rg_qp_force_speed_sel     : 1;
        FIELD rg_qp_force_eq_en_sel     : 1;
        FIELD rg_qp_force_eq_en         : 1;
        FIELD rg_qp_rx_dcleq_intf       : 4;
        FIELD rg_qp_force_sigdet_sel    : 1;
        FIELD rg_qp_force_sigdet        : 1;
        FIELD rg_qp_force_sigdet_5g     : 1;
        FIELD rg_qp_force_sigdet_10g    : 1;
        FIELD rg_qp_sigdet_cal_sample_time : 5;
        FIELD rsv_26                    : 6;


} qp_pma_top_REG_RX_CTRL_11, *Pqp_pma_top_REG_RX_CTRL_11;

typedef struct
{


        FIELD rg_qp_freq_det_frc        : 1;
        FIELD rg_qp_freq_det_frc_en     : 1;
        FIELD rg_qp_lpf_window_sel      : 2;
        FIELD rg_qp_phya_pwd            : 1;
        FIELD rsv_5                     : 3;
        FIELD rg_qp_ppm_thres           : 6;
        FIELD rsv_14                    : 2;
        FIELD rg_qp_rx_eq_en_h_dly      : 13;
        FIELD rsv_29                    : 2;
        FIELD rg_qp_rx_pwd              : 1;


} qp_pma_top_REG_RX_CTRL_2, *Pqp_pma_top_REG_RX_CTRL_2;

typedef struct
{


        FIELD rg_qp_force_speed_chg_all_re_en : 1;
        FIELD rg_qp_pcie_usb_sol_1      : 1;
        FIELD rg_qp_force_pcie_mode_sel : 1;
        FIELD rg_qp_force_pcie_mode     : 1;
        FIELD rg_qp_force_spd_chg_all   : 1;
        FIELD rsv_5                     : 3;
        FIELD rg_qp_force_rx_path_rdy_time : 8;
        FIELD rg_qp_lck2data_dly_time   : 10;
        FIELD rg_qp_pcie_usb_system     : 1;
        FIELD rg_qp_force_sigdet_or     : 1;
        FIELD rg_qp_force_sigdet_and    : 1;
        FIELD rg_qp_force_sigdet_usb    : 1;
        FIELD rg_qp_force_usb_mode_sel  : 1;
        FIELD rg_qp_force_usb_mode      : 1;


} qp_pma_top_REG_RX_CTRL_36, *Pqp_pma_top_REG_RX_CTRL_36;

typedef struct
{


        FIELD rg_qp_eq_en_dly           : 13;
        FIELD rg_qp_force_eq_dly_en_sel : 1;
        FIELD rg_qp_force_eq_dly_en     : 1;
        FIELD rg_qp_sgmii_eq_train_sel  : 1;
        FIELD rg_qp_force_pcie_cdr_lpf_kp_gain_en : 1;
        FIELD rg_qp_pcie_gen1_cdr_lpf_kp_gain : 3;
        FIELD rg_qp_pcie_gen2_cdr_lpf_kp_gain : 3;
        FIELD rg_qp_force_pcie_cdr_lpf_ki_gain_en : 1;
        FIELD rg_qp_pcie_gen1_cdr_lpf_ki_gain : 3;
        FIELD rg_qp_pcie_gen2_cdr_lpf_ki_gain : 3;
        FIELD rsv_30                    : 2;


} qp_pma_top_REG_RX_CTRL_45, *Pqp_pma_top_REG_RX_CTRL_45;

typedef struct
{


        FIELD rg_qp_force_usb_pcie_pd_pwd_sel : 1;
        FIELD rg_qp_force_usb_pcie_pd_pwd : 1;
        FIELD rg_qp_force_usb_pcie_pr_pwd_sel : 1;
        FIELD rg_qp_force_usb_pcie_pr_pwd : 1;
        FIELD rg_qp_force_usb_pcie_eye_pwd_sel : 1;
        FIELD rg_qp_force_usb_pcie_eye_pwd : 1;
        FIELD rg_qp_force_usb_pcie_afe_pwd_sel : 1;
        FIELD rg_qp_force_usb_pcie_afe_pwd : 1;
        FIELD rg_qp_force_usb_pcie_sigdet_en_sel : 1;
        FIELD rg_qp_force_usb_pcie_sigdet_en : 1;
        FIELD rg_qp_force_usb_pcie_power_st_sel : 1;
        FIELD rg_qp_force_usb_pcie_power_st : 2;
        FIELD rg_qp_fre_lock_sel        : 1;
        FIELD rg_qp_force_power_st_change_sel : 1;
        FIELD rg_qp_force_power_st_change : 1;
        FIELD rg_qp_force_pcie_cdr_pr_kband_div_en : 1;
        FIELD rg_qp_pcie_gen2_cdr_pr_kband_div : 3;
        FIELD rg_qp_pcie_gen1_cdr_pr_kband_div : 3;
        FIELD rg_force_usb_sig_clr      : 1;
        FIELD rg_qp_force_last_lfps_finish_sel : 1;
        FIELD rg_qp_force_last_lfps_finish : 1;
        FIELD rg_reback_p0_lck2ref_en   : 1;
        FIELD rg_qp_pcie_usb_bypass_eq_p1_to_p0_en : 1;
        FIELD rg_qp_pcie_usb_bypass_eq_p2_to_p0_en : 1;
        FIELD rg_qp_pcie_usb_bypass_eq_p3_to_p0_en : 1;
        FIELD rsv_30                    : 2;


} qp_pma_top_REG_RX_CTRL_46, *Pqp_pma_top_REG_RX_CTRL_46;

typedef struct
{


        FIELD rg_qp_impcal_cyccnt       : 10;
        FIELD rg_fredet_chk_cycle       : 20;
        FIELD rsv_30                    : 2;


} qp_pma_top_REG_RX_CTRL_5, *Pqp_pma_top_REG_RX_CTRL_5;

typedef struct
{


        FIELD rg_qp_rx_eq_en_h_dly_short : 13;
        FIELD rg_qp_eq_en_dly_short     : 13;
        FIELD rg_p1_to_p0_do_eq_usb     : 1;
        FIELD rg_p2_to_p0_do_eq_usb     : 1;
        FIELD rg_p3_to_p0_do_eq_usb     : 1;
        FIELD rsv_29                    : 3;


} qp_pma_top_REG_RX_CTRL_50, *Pqp_pma_top_REG_RX_CTRL_50;

typedef struct
{


        FIELD rg_fredet_golden_cycle    : 20;
        FIELD rsv_20                    : 12;


} qp_pma_top_REG_RX_CTRL_6, *Pqp_pma_top_REG_RX_CTRL_6;

typedef struct
{


        FIELD rg_fredet_tolerate_cycle  : 20;
        FIELD rsv_20                    : 4;
        FIELD rg_fredet_relck_num       : 4;
        FIELD rg_fredet_clear_unlck_cnt : 1;
        FIELD rsv_29                    : 3;


} qp_pma_top_REG_RX_CTRL_7, *Pqp_pma_top_REG_RX_CTRL_7;

typedef struct
{


        FIELD rg_qp_rx_pi_cal_en_h_dly  : 8;
        FIELD rg_qp_rx_saosc_en_h_dly   : 6;
        FIELD rsv_14                    : 18;


} qp_pma_top_REG_RX_DLY_0, *Pqp_pma_top_REG_RX_DLY_0;

typedef struct
{


        FIELD rg_tdc_ck_stb_timer       : 8;
        FIELD rg_tdc_mst_en             : 1;
        FIELD rsv_9                     : 7;
        FIELD rg_ncpo_ana_msb           : 2;
        FIELD rsv_18                    : 14;


} qp_pma_top_REG_SS_LCPLL_PWCTL_SETTING_2, *Pqp_pma_top_REG_SS_LCPLL_PWCTL_SETTING_2;

typedef struct
{


        FIELD rg_lcpll_ncpo_value       : 31;
        FIELD rsv_31                    : 1;


} qp_pma_top_REG_SS_LCPLL_TDC_FLT_2, *Pqp_pma_top_REG_SS_LCPLL_TDC_FLT_2;

typedef struct
{


        FIELD rg_lcpll_pon_hrdds_pcw_ncpo_gpon : 31;
        FIELD rsv_31                    : 1;


} qp_pma_top_REG_SS_LCPLL_TDC_PCW_1, *Pqp_pma_top_REG_SS_LCPLL_TDC_PCW_1;
#define _RG_PCIE_CLKDRV_IMPSEL 0xf034
#define _RG_QP_BGR_EN 0xf030
#define _RG_QP_CDR_FORCE_IBANDLPF_R_OFF 0xf020
#define _RG_QP_CDR_LPF_MJV_LIM 0xf00c
#define _RG_QP_CDR_PR_CKREF_DIV1 0xf018
#define _RG_QP_CDR_PR_KBAND_DIV_PCIE 0xf01c
#define _RG_QP_PLL_IPLL_DIG_PWR_SEL 0xf03c
#define _RG_QP_PLL_SDM_ORD 0xf040
#define _RG_QP_RXAFE_RESERVE 0xf004
#define _RG_QP_RXLBTX_EN 0xf02c
#define _RG_QP_TDC_FT_CK_EN 0xf038
#define _RG_QP_TX_MODE_16B_EN 0xf028
#define _qp_dig_csr_QP_CK_RST_CTRL_3 0xa30c
#define _qp_dig_csr_QP_CK_RST_CTRL_7 0xa340
#define _qp_pma_top_INTF_CTRL_6 0xe318
#define _qp_pma_top_INTF_CTRL_7 0xe31c
#define _qp_pma_top_INTF_CTRL_8 0xe320
#define _qp_pma_top_INTF_CTRL_9 0xe324
#define _qp_pma_top_INTF_STS_9 0xe364
#define _qp_pma_top_PLL_CK_CTRL_0 0xe414
#define _qp_pma_top_PLL_CK_CTRL_1 0xe418
#define _qp_pma_top_PLL_CK_CTRL_2 0xe41c
#define _qp_pma_top_PLL_CTRL_0 0xe400
#define _qp_pma_top_PLL_CTRL_1 0xe404
#define _qp_pma_top_PLL_CTRL_2 0xe408
#define _qp_pma_top_PLL_CTRL_3 0xe40c
#define _qp_pma_top_PLL_CTRL_4 0xe410
#define _qp_pma_top_PON_RXFEDIG_CTRL_0 0xe100
#define _qp_pma_top_QP_TX_DA_CTRL_0 0xe000
#define _qp_pma_top_QP_TX_DA_CTRL_3 0xe00c
#define _qp_pma_top_RX_CTRL_10 0xe650
#define _qp_pma_top_RX_CTRL_11 0xe654
#define _qp_pma_top_RX_CTRL_2 0xe630
#define _qp_pma_top_RX_CTRL_36 0xe6b8
#define _qp_pma_top_RX_CTRL_45 0xe6dc
#define _qp_pma_top_RX_CTRL_46 0xe6e0
#define _qp_pma_top_RX_CTRL_5 0xe63c
#define _qp_pma_top_RX_CTRL_50 0xe6f0
#define _qp_pma_top_RX_CTRL_6 0xe640
#define _qp_pma_top_RX_CTRL_7 0xe644
#define _qp_pma_top_RX_DLY_0 0xe614
#define _qp_pma_top_SS_LCPLL_PWCTL_SETTING_2 0xe208
#define _qp_pma_top_SS_LCPLL_TDC_FLT_2 0xe230
#define _qp_pma_top_SS_LCPLL_TDC_PCW_1 0xe248
#define QP_ANA_BASE 0x1fa5f000
#define QP_DIG_BASE 0x1fa5a000
#define QP_PMA_BASE 0x1fa5e000
#define QP_ANA_OFFSET 0xf000
#define QP_DIG_OFFSET 0xa000
#define QP_PMA_OFFSET 0xe000
#define SerDes_QP_PCIe_efuse_valid_LSB 32
#define RG_QP_PCIE_TX_TERM_SEL_LSB 67
#define RG_QP_PCIE_RX_IMP_SEL_LSB 69
#endif
