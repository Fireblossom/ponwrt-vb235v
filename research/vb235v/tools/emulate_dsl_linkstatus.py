#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Execute the pinned original DSL link-status getter with modeled proc reads.

Requires Unicorn 2.1.4. There is no host open/read/socket/ioctl/device backend.
The actual ARM64 parser runs unchanged; its input is synthetic test text.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

from elf_dynamic_inventory import SharedObject

EXPECTED = 'e0aaacc2961e90854efd3a64499da717a9787af5aa6a5332412cebb3d544a78b'
BASE, STUBS, DATA, STACK, INPUT, STOP = 0x100000, 0x200000, 0x300000, 0x400000, 0x600000, 0x20f000
SENTINEL = 0xdec0adde


def require(condition, message):
    if not condition:
        raise ValueError(message)


class LinkStatus:
    def __init__(self, path):
        import unicorn
        from unicorn import arm64_const
        require(unicorn.__version__ == '2.1.4', 'Use reviewed Unicorn 2.1.4')
        self.unicorn, self.regs = unicorn, arm64_const
        self.module = SharedObject(path)
        require(hashlib.sha256(self.module.data).hexdigest() == EXPECTED, 'Unreviewed original DSL library')
        self.uc = unicorn.Uc(unicorn.UC_ARCH_ARM64, unicorn.UC_MODE_ARM)
        for start, length in [(BASE, 0x40000), (STUBS, 0x10000), (DATA, 0x20000),
                              (STACK, 0x40000), (INPUT, 0x20000)]:
            self.uc.mem_map(start, length)
        self.executable = []
        for section in self.module.sections:
            if not section['flags'] & 2:
                continue
            require(section['address'] + section['size'] <= 0x40000, 'ELF exceeds fixed mapping')
            if section['type'] != 8 and section['size']:
                self.uc.mem_write(BASE + section['address'], self.module.payload(section))
            if section['flags'] & 4:
                self.executable.append((BASE + section['address'], BASE + section['address'] + section['size']))
        symbols = {s['name']: s for table in self.module.symbol_tables.values() for s in table
                   if s['section'] and s['name']}
        self.entry = BASE + symbols['blapi_xdsl_get_xdsl_linkstatus']['value']
        require(self.entry == BASE + 0x97b8, 'Original getter entry differs')
        self.stubs = {}; allocated = {}
        for section in self.module.sections:
            if section['type'] != 4:
                continue
            table = self.module.symbol_tables[section['link']]
            for offset in range(0, section['size'], 24):
                address, info, addend = struct.unpack_from('<QQq', self.module.payload(section), offset)
                symbol = table[info >> 32]; kind = info & 0xffffffff
                if kind == 1027:
                    value = BASE + addend
                elif kind in (257, 1025, 1026):  # ABS64, GLOB_DAT, JUMP_SLOT
                    if symbol['section']:
                        value = BASE + symbol['value'] + addend
                    else:
                        require(addend == 0, 'Unmodeled imported-symbol addend')
                        name = symbol['name']
                        if name not in allocated:
                            if name in ('__stack_chk_guard', 'stderr'):
                                value = DATA + 32 * len(allocated)
                                self.uc.mem_write(value, struct.pack('<Q', 0x123456789abcdef0))
                            else:
                                value = STUBS + 16 * len(allocated)
                                self.stubs[value] = name
                                self.uc.mem_write(value, bytes.fromhex('c0035fd6'))
                            allocated[name] = value
                        value = allocated[name]
                else:
                    raise ValueError('Unmodeled ELF relocation ' + str(kind))
                require(0 <= address <= 0x40000 - 8, 'Relocation outside ELF mapping')
                self.uc.mem_write(BASE + address, struct.pack('<Q', value))
        self.uc.hook_add(unicorn.UC_HOOK_CODE, self._code)
        self.uc.hook_add(unicorn.UC_HOOK_INTR, self._interrupt)

    def reg(self, index):
        return self.uc.reg_read(getattr(self.regs, 'UC_ARM64_REG_X' + str(index)))

    def cstring(self, address, limit=256):
        data = bytes(self.uc.mem_read(address, limit))
        end = data.find(b'\0')
        require(end >= 0, 'Guest string exceeds its model bound')
        return data[:end]

    def _interrupt(self, uc, number, user_data):
        raise RuntimeError('Guest interrupt/syscall rejected')

    def _callback(self, name):
        a = [self.reg(index) for index in range(3)]
        self.calls[name] += 1
        if name == 'open':
            require(self.cstring(a[0]) == b'/proc/tc3162/adsl_stats' and a[1] == 0x800,
                    'Unexpected guest file/open flags')
            return -1 if self.open_fails else 7
        if name == 'read':
            require(a[0] == 7 and a[2] == 127, 'Unexpected modeled proc read')
            if self.read_fails:
                return -1
            payload = self.response[:127]
            self.uc.mem_write(a[1], payload)
            return len(payload)
        if name == 'close':
            require(a[0] == 7, 'Unexpected descriptor close')
            return 0
        if name == 'memset':
            require(a[2] <= 4096, 'Guest memset exceeds budget')
            self.uc.mem_write(a[0], bytes([a[1] & 255]) * a[2])
            return a[0]
        if name == 'strncpy':
            require(a[0] == INPUT and a[2] == 128, 'Unexpected caller-buffer copy')
            source = self.cstring(a[1])
            self.uc.mem_write(a[0], source[:128].ljust(128, b'\0'))
            return a[0]
        if name == 'strstr':
            source, needle = self.cstring(a[0]), self.cstring(a[1])
            require(needle in (b'up', b'PTM'), 'Unexpected original parser token')
            self.tokens.append(needle.decode())
            position = source.find(needle)
            return 0 if position < 0 else a[0] + position
        raise RuntimeError('Unmodeled guest import rejected: ' + name)

    def _code(self, uc, address, size, user_data):
        self.instructions += 1
        require(self.instructions <= 20000, 'Guest instruction budget exceeded')
        if address in self.stubs:
            result = self._callback(self.stubs[address])
            uc.reg_write(self.regs.UC_ARM64_REG_X0, result & 0xffffffffffffffff)
            uc.reg_write(self.regs.UC_ARM64_REG_PC, self.reg(30))
        else:
            require(any(start <= address < end for start, end in self.executable),
                    'Guest execution outside reviewed code')

    def run(self, response, *, open_fails=False, read_fails=False):
        require(type(response) is bytes and len(response) <= 4096, 'Synthetic response exceeds model budget')
        self.response, self.open_fails, self.read_fails = response, open_fails, read_fails
        self.calls, self.tokens, self.instructions = Counter(), [], 0
        self.uc.mem_write(INPUT, bytes([0xa5]) * 128 + bytes(128) + struct.pack('<I', SENTINEL))
        for index in range(31):
            self.uc.reg_write(getattr(self.regs, 'UC_ARM64_REG_X' + str(index)), 0)
        self.uc.reg_write(self.regs.UC_ARM64_REG_SP, STACK + 0x3f000)
        self.uc.reg_write(self.regs.UC_ARM64_REG_X0, INPUT)
        self.uc.reg_write(self.regs.UC_ARM64_REG_X1, INPUT + 256)
        self.uc.reg_write(self.regs.UC_ARM64_REG_X30, STOP)
        self.uc.emu_start(self.entry, STOP, timeout=2_000_000, count=20000)
        require(self.uc.reg_read(self.regs.UC_ARM64_REG_PC) == STOP, 'Guest did not return within budget')
        result = self.reg(0) & 0xffffffff
        if result >= 0x80000000:
            result -= 1 << 32
        state = struct.unpack('<I', self.uc.mem_read(INPUT + 256, 4))[0]
        output = bytes(self.uc.mem_read(INPUT, 128))
        return result, state, output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    getter = LinkStatus(args.library)
    samples = [
        ('empty', b''), ('down', b'down'), ('ATM-label', b'link up ATM'),
        ('PTM-label', b'link up PTM'), ('reversed-tokens', b'PTM link up'),
        ('uppercase-UP', b'UP PTM'), ('lowercase-ptm', b'up ptm'),
        ('startup-substring', b'startup'), ('backup-substring', b'backup info PTM'),
        ('NUL-after-up', b'up\0PTM'), ('NUL-before-up', b'down\0up PTM'),
        ('up-at-read-boundary', b'x' * 125 + b'up'),
        ('up-truncated', b'x' * 126 + b'up'),
        ('PTM-at-read-boundary', b'up' + b'x' * 122 + b'PTM'),
        ('PTM-truncated', b'up' + b'x' * 123 + b'PTM'),
    ]
    vectors = []
    for label, response in samples:
        result, state, output = getter.run(response)
        visible = response[:127].split(b'\0')[0]
        expected_ret = 0 if b'up' in visible else -1
        expected_state = (2 if b'PTM' in visible else 1) if expected_ret == 0 else SENTINEL
        expected_output = visible.ljust(128, b'\0') if response else bytes([0xa5]) * 128
        require((result, state, output) == (expected_ret, expected_state, expected_output),
                'Original getter differs from derived parser contract: ' + label)
        vectors.append({'case': label, 'return': result, 'state': state if state != SENTINEL else 'untouched',
                        'instructions': getter.instructions, 'modeled_imports': dict(getter.calls),
                        'actual_parser_tokens': getter.tokens})
    for label, options in [('open-failure', {'open_fails': True}), ('read-failure', {'read_fails': True})]:
        result, state, output = getter.run(b'up PTM', **options)
        require((result, state, output) == (-1, SENTINEL, bytes([0xa5]) * 128), 'Failure path overwrites caller state')
        vectors.append({'case': label, 'return': result, 'state': 'untouched', 'modeled_imports': dict(getter.calls)})
    report = {'stage': 'M61', 'library_sha256': EXPECTED, 'original_ARM64_getter_executed': True,
              'proc_path': '/proc/tc3162/adsl_stats', 'open_flags': 'O_RDONLY|O_NONBLOCK (0x800)',
              'maximum_read_bytes': 127, 'caller_text_buffer_bytes': 128,
              'state_1': 'up substring present; PTM substring absent',
              'state_2': 'both up and PTM substrings present',
              'failure_return': -1, 'failure_state_word_untouched': True,
              'vectors_passed': len(vectors), 'vectors': vectors,
              'guest_syscalls_or_unmodeled_imports_allowed': False,
              'host_device_or_network_backend': False, 'actual_DSL_line_or_endpoint_read': False}
    args.output.write_bytes((json.dumps(report, indent=2) + '\n').encode())
    print(json.dumps({'vectors_passed': len(vectors), 'actual_DSL_line_read': False}))


if __name__ == '__main__':
    main()
