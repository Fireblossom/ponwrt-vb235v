/* SPDX-License-Identifier: GPL-2.0-only */
/* Selected actual C functions run only against these in-memory backends. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;
typedef uint32_t u32;
#define BIT(n) (1U << (n))
#define GENMASK(h,l) ((~0U << (l)) & (~0U >> (31 - (h))))
#define FIELD_PREP(m,v) (((u32)(v) << __builtin_ctz((u32)(m))) & (u32)(m))
#define FIELD_PREP_CONST(m,v) FIELD_PREP(m,v)
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define LAB_PRINT_PON 0
/* @DEFINITIONS@ */
struct regmap { u32 base; };
struct airoha_pcs_match_data { int port_type; };
struct airoha_pcs_priv {
 const struct airoha_pcs_match_data *data;
 struct regmap *pcs_pma[2], *pcs_ana;
 u8 pon_mode;
 bool pon_ethernet;
};
struct an7583_pcs_pon_rate { u8 txpll, tx, rx, ana, preset; };
struct event { char op; u32 address, mask, value; };
struct cell { u32 address, value; };
static struct event events[512];
static struct cell memory[256];
static unsigned int event_count, cell_count;
static u32 seed;
static u32 *location(u32 address) {
 unsigned int i;
 for (i=0;i<cell_count;i++) if (memory[i].address==address) return &memory[i].value;
 assert(cell_count < ARRAY_SIZE(memory));
 memory[cell_count]=(struct cell){address, seed ^ (address * 2654435761U)};
 return &memory[cell_count++].value;
}
static void record(char op,u32 address,u32 mask,u32 value) {
 assert(event_count < ARRAY_SIZE(events));
 events[event_count++]=(struct event){op,address,mask,value};
}
static void reset(u32 pattern) { event_count=cell_count=0; seed=pattern; }
static bool trace_equal(const struct event *a,const struct event *b,unsigned int count) {
 unsigned int i;
 for (i=0;i<count;i++) if (a[i].op!=b[i].op || a[i].address!=b[i].address ||
  a[i].mask!=b[i].mask || a[i].value!=b[i].value) return false;
 return true;
}
static int update(struct regmap *map,u32 reg,u32 mask,u32 value,char op) {
 u32 *p=location(map->base+reg);
 *p=(*p & ~mask) | (value & mask);
 record(op,map->base+reg,mask,value & mask);
 return 0;
}
static int regmap_update_bits(struct regmap *m,u32 r,u32 mask,u32 v) {return update(m,r,mask,v,'U');}
static int regmap_write_bits(struct regmap *m,u32 r,u32 mask,u32 v) {return update(m,r,mask,v,'F');}
static int regmap_set_bits(struct regmap *m,u32 r,u32 mask) {return update(m,r,mask,mask,'S');}
static int regmap_clear_bits(struct regmap *m,u32 r,u32 mask) {return update(m,r,mask,0,'C');}
static int regmap_write(struct regmap *m,u32 r,u32 v) {return update(m,r,~0U,v,'W');}
static void udelay(unsigned int n) {record('D',0,n,n);}
static void usleep_range(unsigned int a,unsigned int b) {record('D',0,a,b);}
static void vendor_field(u32 address,unsigned int high,unsigned int low,u32 value) {
 struct regmap map={0};
 assert(low<=high && high<32);
 update(&map,address,GENMASK(high,low),value << low,'F');
}
#define IO_SPHYA_REG_BITS(a,h,l,v) vendor_field((a),(h),(l),(v))
/* @BACKENDS@ */
/* @FUNCTIONS@ */
/* @EXPECTATIONS@ */

int main(void) {
 struct regmap pma[2]={{0x1fa8e000U},{0x1fa7e000U}}, ana={0x1fa8f000U};
 struct airoha_pcs_match_data data={0};
 struct airoha_pcs_priv priv={&data,{&pma[0],&pma[1]},&ana,0,false};
 const int ports[]={AIROHA_PCS_ETH,AIROHA_PCS_PON,AIROHA_PCS_USB,AIROHA_PCS_PCIE};
 const phy_interface_t modes[]={PHY_INTERFACE_MODE_NA,PHY_INTERFACE_MODE_SGMII,
  PHY_INTERFACE_MODE_1000BASEX,PHY_INTERFACE_MODE_2500BASEX,PHY_INTERFACE_MODE_5GBASER,
  PHY_INTERFACE_MODE_10GBASER,PHY_INTERFACE_MODE_USXGMII};
 const u32 patterns[]={0,~0U,0x12345678U};
 struct event reference[512]; unsigned int count, rx=0, plug=0;
 unsigned int p,m,r,i,j;
 for (p=0;p<ARRAY_SIZE(ports);p++) for (m=0;m<ARRAY_SIZE(modes);m++)
 for (r=0;r<ARRAY_SIZE(an7583_pcs_pon_rates);r++) for (i=0;i<2;i++)
 for (j=0;j<ARRAY_SIZE(patterns);j++) {
  data.port_type=ports[p]; priv.pon_mode=r; priv.pon_ethernet=false;
  reset(patterns[j]); ref_rx(&priv,i,modes[m]); count=event_count;
  memcpy(reference,events,count*sizeof(events[0]));
  reset(patterns[j]); an7583_pcs_common_phya_rx(&priv,i,modes[m]);
  assert(count==event_count && trace_equal(reference,events,count)); rx++;
  reset(patterns[j]); ref_first_plug(&priv,i,modes[m]); count=event_count;
  memcpy(reference,events,count*sizeof(events[0]));
  reset(patterns[j]); an7583_pcs_first_plug_in(&priv,i,modes[m]);
  assert(count==event_count && trace_equal(reference,events,count)); plug++;
 }
 data.port_type=AIROHA_PCS_PON; priv.pon_mode=AIROHA_PCS_PON_MODE_EPON_10G_10G; priv.pon_ethernet=true;
 for (j=0;j<ARRAY_SIZE(patterns);j++) {
  reset(patterns[j]); XPON_DIG_reset(); count=event_count;
  memcpy(reference,events,count*sizeof(events[0])); assert(count==15);
  reset(patterns[j]); an7583_pcs_pon_eth_dig_reset(&priv,0);
  assert(count==event_count && trace_equal(reference,events,count));
  reset(patterns[j]); an7583_pcs_common_phya_rx(&priv,0,PHY_INTERFACE_MODE_USXGMII);
  check_vendor_clocks();
  reset(patterns[j]); an7583_pcs_first_plug_in(&priv,0,PHY_INTERFACE_MODE_USXGMII);
  unsigned int off=0,on=0,eye=0,forced=0,delay=0;
  for (i=0;i<event_count;i++) {
   off += events[i].op=='B' && events[i].address==TDC_OFF_ID;
   on += events[i].op=='B' && events[i].address==TDC_ON_ID;
   eye += events[i].op=='B' && events[i].address==EO_SCAN_ID;
   forced += events[i].op=='F';
   delay += events[i].op=='D' && events[i].mask==10 && events[i].value==10;
  }
  assert(off==1 && on==0 && eye==1 && forced==14 && delay==1);
 }
 printf("{\"default_rx_traces_equal\":%u,\"default_first_plug_traces_equal\":%u,"
        "\"vendor_reset_trace_cases\":%u,\"ethernet_clock_and_call_policy_cases\":%u}\n",
        rx,plug,(unsigned int)ARRAY_SIZE(patterns),(unsigned int)ARRAY_SIZE(patterns));
 return 0;
}
