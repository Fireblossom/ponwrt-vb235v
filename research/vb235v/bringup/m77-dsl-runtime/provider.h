/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef PONWRT_DSL_PROVIDER_H
#define PONWRT_DSL_PROVIDER_H
#include "core.h"
#include "provider_uapi.h"
struct dsl_provider { int fd; bool claimed; struct pndsl_query query; };
int dsl_provider_open(struct dsl_provider *);
int dsl_provider_claim(struct dsl_provider *,const struct pndsl_claim *,struct dsl_hw *);
int dsl_provider_release(struct dsl_provider *);
/* Actual raw transport is unreachable without claimed, measured peer/tail capabilities. */
int dsl_rom_serve(struct dsl_provider *,struct dsl_rom_session *,unsigned timeout_ms);
#endif
