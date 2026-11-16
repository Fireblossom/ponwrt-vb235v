/* SPDX-License-Identifier: GPL-2.0-only */
/* Host-only control-flow model. No kernel execution or hardware emulation. */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef int32_t s32;
typedef int phy_interface_t;
/* CONSTANTS_INSERT */

struct device { void *of_node; };
struct airoha_pcs_priv;
struct airoha_pcs_maps {
    void *pcs_mac, *hsgmii_an, *hsgmii_pcs, *multi_sgmii;
    void *usxgmii_pcs, *hsgmii_rate_adp;
};
struct airoha_pcs_match_data {
    int port_type;
    bool usxgmii_xfi_mode_sel;
    int (*bringup)(struct airoha_pcs_priv *, int, phy_interface_t);
    void (*link_up)(struct airoha_pcs_priv *, int);
    int (*pon_start_rx)(struct airoha_pcs_priv *, int, phy_interface_t);
    int (*pon_retrain_rx)(struct airoha_pcs_priv *, int, phy_interface_t);
    int (*pon_stop_rx)(struct airoha_pcs_priv *, int);
};
struct airoha_pcs_priv {
    struct device *dev;
    const struct airoha_pcs_match_data *data;
    struct airoha_pcs_maps maps[2];
    void *scu, *xfi_rst, *pcs_pma[2];
    int rsts[2];
    u8 pon_mode;
    bool pon_ethernet;
    u32 pon_stage, pon_calibration_runs, pon_eo_fom, pon_eo_gain, pon_eo_peaking;
    int pon_last_error;
};
struct airoha_pcs_port {
    struct airoha_pcs_priv *priv;
    int index;
    phy_interface_t interface;
};
struct phylink_pcs { struct airoha_pcs_port *port; };
struct phylink_link_state { phy_interface_t interface; bool link; };
struct airoha_pcs_pon_rx_status {
    bool signal_detected, freqdet_locked, rx_ready_gate, rx_fifo_reset_released;
    u32 rx_mode_raw, frequency_level, frequency_target;
    u32 calibration_stage, calibration_runs, eo_fom, eo_gain, eo_peaking;
    int calibration_error;
};
struct an7583_pcs_pon_rate { u8 txpll, tx, rx, ana, preset; };
static struct airoha_pcs_port *to_airoha_pcs_port(struct phylink_pcs *pcs)
{ return pcs->port; }

struct access { uintptr_t object; u32 op, reg, mask, value; };
static struct access trace[1024];
static unsigned int trace_count;
static int injected_error;
static bool property_present, compatible = true;
static int property_count = 1, property_error;
static const char *property_value = "usxgmii";
static int record(u32 op, void *object, u32 reg, u32 mask, u32 value)
{
    assert(trace_count < 1024);
    trace[trace_count++] = (struct access){(uintptr_t)object, op, reg, mask, value};
    return injected_error;
}
static int regmap_write(void *m, u32 r, u32 v) { return record(1,m,r,0,v); }
static int regmap_update_bits(void *m, u32 r, u32 k, u32 v) { return record(2,m,r,k,v); }
static int regmap_set_bits(void *m, u32 r, u32 k) { return record(3,m,r,k,k); }
static int regmap_clear_bits(void *m, u32 r, u32 k) { return record(4,m,r,k,0); }
static int regmap_read(void *m, u32 r, u32 *v) { *v=0; return record(5,m,r,0,0); }
static int reset_control_assert(void *r) { return record(6,r,0,0,0); }
static int reset_control_deassert(void *r) { return record(7,r,0,0,0); }
static int reset_control_bulk_assert(unsigned int n, void *r) { return record(8,(void *)(uintptr_t)n,0,0,0); }
static int reset_control_bulk_deassert(unsigned int n, void *r) { return record(9,(void *)(uintptr_t)n,0,0,0); }
static void usleep_range(unsigned int a, unsigned int b) { record(10,0,a,b,0); }
static void udelay(unsigned int a) { record(11,0,a,0,0); }
static int backend_bringup(struct airoha_pcs_priv *p, int i, phy_interface_t f)
{ return record(12,0,i,f,0); }
static void backend_link_up(struct airoha_pcs_priv *p, int i) { record(13,0,i,0,0); }
static int backend_rx(struct airoha_pcs_priv *p, int i, phy_interface_t f)
{ return record(14,0,i,f,0); }
static int backend_stop(struct airoha_pcs_priv *p, int i) { return record(15,0,i,0,0); }
static bool device_is_compatible(struct device *d, const char *s) { return compatible; }
static bool of_property_present(void *n, const char *s)
{ assert(!strcmp(s,"airoha,pon-ethernet-mode")); return property_present; }
static int of_property_count_strings(void *n, const char *s)
{ assert(!strcmp(s,"airoha,pon-ethernet-mode")); return property_count; }
static int of_property_read_string(void *n, const char *s, const char **v)
{ assert(!strcmp(s,"airoha,pon-ethernet-mode")); *v=property_value; return property_error; }
#define dev_err_probe(d,e,...) (e)
#define dev_dbg(...) ((void)0)
#define dev_info(...) ((void)0)
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define READ_ONCE(a) (a)
#define BIT(n) (1U << (n))
#define GENMASK(h,l) ((u32)((~0ULL << (l)) & (~0ULL >> (63-(h)))))
#define FIELD_PREP(m,v) (((u32)(v) << __builtin_ctz((u32)(m))) & (m))
#define FIELD_PREP_CONST(m,v) FIELD_PREP(m,v)
#define FIELD_GET(m,v) (((v) & (m)) >> __builtin_ctz((u32)(m)))
#define phylink_get_link_timer_ns(...) 1000
#define phylink_mii_c22_pcs_encode_advertisement(...) 1
#define airoha_pcs_setup_scu_eth(...) record(20,0,0,0,0)
#define an7581_pcs_setup_scu_pcie(...) record(21,0,0,0,0)
#define an7583_pcs_setup_scu_pcie(...) record(22,0,0,0,0)
#define airoha_pcs_init(...) record(23,0,0,0,0)
#define airoha_pcs_interrupt_init(...) record(24,0,0,0,0)
#define airoha_pcs_get_state_sgmii(...) record(25,0,0,0,0)
#define airoha_pcs_get_state_hsgmii(...) record(26,0,0,0,0)
#define airoha_pcs_get_state_usxgmii(...) record(27,0,0,0,0)
#define airoha_pcs_get_state_10gbaser(...) record(28,0,0,0,0)

/* FUNCTIONS_INSERT */

struct outcome {
    int ret;
    u8 mode;
    int interface;
    bool link;
    struct airoha_pcs_pon_rx_status status;
};
static struct outcome invoke(unsigned int which, bool old, bool ethernet,
                             phy_interface_t interface, unsigned int neg)
{
    struct airoha_pcs_match_data data = { .port_type=AIROHA_PCS_PON,
        .usxgmii_xfi_mode_sel=true, .bringup=backend_bringup, .link_up=backend_link_up,
        .pon_start_rx=backend_rx, .pon_retrain_rx=backend_rx, .pon_stop_rx=backend_stop };
    struct airoha_pcs_priv priv = {.data=&data, .pon_ethernet=ethernet,
        .pon_mode=ethernet ? AIROHA_PCS_PON_MODE_EPON_10G_10G : AIROHA_PCS_PON_MODE_GPON};
    struct airoha_pcs_port port = {.priv=&priv, .interface=interface};
    struct phylink_pcs pcs = {&port};
    struct phylink_link_state state = {.interface=interface,.link=true};
    struct outcome result = {0};
    unsigned long advertising = 0;
#define RUN_VOID(name,...) do { if(old) ref_##name(__VA_ARGS__); else name(__VA_ARGS__); } while(0)
#define RUN_INT(name,...) do { result.ret=old ? ref_##name(__VA_ARGS__) : name(__VA_ARGS__); } while(0)
    trace_count=0;
    switch(which) {
    case 0: RUN_VOID(airoha_pcs_pre_config,&pcs,interface); break;
    case 1: RUN_INT(airoha_pcs_post_config,&pcs,interface); break;
    case 2: RUN_INT(airoha_pcs_config,&pcs,neg,interface,&advertising,false); break;
    case 3: RUN_INT(airoha_pcs_inband_caps,&pcs,interface); break;
    case 4: RUN_VOID(airoha_pcs_an_restart,&pcs); break;
    case 5: RUN_VOID(airoha_pcs_get_state,&pcs,neg,&state); break;
    case 6: RUN_VOID(airoha_pcs_link_up,&pcs,neg,interface,SPEED_1000,DUPLEX_FULL); break;
    case 7: RUN_VOID(airoha_pcs_link_down,&pcs); break;
    case 8: RUN_INT(airoha_pcs_setup_scu,&priv,0,interface); break;
    case 9: RUN_INT(airoha_pcs_pon_config_rx,&pcs,AIROHA_PCS_PON_MODE_EPON_10G_10G,0,0); break;
    case 10: RUN_INT(airoha_pcs_pon_retrain_rx,&pcs); break;
    case 11: RUN_INT(airoha_pcs_pon_stop_rx,&pcs); break;
    case 12: RUN_INT(airoha_pcs_pon_get_rx_status,&pcs,&result.status); break;
    default: assert(false);
    }
    result.mode=priv.pon_mode; result.interface=port.interface; result.link=state.link;
    return result;
}

int main(void)
{
    const phy_interface_t modes[] = {PHY_INTERFACE_MODE_NA,PHY_INTERFACE_MODE_SGMII,
        PHY_INTERFACE_MODE_1000BASEX,PHY_INTERFACE_MODE_2500BASEX,
        PHY_INTERFACE_MODE_USXGMII,PHY_INTERFACE_MODE_10GBASER,PHY_INTERFACE_MODE_INTERNAL};
    const unsigned int negotiation[] = {PHYLINK_PCS_NEG_OUTBAND,
        PHYLINK_PCS_NEG_INBAND_DISABLED,PHYLINK_PCS_NEG_INBAND_ENABLED};
    unsigned int defaults=0, invalid=0, optical=0, profiles=0, valid=0, m,n,w,e;
    struct access saved[1024];
    for(e=0;e<2;e++) for(m=0;m<ARRAY_SIZE(modes);m++) for(n=0;n<3;n++) for(w=0;w<13;w++) {
        injected_error=e ? -EIO : 0;
        struct outcome a=invoke(w,true,false,modes[m],negotiation[n]);
        unsigned int count=trace_count;
        memcpy(saved,trace,count*sizeof(*trace));
        struct outcome b=invoke(w,false,false,modes[m],negotiation[n]);
        assert(count==trace_count && !memcmp(saved,trace,count*sizeof(*trace)));
        assert(a.ret==b.ret && a.mode==b.mode && a.interface==b.interface && a.link==b.link);
        assert(!memcmp(&a.status,&b.status,sizeof(a.status)));
        defaults++;
    }
    injected_error=0;
    for(m=0;m<ARRAY_SIZE(modes);m++) if(modes[m]!=PHY_INTERFACE_MODE_USXGMII)
        for(w=0;w<13;w++) {
            struct outcome r=invoke(w,false,true,modes[m],PHYLINK_PCS_NEG_INBAND_ENABLED);
            assert(!trace_count);
            if(w>=9) assert(r.ret==-EOPNOTSUPP);
            if(w==1 || w==2 || w==8) assert(r.ret==-EINVAL);
            if(w==3) assert(!r.ret);
            if(w==5) assert(!r.link);
            invalid++;
        }
    for(w=9;w<13;w++) {
        struct outcome r=invoke(w,false,true,PHY_INTERFACE_MODE_USXGMII,PHYLINK_PCS_NEG_INBAND_ENABLED);
        assert(r.ret==-EOPNOTSUPP && !trace_count); optical++;
    }
    for(w=0;w<9;w++) {
        struct outcome r=invoke(w,false,true,PHY_INTERFACE_MODE_USXGMII,0);
        assert(r.ret>=0 && r.mode==AIROHA_PCS_PON_MODE_EPON_10G_10G);
        valid++;
    }
    for(w=0;w<2;w++) {
        struct outcome r=invoke(w ? 8 : 0,false,true,PHY_INTERFACE_MODE_USXGMII,0);
        bool found=false;
        for(n=0;n<trace_count;n++) if(trace[n].op==2 && trace[n].reg==AIROHA_SCU_WAN_CONF)
            found=(trace[n].value & 0xff)==0x12;
        assert(!r.ret && found);
    }
    for(w=0;w<8;w++) {
        struct device dev={0};
        struct airoha_pcs_priv p={.dev=&dev};
        property_present=w!=0; compatible=w!=2 && w!=0; property_count=w==3 ? 2 : w==4 ? 0 : 1;
        property_error=w==5 ? -EINVAL : 0;
        property_value=w==6 ? "unsupported" : w==7 ? "" : "usxgmii";
        trace_count=0;
        int ret=airoha_pcs_parse_pon_ethernet(&p);
        assert(!trace_count);
        if(w==0) assert(!ret && !p.pon_ethernet && p.pon_mode==AIROHA_PCS_PON_MODE_GPON);
        else if(w==1) {
            assert(!ret && p.pon_ethernet && p.pon_mode==AIROHA_PCS_PON_MODE_EPON_10G_10G);
            const struct an7583_pcs_pon_rate *rate=an7583_pcs_pon_rate(&p);
            assert(rate->txpll==1 && rate->tx==1 && rate->rx==1 && rate->ana==1 && rate->preset==1);
        } else assert(ret==-EINVAL && !p.pon_ethernet);
        profiles++;
    }
    printf("{\"default_comparisons\":%u,\"invalid_interface_no_access_cases\":%u,"
           "\"optical_api_no_access_cases\":%u,\"profile_parse_cases\":%u,"
           "\"valid_profile_entry_cases\":%u,\"usxgmii_wan_route_checks\":2}\n",
           defaults,invalid,optical,profiles,valid);
    return 0;
}
