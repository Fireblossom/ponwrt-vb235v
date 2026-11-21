// SPDX-License-Identifier: GPL-2.0-only
/* Authenticated rpcd diagnostics, current-boot evidence and bounded history. */
#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <json-c/json.h>
#include <limits.h>
#include <math.h>
#include <poll.h>
#include <regex.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#ifndef RUN
#define RUN "/tmp/ponwrt"
#endif
#define SAVE "/etc/ponwrt/diagnostics"
#ifndef DSL_CONTROL
#define DSL_CONTROL "/var/run/ponwrt-dsl-control.sock"
#endif
#define LIMIT (128*1024)
static volatile sig_atomic_t running=1;
static void stop_handler(int sig){(void)sig;running=0;}
static void add_s(json_object *o,const char *k,const char *v){json_object_object_add(o,k,v?json_object_new_string(v):NULL);}
static void add_i(json_object *o,const char *k,long long v){json_object_object_add(o,k,json_object_new_int64(v));}
static void add_b(json_object *o,const char *k,bool v){json_object_object_add(o,k,json_object_new_boolean(v));}
static char *read_file(const char *path,size_t limit)
{
 int fd=open(path,O_RDONLY|O_CLOEXEC|O_NOFOLLOW);if(fd<0)return NULL;
 char *buf=calloc(1,limit+1);if(!buf){close(fd);return NULL;}size_t at=0;
 while(at<limit){ssize_t n=read(fd,buf+at,limit-at);if(n<0&&errno==EINTR)continue;if(n<=0)break;at+=(size_t)n;}
 close(fd);buf[at]=0;return buf;
}
static void trim(char *s){if(s){size_t n=strlen(s);while(n&&strchr(" \n\r\t",s[n-1]))s[--n]=0;}}
static long long number(const char *path,long long fallback){char *s=read_file(path,128);if(!s)return fallback;char *end;errno=0;long long n=strtoll(s,&end,0);bool ok=!errno&&end!=s;free(s);return ok?n:fallback;}
static double uptime_s(void){char *s=read_file("/proc/uptime",128);double v=s?strtod(s,NULL):0;free(s);return v;}
static json_object *read_json(const char *path)
{
 char *s=read_file(path,2*1024*1024);if(!s)return NULL;json_object *o=json_tokener_parse(s);free(s);return o;
}
static bool atomic_json(const char *path,json_object *o)
{
 char temp[PATH_MAX];if(snprintf(temp,sizeof(temp),"%s.XXXXXX",path)>=(int)sizeof(temp))return false;
 int fd=mkstemp(temp);if(fd<0)return false;fchmod(fd,0600);
 const char *s=json_object_to_json_string_ext(o,JSON_C_TO_STRING_PLAIN);size_t len=strlen(s),at=0;
 while(at<len){ssize_t n=write(fd,s+at,len-at);if(n<=0){close(fd);unlink(temp);return false;}at+=(size_t)n;}
 bool ok=fsync(fd)==0;close(fd);if(!ok||rename(temp,path)){unlink(temp);return false;}
 char parent[PATH_MAX];strncpy(parent,path,sizeof(parent)-1);parent[sizeof(parent)-1]=0;char *slash=strrchr(parent,'/');if(slash){*slash=0;fd=open(parent,O_RDONLY|O_DIRECTORY|O_CLOEXEC);if(fd>=0){fsync(fd);close(fd);}}return true;
}
static char *command(const char *program,char *const argv[])
{
 int p[2];if(pipe(p))return NULL;pid_t pid=fork();if(pid<0){close(p[0]);close(p[1]);return NULL;}
 if(!pid){dup2(p[1],STDOUT_FILENO);int null=open("/dev/null",O_RDWR);dup2(null,STDIN_FILENO);dup2(null,STDERR_FILENO);close(p[0]);close(p[1]);alarm(3);execv(program,argv);_exit(127);}
 close(p[1]);char *buf=calloc(1,LIMIT+1);size_t at=0;struct pollfd f={.fd=p[0],.events=POLLIN};
 time_t end=time(NULL)+4;while(buf&&at<LIMIT&&time(NULL)<=end){int ready=poll(&f,1,200);if(ready<0&&errno==EINTR)continue;if(ready<=0)continue;ssize_t n=read(p[0],buf+at,LIMIT-at);if(n<=0)break;at+=(size_t)n;}
 close(p[0]);kill(pid,SIGKILL);int status;while(waitpid(pid,&status,0)<0&&errno==EINTR){}return buf;
}
static char *replace_pattern(const char *input,const char *pattern,const char *replacement)
{
 regex_t re;if(regcomp(&re,pattern,REG_EXTENDED|REG_ICASE))return strdup(input);
 size_t cap=LIMIT+1,used=0;char *out=calloc(1,cap);const char *at=input;regmatch_t match;
 if(!out){regfree(&re);return NULL;}
 while(*at&&regexec(&re,at,1,&match,0)==0){size_t prefix=(size_t)match.rm_so,rlen=strlen(replacement);if(used+prefix+rlen>=cap)break;memcpy(out+used,at,prefix);used+=prefix;memcpy(out+used,replacement,rlen);used+=rlen;at+=match.rm_eo;if(!match.rm_eo)break;}
 size_t tail=strlen(at);if(tail>=cap-used)tail=cap-used-1;memcpy(out+used,at,tail);regfree(&re);return out;
}
static char *redact(const char *input)
{
 char *lines=strdup(input?input:""),*save=NULL;char *clean=calloc(1,LIMIT+1);size_t at=0;if(!lines||!clean){free(lines);free(clean);return NULL;}
 for(char *line=strtok_r(lines,"\n",&save);line;line=strtok_r(NULL,"\n",&save)){
  bool sensitive=strcasestr(line,"password")||strcasestr(line,"passwd")||strcasestr(line,"psk")||strcasestr(line,"secret")||strcasestr(line,"authorization:")||strcasestr(line,"username")||strcasestr(line,"ssid")||strcasestr(line,"private key")||strcasestr(line,"token")||strcasestr(line,"PAP ")||strcasestr(line,"CHAP ")||strcasestr(line,"user=")||strcasestr(line,"credential");
  const char *text=sensitive?"[已隐藏含凭证或网络标识的日志行]":line;size_t len=strlen(text);if(at+len+2>LIMIT)break;memcpy(clean+at,text,len);at+=len;clean[at++]='\n';
 }
 free(lines);char *mac=replace_pattern(clean,"([[:xdigit:]]{2}:){5}[[:xdigit:]]{2}","[MAC]");free(clean);if(!mac)return NULL;
 char *ip=replace_pattern(mac,"([0-9]{1,3}\\.){3}[0-9]{1,3}","[IP]");free(mac);if(!ip)return NULL;
 char *ipv6=replace_pattern(ip,"([[:xdigit:]]{0,4}:){2,}[[:xdigit:]:]{0,39}","[IPv6]");free(ip);return ipv6;
}
static json_object *lines_json(const char *s)
{
 json_object *arr=json_object_new_array();char *copy=strdup(s?s:""),*save=NULL;if(!copy)return arr;
 for(char *line=strtok_r(copy,"\n",&save);line;line=strtok_r(NULL,"\n",&save))json_object_array_add(arr,json_object_new_string(line));
 free(copy);return arr;
}
static void issue(json_object *issues,const char *code,const char *title,const char *detail)
{
 json_object *o=json_object_new_object();add_s(o,"code",code);add_s(o,"title",title);add_s(o,"detail",detail);json_object_array_add(issues,o);
}
static json_object *missing_dsl(const char *code,const char *detail)
{
 static const char *ids[]={"inputs","owner","endpoint","line","ppp","internet"};
 static const char *names[]={"固件与启动服务","硬件准备与资源占用","DSL 端点启动","线路同步","Telekom 自动认证","IPv4 / IPv6 与局域网"};
 json_object *dsl=json_object_new_object(),*stages=json_object_new_array(),*line=json_object_new_object();
 add_s(dsl,"state","blocked");add_b(dsl,"can_retry",false);add_s(dsl,"code",code);add_s(line,"detail","尚未取得本次启动的线路状态");json_object_object_add(line,"showtime",NULL);json_object_object_add(dsl,"line",line);
 for(size_t i=0;i<6;i++){json_object *o=json_object_new_object();add_s(o,"id",ids[i]);add_s(o,"title",names[i]);add_s(o,"state",i?"pending":"blocked");add_s(o,"detail",i?"等待前序阶段提供有效结果":detail);if(!i)add_s(o,"code",code);json_object_array_add(stages,o);}
 json_object_object_add(dsl,"stages",stages);return dsl;
}
static bool true_field(json_object *o,const char *key)
{
 json_object *v=NULL;return o&&json_object_object_get_ex(o,key,&v)&&json_object_is_type(v,json_type_boolean)&&json_object_get_boolean(v);
}
static const char *string_field(json_object *o,const char *key)
{
 json_object *v=NULL;return o&&json_object_object_get_ex(o,key,&v)&&json_object_is_type(v,json_type_string)?json_object_get_string(v):"";
}
static const char *safe_state(json_object *o)
{
 const char *s=string_field(o,"state");const char *states[]={"done","running","failed","error","stopped","blocked","pending","unknown","unavailable","online","offline","unsupported"};
 for(size_t i=0;i<sizeof(states)/sizeof(states[0]);i++)if(!strcmp(s,states[i]))return s;
 return "unknown";
}
static void safe_text(json_object *to,json_object *from,const char *key,size_t limit)
{
 const char *s=string_field(from,key);char *bounded=strndup(s,limit),*clean=redact(bounded);free(bounded);trim(clean);add_s(to,key,clean?clean:"");free(clean);
}
/* Project only public fields. Never forward arbitrary controller JSON to the UI. */
static json_object *project_dsl(json_object *raw,long long generation)
{
 static const char *ids[]={"inputs","owner","endpoint","line","ppp","internet"};
 static const char *titles[]={"固件与启动服务","硬件准备与资源占用","DSL 端点启动","线路同步","Telekom 自动认证","IPv4 / IPv6 与局域网"};
 json_object *out=json_object_new_object(),*line=NULL,*stages=NULL,*events=NULL,*proof=NULL;
 add_s(out,"state",safe_state(raw));safe_text(out,raw,"code",128);add_b(out,"can_retry",true_field(raw,"can_retry"));add_i(out,"generation",generation);
 json_object_object_get_ex(raw,"line",&line);json_object *public_line=json_object_new_object(),*showtime=NULL;
 if(line&&json_object_object_get_ex(line,"showtime",&showtime)&&json_object_is_type(showtime,json_type_boolean))add_b(public_line,"showtime",json_object_get_boolean(showtime));else json_object_object_add(public_line,"showtime",NULL);
 safe_text(public_line,line,"detail",768);json_object_object_add(out,"line",public_line);
 json_object *public_stages=json_object_new_array();json_object_object_get_ex(raw,"stages",&stages);bool ppp_done=false,internet_done=false;
 for(size_t i=0;i<6;i++){
  json_object *source=NULL;if(stages&&json_object_is_type(stages,json_type_array))for(size_t j=0;j<json_object_array_length(stages)&&j<16;j++){json_object *v=json_object_array_get_idx(stages,j);if(!strcmp(string_field(v,"id"),ids[i])){source=v;break;}}
  json_object *step=json_object_new_object();add_s(step,"id",ids[i]);add_s(step,"title",titles[i]);add_s(step,"state",source?safe_state(source):"unknown");safe_text(step,source,"detail",768);safe_text(step,source,"code",128);json_object_array_add(public_stages,step);
  if(i==4)ppp_done=source&&!strcmp(safe_state(source),"done");
  if(i==5)internet_done=source&&!strcmp(safe_state(source),"done");
 }
 json_object_object_add(out,"stages",public_stages);json_object *public_events=json_object_new_array();json_object_object_get_ex(raw,"events",&events);
 if(events&&json_object_is_type(events,json_type_array)){size_t count=json_object_array_length(events),start=count>64?count-64:0;for(size_t i=start;i<count;i++){json_object *v=json_object_array_get_idx(events,i),*e=json_object_new_object(),*t=NULL;safe_text(e,v,"code",128);safe_text(e,v,"stage",64);safe_text(e,v,"detail",768);add_s(e,"state",safe_state(v));if(json_object_object_get_ex(v,"uptime_s",&t)&&(json_object_is_type(t,json_type_double)||json_object_is_type(t,json_type_int))&&isfinite(json_object_get_double(t)))json_object_object_add(e,"uptime_s",json_object_get(t));json_object_array_add(public_events,e);}}
 json_object_object_add(out,"events",public_events);
 json_object_object_get_ex(raw,"internet",&proof);json_object *pg=NULL;bool same=proof&&json_object_object_get_ex(proof,"generation",&pg)&&json_object_is_type(pg,json_type_int)&&json_object_get_int64(pg)==generation;
 bool authenticated=same&&true_field(line,"showtime")&&ppp_done&&internet_done&&true_field(proof,"authenticated");
 json_object *internet=json_object_new_object();bool ipv4=authenticated&&true_field(proof,"ipv4"),ipv6=authenticated&&true_field(proof,"ipv6");add_b(internet,"authenticated",authenticated);add_b(internet,"ipv4",ipv4);add_b(internet,"ipv6",ipv6);add_s(internet,"state",ipv4||ipv6?"online":"offline");add_s(internet,"detail",ipv4||ipv6?"本次 DSL 会话已有认证与地址配置证据":"尚无当前 DSL 会话与地址配置证据");json_object_object_add(out,"internet",internet);return out;
}
static json_object *current_dsl(const char *boot,double up)
{
 json_object *o=read_json(RUN"/dsl-state.json"),*id=NULL,*updated=NULL,*schema=NULL,*generation=NULL;
 if(!o)return missing_dsl("DSL_STATE_UNAVAILABLE","未收到 DSL 运行服务的状态；请检查服务启动日志。");
 bool valid=json_object_object_get_ex(o,"boot_id",&id)&&json_object_is_type(id,json_type_string)&&!strcmp(json_object_get_string(id),boot)&&json_object_object_get_ex(o,"updated_uptime_s",&updated)&&(json_object_is_type(updated,json_type_double)||json_object_is_type(updated,json_type_int))&&json_object_object_get_ex(o,"schema",&schema)&&json_object_is_type(schema,json_type_int)&&json_object_get_int(schema)==1&&json_object_object_get_ex(o,"generation",&generation)&&json_object_is_type(generation,json_type_int)&&json_object_get_int64(generation)>0;
 double age=valid?up-json_object_get_double(updated):1e9;
 if(!valid||!isfinite(age)||age<0||age>30){json_object_put(o);return missing_dsl("DSL_STATE_STALE","DSL 状态不属于本次启动，或已经过期；旧的联网结果不会沿用。");}
 json_object *public=project_dsl(o,json_object_get_int64(generation));json_object_put(o);return public;
}
static json_object *collect(const char *kernel)
{
 json_object *root=json_object_new_object(),*system=json_object_new_object(),*issues=json_object_new_array();
 char *boot=read_file("/proc/sys/kernel/random/boot_id",128),*revision=read_file("/etc/vb235v-system-revision",128),*online=read_file("/sys/devices/system/cpu/online",128);trim(boot);trim(revision);trim(online);double up=uptime_s();
 add_i(root,"schema",1);add_s(system,"boot_id",boot?boot:"unknown");add_s(system,"revision",revision);add_s(system,"cpu_online",online);json_object_object_add(system,"uptime_s",json_object_new_double(up));json_object_object_add(root,"system",system);
 json_object *dsl=current_dsl(boot?boot:"unknown",up),*dslstate=NULL,*dslcode=NULL;json_object_object_get_ex(dsl,"state",&dslstate);json_object_object_get_ex(dsl,"code",&dslcode);
 if(!dslstate||strcmp(json_object_get_string(dslstate),"online"))issue(issues,dslcode?json_object_get_string(dslcode):"DSL_NOT_ONLINE","DSL 连接尚未完成","查看 DSL 启动链路中的首个受阻阶段和对应错误。");
 json_object_object_add(root,"dsl",dsl);
 json_object *internet=json_object_new_object(),*proof=NULL;
 /* Only the generation-aware DSL controller may publish session proof. */
 if(json_object_object_get_ex(dsl,"internet",&proof)&&json_object_is_type(proof,json_type_object)){json_object_put(internet);internet=json_object_get(proof);}else{add_s(internet,"state","offline");add_b(internet,"authenticated",false);add_b(internet,"ipv4",false);add_b(internet,"ipv6",false);add_s(internet,"detail","尚无当前 DSL 会话与地址配置证据");}
 json_object_object_add(root,"internet",internet);
 json_object *ports=json_object_new_array();const char *names[]={"lan-test","eth1","eth2"};const char *labels[]={"1G 网口","2.5G 口 / eth1","2.5G 口 / eth2"};
 for(size_t i=0;i<3;i++){char path[256];snprintf(path,sizeof(path),"/sys/class/net/%s",names[i]);if(access(path,F_OK))continue;json_object *o=json_object_new_object();add_s(o,"name",names[i]);add_s(o,"label",labels[i]);add_b(o,"management",i!=1);snprintf(path,sizeof(path),"/sys/class/net/%s/carrier",names[i]);long long carrier=number(path,-1);if(carrier<0)json_object_object_add(o,"carrier",NULL);else add_b(o,"carrier",carrier==1);snprintf(path,sizeof(path),"/sys/class/net/%s/speed",names[i]);add_i(o,"speed_mbps",number(path,-1));snprintf(path,sizeof(path),"/sys/class/net/%s/duplex",names[i]);char *duplex=read_file(path,32);trim(duplex);add_s(o,"duplex",duplex);free(duplex);json_object_array_add(ports,o);}
 json_object_object_add(root,"ports",ports);
 json_object *cpu=json_object_new_object();add_s(cpu,"online",online);long long rate=number("/sys/devices/system/cpu/cpufreq/policy0/scaling_cur_freq",-1);if(rate>=0)add_i(cpu,"frequency_khz",rate);else json_object_object_add(cpu,"frequency_khz",NULL);json_object_object_add(root,"cpu",cpu);
 json_object *thermal=json_object_new_array();DIR *dir=opendir("/sys/class/thermal");struct dirent *e;
 if(dir){while((e=readdir(dir))){if(strncmp(e->d_name,"thermal_zone",12))continue;char path[512];snprintf(path,sizeof(path),"/sys/class/thermal/%s/temp",e->d_name);json_object *t=json_object_new_object();add_s(t,"name",e->d_name);add_i(t,"temperature_mC",number(path,LLONG_MIN));json_object_array_add(thermal,t);}closedir(dir);}
 json_object_object_add(root,"thermal",thermal);if(!json_object_array_length(thermal))issue(issues,"THERMAL_UNAVAILABLE","温度监测尚不可用","未检测到温度传感器节点；无法确认当前芯片温度。");
 if(rate<0)issue(issues,"CPU_FREQUENCY_UNAVAILABLE","CPU 调频状态不可用","尚无可读取的 CPU 调频策略或实际频率。");
 json_object *wifi=json_object_new_object();bool fallback=kernel&&strstr(kernel,"eeprom load fail, use default bin"),calibration=kernel&&strstr(kernel,"VB235v private ART EEPROM loaded; reference fallback disabled");add_s(wifi,"driver","mt7996e");add_b(wifi,"reference_fallback",fallback);long long phys=0;dir=opendir("/sys/class/ieee80211");if(dir){while((e=readdir(dir)))if(!strncmp(e->d_name,"phy",3))phys++;closedir(dir);}add_b(wifi,"private_calibration",phys>0&&calibration&&!fallback);add_i(wifi,"phys",phys);json_object_object_add(root,"wifi",wifi);
 if(!phys)issue(issues,"WIFI_PHY_UNAVAILABLE","Wi-Fi 无线设备未就绪","未检测到无线 PHY；这与仅关闭无线接口不同，请检查驱动加载与校准日志。");
 if(fallback)issue(issues,"WIFI_REFERENCE_CALIBRATION","Wi-Fi 使用了默认校准","本机校准未被正确采用，请保留日志并检查驱动与校准文件。");
 if(kernel&&strstr(kernel,"Disabling IRQ #40"))issue(issues,"PCIE_IRQ_DISABLED","PCIe 中断已被停用","内核记录了未处理的中断；相关无线功能可能已经失效。");
 if(kernel&&strstr(kernel,"WARNING:"))issue(issues,"KERNEL_WARNING","本次启动出现内核警告","请查看内核日志中的调用栈；即使功能已恢复，也需要确认警告原因。");
 json_object *storage=json_object_new_object();struct statvfs fs;if(!statvfs("/overlay",&fs))add_i(storage,"overlay_available_bytes",(long long)fs.f_bavail*(long long)fs.f_frsize);else json_object_object_add(storage,"overlay_available_bytes",NULL);
 bool protected=true,known=true;long long corrected=0,failed=0;
 for(int i=0;i<7;i++){char path[128];snprintf(path,sizeof(path),"/sys/class/mtd/mtd%d/flags",i);long long flags=number(path,-1);if(flags<0)known=false;else if((bool)(flags&0x400)!=(i==5))protected=false;snprintf(path,sizeof(path),"/sys/class/mtd/mtd%d/corrected_bits",i);long long n=number(path,-1);if(n>=0)corrected+=n;snprintf(path,sizeof(path),"/sys/class/mtd/mtd%d/ecc_failures",i);n=number(path,-1);if(n>=0)failed+=n;}
 if(known)add_b(storage,"protected_readonly",protected);else json_object_object_add(storage,"protected_readonly",NULL);add_i(storage,"corrected_bits",corrected);add_i(storage,"ecc_failures",failed);json_object_object_add(root,"storage",storage);
 if(failed)issue(issues,"NAND_UNCORRECTABLE_ECC","存储读取出现不可纠正错误","请导出诊断并保留原始现场，不要反复擦写存储。");
 json_object *watchdog=json_object_new_object();bool registered=access("/sys/class/watchdog/watchdog0",F_OK)==0;add_b(watchdog,"registered",registered);json_object_object_add(root,"watchdog",watchdog);
 json_object *acceleration=json_object_new_object();char *crypto=read_file("/proc/crypto",LIMIT);add_s(acceleration,"crypto",crypto&&strstr(crypto,"eip93")?"硬件算法已注册":"未检测到 EIP93 算法");add_s(acceleration,"npu","需要当前固件握手证据");add_s(acceleration,"offload","需要当前流量验证");free(crypto);json_object_object_add(root,"acceleration",acceleration);json_object_object_add(root,"issues",issues);
 free(boot);free(revision);free(online);return root;
}
static json_object *log_snapshot(char **kernel_out)
{
 char *ka[]={"/bin/dmesg",NULL},*la[]={"/sbin/logread","-l","150",NULL};
 char *kernel=command(ka[0],ka),*system=command(la[0],la);json_object *logs=json_object_new_object();
 char *safe=redact(kernel);json_object_object_add(logs,"kernel",lines_json(safe));free(safe);safe=redact(system);json_object_object_add(logs,"system",lines_json(safe));free(safe);
 char *boot=read_file("/proc/sys/kernel/random/boot_id",128);trim(boot);json_object *dsl=current_dsl(boot?boot:"unknown",uptime_s()),*events=NULL;if(dsl&&json_object_object_get_ex(dsl,"events",&events))json_object_object_add(logs,"dsl",json_object_get(events));else json_object_object_add(logs,"dsl",json_object_new_array());if(dsl)json_object_put(dsl);free(boot);
 free(system);*kernel_out=kernel;return logs;
}
static json_object *empty_object(json_object *o){return o?o:json_object_new_object();}
static json_object *status_snapshot(void)
{
 json_object *o=read_json(RUN"/status.json"),*system=NULL,*stamp=NULL;char *boot=read_file("/proc/sys/kernel/random/boot_id",128);trim(boot);
 bool valid=o&&boot&&json_object_object_get_ex(o,"system",&system)&&!strcmp(string_field(system,"boot_id"),boot)&&json_object_object_get_ex(system,"uptime_s",&stamp);
 double age=valid?uptime_s()-json_object_get_double(stamp):1e9;
 if(valid&&isfinite(age)&&age>=0&&age<=30){json_object *dsl=current_dsl(boot,uptime_s()),*internet=NULL;json_object_object_add(o,"dsl",dsl);if(json_object_object_get_ex(dsl,"internet",&internet))json_object_object_add(o,"internet",json_object_get(internet));else{internet=json_object_new_object();add_s(internet,"state","offline");add_b(internet,"authenticated",false);add_b(internet,"ipv4",false);add_b(internet,"ipv6",false);add_s(internet,"detail","DSL 会话证据缺失或已经过期");json_object_object_add(o,"internet",internet);}free(boot);return o;}
 free(boot);
 if(o)json_object_put(o);
 o=json_object_new_object();add_s(o,"error","DIAGNOSTICS_STALE");return o;
}
static int daemon_main(void)
{
 umask(077);mkdir("/etc/ponwrt",0700);mkdir(SAVE,0700);mkdir(RUN,0700);
 int lock=open(RUN"/diagnostics.lock",O_RDWR|O_CREAT|O_NOFOLLOW|O_CLOEXEC,0600);if(lock<0||flock(lock,LOCK_EX|LOCK_NB))return 1;
 json_object *old=read_json(SAVE"/current.json"),*history=read_json(SAVE"/history.json");if(!history||!json_object_is_type(history,json_type_array)){if(history)json_object_put(history);history=json_object_new_array();}
 if(old){char *boot=read_file("/proc/sys/kernel/random/boot_id",128);trim(boot);if(!boot||strcmp(string_field(old,"boot_id"),boot)){json_object_array_add(history,old);while(json_object_array_length(history)>8)json_object_array_del_idx(history,0,1);atomic_json(SAVE"/history.json",history);}else json_object_put(old);free(boot);}
 atomic_json(RUN"/history.json",history);json_object_put(history);signal(SIGTERM,stop_handler);signal(SIGINT,stop_handler);
 double last_persist=-120;char *previous_stage=NULL;json_object *snapshot=NULL,*logs=NULL;
 while(running){char *kernel=NULL;if(logs)json_object_put(logs);logs=log_snapshot(&kernel);if(snapshot)json_object_put(snapshot);snapshot=collect(kernel);free(kernel);atomic_json(RUN"/status.json",snapshot);atomic_json(RUN"/logs.json",logs);
  json_object *dsl=NULL,*code=NULL;json_object_object_get_ex(snapshot,"dsl",&dsl);if(dsl)json_object_object_get_ex(dsl,"code",&code);const char *current=code?json_object_get_string(code):"";double up=uptime_s();
  if(!previous_stage||strcmp(previous_stage,current)||up-last_persist>=120){json_object *record=json_object_new_object(),*sys=NULL;json_object_object_get_ex(snapshot,"system",&sys);add_s(record,"boot_id",sys?json_object_get_string(json_object_object_get(sys,"boot_id")):"unknown");add_s(record,"title","启动记录");add_s(record,"message",current);add_b(record,"clean_shutdown",false);json_object_object_add(record,"snapshot",json_object_get(snapshot));json_object_object_add(record,"logs",json_object_get(logs));atomic_json(SAVE"/current.json",record);json_object_put(record);last_persist=up;free(previous_stage);previous_stage=strdup(current);}
  for(int i=0;i<10&&running;i++)sleep(1);
 }
 json_object *record=read_json(SAVE"/current.json");if(record){add_b(record,"clean_shutdown",true);atomic_json(SAVE"/current.json",record);json_object_put(record);}if(snapshot)json_object_put(snapshot);if(logs)json_object_put(logs);free(previous_stage);close(lock);return 0;
}
static json_object *input_json(void){char b[4097];size_t n=fread(b,1,sizeof(b)-1,stdin);b[n]=0;return json_tokener_parse(b);}
static json_object *retry_dsl(void)
{
 json_object *o=json_object_new_object();bool accepted=false;long long generation=0;
 int fd=-1;char dir[]=RUN"/diag-retry.XXXXXX";bool directory=false;struct sockaddr_un local={.sun_family=AF_UNIX},peer={.sun_family=AF_UNIX};struct stat st;
 if(lstat(DSL_CONTROL,&st)||!S_ISSOCK(st.st_mode)||st.st_uid!=0||(st.st_mode&077))goto done;
 if(!mkdtemp(dir))goto done;
 directory=true;fd=socket(AF_UNIX,SOCK_DGRAM|SOCK_CLOEXEC,0);if(fd<0)goto done;
 snprintf(local.sun_path,sizeof(local.sun_path),"%s/client",dir);strcpy(peer.sun_path,DSL_CONTROL);
 int one=1;if(setsockopt(fd,SOL_SOCKET,SO_PASSCRED,&one,sizeof(one)))goto done;
 mode_t old=umask(077);int rc=bind(fd,(struct sockaddr *)&local,sizeof(local));umask(old);if(rc||chmod(local.sun_path,0600))goto done;
 if(connect(fd,(struct sockaddr *)&peer,sizeof(peer))||send(fd,"retry",5,0)!=5)goto done;
 struct pollfd poller={.fd=fd,.events=POLLIN};if(poll(&poller,1,2000)!=1)goto done;
 char response[80]={0};union {struct cmsghdr align;char bytes[CMSG_SPACE(sizeof(struct ucred))+CMSG_SPACE(8*sizeof(int))];} ancillary;struct iovec iov={.iov_base=response,.iov_len=sizeof(response)-1};
 struct msghdr msg={.msg_iov=&iov,.msg_iovlen=1,.msg_control=ancillary.bytes,.msg_controllen=sizeof(ancillary.bytes)};
 ssize_t n=recvmsg(fd,&msg,MSG_DONTWAIT|MSG_CMSG_CLOEXEC);if(n<=0)goto done;
 bool root=false,bad=(msg.msg_flags&(MSG_TRUNC|MSG_CTRUNC))!=0;
 for(struct cmsghdr *c=CMSG_FIRSTHDR(&msg);c;c=CMSG_NXTHDR(&msg,c)){
  if(c->cmsg_level==SOL_SOCKET&&c->cmsg_type==SCM_CREDENTIALS&&c->cmsg_len==CMSG_LEN(sizeof(struct ucred))){struct ucred cred;memcpy(&cred,CMSG_DATA(c),sizeof(cred));root=cred.uid==0;}
  else{bad=true;if(c->cmsg_level==SOL_SOCKET&&c->cmsg_type==SCM_RIGHTS){size_t bytes=c->cmsg_len>=CMSG_LEN(0)?c->cmsg_len-CMSG_LEN(0):0;int *fds=(int *)CMSG_DATA(c);for(size_t i=0;i<bytes/sizeof(int);i++)close(fds[i]);}}
 }
 if(!root||bad||n<5||memcmp(response,"ACK ",4)||(size_t)n!=strlen(response))goto done;
 for(ssize_t i=4;i<n;i++)if(response[i]<'0'||response[i]>'9')goto done;
 char *end=NULL;errno=0;generation=strtoll(response+4,&end,10);
 if(errno||generation<=0||!end||*end)goto done;
 accepted=true;add_i(o,"generation",generation);
done:
 if(fd>=0)close(fd);
 if(directory){if(local.sun_path[0])unlink(local.sun_path);rmdir(dir);}
 add_b(o,"accepted",accepted);add_s(o,"detail",accepted?"DSL 服务已确认新一轮启动，请核对阶段进度":"DSL 服务未确认重试，请检查服务状态与日志");return o;
}
static json_object *rpc_call(const char *method)
{
 if(!strcmp(method,"status"))return status_snapshot();
 if(!strcmp(method,"history")){json_object *o=json_object_new_object(),*history=read_json(SAVE"/history.json");json_object_object_add(o,"boots",history?history:json_object_new_array());return o;}
 if(!strcmp(method,"logs")){json_object *args=input_json(),*source=NULL,*logs=read_json(RUN"/logs.json"),*lines=NULL,*out=json_object_new_object();const char *name="system";if(args&&json_object_object_get_ex(args,"source",&source)&&json_object_is_type(source,json_type_string))name=json_object_get_string(source);
  if(!strcmp(name,"previous")){json_object *history=read_json(SAVE"/history.json");size_t n=history?json_object_array_length(history):0;json_object *record=n?json_object_array_get_idx(history,n-1):NULL,*oldlogs=NULL;if(record&&json_object_object_get_ex(record,"logs",&oldlogs))json_object_object_get_ex(oldlogs,"kernel",&lines);json_object_object_add(out,"lines",lines?json_object_get(lines):json_object_new_array());if(history)json_object_put(history);}
  else{if(strcmp(name,"system")&&strcmp(name,"kernel")&&strcmp(name,"dsl"))name="system";if(logs)json_object_object_get_ex(logs,name,&lines);json_object_object_add(out,"lines",lines?json_object_get(lines):json_object_new_array());}
  add_s(out,"detail","已脱敏；日志与阶段证据需结合阅读");if(args)json_object_put(args);if(logs)json_object_put(logs);return out;}
 if(!strcmp(method,"support")){json_object *out=json_object_new_object();add_i(out,"schema",1);add_b(out,"redacted",true);json_object_object_add(out,"status",status_snapshot());json_object_object_add(out,"logs",empty_object(read_json(RUN"/logs.json")));json_object *history=read_json(SAVE"/history.json");json_object_object_add(out,"history",history?history:json_object_new_array());return out;}
 if(!strcmp(method,"retry"))return retry_dsl();
 json_object *error=json_object_new_object();add_s(error,"error","unknown_method");return error;
}
int main(int argc,char **argv)
{
 if(argc==2&&!strcmp(argv[1],"daemon"))return daemon_main();
 if(argc==2&&!strcmp(argv[1],"list")){puts("{\"status\":{},\"logs\":{\"source\":\"string\"},\"history\":{},\"support\":{},\"retry\":{}}");return 0;}
 if(argc==3&&!strcmp(argv[1],"call")){json_object *o=rpc_call(argv[2]);puts(json_object_to_json_string_ext(o,JSON_C_TO_STRING_PLAIN));json_object_put(o);return 0;}
 fputs("usage: ponwrt-diag daemon | list | call METHOD\n",stderr);return 2;
}
