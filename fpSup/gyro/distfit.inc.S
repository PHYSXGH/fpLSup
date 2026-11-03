/* ===========================================================================
 * distfit.inc.S -- the lens's own distortion, turned into Gyroflow's numbers.
 *
 * The firmware keeps, for the mounted lens, a table of five focus support
 * points, each holding four f64 radial coefficients per colour plane.  Those
 * are the numbers it writes into a DNG's WarpRectilinear opcode: interpolating
 * the table linearly reproduces a real DNG's opcode to nine decimal places, so
 * what comes out of here is the camera's own answer, not a fit to a picture.
 *
 *   0xC307CE2C   five u32, the support axis, in 2^24 / object distance in mm
 *                (0, 18641, 37283, 49637, 55924 = inf, 900, 450, 338, 300 mm)
 *   0xC307D270   five nodes x three planes x four doubles
 *
 * Two traps, both paid for:
 *
 *   kr0 is not 1.  It is the lens breathing -- 1.2% of magnification between
 *   infinity and the near limit on the 40 mm.  That is a focal length, not a
 *   distortion, so it multiplies the camera matrix and is divided out before
 *   the shape is fitted.  Fitting with it left in costs a factor of forty in
 *   residual, because the theta model's leading term is pinned at 1 and the
 *   coefficients have to absorb the scale.
 *
 *   The support axis is not the focus position the lens reports.  getfpos
 *   spans 5977..11116; the axis spans 0..55924.  They only meet through the
 *   object distance in millimetres.
 *
 * The fit is collocation at three radii rather than least squares over the
 * whole frame: 0.010..0.078 px of error against 0.016..0.061 for the sixteen
 * point fit, for three arctangents instead of sixteen and no accumulation.
 * ========================================================================= */

.equ F_FOCUS_POS,   0xC035FD48      /* () -> focus position, = lens getfpos   */
.equ F_FOCUS_DIST,  0xC035FE08      /* (pos) -> object distance in mm         */
.equ DIST_AXIS,     0xC307CE2C      /* five u32                               */
.equ DIST_TABLE,    0xC307D270      /* five x three x four f64                */
.equ DIST_PLANE,    1               /* green: the plane luminance follows     */
.equ DIST_INF,      0x07FFFFFF      /* what cnvfdist returns at infinity      */
.equ DIST_FOCAL,    0xC307CDF0      /* focal length the table was measured at */

/* ---------------------------------------------------------------------------
 * pg_dist_focal -- r0 = the focal length the mount reports, in tenths of a mm.
 * Returns the one the correction data was measured at, when there is one.
 *
 * The two disagree.  A SIGMA 40mm F1.4 Art reports 40.0 and calibrates at
 * 39.4; the LUMIX S 40/F2 says 40.0 to both.  The mount's number is the name
 * on the barrel, the block's is what the optics measured, and the camera
 * matrix wants the second: it is the scale that turns a gyro angle into a
 * pixel displacement, so 1.5% of error there is 1.5% of over-correction on
 * every rotation.  It costs only a seventh of a pixel on the distortion shape,
 * which is why this is worth doing for the stabiliser and not for the warp.
 *
 * Falls back to the mount whenever the block is empty or implausible, so a
 * lens with no correction data still gets its nominal focal length.
 * ------------------------------------------------------------------------- */
    .global pg_dist_focal
pg_dist_focal:
    push    {r4, lr}
    mov     r4, r0
    ldr_addr ip, DIST_FOCAL
    ldr     r0, [ip]
    /* A zoom lens: the word is the first of a list of zoom positions, rising,
     * and so only ever the wide end (SIGMA 28-70mm: 28.9, 32.7 ... 67.7 mm,
     * read on the fp L 2026-11-03, projects/fpl-port/LENS_TABLES.md).  A prime
     * has one entry and fill after it.  So a plausible, larger next word means
     * a zoom, and the mount's focal -- the one the lens is at now, from the
     * DNG's FocalLength getter (gcsv_json.S j_lens) -- is the number for it. */
    ldr     r1, [ip, #4]
    cmp     r1, r0
    bls     18f                         /* not rising: a prime                */
    movw    r2, #20000
    cmp     r1, r2
    bls     19f                         /* a zoom: the mount's focal          */
18:
    cmp     r0, #10                     /* nothing shorter than a millimetre */
    blo     19f
    movw    ip, #20000                  /* nor longer than two metres        */
    cmp     r0, ip
    bhi     19f
    subs    r1, r0, r4                  /* and within a quarter of the mount */
    rsblt   r1, r1, #0
    cmp     r4, r1, lsl #2
    blo     19f
    pop     {r4, pc}
19: mov     r0, r4
    pop     {r4, pc}

/* ---------------------------------------------------------------------------
 * pg_atan -- d0 = atan(d0).  Clobbers d1..d3.
 *
 * Two halvings bring any argument the frame can produce (0.52 at full frame,
 * under 1.5 for any crop) below a quarter, where the plain series is exact to
 * more places than a double carries.  No quadrant work: the argument is a
 * radius over a focal length, so it is never negative and never large.
 * ------------------------------------------------------------------------- */
    .align  3
    .global pg_atan
pg_atan:
    vmov.f64 d3, #1.0
    vmul.f64 d1, d0, d0                 /* halve once  */
    vadd.f64 d1, d1, d3
    vsqrt.f64 d1, d1
    vadd.f64 d1, d1, d3
    vdiv.f64 d0, d0, d1
    vmul.f64 d1, d0, d0                 /* halve twice */
    vadd.f64 d1, d1, d3
    vsqrt.f64 d1, d1
    vadd.f64 d1, d1, d3
    vdiv.f64 d0, d0, d1

    vmul.f64 d1, d0, d0                 /* Horner in x^2 */
    vldr    d2, pg_at7
    vldr    d3, pg_at6
    vmla.f64 d3, d2, d1
    vldr    d2, pg_at5
    vmla.f64 d2, d3, d1
    vldr    d3, pg_at4
    vmla.f64 d3, d2, d1
    vldr    d2, pg_at3
    vmla.f64 d2, d3, d1
    vldr    d3, pg_at2
    vmla.f64 d3, d2, d1
    vldr    d2, pg_at1
    vmla.f64 d2, d3, d1
    vmov.f64 d3, #1.0
    vmla.f64 d3, d2, d1
    vmul.f64 d0, d0, d3
    vadd.f64 d0, d0, d0                 /* undo the two halvings */
    vadd.f64 d0, d0, d0
    bx      lr

    .align  3
pg_at1: .double -0.33333333333333331
pg_at2: .double  0.20000000000000001
pg_at3: .double -0.14285714285714285
pg_at4: .double  0.11111111111111110
pg_at5: .double -0.09090909090909091
pg_at6: .double  0.07692307692307693
pg_at7: .double -0.06666666666666667

#ifndef FPSUP_CAMERA_FPL
/* ---------------------------------------------------------------------------
 * pg_dist_kr -- r0 = where to put four doubles.  Returns 1 if the mounted lens
 * has correction data, 0 if the table is empty or the focus cannot be read.
 * ------------------------------------------------------------------------- */
    .global pg_dist_kr
pg_dist_kr:
    push    {r4, r5, r6, r7, r8, lr}
    mov     r4, r0

    ldr_addr ip, F_FOCUS_POS
    blx     ip
    ldr_addr ip, F_FOCUS_DIST
    blx     ip                          /* r0 = object distance in mm */

    vldr    d4, pg_zero                 /* d4 = the axis value we are at */
    cmp     r0, #0
    ble     11f                         /* nonsense distance -> infinity */
    movw    r1, #:lower16:DIST_INF
    movt    r1, #:upper16:DIST_INF
    cmp     r0, r1
    bge     11f                         /* infinity -> axis 0 */
    vmov    s0, r0
    vcvt.f64.s32 d0, s0
    vldr    d1, pg_2p24
    vdiv.f64 d4, d1, d0
11:
    ldr_addr r5, DIST_AXIS
    mov     r6, #0                      /* the node we sit on */
    mov     r7, #1
12: cmp     r7, #4
    bge     13f
    ldr     r0, [r5, r7, lsl #2]
    vmov    s0, r0
    vcvt.f64.u32 d0, s0
    vcmp.f64 d4, d0
    vmrs    APSR_nzcv, fpscr
    blt     13f
    mov     r6, r7
    add     r7, r7, #1
    b       12b
13:
    /* t = (axis - a[i]) / (a[i+1] - a[i]), held to [0,1] */
    ldr     r0, [r5, r6, lsl #2]
    vmov    s0, r0
    vcvt.f64.u32 d0, s0
    add     r7, r6, #1
    ldr     r0, [r5, r7, lsl #2]
    vmov    s2, r0
    vcvt.f64.u32 d1, s2
    vsub.f64 d1, d1, d0                 /* the span */
    vcmp.f64 d1, #0.0
    vmrs    APSR_nzcv, fpscr
    beq     19f                         /* a degenerate axis is not usable */
    vsub.f64 d0, d4, d0
    vdiv.f64 d3, d0, d1                 /* t */
    vldr    d0, pg_zero
    vcmp.f64 d3, d0
    vmrs    APSR_nzcv, fpscr
    vmovlt.f64 d3, d0
    vmov.f64 d0, #1.0
    vcmp.f64 d3, d0
    vmrs    APSR_nzcv, fpscr
    vmovgt.f64 d3, d0

    /* lerp the plane's four coefficients between node i and node i+1 */
    ldr_addr r8, DIST_TABLE
    add     r0, r6, r6, lsl #1          /* 3 * i */
    add     r0, r0, #DIST_PLANE
    add     r0, r8, r0, lsl #5          /* the low node's record  */
    add     r1, r0, #96                 /* the high node's record */
    mov     r2, #4
14: vldr    d1, [r0]
    vldr    d2, [r1]
    vsub.f64 d2, d2, d1
    vmla.f64 d1, d2, d3
    vstr    d1, [r4]
    add     r0, r0, #8
    add     r1, r1, #8
    add     r4, r4, #8
    subs    r2, r2, #1
    bne     14b

    /* A lens with no data leaves the table zeroed; kr0 near one is the tell. */
    sub     r4, r4, #32
    vldr    d0, [r4]
    vldr    d1, pg_half
    vcmp.f64 d0, d1
    vmrs    APSR_nzcv, fpscr
    ble     19f
    vldr    d1, pg_onehalf
    vcmp.f64 d0, d1
    vmrs    APSR_nzcv, fpscr
    bge     19f
    mov     r0, #1
    pop     {r4, r5, r6, r7, r8, pc}
19: mov     r0, #0
    pop     {r4, r5, r6, r7, r8, pc}

#else   /* FPSUP_CAMERA_FPL */
/* ---------------------------------------------------------------------------
 * pg_dist_kr, fp L -- r0 = where to put four doubles.  Returns 1 if the
 * mounted lens has correction data, 0 if not.
 *
 * The same block as the fp's, read in full (projects/fpl-port/LENS_TABLES.md):
 *
 *   F+0x000   zoom positions, u32 tenths of a mm, rising       -> Nz (<= 15)
 *   F+0x03C   focus axis, Nz x Na rows of Nn u32, 2^24 / mm     -> Nn
 *   F+0x3CC   apertures, Nz rows of Na u32, APEX Av x 1024      -> Na
 *   F+0x480   records [zoom][aperture][node][plane], 4 f64 each
 *
 * Each list ends at 0xFFFF, 0x7FFFFFFF or 0xFFFFFFFF; the counts must divide
 * exactly or the block is not used.  A prime is Nz = 1 (SIGMA 45mm F2.8: 1 x 3
 * x 12), the SIGMA 28-70mm is 9 x 3 x 8.
 *
 * Where the lens is, from the camera at the moment of the call: the current
 * focal (the DNG FocalLength getter), the aperture (lens getav) and the focus
 * distance (getfpos -> cnvfdist; infinity is 0x7FFFFFFF here).  Zoom is
 * bracketed in the zoom list (linear in mm), then in each of the two
 * zoom rows the aperture
 * in that row's apertures, then in each of those rows the focus on that row's
 * own axis; each bracket is linear and held at its ends.  Eight records at
 * most, weighted, green plane.
 *
 * Then the radius: the camera's DNG carries kr_j x s^(2j) with s = 21.4908 /
 * 21.63 = 0.993564, two doubles of the firmware (fwtarget.SENSOR, defines
 * FPSUP_DIST_HALFDIAG_AT / FPSUP_DIST_REF_AT).  Run under unicorn against
 * ten DNGs (gyro/test_distfit.py FpLBlock), given the focal the camera
 * blended with.  Between zoom positions that is finer than the getter
 * reports (35.1 for 35.0): with the reported focal the 35 mm take is off by
 * 8e-4 in the coefficients, about a pixel at the 4K corner.
 * ------------------------------------------------------------------------- */
.equ F_FOCAL_NOW,   0xC03629D8      /* () -> current focal, tenths of a mm   */
.equ F_APERTURE,    0xC0362158      /* () -> APEX Av x 1024 = lens getav     */
.equ DIST_APS,      0x3CC           /* offsets in the block                  */
.equ DIST_ROWS,     0x3C
.equ DIST_RECS,     0x480
.equ DIST_NZ_MAX,   15
.equ DIST_NA_MAX,   45
.equ DIST_AX_MAX,   228
.equ KR_DZ, 0                       /* locals */
.equ KR_DA, 4
.equ KR_DN, 8
.equ KR_ZZ, 12
.equ KR_ROW, 16

    .global pg_dist_kr
pg_dist_kr:
    push    {r4, r5, r6, r7, r8, r9, r10, r11, lr}
    vpush   {d8, d9, d10, d11, d12, d13, d14, d15}
    sub     sp, sp, #28                 /* 36 + 64 + 28: eight-byte aligned */
    mov     r4, r0

    ldr_addr ip, F_FOCAL_NOW
    blx     ip
    vmov    s0, r0
    vcvt.f64.u32 d8, s0                 /* d8 = focal, tenths of a mm */
    ldr_addr ip, F_APERTURE
    blx     ip
    vmov    s0, r0
    vcvt.f64.s32 d9, s0                 /* d9 = Av x 1024 */
    ldr_addr ip, F_FOCUS_POS
    blx     ip
    ldr_addr ip, F_FOCUS_DIST
    blx     ip                          /* r0 = object distance in mm */
    vldr    d10, kr_zero                /* d10 = axis value, 0 = infinity */
    cmp     r0, #0
    ble     1f
    ldr_addr r1, DIST_INF               /* 0x07FFFFFF and up: 0x7FFFFFFF too */
    cmp     r0, r1
    bge     1f
    vmov    s0, r0
    vcvt.f64.s32 d0, s0
    vldr    d1, kr_2p24
    vdiv.f64 d10, d1, d0
1:
    ldr_addr r5, DIST_FOCAL             /* F, the block */
    mov     r0, r5
    mov     r1, #DIST_NZ_MAX
    bl      pg_count
    movs    r6, r0                      /* Nz */
    beq     99f
    add     r0, r5, #DIST_APS
    mov     r1, #DIST_NA_MAX
    bl      pg_count
    mov     r1, r6
    bl      pg_div_exact
    movs    r7, r0                      /* Na */
    beq     99f
    add     r0, r5, #DIST_ROWS
    mov     r1, #DIST_AX_MAX
    bl      pg_count
    mul     r1, r6, r7
    bl      pg_div_exact
    mov     r8, r0                      /* Nn */
    cmp     r8, #2
    blt     99f

    vldr    d0, kr_zero
    vstr    d0, [r4]
    vstr    d0, [r4, #8]
    vstr    d0, [r4, #16]
    vstr    d0, [r4, #24]

    mov     r0, r5                      /* zoom */
    mov     r1, r6
    vmov.f64 d0, d8
    bl      pg_bracket
    mov     r9, r0                      /* z */
    vmov.f64 d11, d0                    /* v: linear in mm, as the camera does
                                         * (A001_106/107/108: one weight fits
                                         * all four coefficients at 50.1, 35.1,
                                         * 60.0 mm).  The focal the camera blends
                                         * with is finer than the getter's 0.1 mm
                                         * steps say: 35.1 where it reports 35.0. */
    mov     r0, #0
    str     r0, [sp, #KR_DZ]
20: ldr     r0, [sp, #KR_DZ]
    cmp     r0, #2
    bge     50f
    vmov.f64 d14, d11                   /* wz = v for the upper row */
    cmp     r0, #0
    bne     21f
    vmov.f64 d1, #1.0
    vsub.f64 d14, d1, d11               /* 1 - v for the lower */
21: vcmp.f64 d14, #0.0
    vmrs    APSR_nzcv, fpscr
    beq     49f
    add     r1, r9, r0                  /* zz */
    str     r1, [sp, #KR_ZZ]
    mul     r2, r1, r7
    add     r0, r5, #DIST_APS
    add     r0, r0, r2, lsl #2          /* this zoom's apertures */
    mov     r1, r7
    vmov.f64 d0, d9
    bl      pg_bracket
    mov     r10, r0                     /* a */
    vmov.f64 d12, d0                    /* u */
    mov     r0, #0
    str     r0, [sp, #KR_DA]
30: ldr     r0, [sp, #KR_DA]
    cmp     r0, #2
    bge     49f
    vmov.f64 d15, d12
    cmp     r0, #0
    bne     31f
    vmov.f64 d1, #1.0
    vsub.f64 d15, d1, d12
31: vmul.f64 d15, d15, d14              /* wz wa */
    vcmp.f64 d15, #0.0
    vmrs    APSR_nzcv, fpscr
    beq     48f
    ldr     r1, [sp, #KR_ZZ]
    mul     r2, r1, r7
    add     r2, r2, r10
    add     r2, r2, r0                  /* row = zz Na + a + da */
    str     r2, [sp, #KR_ROW]
    mul     r3, r2, r8
    add     r0, r5, #DIST_ROWS
    add     r0, r0, r3, lsl #2          /* this row's axis */
    mov     r1, r8
    vmov.f64 d0, d10
    bl      pg_bracket
    mov     r11, r0                     /* n */
    vmov.f64 d13, d0                    /* t */
    mov     r0, #0
    str     r0, [sp, #KR_DN]
40: ldr     r0, [sp, #KR_DN]
    cmp     r0, #2
    bge     48f
    vmov.f64 d1, d13
    cmp     r0, #0
    bne     41f
    vmov.f64 d2, #1.0
    vsub.f64 d1, d2, d13
41: vmul.f64 d1, d1, d15                /* the record's weight */
    vcmp.f64 d1, #0.0
    vmrs    APSR_nzcv, fpscr
    beq     47f
    ldr     r2, [sp, #KR_ROW]
    mul     r3, r2, r8
    add     r3, r3, r11
    add     r3, r3, r0                  /* row Nn + n + dn */
    add     r3, r3, r3, lsl #1
    add     r3, r3, #DIST_PLANE
    add     r1, r5, #DIST_RECS
    add     r1, r1, r3, lsl #5          /* the record */
    mov     r2, #0
42: add     r3, r4, r2, lsl #3
    vldr    d2, [r1]
    vldr    d3, [r3]
    vmla.f64 d3, d2, d1
    vstr    d3, [r3]
    add     r1, r1, #8
    add     r2, r2, #1
    cmp     r2, #4
    blt     42b
47: ldr     r0, [sp, #KR_DN]
    add     r0, r0, #1
    str     r0, [sp, #KR_DN]
    b       40b
48: ldr     r0, [sp, #KR_DA]
    add     r0, r0, #1
    str     r0, [sp, #KR_DA]
    b       30b
49: ldr     r0, [sp, #KR_DZ]
    add     r0, r0, #1
    str     r0, [sp, #KR_DZ]
    b       20b
50:
    /* A lens with no data leaves the records zeroed; kr0 near one is the tell. */
    vldr    d0, [r4]
    vldr    d1, kr_half
    vcmp.f64 d0, d1
    vmrs    APSR_nzcv, fpscr
    ble     99f
    vldr    d1, kr_onehalf
    vcmp.f64 d0, d1
    vmrs    APSR_nzcv, fpscr
    bge     99f

    /* kr_j x s^(2j), s from the firmware's own two doubles */
    ldr_addr r0, FPSUP_DIST_HALFDIAG_AT
    ldr_addr r1, FPSUP_DIST_REF_AT
    vldr    d0, [r0]
    vldr    d1, [r1]
    vcmp.f64 d1, #0.0
    vmrs    APSR_nzcv, fpscr
    beq     99f
    vdiv.f64 d0, d0, d1                 /* s */
    vldr    d1, pg_s_lo                 /* not these two doubles: no data */
    vcmp.f64 d0, d1
    vmrs    APSR_nzcv, fpscr
    ble     99f
    vldr    d1, pg_s_hi
    vcmp.f64 d0, d1
    vmrs    APSR_nzcv, fpscr
    bge     99f
    vmul.f64 d0, d0, d0                 /* s^2 */
    vldr    d1, [r4, #8]
    vmul.f64 d1, d1, d0
    vstr    d1, [r4, #8]
    vmul.f64 d2, d0, d0                 /* s^4 */
    vldr    d1, [r4, #16]
    vmul.f64 d1, d1, d2
    vstr    d1, [r4, #16]
    vmul.f64 d2, d2, d0                 /* s^6 */
    vldr    d1, [r4, #24]
    vmul.f64 d1, d1, d2
    vstr    d1, [r4, #24]
    mov     r0, #1
    b       98f
99: mov     r0, #0
98: add     sp, sp, #28
    vpop    {d8, d9, d10, d11, d12, d13, d14, d15}
    pop     {r4, r5, r6, r7, r8, r9, r10, r11, pc}

    .align  3
pg_s_lo: .double 0.8
pg_s_hi: .double 1.25
kr_zero:    .double 0.0                 /* this routine's own: the file's pool */
kr_half:    .double 0.5                 /* is out of vldr reach from here      */
kr_onehalf: .double 1.5
kr_2p24:    .double 16777216.0

/* pg_count -- r0 = u32 list, r1 = how many at most.  r0 = entries before the
 * first 0xFFFF / 0x7FFFFFFF / 0xFFFFFFFF.  Clobbers r1-r3, ip. */
pg_count:
    mov     r2, #0
1:  cmp     r2, r1
    bhs     2f
    ldr     r3, [r0, r2, lsl #2]
    movw    ip, #0xFFFF
    cmp     r3, ip
    beq     2f
    cmn     r3, #1
    beq     2f
    mvn     ip, #0x80000000
    cmp     r3, ip
    beq     2f
    add     r2, r2, #1
    b       1b
2:  mov     r0, r2
    bx      lr

/* pg_div_exact -- r0 / r1, or 0 unless r1 divides r0 exactly and r0 > 0.
 * Clobbers r2. */
pg_div_exact:
    mov     r2, #0
    cmp     r1, #0
    beq     2f
1:  cmp     r0, r1
    blo     2f
    sub     r0, r0, r1
    add     r2, r2, #1
    b       1b
2:  cmp     r0, #0
    movne   r2, #0
    mov     r0, r2
    bx      lr

/* pg_bracket -- r0 = rising u32 list, r1 = entries (>= 1), d0 = the value.
 * r0 = i, d0 = t in [0, 1]: the value lies t of the way from entry i to
 * entry i + 1, held at the ends.  One entry, or a span that does not rise:
 * i, t = 0.  Clobbers r1-r3, ip, d1, d2. */
pg_bracket:
    mov     r2, #0
    sub     r1, r1, #1                  /* pairs: i <= entries - 2 */
    cmp     r1, #0
    ble     8f
1:  add     r3, r2, #1
    cmp     r3, r1
    bge     2f
    ldr     ip, [r0, r3, lsl #2]
    vmov    s2, ip
    vcvt.f64.u32 d1, s2
    vcmp.f64 d0, d1
    vmrs    APSR_nzcv, fpscr
    blt     2f
    mov     r2, r3
    b       1b
2:  ldr     ip, [r0, r2, lsl #2]
    vmov    s2, ip
    vcvt.f64.u32 d1, s2
    add     r3, r2, #1
    ldr     ip, [r0, r3, lsl #2]
    vmov    s4, ip
    vcvt.f64.u32 d2, s4
    vsub.f64 d2, d2, d1                 /* the span */
    vcmp.f64 d2, #0.0
    vmrs    APSR_nzcv, fpscr
    ble     8f
    vsub.f64 d0, d0, d1
    vdiv.f64 d0, d0, d2
    vldr    d1, kr_zero
    vcmp.f64 d0, d1
    vmrs    APSR_nzcv, fpscr
    vmovlt.f64 d0, d1
    vmov.f64 d1, #1.0
    vcmp.f64 d0, d1
    vmrs    APSR_nzcv, fpscr
    vmovgt.f64 d0, d1
    mov     r0, r2
    bx      lr
8:  vldr    d0, kr_zero
    mov     r0, r2
    bx      lr
#endif  /* FPSUP_CAMERA_FPL */

/* ---------------------------------------------------------------------------
 * pg_dist_fit -- r0 = the four kr doubles, r1 = room for four results,
 * r2 = 160 bytes of working room, d7 = s (corner radius over focal length).
 *
 * Collocation: four radii, four unknowns, solved outright.  The DNG maps a
 * corrected radius rho (of the corner distance) to a source radius
 * rho * f(rho); Gyroflow maps the same ray's angle to theta + k1 theta^3 +
 * k2 theta^5 + k3 theta^7 + k4 theta^9.  Equating them at four radii is a 4x4
 * system.  Three radii and k4 = 0 left up to 0.70 px at the 4K corner on the
 * 28-70's wide end; four leave 0.086 px at worst over fourteen fp L takes
 * (projects/fpl-port/LENS_TABLES.md).
 * ------------------------------------------------------------------------- */
    .global pg_dist_fit
pg_dist_fit:
    push    {r4, r5, r6, r7, r8, lr}
    vpush   {d8, d9, d10, d11}
    mov     r4, r0                      /* the four kr coefficients */
    mov     r5, r1                      /* where the four answers go */
    mov     r6, r2                      /* 160 bytes of working room, caller's:
                                         * on the stack it was one vpush away
                                         * from the base pointer and the bug
                                         * was invisible from the host. */
    vldr    d8, [r4]                    /* kr0: the breathing term the shape
                                         * is normalised by.  Losing this load
                                         * makes g collapse to zero and the
                                         * right-hand side come out as -theta. */
    adr     r7, pg_rho
    mov     r8, #0
20: add     r0, r7, r8, lsl #3
    vldr    d9, [r0]                    /* rho */
    vmul.f64 d10, d9, d7                /* u = rho * s */

    /* g(rho) = (kr0 + kr1 r2 + kr2 r2^2 + kr3 r2^3) / kr0 */
    vmul.f64 d1, d9, d9                 /* r2 */
    vldr    d2, [r4, #24]
    vldr    d3, [r4, #16]
    vmla.f64 d3, d2, d1
    vldr    d2, [r4, #8]
    vmla.f64 d2, d3, d1
    vldr    d3, [r4]
    vmla.f64 d3, d2, d1
    vdiv.f64 d3, d3, d8                 /* g */
    vmul.f64 d11, d3, d10               /* g rho s -- the source radius */

    vmov.f64 d0, d10
    bl      pg_atan                     /* theta; it touches no core register */
    vsub.f64 d11, d11, d0               /* b = g rho s - theta */
    add     r0, r6, r8, lsl #3
    vstr    d11, [r0, #128]             /* right-hand sides after the matrix */

    vmul.f64 d1, d0, d0                 /* theta^2 */
    vmul.f64 d2, d0, d1                 /* theta^3 */
    add     r0, r6, r8, lsl #5          /* row i, 32 bytes a row */
    vstr    d2, [r0]
    vmul.f64 d2, d2, d1                 /* theta^5 */
    vstr    d2, [r0, #8]
    vmul.f64 d2, d2, d1                 /* theta^7 */
    vstr    d2, [r0, #16]
    vmul.f64 d2, d2, d1                 /* theta^9 */
    vstr    d2, [r0, #24]

    add     r8, r8, #1
    cmp     r8, #4
    blt     20b

    bl      pg_solve4                   /* reads r6, writes through r5 */
    vpop    {d8, d9, d10, d11}
    pop     {r4, r5, r6, r7, r8, pc}

    .align  3
pg_rho: .double 0.40
        .double 0.70
        .double 0.90
        .double 1.00

/* ---------------------------------------------------------------------------
 * pg_solve4 -- r6 = a 4x4 matrix in row order (32 bytes a row) followed by
 * four right-hand sides, r5 = where the four answers go.  Gaussian
 * elimination with partial pivoting, then back substitution; destroys the
 * matrix.  r0 = 1, or 0 if a pivot is zero.  Clobbers d0-d4.
 * ------------------------------------------------------------------------- */
pg_solve4:
    push    {r4, r7, r8, lr}
    mov     r4, #0                      /* the column being cleared */
30: cmp     r4, #4
    bge     40f
    mov     r7, r4                      /* the pivot row: largest |a[p][k]| */
    add     ip, r6, r4, lsl #5
    add     ip, ip, r4, lsl #3
    vldr    d0, [ip]
    vabs.f64 d0, d0
    add     r8, r4, #1
31: cmp     r8, #4
    bge     32f
    add     ip, r6, r8, lsl #5
    add     ip, ip, r4, lsl #3
    vldr    d1, [ip]
    vabs.f64 d1, d1
    vcmp.f64 d1, d0
    vmrs    APSR_nzcv, fpscr
    vmovgt.f64 d0, d1
    movgt   r7, r8
    add     r8, r8, #1
    b       31b
32: vcmp.f64 d0, #0.0
    vmrs    APSR_nzcv, fpscr
    beq     39f
    cmp     r7, r4
    beq     34f
    mov     r8, #0                      /* swap rows k and p */
33: add     ip, r6, r4, lsl #5
    add     ip, ip, r8, lsl #3
    add     lr, r6, r7, lsl #5
    add     lr, lr, r8, lsl #3
    vldr    d1, [ip]
    vldr    d2, [lr]
    vstr    d2, [ip]
    vstr    d1, [lr]
    add     r8, r8, #1
    cmp     r8, #4
    blt     33b
    add     ip, r6, r4, lsl #3          /* and their right-hand sides */
    add     lr, r6, r7, lsl #3
    vldr    d1, [ip, #128]
    vldr    d2, [lr, #128]
    vstr    d2, [ip, #128]
    vstr    d1, [lr, #128]
34: add     ip, r6, r4, lsl #5
    add     ip, ip, r4, lsl #3
    vldr    d3, [ip]                    /* the pivot */
    add     r7, r4, #1                  /* every row below it */
35: cmp     r7, #4
    bge     38f
    add     ip, r6, r7, lsl #5
    add     ip, ip, r4, lsl #3
    vldr    d4, [ip]
    vdiv.f64 d4, d4, d3                 /* the factor */
    mov     r8, r4
36: add     ip, r6, r4, lsl #5          /* a[i][c] -= f a[k][c], c = k..3 */
    add     ip, ip, r8, lsl #3
    vldr    d1, [ip]
    add     lr, r6, r7, lsl #5
    add     lr, lr, r8, lsl #3
    vldr    d2, [lr]
    vmls.f64 d2, d4, d1
    vstr    d2, [lr]
    add     r8, r8, #1
    cmp     r8, #4
    blt     36b
    add     ip, r6, r4, lsl #3          /* b[i] -= f b[k] */
    vldr    d1, [ip, #128]
    add     lr, r6, r7, lsl #3
    vldr    d2, [lr, #128]
    vmls.f64 d2, d4, d1
    vstr    d2, [lr, #128]
    add     r7, r7, #1
    b       35b
38: add     r4, r4, #1
    b       30b

40: mov     r4, #3                      /* back substitution */
41: add     ip, r6, r4, lsl #3
    vldr    d0, [ip, #128]
    add     r8, r4, #1
42: cmp     r8, #4
    bge     43f
    add     ip, r6, r4, lsl #5
    add     ip, ip, r8, lsl #3
    vldr    d1, [ip]
    add     ip, r5, r8, lsl #3
    vldr    d2, [ip]
    vmls.f64 d0, d1, d2
    add     r8, r8, #1
    b       42b
43: add     ip, r6, r4, lsl #5
    add     ip, ip, r4, lsl #3
    vldr    d1, [ip]
    vdiv.f64 d0, d0, d1
    add     ip, r5, r4, lsl #3
    vstr    d0, [ip]
    subs    r4, r4, #1
    bpl     41b
    mov     r0, #1
    pop     {r4, r7, r8, pc}
39: mov     r0, #0
    pop     {r4, r7, r8, pc}

    .align  3
pg_zero:    .double 0.0
pg_half:    .double 0.5
pg_onehalf: .double 1.5
pg_2p24:    .double 16777216.0
