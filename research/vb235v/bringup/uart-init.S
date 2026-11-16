/* SPDX-License-Identifier: GPL-2.0-only */
/* Standalone AArch64 PID1. Only write(1,...) and nanosleep(); no shell,
 * device opens, ioctls, networking, reboot, or persistent storage access.
 * Linux asm-generic syscall numbers: write=64, nanosleep=101.
 */
.section .text
.global _start
.type _start, %function
_start:
1:
	mov x0, #1
	adr x1, message
	mov x2, #message_end - message
	mov x8, #64
	svc #0
	adr x0, delay
	mov x1, #0
	mov x8, #101
	svc #0
	b 1b
.size _start, . - _start

.section .rodata
message:
	.ascii "VB235v UART-only development PID1 alive; no peripheral tests performed.\n"
message_end:
.balign 8
delay:
	.quad 3, 0

.section .note.GNU-stack,"",%progbits
