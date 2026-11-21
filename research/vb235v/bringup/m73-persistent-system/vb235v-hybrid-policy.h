/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef VB235V_HYBRID_POLICY_H
#define VB235V_HYBRID_POLICY_H
#include <linux/types.h>
#include <linux/errno.h>
/* Physical addresses are allowed only after the complete slot1 map has
 * been admitted as identity. Never apply this to a compacted/remapped view. */
#define VB_HYBRID_START 0x05c80000ULL
#define VB_HYBRID_BYTES 0x04fc0000ULL
#define VB_HYBRID_END (VB_HYBRID_START + VB_HYBRID_BYTES)
#define VB_HYBRID_ERASE 0x40000ULL
#define VB_HYBRID_PAGE 4096ULL
#define VB_HYBRID_SCRATCH (VB_HYBRID_END - VB_HYBRID_ERASE)
enum vb_hybrid_op { VB_HYBRID_PROGRAM, VB_HYBRID_ERASE_OP, VB_HYBRID_RETIRE };
struct vb_hybrid_policy {
 bool identity_verified;
 bool writes_admitted;
 bool scratch_only;
 bool retirement_admitted;
 bool ubi_test_only;
};
static inline int vb_hybrid_check(const struct vb_hybrid_policy *p,
                                 enum vb_hybrid_op op, u64 from, u64 bytes)
{
 u64 alignment, start;
 if (!p || !p->identity_verified || !p->writes_admitted)
  return -EROFS;
 if (p->scratch_only && p->ubi_test_only)
  return -EINVAL;
 start = p->ubi_test_only ? VB_HYBRID_END - 0x800000 :
         (p->scratch_only ? VB_HYBRID_SCRATCH : VB_HYBRID_START);
 if (!bytes || from < start || from >= VB_HYBRID_END || bytes > VB_HYBRID_END - from)
  return -ERANGE;
 if (op == VB_HYBRID_PROGRAM)
  alignment = VB_HYBRID_PAGE;
 else if (op == VB_HYBRID_ERASE_OP)
  alignment = VB_HYBRID_ERASE;
 else if (op == VB_HYBRID_RETIRE) {
  if (!p->retirement_admitted || p->ubi_test_only)
   return -EROFS;
  if (bytes != VB_HYBRID_ERASE)
   return -EINVAL;
  alignment = VB_HYBRID_ERASE;
 } else
  return -EINVAL;
 return (from % alignment || bytes % alignment) ? -EINVAL : 0;
}
static inline int vb_hybrid_runtime_marker(const struct vb_hybrid_policy *p,
                                           u64 block_offset, u8 marker[2])
{
 int ret;
 if (!marker)
  return -EINVAL;
 ret = vb_hybrid_check(p, VB_HYBRID_RETIRE, block_offset, VB_HYBRID_ERASE);
 if (ret)
  return ret;
 /* Keep factory-initial marker byte zero erased. Program runtime byte one.
  * Caller must use a RAW first-page OOB operation and verify readback. */
 marker[0] = 0xff;
 marker[1] = 0x00;
 return 0;
}
#endif
