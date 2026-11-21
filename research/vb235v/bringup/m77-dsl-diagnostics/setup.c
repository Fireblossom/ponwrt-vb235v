// SPDX-License-Identifier: GPL-2.0-only
/* One-time local administrator setup. No passwords in argv or diagnostics. */
#define _GNU_SOURCE
#include <crypt.h>
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <json-c/json.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>

#define TOKEN_FILE "/etc/ponwrt/setup.token"
#define BODY_LIMIT 4096
static void reply(bool ok, const char *code, const char *message)
{
 json_object *o=json_object_new_object();
 json_object_object_add(o,"ok",json_object_new_boolean(ok));
 json_object_object_add(o,"code",json_object_new_string(code));
 json_object_object_add(o,"message",json_object_new_string(message));
 puts("Content-Type: application/json\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\nX-Frame-Options: DENY\r\n");
 puts(json_object_to_json_string_ext(o,JSON_C_TO_STRING_PLAIN));json_object_put(o);
}
static bool random_bytes(void *p,size_t n)
{
 int fd=open("/dev/urandom",O_RDONLY|O_CLOEXEC);if(fd<0)return false;
 size_t at=0;while(at<n){ssize_t r=read(fd,(char *)p+at,n-at);if(r<=0){close(fd);return false;}at+=(size_t)r;}
 close(fd);return true;
}
static int command(char *const argv[],char *output,size_t cap)
{
 int fds[2];if(pipe(fds))return -1;pid_t pid=fork();
 if(pid<0){close(fds[0]);close(fds[1]);return -1;}
 if(!pid){int null=open("/dev/null",O_RDWR);dup2(null,STDIN_FILENO);dup2(fds[1],STDOUT_FILENO);dup2(null,STDERR_FILENO);close(fds[0]);close(fds[1]);alarm(5);execv(argv[0],argv);_exit(127);}
 close(fds[1]);size_t used=0;char buf[256];ssize_t n;
 while((n=read(fds[0],buf,sizeof(buf)))>0){if(output&&used+(size_t)n<cap){memcpy(output+used,buf,(size_t)n);used+=(size_t)n;}}
 close(fds[0]);if(output&&cap)output[used]=0;int status=0;while(waitpid(pid,&status,0)<0&&errno==EINTR){}
 return WIFEXITED(status)?WEXITSTATUS(status):-1;
}
static bool configured(void)
{
 char buf[256];char *args[]={"/sbin/uci","-q","get","rpcd.ponwrt_admin.password",NULL};
 return command(args,buf,sizeof(buf))==0&&buf[0]&&buf[0]!='\n';
}
static bool tls(void)
{
 const char *v=getenv("HTTPS");return v&&(!strcmp(v,"on")||!strcmp(v,"1")||!strcmp(v,"yes"));
}
static bool same_origin(void)
{
 const char *origin=getenv("HTTP_ORIGIN"),*host=getenv("HTTP_HOST");char allowed[300];
 if(!origin)return true;
 if(!host||strlen(host)>250||strchr(host,'\r')||strchr(host,'\n'))return false;
 snprintf(allowed,sizeof(allowed),"https://%s",host);return !strcmp(origin,allowed);
}
static bool token_matches(const char *provided)
{
 char expected[66]={0};int fd=open(TOKEN_FILE,O_RDONLY|O_CLOEXEC|O_NOFOLLOW);if(fd<0)return false;
 struct stat st;if(fstat(fd,&st)||!S_ISREG(st.st_mode)||(st.st_mode&077)){close(fd);return false;}
 ssize_t n=read(fd,expected,sizeof(expected)-1);close(fd);if(n<64)return false;
 if(strlen(provided)!=64)return false;
 unsigned difference=0;
 for(size_t i=0;i<64;i++)difference|=(unsigned char)provided[i]^(unsigned char)expected[i];
 explicit_bzero(expected,sizeof(expected));return difference==0;
}
static bool set_uci(const char *operation,const char *value)
{
 char *args[]={"/sbin/uci","-q",(char *)operation,(char *)value,NULL};return command(args,NULL,0)==0;
}
static bool install_login(const char *password)
{
 static const char alphabet[]="./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";
 unsigned char bytes[16];char salt[64],hash[256],assignment[300];
 if(!random_bytes(bytes,sizeof(bytes)))return false;
 strcpy(salt,"$6$rounds=50000$");size_t n=strlen(salt);
 for(size_t i=0;i<sizeof(bytes);i++)salt[n++]=alphabet[bytes[i]&63];
 salt[n++]='$';salt[n]=0;
 char *value=crypt(password,salt);if(!value||strncmp(value,"$6$",3)||strlen(value)>=sizeof(hash))return false;
 strcpy(hash,value);snprintf(assignment,sizeof(assignment),"rpcd.ponwrt_admin.password=%s",hash);
 set_uci("delete","rpcd.ponwrt_admin");
 bool ok=set_uci("set","rpcd.ponwrt_admin=login")&&set_uci("set","rpcd.ponwrt_admin.username=admin")&&
  set_uci("set",assignment)&&set_uci("add_list","rpcd.ponwrt_admin.read=ponwrt-diagnostics")&&
  set_uci("add_list","rpcd.ponwrt_admin.write=ponwrt-diagnostics")&&set_uci("commit","rpcd")&&configured();
 explicit_bzero(hash,sizeof(hash));explicit_bzero(assignment,sizeof(assignment));explicit_bzero(salt,sizeof(salt));
 return ok;
}
static int init_token(void)
{
 if(configured())return 0;
 if(mkdir("/etc/ponwrt",0700)&&errno!=EEXIST)return 1;
 struct stat st;if(!lstat(TOKEN_FILE,&st))return S_ISREG(st.st_mode)&&!(st.st_mode&077)?0:1;
 unsigned char data[32];char hex[65];if(!random_bytes(data,sizeof(data)))return 1;
 for(size_t i=0;i<sizeof(data);i++)snprintf(hex+i*2,3,"%02x",data[i]);
 int fd=open(TOKEN_FILE,O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);if(fd<0)return 1;
 bool ok=write(fd,hex,64)==64&&!fsync(fd);close(fd);explicit_bzero(data,sizeof(data));explicit_bzero(hex,sizeof(hex));return ok?0:1;
}
int main(int argc,char **argv)
{
 if(argc==2&&!strcmp(argv[1],"--init"))return init_token();
 alarm(15);const char *method=getenv("REQUEST_METHOD");
 if(method&&!strcmp(method,"GET")){
  json_object *o=json_object_new_object();json_object_object_add(o,"setup_required",json_object_new_boolean(!configured()));
  json_object_object_add(o,"tls_required",json_object_new_boolean(!tls()));
  puts("Content-Type: application/json\r\nCache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n\r\n");
  puts(json_object_to_json_string_ext(o,JSON_C_TO_STRING_PLAIN));json_object_put(o);return 0;
 }
 if(!method||strcmp(method,"POST")){reply(false,"METHOD","仅支持初始化请求。");return 0;}
 if(!tls()||!same_origin()){reply(false,"TRANSPORT","请从设备自身的 HTTPS 页面设置密码。");return 0;}
 const char *type=getenv("CONTENT_TYPE"),*length=getenv("CONTENT_LENGTH");char *end;
 if(!type||strncmp(type,"application/json",16)||!length){reply(false,"BODY","请求格式不正确。");return 0;}
 errno=0;long count=strtol(length,&end,10);if(errno||*end||count<=0||count>BODY_LIMIT){reply(false,"BODY","请求长度不正确。");return 0;}
 char body[BODY_LIMIT+1];if(fread(body,1,(size_t)count,stdin)!=(size_t)count){reply(false,"BODY","请求未完整接收。");return 0;}body[count]=0;
 json_tokener *parser=json_tokener_new();json_object *o=json_tokener_parse_ex(parser,body,(int)count);
 bool parsed=json_tokener_get_error(parser)==json_tokener_success&&json_tokener_get_parse_end(parser)==(size_t)count;
 json_tokener_free(parser);json_object *token=NULL,*password=NULL;
 if(!parsed||!o||!json_object_is_type(o,json_type_object)||!json_object_object_get_ex(o,"token",&token)||!json_object_is_type(token,json_type_string)||!json_object_object_get_ex(o,"password",&password)||!json_object_is_type(password,json_type_string)){
  reply(false,"BODY","初始化参数不完整。");goto done;
 }
 const char *secret=json_object_get_string(password),*code=json_object_get_string(token);size_t bytes=(size_t)json_object_get_string_len(password);
 if(bytes<12||bytes>128||strlen(secret)!=bytes||strchr(secret,'\n')||strchr(secret,'\r')||(size_t)json_object_get_string_len(token)!=strlen(code)){
  reply(false,"PASSWORD","密码需为 12–128 字节，不能包含换行或空字符。");goto done;
 }
 int lock=open("/tmp/ponwrt-setup.lock",O_RDWR|O_CREAT|O_CLOEXEC|O_NOFOLLOW,0600);
 if(lock<0||flock(lock,LOCK_EX|LOCK_NB)){if(lock>=0)close(lock);reply(false,"BUSY","另一个设置请求正在处理。");goto done;}
 if(configured())reply(false,"ALREADY_SETUP","管理员已设置，请直接登录。");
 else if(!token_matches(code))reply(false,"TOKEN","初始化码不正确或已经失效。");
 else if(!install_login(secret))reply(false,"SAVE","设置未能完整保存，请检查存储状态后重试。");
 else{unlink(TOKEN_FILE);reply(true,"OK","管理员已设置。");}
 close(lock);
done:
 if(password&&json_object_is_type(password,json_type_string))explicit_bzero((void *)json_object_get_string(password),(size_t)json_object_get_string_len(password));
 if(o)json_object_put(o);
 explicit_bzero(body,sizeof(body));return 0;
}
