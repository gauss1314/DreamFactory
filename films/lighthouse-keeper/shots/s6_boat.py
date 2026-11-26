"""s6  The lost boat.  Mid shot on the open sea: a small fishing boat with a swinging lantern pitches over the swell in
rain and fog; the lighthouse far off is dark; ahead of the boat, rocks show in white water.  2.5 s the horn (the
lantern jerks, the bow lifts); 4.5 s a sea breaks over the bow."""
import math
import numpy as np, cv2
from lp import W, H, comp
from lp.cam import Camera3D
from lp.paint import f32, rgb, smooth, fbm, Canvas
from lp.comp import ease
import sea as SEA, storm as ST, boat as BT

VER = 'v1'
EYE0 = np.array([0., 0., 7.0])
TGT = np.array([3., 60., 1.0])
FOC = 1250.
PUSH = 1.2
TOWER_AT = (-150., 380., 4.)
ROCKS = ((17., 50., 8., 4.2, 51), (26., 58., 5., 2.6, 53), (10., 64., 3.5, 1.6, 55), (31., 70., 4., 1.8, 57))
PAL = dict(deep='#17222b', body='#1c2a33', face='#2f4452', sky_lo='#55606d', foam='#d8e2e6', foam_sh='#7f8c99', thr=(.24, .35, .47))


def cam_at(f, n):
    fwd = (TGT - EYE0) / np.linalg.norm(TGT - EYE0)
    d = PUSH * ease(f / (n - 1.))
    return Camera3D(EYE0 + fwd * d, TGT + fwd * d, FOC), d


class Shot:
    n = 144
    finish = dict(hal_amt=.2, vig=.12)

    def setup(self):
        ev = self.scene.get('events', {})
        self.t_horn = float(ev.get('horn', 2.5)); self.t_hit = float(ev.get('hit', 4.5))
        self.cam0, _ = cam_at(0, self.n)
        c0 = self.cam0
        self.hz = float(c0.project(np.array([0., 1e6, EYE0[2]]))[0][1])
        hz = self.hz
        sk = ST.cached(f'lk_s6_sky_{VER}.npy', lambda: np.dstack(ST.sky_plate(H + 60, W + 200, hz + 30, seed=61)))
        self.sky = sk[..., :3].copy()
        self.sea = SEA.Sea(seed=11, wind=(1., -.35), heading=math.atan2(-.35, 1.), lmax=70., lmin=2.2, steep=.14, n=9, env_amt=.5)
        self.sea.textures()
        import lighthouse as lh
        self.tdepth = float(c0.cam(np.array(TOWER_AT))[2])
        tw = ST.cached(f'lk_s6_tower_{VER}.npy', lambda: lh.paint_tower(c0, 'storm', lamp=0.0, at=TOWER_AT, house=True))
        self.sp_tower = ST.Sprite(tw, self.tdepth)
        rk = ST.cached(f'lk_s6_rocks_{VER}.npy', self._rocks)
        self.sp_rocks = ST.Sprite(rk[..., :4], 55., extra=rk[..., 4])
        self.rain = ST.Rain(H, W, seed=13, dens=.9)
        self.mist = ST.mist_band(H, W, hz + 10, 46, 7, .75)

    def _rocks(self):
        c = self.cam0
        out = np.zeros((H, W, 5), f32)
        from lp.ink import paste
        for (x, y, wd, ht, sd) in ROCKS:
            P = lambda a, z: c.project(np.array([x + a, y, z]))[0]
            r = np.random.default_rng(sd)
            xs = np.linspace(-wd / 2, wd / 2, 9); zt = ht * np.clip(1 - (np.abs(xs) / (wd / 2)) ** 1.5, 0, 1) * r.uniform(.6, 1.1, 9)
            zt[0] = zt[-1] = -1.5
            pts = np.array([P(a, z) for a, z in zip(xs, zt)])
            x0, y0 = int(pts[:, 0].min() - 6), int(pts[:, 1].min() - 6); y1 = int(P(0, -3)[1]) + 4
            L = SEA.rock(int(pts[:, 0].max() - x0 + 12), max(8, y1 - y0), pts - [x0, y0], seed=sd, cell=max(8, int(wd * 4)),
                         pal=('#171a28', '#212538', '#30354b', '#454b63', '#5f6680'))
            dz = float(c.cam(np.array([x, y, 0]))[2])
            sub = np.zeros((H, W, 4), f32); paste(sub, L, x0, y0)
            a = sub[..., 3]
            out[..., :4] = sub + out[..., :4] * (1 - a[..., None])
            out[..., 4] = np.where(a > .5, dz, out[..., 4])
        return out

    # ------------------------------------------------------------------ the boat
    def bow_wave(self, t):
        """the sea that meets the bow at t_hit: travels toward the boat, steep on its face"""
        T = self.t_hit
        amp = float(np.interp(t, [0, T - 1.6, T - .3, T + .1, T + .8, 9], [0, .4, 2.2, 2.4, .5, .1]))
        X, Y, hd = self.boat_xy(T)
        d = np.array([-math.cos(hd), -math.sin(hd)])
        bow = np.array([X, Y]) + np.array([math.cos(hd), math.sin(hd)]) * 3.5
        p = bow - d * 6.0 * (T - t)
        return SEA.ridge(d, p, 6., amp, back=9., front=4., width=10., lean=.35)

    def boat_xy(self, t):
        hd = .30 + .04 * math.sin(t * .7)
        return -9.0 + 1.6 * t, 34. + .5 * t, hd

    def pose(self, t, cam):
        X, Y, hd = self.boat_xy(t)
        rg = [self.bow_wave(t)]
        hf = lambda xs, ys: self.sea.height(xs, ys, t, rg)[:, 0] * self.gain(t)
        P = BT.place(cam, X, Y, hd, hf, L=9.0, beam=3.2, freeboard=.15)
        # the horn: a jolt, the bow lifts
        k = t - self.t_horn
        if k >= 0: P['pitch'] += .07 * math.exp(-k / .5) * math.sin(min(k / .25, 1) * math.pi / 2)
        return P, hf

    def gain(self, t):
        return .9 + .08 * math.sin(t * .4)

    def swing(self, t, cam):
        """the lantern: a pendulum pushed by the boat's pitching and by the horn"""
        p0 = self.pose(t, cam)[0]['pitch']; p1 = self.pose(t - .2, cam)[0]['pitch']; p2 = self.pose(t - .4, cam)[0]['pitch']
        acc = (p0 - 2 * p1 + p2) / .04
        s = -.55 * (p0 - p1) / .2 - .05 * acc + .12 * math.sin(t * 2.9 + .4)
        k = t - self.t_horn
        if k >= 0: s += .45 * math.exp(-k / .7) * math.sin(k * 7.5)
        return float(np.clip(s, -.8, .8))

    # ------------------------------------------------------------------ frame
    def frame(self, f):
        t = f / 24.
        cam, d = cam_at(f, self.n)
        M = np.float32([[1, 0, 100 - 10 * t], [0, 1, 30]])
        img = cv2.warpAffine(self.sky, M, (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT_101)
        g = self.gain(t)
        A0 = self.sea.A.copy(); self.sea.A = A0 * g
        rg = [self.bow_wave(t)]
        G = self.sea.render(cam, t, ridges=rg, h=H // 2, w=W // 2)
        sc, Ms, info = self.sea.paint(G, cam, t, PAL, light=(-.5, .4, .75), fog_col='#58606f', fog_k=(.012, .9))
        self.sea.A = A0
        zfull = cv2.resize(G['z'], (W, H), interpolation=cv2.INTER_NEAREST)
        img = img * (1 - Ms[..., None]) + sc * Ms[..., None]
        # the dark lighthouse far away in the murk
        R = self.sp_tower.roi(d, cam.cx, cam.cy)
        if R is not None:
            X0, Y0, L, _ = R; hh, ww = L.shape[:2]; zr = zfull[Y0:Y0 + hh, X0:X0 + ww]
            L = L * ((zr <= 0) | (zr > self.tdepth - 20)).astype(f32)[..., None]
            k = .45
            L[..., :3] = L[..., :3] * (1 - k) + rgb('#4f5767') * k * L[..., 3:4]
            img[Y0:Y0 + hh, X0:X0 + ww] = ST.over(img[Y0:Y0 + hh, X0:X0 + ww], L)
        img = img + (rgb('#5b6271') - img) * (self.mist * .8)[..., None]
        # rocks ahead in white water
        R = self.sp_rocks.roi(d, cam.cx, cam.cy)
        if R is not None:
            X0, Y0, L, rd = R; hh, ww = L.shape[:2]; zr = zfull[Y0:Y0 + hh, X0:X0 + ww]
            vis = ((zr <= 0) | (zr > rd - 1.5)).astype(f32)
            L = L * vis[..., None]
            L[..., :3] = L[..., :3] * .82 + rgb('#4a5262') * .18 * L[..., 3:4]
            sub = ST.over(img[Y0:Y0 + hh, X0:X0 + ww], L)
            img[Y0:Y0 + hh, X0:X0 + ww] = SEA.surf(sub, L[..., 3], vis, f, seed=5, up=9, down=12, amt=1.0, swell=1.3)
        # the boat
        P, hf = self.pose(t, cam)
        sw = self.swing(t, cam)
        fd = (f // 2) * 2
        img = BT.draw(img, P['x'], P['y'], P['scale'], P['pitch'], P['roll'], lantern_swing=sw, palette='storm', facing=P['facing'],
                      f=fd, fore=P['fore'], lamp=1.0, wet=.3)
        # wash along the waterline and the sea over the bow
        cvs = Canvas(H, W, layer=True)
        self._wash(cvs, P, f)
        age = fd / 24. - self.t_hit
        if age >= 0:
            bx, by = P['bow_px']
            mist = np.zeros((H, W), f32)
            SEA.burst(cvs, bx - 10 * P['facing'], by + 6, 150, age, seed=63, wind=(.5, 0), life=1.3, n=46, mist=mist)
            img = img + (rgb('#aab5c0') - img) * (mist * .7)[..., None]
        SEA.crest_spray(cvs, info['foam'], G, f, wind=(1., -.1), n=120, seed=6, scale=.6)
        img = ST.over(img, cvs.layer())
        # rain
        cur = self.rain.curtains(f)
        veil = cur * smooth(self.hz - 400, self.hz + 60, np.arange(H, dtype=f32)[:, None])
        img = img + (rgb('#77818f') - img) * (veil * .2)[..., None]
        rs = self.rain.streaks(f)
        img = img + (rgb('#a8b6c4') * .75 - img) * (rs * .75)[..., None]
        return np.clip(img, 0, 1.3).astype(f32)

    def _wash(self, cvs, P, f):
        """white water curling along the hull at the waterline, heavier at the bow"""
        r = np.random.default_rng(700 + f // 2)
        n = 26
        u = r.uniform(-.48, .5, n)
        s = P['scale'] * P['fore']
        c, si = math.cos(P['pitch']), math.sin(P['pitch'])
        x = P['x'] + P['facing'] * u * c * s
        y = P['y'] - u * si * s + r.uniform(-.01, .02, n) * P['scale']
        L = P['scale'] * r.uniform(.04, .12, n) * (1 + 1.2 * np.clip(u, 0, 1))
        from lp.paint import arcs
        Pp = arcs(x, y, -P['facing'] * 0 + r.normal(0, .15, n) + (math.pi if P['facing'] < 0 else 0) - P['pitch'] * P['facing'], L, r.normal(0, .5, n), K=5)
        cvs.strokes(Pp, P['scale'] * r.uniform(.005, .014, n), np.broadcast_to(rgb('#cdd7dd'), (n, 3)), op=r.uniform(.5, .95, n), dry=r.uniform(.2, .7, n), seed=f // 2, shape='round', bristle=.05)

    def actors(self, f):
        t = f / 24.
        cam, d = cam_at(f, self.n)
        P, _ = self.pose(t, cam)
        return [BT.actor(P)]
