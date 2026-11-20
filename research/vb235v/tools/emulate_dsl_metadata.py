#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Execute original libpt readiness/interface logic with memory-only IPC/socket models."""
import argparse
import json
from pathlib import Path
import struct

from emulate_dsl_libpt import Transaction, BASE, DATA, STACK, STOP, EXPECTED_SHA256

METADATA = DATA + 0xf000
SELECTORS = (0xbeea, 0xbeeb, 0xbeec, 0xbeed, 0xbeef)


def require(condition, message):
    if not condition:
        raise ValueError(message)


class GuestExit(Exception):
    pass


class GuestTrap(Exception):
    pass


class Metadata(Transaction):
    def __init__(self, path, metadata, *, socket_fails=False, option_fails=None):
        require(len(metadata) == 40, 'Metadata must be exactly 40 bytes')
        self.metadata = metadata
        self.metadata_reads = []
        self.options = []
        self.socket_fails, self.option_fails = socket_fails, option_fails
        super().__init__(path)
        self.uc.mem_write(METADATA, metadata)
        for index in range(5):
            self.uc.mem_write(BASE + 0x13008 + 4 * index, struct.pack('<i', -1))
        self.uc.mem_write(BASE + self.symbols['ifName']['value'], bytes(16))
        self.uc.hook_add(self.unicorn.UC_HOOK_MEM_READ, self._read_metadata,
                         begin=METADATA, end=METADATA + 39)

    def _read_metadata(self, uc, access, address, size, value, user_data):
        self.metadata_reads.append((address - METADATA, size))

    def _interrupt(self, uc, number, user_data):
        if number == 7 and uc.reg_read(self.regs.UC_ARM64_REG_PC) == BASE + 0x16b8:
            raise GuestTrap('Original bounds/overlap BRK #1000')
        raise RuntimeError('Guest interrupt/syscall rejected')

    def _callback(self, name):
        a = [self._reg(index) for index in range(5)]
        if name == 'shmget':
            self.calls[name] += 1
            require(a[:3] == [0x1492, 40, 0x3b6], 'Unexpected modeled IPC request')
            return 8
        if name == 'shmat':
            self.calls[name] += 1
            require(a[:3] == [8, 0, 0], 'Unexpected modeled IPC attach')
            return METADATA
        if name == 'shmdt':
            self.calls[name] += 1
            require(a[0] == METADATA, 'Unexpected modeled IPC detach')
            return 0
        if name == 'socket':
            self.calls[name] += 1
            wire_selector = int.from_bytes(self.selector.to_bytes(2, 'little'), 'big')
            require(a[:3] == [17, 3, wire_selector], 'Unexpected packet socket request')
            return -1 if self.socket_fails else 13
        if name == 'setsockopt':
            self.calls[name] += 1
            require(a[0] == 13 and a[1] == 1 and a[2] in (2, 25, 20, 36),
                    'Unexpected socket option')
            expected_sizes = {2: 4, 25: 15, 20: 16, 36: 4}
            require(a[4] == expected_sizes[a[2]], 'Socket option size differs')
            value = self._bytes(a[3], a[4])
            row = {'level': 1, 'option': a[2], 'bytes': a[4]}
            if a[2] == 25:
                length = struct.unpack_from('<I', self.metadata, 4)[0]
                expected = self.metadata[16:16 + length].ljust(15, b'\0')
                require(value == expected, 'Modeled interface binding differs')
                row['interface_matches_metadata'] = True
            elif a[2] == 20:
                require(struct.unpack('<qq', value) == (self.timeout, 0), 'Receive timeout differs')
                row['timeout_seconds'] = self.timeout
            elif a[2] == 36:
                require(struct.unpack('<I', value)[0] == 16, 'Original socket mark differs')
                row['mark'] = 16
            self.options.append(row)
            return -1 if self.option_fails == a[2] else 0
        if name == 'perror':
            self.calls[name] += 1
            return 0
        if name == 'exit':
            self.calls[name] += 1
            require(a[0] == 1, 'Unexpected original exit status')
            raise GuestExit('Original code requests exit(1)')
        return super()._callback(name)

    def run_fd(self, selector, timeout=1):
        require(selector in SELECTORS and 0 <= timeout <= 60, 'Unsupported modeled arguments')
        self.selector, self.timeout = selector, timeout
        self.instructions = 0
        self.uc.reg_write(self.regs.UC_ARM64_REG_SP, STACK + 0x1f000)
        self.uc.reg_write(self.regs.UC_ARM64_REG_X0, selector)
        self.uc.reg_write(self.regs.UC_ARM64_REG_X1, timeout)
        self.uc.reg_write(self.regs.UC_ARM64_REG_X30, STOP)
        outcome = 'return'; result = None
        try:
            self.uc.emu_start(BASE + self.symbols['pt_fd_open']['value'], STOP,
                              timeout=2_000_000, count=200000)
            require(self.uc.reg_read(self.regs.UC_ARM64_REG_PC) == STOP, 'Guest budget exhausted')
            result = self._reg(0) & 0xffffffff
            if result >= 0x80000000:
                result -= 0x100000000
        except GuestTrap:
            outcome = 'guest-brk-1000'
        except GuestExit:
            outcome = 'guest-exit-1'
        return {'selector': hex(selector), 'outcome': outcome, 'return': result,
                'metadata_read_ranges': sorted(set(self.metadata_reads)),
                'modeled_imports': dict(self.calls), 'socket_options': self.options,
                'instructions': self.instructions}


def make_metadata(flags, name=b'ae_wan', declared_length=None, suffix=None):
    require(len(name) <= 16, 'Synthetic interface name too long')
    data = bytearray(40)
    struct.pack_into('<II', data, 0, flags, len(name) if declared_length is None else declared_length)
    data[16:16 + len(name)] = name
    if suffix is not None:
        require(len(suffix) == 12, 'Invalid synthetic metadata suffix')
        data[28:] = suffix
    return bytes(data)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('libpt', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    vectors = []
    for selector in SELECTORS:
        for flags in (0, 1):
            result = Metadata(args.libpt, make_metadata(flags)).run_fd(selector)
            expected = 2 if selector == 0xbeea and flags == 0 else 0
            require(result['outcome'] == 'return' and result['return'] == expected, 'Readiness contract differs')
            require(result['modeled_imports'].get('socket', 0) == (0 if expected == 2 else 1),
                    'Unexpected socket request before readiness')
            vectors.append({'case': 'selector-readiness', 'flags': flags, **result})
    for flags in (2, 3, 0x80000000, 0x80000001):
        result = Metadata(args.libpt, make_metadata(flags)).run_fd(0xbeea)
        require(result['return'] == (0 if flags & 1 else 2), 'Readiness bit contract differs')
        vectors.append({'case': 'readiness-bit-isolation', 'flags': flags, **result})
    for length in (0, 12, 13):
        data = make_metadata(1, b'abcdefghijkl', declared_length=length)
        result = Metadata(args.libpt, data).run_fd(0xbeea)
        expected = 'guest-brk-1000' if length == 13 else 'return'
        require(result['outcome'] == expected and (length == 13 or result['return'] == 0),
                'Interface-copy bound differs')
        vectors.append({'case': 'interface-length-boundary', 'declared_length': length, **result})
    result = Metadata(args.libpt, make_metadata(1, suffix=bytes([0xff]) * 12)).run_fd(0xbeea)
    require(result['return'] == 0 and max(a + n for a, n in result['metadata_read_ranges']) == 28,
            'Unexpected metadata suffix consumption')
    vectors.append({'case': 'suffix-not-consumed-by-this-function', **result})
    result = Metadata(args.libpt, make_metadata(1), socket_fails=True).run_fd(0xbeea)
    require(result['return'] == 1, 'Socket failure result differs')
    vectors.append({'case': 'modeled-socket-failure', **result})
    result = Metadata(args.libpt, make_metadata(1), option_fails=25).run_fd(0xbeea)
    require(result['outcome'] == 'guest-exit-1' and result['modeled_imports'].get('close') == 1,
            'Binding failure cleanup/exit differs')
    vectors.append({'case': 'modeled-bind-device-failure', **result})
    report = {'stage': 'M62', 'original_libpt_sha256': EXPECTED_SHA256,
              'original_ARM64_pt_fd_open_executed': True,
              'shared_memory_key': 0x1492, 'requested_segment_bytes': 40,
              'selected_consumer_copies_bytes': 28, 'flags_u32_offset': 0,
              'interface_copy_length_u32_offset': 4, 'interface_bytes_offset': 16,
              'maximum_interface_copy_bytes': 12, 'other_metadata_fields_not_assigned_semantics': True,
              'ready_mask_for_BEEA': 1, 'not_ready_return': 2, 'socket_failure_return': 1,
              'socket_mark_from_original_code': 16, 'vectors_passed': len(vectors), 'vectors': vectors,
              'sysv_segment_or_network_backend_used': False, 'device_operations': False,
              'endpoint_firmware_loaded': False, 'DSL_showtime_verified': False}
    args.output.write_bytes((json.dumps(report, indent=2) + '\n').encode())
    print(json.dumps({'vectors_passed': len(vectors), 'device_operations': False}))


if __name__ == '__main__':
    main()
