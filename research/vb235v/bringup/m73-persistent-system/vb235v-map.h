/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef VB235V_MAP_H
#define VB235V_MAP_H
#include <linux/types.h>
#define VB_BLOCKS 2048
#define VB_POOL 163
#define VB_PAGE 4096
#define VB_ERASE 0x40000
#define VB_LIMIT 0xc680000
struct vb_map {
	u16 physical[VB_BLOCKS];
	u16 initial_bad[250];
	u16 bad[250], replacement[250];
	u16 bbt_block, bmt_block, logical_blocks;
	u8 initial_count, mapped_count;
	bool valid;
};
typedef int (*vb_read_page)(void *context, u16 block, u8 *page);
int vb_decode_bbt(struct vb_map *map, const u8 *page, size_t length);
int vb_decode_bmt(struct vb_map *map, const u8 *page, size_t length);
int vb_map_finish(struct vb_map *map);
int vb_map_load(struct vb_map *map, vb_read_page read_page, void *context);
int vb_translate(const struct vb_map *map, u32 logical, u32 *physical);
#endif
