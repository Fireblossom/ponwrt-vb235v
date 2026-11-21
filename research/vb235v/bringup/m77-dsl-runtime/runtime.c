/* SPDX-License-Identifier: GPL-2.0-only */
#define _GNU_SOURCE
#include "provider.h"
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <time.h>
#include <unistd.h>

static const struct {const char *name,*hash;size_t size;} manifest[]={
 {"ddr_cal.bin","7ea80b9b2c30f6687a0b14e1e8bc259f9daaf554b138770b4fb1b1886dfe1404",22744},
 {"iNIC.bin","2840bd859eb27dbcc2997abde5223a7059ef3d97e89d047a2854eef664ed341f",39556},
 {"tclinux.bin","c6e0a8d0cbaf282b956a9fd3b9050cb073434947c6a32c9b95976b72eaa2a412",4214743}
};
struct stage {const char *id,*title,*state,*detail,*code;};
struct event {uint64_t uptime;const char *stage,*state,*detail,*code;};
static struct {
 char boot_id[40];uint64_t generation;const char *state,*code;bool can_retry;
 struct stage stages[6];struct event events[32];unsigned count;int dirfd;
} status;
static volatile sig_atomic_t stopping;
static uint64_t uptime_s(void)
{struct timespec t;if(clock_gettime(CLOCK_BOOTTIME,&t))return 0;return (uint64_t)t.tv_sec;}
static bool cancelled(void *ctx){(void)ctx;return stopping!=0;}
static void stop(int sig){(void)sig;stopping=1;}
static void stage(unsigned i,const char *state,const char *code,const char *detail)
{
 status.stages[i].state=state;status.stages[i].code=code;status.stages[i].detail=detail;
 if(status.count==32){memmove(status.events,status.events+1,sizeof(status.events[0])*31);status.count--;}
 status.events[status.count++]=(struct event){uptime_s(),status.stages[i].id,state,detail,code};
}
static void quoted(FILE *f,const char *s)
{
 fputc('"',f);for(;*s;s++){unsigned char c=(unsigned char)*s;
  if(c=='"'||c=='\\'){fputc('\\',f);fputc(c,f);}else if(c<32)fprintf(f,"\\u%04x",c);else fputc(c,f);
 }fputc('"',f);
}
static int publish(void)
{
 const char *tmp=".dsl-state.new";
 int fd=openat(status.dirfd,tmp,O_CREAT|O_EXCL|O_WRONLY|O_CLOEXEC|O_NOFOLLOW,0600);
 if(fd<0)return -1;
 FILE *f=fdopen(fd,"w");if(!f){close(fd);unlinkat(status.dirfd,tmp,0);return -1;}
 fprintf(f,"{\"schema\":1,\"boot_id\":");quoted(f,status.boot_id);
 fprintf(f,",\"generation\":%"PRIu64",\"updated_uptime_s\":%"PRIu64",\"state\":",status.generation,uptime_s());quoted(f,status.state);
 fputs(",\"code\":",f);quoted(f,status.code);fprintf(f,",\"can_retry\":%s,\"stages\":[",status.can_retry?"true":"false");
 for(unsigned i=0;i<6;i++){
  struct stage *s=&status.stages[i];if(i)fputc(',',f);fputs("{\"id\":",f);quoted(f,s->id);
  fputs(",\"title\":",f);quoted(f,s->title);fputs(",\"state\":",f);quoted(f,s->state);
  fputs(",\"detail\":",f);quoted(f,s->detail);fputs(",\"code\":",f);quoted(f,s->code);fputc('}',f);
 }
 fputs("],\"events\":[",f);
 for(unsigned i=0;i<status.count;i++){
  struct event *e=&status.events[i];if(i)fputc(',',f);fprintf(f,"{\"uptime_s\":%"PRIu64",\"stage\":",e->uptime);quoted(f,e->stage);
  fputs(",\"state\":",f);quoted(f,e->state);fputs(",\"code\":",f);quoted(f,e->code);fputs(",\"detail\":",f);quoted(f,e->detail);fputc('}',f);
 }
 fprintf(f,"],\"line\":{\"showtime\":false,\"state\":\"unknown\"},\"internet\":{\"generation\":%"PRIu64",\"authenticated\":false,\"ipv4\":false,\"ipv6\":false,\"state\":\"pending\"}}\n",status.generation);
 int e=fflush(f);if(!e)e=fsync(fd);if(fclose(f)&&!e)e=-1;
 if(!e)e=renameat(status.dirfd,tmp,status.dirfd,"dsl-state.json");
 if(!e)e=fsync(status.dirfd);
 if(e)unlinkat(status.dirfd,tmp,0);
 return e;
}
static int read_boot_id(void)
{
 int fd=open("/proc/sys/kernel/random/boot_id",O_RDONLY|O_CLOEXEC|O_NOFOLLOW);if(fd<0)return -1;
 ssize_t n=read(fd,status.boot_id,39);close(fd);if(n<36)return -1;status.boot_id[36]=0;
 for(unsigned i=0;i<36;i++){
  char c=status.boot_id[i];if(i==8||i==13||i==18||i==23){if(c!='-')return -1;}
  else if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return -1;
 }return 0;
}
static int state_dir(const char *path)
{
 if(mkdir(path,0700)&&errno!=EEXIST)return -1;
 status.dirfd=open(path,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);if(status.dirfd<0)return -1;
 struct stat st;if(fstat(status.dirfd,&st)||st.st_uid!=0||(st.st_mode&0077))return -1;
 return 0;
}
static void previous_generation(void)
{
 int fd=openat(status.dirfd,"dsl-state.json",O_RDONLY|O_CLOEXEC|O_NOFOLLOW);if(fd<0)return;
 char text[16385];ssize_t n=read(fd,text,sizeof(text)-1);close(fd);if(n<=0)return;text[n]=0;
 char pattern[80];snprintf(pattern,sizeof(pattern),"\"boot_id\":\"%s\"",status.boot_id);
 if(!strstr(text,pattern))return;
 char *p=strstr(text,"\"generation\":");if(!p)return;
 errno=0;char *end=NULL;unsigned long long v=strtoull(p+13,&end,10);
 if(!errno&&end!=p+13&&v<UINT64_MAX)status.generation=(uint64_t)v;
}
static int begin_generation(void)
{
 if(status.generation==UINT64_MAX)return -1;
 status.generation++;status.state="running";status.code="STARTING";status.can_retry=false;
 const char *ids[]={"inputs","owner","endpoint","line","ppp","internet"};
 const char *titles[]={"Firmware inputs","Exclusive hardware owner","Endpoint bootstrap","DSL line","Automatic PPP","Internet"};
 for(unsigned i=0;i<6;i++)status.stages[i]=(struct stage){ids[i],titles[i],i==0?"running":"pending","Awaiting verified prior stage","PENDING"};
 stage(0,"running","INPUTS_CHECKING","Checking pinned private firmware inputs");return publish();
}
static int load_inputs(const char *directory,uint8_t *data[3],struct pndsl_claim *claim)
{
 int dir=open(directory,O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);if(dir<0)return DSL_E_FIRMWARE;
 int e=DSL_E_FIRMWARE;
 for(unsigned i=0;i<3;i++){
  int fd=openat(dir,manifest[i].name,O_RDONLY|O_NOFOLLOW|O_CLOEXEC);if(fd<0)goto done;
  struct stat st;if(fstat(fd,&st)||!S_ISREG(st.st_mode)||st.st_uid!=0||(st.st_mode&0022)||st.st_size!=(off_t)manifest[i].size){close(fd);goto done;}
  data[i]=malloc(manifest[i].size);if(!data[i]){close(fd);goto done;}
  size_t n=0;while(n<manifest[i].size){ssize_t k=read(fd,data[i]+n,manifest[i].size-n);if(k<0&&errno==EINTR)continue;if(k<=0)break;n+=(size_t)k;}
  char extra;ssize_t more=read(fd,&extra,1);close(fd);if(n!=manifest[i].size||more!=0)goto done;
  dsl_sha256(data[i],n,claim->sha256[i]);claim->sizes[i]=(__u32)n;
  char hex[65];for(unsigned b=0;b<32;b++)snprintf(hex+b*2,3,"%02x",claim->sha256[i][b]);
  if(strcmp(hex,manifest[i].hash))goto done;
 }
 e=DSL_OK;
done:close(dir);return e;
}
static int attempt(const char *firmware)
{
 uint8_t *data[3]={0};struct pndsl_claim claim={.abi=PNDSL_ABI,.generation=status.generation};
 memcpy(claim.profile,PNDSL_PROFILE,sizeof(PNDSL_PROFILE));struct dsl_provider provider={.fd=-1};struct dsl_hw hw={0};
 int e=load_inputs(firmware,data,&claim);unsigned failed=0;const char *code=NULL,*detail=NULL;
 if(e){code="INPUTS_MISSING_OR_MISMATCH";detail="Private firmware size, ownership or pinned SHA256 validation failed";goto done;}
 stage(0,"done","INPUTS_PINNED","All three private firmware inputs match the pinned manifest");
 stage(1,"running","OWNER_QUERY","Querying the native exclusive board-mode provider");if(publish()){e=DSL_E_IO;goto done;}
 failed=1;e=dsl_provider_open(&provider);
 if(e){code="OWNER_PROVIDER_UNBOUND";detail="Native MDIO and GPIO board-mode provider is absent or incompatible";goto done;}
 e=dsl_provider_claim(&provider,&claim,&hw);
 if(e){code="OWNER_PROFILE_UNVERIFIED";detail="Exclusive PCS, pinmux and reset ownership is not verified and admitted";goto done;}
 hw.cancelled=cancelled;
 stage(1,"done","OWNER_CLAIMED","Native provider admitted the pinned inputs and exclusive board profile");
 failed=2;stage(2,"running","ENDPOINT_RESET_PLL","Applying the verified endpoint reset and conditional PLL sequence");
 if(publish()){e=DSL_E_IO;goto done;}
 e=dsl_endpoint_prepare(&hw);if(e)goto done;
 stage(2,"running","DDR_TRANSFER","Transferring pinned DDR calibration through the verified MDIO bridge");if(publish()){e=DSL_E_IO;goto done;}
 e=dsl_ddr_load(&hw,data[0],manifest[0].size);if(e)goto done;
 stage(2,"running","INIC_TRANSFER","DDR phase acknowledged; transferring only confirmed iNIC segments");if(publish()){e=DSL_E_IO;goto done;}
 e=dsl_inic_load_known(&hw,data[1],manifest[1].size);
 /* No continuation exists past the unresolved trailer. Never report ready. */
 if(e==DSL_OK)e=DSL_BLOCK_INIC_TRAILER;
done:
 if(!code)code=dsl_code(e);
 if(!detail)detail=e==DSL_BLOCK_INIC_TRAILER?"Original iNIC configuration trailer and execute acknowledgement require independent validation":"Endpoint stage stopped; current line and PPP remain unverified";
 int release=dsl_provider_release(&provider);
 for(unsigned i=0;i<3;i++)free(data[i]);
 status.state="blocked";status.code=code;status.can_retry=!stopping&&release==DSL_OK;
 stage(failed,"blocked",code,detail);
 stage(3,"unknown","LINE_UNVERIFIED","No current-generation DSL showtime evidence");
 stage(4,"pending","PPP_UNIMPLEMENTED","Automatic PPP authentication has no verified running provider");
 stage(5,"pending","INTERNET_UNVERIFIED","No authenticated IPv4 or IPv6 client-service evidence");
 if(release){status.code="OWNER_RELEASE_FAILED";stage(1,"error",status.code,"Provider failed to restore ownership; further retries are disabled");}
 if(publish())return -1;
 return e;
}
static int open_control(const char *path)
{
 struct sockaddr_un addr={.sun_family=AF_UNIX};if(strlen(path)>=sizeof(addr.sun_path)){errno=ENAMETOOLONG;return -1;}strcpy(addr.sun_path,path);
 struct stat st;if(!lstat(path,&st)){
  if(!S_ISSOCK(st.st_mode)||st.st_uid!=0){errno=EPERM;return -1;}
  int probe=socket(AF_UNIX,SOCK_DGRAM|SOCK_CLOEXEC,0);if(probe<0)return -1;
  int e=connect(probe,(struct sockaddr *)&addr,sizeof(addr));int saved=errno;close(probe);
  if(!e||saved!=ECONNREFUSED){errno=EADDRINUSE;return -1;}
  if(unlink(path))return -1;
 }else if(errno!=ENOENT)return -1;
 int fd=socket(AF_UNIX,SOCK_DGRAM|SOCK_CLOEXEC,0);if(fd<0)return -1;int one=1;
 if(setsockopt(fd,SOL_SOCKET,SO_PASSCRED,&one,sizeof(one))||bind(fd,(struct sockaddr *)&addr,sizeof(addr))||chmod(path,0600)){close(fd);return -1;}return fd;
}
int main(int argc,char **argv)
{
 const char *firmware="/lib/firmware/ponwrt/dsl",*dir="/tmp/ponwrt",*control="/var/run/ponwrt-dsl-control.sock";bool once=false;
 for(int i=1;i<argc;i++){
  if(!strcmp(argv[i],"--once"))once=true;
  else if(!strcmp(argv[i],"--firmware-dir")&&i+1<argc)firmware=argv[++i];
  else if(!strcmp(argv[i],"--state-dir")&&i+1<argc)dir=argv[++i];
  else if(!strcmp(argv[i],"--control-path")&&i+1<argc)control=argv[++i];
  else {fputs("usage: ponwrt-dsl [--once] [--firmware-dir DIR] [--state-dir DIR] [--control-path PATH]\n",stderr);return 2;}
 }
 if(geteuid()!=0){fputs("root required\n",stderr);return 2;}umask(077);
 if(read_boot_id()||state_dir(dir)){fputs("state setup failed\n",stderr);return 1;}
 int lock=openat(status.dirfd,"dsl-runtime.lock",O_CREAT|O_NOFOLLOW|O_CLOEXEC|O_RDWR,0600);
 if(lock<0||flock(lock,LOCK_EX|LOCK_NB)){fputs("runtime already active or lock unavailable\n",stderr);return 1;}
 /* Recover only our private incomplete atomic file while holding the lock. */
 unlinkat(status.dirfd,".dsl-state.new",0);previous_generation();
 signal(SIGTERM,stop);signal(SIGINT,stop);
 int socket=-1;if(!once&&(socket=open_control(control))<0){fputs("control setup failed\n",stderr);return 1;}
 if(begin_generation())return 1;
 int result=attempt(firmware);
 if(once){close(lock);close(status.dirfd);return result?1:0;}
 while(!stopping){
  struct pollfd p={.fd=socket,.events=POLLIN};int ready=poll(&p,1,5000);
  if(ready<0){if(errno==EINTR)continue;break;}
  if(!ready){if(publish())break;continue;}
  char command[16];union {struct cmsghdr align;char bytes[CMSG_SPACE(sizeof(struct ucred))+CMSG_SPACE(sizeof(int)*4)];} credentials;
  struct sockaddr_un from={0};struct iovec io={command,sizeof(command)};
  struct msghdr msg={.msg_name=&from,.msg_namelen=sizeof(from),.msg_iov=&io,.msg_iovlen=1,.msg_control=credentials.bytes,.msg_controllen=sizeof(credentials.bytes)};
  ssize_t n=recvmsg(socket,&msg,MSG_CMSG_CLOEXEC);if(n<0)continue;
  bool root=false,valid_control=true,saw_credentials=false;
  for(size_t offset=0;offset+sizeof(struct cmsghdr)<=msg.msg_controllen;){
   struct cmsghdr *c=(struct cmsghdr *)(credentials.bytes+offset);
   if(c->cmsg_len<sizeof(*c)||c->cmsg_len>msg.msg_controllen-offset){valid_control=false;break;}
   if(c->cmsg_level==SOL_SOCKET&&c->cmsg_type==SCM_CREDENTIALS&&c->cmsg_len==sizeof(*c)+sizeof(struct ucred)){
    if(saw_credentials)valid_control=false;
    saw_credentials=true;root=((struct ucred *)CMSG_DATA(c))->uid==0;
   }else{
    valid_control=false;
    if(c->cmsg_level==SOL_SOCKET&&c->cmsg_type==SCM_RIGHTS){
     size_t count=(c->cmsg_len-sizeof(*c))/sizeof(int);int *fds=(int *)CMSG_DATA(c);
     for(size_t i=0;i<count;i++)close(fds[i]);
    }
   }
   size_t step=(c->cmsg_len+sizeof(size_t)-1)&~(sizeof(size_t)-1);
   if(step>msg.msg_controllen-offset)break;
   offset+=step;
  }
  bool valid=root&&saw_credentials&&valid_control&&!(msg.msg_flags&(MSG_TRUNC|MSG_CTRUNC))&&n==5&&!memcmp(command,"retry",5)&&status.can_retry;
  char reply[80];int length;
  if(valid&&begin_generation()==0){length=snprintf(reply,sizeof(reply),"ACK %"PRIu64,status.generation);sendto(socket,reply,(size_t)length,0,(struct sockaddr *)&from,msg.msg_namelen);attempt(firmware);}
  else {length=snprintf(reply,sizeof(reply),"NACK");sendto(socket,reply,(size_t)length,0,(struct sockaddr *)&from,msg.msg_namelen);}
 }
 status.can_retry=false;status.state="stopped";status.code="SERVICE_STOPPED";publish();
 close(socket);unlink(control);close(lock);close(status.dirfd);return 0;
}
