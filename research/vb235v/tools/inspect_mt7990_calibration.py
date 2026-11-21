#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Inspect only native-driver fields in a verified private VB235v ART backup."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

SIZE = 7680
OFFSET = 0x40000


def inspect(art, expected):
    if len(art) != 0x380000 or hashlib.sha256(art).hexdigest() != expected:
        raise ValueError('Private ART backup size/hash does not match the supplied trusted anchor')
    data = art[OFFSET:OFFSET+SIZE]
    if len(data) != SIZE or struct.unpack_from('<H', data)[0] != 0x7993:
        raise ValueError('Expected MT7990/MT7993 EEPROM header absent')
    conf = data[0x190:0x198]
    bands = [
        {'band_index':0, 'band_selector':conf[0] & 7, 'tx_paths':(conf[1] >> 3) & 7,
         'rx_paths':conf[3] & 7, 'spatial_streams':(conf[4] >> 3) & 7, 'PA_LNA_selector':conf[6] & 3},
        {'band_index':1, 'band_selector':(conf[0] >> 3) & 7, 'tx_paths':conf[2] & 7,
         'rx_paths':(conf[3] >> 3) & 7, 'spatial_streams':conf[5] & 7, 'PA_LNA_selector':conf[7] & 3},
    ]
    for band in bands:
        if not 1 <= band['tx_paths'] <= 4 or not 1 <= band['rx_paths'] <= 4 or not 1 <= band['spatial_streams'] <= min(band['tx_paths'], band['rx_paths']):
            raise ValueError('EEPROM path/stream fields are inconsistent with the native parser')
    if [b['band_selector'] for b in bands] != [1, 2]:
        raise ValueError('Expected dual-band 2.4/5 GHz selection absent')
    return data, {'classification':'private ART field inspection; RF calibration not yet validated on hardware',
                  'ART_sha256':expected, 'ART_bytes':len(art), 'ART_relative_offset':OFFSET,
                  'EEPROM_bytes':SIZE, 'EEPROM_sha256':hashlib.sha256(data).hexdigest(),
                  'chip_id':'0x7993', 'EEPROM_version':struct.unpack_from('<H', data, 2)[0],
                  'bands':bands, 'MAC_addresses_exported':False, 'raw_calibration_exported':False,
                  'radio_tested':False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--art', type=Path, required=True)
    p.add_argument('--art-sha256', required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--private-eeprom', type=Path)
    args = p.parse_args()
    if args.art.stat().st_size != 0x380000:
        raise ValueError('Unexpected ART size')
    data, report = inspect(args.art.read_bytes(), args.art_sha256)
    if args.private_eeprom:
        with args.private_eeprom.open('xb') as stream:
            stream.write(data)
    args.output.write_bytes((json.dumps(report, indent=2)+'\n').encode())
    print('Verified private ART EEPROM header and dual-band fields; MAC addresses and calibration contents omitted.')


if __name__ == '__main__':
    main()
