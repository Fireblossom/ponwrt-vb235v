# SPDX-License-Identifier: GPL-2.0-only
"""Compare a small, explicit mailbox control contract from private source copies.

No preprocessor, kernel ABI, payload equivalence or hardware execution is inferred.
Unsupported enum expressions are rejected rather than evaluated as Python code.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re


def enum_values(text, needle):
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    blocks = [body for body in re.findall(r'\benum(?:\s+[A-Za-z_][A-Za-z0-9_]*)?\s*\{([^{}]*)\}', text)
              if re.search(r'\b' + re.escape(needle) + r'\b', body)]
    if len(blocks) != 1:
        raise ValueError('Enum not uniquely located: ' + needle)
    result, next_value = {}, 0
    for item in blocks[0].split(','):
        item = item.strip()
        if not item:
            continue
        match = re.fullmatch(r'([A-Za-z_][A-Za-z0-9_]*)(?:\s*=\s*(0[xX][0-9a-fA-F]+|[0-9]+))?', item)
        if not match or match[1] in result:
            raise ValueError('Unsupported/duplicate enum entry')
        value = int(match[2], 0) if match[2] else next_value
        result[match[1]] = value
        next_value = value + 1
    return result


def vendor_argument_masks(header):
    matches = re.findall(r'typedef\s+union\s*\{\s*struct\s*\{([^{}]*)\}\s*bits\s*;\s*unsigned\s+short\s+hWord\s*;\s*\}\s*mboxArg_t\s*;', header, re.S)
    if len(matches) != 1:
        raise ValueError('Argument union not uniquely located')
    body = re.sub(r'/\*.*?\*/|//[^\n]*', '', matches[0], flags=re.S)
    fields = re.findall(r'unsigned\s+short\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(\d+)\s*;', body)
    remainder = re.sub(r'unsigned\s+short\s+[A-Za-z_][A-Za-z0-9_]*\s*:\s*\d+\s*;', '', body)
    if remainder.strip() or not fields:
        raise ValueError('Unsupported argument bitfield declaration')
    masks, offset = {}, 0
    for name, width in fields:
        width = int(width)
        if not width or offset + width > 16 or name in masks:
            raise ValueError('Invalid argument bitfield')
        masks[name] = ((1 << width) - 1) << offset
        offset += width
    return masks


def modern_masks(source):
    masks = {}
    for name, kind, first, second in re.findall(
            r'^#define\s+(MBOX_MSG_[A-Z_]+)\s+(BIT|GENMASK)\(\s*(\d+)\s*(?:,\s*(\d+)\s*)?\)\s*$', source, re.M):
        first = int(first)
        if name in masks or first > 15:
            raise ValueError('Invalid/duplicate modern argument mask')
        if kind == 'BIT' and not second:
            masks[name] = 1 << first
        elif kind == 'GENMASK' and second and int(second) <= first:
            masks[name] = ((1 << (first + 1)) - 1) ^ ((1 << int(second)) - 1)
        else:
            raise ValueError('Unsupported bit mask')
    return masks


def compare(header, source):
    vendor = enum_values(header, 'MFUNC_WIFI')
    modern = enum_values(source, 'NPU_FUNC_WIFI')
    pairs = [('MFUNC_WIFI', 'NPU_FUNC_WIFI'), ('MFUNC_TUNNEL', 'NPU_FUNC_TUNNEL'),
             ('MFUNC_NOTIFY', 'NPU_FUNC_NOTIFY'), ('MFUNC_DBA', 'NPU_FUNC_DBA'),
             ('MFUNC_TR471', 'NPU_FUNC_TR471'), ('MFUNC_HWNAT', 'NPU_FUNC_PPE')]
    selectors = [{'stock_name': a, 'ponwrt_name': b, 'stock': vendor[a], 'ponwrt': modern[b],
                  'equal_numeric_selector': vendor[a] == modern[b]} for a, b in pairs]
    vendor_masks, current_masks = vendor_argument_masks(header), modern_masks(source)
    pairs = [('block_mode', 'MBOX_MSG_WAIT_RSP'), ('done_bit', 'MBOX_MSG_DONE'),
             ('ret_status', 'MBOX_MSG_STATUS'), ('static_buff', 'MBOX_MSG_STATIC_BUF'),
             ('func_id', 'MBOX_MSG_FUNC_ID')]
    masks = [{'stock_field': a, 'ponwrt_mask': b, 'stock': vendor_masks[a], 'ponwrt': current_masks[b],
              'equal_numeric_mask': vendor_masks[a] == current_masks[b]} for a, b in pairs]
    return {'function_selectors': selectors, 'control_masks': masks,
            'all_selected_numeric_fields_equal': all(row['equal_numeric_selector'] for row in selectors)
                and all(row['equal_numeric_mask'] for row in masks),
            'not_established': ['Wi-Fi/PPE payload layout and selector compatibility', 'DMA buffer ownership and coherency',
                                'callback/lifetime/timeout compatibility', 'stock firmware support in PonWrt',
                                'successful mailbox traffic or acceleration']}


def read_source(path):
    if path.stat().st_size > 1024 * 1024:
        raise ValueError('Source exceeds 1 MiB')
    return path.read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stock_header', type=Path)
    parser.add_argument('ponwrt_npu_source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    header, source = read_source(args.stock_header), read_source(args.ponwrt_npu_source)
    result = compare(header.decode(), source.decode())
    result['input_sha256'] = {'stock_header': hashlib.sha256(header).hexdigest(), 'ponwrt_source': hashlib.sha256(source).hexdigest()}
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps({'all_selected_numeric_fields_equal': result['all_selected_numeric_fields_equal']}))


if __name__ == '__main__':
    main()
