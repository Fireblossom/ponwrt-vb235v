// SPDX-License-Identifier: GPL-2.0-only
#define main diagnostics_program_main
#include "diagnostics.c"
#undef main
#include <assert.h>

int main(void)
{
 const char *input="{\"state\":\"online\",\"code\":\"SESSION_READY\",\"generation\":7,\"password\":\"do-not-export\",\"line\":{\"showtime\":true},\"stages\":[{\"id\":\"ppp\",\"state\":\"done\"},{\"id\":\"internet\",\"state\":\"done\"}],\"internet\":{\"generation\":7,\"authenticated\":true,\"ipv4\":true,\"ipv6\":false,\"username\":\"do-not-export\"},\"events\":[{\"code\":\"LINK_UP\",\"detail\":\"peer 00:11:22:33:44:55 192.0.2.1 2001:db8::7\",\"raw\":\"do-not-export\"}]}";
 json_object *raw=json_tokener_parse(input),*out=project_dsl(raw,7),*internet=json_object_object_get(out,"internet");
 assert(true_field(internet,"authenticated")&&true_field(internet,"ipv4"));
 const char *serialized=json_object_to_json_string(out);assert(!strstr(serialized,"do-not-export")&&!strstr(serialized,"192.0.2.1")&&!strstr(serialized,"00:11:22:33:44:55")&&!strstr(serialized,"2001:db8::7"));json_object_put(out);
 /* A previous generation's session cannot turn a new attempt green. */
 out=project_dsl(raw,8);assert(!true_field(json_object_object_get(out,"internet"),"authenticated"));json_object_put(out);
 json_object_object_add(json_object_object_get(raw,"line"),"showtime",json_object_new_boolean(false));out=project_dsl(raw,7);assert(!true_field(json_object_object_get(out,"internet"),"authenticated"));json_object_put(out);
 json_object_object_add(json_object_object_get(raw,"line"),"showtime",json_object_new_boolean(true));json_object_object_add(json_object_array_get_idx(json_object_object_get(raw,"stages"),0),"state",json_object_new_string("running"));out=project_dsl(raw,7);assert(!true_field(json_object_object_get(out,"internet"),"authenticated"));json_object_put(out);json_object_put(raw);
 /* Missing, unexpected and hostile value types must remain unknown/offline. */
 const char *bad[]={"{}","[]","null","1","{\"line\":true,\"stages\":[null,3,{},[]],\"events\":[false,{},[]],\"internet\":\"online\"}","{\"state\":\"<img onerror=alert(1)>\",\"internet\":{\"generation\":7,\"authenticated\":\"true\",\"ipv4\":true}}"};
 for(size_t i=0;i<sizeof(bad)/sizeof(bad[0]);i++){raw=json_tokener_parse(bad[i]);out=project_dsl(raw,7);assert(!true_field(json_object_object_get(out,"internet"),"authenticated"));assert(json_object_array_length(json_object_object_get(out,"stages"))==6);json_object_put(out);if(raw)json_object_put(raw);}
 char *safe=redact("password=synthetic-password\nssid synthetic-network\nPAP sent private-user\nCHAP secret-packet\nsetup token abcd\nready link up\n");assert(!strstr(safe,"synthetic-password")&&!strstr(safe,"synthetic-network")&&!strstr(safe,"private-user")&&!strstr(safe,"secret-packet")&&!strstr(safe,"abcd")&&strstr(safe,"ready link up"));free(safe);
 puts("diagnostic evidence, generation gates and export redaction: PASS");return 0;
}
