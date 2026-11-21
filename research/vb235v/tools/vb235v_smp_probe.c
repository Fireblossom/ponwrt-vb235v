/* SPDX-License-Identifier: GPL-2.0-only */
#define _GNU_SOURCE
#include <errno.h>
#include <inttypes.h>
#include <pthread.h>
#include <sched.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define CORES 2
#define WORDS 32768
#define ROUNDS 1024
static uint64_t data[CORES][WORDS] __attribute__((aligned(64)));
static pthread_barrier_t barrier;
static atomic_uint errors, cpu_mask;
static uint64_t checksums[CORES];
static uint64_t pattern(unsigned core,unsigned round,unsigned index)
{
	uint64_t x=UINT64_C(0x9e3779b97f4a7c15)*(index+1);
	x^=(uint64_t)(round+1)<<32 | (core+1);
	x^=x>>30; x*=UINT64_C(0xbf58476d1ce4e5b9);
	x^=x>>27; x*=UINT64_C(0x94d049bb133111eb);
	return x^(x>>31);
}
static void *worker(void *arg)
{
	unsigned core=(unsigned)(uintptr_t)arg;
	cpu_set_t set;
	uint64_t sum=0;
	CPU_ZERO(&set); CPU_SET(core,&set);
	if(pthread_setaffinity_np(pthread_self(),sizeof(set),&set))
		atomic_fetch_add(&errors,1);
	for(unsigned round=0;round<ROUNDS;round++) {
		int cpu=sched_getcpu();
		if(cpu!=(int)core) atomic_fetch_add(&errors,1);
		else atomic_fetch_or(&cpu_mask,1U<<cpu);
		for(unsigned i=0;i<WORDS;i++) data[core][i]=pattern(core,round,i);
		pthread_barrier_wait(&barrier);
		for(unsigned owner=0;owner<CORES;owner++)
			for(unsigned i=0;i<WORDS;i++) {
				uint64_t value=data[owner][i];
				if(value!=pattern(owner,round,i)) atomic_fetch_add(&errors,1);
				sum=(sum<<1 | sum>>63)^value;
			}
		pthread_barrier_wait(&barrier);
	}
	checksums[core]=sum;
	return NULL;
}
int main(void)
{
	pthread_t threads[CORES];
	struct timespec start,end;
	clock_gettime(CLOCK_MONOTONIC,&start);
	if(pthread_barrier_init(&barrier,NULL,CORES)) return 2;
	for(unsigned i=0;i<CORES;i++)
		if(pthread_create(&threads[i],NULL,worker,(void *)(uintptr_t)i)) return 2;
	for(unsigned i=0;i<CORES;i++) pthread_join(threads[i],NULL);
	clock_gettime(CLOCK_MONOTONIC,&end);
	for(unsigned i=1;i<CORES;i++)
		if(checksums[i]!=checksums[0]) atomic_fetch_add(&errors,1);
	double seconds=end.tv_sec-start.tv_sec+(end.tv_nsec-start.tv_nsec)/1e9;
	printf("{\"threads\":%u,\"rounds\":%u,\"barrier_phases\":%u,\"shared_words_checked\":%llu,\"cpu_mask\":%u,\"errors\":%u,\"checksum\":\"%016" PRIx64 "\",\"seconds\":%.3f}\n",
	       CORES,ROUNDS,ROUNDS*2,(unsigned long long)CORES*CORES*WORDS*ROUNDS,
	       atomic_load(&cpu_mask),atomic_load(&errors),checksums[0],seconds);
	return atomic_load(&errors)||atomic_load(&cpu_mask)!=((1U<<CORES)-1);
}
