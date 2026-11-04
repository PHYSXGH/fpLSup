.syntax unified
.arm
.text
/* fp L addresses (assembled with FPSUP_CAMERA=fp: nothing is mapped again) */
.equ MEM_HEAP, 0xC001CF78
.equ MEM_GET,  0xC001D038
.equ MEM_FREE, 0xC001D2B8
.equ F_CTOR,   0xC03660A8
.equ F_OPEN,   0xC03661C8          /* (obj, path, 7) = create */
.equ F_WRITE,  0xC0366300
.equ F_CLOSE,  0xC0366238
.equ F_DTOR,   0xC03660E8
.equ DCACHE,   0xC000E91C          /* clean the D-cache: the card write reads memory, not the cache */

.macro LDA reg, value
    movw    \reg, #:lower16:\value
    movt    \reg, #:upper16:\value
.endm

/* The trigger: the first instruction of the hooked function branches here.  Counts calls; on the
 * 5th, 15th and 40th writes [data_p, +len_p) to \PROBE1.BIN, \PROBE2.BIN, \PROBE3.BIN, then runs the
 * replaced instruction and goes back. */
.global trig
trig:
    push    {r0-r3, ip, lr}
    ldr     r2, cnt_p
    ldr     r3, [r2]
    add     r3, r3, #1
    str     r3, [r2]
    mov     r2, #0
    ldr     ip, th1
    cmp     r3, ip
    moveq   r2, #1
    ldr     ip, th2
    cmp     r3, ip
    moveq   r2, #2
    ldr     ip, th3
    cmp     r3, ip
    moveq   r2, #3
    cmp     r2, #0
    beq     1f
    ldr     ip, base_n
    add     r2, r2, ip              /* file number = 1..3 + base_n */
    ldr     r0, data_p
    cmp     r0, #0
    moveq   r0, sp                  /* no data address: the stack (the caller chain) */
    ldr     r1, len_p
    bl      sddump
1:  pop     {r0-r3, ip, lr}
.global orig
orig:
    .word   0                       /* the replaced instruction (host fills) */
    ldr     pc, back_p
.balign 4
.global back_p
back_p: .word 0                     /* hooked function + 4 */
.global data_p
data_p: .word 0
.global len_p
len_p:  .word 0
.global cnt_p
cnt_p:  .word 0                     /* -> cnt */
.global cnt
cnt:    .word 0
.global wrote
wrote:  .word 0                     /* files written (f_create succeeded) */
.global th1
th1:    .word 5
.global th2
th2:    .word 15
.global th3
th3:    .word 40
.global base_n
base_n: .word 0                     /* added to the file number (1..3) */

/* sddump(r0 data, r1 len, r2 n): \PROBEn.BIN on the SD card */
sddump:
    push    {r4-r8, lr}
    sub     sp, sp, #8
    mov     r4, r0
    mov     r5, r1
    mov     r6, r2
    mov     r0, #0
    LDA     ip, MEM_HEAP
    blx     ip
    mov     r7, r0
    mov     r1, #0x1000
    mov     r2, #0
    mov     r3, #0
    str     r3, [sp]
    LDA     ip, MEM_GET
    blx     ip
    cmp     r0, #0
    beq     9f
    mov     r8, r0
    add     r0, r8, #0xF00
    LDA     r1, 0x4F52505C          /* "\PRO" */
    str     r1, [r0]
    LDA     r1, 0x2E304542          /* "BE0." */
    add     r1, r1, r6, lsl #16     /* the digit */
    str     r1, [r0, #4]
    LDA     r1, 0x004E4942          /* "BIN\0" */
    str     r1, [r0, #8]
    mov     r0, r8
    mov     r1, #1                  /* the SD card */
    LDA     ip, F_CTOR
    blx     ip
    mov     r0, r8
    add     r1, r8, #0xF00
    mov     r2, #7
    LDA     ip, F_OPEN
    blx     ip
    cmp     r0, #0
    beq     8f
    ldr     r0, cnt_p
    ldr     r1, [r0, #4]            /* wrote++ */
    add     r1, r1, #1
    str     r1, [r0, #4]
    LDA     ip, DCACHE
    blx     ip
    mov     r0, r8
    mov     r1, r4
    mov     r2, r5
    LDA     ip, F_WRITE
    blx     ip
    mov     r0, r8
    LDA     ip, F_CLOSE
    blx     ip
8:  mov     r0, r8
    mov     r1, #2
    LDA     ip, F_DTOR
    blx     ip
    mov     r0, r7
    mov     r1, r8
    LDA     ip, MEM_FREE
    blx     ip
9:  add     sp, sp, #8
    pop     {r4-r8, pc}
