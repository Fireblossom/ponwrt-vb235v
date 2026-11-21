#!/usr/bin/env python3
"""Exercise the unchanged private loader with synthetic, non-private bytes."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

source, out = map(Path, sys.argv[1:3])
out.mkdir(parents=True,exist_ok=True)
text=(source/'mt7996/eeprom.c').read_text()
start=text.index('static int mt7996_vb235v_development_calibration(')
end=text.index('\nstatic int mt7996_eeprom_load(',start)
function=text[start:end]
header=(source/'mt7996/mt7996.h').read_text()
eeprom=(source/'mt7996/eeprom.h').read_text()
assert re.search(r'MT7996_EEPROM_SIZE\s+7680\b',header)
assert re.search(r'MT7990_DEVICE_ID\s+0x7993\b',header)
assert re.search(r'MT_EE_WIFI_CONF\s*=\s*0x190\b',eeprom)
c=r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
typedef uint8_t u8;
#define MT7996_EEPROM_SIZE 7680
#define MT7990_DEVICE_ID 0x7993
#define MT7996_FEM_INT 1
#define MT_EE_WIFI_CONF 0x190
#define EEPROM_MODE_FLASH 3
struct firmware { size_t size; const u8 *data; };
struct mt7996_dev { struct {struct {u8 *data;} eeprom;void *dev;} mt76;struct {int fem;} var;int eeprom_mode; };
static struct firmware fw;
static int request_error,releases,logs;
static bool chip_valid=true;
static bool is_mt7990(void *d) {(void)d;return chip_valid;}
static int request_firmware(const struct firmware **p,const char *name,void *d) {
    (void)d;assert(strcmp(name,"vb235v/mt7990-board-eeprom.bin")==0);
    if(request_error)return request_error;*p=&fw;return 0;
}
static void release_firmware(const struct firmware *p) {assert(p==&fw);releases++;}
static unsigned get_unaligned_le16(const u8 *p) {return p[0]|(p[1]<<8);}
#define dev_info(d,...) ((void)(d),logs++)
/* ACTUAL_FUNCTION */
int main(void) {
    const u8 conf[8]={0x11,0x10,0x03,0x1a,0x10,0x02,0x08,0x08};
    const size_t sizes[]={0,1,2,0x190,0x197,7679,7680,7681,8192};
    int cases=0;
    for(size_t i=0;i<sizeof(sizes)/sizeof(sizes[0]);i++)for(int bad=0;bad<10;bad++) {
        size_t n=sizes[i];u8 *input=n?malloc(n):NULL;assert(!n||input);
        if(n)memset(input,0,n);
        if(n>=2){input[0]=0x93;input[1]=0x79;}
        if(n>=0x198)memcpy(input+0x190,conf,8);
        if(bad==1&&n)input[0]^=1;
        if(bad>=2&&n>=0x198)input[0x190+bad-2]^=1;
        u8 *dest=malloc(7680);assert(dest);memset(dest,0xa5,7680);
        struct mt7996_dev d={.mt76.eeprom.data=dest,.var.fem=MT7996_FEM_INT};
        fw=(struct firmware){n,input};releases=logs=0;request_error=0;
        int ret=mt7996_vb235v_development_calibration(&d);
        bool valid=n==7680&&bad==0;
        assert(ret==(valid?0:-EINVAL)&&releases==1&&logs==(valid?1:0));
        if(valid)assert(!memcmp(dest,input,7680)&&d.eeprom_mode==EEPROM_MODE_FLASH);
        else for(size_t j=0;j<7680;j++)assert(dest[j]==0xa5);
        free(input);free(dest);cases++;
    }
    u8 dest[7680];memset(dest,0xa5,sizeof(dest));
    struct mt7996_dev d={.mt76.eeprom.data=dest,.var.fem=MT7996_FEM_INT};
    request_error=-ENOENT;releases=logs=0;
    assert(mt7996_vb235v_development_calibration(&d)==-ENOENT&&!releases&&!logs);cases++;
    request_error=-EIO;assert(mt7996_vb235v_development_calibration(&d)==-EIO);cases++;
    request_error=0;chip_valid=false;assert(mt7996_vb235v_development_calibration(&d)==-EINVAL);cases++;
    chip_valid=true;d.var.fem=99;assert(mt7996_vb235v_development_calibration(&d)==-EINVAL);cases++;
    printf("PASS: %d unchanged-loader size/header/config/error cases; no out-of-bounds or destination writes on reject.\n",cases);
}
'''.replace('/* ACTUAL_FUNCTION */',function)
path=out/'calibration.c'
path.write_text(c)
cmd=['gcc','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
     '-fsanitize=address,undefined','-fno-omit-frame-pointer',str(path),'-o',str(out/'calibration')]
subprocess.run(cmd,check=True)
run=subprocess.run([str(out/'calibration')],text=True,capture_output=True,check=True)
print(run.stdout,end='')
(out/'report.json').write_text(json.dumps({'status':'passed','stdout':run.stdout.strip(),
    'synthetic_data_only':True,'loader_sha256':hashlib.sha256(function.encode()).hexdigest(),
    'limitations':['Valid header/config does not authenticate RF tables; private full-file hash remains an image/input integrity check.']},indent=2)+'\n')
