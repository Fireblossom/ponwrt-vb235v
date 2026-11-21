#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Offline OEM arithmetic model. Reads recorded JSON, never hardware or sysfs.

This models the manufacturer's fixed-coefficient AN7583 temperature formula;
it does not establish per-die calibration accuracy or validate a sampler.
"""
import argparse
import json

SENSORS = (
    {'logical_id': 0, 'name': 'BGP', 'mux': 0, 'bg_coeff_x100': 973, 'gain': 7440, 'offset_c': 294},
    {'logical_id': 1, 'name': 'GBE', 'mux': 5, 'bg_coeff_x100': 995, 'gain': 7620, 'offset_c': 298},
    {'logical_id': 2, 'name': 'CPU', 'mux': 6, 'bg_coeff_x100': 1035, 'gain': 8390, 'offset_c': 344},
)

def trunc_div(numerator, denominator):
    """C integer division toward zero without floating point rounding."""
    if denominator == 0:
        raise ValueError('zero denominator')
    sign = -1 if (numerator < 0) != (denominator < 0) else 1
    return sign * (abs(numerator) // abs(denominator))

def unsigned32(value, name):
    if type(value) is not int or not 0 <= value <= 0xffffffff:
        raise ValueError(name+' must be a recorded unsigned 32-bit integer')
    return value

def temperature(snapshot):
    if not isinstance(snapshot, dict):
        raise ValueError('record must be a JSON object')
    logical_id = snapshot.get('logical_sensor')
    if type(logical_id) is not int or not 0 <= logical_id < len(SENSORS):
        raise ValueError('logical_sensor is 0/1/2, never a raw mux value 5/6')
    sensor = SENSORS[logical_id]
    if snapshot.get('mux') != sensor['mux']:
        raise ValueError('recorded mux and logical sensor do not match')
    # A valid record must come from one serialized Zero/D0/D1 transaction.
    # This assertion is caller metadata, not a hardware-attestation mechanism.
    if snapshot.get('serialized_triplet') is not True:
        raise ValueError('no complete serialized Zero/D0/D1 transaction')
    zero = unsigned32(snapshot.get('zero'), 'zero')
    d0 = unsigned32(snapshot.get('d0'), 'd0')
    d1 = unsigned32(snapshot.get('d1'), 'd1')
    delta = d1-d0
    denominator = trunc_div(delta*sensor['bg_coeff_x100'], 100)+(zero-d1)
    if delta <= 0 or denominator <= 0:
        raise ValueError('nonpositive diode delta/denominator: invalid diagnostic sample')
    # Python integers model a proposed signed-64-bit implementation, avoiding
    # the original kernel's unchecked signed-32-bit product overflow.
    if abs(delta*sensor['gain']*10) > 0x7fffffffffffffff:
        raise ValueError('64-bit product overflow')
    temp_x10 = trunc_div(sensor['gain']*delta*10, denominator)-sensor['offset_c']*10
    mc = temp_x10*100
    # This is a diagnostic plausibility filter, not a specified chip rating.
    if not -40000 <= mc <= 150000:
        raise ValueError('converted temperature outside diagnostic plausibility window')
    return {'temperature_mC': mc, 'sensor': sensor['name'], 'mux': sensor['mux'],
            'calibration': 'OEM-fixed-coefficients; per-die accuracy unverified',
            'source': 'recorded-three-point-ratio', 'delta': delta,
            'denominator': denominator, 'hardware_validated': False}

def calibrated_voltage(raw_adc, efuse_word):
    """Offline AVS voltage model; deliberately rejects uncalibrated fallback."""
    raw_adc = unsigned32(raw_adc, 'raw_adc')
    efuse_word = unsigned32(efuse_word, 'efuse_word')
    if efuse_word in (0, 0xffffffff):
        raise ValueError('missing AVS two-point EFUSE calibration')
    low = (efuse_word & 0xffff) >> 4
    high = (efuse_word >> 16) >> 4
    if not low or high <= low:
        raise ValueError('invalid AVS two-point EFUSE ordering')
    slope = ((1000000 // (high-low))+5)//10
    if not slope:
        raise ValueError('invalid AVS slope')
    adc = raw_adc >> 4
    if adc <= low:
        raise ValueError('ADC does not exceed low calibration code')
    mv = ((adc-low)*slope+50000+50)//100
    return {'voltage_mV': mv, 'calibration': 'OEM-two-point-EFUSE',
            'low_code_shift4': low, 'high_code_shift4': high,
            'slope_0_01mV_per_shifted_code': slope, 'hardware_validated': False}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('record', type=argparse.FileType('r', encoding='utf-8'))
    a = p.parse_args()
    print(json.dumps(temperature(json.load(a.record)), indent=2))

if __name__ == '__main__':
    main()
