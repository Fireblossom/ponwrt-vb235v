/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef PONWRT_DSL_OWNER_H
#define PONWRT_DSL_OWNER_H
#include <linux/device.h>
#include <linux/module.h>
/* A board/Ethernet owner must quiesce DMA/NAPI/IRQ/phylink and verify actual
 * mux/clock/reset/pin mode. No implementation or default owner is supplied. */
struct pndsl_owner_ops {
 struct module *module;
 const char *profile;
 int (*claim)(struct device *,unsigned int *ifindex,u8 peer[6]);
 int (*release)(struct device *);
};
int ponwrt_dsl_owner_register(struct device *,const struct pndsl_owner_ops *);
int ponwrt_dsl_owner_unregister(struct device *);
#endif
