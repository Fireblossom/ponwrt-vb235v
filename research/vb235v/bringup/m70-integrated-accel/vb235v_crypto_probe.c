// SPDX-License-Identifier: GPL-2.0-only
#include <linux/module.h>
#include <linux/of.h>
#include <linux/scatterlist.h>
#include <linux/slab.h>
#include <linux/rtnetlink.h>
#include <crypto/skcipher.h>
#include <crypto/aead.h>
#include <crypto/authenc.h>
#include <crypto/hash.h>
#include <linux/crypto.h>

struct vector { const char *driver; unsigned int kind,keylen,len,authsize; u8 digest[32]; };
#include "crypto-vectors.h"
static u8 pattern(unsigned int i) { return (i*13+i/17+0x5a)&255; }
static void fill(u8 *p,unsigned int n) { for(unsigned int i=0;i<n;i++)p[i]=pattern(i); }
static bool plain_ok(u8 *p,unsigned int n) { for(unsigned int i=0;i<n;i++)if(p[i]!=pattern(i))return false;return true; }
static void sg_make(struct scatterlist *sg,u8 *buf,unsigned int n,bool split)
{
	sg_init_table(sg,split?2:1);
	if(split){sg_set_buf(sg,buf,513);sg_set_buf(sg+1,buf+513,n-513);}
	else sg_set_buf(sg,buf,n);
}
static int digest_check(u8 *buf,unsigned int n,const u8 *expected)
{
	struct crypto_shash *tfm=crypto_alloc_shash("sha256",0,0);
	struct shash_desc *desc;u8 result[32];int ret;
	if(IS_ERR(tfm))return PTR_ERR(tfm);
	desc=kmalloc(sizeof(*desc)+crypto_shash_descsize(tfm),GFP_KERNEL);
	if(!desc){crypto_free_shash(tfm);return -ENOMEM;}
	desc->tfm=tfm;ret=crypto_shash_digest(desc,buf,n,result);
	if(!ret&&memcmp(result,expected,32))ret=-EBADMSG;
	kfree(desc);crypto_free_shash(tfm);return ret;
}
static int cipher_test(const struct vector *v,bool split)
{
	struct crypto_skcipher *tfm=crypto_alloc_skcipher(v->driver,0,0);
	struct skcipher_request *req=NULL;struct scatterlist src[2],dst[2];
	DECLARE_CRYPTO_WAIT(wait);u8 key[32],iv[16],*in=NULL,*out=NULL;int ret;
	if(IS_ERR(tfm))return PTR_ERR(tfm);
	if(strcmp(crypto_tfm_alg_driver_name(crypto_skcipher_tfm(tfm)),v->driver)){ret=-EINVAL;goto done;}
	in=kmalloc(v->len+16,GFP_KERNEL);out=kmalloc(v->len+16,GFP_KERNEL);
	req=skcipher_request_alloc(tfm,GFP_KERNEL);
	if(!in||!out||!req){ret=-ENOMEM;goto done;}
	for(unsigned int i=0;i<32;i++)key[i]=i;
	ret=crypto_skcipher_setkey(tfm,key,v->keylen);if(ret)goto done;
	fill(in+split,v->len);sg_make(src,in+split,v->len,split);sg_make(dst,out+split,v->len,split);
	skcipher_request_set_callback(req,CRYPTO_TFM_REQ_MAY_BACKLOG,crypto_req_done,&wait);
	for(unsigned int i=0;i<16;i++)iv[i]=0x30+i;
	skcipher_request_set_crypt(req,src,dst,v->len,iv);
	ret=crypto_wait_req(crypto_skcipher_encrypt(req),&wait);if(ret)goto done;
	ret=digest_check(out+split,v->len,v->digest);if(ret)goto done;
	for(unsigned int i=0;i<16;i++)iv[i]=0x30+i;
	skcipher_request_set_crypt(req,dst,src,v->len,iv);
	ret=crypto_wait_req(crypto_skcipher_decrypt(req),&wait);
	if(!ret&&!plain_ok(in+split,v->len))ret=-EBADMSG;
done:
	skcipher_request_free(req);kfree(in);kfree(out);crypto_free_skcipher(tfm);return ret;
}
static int aead_test(const struct vector *v,bool split)
{
	struct crypto_aead *tfm=crypto_alloc_aead(v->driver,0,0);
	struct aead_request *req=NULL;struct scatterlist sg[2];DECLARE_CRYPTO_WAIT(wait);
	u8 keyblob[8+48+32]={0},iv[16],*buf=NULL,*saved=NULL;int ret;const char *phase="driver";
	unsigned int total=32+v->len+v->authsize;
	struct rtattr *rta=(struct rtattr *)keyblob;
	struct crypto_authenc_key_param *param=(void *)(keyblob+4);
	if(IS_ERR(tfm))return PTR_ERR(tfm);
	if(strcmp(crypto_tfm_alg_driver_name(crypto_aead_tfm(tfm)),v->driver)){ret=-EINVAL;goto done;}
	pr_info("M70_CRYPTO_AEAD_PROVIDER module=%s\n",module_name(crypto_aead_tfm(tfm)->__crt_alg->cra_module));
	rta->rta_type=CRYPTO_AUTHENC_KEYA_PARAM;rta->rta_len=8;param->enckeylen=cpu_to_be32(v->keylen);
	for(unsigned int i=0;i<48;i++)keyblob[8+i]=0x80+i;
	for(unsigned int i=0;i<v->keylen;i++)keyblob[56+i]=i;
	phase="setkey";ret=crypto_aead_setkey(tfm,keyblob,56+v->keylen);if(ret)goto done;
	phase="authsize";ret=crypto_aead_setauthsize(tfm,v->authsize);if(ret)goto done;
	buf=kmalloc(total+16,GFP_KERNEL);saved=kmalloc(total,GFP_KERNEL);req=aead_request_alloc(tfm,GFP_KERNEL);
	if(!buf||!saved||!req){ret=-ENOMEM;goto done;}
	for(unsigned int i=0;i<32;i++)buf[split+i]=i;
	fill(buf+split+32,v->len);sg_make(sg,buf+split,total,split);
	aead_request_set_callback(req,CRYPTO_TFM_REQ_MAY_BACKLOG,crypto_req_done,&wait);aead_request_set_ad(req,32);
	for(unsigned int i=0;i<16;i++)iv[i]=0x30+i;
	aead_request_set_crypt(req,sg,sg,v->len,iv);
	phase="encrypt";ret=crypto_wait_req(crypto_aead_encrypt(req),&wait);if(ret)goto done;
	phase="oracle";ret=digest_check(buf+split,total,v->digest);if(ret)goto done;
	memcpy(saved,buf+split,total);
	for(unsigned int i=0;i<16;i++)iv[i]=0x30+i;
	aead_request_set_crypt(req,sg,sg,v->len+v->authsize,iv);
	phase="decrypt";ret=crypto_wait_req(crypto_aead_decrypt(req),&wait);if(ret)goto done;
	if(!plain_ok(buf+split+32,v->len)){ret=-EBADMSG;goto done;}
	for(unsigned int tamper=0;tamper<4;tamper++){
		unsigned int offsets[]={0,32+v->len/2,32+v->len,total-1};
		memcpy(buf+split,saved,total);buf[split+offsets[tamper]]^=1;
		for(unsigned int i=0;i<16;i++)iv[i]=0x30+i;
		aead_request_set_crypt(req,sg,sg,v->len+v->authsize,iv);
		phase="tamper";ret=crypto_wait_req(crypto_aead_decrypt(req),&wait);
		pr_info("M70_CRYPTO_TAMPER offset=%u ret=%d expected=%d\n",offsets[tamper],ret,-EBADMSG);
		if(ret!=-EBADMSG){if(!ret)ret=-EINVAL;goto done;}
	}
	ret=0;
done:
	pr_info("M70_CRYPTO_AEAD phase=%s ret=%d\n",phase,ret);
	aead_request_free(req);kfree(buf);kfree(saved);crypto_free_aead(tfm);return ret;
}
static int hash_test(const struct vector *v,bool split)
{
	struct crypto_ahash *tfm=crypto_alloc_ahash(v->driver,0,0);
	struct ahash_request *req=NULL;struct scatterlist sg[2];DECLARE_CRYPTO_WAIT(wait);
	u8 key[48],result[32],*buf=NULL;int ret;
	if(IS_ERR(tfm))return PTR_ERR(tfm);
	if(strcmp(crypto_tfm_alg_driver_name(crypto_ahash_tfm(tfm)),v->driver)){ret=-EINVAL;goto done;}
	if(v->kind==3){for(unsigned int i=0;i<48;i++)key[i]=0x80+i;ret=crypto_ahash_setkey(tfm,key,48);if(ret)goto done;}
	buf=kmalloc(v->len+16,GFP_KERNEL);req=ahash_request_alloc(tfm,GFP_KERNEL);
	if(!buf||!req){ret=-ENOMEM;goto done;}
	fill(buf+split,v->len);sg_make(sg,buf+split,v->len,split);
	ahash_request_set_callback(req,CRYPTO_TFM_REQ_MAY_BACKLOG,crypto_req_done,&wait);
	ahash_request_set_crypt(req,sg,result,v->len);
	ret=crypto_wait_req(crypto_ahash_digest(req),&wait);
	if(!ret&&memcmp(result,v->digest,32))ret=-EBADMSG;
done:
	ahash_request_free(req);kfree(buf);crypto_free_ahash(tfm);return ret;
}
static int __init vb235v_crypto_probe_init(void)
{
	unsigned int passed=0,failed=0;
	if(!of_machine_is_compatible("tplink,vb235v-ram-accel-development"))return -ENODEV;
	for(unsigned int i=0;i<ARRAY_SIZE(vectors);i++)for(unsigned int split=0;split<2;split++){
		const struct vector *v=&vectors[i];int ret;
		pr_info("M70_CRYPTO_BEGIN case=%u split=%u driver=%s keybytes=%u bytes=%u\n",i,split,v->driver,v->keylen,v->len);
		ret=v->kind==0?cipher_test(v,split):v->kind==1?aead_test(v,split):hash_test(v,split);
		pr_info("M70_CRYPTO_RESULT case=%u split=%u ret=%d\n",i,split,ret);
		if(ret)failed++;else passed++;
	}
	pr_info("M70_CRYPTO_COMPLETE passed=%u errors=%u\n",passed,failed);return failed?-EIO:0;
}
static void __exit vb235v_crypto_probe_exit(void) {}
module_init(vb235v_crypto_probe_init);module_exit(vb235v_crypto_probe_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("VB235v RAM-only EIP93 large-request oracle checks");
