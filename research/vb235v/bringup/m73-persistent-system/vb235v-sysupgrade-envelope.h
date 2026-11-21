/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef VB235V_SYSUPGRADE_ENVELOPE_H
#define VB235V_SYSUPGRADE_ENVELOPE_H

/* Read-only fwtool framing inspector. Caller supplies U-Boot u8/u32, errno,
 * memset and crc32(). CRC is corruption detection, never authentication.
 * JSON semantics, board admission, FIT/rootfs validation and signature
 * verification are separate requirements. This function grants no writes.
 */
struct vb_sysupgrade_envelope {
 size_t payload_bytes;
 size_t metadata_offset;
 size_t metadata_bytes;
 size_t signature_offset;
 size_t signature_bytes;
};

static u32 vb_su_be32(const u8 *p)
{
 return ((u32)p[0] << 24) | ((u32)p[1] << 16) |
        ((u32)p[2] << 8) | (u32)p[3];
}

static int vb_sysupgrade_envelope_inspect(const u8 *image, size_t length,
                                         struct vb_sysupgrade_envelope *out)
{
 struct vb_sysupgrade_envelope value;
 size_t cursor = length;
 unsigned int layers = 0;
 int have_metadata = 0, have_signature = 0;

 if (!out)
  return -EINVAL;
 memset(out, 0, sizeof(*out));
 memset(&value, 0, sizeof(value));
 if (!image || length < 25 || length > 0x5000000)
  return -EINVAL;

 while (cursor >= 16) {
  const u8 *tr = image + cursor - 16;
  size_t size, start, data_bytes;
  u32 type;

  if (vb_su_be32(tr) != 0x46577830)
   break;
  if (++layers > 2)
   return -EBADMSG;
  size = vb_su_be32(tr + 12);
  if (size < 16 || size > cursor || tr[9] || tr[10] || tr[11])
   return -EBADMSG;
  if (vb_su_be32(tr + 4) != (u32)~crc32(0, image, cursor - 16))
   return -EBADMSG;
  start = cursor - size;
  data_bytes = size - 16;
  type = tr[8];
  if (type == 0) {
   /* Upstream appends the opaque signature after metadata. */
   if (have_signature || have_metadata || !data_bytes || data_bytes > 1024)
    return -EBADMSG;
   have_signature = 1;
   value.signature_offset = start;
   value.signature_bytes = data_bytes;
  } else if (type == 1) {
   if (have_metadata || data_bytes <= 8 || data_bytes > 8 + 30 * 1024)
    return -EBADMSG;
   /* Version and reserved flags are zero in the supported format. */
   if (vb_su_be32(image + start) || vb_su_be32(image + start + 4))
    return -EBADMSG;
   have_metadata = 1;
   value.metadata_offset = start + 8;
   value.metadata_bytes = data_bytes - 8;
  } else {
   return -EOPNOTSUPP;
  }
  cursor = start;
 }
 if (!have_metadata)
  return -EBADMSG;
 value.payload_bytes = cursor;
 *out = value;
 return 0;
}
#endif
