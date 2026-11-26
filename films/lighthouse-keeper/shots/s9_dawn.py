"""s9 黎明.  A still dawn after the storm.  From just off the gallery: the lantern (still lit) and the green dome on the
left, the otter lying along the iron railing in front of it, the calm sea below breaking into gold under a sun that has
just cleared the horizon.  The fishing boat passes under the tower and sounds its horn twice (3.0 s, 3.6 s), trailing
a fine wake; a slow wave washes the reef (6.0 s); the lamp, its night's work done, goes out (9.0 s).  The air moves:
thrift in the deck's cracks, the sea's glitter.  The camera eases in a little.  The driver fades out the last 2 s."""
import numpy as np, cv2, math, os
from lp import W, H, comp, clouds, cache_path
from lp.paint import f32, rgb, mix, ramp, smooth, fbm, grid, repaint, mottle, Canvas, arcs, jit_color, lum
from lp.ink import Cel, spl
from lp.cam import Camera3D
import lighthouse as lh
import island
import otteract
try:
    import boat
except Exception:                       # the sea lane's boat; a stand-in is drawn if it is missing
    boat = None

VER = 'v3'
AT = (0., 0., 5.6)
ZD = AT[2] + lh.Z_DECK


def _cam():
    r, phi, h = 5.9, math.radians(-72), 1.9
    eye = np.array([r * math.cos(phi), r * math.sin(phi), ZD + h])
    to = -eye[:2] / np.linalg.norm(eye[:2])
    yaw, pit = math.radians(27), math.radians(7.5)
    fx = to[0] * math.cos(yaw) + to[1] * math.sin(yaw); fy = -to[0] * math.sin(yaw) + to[1] * math.cos(yaw)
    fwd = np.array([fx * math.cos(pit), fy * math.cos(pit), -math.sin(pit)])
    return Camera3D(eye, eye + fwd, focal=1200.)


CAM = _cam()
HZ = float(CAM.project(CAM.eye + np.r_[CAM.R[2][:2] / np.linalg.norm(CAM.R[2][:2]), 0] * 1e6)[0][1])
SUN = (1500., HZ - 58.)
SR = 46.


def sun_dir(cam=CAM):
    d = np.array([(SUN[0] - cam.cx) / cam.f, (SUN[1] - cam.cy) / cam.f, 1.]) @ cam.R
    return d / np.linalg.norm(d)


def _rail_pt(az):
    """world point on the top rail at world azimuth az"""
    return np.array([AT[0] + lh.R_RAIL * math.cos(az), AT[1] + lh.R_RAIL * math.sin(az), ZD + (lh.Z_RAIL[2] - lh.Z_DECK)])


def _marks():
    # the otter lies on the near top rail, right of the lamp, its head toward the sun
    az = math.radians(-58.)
    P = np.array([_rail_pt(az + d) for d in np.radians([-9, -4.5, 0, 4.5, 9])])
    S, _ = CAM.project(P)
    c = P[2]
    sc = float(CAM.scale(c))
    sd = np.array(SUN) - S[2]; sd /= np.linalg.norm(sd)
    lx, ly = lh.lamp_px(CAM, AT)
    return dict(ground=float(S[2][1]), x0=float(S[1][0]), x1=float(S[3][0]), scale=float(.40 * sc),
                light=dict(dir=(float(sd[0]), float(sd[1])), color='#ffe7b8', amt=.8),
                rail=[(float(x), float(y)) for x, y in S], rail_w=float(.05 * sc),
                lamp=(lx, ly), lamp_off=9.0, sun=SUN, back_light=dict(color='#ffc46b', at=(lx, ly), amt=.5, off=9.0))


BOAT_PATH = lambda t: (36. - 2.3 * t, 66. - .9 * t)          # world m; it runs right to left under the tower


class Shot:
    n = 312
    finish = dict(hal_amt=.24, vig=.10)
    M = _marks()
    CX, CY = M['x0'] * .5 + M['x1'] * .5, M['ground'] - 120     # the push closes gently on the otter

    # ---------------------------------------------------------------- setup
    def setup(self):
        cv2.setNumThreads(2)
        ev = self.scene.get('events', {})
        self.t_horn = list(ev.get('horn', [3.0, 3.6]))
        self.t_wave = float(ev.get('wave', 6.0))
        self.t_off = float(ev.get('lampoff', 9.0))
        cam = CAM
        sd = sun_dir()
        self.sd = sd
        def cached(name, fn):
            p = cache_path(f's9_{name}_{VER}.npy')
            if os.path.exists(p): return np.load(p).astype(f32)
            a = fn(); np.save(p + '.tmp.npy', a.astype(np.float16)); os.replace(p + '.tmp.npy', p)
            return a.astype(f32)
        light = sd * np.array([1, 1, .6]) + np.array([0, 0, .35])
        self.sky = cached('sky', sky_plate)
        sea = cached('sea', lambda: np.dstack(sea_plate(cam, sd)))
        self.sea, self.Y, self.sheen = sea[..., :3].copy(), sea[..., 3].copy(), sea[..., 4].copy()
        del sea
        def tower():
            on, m = lh.paint_tower(cam, 'dawn', 1.0, AT, light=light, house=False, masks=True, seed=7)
            off = lh.paint_tower(cam, 'dawn', 0.0, AT, light=light, house=False, seed=7)
            g = cv2.dilate(m['glass'], np.ones((5, 5), np.uint8))
            g = cv2.GaussianBlur(g, (0, 0), 1.2)
            return np.dstack([on, off, g])
        T = cached('tower', tower)
        self.on, self.off, self.glass = T[..., :4].copy(), T[..., 4:8].copy(), T[..., 8].copy()
        del T
        def reef():
            L, info = island.paint_rocks(cam, reef_rocks(), 'dawn', light=light, seed=12, sizes=(5, 2.5, 1.3), tex=.06, dabs=.6, rim=.2, wet=.45)
            from shots.s1_island import _foam
            fo = _foam(info['foam'], 110.)
            return np.dstack([L, fo])
        R = cached('reef', reef)
        self.reef, self.foam = R[..., :4].copy(), R[..., 4].copy()
        self.gl = glitter_set(cam, sd)
        self.thrift_at = self._clumps()
        self.thrift = island.Thrift(self.thrift_at, 'dawn', seed=9, heads=3, blades=70)
        self.lamp = lh.lamp_px(cam, AT)
        self.lr = lh.lamp_radius_px(cam, AT)
        self.shadow = self._post_shadows(sd)

    def _post_shadows(self, sd):
        """the low sun lays the railing posts' shadows long across the deck"""
        sh = sd[:2] / np.linalg.norm(sd[:2]); el = math.atan2(sd[2], np.linalg.norm(sd[:2]))
        Ls = min(7., (lh.Z_RAIL[2] - lh.Z_DECK) / math.tan(max(el, .02)))
        cv = Canvas(H, W, layer=True, color='#000000')
        P = []; WD = []
        dax = np.linalg.norm(CAM.eye[:2] - np.array(AT[:2]))
        for k in range(36):
            az = -math.pi + 2 * math.pi * (k + .5) / 36
            B = np.array([AT[0] + lh.R_RAIL * math.cos(az), AT[1] + lh.R_RAIL * math.sin(az)])
            ss = np.linspace(0, Ls, 60)
            Q = B[None] - sh[None] * ss[:, None]
            rr = np.hypot(Q[:, 0] - AT[0], Q[:, 1] - AT[1])
            ok = (rr > 1.62) & (rr < lh.R_DECK - .03) & (np.hypot(*(Q - CAM.eye[:2]).T) < dax)
            if ok.sum() < 4: continue
            i0 = np.argmax(ok); i1 = i0 + np.argmin(ok[i0:]) if not ok[i0:].all() else len(ok)
            Q = Q[i0:i1]
            if len(Q) < 4: continue
            idx = np.linspace(0, len(Q) - 1, 6).astype(int)
            S, z = CAM.project(np.c_[Q[idx], np.full(6, ZD + .005)])
            if (z < .3).any(): continue
            P.append(S); WD.append(float(CAM.f / z.mean()) * .03)
        if P:
            cv.strokes(np.array(P, f32), np.array(WD), np.zeros(3, f32), op=.9, seed=4, shape='flat', bristle=.03)
        return cv2.GaussianBlur(cv.a, (0, 0), .8) * (self.on[..., 3] > .5)

    def _clumps(self):
        """thrift rooted in the cracks of the gallery deck, by the railing posts"""
        out = []
        r = np.random.default_rng(3)
        for az, rad, s in ((-108, 1.8, .9), (-92, 1.78, 1.1), (-76, 1.85, .8), (-60, 1.8, .7), (-50, 2.05, .6)):
            P = np.array([AT[0] + rad * math.cos(math.radians(az)), AT[1] + rad * math.sin(math.radians(az)), ZD])
            (x, y), z = CAM.project(P)
            if 0 < x < W and 0 < y < H:
                out.append((float(x), float(y), float(CAM.scale(P) * .32 * s)))
        return out

    # ---------------------------------------------------------------- per frame
    def lampk(self, f):
        """1 lit .. 0 out: the flame shrinks over half a second from the declared moment"""
        t = f / 24.
        q = np.clip((t - self.t_off) / .55, 0, 1)
        return float(1 - q ** .7) if q < 1 else 0.

    def zoom(self, f):
        return 1 + .028 * comp.ease(f / (self.n - 1.))

    def frame(self, f):
        t = f / 24.
        sea = self.sea.copy()
        y0 = int(HZ) - 2
        Y = self.Y[y0:]
        sw = np.sin(2 * np.pi * (Y / 22. + t / 6.)) + .4 * np.sin(2 * np.pi * (Y / 9. + t / 3.7) + 1.3)
        sea[y0:] *= (1 + .035 * sw * np.clip(40. / (Y + 1e-3), .2, 1))[..., None]
        sea = self._glitter(sea, f)
        sea = self._wake(sea, f)
        seam = smooth(HZ - .5, HZ + 1., np.arange(H, dtype=f32))[:, None, None]
        img = self.sky * (1 - seam) + sea * seam
        # the reef, the wave that washes it
        img = comp.over(img, self.reef)
        img = self._wave(img, f)
        img = self._boat(img, f)
        # the tower: lantern lit until the declared moment, then out
        k = self.lampk(f)
        g = self.glass[..., None] * (1 - k)
        L = self.on * (1 - g) + self.off * g
        img = comp.over(img, L)
        img = img * (1 - self.shadow[..., None] * (1 - rgb('#c4a8c8')) * .55)
        if k > 0:
            fl = k * (1 + .03 * math.sin(f * .9) * (f % 2 == 0))
            img = lh.lamp_glow(img, CAM, AT, amt=.32 * fl, col='#ffc46b', size=.45)
            img = img + (self.glass * .10 * fl)[..., None] * rgb('#ffb458')
        # sun's breath on the whole lit side: a faint warm veil toward the sun
        # the otter, on the near rail
        img = otteract.draw(img, 's9', f, self.M)
        # deck thrift in the wind (on threes)
        cv = Canvas(H - 700, 1100, layer=True, color='#86906e')
        for (x, y, sz) in self.thrift_at:
            cv.strokes(arcs(np.array([x]), np.array([y - 700 + sz * .03]), np.zeros(1), sz * .9, 0., K=3), sz * .12, rgb('#8d7a98'), op=.45, seed=5, shape='round', bristle=.02)
        gust = .7 + .5 * math.sin(t * .9) + .35 * math.exp(-((t - 7.5) / 1.2) ** 2)
        self.thrift.draw(cv, f, wind=gust, ox=0, oy=700, light=1)
        img[700:, :1100] = comp.over(img[700:, :1100], cv.layer())
        # the push
        z = self.zoom(f)
        M = np.float32([[1 / z, 0, self.CX - self.CX / z], [0, 1 / z, self.CY - self.CY / z]])
        img = cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT_101)
        return img

    def _glitter(self, sea, f):
        g = self.gl
        d = (f // 2) * 2
        t = d / 24.
        tw = np.clip(np.sin(2 * np.pi * (g['ph'] + t * g['rate'])), 0, 1) ** 2.5
        b = g['b'] * tw
        on = b > .05
        if not on.any(): return sea
        xy, L, w = g['xy'][on], g['L'][on], g['w'][on]
        x0, y0 = int(max(0, xy[:, 0].min() - 60)), int(max(0, xy[:, 1].min() - 6))
        x1, y1 = int(min(W, xy[:, 0].max() + 60)), int(min(H, xy[:, 1].max() + 6))
        cv = Canvas(y1 - y0, x1 - x0, layer=True, color='#fff1cc')
        P = arcs(xy[:, 0] - x0, xy[:, 1] - y0, np.zeros(len(L)), L, 0., K=3)
        cv.strokes(P, w, rgb('#fff1cc'), op=np.clip(b[on], 0, 1), seed=d, shape='round', bristle=.02)
        sea[y0:y1, x0:x1] = comp.over(sea[y0:y1, x0:x1], cv.layer())
        return sea

    # boat ---------------------------------------------------------------
    def _pose(self, t):
        X, Y = BOAT_PATH(t)
        hdg = math.atan2(-.9, -2.3)
        hf = lambda xs, ys: .06 * np.sin(.35 * np.asarray(xs) + .5 * np.asarray(ys) + t * 1.3)
        if boat is not None:
            return boat.place(CAM, X, Y, hdg, hf)
        (x, y), _ = CAM.project(np.array([X, Y, 0.]))
        return dict(x=float(x), y=float(y), scale=float(CAM.scale(np.array([X, Y, 0.])) * 9), pitch=0., roll=0., facing=-1, fore=1.)

    def _wake(self, sea, f):
        """two fine arms spreading from the stern and a churned trail, fading with age"""
        t = (f // 2) * 2 / 24.
        hdg = math.atan2(-.9, -2.3)
        dx, dy = math.cos(hdg), math.sin(hdg); px, py = -dy, dx
        ages = np.linspace(.05, 7.5, 60)
        P = []; WD = []; OP = []; C = []
        for s in (-1, 1, 0):
            pts = []
            for a in ages:
                X, Y = BOAT_PATH(t - a)
                X -= dx * 4.3; Y -= dy * 4.3
                o = s * (.9 + a * 2.3 * .34) if s else 0.
                pts.append((X + px * o, Y + py * o, 0.))
            S, z = CAM.project(np.array(pts))
            for i in range(0, len(S) - 3, 2):
                q = S[i:i + 4]
                if (q[:, 1] < HZ + 2).any() or (z[i:i + 4] < 1).any(): continue
                age = ages[i]
                P.append(q); WD.append(max(.6, float(CAM.f / z[i]) * (.22 if s == 0 else .1)))
                OP.append(float(np.exp(-age / (2.2 if s == 0 else 3.4)) * (.75 if s == 0 else .6)))
        if not P: return sea
        P = np.array(P, f32)
        x0, y0 = int(max(0, P[..., 0].min() - 10)), int(max(0, P[..., 1].min() - 10))
        x1, y1 = int(min(W, P[..., 0].max() + 10)), int(min(H, P[..., 1].max() + 10))
        if x1 <= x0 or y1 <= y0: return sea
        cv = Canvas(y1 - y0, x1 - x0, layer=True, color='#fff6ea')
        P = P - np.array([x0, y0], f32)
        cv.strokes(P, np.array(WD), rgb('#fff6ea'), op=np.array(OP), dry=.25, seed=(f // 2), shape='round', bristle=.04)
        sea[y0:y1, x0:x1] = comp.over(sea[y0:y1, x0:x1], cv.layer())
        return sea

    def _boat(self, img, f):
        d = (f // 2) * 2
        t = d / 24.
        p = self._pose(t)
        if boat is not None:
            p2 = self._pose(t - 2 / 24.)
            swing = .25 * math.sin(t * 2.1) - 2. * (p['pitch'] - p2['pitch'])
            img = boat.draw(img, p['x'], p['y'], p['scale'], p['pitch'], .32, lantern_swing=swing, palette='dawn', facing=p['facing'], f=d,
                            fore=p['fore'], lamp=0.0, wet=0.0, cut=True)
        else:
            c = Cel(W, H)
            x, y, s = p['x'], p['y'], p['scale']
            c.fill([[x - s / 2, y - s * .08], [x + s / 2, y - s * .1], [x + s * .4, y + s * .05], [x - s * .45, y + s * .05]], '#a4463e')
            img = comp.over(img, c.layer())
        # horn: a puff of steam from the funnel for each declared blast
        fx, fy = p['x'] - p['facing'] * p['scale'] * .18 * p['fore'], p['y'] - p['scale'] * .36
        for th in self.t_horn:
            a = t - th
            if 0 <= a < 2.2:
                img = _puff(img, fx, fy, p['scale'], a, int(th * 10))
        return img

    def _wave(self, img, f):
        """foam at the reef: a slow breathing lace, and the declared wave that runs in and washes over it"""
        t = f / 24.
        a = t - self.t_wave
        br = .35 + .15 * math.sin(t * 2 * math.pi / 5.)
        if -1.2 < a < 3.5:
            br += .8 * smooth(-1.2, 0, a) * math.exp(-max(0, a) / 1.1)
        img = img + (self.foam * np.clip(br, 0, 1.2))[..., None] * (rgb('#fff6ea') - img) * .85
        return img

    def actors(self, f):
        acts = otteract.actors('s9', f, self.M)
        z = self.zoom(f)
        out = []
        for a in acts:
            a = dict(a)
            a['x'] = self.CX + (a['x'] - self.CX) * z; a['y'] = self.CY + (a['y'] - self.CY) * z; a['s'] = a['s'] * z
            if 'points' in a:
                a['points'] = {k: [self.CX + (v[0] - self.CX) * z, self.CY + (v[1] - self.CY) * z] for k, v in a['points'].items()}
            out.append(a)
        if boat is not None:
            p = self._pose((f // 2) * 2 / 24.)
            b = boat.actor(p)
            b['x'] = self.CX + (b['x'] - self.CX) * z; b['y'] = self.CY + (b['y'] - self.CY) * z
            out.append(b)
        return out


def _puff(img, x, y, s, a, seed):
    """a white steam puff rising and thinning: drawn as a few round gouache dabs"""
    r = np.random.default_rng(seed)
    R = s * .05 * (1 + a * 1.4)
    op = smooth(0, .12, a) * math.exp(-a / .9)
    n = 7
    cx = x + r.normal(0, .3, n) * R - a * s * .05
    cy = y - a * s * .12 - r.uniform(0, 1, n) * R
    x0, y0, x1, y1 = int(max(0, cx.min() - R * 2)), int(max(0, cy.min() - R * 2)), int(min(W, cx.max() + R * 2)), int(min(H, cy.max() + R * 2))
    if x1 <= x0 or y1 <= y0: return img
    cv = Canvas(y1 - y0, x1 - x0, layer=True, color='#fffaf2')
    P = arcs(cx - x0, cy - y0, r.uniform(0, 3, n), R * 1.2, .8, K=4)
    cv.strokes(P, R * r.uniform(.5, .8, n), rgb('#fffaf2'), op=op * r.uniform(.5, .9, n), seed=seed, shape='round', bristle=.03)
    img[y0:y1, x0:x1] = comp.over(img[y0:y1, x0:x1], cv.layer())
    return img


# ================================================================= plates
def sky_plate():
    x, y = grid()
    t = np.clip(y / HZ, 0, 1)
    base = ramp(t, [(0, '#8fb6d9'), (.28, '#b3bfd9'), (.55, '#e9c6c8'), (.80, '#f7d9a8'), (1, '#ffe7b8')])
    d = np.sqrt((x - SUN[0]) ** 2 + ((y - SUN[1]) * 1.6) ** 2)
    base = base + (np.exp(-(d / 700.) ** 1.4) * .22)[..., None] * (rgb('#fff0c8') - base)
    base = base + (np.exp(-(d / 160.) ** 2) * .16)[..., None] * (rgb('#fff6e0') - base)
    ang = fbm(H, W, (260, 90), (1, .4), 3) * .06
    out = repaint(base, (50, 22), seed=6, angle=ang, thr=(0, .004), density=.9, aspect=6.5, jit=(.001, .004, .006), op=.5, dry=.18, curve=.12, bristle=.02)
    out = mottle(out, .006, 5, .002)
    # sun disc
    c = Cel(W, H, 0, 0, ss=2)
    tt = np.linspace(0, 2 * np.pi, 64, endpoint=False)
    c.fill(np.c_[SUN[0] + SR * np.cos(tt), SUN[1] + SR * np.sin(tt)], '#fff3d6')
    out = comp.over(out, c.layer())
    out = comp.glow(out, SUN[0], SUN[1], 240, '#ffd8a0', .22, 2.2)
    # clouds: low pink banks with gold rims toward the sun, long high strata
    S = clouds.Sky(H, W, out, light=(.75, -.35, .5), seed=31)
    Tp = clouds.tones('#fff0d8', '#f2c8bc', '#d8aab8', '#b898b4')
    Tf = clouds.tones('#f6dcc8', '#e8c0bc', '#cfa8b8', '#b49cb8')
    for (x, b, w, h, sd) in ((900, HZ + 2, 420, 30, 1), (1250, HZ + 1, 260, 18, 2), (1820, HZ + 2, 360, 26, 3), (2040, HZ + 2, 300, 40, 4)):
        S.bank(x, b, w, h, Tf, '#e8c4c0', seed=sd, tiers=2, levels=2, n=6, pool=.5, lit=.25, soft=1.0, detail=.7)
    S.bank(1180, 250, 620, 70, Tp, '#e0bcc4', seed=11, profile=clouds.peak(.4, .25, .35, .7, .5, .2), n=7, levels=2, pool=.3, lit=.3, soft=1.4, detail=.6)
    S.bank(1820, 170, 520, 56, Tp * .98, '#d8b8c4', seed=12, n=6, levels=2, pool=.3, lit=.28, soft=1.4, detail=.6)
    S.strata(HZ - 40, HZ - 8, 18, ['#ffe6c4', '#f6cdb8', '#ffefd6'], seed=13, x=(700, 2048), w=(.05, .2), th=(1.5, 3.5), op=(.35, .7))
    S.strata(90, 330, 22, ['#f4d0c8', '#e9c6c8', '#fbe0cc'], seed=14, x=(600, 2048), w=(.08, .3), th=(1.5, 4.5), op=(.25, .55), power=1.0)
    return S.paint(5)


def sea_plate(cam, sd):
    u, v, t = cam.uv((0, 0, 0), (1, 0, 0), (0, 1, 0))
    Y = np.where(t > 0, v, 1e4).astype(f32)
    x, y = grid()
    q = np.clip((y - HZ) / (H - HZ), 0, 1)
    base = ramp(q, [(0, '#e6c8c6'), (.04, '#c7b6c4'), (.25, '#aeb0c8'), (.6, '#9aa8c8'), (1, '#8a9ac0')])
    d = cam.rays(); d /= np.linalg.norm(d, axis=-1, keepdims=True)
    rf = d * np.array([1, 1, -1], f32)
    sheen = _refl(rf, sd, .07, .3) * (y > HZ)
    base = base + sheen[..., None] * (rgb('#ffe2a8') - base) * .55
    r = np.random.default_rng(7)
    cv = Canvas(img=base)
    n = 4200
    Xw = r.uniform(-60, 160, n); Yw = 20 + 1200 * r.uniform(0, 1, n) ** 2.6
    P = np.zeros((n, 5, 2), f32); WD = np.zeros(n, f32); C = np.zeros((n, 3), f32); OP = np.zeros(n, f32); keep = np.zeros(n, bool)
    for i in range(n):
        Lw = r.uniform(2, 7) * (1 + Yw[i] / 200)
        xs = Xw[i] + np.linspace(-.5, .5, 5) * Lw
        ys = Yw[i] + np.sin(np.linspace(0, 3, 5) + i) * .2 * (1 + Yw[i] / 150)
        pts, z = cam.project(np.stack([xs, ys, np.zeros(5)], -1))
        if (z < 1).any(): continue
        P[i] = pts
        WD[i] = max(.5, cam.f / z[2] * .1 * r.uniform(.6, 1.3))
        cy, cx = int(np.clip(pts[2, 1], 0, H - 1)), int(np.clip(pts[2, 0], 0, W - 1))
        crest = r.random() < .5
        bc = base[cy, cx]
        C[i] = mix(bc * 1.06, rgb('#ffeccc'), .25 + .5 * sheen[cy, cx]) if crest else bc * mix(np.ones(3, f32), rgb('#b6a8d0') * 1.1, .35) * .95
        OP[i] = r.uniform(.3, .65)
        keep[i] = (-20 <= pts[2, 0] < W + 20) and HZ < pts[2, 1] < H + 20
    cv.strokes(P[keep], WD[keep], np.clip(C[keep], 0, 1), op=OP[keep], dry=.2, seed=9, shape='round', bristle=.05)
    out = mottle(cv.img, .008, 8, .003)
    return out, Y, sheen.astype(f32)


def _refl(rf, md, sh, sv):
    az = np.arctan2(rf[..., 0], rf[..., 1]) - math.atan2(md[0], md[1])
    el = np.arctan2(rf[..., 2], np.hypot(rf[..., 0], rf[..., 1])) - math.atan2(md[2], math.hypot(md[0], md[1]))
    return np.exp(-(az / sh) ** 2 - (el / sv) ** 2).astype(f32)


def glitter_set(cam, sd):
    r = np.random.default_rng(21)
    m = 14000
    Yw = 25 + 1600 * r.uniform(0, 1, m) ** 2.4
    a0 = math.atan2(sd[0], sd[1])
    Xw = cam.eye[0] + (Yw - cam.eye[1]) * math.tan(a0) + r.normal(0, 1, m) * (1 + Yw * .09)
    P3 = np.stack([Xw, Yw, np.zeros_like(Xw)], -1)
    d = P3 - cam.eye; d /= np.linalg.norm(d, axis=-1, keepdims=True)
    pr = _refl(d * np.array([1, 1, -1]), sd, .06, .26)
    keep = r.random(m) < pr
    P3 = P3[keep]
    xy, z = cam.project(P3)
    ok = (xy[:, 1] > HZ + 1) & (xy[:, 0] > -20) & (xy[:, 0] < W + 20) & (z > 1)
    P3, xy, z = P3[ok], xy[ok], z[ok]
    n = len(xy)
    s = cam.f / z
    return dict(xy=xy.astype(f32), L=np.clip(s * r.uniform(.6, 2.2, n), 2, 46).astype(f32), w=np.clip(s * r.uniform(.06, .14, n), .45, 3.5).astype(f32),
                ph=r.uniform(0, 1, n).astype(f32), rate=r.uniform(.3, .8, n).astype(f32), b=r.uniform(.55, 1., n).astype(f32))


def reef_rocks():
    r = np.random.default_rng(41)
    P = island.prism
    kw = dict(rough=.34, inset=.4, flare=.22, dome=.2)
    return [P(13.0, 30.0, 3.2, 2.0, -.08, 1.1, r, k=12, **kw), P(17.5, 32.5, 2.4, 1.6, -.08, .7, r, k=11, **kw), P(9.5, 33.5, 1.8, 1.2, -.08, .5, r, k=10, **kw),
            P(21.0, 29.0, 1.6, 1.0, -.08, .4, r, k=10, **kw), P(15.2, 27.0, 1.2, .8, -.08, .3, r, k=9, **kw), P(6.5, 31.0, 1.0, .6, -.08, .2, r, k=9, **kw),
            P(11.0, 27.5, .7, .45, -.08, .15, r, k=8, **kw), P(19.4, 35.0, 1.3, .8, -.08, .3, r, k=9, **kw)]
