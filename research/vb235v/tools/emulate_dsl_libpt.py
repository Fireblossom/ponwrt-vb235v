#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Run the pinned libpt ARM64 transaction with modeled external callbacks.

Requires Unicorn 2.1.4. No vendor library is loaded into the host process.
No host socket, ioctl, shared memory, subprocess or device operation exists.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import random
import struct

from dsl_pt_wire import decode_frame, encode_request
from elf_dynamic_inventory import SharedObject

EXPECTED_SHA256 = 'eb8dc5d2929120e48b58d9bb67a717346a46837e191533f02b957d363f77ff7f'
BASE = 0x100000
STUBS = 0x200000
STOP = 0x20f000
DATA = 0x300000
STACK = 0x400000
HEAP = 0x500000
INPUT = 0x600000


def require(condition, message):
    if not condition:
        raise ValueError(message)


class Transaction:
    def __init__(self, path):
        import unicorn
        from unicorn import arm64_const
        require(unicorn.__version__ == '2.1.4', 'Use the reviewed Unicorn version 2.1.4')
        self.unicorn = unicorn
        self.regs = arm64_const
        self.module = SharedObject(path)
        require(hashlib.sha256(self.module.data).hexdigest() == EXPECTED_SHA256,
                'libpt differs from the verified stock snapshot')
        self.uc = unicorn.Uc(unicorn.UC_ARCH_ARM64, unicorn.UC_MODE_ARM)
        self.uc.mem_map(BASE, 0x20000)
        self.uc.mem_map(STUBS, 0x10000)
        self.uc.mem_map(DATA, 0x10000)
        self.uc.mem_map(STACK, 0x20000)
        self.uc.mem_map(HEAP, 0x100000)
        self.uc.mem_map(INPUT, 0x10000)
        self.executables = []
        for section in self.module.sections:
            if not section['flags'] & 2:
                continue
            require(section['address'] + section['size'] <= 0x20000, 'ELF mapping exceeds the fixed budget')
            if section['type'] != 8 and section['size']:
                self.uc.mem_write(BASE + section['address'], self.module.payload(section))
            if section['flags'] & 4:
                self.executables.append((BASE + section['address'], BASE + section['address'] + section['size']))
        self.symbols = {symbol['name']: symbol for table in self.module.symbol_tables.values()
                        for symbol in table if symbol['name'] and symbol['section']}
        self.stubs = {}
        self.calls = Counter()
        self.instructions = 0
        self.heap_next = HEAP
        self.sent = []
        self.reply = None
        self.fail_malloc = False
        self.fail_allocation_at = None
        self._relocate()
        for name, value in [('ifName', b'ae_wan\0'), ('dest_mac', bytes.fromhex('020000000002'))]:
            self.uc.mem_write(BASE + self.symbols[name]['value'], value)
        # pt_fd_open is a modeled callback; its descriptor side effect is synthetic.
        for index in range(5):
            self.uc.mem_write(BASE + 0x13008 + 4 * index, struct.pack('<i', 7 + index))
        self.uc.mem_write(STOP, bytes.fromhex('c0035fd6'))
        self.uc.hook_add(unicorn.UC_HOOK_CODE, self._code)
        self.uc.hook_add(unicorn.UC_HOOK_INTR, self._interrupt)

    def _relocate(self):
        stubs_by_name = {}
        for section in self.module.sections:
            if section['type'] != 4:
                continue
            table = self.module.symbol_tables[section['link']]
            for offset in range(0, section['size'], 24):
                address, info, addend = struct.unpack_from('<QQq', self.module.payload(section), offset)
                symbol = table[info >> 32]
                kind = info & 0xffffffff
                if kind == 1027:
                    value = BASE + addend
                elif kind in (1025, 1026):
                    name = symbol['name']
                    if symbol['section'] and name not in ('pt_fd_open', 'sismDbgMsg'):
                        value = BASE + symbol['value'] + addend
                    elif name in ('__stack_chk_guard', 'sism_log_hdr', 'sism_log_level'):
                        value = DATA + len(stubs_by_name) * 32
                        if name == '__stack_chk_guard':
                            self.uc.mem_write(value, struct.pack('<Q', 0x123456789abcdef0))
                        stubs_by_name[name] = value
                    else:
                        if name not in stubs_by_name:
                            value = STUBS + len(stubs_by_name) * 16
                            stubs_by_name[name] = value
                            self.stubs[value] = name
                            self.uc.mem_write(value, bytes.fromhex('c0035fd6'))
                        value = stubs_by_name[name]
                else:
                    raise ValueError('Unsupported ELF relocation: ' + str(kind))
                self.uc.mem_write(BASE + address, struct.pack('<Q', value))

    def _interrupt(self, uc, number, user_data):
        raise RuntimeError('Guest interrupt/syscall rejected: ' + str(number))

    def _reg(self, index):
        return self.uc.reg_read(getattr(self.regs, 'UC_ARM64_REG_X' + str(index)))

    def _bytes(self, address, size):
        require(0 <= size <= 65536, 'Modeled callback exceeds its byte budget')
        return bytes(self.uc.mem_read(address, size))

    def _callback(self, name):
        a = [self._reg(index) for index in range(6)]
        self.calls[name] += 1
        if name in ('pt_fd_open', 'close', 'free', 'sismDbgMsg'):
            return 0
        if name == 'malloc':
            require(0 < a[0] <= 65536, 'Unexpected allocation')
            if self.fail_malloc or self.calls['malloc'] == self.fail_allocation_at:
                return 0
            value = self.heap_next
            self.heap_next += (a[0] + 15) & ~15
            require(self.heap_next <= HEAP + 0x100000, 'Heap budget exceeded')
            return value
        if name == 'memset':
            require(a[2] <= 65536, 'memset budget exceeded')
            self.uc.mem_write(a[0], bytes([a[1] & 255]) * a[2])
            return a[0]
        if name == 'memcpy':
            self.uc.mem_write(a[0], self._bytes(a[1], a[2]))
            return a[0]
        if name == 'strncpy':
            require(a[2] <= 256, 'strncpy budget exceeded')
            value = self._bytes(a[1], a[2]).split(b'\0')[0]
            self.uc.mem_write(a[0], value[:a[2]].ljust(a[2], b'\0'))
            return a[0]
        if name in ('htons', 'ntohs', 'htonl', 'ntohl'):
            size = 2 if name.endswith('s') else 4
            return int.from_bytes((a[0] & ((1 << (size * 8)) - 1)).to_bytes(size, 'little'), 'big')
        if name == 'ioctl':
            require(a[1] in (0x8933, 0x8927), 'Unexpected ioctl request')
            if a[1] == 0x8933:
                self.uc.mem_write(a[2] + 16, struct.pack('<I', 3))
            else:
                self.uc.mem_write(a[2] + 16, struct.pack('<H', 1) + bytes.fromhex('021122334455'))
            return 0
        if name == 'sendto':
            frame = self._bytes(a[1], a[2])
            self.sent.append(frame)
            # The endpoint response is modeled, including its status word.
            reply = bytearray(frame)
            reply[:6], reply[6:12] = frame[6:12], frame[:6]
            struct.pack_into('>I', reply, 14 + 12, 0x11223344)
            self.reply = bytes(reply)
            return len(frame)
        if name == 'recvfrom':
            require(self.reply is not None and len(self.reply) <= a[2], 'No bounded modeled reply')
            self.uc.mem_write(a[1], self.reply)
            return len(self.reply)
        # Imports such as system/socket/shmget/shmat/setsockopt have no backend.
        raise RuntimeError('Unmodeled guest import rejected: ' + name)

    def _code(self, uc, address, size, user_data):
        self.instructions += 1
        require(self.instructions <= 200000, 'Instruction budget exceeded')
        if address in self.stubs:
            result = self._callback(self.stubs[address])
            uc.reg_write(self.regs.UC_ARM64_REG_X0, result & 0xffffffffffffffff)
            uc.reg_write(self.regs.UC_ARM64_REG_PC, self._reg(30))
        else:
            require(any(start <= address < end for start, end in self.executables),
                    'Execution outside the mapped vendor code')

    def run(self, host_record, *, fail_malloc=False, fail_allocation_at=None):
        require(len(host_record) == 192, 'Host record must be exactly 192 bytes')
        self.fail_malloc = fail_malloc
        self.fail_allocation_at = fail_allocation_at
        self.uc.mem_write(INPUT, host_record)
        self.uc.reg_write(self.regs.UC_ARM64_REG_SP, STACK + 0x20000 - 16)
        self.uc.reg_write(self.regs.UC_ARM64_REG_X0, INPUT)
        self.uc.reg_write(self.regs.UC_ARM64_REG_X30, STOP)
        self.uc.emu_start(BASE + self.symbols['SRC_blapi']['value'], STOP,
                          timeout=2_000_000, count=200000)
        require(self.uc.reg_read(self.regs.UC_ARM64_REG_PC) == STOP,
                'Transaction did not return within its execution budget')
        return self.uc.reg_read(self.regs.UC_ARM64_REG_X0), self._bytes(INPUT, 192)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    record = bytearray(192)
    struct.pack_into('>II', record, 4, 22, 1)
    command = b'offline-format-fixture\0'
    record[16:16 + len(command)] = command
    struct.pack_into('>4I', record, 176, 1, 2, 3, 4)
    transaction = Transaction(args.library)
    result, updated = transaction.run(bytes(record))
    require(result == 0 and len(transaction.sent) == 1, 'Modeled transaction failed')
    frame = transaction.sent[0]
    require(len(frame) == 218 and frame[12:14] == b'\xbe\xea', 'Unexpected frame geometry')
    require(frame[14:20] == bytes.fromhex('751775170001'), 'Unexpected wire header')
    require(frame[14 + 16:14 + 24] == record[4:12], 'Operation fields differ')
    require(frame[14 + 28:14 + 188] == record[16:176], 'Command bytes differ')
    require(frame[14 + 188:14 + 204] == record[176:192], 'Tail fields differ')
    require(struct.unpack_from('<I', updated)[0] == 0x11223344, 'Status copyback differs')
    generator = random.Random(0x235)
    vectors = [bytes(192), bytes([255]) * 192, bytes(range(192))]
    vectors += [bytes(generator.randrange(256) for _ in range(192)) for _ in range(64)]
    for vector in vectors:
        other = Transaction(args.library)
        other_result, other_updated = other.run(vector)
        require(other_result == 0 and len(other.sent) == 1, 'Variant transaction failed')
        require(other.sent[0][14:] == encode_request(vector), 'Codec differs from actual vendor instructions')
        require(struct.unpack_from('<I', other_updated)[0] == 0x11223344,
                'Variant status copyback differs')
        decode_frame(other.sent[0])
    failure_results = []
    for allocation in (1, 2, 3):
        failure = Transaction(args.library)
        failed_result, _ = failure.run(bytes(record), fail_allocation_at=allocation)
        require(failed_result != 0 and not failure.sent, 'Allocation failure transmitted a frame')
        failure_results.append({'allocation': allocation, 'result_u32': failed_result & 0xffffffff,
                                'frames': len(failure.sent)})
    report = {'classification': 'actual pinned ARM64 functions with modeled external callbacks',
              'library_sha256': EXPECTED_SHA256, 'emulator': 'Unicorn 2.1.4',
              'entry_function': 'SRC_blapi', 'instruction_count': transaction.instructions,
              'external_callbacks': dict(transaction.calls), 'frame_bytes': len(frame),
              'ethertype': '0xbeea', 'payload_bytes': len(frame) - 14,
              'payload_magic': '0x75177517', 'payload_version': 1,
              'host_record_bytes': 192, 'command_bytes': 160,
              'command_payload_offset': 28, 'tail_payload_offset': 188,
              'modeled_status_copyback_verified': True,
              'successful_native_instruction_vectors': len(vectors) + 1,
              'codec_matches_vendor_instruction_output': True,
              'allocation_failure_cases': failure_results,
              'allocation_failure_sends_nothing': True,
              'endpoint_response_modeled': True, 'real_endpoint_compatibility_proven': False,
              'host_network_operations': False, 'router_commands_sent': False}
    args.output.write_bytes((json.dumps(report, indent=2) + '\n').encode('utf8'))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
