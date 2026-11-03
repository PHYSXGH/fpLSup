#!/usr/bin/env python3
"""The camera-side distortion fit, checked against the arithmetic it stands in for.

distfit.inc.S has no libm to lean on and no room for sixteen-point least
squares, so it carries its own arctangent and solves three collocation
equations outright.  This mirrors both in Python and holds them against the
real thing, so a change to the assembly that changes the answer shows up here
rather than in a clip.
"""
import math
import unittest

# --- what the assembly does, instruction for instruction ---------------------

AT = [-1 / 3, 1 / 5, -1 / 7, 1 / 9, -1 / 11, 1 / 13, -1 / 15]


def asm_atan(u):
    """Two halvings, then the plain series, exactly as pg_atan runs it."""
    for _ in range(2):
        u = u / (1.0 + math.sqrt(1.0 + u * u))
    x2 = u * u
    s = AT[6]
    for c in reversed(AT[:6]):
        s = c + s * x2
    return u * (1.0 + s * x2) * 4.0


RHO = (0.55, 0.85, 1.00)


def asm_fit(kr, s, normalise=True):
    """pg_dist_fit: collocation at three radii, solved by Cramer's rule."""
    k0 = kr[0] if normalise else 1.0
    m, b = [], []
    for rho in RHO:
        u = rho * s
        r2 = rho * rho
        g = (kr[0] + kr[1] * r2 + kr[2] * r2 * r2 + kr[3] * r2 ** 3) / k0
        th = asm_atan(u)
        m.append([th ** 3, th ** 5, th ** 7])
        b.append(g * rho * s - th)

    def det(a):
        return (a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
                - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
                + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0]))

    d = det(m)
    out = []
    for c in range(3):
        n = [row[:] for row in m]
        for r in range(3):
            n[r][c] = b[r]
        out.append(det(n) / d)
    return out


def asm_interpolate(axis, nodes, a, plane=1):
    """pg_dist_kr's bracketing and lerp."""
    i = 0
    for j in range(1, 4):
        if a >= axis[j]:
            i = j
    t = min(max((a - axis[i]) / (axis[i + 1] - axis[i]), 0.0), 1.0)
    lo, hi = nodes[i][plane], nodes[i + 1][plane]
    return [lo[k] + t * (hi[k] - lo[k]) for k in range(4)]


# --- the LUMIX S 40/F2, read off the camera at 0xC307CE2C / 0xC307D270 -------

AXIS = (0, 18641, 37283, 49637, 55924)
GREEN = [(+0.987878098, +0.000230792, -0.001804660, +0.012710940),
         (+0.995612771, -0.003803673, -0.003186222, +0.011056404),
         (+0.999854447, -0.010596089, +0.003693395, +0.003874420),
         (+0.999856513, -0.016680599, +0.013089761, -0.003420052),
         (+0.999845119, -0.020184787, +0.018855619, -0.007281209)]
NODES = [[kr, kr, kr] for kr in GREEN]        # only the green plane is used

W, H, FOCAL_MM = 1936, 1090, 40.0
FOCAL_PX = W * FOCAL_MM / 35.9
RMAX = math.hypot(W / 2, H / 2)
S = RMAX / FOCAL_PX


class Atan(unittest.TestCase):
    def test_matches_libm_over_the_range_a_frame_can_produce(self):
        worst = max(abs(asm_atan(u) - math.atan(u))
                    for u in [x / 2000 for x in range(0, 3001)])
        # A hundredth of a nanoradian.  Multiplied by a focal length of two
        # thousand pixels that is 3e-8 px, so the series stops where it does.
        self.assertLess(worst, 1e-10, f'atan off by {worst}')

    def test_still_exact_at_the_top_of_the_range(self):
        # 1.5 is past any crop the fp offers; two halvings must still cover it.
        self.assertLess(abs(asm_atan(1.5) - math.atan(1.5)), 1e-10)


class Fit(unittest.TestCase):
    def residual(self, coeffs, kr):
        """Worst radial error over the frame, in pixels."""
        k0 = kr[0]
        worst = 0.0
        for k in range(1, 17):
            rho = k / 16
            r2 = rho * rho
            g = (kr[0] + kr[1] * r2 + kr[2] * r2 * r2 + kr[3] * r2 ** 3) / k0
            th = math.atan(rho * S)
            model = th + sum(coeffs[i] * th ** (3 + 2 * i) for i in range(3))
            worst = max(worst, abs(model - g * rho * S) * FOCAL_PX)
        return worst

    def test_every_focus_node_fits_within_a_tenth_of_a_pixel(self):
        for i, kr in enumerate(GREEN):
            with self.subTest(node=i):
                self.assertLess(self.residual(asm_fit(kr, S), kr), 0.1)

    def test_interpolation_reproduces_a_real_dng(self):
        """A001's WarpRectilinear is a point on this table, not a fit to it.

        The clip's focus is not recorded anywhere, so the weight is recovered
        from one coefficient and the other three have to follow.  They do, to
        every digit the DNG carries -- which is what says the camera
        interpolates this table linearly and nothing else.
        """
        red = [(+0.988186498, -0.000141155, -0.001774456, +0.012716836),
               (+0.995987233, -0.004059714, -0.003203755, +0.011073191),
               (+1.000259153, -0.010650879, +0.003483107, +0.003991585),
               (+1.000265411, -0.016602340, +0.012760489, -0.003239510),
               (+1.000258102, -0.020125213, +0.018681989, -0.007207876)]
        dng = (1.000263615, -0.014894077, 0.010097579, -0.001163950)
        lo, hi = red[2], red[3]
        t = (dng[1] - lo[1]) / (hi[1] - lo[1])          # from kr1 alone
        for k in (0, 2, 3):
            self.assertAlmostEqual(lo[k] + t * (hi[k] - lo[k]), dng[k], places=8)

        # and the weight lands where a plausible focus distance would put it
        axis = AXIS[2] + t * (AXIS[3] - AXIS[2])
        self.assertAlmostEqual(16777216 / axis, 364.0, delta=1.0)

        # the same weight comes back out of the bracketing the assembly does
        kr = asm_interpolate(AXIS, [[c, c, c] for c in red], axis, plane=0)
        for got, want in zip(kr, dng):
            self.assertAlmostEqual(got, want, places=8)

    def test_breathing_is_not_absorbed_into_the_coefficients(self):
        # kr0 rides on the focal length.  Fitting with it left in wrecks the fit;
        # this pins the difference so the normalisation cannot quietly go away.
        kr = GREEN[0]                      # infinity, where breathing is largest
        good = self.residual(asm_fit(kr, S), kr)
        bad = self.residual(asm_fit(kr, S, normalise=False), kr)
        self.assertLess(good, 0.1)
        self.assertGreater(bad, 10.0)

    def test_axis_is_reciprocal_distance(self):
        for v, mm in zip(AXIS[1:], (900, 450, 338, 300)):
            self.assertAlmostEqual(16777216 / v, mm, delta=0.5)


class Source(unittest.TestCase):
    """Checks on the assembly that the arithmetic model cannot make.

    Both focal entries of the camera matrix have to be the one the breathing
    term was folded into.  pg_dist_prepare restores r0, so reading r0 after it
    silently puts the unscaled focal in the first row and the scaled one in the
    second -- which is what a real clip came out with.
    """




    def test_the_kr0_load_is_still_there(self):
        import pathlib
        asm = pathlib.Path(__file__).resolve().parent.joinpath('distfit.inc.S').read_text()
        # losing this made g collapse to zero and every right-hand side come
        # out as -theta, which still solved and still looked like numbers
        self.assertIn('vldr    d8, [r4]', asm)


if __name__ == '__main__':
    unittest.main()


# --- pg_dist_focal, run for real -------------------------------------------
class DistFocal(unittest.TestCase):
    """The calibration focal is the first word of a list of zoom positions.  A
    prime has one entry; a zoom has a rising list, and the first entry is only
    the wide end (SIGMA 28-70mm on the fp L: 28.9, 32.7 ... 67.7 mm).  So a zoom
    gets the mount's focal.  Runs the assembled routine under unicorn."""

    @classmethod
    def setUpClass(cls):
        try:
            from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
        except ImportError:
            raise unittest.SkipTest('needs unicorn')
        import pathlib, sys as _sys
        here = pathlib.Path(__file__).resolve().parent
        _sys.path.insert(0, str(here.parent / 'fp_usb_shell'))
        from armasm import assemble, symbols
        from fwtarget import fw
        src = here / 'distfit_probe.S'
        cls.code, cls.sym = assemble(src), symbols(src)
        cls.focal_at = fw(0xC307CDF0)
        cls.Uc, cls.ARM = Uc, (UC_ARCH_ARM, UC_MODE_ARM)

    def call(self, words, mount):
        import struct
        from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_LR, UC_ARM_REG_SP
        uc = self.Uc(*self.ARM)
        code_at, stack, done = 0x10000, 0x80000, 0x90000
        uc.mem_map(code_at, 0x10000); uc.mem_write(code_at, self.code)
        uc.mem_map(stack - 0x1000, 0x2000); uc.mem_map(done, 0x1000)
        page = self.focal_at & ~0xFFF
        uc.mem_map(page, 0x2000)
        uc.mem_write(self.focal_at, struct.pack('<%dI' % len(words), *words))
        uc.reg_write(UC_ARM_REG_R0, mount)
        uc.reg_write(UC_ARM_REG_SP, stack)
        uc.reg_write(UC_ARM_REG_LR, done)
        uc.emu_start(code_at + self.sym['pg_dist_focal'], done, count=1000)
        return uc.reg_read(UC_ARM_REG_R0)

    def test_a_prime_gets_its_calibration_focal(self):
        self.assertEqual(self.call([394, 0xFFFF], 400), 394)     # Art 40mm: 39.4 measured
        self.assertEqual(self.call([450, 0xFFFF], 450), 450)     # 45mm F2.8 on the fp L

    def test_a_prime_with_anything_but_a_rising_next_word_is_a_prime(self):
        self.assertEqual(self.call([394, 0], 400), 394)
        self.assertEqual(self.call([394, 394], 400), 394)
        self.assertEqual(self.call([394, 0x7FFFFFFF], 400), 394)

    def test_a_zoom_gets_the_mount_focal_not_the_wide_end(self):
        zoom = [289, 327, 365, 386, 409, 430, 453, 520, 677, 0xFFFF]
        self.assertEqual(self.call(zoom, 350), 350)              # 35 mm, not 28.9
        self.assertEqual(self.call(zoom, 280), 280)              # even at the wide end

    def test_implausible_calibration_still_falls_back(self):
        self.assertEqual(self.call([0, 0xFFFF], 400), 400)
        self.assertEqual(self.call([900, 0xFFFF], 400), 400)     # more than a quarter off
