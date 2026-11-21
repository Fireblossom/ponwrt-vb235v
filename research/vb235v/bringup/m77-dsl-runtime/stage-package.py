#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Stage authored userspace package sources into a NEW directory; no hardware IO."""
from pathlib import Path
import argparse
import shutil
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('destination',type=Path)
a=p.parse_args()
here=Path(__file__).resolve().parent
dest=a.destination.resolve()
if dest.exists():
    raise SystemExit('Destination must not already exist')
dest.mkdir(parents=True)
(dest/'src').mkdir()
for name in ['core.c','core.h','sha256.c','provider.c','provider.h','provider_uapi.h','runtime.c']:
    shutil.copyfile(here/name,dest/'src'/name)
shutil.copyfile(here/'openwrt-package.mk',dest/'Makefile')
for name in ['ponwrt-dsl.init','ponwrt-dsl.config']:
    shutil.copyfile(here/name,dest/name)
print('Staged disabled-by-default userspace package; firmware and kernel provider excluded')
