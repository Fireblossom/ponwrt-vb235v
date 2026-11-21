/* SPDX-License-Identifier: GPL-2.0-only WITH Linux-syscall-note */
#ifndef PONWRT_DSL_UAPI_H
#define PONWRT_DSL_UAPI_H
#include <linux/types.h>
#include <linux/ioctl.h>
#define PNDSL_ABI 1
#define PNDSL_PROFILE "vb235v-dsl-exclusive-v1"
#define PNDSL_F_BOARD_VERIFIED 1u
#define PNDSL_F_OWNER_PRESENT 2u
#define PNDSL_F_CLAIMED 4u
#define PNDSL_F_RAW_READ_SAFE 8u
#define PNDSL_F_PEER_VERIFIED 16u
#define PNDSL_F_ROM_TAIL_VERIFIED 32u
struct pndsl_query { __u32 abi,flags,ifindex,reserved; char profile[48]; __u8 peer[6],pad[2]; };
struct pndsl_claim { __u32 abi,sizes[3]; __u8 sha256[3][32]; __u64 generation; char profile[48]; };
struct pndsl_word { __u32 address,value; };
struct pndsl_raw { __u32 reg,value; };
#define PNDSL_QUERY _IOR('D',0,struct pndsl_query)
#define PNDSL_CLAIM _IOW('D',1,struct pndsl_claim)
#define PNDSL_RELEASE _IO('D',2)
#define PNDSL_RESET _IOW('D',3,__u32)
#define PNDSL_READ32 _IOWR('D',4,struct pndsl_word)
#define PNDSL_WRITE32 _IOW('D',5,struct pndsl_word)
#define PNDSL_RAW_READ _IOWR('D',6,struct pndsl_raw)
#endif
