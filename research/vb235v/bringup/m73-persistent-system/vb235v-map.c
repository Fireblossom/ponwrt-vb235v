// SPDX-License-Identifier: GPL-2.0-only
/* Bounded decoder for the observed VB235v factory BBT/BMT-v1 format.
 * No reconstruction, repair, bad-block marking or flash writes occur here.
 */
#include <linux/errno.h>
#include <linux/string.h>
#include "vb235v-map.h"

static u16 le16(const u8 *p)
{
	return p[0] | ((u16)p[1] << 8);
}

int vb_decode_bbt(struct vb_map *m, const u8 *p, size_t n)
{
	u16 sum;
	unsigned int i;

	if (!m || !p || n < 512 || memcmp(p, "RAWB", 4) || p[8] != 1 || p[9] > 250)
		return -EINVAL;
	sum = p[8] + p[9];
	for (i = 12; i < 512; i++)
		sum += p[i];
	if (p[4] != (sum & 255) || p[5] != (sum >> 8) || p[6] || p[7])
		return -EBADMSG;
	for (i = 0; i < p[9]; i++) {
		u16 value = le16(p + 12 + 2 * i);

		if (value >= VB_BLOCKS - VB_POOL || (i && value <= le16(p + 10 + 2 * i)))
			return -EINVAL;
	}
	m->initial_count = p[9];
	for (i = 0; i < p[9]; i++)
		m->initial_bad[i] = le16(p + 12 + 2 * i);
	return 0;
}

int vb_decode_bmt(struct vb_map *m, const u8 *p, size_t n)
{
	unsigned int i, j;
	u8 sum;

	if (!m || !p || n < 20 + VB_POOL * 4 || memcmp(p, "BMT", 3) ||
	    p[3] != 1 || p[5] > VB_POOL)
		return -EINVAL;
	sum = p[3] + p[5];
	for (i = 20; i < 20 + VB_POOL * 4; i++)
		sum += p[i];
	if (sum != p[6])
		return -EBADMSG;
	for (i = 0; i < p[5]; i++) {
		u16 bad = le16(p + 20 + 4 * i);
		u16 replacement = le16(p + 22 + 4 * i);

		if (bad >= VB_BLOCKS - VB_POOL || replacement < VB_BLOCKS - VB_POOL ||
		    replacement >= VB_BLOCKS)
			return -EINVAL;
		for (j = 0; j < i; j++)
			if (bad == le16(p + 20 + 4 * j) || replacement == le16(p + 22 + 4 * j))
				return -EINVAL;
	}
	m->mapped_count = p[5];
	for (i = 0; i < p[5]; i++) {
		m->bad[i] = le16(p + 20 + 4 * i);
		m->replacement[i] = le16(p + 22 + 4 * i);
	}
	return 0;
}

int vb_map_finish(struct vb_map *m)
{
	bool used[VB_BLOCKS] = { false };
	u16 i, j, physical;

	if (!m)
		return -EINVAL;
	m->valid = false;
	if (m->bbt_block < VB_BLOCKS - VB_POOL || m->bbt_block >= VB_BLOCKS ||
	    m->bmt_block < VB_BLOCKS - VB_POOL || m->bmt_block >= VB_BLOCKS ||
	    m->bmt_block == m->bbt_block || m->initial_count > 250 || m->mapped_count > VB_POOL)
		return -EINVAL;
	for (i = 0; i < m->mapped_count; i++) {
		if (m->replacement[i] == m->bmt_block || m->replacement[i] == m->bbt_block)
			return -EINVAL;
		for (j = 0; j < m->initial_count; j++)
			if (m->bad[i] == m->initial_bad[j])
				return -EINVAL;
	}
	m->logical_blocks = VB_BLOCKS - VB_POOL - m->initial_count;
	for (i = 0; i < m->logical_blocks; i++) {
		physical = i;
		for (j = 0; j < m->initial_count; j++)
			if (physical >= m->initial_bad[j])
				physical++;
		for (j = 0; j < m->mapped_count; j++)
			if (physical == m->bad[j]) {
				physical = m->replacement[j];
				break;
			}
		if (physical >= VB_BLOCKS || used[physical])
			return -EINVAL;
		used[physical] = true;
		m->physical[i] = physical;
	}
	m->valid = true;
	return 0;
}

int vb_map_load(struct vb_map *m, vb_read_page read_page, void *context)
{
	u8 page[VB_PAGE];
	int block;
	bool found_bbt = false, found_bmt = false;

	if (!m || !read_page)
		return -EINVAL;
	memset(m, 0, sizeof(*m));
	/* Factory BBT chooses the first valid record from the pool start. */
	for (block = VB_BLOCKS - VB_POOL; block < VB_BLOCKS; block++) {
		if (read_page(context, block, page))
			continue;
		if (!vb_decode_bbt(m, page, sizeof(page))) {
			m->bbt_block = block;
			found_bbt = true;
			break;
		}
	}
	/* Factory BMT chooses the first valid record from the pool end. */
	for (block = VB_BLOCKS - 1; block >= VB_BLOCKS - VB_POOL; block--) {
		if (read_page(context, block, page))
			continue;
		if (!vb_decode_bmt(m, page, sizeof(page))) {
			m->bmt_block = block;
			found_bmt = true;
			break;
		}
	}
	if (!found_bbt || !found_bmt)
		return -ENOENT;
	return vb_map_finish(m);
}

int vb_translate(const struct vb_map *m, u32 logical, u32 *physical)
{
	u32 block = logical / VB_ERASE;

	if (!m || !physical || !m->valid || logical >= VB_LIMIT || block >= m->logical_blocks)
		return -EINVAL;
	*physical = (u32)m->physical[block] * VB_ERASE + logical % VB_ERASE;
	return 0;
}
