# SPDX-License-Identifier: GPL-2.0-only
"""Offline admission checks for the narrowly scoped UART development artifacts.

These checks exclude specified probe paths; they do not prove hardware safety
or authorize booting an image. No device access or binary execution occurs.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from fdt_board_inventory import cells, parse

FORBIDDEN = ('MODULES', 'NET', 'PCI', 'MTD', 'NVMEM', 'BLOCK', 'SPI', 'I2C',
             'GPIOLIB', 'NEW_LEDS', 'INPUT', 'WATCHDOG', 'PINCTRL',
             'RESET_CONTROLLER', 'USB_SUPPORT', 'MMC', 'SCSI', 'ATA', 'SOUND', 'EFI')
REQUIRED = ('ARM64', 'OF', 'PRINTK', 'TTY', 'ARM_GIC_V3', 'ARM_ARCH_TIMER',
            'ARM_PSCI_FW', 'SERIAL_8250', 'SERIAL_8250_CONSOLE', 'SERIAL_OF_PLATFORM',
            'SERIAL_EARLYCON', 'BINFMT_ELF', 'BLK_DEV_INITRD')
BOOTARGS = 'console=ttyS0,115200n8 earlycon=uart8250,mmio32,0x1fbf0000 rdinit=/init panic=0'
RESERVATIONS = {'atf@80000000': [0, 0x80000000, 0, 0x200000],
                'npu-reserved@84000000': [0, 0x84000000, 0, 0x100000],
                'stock-ramoops@8b000000': [0, 0x8b000000, 0, 0x100000],
                'stock-log@8b100000': [0, 0x8b100000, 0, 0x100000]}


def check_config(text):
    values = {}
    for line in text.splitlines():
        match = re.fullmatch(r'CONFIG_([A-Za-z0-9_]+)=(.*)', line)
        if match:
            if match[1] in values:
                raise ValueError('Duplicate config symbol')
            values[match[1]] = match[2]
    enabled = [name for name in FORBIDDEN if values.get(name) in ('y', 'm')]
    enabled.extend(name for name, value in values.items()
                   if name.startswith('POWER_RESET_') and value in ('y', 'm'))
    missing = [name for name in REQUIRED if values.get(name) != 'y']
    if enabled or missing:
        raise ValueError('Config gate failed: forbidden=' + str(enabled) + ', required_missing=' + str(missing))
    initramfs = values.get('INITRAMFS_SOURCE', '')
    if not initramfs.startswith('"') or initramfs in ('', '""'):
        raise ValueError('No embedded initramfs source configured')
    return {'forbidden_subsystems_disabled': list(FORBIDDEN), 'required_symbols_enabled': list(REQUIRED),
            'embedded_initramfs_configured': True}


def check_dtb(data):
    nodes, reserve = parse(data)
    allowed = {'/', '/aliases', '/chosen', '/memory@80000000', '/reserved-memory', '/cpus', '/cpus/cpu@0',
               '/psci', '/interrupt-controller@9000000', '/timer', '/serial@1fbf0000'}
    allowed.update('/reserved-memory/' + name for name in RESERVATIONS)
    if set(nodes) != allowed or reserve:
        raise ValueError('Unexpected/missing DT nodes or reservation-map entries')
    expected_properties = {
        '/': {'model', 'compatible', '#address-cells', '#size-cells', 'interrupt-parent'},
        '/aliases': {'serial0'}, '/chosen': {'stdout-path', 'bootargs'},
        '/memory@80000000': {'device_type', 'reg'},
        '/reserved-memory': {'#address-cells', '#size-cells', 'ranges'},
        '/cpus': {'#address-cells', '#size-cells'},
        '/cpus/cpu@0': {'device_type', 'compatible', 'reg', 'enable-method'},
        '/psci': {'compatible', 'method'},
        '/interrupt-controller@9000000': {'compatible', '#interrupt-cells', 'interrupt-controller',
                                        '#address-cells', '#size-cells', 'ranges', 'reg', 'interrupts', 'phandle'},
        '/timer': {'compatible', 'interrupts', 'clock-frequency'},
        '/serial@1fbf0000': {'compatible', 'reg', 'interrupts', 'clock-frequency', 'reg-shift', 'reg-io-width', 'status', 'phandle'},
    }
    expected_properties.update({'/reserved-memory/' + name: {'reg', 'no-map'} for name in RESERVATIONS})
    for path, properties in nodes.items():
        # DTC emits UART phandle only if needed; aliases may use a path string.
        if set(properties) - expected_properties[path]:
            raise ValueError('Unexpected DT property at ' + path)
    def expect(path, key, value):
        actual = nodes[path].get(key)
        encoded = value.encode() + b'\0' if isinstance(value, str) else b''.join(v.to_bytes(4, 'big') for v in value)
        if actual != encoded:
            raise ValueError('Unexpected DT value: ' + path + ':' + key)
    expect('/', 'compatible', 'tplink,vb235v-v1\0airoha,an7583')
    expect('/', '#address-cells', [2])
    expect('/', '#size-cells', [2])
    expect('/memory@80000000', 'device_type', 'memory')
    expect('/memory@80000000', 'reg', [0, 0x80000000, 0, 0x20000000])
    expect('/chosen', 'bootargs', BOOTARGS)
    expect('/chosen', 'stdout-path', 'serial0:115200n8')
    expect('/aliases', 'serial0', '/serial@1fbf0000')
    for name, value in RESERVATIONS.items():
        expect('/reserved-memory/' + name, 'reg', value)
        if nodes['/reserved-memory/' + name].get('no-map') != b'':
            raise ValueError('Reservation lacks no-map')
    expect('/psci', 'compatible', 'arm,psci-0.2')
    expect('/psci', 'method', 'smc')
    expect('/cpus', '#address-cells', [1])
    expect('/cpus', '#size-cells', [0])
    expect('/cpus/cpu@0', 'reg', [0])
    expect('/cpus/cpu@0', 'enable-method', 'psci')
    expect('/cpus/cpu@0', 'compatible', 'arm,cortex-a53')
    expect('/interrupt-controller@9000000', 'compatible', 'arm,gic-v3')
    expect('/interrupt-controller@9000000', '#interrupt-cells', [3])
    expect('/interrupt-controller@9000000', 'reg', [0, 0x09000000, 0, 0x20000, 0, 0x09080000, 0, 0x80000])
    expect('/interrupt-controller@9000000', 'interrupts', [1, 9, 8])
    expect('/timer', 'compatible', 'arm,armv8-timer')
    expect('/timer', 'interrupts', [1, 13, 8, 1, 14, 8, 1, 11, 8, 1, 10, 8])
    expect('/timer', 'clock-frequency', [25000000])
    expect('/serial@1fbf0000', 'compatible', 'ns16550')
    expect('/serial@1fbf0000', 'reg', [0, 0x1fbf0000, 0, 0x30])
    expect('/serial@1fbf0000', 'interrupts', [0, 18, 4])
    expect('/serial@1fbf0000', 'clock-frequency', [1843200])
    expect('/serial@1fbf0000', 'reg-shift', [2])
    expect('/serial@1fbf0000', 'reg-io-width', [4])
    expect('/serial@1fbf0000', 'status', 'okay')
    gic = cells(nodes['/interrupt-controller@9000000']['phandle'])
    expect('/', 'interrupt-parent', gic)
    return {'exact_uart_only_node_set': True, 'nodes': len(nodes), 'enabled_cpu_nodes': 1,
            'stock_resource_ranges_checked': True, 'no_storage_network_gpio_nodes': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--dtb', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.config.stat().st_size > 1024 * 1024:
        raise ValueError('Config exceeds 1 MiB')
    result = {'config': check_config(args.config.read_text()), 'boot_authorized': False,
              'limitations': 'Static admission checks do not prove hardware safety, current DMA quiescence or recoverability.'}
    if args.dtb:
        if args.dtb.stat().st_size > 1024 * 1024:
            raise ValueError('DTB exceeds 1 MiB')
        data = args.dtb.read_bytes()
        result.update(dtb=check_dtb(data), dtb_sha256=hashlib.sha256(data).hexdigest())
    if args.output:
        with args.output.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
    print('UART DEVELOPMENT STATIC CHECKS PASSED; no hardware actions performed')


if __name__ == '__main__':
    main()
