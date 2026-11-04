.syntax unified
.arm
.text
.global readcp
readcp:
    mrc     p15, 0, r0, c12, c0, 0      @ VBAR
    mrc     p15, 0, r2, c1, c0, 0       @ SCTLR (bit 13 V: high vectors 0xFFFF0000)
    mrc     p15, 0, r3, c0, c0, 5       @ MPIDR (which core)
    ldr     r1, scratch
    str     r0, [r1]
    str     r2, [r1, #4]
    str     r3, [r1, #8]
    bx      lr
.balign 4
.global scratch
scratch:
    .word   0
