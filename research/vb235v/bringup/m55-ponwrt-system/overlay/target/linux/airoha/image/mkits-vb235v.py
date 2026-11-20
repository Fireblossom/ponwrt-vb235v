#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Describe this board's inline RAM FIT using SHA256 hashes only."""
import argparse
from pathlib import Path
import re


def fit_path(path):
    value = path.resolve(strict=True).as_posix()
    if not re.fullmatch(r'/[A-Za-z0-9_./+~@-]+', value):
        raise ValueError('FIT build paths must use ordinary ASCII characters without spaces')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kernel', type=Path)
    parser.add_argument('dtb', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    kernel, dtb = fit_path(args.kernel), fit_path(args.dtb)
    if not 1 <= args.kernel.stat().st_size <= 56 * 1024 * 1024:
        raise ValueError('Kernel payload exceeds the RAM upload budget')
    if not 40 <= args.dtb.stat().st_size <= 1024 * 1024:
        raise ValueError('Invalid DTB size')
    args.output.write_text('''/dts-v1/;
/ {
 description = "TP-LinkBox 7 VB235v PonWrt RAM development";
 #address-cells = <1>;
 images {
  kernel {
   description = "ARM64 Linux with embedded PonWrt initramfs";
   data = /incbin/("KERNEL_PATH");
   type = "kernel"; arch = "arm64"; os = "linux"; compression = "lzma";
   load = <0x80200000>; entry = <0x80200000>;
   hash-1 { algo = "sha256"; };
  };
  fdt {
   data = /incbin/("DTB_PATH");
   type = "flat_dt"; arch = "arm64"; compression = "none";
   hash-1 { algo = "sha256"; };
  };
 };
 configurations {
  default = "config-1";
  config-1 { kernel = "kernel"; fdt = "fdt"; };
 };
};
'''.replace('KERNEL_PATH', kernel).replace('DTB_PATH', dtb), encoding='ascii')


if __name__ == '__main__':
    main()
