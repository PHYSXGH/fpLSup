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
        self.assertEqual(self.f['formats'], ['og4k', 'og48k', 'w48k', 'u48k', 'uhdc'])
        self.assertEqual(sorted(p.name for p in (self.out / 'RESCUS').iterdir()),
                         ['OG48K.RCD', 'OG4K.RCD', 'U48K.RCD', 'UHDC.RCD', 'W48K.RCD'])

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

    def test_rate_rows_parse_the_fp_l_keys(self):
        """key_rate_row (the frame-rate menu's greying): the fp L's keys end in FPS; the fp parser saw none
        of them and greyed every stock rate but the virtual 17.98 (camera, 2026-11-04).  The function
        from ogc.c, compiled on the host with OGC_FPL, against every rate token and some near misses."""
        import shutil
        if not shutil.which('cc'):
            self.skipTest('needs a host C compiler')
        src = (HERE / 'ogc.c').read_text()
        a = src.index('static u32 key_rate_row(u32 key, u32 lab)')
        fn = src[a:src.index('\n}\n', a) + 3]
        keys = ['OG4K23_98FPS', 'OG4K24FPS', 'OG4K25FPS', 'OG4K29_97FPS', 'OG4K48FPS', 'OG4K50FPS',
                'OG4K59_94FPS', 'OG4K100FPS', 'OG4K119_88FPS',
                'OG4K23_98', 'OG4K24', 'OG4K24FPSCROP', 'OG4K23_9FPS', 'OG4K30FPS', 'OG48K24FPS', 'UHD24FPS']
        want = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 9, 9, 9, 9, 9, 9]
        c = ['#include <stdio.h>', '#include <stdint.h>', '#include <string.h>', 'typedef uint32_t u32;',
             'static unsigned char M[4096];', '#define B8(a) M[(a)]', '#define OGC_FPL 1', fn,
             'int main(void) {', '  const char *k[] = {' + ', '.join('"%s"' % k for k in keys) + '};',
             '  strcpy((char *)M + 2048, "OG4K");',
             '  for (u32 i = 0; i < %d; i++) {' % len(keys),
             '    memset(M, 0, 32); strncpy((char *)M, k[i], 16);',
             '    printf("%u\\n", key_rate_row(0, 2048)); }', '  return 0; }']
        with tempfile.TemporaryDirectory() as t:
            (pathlib.Path(t) / 'k.c').write_text('\n'.join(c))
            subprocess.run(['cc', '-O1', '-o', t + '/k', t + '/k.c'], check=True)
            got = [int(x) for x in subprocess.run([t + '/k'], capture_output=True, text=True).stdout.split()]
        self.assertEqual(got, want)

    def test_3_2_live_view_uses_photo_modes_profiles(self):
        """every uncropped video live-view profile (width 1928, no raster) has a photo-mode twin with the
        same read and rate that keeps every row; while OG4K / OG48K is live each gets its twin's differing
        fields (camera, 2026-11-05: p51 live view, p1551 / p1516 half-press)"""
        import rcd
        import fpl_formats as F
        sys.path.insert(0, str(ROOT / 'projects' / 'fpl-port' / 'tools'))
        import canvas_compare as C
        cols = C.columns(self.img, C.FPL['builder'])
        mp = lambda p: word(self.img, C.FPL['mapping'] + 4 * p)
        cv = lambda p: {o: word(self.img, c + 4 * mp(p)) for o, c in cols.items()}
        read = lambda c: (c[0xF4], c[0xF8], c[0xFC], c[0x100], c[0x104], c[0x30])
        want = {}
        for v, t in F.LV_TWINS:
            cvv, cvt = cv(v), cv(t)
            self.assertEqual(read(cvv), read(cvt), (v, t))
            self.assertGreater(cvt[0x28], cvv[0x28], (v, t))              # the twin shows more rows
            want.setdefault(tuple((o, cvt[o]) for o in sorted(cols) if cvv[o] != cvt[o]), []).append(v)
        # no uncropped video live-view profile left out (photo ids are the twins)
        twins = {t for _, t in F.LV_TWINS}
        lv = [p for p in range(1, 2000) if mp(p) != 0xFFFFFFFF and cv(p)[0x0C] == 1928 and cv(p)[0x00] == 0
              and p not in twins and any(read(cv(p)) == read(cv(t)) for t in twins)]
        self.assertEqual(sorted(lv), sorted(v for v, _ in F.LV_TWINS))
        expect = sorted((sorted(ps), list(pairs), 0) for pairs, ps in want.items())
        for name in ('OG4K', 'OG48K'):
            d = rcd.decode((self.out / 'RESCUS' / f'{name}.RCD').read_bytes(), self.img, None)
            self.assertEqual(sorted((sorted(p), list(q), c) for p, q, c in d['standby']), expect, name)

    def test_lvpub_records_and_passes_through(self):
        """the cine LV_Resolution publisher's hook: r0 / r1 into S.LVPUB_OBJ / VAL, then the stock code
        from its second word with the same arguments (unicorn; the replay goes back to 0xC059878C)"""
        try:
            from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
            from unicorn import arm_const as A
        except ImportError:
            self.skipTest('needs unicorn')
        facts = self.f
        L0, SC, S = int(facts['layout0'], 16), int(facts['s_coord'], 16), facts['S']
        h = next(h for h in facts['hooks'] if h['site'] == '0xC0598788')
        mu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        mu.mem_map(0xC0000000, (len(self.img) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(0xC0000000, self.img)
        mu.mem_write(L0, self.core[facts['img_off']: facts['img_off'] + (SC - L0) + 0x1000])
        mu.mem_map(0x10000000, 0x100000)
        put = lambda a, *v: mu.mem_write(a, struct.pack(f'<{len(v)}I', *v))
        put(int(h['next'], 16), int(h['replay'], 16))
        seen = []
        mu.hook_add(UC_HOOK_CODE, lambda uc, a, n, d: (seen.append((uc.reg_read(A.UC_ARM_REG_R0),
                    uc.reg_read(A.UC_ARM_REG_R1))), uc.emu_stop()), begin=0xC059878C, end=0xC059878C)
        mu.reg_write(A.UC_ARM_REG_SP, 0x10080000)
        mu.reg_write(A.UC_ARM_REG_R0, 0xC37B7364)
        mu.reg_write(A.UC_ARM_REG_R1, 3)
        mu.reg_write(A.UC_ARM_REG_LR, 0x10004000)
        mu.emu_start(int(h['to'], 16), 0x10004000, count=100)
        self.assertEqual(seen, [(0xC37B7364, 3)])
        self.assertEqual(struct.unpack('<2I', mu.mem_read(SC + S['LVPUB_OBJ'], 8)), (0xC37B7364, 3))
        self.assertEqual(mu.reg_read(A.UC_ARM_REG_SP), 0x10080000 - 16)       # the replayed push only

    # ---- the live-view resolution label (fpl_formats LV_CLIPS / LV_GROUPS) ----
    @staticmethod
    def lv_keys_py(old, times, ids, prop):
        """the reference: every property gets a copy of its LAST key at each time, `prop` the ids"""
        out = bytearray(old[:28])
        count, src = struct.unpack('>I', old[12:16])[0], 28
        for p in range(count):
            keys = struct.unpack('>I', old[src:src + 4])[0]
            out += struct.pack('>I', keys + len(times)) + old[src + 4:src + 20 + 10 * keys]
            last = old[src + 20 + 10 * (keys - 1):src + 30 + 10 * (keys - 1)]
            for t, i in zip(times, ids):
                k = bytearray(last)
                k[2:6] = struct.pack('>I', t)
                if p == prop:
                    k[6:10] = struct.pack('>I', i)
                out += k
            src += 20 + 10 * keys
        assert src == len(old)
        out[4:8] = struct.pack('>I', len(out))
        return bytes(out)

    def test_lv_label_keys_c_matches_the_reference(self):
        """ogc.c lv_keys, compiled on the host, on the real live-view records: rows k = 2..7 (all six
        states), an image clip and a FrameRatePos clip; and the stock record is what the table expects"""
        import shutil
        import fpl_formats as F
        if not shutil.which('cc'):
            self.skipTest('needs a host C compiler')
        src = (HERE / 'ogc.c').read_text()
        fns = []
        for name in ('static u32 be32(', 'static void put_be32(', 'static void copy8('):   # one-liners
            a = src.index(name)
            fns.append(src[a:src.index('\n', a) + 1])
        a = src.index('static u32 lv_keys(')
        fns.append(src[a:src.index('\n}\n', a) + 3])
        times = [100 * k // 3 for k in range(2, 8)]
        ids = [0x40000010 + k for k in range(6)]
        cases = [(F.LV_CLIPS[0][0], 0), (F.LV_CLIPS[1][0], 0), (F.LV_CLIPS[4][0], 0xFFFFFFFF)]
        c = ['#include <stdio.h>', '#include <stdint.h>', 'typedef uint32_t u32; typedef uint8_t u8;',
             'static unsigned char M[8192];', '#define B8(a) M[(a)]', '#define u8at(a) M[(a)]'] + fns + [
             'int main(void) {', '  u32 t[6] = {%s}, i[6] = {%s};' % (', '.join(map(str, times)), ', '.join(map(str, ids))),
             '  int c; u32 n = 0; while ((c = getchar()) != EOF) M[n++] = (u8)c;',
             '  u32 prop = (u32)M[0] | (u32)M[1] << 8 | (u32)M[2] << 16 | (u32)M[3] << 24;',
             '  u32 len = lv_keys(4, n - 4, 4096, 2048, 6, t, i, prop);',
             '  fwrite(M + 4096, 1, len, stdout); return 0; }']
        with tempfile.TemporaryDirectory() as td:
            (pathlib.Path(td) / 'k.c').write_text('\n'.join(c))
            subprocess.run(['cc', '-O1', '-o', td + '/k', td + '/k.c'], check=True)
            for a, prop in cases:
                n = struct.unpack('>I', self.img[a - 0xC0000000 + 4:a - 0xC0000000 + 8])[0]
                old = self.img[a - 0xC0000000:a - 0xC0000000 + n]
                got = subprocess.run([td + '/k'], input=struct.pack('<I', prop) + old, capture_output=True).stdout
                want = self.lv_keys_py(old, times, ids, prop)
                self.assertEqual(got, want, hex(a))
                self.assertLessEqual(len(got), 1024, 'QS_CAP')
                # the copies are of the wide key: a width property's new keys say 138 / 113
                if prop == 0:
                    w = struct.unpack('>f', want[28 + 20 + 30 + 60 + 20 + 20 + 6:28 + 20 + 30 + 60 + 20 + 20 + 10])[0]
                    self.assertIn(w, (138.0, 113.0))

    def test_lv_label_records_are_in_the_core_table(self):
        """the 12 live-view rows (6 clips QS_LVCLONE, 6 groups QS_END), with the stock records' length
        and hash, in the table the core binary-searches (sorted by address)"""
        import fpl_formats as F
        import build_v3_rescustom as B3
        sys.path.insert(0, str(ROOT / 'fpSup' / 'uishare'))
        from ui import fpui
        tab = self.core[self.f['qstab_off']:]
        ver, n, rows_off = struct.unpack_from('<3I', tab)
        rows = [struct.unpack_from('<IIHBBHH', tab, rows_off + 16 * i) for i in range(n)]
        self.assertEqual([r[0] for r in rows], sorted(r[0] for r in rows))
        by = {r[0]: r for r in rows}
        for a, kind in F.LV_CLIPS:
            r = by[a]
            ln = struct.unpack('>I', self.img[a - 0xC0000000 + 4:a - 0xC0000000 + 8])[0]
            self.assertEqual(r[1:], (fpui.fnv(self.img[a - 0xC0000000:a - 0xC0000000 + ln]), ln, B3.QS_LVCLONE,
                                     0 if kind is None else 1, 0xFF if kind is None else kind, 0), hex(a))
        for a in F.LV_GROUPS:
            self.assertEqual(by[a][3], 1, hex(a))                                   # QS_END
            self.assertEqual(struct.unpack('>I', self.img[a - 0xC0000000 + 36:a - 0xC0000000 + 40])[0], 66)

    def test_lv_label_images_ride_in_each_format(self):
        """each format's pack: <label>_LVL 138x43 and <label>_LVM 113x35 (the stock DCI 4K label's
        size, whose key the rows copy), named in its UI block for ROW.LVID"""
        import rcd
        sys.path.insert(0, str(HERE.parent))
        import xci
        for name in ('OG4K', 'OG48K'):
            data = (self.out / 'RESCUS' / f'{name}.RCD').read_bytes()
            d = rcd.decode(data, self.img, None)
            off, ln = d['pack']
            pack = data[off:off + ln]
            dims, at = [], pack.find(xci.MAGIC)
            while at >= 0:
                dims.append(xci.decode(pack, at)[:2])
                at = pack.find(xci.MAGIC, at + 4)
            self.assertIn((138, 43), dims, name)
            self.assertIn((113, 35), dims, name)
            for suffix in ('LVL', 'LVM'):
                self.assertIn(f'{name}_{suffix}'.encode() + b'\0', pack, name)

    def test_w48k_is_mode_188s_band_at_the_stock_timings(self):
        """W48K: the 4784x1700 band (mode 188) recorded 1:1 at 4784x1696 / 4768x1680; every stock
        rate has the timing words of SIGMA's own mode for it (188..195), 17.98 the solver's"""
        import rcd
        d = rcd.decode((self.out / 'RESCUS' / 'W48K.RCD').read_bytes(), self.img, None)
        self.assertEqual((d['profile'], d['act'], d['aspect'], d['flags'], d['bit_depths']),
                         (2061, (4768, 1680), 3, 0, (8, 10, 12)))
        rec = dict(d['canvas_rec'])
        self.assertEqual((rec[0x00], rec[0x04], rec[0xF4], rec[0xF8], rec[0xFC], rec[0x60]),
                         (4784, 1696, 4784, 1700, 0x40000000, 1023))
        tt = {}
        for i in range(85):
            w = struct.unpack_from('<3I', self.img, 0xC0B90FF8 + 0x20 * i - 0xC0000000)
            tt[w[0]] = w[1:]
        stock = {2398: 195, 2400: 194, 2500: 193, 2997: 192, 4800: 190, 5000: 189, 5994: 188}
        self.assertEqual({e['rank'] for e in d['entries']}, set(stock) | {1798})
        for e in d['entries']:
            self.assertEqual(e['donor'], 188)
            if e['rank'] in stock:
                self.assertEqual((e['w0'], e['w1']), tt[stock[e['rank']]], e['key'])

    def test_u48k_is_mode_155s_read_at_the_stock_timings(self):
        """U48K: the 4784x2700 read (mode 155) recorded 1:1 at 4784x2688 / 4768x2672; each stock rate
        has the timing words of SIGMA's own mode for it (155..158); nothing faster than 29.97"""
        import rcd
        d = rcd.decode((self.out / 'RESCUS' / 'U48K.RCD').read_bytes(), self.img, None)
        self.assertEqual((d['profile'], d['act'], d['aspect'], d['flags']), (2061, (4768, 2672), 3, 0))
        rec = dict(d['canvas_rec'])
        self.assertEqual((rec[0x00], rec[0x04], rec[0xF4], rec[0xF8]), (4784, 2688, 4784, 2700))
        tt = {}
        for i in range(85):
            w = struct.unpack_from('<3I', self.img, 0xC0B90FF8 + 0x20 * i - 0xC0000000)
            tt[w[0]] = w[1:]
        stock = {2398: 158, 2400: 157, 2500: 156, 2997: 155}
        self.assertEqual({e['rank'] for e in d['entries']}, set(stock) | {1798})
        for e in d['entries']:
            self.assertEqual(e['donor'], 155)
            if e['rank'] in stock:
                self.assertEqual((e['w0'], e['w1']), tt[stock[e['rank']]], e['key'])

    def test_every_recording_preview_is_within_3x_of_the_frame(self):
        """the recording preview (+0x0C / +0x10, else the base p2061's 1288 x 724) is at most
        PREVIEW_MAX_DOWN smaller than the recorded raster (+0x00 / +0x04) on each axis (U48K flashed at
        3.71x down, camera 2026-11-05), and the active preview is the buffer less 8 x 4 like p2061's"""
        import rcd
        import fpl_formats as F
        for p in sorted((self.out / 'RESCUS').iterdir()):
            d = rcd.decode(p.read_bytes(), self.img, None)
            rec = dict(d['canvas_rec'])
            pw, ph = rec.get(0x0C, 1288), rec.get(0x10, 724)            # else the base p2061's
            rw, rh = rec.get(0x00, 3856), rec.get(0x04, 2170)
            self.assertLessEqual(rw / pw, F.PREVIEW_MAX_DOWN, p.name)
            self.assertLessEqual(rh / ph, F.PREVIEW_MAX_DOWN, p.name)
            if p.name in ('U48K.RCD', 'W48K.RCD'):
                self.assertEqual((rec[0x20], rec[0x28]), (pw - 8, ph - 4), p.name)
                self.assertAlmostEqual(pw / ph, rec[0x00] / rec[0x04], delta=0.02, msg=p.name)

    def test_uhdc_is_stock_uhd_cut_from_mode_196(self):
        """UHDC: stock UHD's frame 1:1 from the middle of mode 196's 6288x2174 read; each stock rate
        at SIGMA's own words (196..203); no playback pairs"""
        import rcd
        d = rcd.decode((self.out / 'RESCUS' / 'UHDC.RCD').read_bytes(), self.img, None)
        self.assertEqual((d['profile'], d['act'], d['aspect'], d['flags'], d['canvas_pb']),
                         (2061, (3840, 2160), 3, 0, []))
        rec = dict(d['canvas_rec'])
        self.assertEqual((rec[0xF4], rec[0xF8], rec[0x60], rec[0xD0]), (6288, 2174, 1023, 1023))
        # the recording preview: U48K's 1616x908 (p2061's flashed, the crop step's froze; camera r17 / r18)
        self.assertEqual((rec[0x0C], rec[0x10], rec[0x20], rec[0x28]), (1616, 908, 1608, 904))
        # the crop window, tuned live (r20 test 2): +0xD8 the preview width, +0xE0 the read height
        self.assertEqual((rec[0xA4], rec[0xD8], rec[0xE0]), (42, rec[0x0C], rec[0xF8]))
        self.assertNotIn(0x00, rec)                                  # p2061's own 3856 x 2170
        tt = {}
        for i in range(85):
            w = struct.unpack_from('<3I', self.img, 0xC0B90FF8 + 0x20 * i - 0xC0000000)
            tt[w[0]] = w[1:]
        stock = {2398: 203, 2400: 202, 2500: 201, 2997: 200, 4800: 198, 5000: 197, 5994: 196}
        self.assertEqual({e['rank'] for e in d['entries']}, set(stock) | {1798})
        for e in d['entries']:
            self.assertEqual(e['donor'], 196)
            if e['rank'] in stock:
                self.assertEqual((e['w0'], e['w1']), tt[stock[e['rank']]], e['key'])

    def test_name_skips_rows_without_playback_pairs(self):
        """ogc_name (compiled from ogc.c on the host, OGC_FPL): a UHD-sized request with OG4K live gets
        OG4K's label, not UHDC's (whose active size is stock UHD's but which has no playback pairs);
        an OG4K-sized request still finds OG4K (playback)"""
        import shutil
        import ogc_layout as L
        if not shutil.which('cc'):
            self.skipTest('needs a host C compiler')
        src = (HERE / 'ogc.c').read_text()
        a = src.index('u32 ogc_name(u8 *S, u32 out, u32 sizes, u32 caller)')
        fn = src[a:src.index('\n}\n', a) + 3]
        S, ROWS, RS = 0x100, 0x400, L.ROW['SIZE']
        c = ['#include <stdio.h>', '#include <stdint.h>', '#include <string.h>',
             'typedef uint32_t u32; typedef uint8_t u8;', 'static u32 M[0x4000];',
             '#define W(a) M[(a) >> 2]', '#define SW(S, o) W((u32)(uintptr_t)(S) + (o))',
             '#define OGC_FPL 1', '#define KEYBLD 0xDEADu',
             f'#define S_NROWS {L.S["NROWS"]}u', f'#define S_PBROW {L.S["PBROW"]}u',
             f'#define S_FLAG {L.S["FLAG"]}u', f'#define S_CUR {L.S["CUR"]}u',
             f'#define ROW_AW {L.ROW["AW"]}u', f'#define ROW_AH {L.ROW["AH"]}u',
             f'#define ROW_PB {L.ROW["PB"]}u', f'#define ROW_LABEL {L.ROW["LABEL"]}u',
             f'static u32 rowp(u8 *S, u32 r) {{ return (u32)(uintptr_t)S + {ROWS} + {RS} * r; }}',
             'typedef u32 (*fw3)(u32, u32, u32);', 'static u32 emitted;',
             'static u32 emit(u32 out, u32 lab, u32 n) { emitted = lab; return 0; }',
             '#define EMIT ((uintptr_t)&emit)', fn,
             'int main(void) {', f'  u8 *S = (u8 *)(uintptr_t){S}; u32 r0 = {S + ROWS}, r1 = r0 + {RS};',
             '  SW(S, S_NROWS) = 2; SW(S, S_FLAG) = 1; SW(S, S_CUR) = 2;',
             '  W(r0 + ROW_AW) = 3840; W(r0 + ROW_AH) = 2160; W(r0 + ROW_PB) = 0x800; W(0x100 + 0x800) = 0xFFFFFFFFu;',
             '  W(r1 + ROW_AW) = 3840; W(r1 + ROW_AH) = 2552; W(r1 + ROW_PB) = 0x810; W(0x100 + 0x810) = 0x0C;',
             '  u32 sz = 0x3000; W(sz + 8) = 3840; W(sz + 12) = 2160;',
             '  ogc_name(S, 0, sz, 0); printf("%u %u\\n", emitted == r1 + ROW_LABEL, SW(S, S_PBROW));',
             '  W(sz + 12) = 2552; emitted = 0;',
             '  ogc_name(S, 0, sz, 0); printf("%u %u\\n", emitted == r1 + ROW_LABEL, SW(S, S_PBROW));',
             '  return 0; }']
        with tempfile.TemporaryDirectory() as td:
            (pathlib.Path(td) / 'n.c').write_text('\n'.join(c))
            subprocess.run(['cc', '-O1', '-w', '-o', td + '/n', td + '/n.c'], check=True)
            out = subprocess.run([td + '/n'], capture_output=True, text=True).stdout.split()
        self.assertEqual(out, ['1', '0', '1', '2'])

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

    def boot(self, with_rcd, rcd_name='OG4K.RCD'):
        sys.path.insert(0, str(ROOT / 'fpSup' / 'loader-v4'))
        if os.environ.get('FPSUP_CAMERA') != 'fpl':
            self.skipTest('the emulated boot runs the camera this process was started for (FPSUP_CAMERA=fpl)')
        import test_v4 as T4
        if T4.Uc is None:
            self.skipTest('needs unicorn')
        rcdb = (self.out / 'RESCUS' / rcd_name).read_bytes()
        files, dirs = T4.card((NAME, self.core), extra=[('RESCUS', 0x10, 0)])
        files['\\fpSup\\LOAD.LOG'] = b''
        dirs['\\fpSup\\RESCUS'] = []
        if with_rcd:
            files['\\fpSup\\RESCUS\\' + rcd_name] = rcdb
            dirs['\\fpSup\\RESCUS'] = [(rcd_name, 0x20, len(rcdb))]
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

    def test_uhdc_declares_its_crop_factor(self):
        """UHDC carries SEC_CROP 248 (9568 / 3856: stock's largest UHD crop step), the others none; the
        core boots with it and accepts the file (the section is required: a core without it refuses)"""
        import rcd
        import ogc_layout as L
        for p in sorted((self.out / 'RESCUS').iterdir()):
            d = rcd.decode(p.read_bytes(), self.img, None)
            self.assertEqual(d['crop100'], 248 if p.name == 'UHDC.RCD' else 0, p.name)
        src = (HERE / 'ogc.c').read_text()
        self.assertIn('if (c) W(req + 0x48) = c;', src)
        T4, log = self.boot(True, 'UHDC.RCD')
        self.assertIn('OCD01010100', [t for c, _, _, t in log], log)

if __name__ == '__main__':
    unittest.main()
