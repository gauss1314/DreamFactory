"""s8  The beam.  The widest image of the film: from above and behind the lantern, the relit beam sweeps out over
the storm sea and cuts the rain.  2.0 s the other beam swings across the lens (a flare); 4.0 s the far boat puts its
helm over, its lantern swings, its wake bends in a white arc away from the reef; the overcast begins to tear and a
road of moonlight opens on the sea."""
import math
import numpy as np, cv2
from lp import W, H, comp
from lp.cam import Camera3D
from lp.paint import f32, rgb, smooth, fbm, Canvas, arcs
from lp.comp import ease
import sea as SEA, storm as ST, boat as BT

VER = 'v4'
AT = (0., 0., 8.)                    # lighthouse foot (island top)
EYE0 = np.array([-5.5, -15.0, 32.0])
TGT = np.array([30., 300., -34.])
FOC = 1120.
PUSH = 1.0
BOAT0 = np.array([-14., 122.])
REEF = ((-26., 160., 9., 3.2, 81), (-13., 170., 5., 2.0, 83), (-38., 172., 4., 1.4, 85))
MOON_PX = (640., 120.)
PAL = dict(deep='#15212a', body='#1c2a33', face='#2f4452', sky_lo='#56616e', foam='#d8e2e6', foam_sh='#7f8c99', beam='#fff2d0', thr=(.24, .35, .47))


def cam_at(f, n):
    fwd = (TGT - EYE0) / np.linalg.norm(TGT - EYE0)
    d = PUSH * ease(f / (n - 1.))
    return Camera3D(EYE0 + fwd * d, TGT + fwd * d, FOC), d


class Shot:
    n = 192
    finish = dict(hal_amt=.24, vig=.12)

    def setup(self):
        import lighthouse as lh
        self.lh = lh
        ev = self.scene.get('events', {})
        self.t_sweep = float(ev.get('sweep', 2.0)); self.t_turn = float(ev.get('turn', 4.0))
        self.cam0, _ = cam_at(0, self.n)
        c0 = self.cam0
        self.hz = float(c0.project(c0.eye + np.array([0., 1e6, 0.]))[0][1])
        hz = self.hz
        sk = ST.cached(f'lk_s8_sky_{VER}.npy', lambda: np.dstack(ST.sky_plate(H + 60, W + 160, hz + 30, seed=81, break_x=MOON_PX[0] + 80)))
        self.sky = sk[..., :3].copy(); self.cov = sk[..., 3].copy()
        self.open = ST.cached(f'lk_s8_open_{VER}.npy', self._open_sky)
        self.sea = SEA.Sea(seed=19, wind=(1., -.35), heading=math.atan2(-.35, 1.), lmax=80., lmin=3.0, steep=.15, n=9, env_amt=.75, group=2.4)
        self.sea.textures()
        self.lamp = lh.lamp_world(AT)
        dz = float(c0.cam(self.lamp)[2]); self.tdepth = dz
        tw = ST.cached(f'lk_s8_tower_{VER}.npy', lambda: lh.paint_tower(c0, 'storm', lamp=1.0, at=AT, house=False, rail='all'))
        self.sp_tower = ST.Sprite(tw, dz)
        rk = ST.cached(f'lk_s8_reef_{VER}.npy', self._reef)
        self.sp_reef = ST.Sprite(rk[..., :4], 160., extra=rk[..., 4])
        self.rain = ST.Rain(H, W, seed=17, dens=.8, speed=.9)
        self.mist = ST.mist_band(H, W, hz + 14, 40, 9, .6)
        az_cam = math.atan2(EYE0[1] - self.lamp[1], EYE0[0] - self.lamp[0])
        self.az0 = az_cam - 2 * math.pi * self.t_sweep / lh.BEAM_PERIOD
        # moon direction: the ray through MOON_PX
        d = np.array([(MOON_PX[0] - c0.cx) / c0.f, (MOON_PX[1] + 30 - c0.cy) / c0.f, 1.]) @ c0.R
        self.moon = d / np.linalg.norm(d)

    def _open_sky(self):
        """the sky behind the tear: paler overcast edges lit by the moon, the moon itself behind thin cloud"""
        h, w = H + 60, W + 160
        x, y = np.meshgrid(np.arange(w, dtype=f32), np.arange(h, dtype=f32))
        mx, my = MOON_PX[0] + 80, MOON_PX[1] + 30
        d = np.sqrt((x - mx) ** 2 + (y - my) ** 2)
        base = np.broadcast_to(rgb('#454a5c'), (h, w, 3)).copy()
        base += (rgb('#7a8098') - base) * np.exp(-d / 420.)[..., None] * .8
        base += (rgb('#b9c0d8') - base) * np.exp(-(d / 130.) ** 1.5)[..., None] * .7
        # thin moonlit cloud streaks across the gap
        from lp.paint import repaint
        ang = np.full((h, w), -.08, f32) + fbm(h, w, (200,), None, 3) * .05
        out = repaint(base, (30, 12), seed=8, angle=ang, thr=(0, .004), density=.9, aspect=7., jit=(.003, .01, .02), op=.6, dry=.3, curve=.1)
        cv = Canvas(h, w, img=out)
        r = np.random.default_rng(4)
        n = 40
        xs = r.uniform(mx - 700, mx + 900, n); ys = my + r.normal(0, 90, n)
        P = arcs(xs, ys, r.normal(-.06, .03, n), r.uniform(80, 340, n), r.normal(0, .1, n), K=7)
        col = np.clip(rgb('#8c90a0') * r.uniform(.85, 1.1, (n, 1)), 0, 1)
        cv.strokes(P, r.uniform(2, 7, n), col.astype(f32), op=r.uniform(.2, .6, n), dry=.4, seed=3, shape='round', bristle=.03)
        disc = np.clip((24 - d) / 1.5, 0, 1)
        o = cv.img + (rgb('#eef0ff') - cv.img) * disc[..., None]
        return o

    def _reef(self):
        c = self.cam0
        out = np.zeros((H, W, 5), f32)
        from lp.ink import paste
        for (x, y, wd, ht, sd) in REEF:
            P = lambda a, z: c.project(np.array([x + a, y, z]))[0]
            r = np.random.default_rng(sd)
            xs = np.sort(r.uniform(-wd / 2, wd / 2, 13)); xs[0], xs[-1] = -wd / 2, wd / 2; zt = ht * np.clip(1 - np.abs(xs / (wd / 2)) ** 2.6, 0, 1) ** .55 * r.uniform(.7, 1.05, 13)
            zt[0] = zt[-1] = -1.5
            pts = np.array([P(a, z) for a, z in zip(xs, zt)])
            x0, y0 = int(pts[:, 0].min() - 6), int(pts[:, 1].min() - 6); y1 = int(P(0, -3)[1]) + 4
            L = SEA.rock(int(pts[:, 0].max() - x0 + 12), max(8, y1 - y0), pts - [x0, y0], seed=sd, cell=8,
                         pal=('#181b29', '#23273a', '#33384e', '#4a5068', '#666c86'))
            dz = float(c.cam(np.array([x, y, 0]))[2])
            sub = np.zeros((H, W, 4), f32); paste(sub, L, x0, y0)
            a = sub[..., 3]
            out[..., :4] = sub + out[..., :4] * (1 - a[..., None])
            out[..., 4] = np.where(a > .5, dz, out[..., 4])
        return out

    # ------------------------------------------------------------------ the boat's course
    def boat_state(self, t):
        """heading toward the reef, then helm over at t_turn: a smooth turn to starboard (away)"""
        T = self.t_turn
        h0 = math.radians(78); h1 = math.radians(-20)
        k = ease(np.clip((t - T) / 2.6, 0, 1)) if t > T else 0.
        k = float(k)
        # integrate the path analytically enough: sample
        sp = 4.6
        ts = np.linspace(0, t, max(2, int(t * 12) + 2))
        hs = np.array([h0 + (h1 - h0) * float(ease(np.clip((q - T) / 2.6, 0, 1))) * (q > T) for q in ts])
        dt = ts[1] - ts[0]
        xs = BOAT0[0] + np.concatenate([[0], np.cumsum(np.cos(hs[:-1]) * sp * dt)])
        ys = BOAT0[1] + np.concatenate([[0], np.cumsum(np.sin(hs[:-1]) * sp * dt)])
        return xs, ys, hs

    def cloud_open(self, t):
        return float(ease(np.clip((t - 2.6) / 5.0, 0, 1)))

    # ------------------------------------------------------------------ frame
    def frame(self, f):
        t = f / 24.
        cam, d = cam_at(f, self.n)
        lh = self.lh
        # sky, and the tear opening around the moon
        M = np.float32([[1, 0, 80 - 9 * t], [0, 1, 30]])
        img = cv2.warpAffine(self.sky, M, (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT_101)
        op = self.cloud_open(t)
        if op > 0:
            Mo = np.float32([[1, 0, 80], [0, 1, 30]])
            o = cv2.warpAffine(self.open, Mo, (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT_101)
            cov = cv2.warpAffine(self.cov, M, (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT_101)
            mq = self._tear(op)
            m = cv2.resize(mq, (W, H), interpolation=cv2.INTER_LINEAR)
            img = img * (1 - m[..., None]) + o * m[..., None]
            # cloud edges at the tear take the moon
            edge = cv2.resize(np.clip(cv2.GaussianBlur(mq, (0, 0), 4.5) - mq, 0, 1), (W, H), interpolation=cv2.INTER_LINEAR) * 1.2 * cov
            img = img + (rgb('#a9b2d4') - img) * np.clip(edge * op, 0, .35)[..., None]
        # sea
        az = lh.beam_az(t, self.az0)
        dirs = ST.beam_dirs(az)
        G = self.sea.render(cam, t, h=H // 2, w=W // 2, s1=2600.)
        bs = SEA.beam_on_surface(G, self.lamp, dirs, half=.03, reach=500., amt=1.0)
        sc, Ms, info = self.sea.paint(G, cam, t, PAL, light=(-.5, .4, .75), beam=bs, fog_col='#5a6272', fog_k=(.0032, .85))
        img = img * (1 - Ms[..., None]) + sc * Ms[..., None]
        zfull = cv2.resize(G['z'], (W, H), interpolation=cv2.INTER_NEAREST)
        # moon road on the sea
        if op > 0:
            img = self._moon_road(img, G, cam, op)
        img = img + (rgb('#606878') - img) * (self.mist * .75)[..., None]
        # reef in white water
        R = self.sp_reef.roi(d, cam.cx, cam.cy)
        if R is not None:
            X0, Y0, L, rd = R; hh, ww = L.shape[:2]; zr = zfull[Y0:Y0 + hh, X0:X0 + ww]
            vis = ((zr <= 0) | (zr > rd - 2.0)).astype(f32)
            L = L * vis[..., None]
            L[..., :3] = L[..., :3] * .7 + rgb('#4c5464') * .3 * L[..., 3:4]
            sub = ST.over(img[Y0:Y0 + hh, X0:X0 + ww], L)
            img[Y0:Y0 + hh, X0:X0 + ww] = SEA.surf(sub, L[..., 3], vis, f, seed=8, up=4, down=5, amt=1.0, swell=1.0)
        # the boat and its wake
        img = self._boat(img, cam, t, f)
        # volumetric beams through the rain
        B = ST.beam_volume(cam, self.lamp, dirs, depth=np.where(zfull > 0, zfull, 0), t=t, reach=380., amt=.9, half=.012, r0=.75)
        cur = self.rain.curtains(f)
        img = comp.screen(img, (B * (.8 + .35 * cur))[..., None] * rgb('#fff2d0'))
        # the tower: lantern and gallery right under us
        R = self.sp_tower.roi(d, cam.cx, cam.cy)
        if R is not None:
            X0, Y0, L, _ = R; hh, ww = L.shape[:2]
            img[Y0:Y0 + hh, X0:X0 + ww] = ST.over(img[Y0:Y0 + hh, X0:X0 + ww], L)
        img = lh.lamp_glow(img, cam, AT, amt=1.0, col='#ffc070')
        # rain, lit in the beams
        rs = self.rain.streaks(f)
        lit = .5 + 2.4 * np.clip(B, 0, 1)
        img = img + (rgb('#a8b6c4') * np.clip(lit, 0, 2.2)[..., None] * .8 - img) * (rs * .7)[..., None]
        # the other beam across the lens
        fa = self.flare_amt(t)
        if fa > 0:
            lx, ly = lh.lamp_px(cam, AT)
            img = ST.flare(img, lx, ly, fa)
        return np.clip(img, 0, 1.5).astype(f32)

    def flare_amt(self, t):
        k = t - self.t_sweep
        if k < -1.5 / 24: return 0.
        if k < 0: return .3
        return float(math.exp(-k / .12))

    def _tear(self, op):
        h, w = H // 4, W // 4
        if not hasattr(self, '_tn'):
            x, y = np.meshgrid(np.arange(w, dtype=f32), np.arange(h, dtype=f32))
            # a long diagonal rift through the moon, ragged
            x = x * 4; y = y * 4
            mx, my = MOON_PX
            u = (x - mx) * math.cos(-.12) + (y - my) * math.sin(-.12)
            v = -(x - mx) * math.sin(-.12) + (y - my) * math.cos(-.12)
            n = fbm(h, w, (30, 10, 3.5), (1, .5, .25), 31)
            self._tn = (np.abs(v + 40 * np.sin(u / 260.)) / 85. + (np.abs(u) / 700.) ** 2 + n * .25).astype(f32)
        lim = self.hz - 20
        m = smooth(1.6 * op + .05, 1.6 * op - .25, self._tn) * smooth(lim, lim - 120, np.arange(h, dtype=f32)[:, None] * 4)
        return cv2.GaussianBlur(m.astype(f32), (0, 0), 1.25)

    def _moon_road(self, img, G, cam, op):
        nx, ny, nz = G['nx'], G['ny'], G['nz']
        h, w = nx.shape
        sc = w / cam.w
        y, x = np.mgrid[0:h, 0:w].astype(f32)
        d = np.stack([(x - cam.cx * sc) / (cam.f * sc), (y - cam.cy * sc) / (cam.f * sc), np.ones_like(x)], -1) @ cam.R.astype(f32)
        d /= np.linalg.norm(d, axis=-1, keepdims=True)
        dn = d[..., 0] * nx + d[..., 1] * ny + d[..., 2] * nz
        rx, ry, rz = d[..., 0] - 2 * dn * nx, d[..., 1] - 2 * dn * ny, d[..., 2] - 2 * dn * nz
        m = self.moon.astype(f32)
        s = np.clip(rx * m[0] + ry * m[1] + rz * m[2], 0, 1)
        g = smooth(.985, .998, s) * (G['z'] > 0)
        g = cv2.GaussianBlur(cv2.resize(g.astype(f32), (W, H), interpolation=cv2.INTER_LINEAR), (0, 0), 1.6)
        return img + (rgb('#cfd8ff') - img) * np.clip(g * op * .6, 0, 1)[..., None]

    def _boat(self, img, cam, t, f):
        xs, ys, hs = self.boat_state(t)
        X, Y, hd = xs[-1], ys[-1], hs[-1]
        hf = lambda a, b: self.sea.height(a, b, t)[:, 0]
        P = BT.place(cam, X, Y, hd, hf, L=9., beam=3.2, freeboard=.15)
        self._pose = P
        # wake: the last ~6 s of the path as a white trail, widening and fading behind the stern
        n = len(xs)
        k0 = max(0, n - 80)
        tr = np.stack([xs[k0:], ys[k0:], np.zeros(n - k0)], -1)
        tr[:, :2] -= np.stack([np.cos(hs[k0:]), np.sin(hs[k0:])], -1) * 3.8
        tr[:, 2] = hf(tr[:, 0], tr[:, 1]) + .1
        pts, z = cam.project(tr)
        age = (np.arange(n - k0)[::-1]) / 12.
        cvs = Canvas(H, W, layer=True)
        sc = float(cam.scale(np.array([X, Y, 0.])))
        if len(pts) > 3:
            turn = abs(hs[-1] - hs[0])
            for j in range(3):
                off = (j - 1) * .9
                q = pts + np.stack([-np.sin(hs[k0:]), np.cos(hs[k0:])], -1) * 0
                wd = sc * (1.0 + age * .7) * (1.0 if j == 1 else .6)
                for i in range(0, len(q) - 2, 2):
                    seg = q[i:i + 5]
                    if len(seg) < 3: continue
                    o = np.clip(1 - age[i] / 6.0, 0, 1) ** .7 * (.95 if j == 1 else .6)
                    if o <= .02: continue
                    side = np.array([[-(seg[-1, 1] - seg[0, 1]), seg[-1, 0] - seg[0, 0]]]) / (np.hypot(*(seg[-1] - seg[0])) + 1e-6)
                    cvs.strokes((seg + side * off * wd[i] * .8)[None], float(wd[i] * .45), rgb('#cfd8de')[None], op=o, dry=.5, seed=i + j * 99, shape='round', bristle=.06)
        img = ST.over(img, cvs.layer())
        k = t - self.t_turn
        sw = .15 * math.sin(t * 2.6) + (.5 * math.exp(-k / .8) * math.sin(k * 6.5) if k >= 0 else 0)
        fd = (f // 2) * 2
        img = BT.draw(img, P['x'], P['y'], P['scale'], P['pitch'], P['roll'] + (.12 * math.sin(min(max(k, 0), 1.5) * 2.1) if k > 0 else 0),
                      lantern_swing=sw, palette='storm', facing=P['facing'], f=fd, fore=P['fore'], lamp=1.0)
        return img

    def actors(self, f):
        t = f / 24.
        cam, d = cam_at(f, self.n)
        xs, ys, hs = self.boat_state(t)
        hf = lambda a, b: self.sea.height(a, b, t)[:, 0]
        P = BT.place(cam, xs[-1], ys[-1], hs[-1], hf)
        return [BT.actor(P)]
