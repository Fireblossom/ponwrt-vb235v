#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""CRC-only YMODEM-1K sender for the pinned U-Boot loady receiver.

This module never opens a port or issues a boot/flash command. The caller must
already have observed loady's binary-ready banner and isolated protocol bytes.
After an uncertain final acknowledgement, stop input and inspect console state;
never replay the transfer into an unobserved shell. Verify receiver filesize,
CRC32 and FIT hashes independently before considering a RAM boot.

Reviewed receiver: installed M73 normal core's common/xyzModem.c,
SHA256 72f538bbaa91696196d3b0ad730bf5bdaa27aff33e0e3e530ad4844bf78f2e79.
The protocol is only a transport; it neither grants a safe RAM address range
nor establishes DMA quiescence or permission to execute an uploaded image.
"""
import binascii
import time

SOH, STX, EOT, ACK, NAK, CAN, CRC = 1, 2, 4, 6, 21, 24, 67


class TransferError(RuntimeError):
    pass


class FinalAcknowledgementMissing(TransferError):
    pass


def frame(sequence, payload):
    if len(payload) not in (128, 1024) or not 0 <= sequence <= 255:
        raise ValueError('YMODEM frame requires 128/1024 bytes and an 8-bit sequence')
    checksum = binascii.crc_hqx(payload, 0)
    return bytes((SOH if len(payload) == 128 else STX, sequence, sequence ^ 255)) + payload + checksum.to_bytes(2, 'big')


class Sender:
    def __init__(self, read, write, *, clock=time.monotonic, timeout=3, retries=8, progress=None):
        if timeout <= 0 or not 1 <= retries <= 16:
            raise ValueError('Invalid bounded transfer limits')
        self.read, self.write, self.clock = read, write, clock
        self.timeout, self.retries, self.progress = timeout, retries, progress
        self.pending = bytearray()
        self.total_retries = self.wire_bytes = 0

    def _write(self, data):
        at = 0
        while at < len(data):
            count = self.write(data[at:])
            if not isinstance(count, int) or not 0 < count <= len(data) - at:
                raise TransferError('Serial write made no valid progress')
            at += count
            self.wire_bytes += count

    def _wait(self, accepted, timeout=None):
        until = self.clock() + (self.timeout if timeout is None else timeout)
        cancels = 0
        while self.clock() < until:
            if not self.pending:
                self.pending.extend(self.read())
                if len(self.pending) > 65536:
                    raise TransferError('Unexpected unbounded receiver output')
            while self.pending:
                value = self.pending.pop(0)
                if value == CAN:
                    cancels += 1
                    if cancels >= 2:
                        raise TransferError('Receiver cancelled the transfer')
                else:
                    cancels = 0
                if value in accepted:
                    return value
        raise TimeoutError('Receiver acknowledgement timed out')

    def _packet(self, encoded, *, final=False):
        attempts = 1 if final else self.retries
        for attempt in range(attempts):
            self._write(encoded)
            try:
                if self._wait({ACK, NAK}) == ACK:
                    return
            except TimeoutError:
                if final:
                    raise FinalAcknowledgementMissing('Final block was sent; completion is uncertain; do not resend into a shell') from None
            if attempt + 1 < attempts:
                self.total_retries += 1
        raise TransferError('Bounded frame retry limit reached')

    def send(self, data, filename, *, maximum_size=64*1024*1024):
        if not isinstance(data, bytes) or not 0 < len(data) <= maximum_size:
            raise ValueError('Invalid RAM image size')
        try:
            name = filename.encode('ascii')
        except (AttributeError, UnicodeEncodeError):
            raise ValueError('Filename must be short ASCII') from None
        if not name or len(name) > 80 or any(c not in b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-' for c in name):
            raise ValueError('Unsafe YMODEM metadata filename')
        metadata = name + b'\0' + str(len(data)).encode() + b'\0'
        if len(metadata) > 128:
            raise ValueError('Metadata does not fit the filename frame')
        start = self.clock()
        if self._wait({CRC, NAK}, timeout=15) != CRC:
            raise TransferError('Receiver did not negotiate CRC mode')
        self._packet(frame(0, metadata.ljust(128, b'\0')))
        # Pinned U-Boot acknowledges its filename header on the first read but
        # does not issue a second C until timeout. ACK already admits block 1.
        blocks = 0
        for at in range(0, len(data), 1024):
            self._packet(frame((blocks + 1) & 255, data[at:at+1024].ljust(1024, b'\x1a')))
            blocks += 1
            if self.progress:
                self.progress(min(at+1024, len(data)), len(data), self.total_retries)
        # Accept both the pinned receiver's immediate ACK and two-EOT peers.
        for attempt in range(2):
            self._write(bytes((EOT,)))
            try:
                if self._wait({ACK, NAK}) == ACK:
                    break
            except TimeoutError:
                if attempt:
                    raise TransferError('EOT acknowledgement missing') from None
        else:
            raise TransferError('EOT handshake rejected')
        # U-Boot emits two ACKs around EOT. Waiting for C separates those old
        # acknowledgements from the final empty-header acknowledgement.
        self._wait({CRC})
        self._packet(frame(0, bytes(128)), final=True)
        return {'bytes': len(data), 'data_blocks': blocks, 'retries': self.total_retries,
                'wire_bytes': self.wire_bytes, 'seconds': self.clock()-start,
                'final_acknowledgement': True}
