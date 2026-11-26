"""s1 夜·孤岛.  Before midnight: a violet night sea under a veiled moon, the lighthouse on its rock, the cottage window
warm, the beam turning slowly through thin mist (8 s a turn).  Sea thrift on the near rock stirs; moonlight breaks on
the long swell.  The camera creeps in."""
import numpy as np, cv2, math, os
from lp import W, H, comp, clouds, cache_path
from lp.paint import f32, rgb, mix, ramp, smooth, fbm, grid, repaint, mottle, Canvas, arcs, jit_color, lum
from lp.ink import Cel, spl
from lp.cam import Camera3D
import lighthouse as lh
import island

VER = 'v7'
HZ = 690.
EYE = 1.7
FOCAL = 2400.
AT = (16.0, 118.0, 5.6)                   # tower foot (world m); the plateau top
MOON = (500., 236.)
MR = 30.
BEAM_AZ0 = math.radians(75.)               # beam 1 looks at us ~4.2 s into the shot


def CAM(z=1.0, CX=1330., CY=430.):
    """the camera after a 2-D push of `z` around (CX, CY): same as a longer lens with a shifted centre"""
    return Camera3D((0, 0, EYE), (0, 100, EYE), focal=FOCAL * z, cx=CX + (W / 2 - CX) * z, cy=CY + (HZ - CY) * z)


def moon_dir(cam):
    d = np.array([(MOON[0] - cam.cx) / cam.f, (MOON[1] - cam.cy) / cam.f, 1.]) @ cam.R
    return d / np.linalg.norm(d)


# ================================================================= plates
def sky_plate():
    x, y = grid()
    t = np.clip(y / HZ, 0, 1)
    base = ramp(t, [(0, '#121a3a'), (.30, '#1a2450'), (.55, '#1f2b5a'), (.80, '#2e3c74'), (.93, '#3a4a85'), (.985, '#55609a'), (1, '#6a6fa8')])
    # cold cyan breath on the horizon, moon wash
    base = base + (np.exp(-np.maximum(0, HZ - y) / 26.) * smooth(HZ + 2, HZ - 4, y))[..., None] * np.array([-.02, .03, .05], f32)
    d = np.sqrt((x - MOON[0]) ** 2 + (y - MOON[1]) ** 2)
    base = base + (np.exp(-(d / 520.) ** 1.6) * .16)[..., None] * (rgb('#6a74b0') - base * .5)
    base = base + (np.exp(-(d / 150.) ** 2) * .10)[..., None] * rgb('#8a94c8')
    ang = fbm(H, W, (260, 90), (1, .4), 3) * .07 - .02
    out = repaint(base, (56, 24), seed=4, angle=ang, thr=(0, .004), density=.9, aspect=6.5, jit=(.001, .004, .008), op=.5, dry=.18, curve=.12, bristle=.02)
    out = mottle(out, .008, 5, .002)
    return out


def stars(img):
    r = np.random.default_rng(12)
    n = 150
    x = r.uniform(0, W, n); y = r.uniform(0, HZ - 120, n) ** 1.0
    s = r.uniform(.6, 1.5, n) ** 1.6
    d = np.sqrt((x - MOON[0]) ** 2 + (y - MOON[1]) ** 2)
    keep = (d > 210) & (r.random(n) < np.clip(1.2 - y / HZ, 0, 1)) & ((x < 1150) | (x > 1520) | (y < 120))
    c = Cel(W, int(HZ), 0, 0, ss=2)
    for xx, yy, ss in zip(x[keep], y[keep], s[keep]):
        col = mix(rgb('#dfe6fb'), rgb('#f6e4d6'), r.random() * .5)
        m = 6; a = np.linspace(0, 2 * np.pi, m, endpoint=False) + r.uniform(0, 1)
        q = np.c_[xx + np.cos(a) * ss * r.uniform(.7, 1.1, m), yy + np.sin(a) * ss * r.uniform(.7, 1.1, m)]
        c.fill(spl(q, closed=True, n=4), col, min(1., .35 + .3 * ss))
    L = c.layer()
    return comp.over(img, L)


def moon_and_clouds(img):
    """the moon and its veil: a high bank lit from behind, long thin strata across the disc, low banks on the horizon"""
    # moon disc with a faint mare pattern
    c = Cel(W, H, 0, 0, ss=2)
    t = np.linspace(0, 2 * np.pi, 64, endpoint=False)
    disc = np.c_[MOON[0] + MR * np.cos(t), MOON[1] + MR * np.sin(t)]
    c.fill(disc, '#f2f2fc')
    r = np.random.default_rng(3)
    for (dx, dy, rr) in ((-8, -6, 11), (9, 4, 9), (-2, 12, 7), (12, -11, 5)):
        q = np.c_[MOON[0] + dx + rr * np.cos(t) * r.uniform(.8, 1.1, 64), MOON[1] + dy + rr * np.sin(t) * .8]
        c.shade(spl(q[::4], closed=True, n=4), '#c9cde8', within=disc, alpha=.6)
    img = comp.over(img, c.layer())
    img = comp.glow(img, MOON[0], MOON[1], 300, '#8f9acb', .28, 2.2)
    img = comp.glow(img, MOON[0], MOON[1], 90, '#cfd8ff', .35, 1.6)
    L = np.array([-.2, -.35, -.9]); L /= np.linalg.norm(L)                    # moon behind the veil: backlit
    S = clouds.Sky(H, W, img, light=(-.55, -.62, .3), seed=11)
    T_far = clouds.tones('#8f9acb', '#6f7ab4', '#4f5a96', '#36407a')
    T_mid = clouds.tones('#c7cfea', '#8f9acb', '#5a66a6', '#2c3670')
    # horizon range: low, far, cool
    for (x, b, w, h, sd) in ((140, 694, 300, 26, 1), (520, 692, 220, 16, 2), (880, 694, 360, 34, 3), (1500, 693, 260, 20, 4), (1880, 694, 380, 40, 5)):
        S.bank(x, b, w, h, T_far, '#3e4a84', seed=sd, tiers=2, levels=2, n=6, pool=.4, lit=.18)
    # a long bank on the right, under the tower's lamp height, keeping the tower's top clear
    T_dim = clouds.tones('#5a66a6', '#46518e', '#343f78', '#283266')
    S.bank(1760, 560, 700, 90, T_dim, '#34407a', seed=21, profile=clouds.peak(.35, .2, .3, .75, .55, .14), n=7, levels=2, pool=.5, lit=.10, half=.26, soft=1.2, detail=.7)
    S.bank(2010, 620, 480, 60, T_dim * .92, '#323e76', seed=22, n=6, levels=2, pool=.5, lit=.08, soft=1.2, detail=.7)
    # the veil: torn bank just under the moon, lit on top by it
    T_veil = clouds.tones('#7f8ac0', '#626eaa', '#46528e', '#303a72')
    S.bank(760, 400, 620, 70, T_veil, '#3e4a88', seed=31, profile=clouds.peak(.3, .25, .4, .65, .5, .2), n=7, levels=2, pool=.3, lit=.10, half=.26, soft=1.6, detail=.55)
    S.bank(300, 452, 420, 46, T_veil * .9, '#3a4684', seed=32, n=6, levels=2, pool=.3, lit=.12, soft=1.2, detail=.7)
    S.strata(MOON[1] - 60, MOON[1] + 40, 26, ['#9aa4d4', '#7f8ac0', '#b9c2e6'], seed=33, x=(MOON[0] - 420, MOON[0] + 380), w=(.06, .22), th=(1.4, 4.2), op=(.2, .55), power=1.0)
    S.strata(150, 200, 12, ['#4a5592', '#5a66a6'], seed=34, x=(900, 1900), w=(.08, .3), th=(1, 3), op=(.15, .4))
    out = S.paint(5)
    return out


def sea_plate(cam):
    """base sea colour, painted swell marks, and the per-pixel world depth (for the moving swell)"""
    u, v, t = cam.uv((0, 0, 0), (1, 0, 0), (0, 1, 0))
    Y = np.where(t > 0, v, 1e4).astype(f32); X = np.where(t > 0, u, 0).astype(f32)
    x, y = grid()
    q = np.clip((y - HZ) / (H - HZ), 0, 1)
    base = ramp(q, [(0, '#3a4a85'), (.02, '#2c3b70'), (.1, '#22305e'), (.45, '#18244a'), (1, '#0f1838')])
    md = moon_dir(cam)
    # moon sheen: reflected view ray near the moon
    d = cam.rays(); d /= np.linalg.norm(d, axis=-1, keepdims=True)
    rf = d * np.array([1, 1, -1], f32)
    sheen = _refl(rf, md, .06, .26) * (y > HZ)
    base = base + sheen[..., None] * (rgb('#5a66a6') - base) * .55
    # long swell strokes, laid in perspective
    r = np.random.default_rng(7)
    cv = Canvas(img=base)
    n = 5200
    Xw = r.uniform(-140, 160, n); Yw = 6 + 900 * r.uniform(0, 1, n) ** 2.4
    Lw = r.uniform(3, 9, n) * (1 + Yw / 300)
    P = np.zeros((n, 5, 2), f32); WD = np.zeros(n, f32); C = np.zeros((n, 3), f32); OP = np.zeros(n, f32)
    keep = np.zeros(n, bool)
    for i in range(n):
        xs = Xw[i] + np.linspace(-.5, .5, 5) * Lw[i]
        ys = Yw[i] + np.sin(np.linspace(0, 3, 5) + i) * .3 * (1 + Yw[i] / 200)
        pts, z = cam.project(np.stack([xs, ys, np.zeros(5)], -1))
        if (z < 1).any(): continue
        P[i] = pts
        WD[i] = max(.5, cam.f / Yw[i] * .16 * r.uniform(.6, 1.3))
        cy = int(np.clip(pts[2, 1], 0, H - 1)); cx = int(np.clip(pts[2, 0], 0, W - 1))
        crest = r.random() < .45
        bc = base[cy, cx]
        C[i] = bc * (1.16 + .4 * sheen[cy, cx]) if crest else bc * .86
        OP[i] = r.uniform(.35, .75)
        keep[i] = (0 <= pts[2, 0] < W) and HZ < pts[2, 1] < H + 20
    cv.strokes(P[keep], WD[keep], np.clip(C[keep], 0, 1), op=OP[keep], dry=.2, seed=9, shape='round', bristle=.06)
    out = mottle(cv.img, .01, 8, .003)
    m = (y > HZ - .5)[..., None]
    return out, Y, sheen.astype(f32), X


def glitter_set(cam):
    """moon glitter: dashes fixed in the world, each with its own twinkle phase"""
    r = np.random.default_rng(21)
    md = moon_dir(cam)
    n = 2600
    pts = []
    # sample where the reflected ray hits near the moon: march along the column
    Yw = 8 + 1400 * r.uniform(0, 1, n * 6) ** 2.6
    a0 = math.atan2(md[0], md[1])
    Xw = Yw * math.tan(a0) + r.normal(0, 1, n * 6) * (1 + Yw * .07)
    P3 = np.stack([Xw, Yw, np.zeros_like(Xw)], -1)
    d = P3 - cam.eye; d /= np.linalg.norm(d, axis=-1, keepdims=True)
    rf = d * np.array([1, 1, -1])
    pr = _refl(rf, md, .05, .24)
    keep = r.random(len(pr)) < pr
    P3 = P3[keep][:n]
    xy, z = cam.project(P3)
    ok = (xy[:, 1] > HZ + 1) & (xy[:, 0] > -20) & (xy[:, 0] < W + 20) & (z > 1)
    P3, xy = P3[ok], xy[ok]
    m = len(xy)
    s = cam.f / P3[:, 1]
    L = np.clip(s * r.uniform(.4, 1.6, m) * .9, 2, 60)
    return dict(xy=xy.astype(f32), Y=P3[:, 1].astype(f32), L=L.astype(f32), w=np.clip(s * r.uniform(.05, .12, m), .45, 4).astype(f32),
                ph=r.uniform(0, 1, m).astype(f32), rate=r.uniform(.35, .9, m).astype(f32), b=r.uniform(.5, 1.0, m).astype(f32))


def _refl(rf, md, sh, sv):
    """how likely a wave facet sends the moon to us: tight across, loose along the column"""
    az = np.arctan2(rf[..., 0], rf[..., 1]) - math.atan2(md[0], md[1])
    el = np.arctan2(rf[..., 2], np.hypot(rf[..., 0], rf[..., 1])) - math.atan2(md[2], math.hypot(md[0], md[1]))
    return np.exp(-(az / sh) ** 2 - (el / sv) ** 2).astype(f32)


def lamp_reflection(cam):
    """the lantern's broken warm column on the water, from the island's waterline toward us"""
    r = np.random.default_rng(23)
    lx, ly = lh.lamp_px(cam, AT)
    n = 420
    y = HZ + 22 + (H - HZ - 22) * r.uniform(0, 1, n) ** 1.8
    Yw = EYE * cam.f / np.maximum(y - cam.cy, 1)
    spread = 6 + (y - HZ) * .10
    x = lx + r.normal(0, 1, n) * spread
    L = np.clip(4 + (y - HZ) * .12, 3, 40) * r.uniform(.5, 1.4, n)
    b = r.uniform(.6, 1.6, n) * np.exp(-((y - HZ) / 260.) ** 1.2)
    return dict(xy=np.stack([x, y], -1).astype(f32), Y=Yw.astype(f32), L=L.astype(f32), w=np.clip((y - HZ) * .012, .6, 3).astype(f32),
                ph=r.uniform(0, 1, n).astype(f32), rate=r.uniform(.3, .7, n).astype(f32), b=b.astype(f32))


def _foam(segs, k=240.):
    """lace of foam where the rock meets the water: short broken strokes along each waterline segment"""
    r = np.random.default_rng(17)
    cv = Canvas(H, W, layer=True, color='#ffffff')
    P = []; WD = []; OP = []
    for (Q, z) in segs:
        a, b = Q[0], Q[1]
        L = np.hypot(*(b - a))
        w = max(.7, k / z)
        for k in range(int(L / (w * 3)) + 1):
            u = r.uniform(0, 1); l = r.uniform(2.5, 7) * w
            c = a + (b - a) * u + r.normal(0, w * .4, 2) * [1, .5] + np.array([0, abs(r.normal(0, w * 1.4))])
            d = (b - a) / (L + 1e-6)
            P.append(np.stack([c + d * l * t + [0, r.normal(0, w * .15)] for t in np.linspace(-.5, .5, 4)]))
            WD.append(w * r.uniform(.4, 1.0)); OP.append(r.uniform(.25, .75))
    if P:
        cv.strokes(np.array(P, f32), np.array(WD), np.ones(3, f32), op=np.array(OP), dry=.3, seed=3, shape='round', bristle=.05)
    return cv.a


def fg_rocks(cam):
    r = np.random.default_rng(31)
    rocks = [island.prism(-2.55, 7.6, 1.6, 1.0, -.08, 1.32, r, k=9, tilt=(.06, .05)),
             island.prism(-1.75, 9.6, 1.4, 1.1, -.08, .9, r, k=8, tilt=(.05, .02)),
             island.prism(-3.6, 6.2, 1.5, 1.2, -.08, 1.55, r, k=9, tilt=(.1, 0)),
             island.prism(-.9, 8.2, .9, .7, -.08, .42, r, k=7),
             island.prism(-1.2, 11.6, 1.1, .6, -.08, .25, r, k=7)]
    return rocks


class Shot:
    n = 168
    finish = dict(hal_amt=.22, vig=.12)
    CX, CY = 1330., 430.

    def setup(self):
        cv2.setNumThreads(2)
        self.cam = cam = CAM()
        def cached(name, fn):
            p = cache_path(f's1_{name}_{VER}.npy')
            if os.path.exists(p): return np.load(p).astype(f32)
            a = fn(); np.save(p + '.tmp.npy', a.astype(np.float16)); os.replace(p + '.tmp.npy', p)
            return a.astype(f32)
        self.md = moon_dir(cam)
        self.sky = cached('sky', lambda: stars(moon_and_clouds(sky_plate())))
        sea = cached('sea', lambda: np.dstack(sea_plate(cam)))
        self.sea, self.Y, self.sheen, self.X = sea[..., :3].copy(), sea[..., 3].copy(), sea[..., 4].copy(), sea[..., 5].copy()
        del sea

        def mid():
            Li, info = island.paint_island(cam, 'night', AT, light=self.md + np.array([0, 0, .35]), seed=3)
            Lt, m = lh.paint_tower(cam, 'night', 1.0, AT, light=self.md * np.array([1, 1, .5]) + np.array([0, 0, .3]), masks=True)
            L = Lt + Li * (1 - Lt[..., 3:4])
            fo = _foam(info['foam'])
            return np.dstack([L, m['glass'], fo, Lt[..., 3]])
        M = cached('mid', mid)
        self.mid, self.glass, self.foam, self.towa = M[..., :4].copy(), M[..., 4].copy(), M[..., 5].copy(), M[..., 6].copy()
        del M
        self.fg = cached('fg', lambda: island.paint_rocks(cam, fg_rocks(cam), 'night', light=self.md + np.array([0, 0, .2]), seed=8, sizes=(18, 9, 4.5), tex=.10, dabs=1.2)[0])
        self.gl = glitter_set(cam)
        self.lr = lamp_reflection(cam)
        self.seam = smooth(HZ - .5, HZ + 1.0, np.arange(H, dtype=f32))[:, None] * np.ones((1, W), f32)
        self.fog = self._fog()
        ys = np.nonzero(self.fg[..., 3].max(1) > .5)[0]
        self.fgtop = int(ys.min()) if len(ys) else H
        self.thrift = island.Thrift(self._clumps(), 'night', seed=4)
        self.lamp = lh.lamp_px(cam, AT)
        self.win = lh.house_window_px(cam, AT)

    def _clumps(self):
        """thrift cushions along the near rock's top edge"""
        a = self.fg[..., 3]
        out = []
        r = np.random.default_rng(5)
        for x in np.arange(30, 900, 70) + r.uniform(-20, 20, 13):
            col = a[:, int(np.clip(x, 0, W - 1))]
            ys = np.nonzero(col > .6)[0]
            if not len(ys): continue
            y = ys.min() + r.uniform(4, 14)
            s = np.interp(y, [700, 1150], [70, 220]) * r.uniform(.7, 1.2)
            out.append((float(x), float(y), float(s)))
        return out

    def _fog(self):
        x, y = grid()
        n = fbm(H, W, (220, 70), (1, .45), 41, aspect=3.5)
        band = np.exp(-((y - (HZ - 70)) / 160.) ** 2) + .55 * np.exp(-((y - (HZ - 260)) / 220.) ** 2)
        return np.clip((.30 + .7 * band) * (1 + .55 * n), 0, 1.6).astype(f32)

    # ---------------------------------------------------------------- per frame
    def frame(self, f):
        t = f / 24.
        z = 1 + .045 * comp.ease(f / (self.n - 1.)) ** 1.1
        zm, zf = z, 1 + (z - 1) * 1.5

        def warp(img, zz, interp=cv2.INTER_LINEAR):
            M = np.float32([[1 / zz, 0, self.CX - self.CX / zz], [0, 1 / zz, self.CY - self.CY / zz]])
            return cv2.warpAffine(img, M, (W, H), flags=interp | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT_101)

        # sea: the long swell rolls toward us, glitter rides its faces
        sea = self.sea.copy()
        y0 = int(HZ) - 2
        Y = self.Y[y0:]
        ph = 2 * np.pi * (Y / 46. + t / 9.) + .6 * np.sin(self.X[y0:] / 37.)
        sw = np.sin(ph) + .35 * np.sin(2 * np.pi * (Y / 17. + t / 5.3) + 1.1)
        sea[y0:] *= (1 + .075 * sw * smooth(0, 60, Y) * np.clip(90. / (Y + 1e-3), .25, 1))[..., None]
        sea[y0:] += (self.sheen[y0:] * .10 * np.clip(sw, 0, 1))[..., None] * rgb('#8f9acb')
        sea = self._glitter(sea, f, self.gl, '#cfd8ff')
        sea = self._glitter(sea, f, self.lr, '#ffc46b')
        m = (np.arange(H) >= int(HZ) - 2)
        base = self.sky.copy()
        base[m] = sea[m] * self.seam[m][..., None] + base[m] * (1 - self.seam[m][..., None])
        img = warp(base, zm)
        # island, tower, foam
        mid = warp(self.mid, zm)
        img = comp.over(img, mid)
        fo = warp(self.foam, zm)
        pulse = .5 + .5 * np.sin(t * 2 * np.pi / 6.5)
        img = img + (fo * (.55 + .45 * pulse))[..., None] * (rgb('#b8c4ee') - img) * .8
        # the beam in the mist, behind the tower where the tower stands in front of it
        cam = CAM(zm, self.CX, self.CY)
        az = lh.beam_az(t, BEAM_AZ0)
        towa = warp(self.towa, zm)
        fog = warp(self.fog, zm)
        tdep = np.linalg.norm(np.array(AT[:2]) - cam.eye[:2])
        B = np.zeros((H, W), f32)
        flare = 0.
        for k in range(2):
            a = az + k * math.pi
            I, dpt = lh.beam_field(cam, a, AT, spread=.06, r0=.5, fade=260., cap=2.2, dip=.11)
            hide = towa * (dpt > tdep)
            B += I * (1 - hide)
            v = np.array([math.cos(a), math.sin(a)]); tc = cam.eye[:2] - np.array(AT[:2]); tc /= np.linalg.norm(tc)
            flare = max(flare, float(v @ tc))
        sky_part = smooth(HZ + 30, HZ - 40, np.arange(H, dtype=f32))[:, None]
        B = B * (fog * .55 + .12) * (.55 + .45 * sky_part)
        img = comp.screen(img, (B * .34)[..., None] * rgb('#fff0c8'))
        # lantern: glass brightens as a beam turns toward us; glow in the air
        fl = max(0., flare) ** 10
        gl = warp(self.glass, zm)
        img = img + (gl * (.10 + .4 * fl))[..., None] * rgb('#ffc46b')
        lx, ly = lh.lamp_px(cam, AT)
        img = _glow(img, lx, ly, lh.lamp_radius_px(cam, AT), .55 + .6 * fl, '#ffc46b')
        wx, wy = lh.house_window_px(cam, AT)
        img = _glow(img, wx, wy, 7.0 * zm, .30, '#ffb458', spread=1.6)
        # foreground: the near rock and its thrift
        fg = warp(self.fg, zf)
        img = comp.over(img, fg)
        ty0 = max(0, int(self.CY + (self.fgtop - 260 - self.CY) * zf))
        cv = Canvas(H - ty0, 1100, layer=True)
        self.thrift.draw(cv, f, wind=1.0, ox=self.CX - self.CX / zf, oy=self.CY - self.CY / zf + ty0 / zf, scale=zf, light=-1)
        img[ty0:, :1100] = comp.over(img[ty0:, :1100], cv.layer())
        return img

    def _glitter(self, sea, f, g, col):
        d = (f // 2) * 2
        t = d / 24.
        sw = np.sin(2 * np.pi * (g['Y'] / 46. + t / 9.))
        tw = np.clip(np.sin(2 * np.pi * (g['ph'] + t * g['rate'])), 0, 1) ** 3
        b = g['b'] * tw * (.45 + .55 * np.clip(sw + .3, 0, 1))
        on = b > .06
        if not on.any(): return sea
        xy, L, w = g['xy'][on], g['L'][on], g['w'][on]
        x0, y0 = int(max(0, xy[:, 0].min() - 70)), int(max(0, xy[:, 1].min() - 8))
        x1, y1 = int(min(W, xy[:, 0].max() + 70)), int(min(H, xy[:, 1].max() + 8))
        cv = Canvas(y1 - y0, x1 - x0, layer=True, color=col)
        P = arcs(xy[:, 0] - x0, xy[:, 1] - y0, np.zeros(len(L)), L, 0., K=3)
        cv.strokes(P, w, rgb(col), op=np.clip(b[on], 0, 1), seed=d, shape='round', bristle=.02)
        l = cv.layer()
        sea[y0:y1, x0:x1] = comp.over(sea[y0:y1, x0:x1], l * np.float32(.92))
        return sea

    def actors(self, f):
        return []


def _glow(img, x, y, r, amt, col, spread=1.0):
    R = int(r * 26 * spread) + 4
    x0, x1, y0, y1 = max(0, int(x - R)), min(W, int(x + R)), max(0, int(y - R)), min(H, int(y + R))
    if x1 <= x0 or y1 <= y0: return img
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(f32)
    q = np.sqrt((xx - x) ** 2 + (yy - y) ** 2) / r
    g = (.5 * np.exp(-(q / 1.2) ** 2) + .25 * np.exp(-(q / 3.4 / spread) ** 2) + .1 * np.exp(-(q / 8. / spread) ** 2)) * amt
    img[y0:y1, x0:x1] = comp.screen(img[y0:y1, x0:x1], g[..., None] * rgb(col))
    return img
