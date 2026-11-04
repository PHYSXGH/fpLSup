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

    def test_no_formats_yet(self):
        self.assertEqual(self.f['formats'], [])
        self.assertEqual(list((self.out / 'RESCUS').iterdir()), [])

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

    def test_boots_under_loader_v4_and_lets_go_without_formats(self):
        sys.path.insert(0, str(ROOT / 'fpSup' / 'loader-v4'))
        if os.environ.get('FPSUP_CAMERA') != 'fpl':
            self.skipTest('the emulated boot runs the camera this process was started for (FPSUP_CAMERA=fpl)')
        import test_v4 as T4
        if T4.Uc is None:
            self.skipTest('needs unicorn')
        files, dirs = T4.card((NAME, self.core), extra=[('RESCUS', 0x10, 0)])
        files['\\fpSup\\LOAD.LOG'] = b''
        dirs['\\fpSup\\RESCUS'] = []
        cam = T4.Camera(files, dirs)
        cam.boot()
        self.assertIsNone(cam.error)
        log = cam.loadlog()
        self.assertIn((T4.CODES['RELEASED'], NAME), [(c, t) for c, _, _, t in log], log)
        self.assertNotIn(T4.CODES['REPAIRED'], [c for c, *_ in log])
        self.assertNotIn(T4.CODES['CONFLICT'], [c for c, *_ in log])


if __name__ == '__main__':
    unittest.main()
