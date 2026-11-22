#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Offline exact ns16550 divisor and minimum line-time calculator; no serial IO."""
import argparse
import json

CLOCK=1843200
def calculate(baud, size=0):
    assert type(baud) is int and baud>0
    divisor=(CLOCK+8*baud)//(16*baud)
    actual=CLOCK/(16*divisor) if divisor else None
    return {'requested_baud':baud,'clock_hz':CLOCK,'divisor':divisor,
            'actual_baud':actual,'error_percent':None if actual is None else 100*(actual-baud)/baud,
            'usable_without_clock_change':actual==baud,
            'payload_bytes':size,'minimum_8N1_seconds':None if not actual else size*10/actual}
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bytes',type=int,default=0)
    a=p.parse_args();assert a.bytes>=0
    print(json.dumps([calculate(b,a.bytes) for b in (115200,230400,460800,921600)],indent=2))
