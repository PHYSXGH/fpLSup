.syntax unified
.arm
.text
.global readmmu
readmmu:
    ldr     r1, scratch
    mrc     p15, 0, r0, c2, c0, 0       @ TTBR0
    str     r0, [r1]
    mrc     p15, 0, r0, c2, c0, 1       @ TTBR1
    str     r0, [r1, #4]
    mrc     p15, 0, r0, c2, c0, 2       @ TTBCR
    str     r0, [r1, #8]
    mrc     p15, 0, r0, c3, c0, 0       @ DACR
    str     r0, [r1, #12]
    mrc     p15, 0, r0, c1, c0, 0       @ SCTLR (TRE bit 28, AFE 29)
    str     r0, [r1, #16]
    mrc     p15, 0, r0, c10, c2, 0      @ PRRR
    str     r0, [r1, #20]
    mrc     p15, 0, r0, c10, c2, 1      @ NMRR
    str     r0, [r1, #24]
    bx      lr
.balign 4
.global scratch
scratch:
    .word   0
