#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Offline admission for the M55 controller-free, full-userspace RAM image."""
import argparse
import hashlib
import json
from pathlib import Path
import posixpath
import struct

from fdt_board_inventory import parse
from inspect_vb235v_sysupgrade import image_data, kernel_bytes, number, text

BOARD = 'tplink,vb235v-ram-development'
MAX_FIT = 56 * 1024 * 1024


def require(condition, message):
    if not condition:
        raise ValueError(message)


def cells(*values):
    return struct.pack('>' + 'I' * len(values), *values)


def audit_dtb(dtb):
    nodes, reserved = parse(dtb)
    return audit_dtb_nodes(nodes, reserved, hashlib.sha256(dtb).hexdigest())


def audit_dtb_nodes(nodes, reserved, dtb_sha256):
    expected_paths = {
        '/', '/aliases', '/chosen', '/memory@80000000', '/reserved-memory',
        '/reserved-memory/atf@80000000', '/reserved-memory/npu@84000000',
        '/reserved-memory/qdma0@87000000', '/reserved-memory/qdma1@89000000',
        '/reserved-memory/logs@8b000000', '/cpus', '/cpus/cpu@0',
        '/psci', '/interrupt-controller@9000000', '/timer', '/serial@1fbf0000',
    }
    symbols = {'gic': b'/interrupt-controller@9000000\0',
               'uart0': b'/serial@1fbf0000\0'}
    if '/__symbols__' in nodes:
        require(nodes['/__symbols__'] == symbols, 'Unexpected compiler DT symbol metadata')
        expected_paths.add('/__symbols__')
    require(set(nodes) == expected_paths, 'Unexpected DT node; peripheral review required')
    require(not reserved, 'Unexpected FDT header reservations')
    expected = {
        '/': {'compatible': (BOARD + '\0airoha,an7583\0').encode(),
              '#address-cells': cells(2), '#size-cells': cells(2)},
        '/aliases': {'serial0': b'/serial@1fbf0000\0'},
        '/chosen': {'stdout-path': b'serial0:115200n8\0',
                    'bootargs': b'console=ttyS0,115200n8 earlycon=uart8250,mmio32,0x1fbf0000 rdinit=/init panic=0\0'},
        '/memory@80000000': {'device_type': b'memory\0', 'reg': cells(0, 0x80000000, 0, 0x20000000)},
        '/reserved-memory': {'#address-cells': cells(2), '#size-cells': cells(2), 'ranges': b''},
        '/cpus': {'#address-cells': cells(1), '#size-cells': cells(0)},
        '/cpus/cpu@0': {'device_type': b'cpu\0', 'compatible': b'arm,cortex-a53\0',
                        'reg': cells(0), 'enable-method': b'psci\0'},
        '/psci': {'compatible': b'arm,psci-0.2\0', 'method': b'smc\0'},
        '/interrupt-controller@9000000': {'compatible': b'arm,gic-v3\0',
            '#interrupt-cells': cells(3), 'interrupt-controller': b'',
            '#address-cells': cells(2), '#size-cells': cells(2), 'ranges': b'',
            'reg': cells(0, 0x9000000, 0, 0x20000, 0, 0x9080000, 0, 0x80000),
            'interrupts': cells(1, 9, 8)},
        '/timer': {'compatible': b'arm,armv8-timer\0',
                   'interrupts': cells(1, 13, 8, 1, 14, 8, 1, 11, 8, 1, 10, 8),
                   'clock-frequency': cells(25000000)},
        '/serial@1fbf0000': {'compatible': b'ns16550\0',
            'reg': cells(0, 0x1fbf0000, 0, 0x30), 'interrupts': cells(0, 18, 4),
            'clock-frequency': cells(1843200), 'reg-shift': cells(2), 'reg-io-width': cells(4)},
    }
    for name, address, size in [('atf', 0x80000000, 0x200000),
                                ('npu', 0x84000000, 0x100000),
                                ('qdma0', 0x87000000, 0x2000000),
                                ('qdma1', 0x89000000, 0x1000000),
                                ('logs', 0x8b000000, 0x200000)]:
        expected[f'/reserved-memory/{name}@{address:x}'] = {
            'reg': cells(0, address, 0, size), 'no-map': b''}
    gic = nodes['/interrupt-controller@9000000'].get('phandle')
    require(gic is not None and len(gic) == 4, 'Missing GIC phandle')
    expected['/']['interrupt-parent'] = gic
    for path, properties in expected.items():
        actual = {k: v for k, v in nodes[path].items() if k not in ('phandle', 'linux,phandle')}
        extra = {'model'} if path == '/' else set()
        require(set(actual) == set(properties) | extra, 'Unexpected DT properties: ' + path)
        for name, value in properties.items():
            require(actual[name] == value, 'DT resource mismatch: ' + path + ':' + name)
    return {'board': BOARD, 'dt_nodes': len(nodes),
            'compiler_symbol_metadata': '/__symbols__' in nodes, 'storage_controllers': 0,
            'ethernet_controllers': 0, 'dtb_sha256': dtb_sha256}


def audit_config(path, *, allow_native_lan=False):
    config = path.read_text()
    for name in ['MTD_NAND_MTK_BMT', 'MTD_UBI', 'NET_AIROHA', 'NET_AIROHA_NPU',
                 'VB235V_NAND_SCRATCH_TEST', 'VB235V_UBI_NAND_TEST',
                 'VB235V_UBI_RAM_TEST', 'RANDOMIZE_BASE']:
        if allow_native_lan and name in ('NET_AIROHA', 'NET_AIROHA_NPU'):
            continue
        require('CONFIG_' + name + '=y' not in config and 'CONFIG_' + name + '=m' not in config,
                'Unexpected enabled kernel feature: ' + name)
    for name in ['ARM64', 'SERIAL_OF_PLATFORM', 'BLK_DEV_INITRD', 'PROC_FS', 'SYSFS', 'TMPFS']:
        require('CONFIG_' + name + '=y\n' in config, 'Missing kernel feature: ' + name)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_initramfs(archive, *, extra_sources=None):
    require(110 <= len(archive) <= MAX_FIT, 'Initramfs outside its byte budget')
    cursor = 0
    entries = {}
    hardlinks = {}
    while True:
        require(cursor + 110 <= len(archive) and archive[cursor:cursor + 6] == b'070701',
                'Invalid/truncated newc header')
        header = archive[cursor:cursor + 110]
        fields = [int(header[6 + i * 8:14 + i * 8], 16) for i in range(13)]
        inode, mode, uid, gid, links, mtime, size, major, minor, rmajor, rminor, namesize, crc = fields
        cursor += 110
        require(1 <= namesize <= 4096 and cursor + namesize <= len(archive), 'Invalid archive path size')
        name_bytes = archive[cursor:cursor + namesize]
        require(name_bytes[-1:] == b'\0' and b'\0' not in name_bytes[:-1], 'Invalid archive path termination')
        name = name_bytes[:-1].decode('utf8')
        cursor = (cursor + namesize + 3) & ~3
        require(cursor + size <= len(archive), 'Truncated archive entry')
        payload = archive[cursor:cursor + size]
        cursor = (cursor + size + 3) & ~3
        if name == 'TRAILER!!!':
            require(size == 0 and not any(archive[cursor:]), 'Unexpected data after archive trailer')
            break
        require(not name.startswith('/') and '..' not in name.split('/'), 'Unsafe archive path')
        name = posixpath.normpath(name)
        require(name not in entries and len(entries) < 20000 and uid == gid == 0 and crc == 0,
                'Duplicate/oversized/non-root archive entry')
        item = {'mode': mode, 'payload': payload, 'hardlink': (major, minor, inode)}
        entries[name] = item
        if mode & 0o170000 == 0o100000 and links > 1 and size:
            hardlinks[item['hardlink']] = payload

    def resolve(name):
        for _ in range(16):
            parts = name.split('/')
            for index in range(len(parts)):
                prefix = '/'.join(parts[:index + 1])
                item = entries.get(prefix)
                if item and item['mode'] & 0o170000 == 0o120000:
                    target = item['payload'].decode('utf8')
                    target = target.lstrip('/') if target.startswith('/') else posixpath.join(posixpath.dirname(prefix), target)
                    name = posixpath.normpath(posixpath.join(target, *parts[index + 1:]))
                    require(name != '..' and not name.startswith('../'), 'Guest symlink leaves its root')
                    break
            else:
                require(name in entries, 'Missing initramfs entry: ' + name)
                item = entries[name]
                data = item['payload'] or hardlinks.get(item['hardlink'], b'')
                return item, data
        raise ValueError('Initramfs symlink loop')

    required = ['bin/busybox', 'sbin/procd', 'sbin/ubusd', 'sbin/uci', 'sbin/netifd',
                'sbin/rpcd', 'usr/sbin/uhttpd', 'usr/sbin/dropbear']
    verified = {}
    for name in required:
        item, payload = resolve(name)
        require(item['mode'] & 0o170000 == 0o100000 and item['mode'] & 0o111 and
                len(payload) >= 64 and payload[:6] == b'\x7fELF\x02\x01' and
                struct.unpack_from('<H', payload, 18)[0] == 183,
                'Not an executable AArch64 userspace file: ' + name)
        verified[name] = hashlib.sha256(payload).hexdigest()
    item, init = resolve('init')
    require(item['mode'] & 0o111 and
            (init.startswith(b'#!') and b'/sbin/init' in init or init[:4] == b'\x7fELF'),
            'Missing executable full-userspace init')
    item, checker = resolve('usr/sbin/ponwrt-ram-check')
    checker_source = Path(__file__).resolve().parents[1] / 'bringup/m55-ponwrt-system/overlay/target/linux/airoha/vb235v/base-files/usr/sbin/ponwrt-ram-check'
    require(item['mode'] & 0o111 and checker == checker_source.read_bytes(), 'Runtime checker differs from source')
    _, upgrade = resolve('lib/upgrade/platform.sh')
    upgrade_source = checker_source.parents[2] / 'lib/upgrade/platform.sh'
    require(upgrade == upgrade_source.read_bytes(), 'Upgrade rejection hooks differ from source')
    for name, source in (extra_sources or {}).items():
        item, payload = resolve(name)
        require(item['mode'] & 0o111 and payload == source.read_bytes(),
                'Additional initramfs script differs: ' + name)
    return {'entries': len(entries), 'archive_bytes': len(archive),
            'archive_sha256': hashlib.sha256(archive).hexdigest(),
            'required_AArch64_userspace_sha256': verified, 'runtime_checker_matches': True,
            'upgrade_rejection_hooks_match': True,
            'init_sha256': hashlib.sha256(init).hexdigest()}


def audit_fit(data, initramfs=None, *, dtb_auditor=audit_dtb, initramfs_extra_sources=None):
    require(40 <= len(data) <= MAX_FIT, 'FIT length outside RAM upload bounds')
    nodes, _ = parse(data, max_bytes=MAX_FIT)
    confs = nodes.get('/configurations', {})
    name = text(confs.get('default'))
    path = '/configurations/' + name
    require([p for p in nodes if p.startswith('/configurations/')] == [path],
            'Unexpected FIT configurations or signatures')
    conf = nodes.get(path, {})
    require(not {'ramdisk', 'firmware', 'loadables'} & conf.keys(), 'Unexpected extra FIT payload')
    kname = text(conf.get('kernel'))
    dname = text(conf.get('fdt'))
    require(kname != dname, 'Kernel and DT roles overlap')
    images = {p for p in nodes if p.startswith('/images/') and '/' not in p[len('/images/'): ]}
    require(images == {'/images/' + kname, '/images/' + dname}, 'Unexpected FIT images')
    kp, kblob = image_data(nodes, kname, 'kernel')
    dp, dtb = image_data(nodes, dname, 'flat_dt')
    require(text(kp.get('os')) == 'linux' and text(dp.get('compression')) == 'none',
            'Unexpected payload OS/DT compression')
    kernel, memory_bytes = kernel_bytes(kblob, text(kp.get('compression')))
    require(memory_bytes >= len(kernel), 'Image length exceeds its declared memory size')
    load = number(kp.get('load'))
    entry = number(kp.get('entry', kp.get('load')))
    require(load == entry == 0x80200000 and load + memory_bytes <= 0x84000000,
            'Kernel memory overlaps a retained reservation')
    result = dtb_auditor(dtb)
    result.update(fit_bytes=len(data), fit_sha256=hashlib.sha256(data).hexdigest(),
                  kernel_uncompressed_bytes=len(kernel), kernel_memory_bytes=memory_bytes,
                  kernel_load=load, fit_payload_hashes_verified=True,
                  userspace_contents_verified=False, hardware_boot_validated=False,
                  persistent_installation_supported=False)
    if initramfs is not None:
        require(kernel.find(initramfs) >= 0, 'Verified initramfs is not embedded in this FIT kernel')
        result['initramfs'] = audit_initramfs(initramfs, extra_sources=initramfs_extra_sources)
        result['userspace_contents_verified'] = True
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dtb', type=Path)
    parser.add_argument('--fit', type=Path)
    parser.add_argument('--kernel-config', type=Path)
    parser.add_argument('--initramfs', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    require((args.dtb is None) != (args.fit is None), 'Supply exactly one DTB or FIT')
    if args.fit:
        require(args.fit.stat().st_size <= MAX_FIT, 'FIT exceeds size limit')
        if args.initramfs:
            require(args.initramfs.stat().st_size <= MAX_FIT, 'Initramfs exceeds size limit')
        report = audit_fit(args.fit.read_bytes(), args.initramfs.read_bytes() if args.initramfs else None)
    else:
        require(args.dtb.stat().st_size <= 1024 * 1024, 'DTB exceeds size limit')
        report = audit_dtb(args.dtb.read_bytes())
    if args.kernel_config:
        report['kernel_config_sha256'] = audit_config(args.kernel_config)
    encoded = json.dumps(report, indent=2) + '\n'
    if args.output:
        args.output.write_bytes(encoded.encode('utf8'))
    print(encoded)
