.syntax unified
.arm
.text
/* RAM-only fault catcher: the vectors' handlers point here.  The first fault is recorded in
 * `rec`; every fault returns into `spin` (ARM, IT/T cleared) in the interrupted mode, so the
 * faulting task parks and, if the scheduler still runs, the USB shell can read `rec`. */
.global entry_und
entry_und:
    push    {r0-r3}
    mov     r0, #3
    b       common
.global entry_pabt
entry_pabt:
    push    {r0-r3}
    mov     r0, #2
    b       common
.global entry_dabt
entry_dabt:
    push    {r0-r3}
    mov     r0, #1
common:
    ldr     r1, recp
    ldr     r2, [r1]
    cmp     r2, #0
    bne     1f
    str     r0, [r1, #4]            @ kind: 1 data abort, 2 prefetch abort, 3 undefined
    str     lr, [r1, #8]            @ lr_<mode>: fault pc + 8 (dabt) / + 4 (pabt, und)
    mrs     r3, spsr
    str     r3, [r1, #12]
    mrc     p15, 0, r3, c6, c0, 0   @ DFAR
    str     r3, [r1, #16]
    mrc     p15, 0, r3, c5, c0, 0   @ DFSR
    str     r3, [r1, #20]
    mrc     p15, 0, r3, c6, c0, 2   @ IFAR
    str     r3, [r1, #24]
    mrc     p15, 0, r3, c5, c0, 1   @ IFSR
    str     r3, [r1, #28]
    ldr     r3, [sp]
    str     r3, [r1, #32]           @ r0
    ldr     r3, [sp, #4]
    str     r3, [r1, #36]           @ r1
    ldr     r3, [sp, #8]
    str     r3, [r1, #40]           @ r2
    ldr     r3, [sp, #12]
    str     r3, [r1, #44]           @ r3
    add     r3, r1, #48
    stmia   r3, {r4-r12}            @ r4..r12 at +48..+80
    add     r3, r1, #84
    stmia   r3, {sp, lr}^           @ user/system sp, lr at +84, +88
    mrc     p15, 0, r3, c0, c0, 5   @ MPIDR
    str     r3, [r1, #92]
1:  add     r2, r2, #1
    str     r2, [r1]                @ count
    mrs     r3, spsr
    bic     r3, r3, #0x20           @ T
    bic     r3, r3, #0x06000000     @ IT[1:0]
    bic     r3, r3, #0xFC00         @ IT[7:2]
    msr     spsr_cxsf, r3
    pop     {r0-r3}
    mov     lr, pc                  @ pc reads two ahead: the spin loop just after movs
    movs    pc, lr
spin:
    b       .
.balign 4
.global recp
recp:
    .word   0
