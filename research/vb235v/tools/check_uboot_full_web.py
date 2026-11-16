# SPDX-License-Identifier: GPL-2.0-only
"""Native callbacks from the actual recovery web backend, with storage/network mocks."""
from pathlib import Path
import argparse,sys,shutil,subprocess,tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
from check_uboot_ram import MOCK
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path);args=parser.parse_args();SRC=args.source.resolve()
EXTRA=r'''
typedef uint8_t u8;typedef uint32_t u32;
#define min(a,b) ((a)<(b)?(a):(b))
#define min_t(t,a,b) ((t)(a)<(t)(b)?(t)(a):(t)(b))
#define DECLARE_GLOBAL_DATA_PTR
#define EIO 5
struct fake_gd {unsigned long ram_base,ram_size,start_addr_sp;};
static struct fake_gd state_gd={0x80000000,0x20000000,~0UL};
static struct fake_gd *gd=&state_gd;
static unsigned char *mock_upload;
#define UPLOAD_ADDRESS ((ulong)mock_upload)
static int install_calls,boot_calls,storage_error,validate_error;
static int selected_slot=-1;
struct vb_target {const char *name;u32 offset,size;bool physical_raw;};
static const struct vb_target test_targets[]={
 {"bootloader",0,786432,false},{"art",0xc0000,3670016,false},
 {"nand-raw-main-oob",0,570425344,true}};
static int vb_storage_init(void){return storage_error;}
static const char *vb_storage_status(void){return "host mock";}
static int vb_active_slot(void){return storage_error?-19:0;}
static const struct vb_target *vb_target_find(const char *name){
 for(unsigned i=0;i<sizeof(test_targets)/sizeof(test_targets[0]);i++)
  if(!strcmp(name,test_targets[i].name))return &test_targets[i];
 return NULL;
}
static int vb_storage_read(const struct vb_target *t,u32 off,void *out,size_t n){
 if(storage_error)return storage_error;
 if(!t||off>t->size||n>t->size-off)return -19;
 for(size_t i=0;i<n;i++)((unsigned char*)out)[i]=(off+i)&255;
 return 0;
}
static int vb_fit_validate(const void *p,size_t n){return validate_error;}
static int vb_storage_install(unsigned slot,const void *p,size_t n,const char *h){
 install_calls++;selected_slot=slot;return storage_error;
}
static int vb_boot(void){boot_calls++;return storage_error;}
static ulong get_timer(ulong base){static ulong ticks;ticks+=100;return ticks-base;}
static const char *env_get(const char *key){return NULL;}
static int uboot_httpd_dhcp_start(struct netif *n){return 0;}
static void uboot_httpd_dhcp_stop(void){}
'''
MAIN=r'''
#include "mock.h"
#include "extra.h"
#include "backend.c"
static char uri[64];static u8_t wnd;static int cases,checks;
#define CHECK(v) do{checks++;if(!(v)){fprintf(stderr,"line %d: %s\n",__LINE__,#v);exit(1);}}while(0)
#define CASE() do{cases++;}while(0)
static void reset(void){
 receiving=NULL;expected_bytes=received_bytes=ready_bytes=0;failed=running=false;
 digest[0]=0;pending_slot=-1;pending_boot=awaiting_reply=false;downloads=0;
 operation_result=install_calls=boot_calls=storage_error=validate_error=0;
 selected_slot=-1;ctrl_polls=stop_count=fs_calls=freed=short_copy=eth_error=no_netif=rx_error=0;
}
static err_t begin(void *c,const char *path,int n){return httpd_post_begin(c,path,"",0,n,uri,sizeof(uri),&wnd);}
static err_t recv(void *c,const void *data,u16_t n){struct pbuf p={n,data};return httpd_post_receive_data(c,&p);}
static void finish(void *c){httpd_post_finished(c,uri,sizeof(uri));}
static void ready(void *c){CHECK(begin(c,"/api/upload",4)==ERR_OK);CHECK(recv(c,"GOOD",4)==ERR_OK);finish(c);CHECK(ready_bytes==4);}
int main(void){
 void *a=(void*)1,*b=(void*)2;struct fs_file f={0};char data[128],path[128];
 mock_upload=malloc(MAX_UPLOAD);CHECK(mock_upload);reset();
 const char *bad[]={"/api/task","/api/env","/api/command","/api/upload-all-flash","/api/nand-scrub","/api/ubi-rebuild","/api/flash-bl2","/api/flash-uboot"};
 for(unsigned i=0;i<sizeof(bad)/sizeof(bad[0]);i++){CASE();CHECK(begin(a,bad[i],1)==ERR_ARG);}
 CASE();CHECK(begin(a,"/api/upload",0)==ERR_ARG);CHECK(begin(a,"/api/upload",MAX_UPLOAD+1)==ERR_ARG);CHECK(begin(NULL,"/api/upload",1)==ERR_ARG);
 CASE();CHECK(begin(a,"/api/upload",4)==ERR_OK);CHECK(begin(b,"/api/upload",4)==ERR_ARG);
 CHECK(recv(b,"BAD!",4)==ERR_ARG);CHECK(!received_bytes&&!failed);finish(b);CHECK(receiving==a);
 CASE();CHECK(recv(a,"GO",2)==ERR_OK);finish(a);CHECK(!ready_bytes&&!receiving);
 CASE();CHECK(begin(a,"/api/upload",1)==ERR_OK);CHECK(recv(a,"!",1)==ERR_OK);finish(a);CHECK(ready_bytes==1&&pending_slot==-1&&!pending_boot);
 CASE();ready(a);CHECK(strlen(digest)==64&&!strcmp(uri,"/api/status"));
 CASE();snprintf(path,sizeof(path),"/api/install/1/%s",digest);CHECK(begin(a,path,1)==ERR_OK);CHECK(recv(a,"!",1)==ERR_OK);finish(a);
 CHECK(pending_slot==1&&awaiting_reply&&!strcmp(uri,"/api/queued"));
 CHECK(fs_open_custom(&f,"/api/status"));fs_close_custom(&f);CHECK(awaiting_reply);
 CASE();CHECK(fs_open_custom(&f,"/api/queued"));CHECK(awaiting_reply);fs_close_custom(&f);CHECK(!awaiting_reply);
 CHECK(uboot_httpd_start(false)==0);CHECK(install_calls==1&&selected_slot==1&&pending_slot==-1);
 reset();CASE();CHECK(begin(a,"/api/boot",1)==ERR_OK);CHECK(recv(a,"!",1)==ERR_OK);finish(a);CHECK(pending_boot&&awaiting_reply);
 CHECK(fs_open_custom(&f,"/api/queued"));fs_close_custom(&f);CHECK(uboot_httpd_start(false)==0&&boot_calls==1);
 reset();CASE();ready(a);snprintf(path,sizeof(path),"/api/install/1/%s",digest);CHECK(begin(a,path,1)==ERR_OK);CHECK(recv(a,"?",1)==ERR_ARG);finish(a);CHECK(pending_slot==-1);
 CASE();CHECK(begin(a,"/api/upload",4)==ERR_OK);short_copy=1;CHECK(recv(a,"GOOD",4)==ERR_ARG);finish(a);CHECK(!ready_bytes);short_copy=0;
 CASE();CHECK(begin(a,"/api/upload",4)==ERR_OK);CHECK(recv(a,"12345",5)==ERR_ARG);finish(a);CHECK(!ready_bytes);
 reset();CASE();CHECK(fs_open_custom(&f,"/api/backup/bootloader"));CHECK(downloads==1&&f.len>786432);
 CHECK(begin(a,"/api/upload",1)==ERR_ARG);CHECK(fs_read_custom(&f,data,7)==7);CHECK(!memcmp(data,"HTTP/1.",7));
 while(f.index<((struct owner*)f.pextension)->header_length)CHECK(fs_read_custom(&f,data,7)>0);
 CHECK(fs_read_custom(&f,data,20)==20);for(int i=0;i<20;i++)CHECK((unsigned char)data[i]==i);
 fs_close_custom(&f);CHECK(!downloads);
 CASE();CHECK(fs_open_custom(&f,"/api/backup/nand-raw-main-oob"));CHECK(f.len>570425344&&f.len<570426000);fs_close_custom(&f);
 CASE();CHECK(fs_open_custom(&f,"/api/backup/unknown"));CHECK(strstr(f.data,"400 Error"));fs_close_custom(&f);
 CASE();storage_error=-19;CHECK(fs_open_custom(&f,"/api/backup/art"));CHECK(strstr(f.data,"400 Error"));fs_close_custom(&f);storage_error=0;
 reset();CASE();ready(a);validate_error=-22;snprintf(path,sizeof(path),"/api/install/1/%s",digest);CHECK(begin(a,path,1)==ERR_ARG);CHECK(!receiving&&pending_slot==-1);
 reset();CASE();ready(a);snprintf(path,sizeof(path),"/api/install/1/%s",digest);path[15]=path[15]=='0'?'1':'0';CHECK(begin(a,path,1)==ERR_ARG);CHECK(pending_slot==-1);
 reset();CASE();CHECK(begin(a,"/api/boot",1)==ERR_OK);CHECK(recv(a,"!",1)==ERR_OK);finish(a);
 CHECK(uboot_httpd_start(false)==0);CHECK(!boot_calls&&!pending_boot&&!awaiting_reply);
 reset();CASE();CHECK(!fs_open_custom(&f,"/index.shtml"));CHECK(fs_open_custom(&f,"/index.html"));CHECK(strstr(f.data,"200 OK"));fs_close_custom(&f);
 CASE();CHECK(!fs_open_custom(&f,"/not-found"));CHECK(fs_open_custom(&f,"/api/unknown"));CHECK(strstr(f.data,"400 Error"));fs_close_custom(&f);
 reset();free(mock_upload);printf("RESULT cases=%d assertions=%d\n",cases,checks);return 0;
}
'''
with tempfile.TemporaryDirectory(prefix='vb235v-full-web-') as directory:
 root=Path(directory);(root/'mock.h').write_text(MOCK);(root/'extra.h').write_text(EXTRA);(root/'main.c').write_text(MAIN)
 for h in ['asm/global_data.h','command.h','console.h','env.h','malloc.h','net.h','net-lwip.h','net/httpd.h','lwip/apps/fs.h','lwip/apps/httpd.h','lwip/pbuf.h','vb235v-recovery.h']:
  p=root/h;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('#include "mock.h"\n')
 for h,s in {'linux/types.h':'#include <stdint.h>\n','linux/errno.h':'#define EOPNOTSUPP 95\n','linux/kconfig.h':'#define CONFIG_IS_ENABLED(x) 0\n','linux/compiler_attributes.h':'#define __weak __attribute__((weak))\n#define __always_unused __attribute__((unused))\n'}.items():
  p=root/h;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s)
 (root/'u-boot').mkdir();shutil.copyfile(SRC/'include/u-boot/sha256.h',root/'u-boot/sha256.h')
 shutil.copyfile(SRC/'net/lwip/httpd-vb235v.c',root/'backend.c')
 command=['cc','-std=gnu11','-O1','-g','-DUSE_HOSTCC','-fsanitize=address,undefined','-fno-omit-frame-pointer','-I',str(root),str(root/'main.c'),str(SRC/'lib/sha256.c'),str(SRC/'lib/sha256_common.c'),'-o',str(root/'test')]
 r=subprocess.run(command,capture_output=True,text=True)
 if r.returncode:raise RuntimeError(r.stderr[-8000:])
 r=subprocess.run([str(root/'test')],capture_output=True,text=True)
 if r.returncode:raise RuntimeError(r.stdout[-2000:]+r.stderr[-8000:])
 print(r.stdout)
 if args.output:args.output.write_text(r.stdout)
