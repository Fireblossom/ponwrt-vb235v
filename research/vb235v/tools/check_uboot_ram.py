# SPDX-License-Identifier: GPL-2.0-only
"""Check pinned U-Boot outputs and execute the actual RAM HTTP callbacks with mocks.

The native harness uses the pinned upstream SHA-256 implementation. Network,
environment, pbuf, console and allocator failure injection are host mocks. This
does not emulate the SoC, lwIP TCP parser, boot handoff or physical NAND.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile

from fdt_board_inventory import parse


MOCK = r'''
#ifndef RECOVERY_MOCK_H
#define RECOVERY_MOCK_H
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef unsigned long ulong;
typedef uint8_t u8_t;
typedef uint16_t u16_t;
typedef int err_t;
#define ERR_OK 0
#define ERR_ARG -16
#define ERR_MEM -1
#define EBUSY 16
#define EOPNOTSUPP 95
#define ENOMEM 12
#define ENODEV 19
#define ENETDOWN 100
#define ENOLINK 67
#define FS_FILE_FLAGS_HEADER_INCLUDED 1
#define FS_READ_EOF -1
#define CONFIG_HTTPD_SERVER_IP "192.168.0.1"
#define CONFIG_HTTPD_SERVER_NETMASK "255.255.255.0"
struct fs_file { const char *data; int len, index, flags; void *pextension; };
struct pbuf { u16_t tot_len; const void *payload; };
struct udevice { int dummy; };
struct netif { int dummy; };
static struct udevice device;
static struct netif interface;
static int freed, short_copy, fail_alloc, fail_env, eth_error, no_netif;
static int rx_error, ctrl_polls, stop_count, fs_calls;
static ulong file_address, file_size;
static size_t strlcpy(char *d, const char *s, size_t n) {
 size_t z=strlen(s); if(n){size_t c=z<n-1?z:n-1;memcpy(d,s,c);d[c]=0;}return z;
}
static void *mock_malloc(size_t n) { return fail_alloc ? NULL : malloc(n); }
static int env_set(const char *key, const char *value) {
 if(fail_env && value)return -1;
 if(!strcmp(key,"fileaddr")&&!value)file_address=0;
 if(!strcmp(key,"filesize")&&!value)file_size=0;
 return 0;
}
static int env_set_hex(const char *key, ulong value) {
 if(fail_env)return -1;
 if(!strcmp(key,"fileaddr"))file_address=value;
 if(!strcmp(key,"filesize"))file_size=value;
 return 0;
}
static void pbuf_free(struct pbuf *p) { freed++; }
static u16_t pbuf_copy_partial(const struct pbuf *p, void *out,u16_t n,u16_t off) {
 if(short_copy && n)n--;
 memcpy(out,(const char *)p->payload+off,n);return n;
}
static int net_lwip_eth_start(void) {return eth_error;}
static void net_lwip_eth_stop(void) {stop_count++;}
static struct udevice *eth_get_dev(void) {return &device;}
static struct netif *net_lwip_new_netif(struct udevice *d) {
 return no_netif ? NULL : &interface;
}
static void net_lwip_remove_netif(struct netif *n) {}
static int net_lwip_rx(struct udevice *d,struct netif *n) {return rx_error;}
static int ctrlc(void) {return ++ctrl_polls>=2;}
static void clear_ctrlc(void) {}
static void httpd_init(void) {fs_calls++;}
static void httpd_stop(void) {}
#endif
'''

HARNESS = r'''
#include "mock.h"
#define malloc mock_malloc
#include "backend.c"
#undef malloc

static char uri[64];
static u8_t wnd;
static int cases, checks;
#define CHECK(v) do {checks++; if(!(v)){fprintf(stderr,"line %d: %s\n",__LINE__,#v);exit(1);}}while(0)
#define CASE() do {cases++;}while(0)
static void reset(void) {
 free(upload_buffer); upload_buffer=NULL; upload_connection=NULL;
 upload_ready=upload_expected=upload_received=0;upload_failed=false;
 upload_hash[0]=0;file_address=file_size=0;
 fail_alloc=fail_env=short_copy=eth_error=no_netif=rx_error=0;
 freed=ctrl_polls=stop_count=fs_calls=0;running=false;
}
static err_t begin(void *c,const char *path,int len) {
 return httpd_post_begin(c,path,"",0,len,uri,sizeof(uri),&wnd);
}
static err_t receive(void *c,const void *d,u16_t len) {
 struct pbuf p={len,d};return httpd_post_receive_data(c,&p);
}
static void finish(void *c) {httpd_post_finished(c,uri,sizeof(uri));}
static void get(const char *path,const char *text) {
 struct fs_file f={0}; CHECK(fs_open_custom(&f,path)==1);
 CHECK(f.index==f.len);CHECK(f.flags==FS_FILE_FLAGS_HEADER_INCLUDED);
 CHECK(strstr(f.data,text));CHECK(fs_read_custom(&f,NULL,0)==FS_READ_EOF);
 fs_close_custom(&f);CHECK(!f.pextension);
}
int main(void) {
 void *a=(void *)1,*b=(void *)2;
 const char *blocked[]={"/api/task","/api/env","/api/upload-all-flash",
  "/api/flash","/api/nand-scrub","/api/ubi-rebuild","/api/command",
  "/api/flash-bl2","/api/flash-uboot","/api/download/1","/unknown"};
 reset(); CASE();get("/","内存恢复开发版");
 CASE();get("/api/device","\"flash\":false");
 CASE();get("/api/status","\"ready\":false");
 for(unsigned i=0;i<sizeof(blocked)/sizeof(blocked[0]);i++) {
  CASE(); CHECK(begin(a,blocked[i],3)==ERR_ARG);
  get(blocked[i],"400 Error"); CHECK(!upload_connection&&!upload_buffer);
 }
 int lengths[]={-1,0,16777217,2147483647};
 for(unsigned i=0;i<sizeof(lengths)/sizeof(lengths[0]);i++) {
  CASE();CHECK(begin(a,"/api/upload",lengths[i])==ERR_ARG);
  CHECK(!upload_connection&&!upload_buffer);
 }
 CASE();CHECK(begin(NULL,"/api/upload",3)==ERR_ARG);
 CASE();fail_alloc=1;CHECK(begin(a,"/api/upload",3)==ERR_MEM);
 CHECK(!upload_connection&&!upload_buffer);fail_alloc=0;
 CASE();CHECK(begin(a,"/api/upload",3)==ERR_OK);CHECK(wnd==1);
 CHECK(begin(b,"/api/upload",4)==ERR_ARG);CHECK(upload_connection==a);
 CASE();CHECK(receive(b,"xxx",3)==ERR_ARG);CHECK(upload_received==0&&freed==1);
 CASE();finish(b);CHECK(upload_connection==a&&upload_ready==0);
 CASE();CHECK(receive(a,"a",1)==ERR_OK);CHECK(receive(a,"bc",2)==ERR_OK);
 CHECK(upload_received==3&&!memcmp(upload_buffer,"abc",3));finish(a);
 CHECK(upload_ready==3&&file_size==3&&file_address==(ulong)upload_buffer);
 CHECK(!strcmp(upload_hash,"ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"));
 CHECK(!strcmp(uri,"/api/status"));get("/api/status",upload_hash);
 CASE();CHECK(begin(a,"/api/upload",4)==ERR_OK);
 CHECK(!upload_ready&&!file_size&&!file_address&&!upload_hash[0]);
 CHECK(receive(a,"abc",3)==ERR_OK);finish(a);
 CHECK(!upload_ready&&!strcmp(uri,"/api/error"));
 CASE();CHECK(begin(a,"/api/upload",3)==ERR_OK);
 CHECK(receive(a,"abcd",4)==ERR_ARG);CHECK(upload_received==0);
 CHECK(receive(a,"abc",3)==ERR_ARG);finish(a);CHECK(!upload_ready);
 CASE();CHECK(begin(a,"/api/upload",3)==ERR_OK);short_copy=1;
 CHECK(receive(a,"abc",3)==ERR_ARG);finish(a);CHECK(!upload_ready);short_copy=0;
 CASE();CHECK(begin(a,"/api/upload",3)==ERR_OK);
 CHECK(httpd_post_receive_data(a,NULL)==ERR_ARG);finish(a);CHECK(!upload_ready);
 CASE();CHECK(receive(a,"abc",3)==ERR_ARG);
 CASE();finish(a);CHECK(!upload_ready&&!strcmp(uri,"/api/error"));
 CASE();CHECK(begin(a,"/api/upload",3)==ERR_OK);CHECK(receive(a,"abc",3)==ERR_OK);
 fail_env=1;finish(a);CHECK(!upload_ready&&!upload_hash[0]&&!file_size);fail_env=0;
 CASE();CHECK(begin(a,"/api/upload",16777216)==ERR_OK);
 memset(upload_buffer,0,16777216);upload_received=16777216;finish(a);
 CHECK(upload_ready==16777216);
 CHECK(!strcmp(upload_hash,"080acf35a507ac9849cfcba47dc2ad83e01b75663a516279c8b9d243b719643e"));
 reset();CASE();CHECK(uboot_httpd_start(true)==-EOPNOTSUPP);CHECK(!running&&!fs_calls);
 CASE();running=true;CHECK(uboot_httpd_start(false)==-EBUSY);running=false;
 CASE();fail_env=1;CHECK(uboot_httpd_start(false)==-ENOMEM);CHECK(!fs_calls);fail_env=0;
 CASE();eth_error=-ENODEV;CHECK(uboot_httpd_start(false)==-ENODEV);CHECK(!fs_calls);
 reset();CASE();no_netif=1;CHECK(uboot_httpd_start(false)==-ENODEV);CHECK(stop_count==1);
 reset();CASE();rx_error=-ENETDOWN;CHECK(uboot_httpd_start(false)==0);
 CHECK(!running&&stop_count==1&&fs_calls==1);
 reset();CASE();rx_error=-ENOLINK;CHECK(uboot_httpd_start(false)==0);CHECK(!running);
 reset();CASE();rx_error=-123;CHECK(uboot_httpd_start(false)==-123);CHECK(!running);
 reset();CASE();CHECK(begin(a,"/api/upload",3)==ERR_OK);
 CHECK(uboot_httpd_start(false)==0);CHECK(!upload_connection&&!upload_ready);
 reset();CASE();CHECK(begin(a,"/api/upload",3)==ERR_OK);
 CHECK(receive(a,"abc",3)==ERR_OK);finish(a);CHECK(uboot_httpd_start(false)==0);
 CHECK(upload_ready==3&&file_size==3); /* completed data survives service exit */
 reset();printf("RESULT cases=%d checks=%d\n",cases,checks);return 0;
}
'''


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_source(source, manifest):
    revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'],
                                       text=True).strip()
    if revision != manifest['commit']:
        raise ValueError('Unexpected source revision')
    status = subprocess.check_output(['git', '-C', str(source), 'status',
                                      '--porcelain=v1', '--untracked-files=all', '-z'])
    rows = [row.decode() for row in status.split(b'\0') if row]
    if (any('R' in row[:2] or 'C' in row[:2] for row in rows) or
            {row[3:] for row in rows} != set(manifest['patch_files'])):
        raise ValueError('Source changes differ from the reviewed patch scope')
    for name, expected in manifest['source_sha256'].items():
        if digest(source / name) != expected:
            raise ValueError('Source differs from reviewed input: ' + name)


def native_check(source):
    with tempfile.TemporaryDirectory(prefix='vb235v-ram-test-') as directory:
        root = Path(directory)
        (root / 'mock.h').write_text(MOCK)
        (root / 'main.c').write_text(HARNESS)
        shutil.copyfile(source / 'net/lwip/httpd-ram.c', root / 'backend.c')
        for header in ('command.h', 'console.h', 'env.h', 'malloc.h', 'net.h',
                       'net-lwip.h', 'net/httpd.h', 'lwip/apps/fs.h',
                       'lwip/apps/httpd.h', 'lwip/pbuf.h'):
            path = root / header
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('#include "mock.h"\n')
        for header, contents in {
            'linux/types.h': '#include <stdint.h>\n',
            'linux/errno.h': '#define EOPNOTSUPP 95\n',
            'linux/kconfig.h': '#define CONFIG_IS_ENABLED(x) 0\n',
            'linux/compiler_attributes.h':
                '#define __weak __attribute__((weak))\n#define __always_unused __attribute__((unused))\n',
        }.items():
            path = root / header
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents)
        (root / 'u-boot').mkdir()
        shutil.copyfile(source / 'include/u-boot/sha256.h', root / 'u-boot/sha256.h')
        command = ['cc', '-std=gnu11', '-O1', '-g', '-DUSE_HOSTCC',
                   '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                   '-I', str(root), str(root / 'main.c'),
                   str(source / 'lib/sha256.c'), str(source / 'lib/sha256_common.c'),
                   '-o', str(root / 'test')]
        compile_result = subprocess.run(command, capture_output=True, text=True)
        if compile_result.returncode:
            raise RuntimeError('Native compile failed:\n' + compile_result.stderr[-6000:])
        result = subprocess.run([str(root / 'test')], capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError('Native harness failed:\n' + result.stdout[-1000:] + result.stderr[-6000:])
        found = re.search(r'RESULT cases=(\d+) checks=(\d+)', result.stdout)
        if not found:
            raise ValueError('Missing native harness result')
        return {'cases': int(found[1]), 'assertions': int(found[2]),
                'asan_ubsan': True, 'sha256': 'pinned upstream implementation',
                'hardware_emulated': False}


def check_build(directory, mode):
    config = dict(line.split('=', 1) for line in (directory / '.config').read_text().splitlines()
                  if line.startswith('CONFIG_') and '=' in line)
    required = {'CONFIG_ENV_IS_NOWHERE': 'y', 'CONFIG_VB235V_RAM_RECOVERY': 'y',
                'CONFIG_BOOTDELAY': '-1', 'CONFIG_TEXT_BASE': '0x81e00000',
                'CONFIG_SYS_MALLOC_LEN': '0x2000000',
                'CONFIG_LINUX_KERNEL_IMAGE_HEADER': 'y',
                'CONFIG_LNX_KRNL_IMG_TEXT_OFFSET_BASE': '0x80000000'}
    if mode == 'net':
        required.update(CONFIG_CMD_HTTPD='y', CONFIG_HTTPD_RAM_RECOVERY='y',
                        CONFIG_NET_LWIP='y')
    for key, value in required.items():
        if config.get(key) != value:
            raise ValueError('Unexpected ' + key)
    forbidden = ('MTD', 'SPI', 'MMC', 'PCI', 'USB', 'WDT', 'WATCHDOG', 'BUTTON',
                 'LED', 'AIROHA_HTTP_RECOVERY', 'AIROHA_UBI_ENV', 'CMD_SAVEENV',
                 'CMD_ERASEENV', 'CMD_FLASH', 'CMD_SF', 'CMD_MTD', 'CMD_NAND', 'CMD_UBI',
                 'HTTPD_DHCP_SERVER')
    if mode == 'serial':
        forbidden += ('NET', 'DM_GPIO', 'PINCTRL')
    for key in forbidden:
        if config.get('CONFIG_' + key) == 'y':
            raise ValueError('Forbidden configuration: ' + key)
    env_backends = {k for k, v in config.items() if k.startswith('CONFIG_ENV_IS_IN_') and v == 'y'}
    if env_backends:
        raise ValueError('Persistent environment selected')
    functions = set()
    for row in (directory / 'u-boot.sym').read_text().splitlines():
        fields = row.split()
        if len(fields) >= 6 and fields[2] == 'F':
            functions.add(fields[-1])
    forbidden_functions = [s for s in functions if
                           re.match(r'(?:mtd_|ubi_|nand_|spinand_|spi_flash_|do_saveenv|env_save$)', s)]
    if forbidden_functions:
        raise ValueError('Storage functions linked: ' + str(forbidden_functions))
    if mode == 'net' and 'lwip_httpd_fs_open_custom' not in functions:
        raise ValueError('RAM backend not linked')
    nodes, _ = parse((directory / 'u-boot.dtb').read_bytes())
    binary = (directory / 'u-boot.bin').read_bytes()
    offset, image_size = struct.unpack_from('<QQ', binary, 8)
    if (binary[56:60] != b'ARM\x64' or offset != 0x1e00000 or
            image_size < len(binary) or image_size > 0x200000):
        raise ValueError('Invalid ARM64 Linux-compatible header')
    if nodes['/memory@80000000']['reg'].hex() != '00000000800000000000000020000000':
        raise ValueError('Unexpected DRAM geometry')
    reservations = {'atf@80000000': (0x80000000, 0x200000),
                    'npu@84000000': (0x84000000, 0x100000),
                    'logs@8b000000': (0x8b000000, 0x200000)}
    for name, (address, size) in reservations.items():
        properties = nodes['/reserved-memory/' + name]
        if properties.get('reg') != struct.pack('>QQ', address, size) or 'no-map' not in properties:
            raise ValueError('Unexpected reserved-memory region: ' + name)
    if mode == 'serial':
        compatible_nodes = {p for p, v in nodes.items() if 'compatible' in v}
        if compatible_nodes != {'/', '/psci', '/timer', '/serial@1fbf0000'}:
            raise ValueError('Unexpected serial-only device inventory')
    else:
        for path in ('/soc/spi@1fa10000', '/soc/mmc@1fa0e000', '/soc/pcs@1fa08000',
                     '/soc/pcs@1fa09000', '/soc/ethernet@1fb50000/ethernet@2',
                     '/soc/ethernet@1fb50000/ethernet@3'):
            if nodes[path].get('status') != b'disabled\0':
                raise ValueError('Unexpected enabled node: ' + path)
        if any(p.startswith('/buttons') or p.startswith('/leds') for p in nodes):
            raise ValueError('Board button/LED nodes should be absent')
    return {'mode': mode, 'binary_bytes': (directory / 'u-boot.bin').stat().st_size,
            'binary_sha256': digest(directory / 'u-boot.bin'),
            'dtb_sha256': digest(directory / 'u-boot.dtb'),
            'config_sha256': digest(directory / '.config'),
            'storage_function_count': len(forbidden_functions),
            'arm64_text_offset': offset, 'arm64_image_size': image_size,
            'dt_nodes': len(nodes), 'compiled': True, 'hardware_booted': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--serial-build', type=Path, required=True)
    parser.add_argument('--net-build', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    manifest_path = Path(__file__).resolve().parents[1] / 'findings/uboot-ram-source.json'
    manifest = json.loads(manifest_path.read_text())
    verify_source(args.source, manifest)
    report = {'source_hashes_checked': len(manifest['source_sha256']),
              'native_http': native_check(args.source),
              'builds': [check_build(args.serial_build, 'serial'),
                         check_build(args.net_build, 'net')],
              'flashable': False, 'hardware_access': False}
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
