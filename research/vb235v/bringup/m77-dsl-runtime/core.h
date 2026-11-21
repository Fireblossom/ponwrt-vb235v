/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef PONWRT_DSL_CORE_H
#define PONWRT_DSL_CORE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define DSL_ROM_BLOCK 1400u
#define DSL_ROM_HEADER 32u
#define DSL_ROM_CAPACITY (DSL_ROM_HEADER + DSL_ROM_BLOCK + 2u)
enum dsl_result {
 DSL_OK=0, DSL_E_ARGUMENT=-1, DSL_E_IO=-2, DSL_E_TIMEOUT=-3,
 DSL_E_CANCEL=-4, DSL_E_FRAME=-5, DSL_E_CHECKSUM=-6,
 DSL_E_SEQUENCE=-7, DSL_E_FIRMWARE=-8, DSL_E_OWNER=-9,
 DSL_BLOCK_INIC_TRAILER=-20, DSL_BLOCK_EXEC_ACK=-21,
 DSL_BLOCK_ROM_TAIL=-22, DSL_E_CRC=-23
};
const char *dsl_code(int result);
struct dsl_hw {
 void *ctx;
 /* All three gates are set only after the native provider CLAIM succeeds. */
 bool exclusive, profile_verified, inputs_verified;
 int (*read32)(void *, uint32_t, uint32_t *);
 int (*write32)(void *, uint32_t, uint32_t);
 int (*reset)(void *, bool);
 uint64_t (*now_ms)(void *);
 int (*wait_ms)(void *, unsigned);
 bool (*cancelled)(void *);
};
struct dsl_c22 {
 void *ctx;
 int (*read)(void *, unsigned reg, uint16_t *);
 int (*write)(void *, unsigned reg, uint16_t);
};
/* Caller must hold one bus lock across each complete bridge operation. */
int dsl_bridge_write32(struct dsl_c22 *, uint32_t, uint32_t);
int dsl_bridge_read32(struct dsl_c22 *, uint32_t, uint32_t *);
int dsl_endpoint_prepare(struct dsl_hw *);
int dsl_ddr_load(struct dsl_hw *, const uint8_t *, size_t);
/* Confirmed segments only. Never emits the unresolved CONF/MAC trailer/INDN. */
int dsl_inic_load_known(struct dsl_hw *, const uint8_t *, size_t);

uint16_t dsl_checksum(const uint8_t *, size_t);
uint16_t dsl_file_checksum(const uint8_t *, size_t);
struct dsl_rom_fields { uint16_t op, seq, file_sum, arg5; uint32_t arg6, arg7; };
/* Tail bytes are an explicit input: caller cannot silently infer them. */
int dsl_rom_encode(uint8_t *, size_t, const struct dsl_rom_fields *,
                   const uint8_t *, size_t, const uint8_t tail[2], size_t *);
struct dsl_rom_packet { uint16_t op, seq; const uint8_t *data; size_t length; };
int dsl_rom_decode(const uint8_t *, size_t, struct dsl_rom_packet *);
int dsl_rom_decode_ethernet(const uint8_t *,size_t,const uint8_t src[6],
                           const uint8_t dst[6],struct dsl_rom_packet *);
struct dsl_rom_session {
 const uint8_t *file; size_t file_len, last_len;
 uint16_t file_sum, last_seq, last_ack;
 unsigned phase; /* 0 notify, 1 RRQ, 2 ACK, 3 transfer complete/execute unknown */
 unsigned duplicate_acks;
 uint8_t identity[6], tail[2];
 bool tail_verified, ack_seen;
};
void dsl_rom_init(struct dsl_rom_session *, const uint8_t *, size_t,
                  const uint8_t identity[6]);
int dsl_rom_handle(struct dsl_rom_session *, const struct dsl_rom_packet *,
                   uint8_t *reply, size_t capacity, size_t *reply_len);
/* No allocations, device operations or string logging in this core. */
void dsl_sha256(const uint8_t *, size_t, uint8_t digest[32]);
#endif
