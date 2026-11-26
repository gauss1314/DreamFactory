"""s9 黎明.  A still dawn after the storm, close on the otter.  The camera hangs just off the gallery, low, looking
along it: the otter stands on the gallery floor and leans on the iron railing in the near third of the frame, the lantern
(still lit) behind it at the upper left, and beyond the rail the calm sea breaking into gold under a sun just clear of the
horizon.  The fishing boat passes under the tower and sounds its horn twice (3.0 s, 3.6 s), a V of wake opening behind
it; a slow wave washes the reef (6.0 s); the lamp, its night's work done, goes out (9.0 s).  The air moves: thrift in the
deck's cracks, the sea's glitter.  The camera dollies in: the gallery grows faster than the sea (two-layer parallax).
The driver fades out the last 2 s."""
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

VER = 'v7'
AT = (0., 0., 5.6)
ZD = AT[2] + lh.Z_DECK
EAZ, YAW = -120., 22.                    # camera azimuth round the tower, view heading (deg, world)
OAZ = -110.                              # the otter's place on the gallery (deg)


def _cam():
    eye = np.array([3.6 * math.cos(math.radians(EAZ)), 3.6 * math.sin(math.radians(EAZ)), ZD + .5])
    y, p = math.radians(YAW), math.radians(2.5)
    fwd = np.array([math.cos(y) * math.cos(p), math.sin(y) * math.cos(p), -math.sin(p)])
    return Camera3D(eye, eye + fwd, focal=1100.)


CAM = _cam()
HZ = float(CAM.project(CAM.eye + np.r_[CAM.R[2][:2] / np.linalg.norm(CAM.R[2][:2]), 0] * 1e6)[0][1])
SUN = (1590., HZ - 66.)
SR = 44.


def sun_dir(cam=CAM):
    d = np.array([(SUN[0] - cam.cx) / cam.f, (SUN[1] - cam.cy) / cam.f, 1.]) @ cam.R
    return d / np.linalg.norm(d)


def _ring(az_deg, r, z):
    a = np.radians(np.atleast_1d(az_deg))
    return np.stack([AT[0] + r * np.cos(a), AT[1] + r * np.sin(a), np.full(a.shape, z)], -1)


def _marks():
    """marks for the otter: it stands on the gallery floor, leaning on the low rail, facing the sea and the sun"""
    feet = _ring(OAZ, 2.68, ZD)[0]
    (fx, fy), _ = CAM.project(feet)
    sc = float(CAM.scale(feet))
    side = _ring([OAZ - 3.5, OAZ + 3.5], 2.68, ZD)
    S, _ = CAM.project(side)
    lean = CAM.project(_ring(np.linspace(OAZ - 9, OAZ + 9, 7), lh.R_RAIL, AT[2] + lh.Z_RAIL[1]))[0]
    top = CAM.project(_ring(np.linspace(OAZ - 9, OAZ + 9, 7), lh.R_RAIL, AT[2] + lh.Z_RAIL[-1]))[0]
    posts = []
    for az in np.arange(-180, 180, 10) + 5:
        if abs(((az - OAZ + 180) % 360) - 180) < 16:
            b = CAM.project(_ring(az, lh.R_RAIL, ZD))[0][0]; t = CAM.project(_ring(az, lh.R_RAIL, AT[2] + lh.Z_RAIL[-1]))[0][0]
            posts.append(((float(b[0]), float(b[1])), (float(t[0]), float(t[1]))))
    sd = np.array(SUN) - np.array([fx, fy - .3 * .4 * sc]); sd /= np.linalg.norm(sd)
    lx, ly = lh.lamp_px(CAM, AT)
    return dict(ground=float(fy), x0=float(min(S[:, 0])), x1=float(max(S[:, 0])), scale=float(.40 * sc),
                light=dict(dir=(float(sd[0]), float(sd[1])), color='#ffe7b8', amt=.85),
                rail=[(float(x), float(y)) for x, y in lean], rail_h=float(lh.Z_RAIL[1] - lh.Z_DECK),
                rail_top=[(float(x), float(y)) for x, y in top], rail_w=float(.045 * CAM.scale(_ring(OAZ, lh.R_RAIL, ZD)[0])),
                posts=posts, facing='right',
                lamp=(lx, ly), lamp_off=9.0, sun=SUN, back_light=dict(color='#ffc46b', at=(lx, ly), amt=.45, off=9.0))


def _boat_path(t):
    """world position: from the right of the frame toward the tower foot, ~2.5 m/s, passing under the gallery"""
    a0 = math.radians(YAW - 36.); a1 = math.radians(YAW - 4.)
    q = t / 13.
    a = a0 + (a1 - a0) * q; d = 78. - 16. * q
    return CAM.eye[0] + d * math.cos(a), CAM.eye[1] + d * math.sin(a)


def _boat_heading():
    (x0, y0), (x1, y1) = _boat_path(0.), _boat_path(13.)
    return math.atan2(y1 - y0, x1 - x0)


class Shot:
    n = 312
    finish = dict(hal_amt=.24, vig=.10)
    M = _marks()
    CX, CY = .8 * (M['x0'] + M['x1']) * .5 + .2 * M['lamp'][0], .55 * (M['ground'] - .5 * M['scale']) + .45 * M['lamp'][1]   # the dolly closes on the otter, the lamp stays in

    # ---------------------------------------------------------------- setup
    def setup(self):
        cv2.setNumThreads(2)
        ev = self.scene.get('events', {})
        self.t_horn = list(ev.get('horn', [3.0, 3.6]))
        self.t_wave = float(ev.get('wave', 6.0))
        self.t_off = float(ev.get('lampoff', 9.0))
        cam = CAM
        sd = self.sd = sun_dir()
        light = sd * np.array([1, 1, .6]) + np.array([0, 0, .35])
        def cached(name, fn):
            p = cache_path(f's9_{name}_{VER}.npy')
            if os.path.exists(p): return np.load(p).astype(f32)
            a = fn(); np.save(p + '.tmp.npy', a.astype(np.float16)); os.replace(p + '.tmp.npy', p)
            return a.astype(f32)
        self.sky = cached('sky', sky_plate)
        sea = cached('sea', lambda: np.dstack(sea_plate(cam, sd)))
        self.sea, self.Y, self.sheen = sea[..., :3].copy(), np.nan_to_num(sea[..., 3], nan=1e4, posinf=1e4, neginf=1e4), sea[..., 4].copy()
        del sea
        def reef():
            L, info = island.paint_rocks(cam, reef_rocks(), 'dawn', light=light, seed=12, sizes=(5, 2.5, 1.3), tex=.06, dabs=.6, rim=.2, wet=.45)
            from shots.s1_island import _foam
            return np.dstack([L, _foam(info['foam'], 110.)])
        R = cached('reef', reef)
        self.reef, self.foam = R[..., :4].copy(), R[..., 4].copy()
        del R
        def fore():
            on, m = lh.paint_tower(cam, 'dawn', 1.0, AT, light=light, house=False, masks=True, seed=7, top_only=True)
            off = lh.paint_tower(cam, 'dawn', 0.0, AT, light=light, house=False, seed=7, top_only=True)
            g = cv2.GaussianBlur(cv2.dilate(m['glass'], np.ones((5, 5), np.uint8)), (0, 0), 1.2)
            on, off = _wall_light(on, g), _wall_light(off, g)
            deck, edge = gallery(cam, light)
            rail = railing(cam, light); lean = railing(cam, light, 'lean')
            sh = post_shadows(cam, sd)
            return np.dstack([on, off, g, deck, rail, sh, edge, lean])
        F = cached('fore', fore)
        self.on, self.off, self.glass = F[..., 0:4].copy(), F[..., 4:8].copy(), F[..., 8].copy()
        self.deck, self.rail, self.shadow, self.edge = F[..., 9:13].copy(), F[..., 13:17].copy(), F[..., 17].copy(), F[..., 18].copy()
        self.lean = F[..., 19:23].copy()
        del F
        self.gl = glitter_set(cam, sd)
        self.thrift_at = self._clumps()
        self.thrift = island.Thrift(self.thrift_at, 'dawn', seed=9, heads=3, blades=70)
        self.hdg = _boat_heading()
        # warm lamp light lying on the deck by the lantern wall
        x, y = grid()
        lx, ly = lh.lamp_px(cam, AT)
        b = _ring(OAZ + 14, 1.95, ZD)[0]
        (bx, by), _ = cam.project(b)
        self.spill = (np.exp(-(((x - bx) / 420.) ** 2 + ((y - by) / 160.) ** 2)) * self.deck[..., 3]).astype(f32)

    def _clumps(self):
        """thrift rooted in the cracks of the gallery floor, along the foot of the rail and the lantern wall"""
        out = []
        for az, rad, s in ((OAZ - 7, 2.72, .8), (OAZ + 9, 2.75, .7), (OAZ + 22, 2.7, .9), (OAZ + 34, 2.66, 1.0), (OAZ + 18, 1.72, .9), (OAZ + 40, 1.75, 1.1)):
            P = _ring(az, rad, ZD)[0]
            (x, y), z = CAM.project(P)
            if z > .3 and -40 < x < W + 40 and 0 < y < H + 20:
                out.append((float(x), float(y), float(min(260., CAM.scale(P) * .26 * s))))
        return out

    # ---------------------------------------------------------------- per frame
    def lampk(self, f):
        """1 lit .. 0 out: the flame shrinks over half a second from the declared moment"""
        q = np.clip((f / 24. - self.t_off) / .55, 0, 1)
        return float(1 - q ** .7) if q < 1 else 0.

    def cams(self, f):
        """the dolly: (zoom, dx) of the near layer and of the far layer"""
        e = comp.ease(f / (self.n - 1.))
        return (1 + .07 * e, -40 * e), (1 + .02 * e, -18 * e)

    def _warp(self, img, z, dx, interp=cv2.INTER_LINEAR):
        M = np.float32([[1 / z, 0, self.CX - (self.CX + dx) / z], [0, 1 / z, self.CY - self.CY / z]])
        return cv2.warpAffine(img, M, (W, H), flags=interp | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT_101)

    def frame(self, f):
        t = f / 24.
        # far layer: sky, sea, reef, boat
        sea = self.sea.copy()
        y0 = int(HZ) - 2
        Y = self.Y[y0:]
        sw = np.sin(2 * np.pi * (Y / 22. + t / 6.)) + .4 * np.sin(2 * np.pi * (Y / 9. + t / 3.7) + 1.3)
        sea[y0:] *= (1 + .035 * sw * np.clip(40. / (Y + 1e-3), .2, 1))[..., None]
        sea = self._glitter(sea, f)
        sea = self._wake(sea, f)
        seam = smooth(HZ - .5, HZ + 1., np.arange(H, dtype=f32))[:, None, None]
        far = self.sky * (1 - seam) + sea * seam
        far = comp.over(far, self.reef)
        far = self._wave(far, f)
        far = self._boat(far, f)
        (zn, dn), (zf, df) = self.cams(f)
        img = self._warp(far, zf, df)
        # near layer through its own dolly: lantern (lit until the declared moment), floor, shadows, warm spill
        k = self.lampk(f)
        g = self.glass[..., None] * (1 - k)
        near = _over4(self.on * (1 - g) + self.off * g, self.deck)
        near = self._warp(near, zn, dn)
        img = comp.over(img, near)
        img = img * (1 - self._warp(self.shadow, zn, dn)[..., None] * (1 - rgb('#c4a8c8')) * .5)
        lx, ly = self._xf(*self.M['lamp'], f)
        if k > 0:
            fl = k * (1 + .03 * math.sin(f * .9) * (f % 2 == 0))
            img = _glow(img, lx, ly, lh.lamp_radius_px(CAM, AT) * zn, .30 * fl, '#ffc46b')
            img = img + (self._warp(self.glass, zn, dn) * .10 * fl)[..., None] * rgb('#ffb458')
            img = img + (self._warp(self.spill, zn, dn) * .07 * fl)[..., None] * rgb('#ffb458')
        img = self._thrift(img, f)
        # the low rail it leans on goes between its body and its forearms: the otter draws its body,
        # hands the picture back for the rail, then draws the forearms resting on it
        M = self.marks(f)
        M['between'] = lambda im, _f: comp.over(im, self._warp(self.lean, zn, dn))
        img = otteract.draw(img, 's9', f, M)
        img = comp.over(img, self._warp(self.rail, zn, dn))
        return img

    def marks(self, f):
        """Shot.M carried through the dolly of the near layer: where the otter is in this frame's picture"""
        (zn, dn), _ = self.cams(f)
        M = dict(self.M)
        P = lambda q: tuple(float(v) for v in self._xf(q[0], q[1], f))
        M['ground'] = self._xf(0, self.M['ground'], f)[1]
        M['x0'] = self._xf(self.M['x0'], 0, f)[0]; M['x1'] = self._xf(self.M['x1'], 0, f)[0]
        M['scale'] = self.M['scale'] * zn
        M['rail'] = [P(q) for q in self.M['rail']]; M['rail_top'] = [P(q) for q in self.M['rail_top']]
        M['rail_w'] = self.M['rail_w'] * zn
        M['posts'] = [(P(b), P(t)) for b, t in self.M['posts']]
        M['lamp'] = P(self.M['lamp'])
        M['back_light'] = dict(self.M['back_light'], at=M['lamp'])
        return M

    def _thrift(self, img, f):
        y0 = int(max(0, min(c[1] for c in self.thrift_at) - 280)) if self.thrift_at else H
        if y0 >= H: return img
        cv = Canvas(H - y0, W, layer=True, color='#86906e')
        for (x, y, sz) in self.thrift_at:
            x, y = self._xf(x, y, f)
            cv.strokes(arcs(np.array([x]), np.array([y - y0 + sz * .03]), np.zeros(1), sz * .9, 0., K=3), sz * .12, rgb('#8d7a98'), op=.45, seed=5, shape='round', bristle=.02)
        t = f / 24.
        gust = .7 + .5 * math.sin(t * .9) + .35 * math.exp(-((t - 7.5) / 1.2) ** 2)
        (zn, dn), _ = self.cams(f)
        self.thrift.draw(cv, f, wind=gust, ox=self.CX - (self.CX + dn) / zn, oy=self.CY - self.CY / zn + y0 / zn, scale=zn, light=1)
        img[y0:] = comp.over(img[y0:], cv.layer())
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
        X, Y = _boat_path(t)
        hf = lambda xs, ys: .06 * np.sin(.35 * np.asarray(xs) + .5 * np.asarray(ys) + t * 1.3)
        if boat is not None:
            return boat.place(CAM, X, Y, self.hdg, hf)
        (x, y), _ = CAM.project(np.array([X, Y, 0.]))
        return dict(x=float(x), y=float(y), scale=float(CAM.scale(np.array([X, Y, 0.])) * 9), pitch=0., roll=0., facing=-1, fore=1.)

    def _wake(self, sea, f):
        """Kelvin wake: two arms opening from the stern at ~19 degrees, each a train of short feathered crests that
        widen, soften and fade with age and catch the light as the swell lifts them; a churned trail down the middle"""
        d = (f // 2) * 2
        t = d / 24.
        dx, dy = math.cos(self.hdg), math.sin(self.hdg); px, py = -dy, dx
        v = 2.6
        r = np.random.default_rng(77)
        ages = np.linspace(.15, 9., 90)
        jit = r.normal(0, 1, (3, len(ages)))
        P = []; WD = []; OP = []
        for si, s in enumerate((-1, 1)):
            for i, a in enumerate(ages):
                X, Y = _boat_path(t - a)
                X -= dx * 4.2; Y -= dy * 4.2
                off = s * (.8 + a * v * .42)
                cx, cy = X + px * off, Y + py * off
                # a crest: short, slanted back from the arm, longer and fainter with age
                L = .9 + a * .35
                ang = self.hdg + math.pi + s * math.radians(55 + 8 * jit[si, i])
                q = np.array([[cx - math.cos(ang) * L * .5, cy - math.sin(ang) * L * .5, 0], [cx, cy, 0], [cx + math.cos(ang) * L * .5, cy + math.sin(ang) * L * .5, 0]])
                S, z = CAM.project(q)
                if (z < 2).any() or (S[:, 1] < HZ + 2).any(): continue
                lift = .55 + .45 * math.sin(2 * math.pi * (t * .7 - a * .55) + jit[2, i])
                P.append(np.vstack([S[0], (S[0] + S[1]) / 2, S[1], (S[1] + S[2]) / 2, S[2]]))
                WD.append(max(.8, float(CAM.f / z[1]) * (.14 + .03 * a)))
                OP.append(float(np.exp(-a / 4.2) * .9 * lift))
        # the churned trail
        for i, a in enumerate(ages[:40]):
            X, Y = _boat_path(t - a); X -= dx * 4.6; Y -= dy * 4.6
            w = .6 + a * .25
            q = np.array([[X + px * w * jit[0, i] * .4 - dx * .8, Y + py * w * jit[0, i] * .4 - dy * .8, 0], [X + px * w * jit[1, i] * .4, Y + py * w * jit[1, i] * .4, 0], [X + dx * .8, Y + dy * .8, 0]])
            S, z = CAM.project(q)
            if (z < 2).any() or (S[:, 1] < HZ + 2).any(): continue
            P.append(np.vstack([S[0], (S[0] + S[1]) / 2, S[1], (S[1] + S[2]) / 2, S[2]]))
            WD.append(max(.6, float(CAM.f / z[1]) * (.25 + .05 * a)))
            OP.append(float(np.exp(-a / 1.6) * .7))
        if not P: return sea
        P = np.array(P, f32)
        x0, y0 = int(max(0, P[..., 0].min() - 10)), int(max(0, P[..., 1].min() - 10))
        x1, y1 = int(min(W, P[..., 0].max() + 10)), int(min(H, P[..., 1].max() + 10))
        if x1 <= x0 or y1 <= y0: return sea
        cv = Canvas(y1 - y0, x1 - x0, layer=True, color='#fff6ea')
        cv.strokes(P - np.array([x0, y0], f32), np.array(WD), rgb('#fff6ea'), op=np.clip(np.array(OP), 0, 1), dry=.3, seed=7, shape='round', bristle=.05)
        sea[y0:y1, x0:x1] = comp.over(sea[y0:y1, x0:x1], cv.layer())
        return sea

    def _boat(self, img, f):
        d = (f // 2) * 2
        t = d / 24.
        p = self._pose(t)
        if boat is not None:
            p2 = self._pose(t - 2 / 24.)
            swing = .25 * math.sin(t * 2.1) - 2. * (p['pitch'] - p2['pitch'])
            img = boat.draw(img, p['x'], p['y'], p['scale'], p['pitch'], .45, lantern_swing=swing, palette='dawn', facing=p['facing'], f=d,
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
        return img + (self.foam * np.clip(br, 0, 1.2))[..., None] * (rgb('#fff6ea') - img) * .85

    def _xf(self, x, y, f, near=True):
        """plate px -> picture px through the dolly of the near (or far) layer"""
        (zn, dn), (zf, df) = self.cams(f)
        z, d = (zn, dn) if near else (zf, df)
        return self.CX + (x - self.CX) * z + d, self.CY + (y - self.CY) * z

    def actors(self, f):
        out = [dict(a) for a in otteract.actors('s9', f, self.marks(f))]
        if boat is not None:
            p = self._pose((f // 2) * 2 / 24.)
            b = boat.actor(p)
            b['x'], b['y'] = self._xf(b['x'], b['y'], f, False)
            out.append(b)
        return out


def _glow(img, x, y, r, amt, col):
    R = int(r * 7) + 4
    x0, x1, y0, y1 = max(0, int(x - R)), min(W, int(x + R)), max(0, int(y - R)), min(H, int(y + R))
    if x1 <= x0 or y1 <= y0: return img
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(f32)
    q = np.sqrt((xx - x) ** 2 + (yy - y) ** 2) / r
    g = (.55 * np.exp(-(q / 1.1) ** 2) + .3 * np.exp(-(q / 2.4) ** 2)) * amt
    img[y0:y1, x0:x1] = comp.screen(img[y0:y1, x0:x1], g[..., None] * rgb(col))
    return img


def _wall_light(L, glass):
    """the iron lantern wall in shade: sunlight bounced off the floor warms its foot, the paint is weathered"""
    h, w = glass.shape
    ys = np.arange(h, dtype=f32)[:, None]
    gb = np.where(glass.max(0) > .3, h - np.argmax((glass > .3)[::-1], 0), 0).astype(f32)[None]     # glass bottom per column
    below = smooth(gb + 4, gb + 30, ys) * (L[..., 3] > .5)
    foot = h - np.argmax((L[..., 3] > .5)[::-1], 0).astype(f32)[None]
    q = np.clip((ys - gb) / np.maximum(foot - gb, 1), 0, 1)
    tex = fbm(h, w, (90, 30, 9), (1, .5, .3), 61)
    col = L[..., :3] / np.maximum(L[..., 3:], 1e-4)
    col = col * (1 + .045 * tex[..., None] * below[..., None])
    col = col + (below * q ** 1.6 * .16)[..., None] * (rgb('#f0c8a8') - col)
    col = col + (below * (1 - q) ** 3 * .10)[..., None] * (rgb('#3e3656') - col)
    return np.dstack([col * L[..., 3:], L[..., 3:]])


def _over4(a, b):
    """premult a over premult b"""
    return a + b * (1 - a[..., 3:4])


# ================================================================= the gallery: floor, edge, railing, shadows
def gallery(cam, light, seed=5):
    """the gallery floor as a painted texture laid on its plane (flagstones round the lantern), and its outer edge"""
    pal = lh.PAL['dawn']; st = pal['stone']
    S = 300                                    # px per metre in the texture
    M = 6.4
    n = int(M * S)
    r = np.random.default_rng(seed)
    cv = Canvas(n, n, color=rgb(st[4]))
    yy, xx = (np.mgrid[0:n, 0:n].astype(f32) + .5) / S - M / 2
    rad = np.hypot(xx, yy); th = np.arctan2(yy, xx)
    # flagstones: two rings of radial slabs, each its own tone; joints dark, worn edges pale
    lab = np.zeros((n, n), np.int32)
    k = 0
    base = cv.img
    for (r0, r1, nf) in ((1.6, 2.25, 22), (2.25, lh.R_DECK, 30)):
        edges = np.sort(r.uniform(-math.pi, math.pi, nf))
        for i in range(nf):
            a0, a1 = edges[i], edges[(i + 1) % nf] + (2 * math.pi if i == nf - 1 else 0)
            m = (rad >= r0) & (rad < r1) & (((th - a0) % (2 * math.pi)) < (a1 - a0))
            k += 1; lab[m] = k
            base[m] = plants_pick(st, .62 + r.normal(0, .06)) * (1 + r.normal(0, .02, 3).astype(f32))
    # joints
    j = np.zeros((n, n), f32)
    for rr in (1.6, 2.25, lh.R_DECK):
        j = np.maximum(j, np.exp(-((rad - rr) / .012) ** 2))
    gx = cv2.Sobel(lab.astype(f32), cv2.CV_32F, 1, 0); gy = cv2.Sobel(lab.astype(f32), cv2.CV_32F, 0, 1)
    j = np.maximum(j, cv2.GaussianBlur(((np.abs(gx) + np.abs(gy)) > 0).astype(f32), (0, 0), 1.6) * 1.5)
    base[:] = base * (1 - .35 * np.clip(j, 0, 1)[..., None]) + rgb(st[1]) * .35 * np.clip(j, 0, 1)[..., None]
    # weather: salt stains, a damp ring near the rail, lichen
    base[:] = mottle(base, .05, seed + 1, .01, scales=(120, 40, 12))
    wet = smooth(2.55, 2.9, rad) * (.5 + .5 * fbm(n, n, (90, 30), (1, .5), seed + 3))
    base[:] = base * (1 - .18 * wet[..., None]) + rgb('#8d7a98') * .18 * wet[..., None]
    g = repaint(base, (9, 4.5), seed=seed + 4, lab=lab, mask=(lab > 0).astype(f32), thr=(0, .01), density=.9, aspect=3.,
                jit=(.006, .02, .022), op=.6, dry=.25, curve=.3, bristle=.05)
    a = ((rad >= 1.58) & (rad <= lh.R_DECK)).astype(f32)
    a = cv2.GaussianBlur(a, (0, 0), .8)
    tex = np.dstack([g * a[..., None], a])
    p0 = (AT[0] - M / 2, AT[1] - M / 2, ZD)
    L = cam.warp_plane(tex, p0, (1, 0, 0), (0, 1, 0), M, M)
    # the slab's outer edge, seen from just above: a band below the rim, lit by the low sun
    c = Cel(W, H)
    az = np.arange(-180, 181, 2.)
    for a0, a1 in zip(az[:-1], az[1:]):
        q = np.vstack([_ring([a0, a1], lh.R_DECK, ZD), _ring([a1, a0], lh.R_DECK, ZD - .26)])
        zc = cam.cam(q)[..., 2]
        if (zc < .2).any(): continue
        nrm = np.array([math.cos(math.radians(a0 + 1)), math.sin(math.radians(a0 + 1)), 0])
        if (cam.eye - q.mean(0)) @ nrm <= 0: continue
        v = .3 + .55 * max(0., float(nrm @ (light / np.linalg.norm(light))))
        c.fill(cam.project(q)[0], plants_pick(st, v))
    E = c.layer()
    # rim highlight on the slab lip
    return _over4(L, E), E[..., 3]


def plants_pick(pal, v):
    from lp import plants
    return plants.pick(pal, np.array([float(np.clip(v, 0, 1))]))[0]


def railing(cam, light, part='rest'):
    """the iron railing: round posts with ball finials and four rails, drawn as steady ink with a sunlit edge.
    part='lean': only the low rail in front of the otter (drawn under its forearms); 'rest': everything else"""
    pal = lh.PAL['dawn']
    iron, hi = rgb(pal['iron']), mix(rgb(pal['iron_hi']), rgb('#ffe2b8'), .35)
    c = Cel(W, H)
    def seg(a, b, wm, col, alpha=1.):
        s = cam.clip_seg(a, b)
        if s is None: return
        if np.abs(s).max() > 2e4: return
        w = max(.8, float(cam.scale((a + b) / 2)) * wm)
        c.line(s, w, col, (0, 0), .04, tremor=.05, alpha=alpha)
    # rails, far to near
    for zr in lh.Z_RAIL:
        az = np.arange(-180, 181, 1.5)
        P = _ring(az, lh.R_RAIL, AT[2] + zr)
        dd = np.linalg.norm(P - cam.eye, axis=-1)
        o = np.argsort(-dd[:-1])
        for i in o:
            near_otter = zr == lh.Z_RAIL[1] and abs(((az[i] + .75 - OAZ + 180) % 360) - 180) < 14
            if near_otter != (part == 'lean'): continue
            wm = .035 if zr == lh.Z_RAIL[-1] else .022
            seg(P[i], P[i + 1], wm, iron)
            if zr == lh.Z_RAIL[-1]: seg(P[i] + [0, 0, .012], P[i + 1] + [0, 0, .012], .012, hi, .8)
    for az in (np.arange(-180, 180, 10) + 5 if part != 'lean' else []):
        b = _ring(az, lh.R_RAIL, ZD)[0]; t = _ring(az, lh.R_RAIL, AT[2] + lh.Z_RAIL[-1] + .06)[0]
        seg(b, t, .032, iron)
        lv = np.array([math.cos(math.radians(az)), math.sin(math.radians(az)), 0]) @ (light / np.linalg.norm(light))
        if lv > -.2:
            side = np.cross(cam.R[2], [0, 0, 1.]); side /= np.linalg.norm(side) + 1e-9
            sgn = 1 if side @ light > 0 else -1
            seg(b + side * .011 * sgn, t + side * .011 * sgn, .009, hi, .7)
        (x, y), z = cam.project(t)
        if z > .3 and -50 < x < W + 50 and -50 < y < H + 50:
            rr = max(1.5, float(cam.scale(t)) * .03)
            tt = np.linspace(0, 2 * math.pi, 20)
            c.fill(np.c_[x + rr * np.cos(tt), y + rr * np.sin(tt)], iron)
            c.fill(np.c_[x + rr * .45 * np.cos(tt) + rr * .3, y + rr * .45 * np.sin(tt) - rr * .3], hi, .8)
    return c.layer()


def post_shadows(cam, sd):
    """the low sun lays the posts' shadows long across the floor"""
    sh = sd[:2] / np.linalg.norm(sd[:2]); el = math.atan2(sd[2], np.linalg.norm(sd[:2]))
    Ls = min(7., (lh.Z_RAIL[-1] - lh.Z_DECK) / math.tan(max(el, .02)))
    cv = Canvas(H, W, layer=True, color='#000000')
    P = []; WD = []
    for k in range(36):
        az = -math.pi + 2 * math.pi * (k + .5) / 36
        B = np.array([AT[0] + lh.R_RAIL * math.cos(az), AT[1] + lh.R_RAIL * math.sin(az)])
        ss = np.linspace(0, Ls, 80)
        Q = B[None] - sh[None] * ss[:, None]
        rr = np.hypot(Q[:, 0] - AT[0], Q[:, 1] - AT[1])
        ok = (rr > 1.62) & (rr < lh.R_DECK - .03)
        if ok.sum() < 4: continue
        i0 = int(np.argmax(ok)); i1 = i0 + (int(np.argmin(ok[i0:])) if not ok[i0:].all() else len(ok) - i0)
        Q = Q[i0:i1]
        if len(Q) < 4: continue
        idx = np.linspace(0, len(Q) - 1, 6).astype(int)
        S, z = cam.project(np.c_[Q[idx], np.full(6, ZD + .005)])
        if (z < .3).any() or np.abs(S).max() > 2e4: continue
        P.append(S); WD.append(float(cam.f / z.mean()) * .03)
    if P:
        cv.strokes(np.array(P, f32), np.array(WD), np.zeros(3, f32), op=.9, seed=4, shape='flat', bristle=.03)
    return cv2.GaussianBlur(cv.a, (0, 0), 1.0)


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
    fh = cam.R[2][:2] / np.linalg.norm(cam.R[2][:2])
    u, v, t = cam.uv((0, 0, 0), (fh[1], -fh[0], 0), (fh[0], fh[1], 0))
    Y = np.where((t > 0) & np.isfinite(v), np.clip(v, -1e4, 1e4), 1e4).astype(f32)
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
    fh = cam.R[2][:2] / np.linalg.norm(cam.R[2][:2]); rh = np.array([fh[1], -fh[0]])
    Yw = 20 + 1200 * r.uniform(0, 1, n) ** 2.6; Xw = r.uniform(-.9, 1.1, n) * (Yw * .95 + 10)
    P = np.zeros((n, 5, 2), f32); WD = np.zeros(n, f32); C = np.zeros((n, 3), f32); OP = np.zeros(n, f32); keep = np.zeros(n, bool)
    for i in range(n):
        Lw = r.uniform(2, 7) * (1 + Yw[i] / 200)
        lat = Xw[i] + np.linspace(-.5, .5, 5) * Lw
        dep = Yw[i] + np.sin(np.linspace(0, 3, 5) + i) * .2 * (1 + Yw[i] / 150)
        Q = cam.eye[:2] + fh[None] * dep[:, None] + rh[None] * lat[:, None]
        pts, z = cam.project(np.c_[Q, np.zeros(5)])
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
    fh = cam.R[2][:2] / np.linalg.norm(cam.R[2][:2]); rh = np.array([fh[1], -fh[0]])
    sh = sd[:2] / np.linalg.norm(sd[:2])
    a0 = math.atan2(sh @ rh, sh @ fh)
    Yw = 25 + 1600 * r.uniform(0, 1, m) ** 2.4
    Xw = Yw * math.tan(a0) + r.normal(0, 1, m) * (1 + Yw * .09)
    Q = cam.eye[:2] + fh[None] * Yw[:, None] + rh[None] * Xw[:, None]
    P3 = np.c_[Q, np.zeros(m)]
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
    """a reef off the tower foot, low in the frame on the sea side"""
    r = np.random.default_rng(41)
    P = island.prism
    kw = dict(rough=.34, inset=.4, flare=.22, dome=.2)
    out = []
    for (da, d, rx, ry, z1, k) in ((-22, 40, 3.2, 2.0, 1.1, 12), (-17, 44, 2.4, 1.6, .7, 11), (-27, 43, 1.8, 1.2, .5, 10), (-13, 41, 1.6, 1.0, .4, 10),
                                  (-20, 37, 1.2, .8, .3, 9), (-30, 39, 1.0, .6, .2, 9), (-24, 47, 1.3, .8, .3, 9)):
        a = math.radians(YAW + da)
        out.append(P(CAM.eye[0] + d * math.cos(a), CAM.eye[1] + d * math.sin(a), rx, ry, -.08, z1, r, k=k, **kw))
    return out
