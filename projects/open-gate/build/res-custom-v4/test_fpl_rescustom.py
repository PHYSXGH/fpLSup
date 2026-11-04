"""res-custom built for the fp L (FPSUP_CAMERA=fpl): what can be checked before fp L formats exist.

    cd projects/open-gate/build/res-custom-v4 && python3 -B -m unittest test_fpl_rescustom

The build is run with FPSUP_CAMERA=fpl whatever this process's camera is; the checks read the fp L
image (out_fpl/MAIN_c0000000.bin).  The full emulated suite (test_v3/v4_rescustom) stays fp-only:
its camera model is the fp's and every format borrows IMX410 modes (port phase 3).

Static, plus one emulated boot (the real Loader v4); not on the camera.
"""
import json
import os
import pathlib
import struct
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[3]
IMAGE = ROOT / 'out_fpl' / 'MAIN_c0000000.bin'
NAME = 'RES-Custom_v0.1.5.BIN'
PICKS = {0xC043BAB0: 0xC043D0A8, 0xC043BAE4: 0xC043D108, 0xC043BB10: 0xC043CE68}   # site -> lookup
KEYBLD_FPL = 0xC043BFB4            # the playback key builder's return (fp 0xC043BCBC)
_BUILT = {}


def built():
    if 'b' not in _BUILT:
        out = pathlib.Path(tempfile.mkdtemp(prefix='ogcfpl-')) / 'o'
        env = dict(os.environ, FPSUP_CAMERA='fpl')
        r = subprocess.run([sys.executable, '-B', str(HERE / 'build_v4_rescustom.py'), '--out', str(out)],
                           capture_output=True, text=True, env=env)
        if r.returncode:
            raise RuntimeError(r.stderr[-4000:])
        facts = json.loads((out / 'build.json').read_text())['files'][NAME]['facts']
        _BUILT['b'] = ((out / NAME).read_bytes(), facts, out)
    return _BUILT['b']


def word(img, a):
    return struct.unpack_from('<I', img, a - 0xC0000000)[0]


def bl_target(site, w):
    off = w & 0xFFFFFF
    off -= (1 << 24) if off & 0x800000 else 0
    return site + 8 + 4 * off


def movw_movt(code, value):
    """offsets of a Thumb movw/movt pair loading value into one register"""
    ops = []
    for i in range(0, len(code) - 4, 2):
        h1, h2 = struct.unpack_from('<2H', code, i)
        if h1 & 0xFBF0 in (0xF240, 0xF2C0) and not h2 & 0x8000:
            imm = (h1 & 0xF) << 12 | (h1 >> 10 & 1) << 11 | (h2 >> 12 & 7) << 8 | (h2 & 0xFF)
            ops.append((i, bool(h1 & 0x80), imm, h2 >> 8 & 0xF))
    return [i for k, (i, top, imm, rd) in enumerate(ops) if not top and imm == value & 0xFFFF
            and any(t and r == rd and v == value >> 16 for _, t, v, r in ops[k + 1:k + 6])]


@unittest.skipUnless(IMAGE.exists(), 'needs the fp L image')
class FplBuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.core, cls.f, cls.out = built()
        cls.img = IMAGE.read_bytes()

    def hooks(self):
        return [(int(h['site'], 16), h['kind']) for h in self.f['hooks']]

    def replays(self):
        return {int(h['site'], 16): int(h['replay'], 16) for h in self.f['hooks']}

    def test_the_formats_ship(self):
        """OG4K and OG48K; not UHDX (stock UHD under a new name would take every UHD-sized key, ogc_name)"""
        self.assertEqual(self.f['formats'], ['og4k', 'og48k'])
        self.assertEqual(sorted(p.name for p in (self.out / 'RESCUS').iterdir()), ['OG48K.RCD', 'OG4K.RCD'])

    def test_og4k_rides_on_mode_98(self):
        import rcd
        d = rcd.decode((self.out / 'RESCUS' / 'OG4K.RCD').read_bytes(), self.img, None)
        self.assertEqual((d['profile'], d['base_row'], d['act'], d['aspect'], d['flags']),
                         (2061, 1841, (3840, 2552), 2, 1))
        self.assertEqual({e['key'] for e in d['entries']},
                         {'OG4K23_98FPS', 'OG4K24FPS', 'OG4K25FPS', 'OG4K29_97FPS'})
        self.assertTrue(all(e['donor'] == 98 for e in d['entries']))

    def test_10_and_12_bit_follow_the_stock_profiles(self):
        """OG4K and OG48K offer 8/10/12; the core writes canvas +0x80/+0x84 by the picked depth with the
        fp L's stock values (p2061 / p2391 / p2721, UHD 23.98 8 / 10 / 12-bit: 9,10 / 9,9 / 7,7)"""
        import rcd
        sys.path.insert(0, str(ROOT / 'projects' / 'fpl-port' / 'tools'))
        import canvas_compare as C
        cols = C.columns(self.img, C.FPL['builder'])
        stock = []
        for pid in (2061, 2391, 2721):
            row = word(self.img, C.FPL['mapping'] + 4 * pid)
            stock.append((word(self.img, cols[0x80] + 4 * row), word(self.img, cols[0x84] + 4 * row)))
        self.assertEqual(stock, [(9, 10), (9, 9), (7, 7)])
        src = (HERE / 'ogc.c').read_text()
        self.assertIn('W(canvas + 0x80) = bd == BD12 ? 7u : 9u;', src)
        self.assertIn('W(canvas + 0x84) = bd == BD8 ? 10u : bd == BD10 ? 9u : 7u;', src)
        for name in ('OG4K', 'OG48K'):
            d = rcd.decode((self.out / 'RESCUS' / f'{name}.RCD').read_bytes(), self.img, None)
            self.assertEqual(d['bit_depths'], (8, 10, 12), name)

    def test_og4k_resize_is_stock_p2001s(self):
        """canvas +0x60/+0x64/+0xD0/+0xD4: the read -> raster downscale x 1024.  OG4K reads mode 98's
        2x-binned 4784 wide into 3856 -- stock p2001's ratio (4784x2700 -> 3856x2170), not its base
        p2061's (9568 -> 3856, 2539; card r6 recorded a 1928-wide picture with it)"""
        import rcd
        sys.path.insert(0, str(ROOT / 'projects' / 'fpl-port' / 'tools'))
        import canvas_compare as C
        cols = C.columns(self.img, C.FPL['builder'])
        row = word(self.img, C.FPL['mapping'] + 4 * 2001)
        p2001 = {o: word(self.img, c + 4 * row) for o, c in cols.items()}
        self.assertEqual((p2001[0xF4], p2001[0x00], p2001[0xFC]), (4784, 3856, 0x40000000))
        d = rcd.decode((self.out / 'RESCUS' / 'OG4K.RCD').read_bytes(), self.img, None)
        rec = dict(d['canvas_rec'])
        self.assertEqual((rec[0xF4], rec[0x00], rec[0xFC]), (4784, 3856, 0x40000000))
        for off in (0x60, 0x64, 0xD0, 0xD4):
            self.assertEqual(rec[off], p2001[off], hex(off))

    def test_the_three_picks_are_bl_hooks_on_the_lookups_and_last(self):
        hooks = self.hooks()
        self.assertEqual([s for s, _ in hooks[-3:]], sorted(PICKS))
        for site, kind in hooks[-3:]:
            self.assertEqual(kind, 1, hex(site))                          # HOOK_BL
            w = word(self.img, site)
            self.assertEqual(w & 0xFF000000, 0xEB000000, hex(site))
            self.assertEqual(bl_target(site, w), PICKS[site], hex(site))

    def test_no_fp_only_hook(self):
        names = set(self.f['hook_names'].values())
        self.assertFalse(names & {'picker', 'v32', 'binpath'}, names)
        self.assertTrue({'pick8', 'pick10', 'pick12'} <= names)

    def test_every_site_is_in_the_image_and_claimed_once(self):
        claims = [int(c['address'], 16) for c in self.f['claims']]
        self.assertEqual(len(claims), len(set(claims)))
        for site, kind in self.hooks():
            self.assertIn(site, claims)
            self.assertTrue(0xC0000000 <= site < 0xC0000000 + len(self.img), hex(site))
            if not self.replays()[site]:                     # no replay: the way down is the stock bl
                self.assertEqual(word(self.img, site) & 0x0F000000, 0x0B000000, hex(site))

    def test_keybld_is_the_fp_l_playback_key_builder(self):
        self.assertTrue(movw_movt(self.core, KEYBLD_FPL))
        self.assertFalse(movw_movt(self.core, 0xC043BCBC), 'the fp address leaked')
        # the call it returns from: the playback key builder's one vtable+0xC call
        self.assertEqual(word(self.img, KEYBLD_FPL - 4), 0xE12FFF33)       # blx r3
        self.assertEqual(word(self.img, KEYBLD_FPL - 0x10), 0xE592300C)    # ldr r3, [r2, #0xc]

    def boot(self, with_rcd):
        sys.path.insert(0, str(ROOT / 'fpSup' / 'loader-v4'))
        if os.environ.get('FPSUP_CAMERA') != 'fpl':
            self.skipTest('the emulated boot runs the camera this process was started for (FPSUP_CAMERA=fpl)')
        import test_v4 as T4
        if T4.Uc is None:
            self.skipTest('needs unicorn')
        rcdb = (self.out / 'RESCUS' / 'OG4K.RCD').read_bytes()
        files, dirs = T4.card((NAME, self.core), extra=[('RESCUS', 0x10, 0)])
        files['\\fpSup\\LOAD.LOG'] = b''
        dirs['\\fpSup\\RESCUS'] = []
        if with_rcd:
            files['\\fpSup\\RESCUS\\OG4K.RCD'] = rcdb
            dirs['\\fpSup\\RESCUS'] = [('OG4K.RCD', 0x20, len(rcdb))]
        cam = T4.Camera(files, dirs)
        cam.boot()
        self.assertIsNone(cam.error)
        log = cam.loadlog()
        self.assertNotIn(T4.CODES['REPAIRED'], [c for c, *_ in log])
        self.assertNotIn(T4.CODES['CONFLICT'], [c for c, *_ in log])
        return T4, log

    def test_boots_under_loader_v4_and_lets_go_without_formats(self):
        T4, log = self.boot(False)
        self.assertIn((T4.CODES['RELEASED'], NAME), [(c, t) for c, _, _, t in log], log)

    def test_with_a_format_the_claims_and_the_bit_menu_go_in(self):
        """found 1, accepted 1, one row; then the claims, veneers and the bit-depth menu pass and the
        core reaches its menu rows (OCO: none here, the bare harness has no GUI -- the same point the
        fp core reaches with OG3K in this harness)"""
        T4, log = self.boot(True)
        texts = [t for c, _, _, t in log]
        self.assertIn('OCD01010100', texts, log)
        self.assertIn('OCO00000000', texts, log)

    def test_imx455_searches_find_the_donor_row_for_a_virtual_id(self):
        """lk_x3c / x5c / x0c (RESCUSTOM_PORT.md: the three IMX455-only per-mode tables): the shims run
        against the real search code.  A virtual id gets the donor's row (161 -> row 26 in all three),
        a real id goes straight down (217 -> 84), an id outside the range still misses (-1).  FN_DONOR is
        a stub answering 161 (ogc_donor: the vm's DONOR word)."""
        try:
            from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM
            from unicorn import arm_const as A
        except ImportError:
            self.skipTest('needs unicorn')
        core, facts = self.core, self.f
        L0, SC, sh = int(facts['layout0'], 16), int(facts['s_coord'], 16), facts['shims']
        S = facts['S']
        mu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        mu.mem_map(0xC0000000, (len(self.img) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(0xC0000000, self.img)
        lay = core[facts['img_off']: facts['img_off'] + (SC - L0) + 0x1000]
        mu.mem_write(L0, lay)                        # at its own coordinates: no pair rewrite needed
        WORK, STUB, OBJ, VM, DONE = 0x10000000, 0x10001000, 0x10002000, 0x10003000, 0x10004000
        mu.mem_map(WORK, 0x100000)
        put = lambda a, *v: mu.mem_write(a, struct.pack(f'<{len(v)}I', *v))
        put(STUB, 0xE3A000A1, 0xE12FFF1E)            # mov r0, #161; bx lr
        put(OBJ, 0xC0B98DE0, 0xC0BB05CC, 0xC0BB01C8)  # the sensor object 0xC343C5B4's three words
        put(VM + facts['VM']['DONOR'], 161)
        put(SC + S['VMID0'], 230)
        put(SC + S['NVM'], 1)
        put(SC + S['VMS'], (VM - SC) & 0xFFFFFFFF)
        put(SC + facts['fns']['DONOR'], STUB)
        hooks = {h['site']: h for h in facts['hooks']}

        def run(site, ident):
            h = hooks[f'0x{site:08X}']
            put(int(h['next'], 16), int(h['replay'], 16))
            mu.reg_write(A.UC_ARM_REG_SP, WORK + 0x80000)
            mu.reg_write(A.UC_ARM_REG_R0, OBJ)
            mu.reg_write(A.UC_ARM_REG_R1, ident)
            mu.reg_write(A.UC_ARM_REG_LR, DONE)
            mu.emu_start(int(h['to'], 16), DONE, count=2000)
            return mu.reg_read(A.UC_ARM_REG_R0)

        for site in (0xC032C658, 0xC032C6C0, 0xC032C728):
            with self.subTest(site=hex(site)):
                self.assertEqual(run(site, 230), 26)
                self.assertEqual(run(site, 217), 84)
                self.assertEqual(run(site, 231), 0xFFFFFFFF)
                self.assertEqual(run(site, 161), 26)

if __name__ == '__main__':
    unittest.main()
