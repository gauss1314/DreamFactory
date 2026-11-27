"""s4  The storm comes.  Low on the rocks below the lighthouse island: the storm deck presses in over the sea, rain
slants down, the swell builds; at 3.5 s a forked bolt lights clouds, waves and tower for a few frames; a big wave
gathers (it rises from 3 s) and smashes on the near rock at 5.5 s.  The beam turns through the rain the whole time."""
import math
import numpy as np, cv2
from lp import W, H, comp
from lp.cam import Camera3D
from lp.paint import f32, rgb, smooth, fbm, Canvas
from lp.comp import ease
import sea as SEA, storm as ST

VER = 'v5'
EYE0 = np.array([0., 0., 4.0])
TGT = np.array([8., 120., 13.])
FOC = 1250.
PUSH = 1.6                  # metres of dolly over the shot
ISLAND = (52., 150., 0.)    # island foot (world); the tower stands on its top
ISLE_TOP = 7.5
HIT = np.array([-1.0, 12.0])  # where the big wave meets the near rock (world xy)
WAVE_DIR = np.array([.16, -1.])
PAL = dict(deep='#16212a', body='#1c2a33', face='#2f4452', sky_lo='#58626f', foam='#d8e2e6', foam_sh='#7d8a97', beam='#fff2d0',
           thr=(.24, .35, .47))


def cam_at(f, n):
    fwd = (TGT - EYE0) / np.linalg.norm(TGT - EYE0)
    d = PUSH * ease(f / (n - 1.)) if n > 1 else 0.
    return Camera3D(EYE0 + fwd * d, TGT + fwd * d, FOC), d


class Shot:
    n = 192
    finish = dict(hal_amt=.2, vig=.12)

    def setup(self):
        ev = self.scene.get('events', {})
        self.t_bolt = float(ev.get('lightning', 3.5)); self.t_crash = float(ev.get('crash', 5.5))
        self.cam0, _ = cam_at(0, self.n)
        c0 = self.cam0
        self.hz = float(c0.project(np.array([0., 1e6, EYE0[2]]))[0][1])
        hz = self.hz
        self.sky, self.cov = (lambda a: (a[..., :3].copy(), a[..., 3].copy()))(ST.cached(f'lk_s4_sky_{VER}.npy', lambda: np.dstack(ST.sky_plate(H + 80, W + 260, hz + 40, seed=41))))
        self.sea = SEA.Sea(seed=7, wind=(1., -.35), heading=math.atan2(-1, .25), lmax=80., lmin=2.4, steep=.15, n=9, env_amt=.5)
        self.sea.textures()
        import lighthouse as lh
        self.lh = lh
        at = (ISLAND[0], ISLAND[1], ISLE_TOP)
        self.at = at
        self.tower = ST.cached(f'lk_s4_tower_{VER}.npy', lambda: lh.paint_tower(c0, 'storm', lamp=1.0, at=at, house=True))
        self.tdepth = float(c0.cam(np.array(at))[2])
        self.isle = ST.cached(f'lk_s4_isle_{VER}.npy', self._isle)
        self.rocks = ST.cached(f'lk_s4_rock_{VER}.npy', self._fg_rock)
        self.mid = ST.cached(f'lk_s4_mid_{VER}.npy', self._mid_rocks)
        self.rain = ST.Rain(H, W, seed=9, dens=1.0)
        tw = self.tower; il = self.isle
        self.sp_isle = ST.Sprite(tw + il * (1 - tw[..., 3:4]), self.tdepth, extra=il[..., 3])
        self.sp_mid = ST.Sprite(self.mid[..., :4], 80., extra=self.mid[..., 4])
        self.sp_rock = ST.Sprite(self.rocks, 9.)
        del self.tower, self.isle, self.mid, self.rocks
        self.mist = ST.mist_band(H, W, hz + 8, 30, 5, .55)
        self.bolt = ST.bolt(620, 120, 790, hz - 70, seed=12, depth=7, branch=.8) + ST.bolt(700, 260, 1040, 330, seed=15, depth=6, branch=.5)[:3]

    # ------------------------------------------------------------------ plates
    def _isle(self):
        c = self.cam0
        P = lambda x, y, z: c.project(np.array([x, y, z]))[0]
        r = np.random.default_rng(3)
        xs = np.linspace(-22, 30, 15)
        zt = ISLE_TOP * np.clip(1 - (np.abs(xs - 2) / 26) ** 2.2, 0, 1) + r.uniform(-.6, .6, 15)
        zt[0] = zt[-1] = -1.0
        pts = np.array([P(ISLAND[0] + x, ISLAND[1], z) for x, z in zip(xs, zt)])
        x0, y0 = int(pts[:, 0].min() - 10), int(pts[:, 1].min() - 10)
        y1 = int(P(ISLAND[0], ISLAND[1], -3)[1]) + 6
        L = SEA.rock(int(pts[:, 0].max() - x0 + 20), y1 - y0, pts - [x0, y0], seed=5, cell=14,
                     pal=('#1b1e2c', '#262a3c', '#353a50', '#4b5068', '#666c86'))
        out = np.zeros((H, W, 4), f32)
        from lp.ink import paste
        paste(out, L, x0, y0)
        return out

    def _fg_rock(self):
        """the ledge the camera stands on (bottom left) and a low rock bottom right"""
        out = np.zeros((H, W, 4), f32)
        from lp.ink import paste
        top = np.array([[-20, 300], [80, 250], [210, 232], [330, 262], [420, 250], [560, 290], [690, 300], [800, 322], [900, 350], [980, 382], [1060, 432], [1120, 500], [1160, 560]], float)
        L = SEA.rock(1180, 560, top, seed=11, cell=110, pal=('#161925', '#202435', '#2e3348', '#43495f', '#5f6680'))
        paste(out, L, 0, H - 560 + 30)
        top2 = np.array([[0, 140], [60, 96], [150, 80], [250, 70], [330, 92], [420, 130], [480, 170]], float)
        L2 = SEA.rock(480, 200, top2, seed=17, cell=70, pal=('#171a27', '#222638', '#30354a', '#454b62', '#626983'))
        paste(out, L2, W - 470, H - 160)
        return out

    def _mid_rocks(self):
        c = self.cam0
        out = np.zeros((H, W, 5), f32)
        from lp.ink import paste
        for k, (x, y, wd, ht, sd) in enumerate(((-34., 62., 9., 3.2, 21), (21., 88., 6., 2.2, 23), (-9., 118., 4., 1.4, 25))):
            P = lambda a, z: c.project(np.array([x + a, y, z]))[0]
            r = np.random.default_rng(sd)
            xs = np.sort(r.uniform(-wd / 2, wd / 2, 13)); xs[0], xs[-1] = -wd / 2, wd / 2; zt = ht * np.clip(1 - np.abs(xs / (wd / 2)) ** 2.6, 0, 1) ** .55 * r.uniform(.7, 1.05, 13)
            zt[0] = zt[-1] = -1.5
            pts = np.array([P(a, z) for a, z in zip(xs, zt)])
            x0, y0 = int(pts[:, 0].min() - 6), int(pts[:, 1].min() - 6); y1 = int(P(0, -3)[1]) + 4
            L = SEA.rock(int(pts[:, 0].max() - x0 + 12), max(8, y1 - y0), pts - [x0, y0], seed=sd, cell=max(8, int(wd * 3)),
                         pal=('#181b29', '#23273a', '#33384e', '#4a5068', '#666c86'))
            dz = float(c.cam(np.array([x, y, 0]))[2])
            sub = np.zeros((H, W, 4), f32); paste(sub, L, x0, y0)
            a = sub[..., 3]
            out[..., :4] = sub + out[..., :4] * (1 - a[..., None])
            out[..., 4] = np.where(a > .5, dz, out[..., 4])
        return out

    def _runup(self, img, rka, age, Pw, k):
        """white water running up the ledge from the impact, then draining back down in streaks; the rock stays wet"""
        Ix, Iy = Pw((1110, 1110))
        x0, y0 = int(max(0, Ix - 900 * k)), int(max(0, Iy - 700 * k))
        sub = img[y0:, x0:int(min(W, Ix + 80))]
        A = rka[y0:, x0:x0 + sub.shape[1]]
        if A.max() < .1: return img
        hh, ww = A.shape
        yy, xx = np.mgrid[y0:y0 + hh, x0:x0 + ww].astype(f32)
        u = ((xx - Ix) * -.82 + (yy - Iy) * -.57) / k                  # metres-ish up the slope, in sprite px
        dtop = cv2.distanceTransform((A > .5).astype(np.uint8), cv2.DIST_L2, 3).astype(f32) / k
        if not hasattr(self, '_caps2'):
            self._caps2 = np.clip(fbm(256, 256, (24, 9, 3.5), (1, .6, .35), 78) * .5 + .5, 0, 1).astype(f32)
        if not hasattr(self, '_streak'):
            self._streak = np.clip(fbm(512, 512, (60, 6, 2.5), (1, .6, .4), 77, aspect=.08) * .5 + .5, 0, 1).astype(f32)
        front = 520 * (1 - math.exp(-age / .16))
        reach = 520.
        lead = smooth(front + 40, front - 30, u) * (u > -80)
        surf = smooth(110, 25, dtop)
        n = self._caps2[(yy.astype(int) // 3) % 256, (xx.astype(int) // 3) % 256]
        wash = A * lead * surf * float(np.clip(1.1 - age / .9, 0, 1)) * (.55 + .6 * n)
        wet = A * smooth(reach + 20, reach - 60, u) * (u > -90) * smooth(170, 40, dtop) * float(min(1, age / .3))
        # the wet rock: darker, with a cold sheen on the upper planes
        dry = float(np.clip(1 - (age - 1.2) / 4.0, .55, 1))
        sub *= (1 - .22 * wet * dry)[..., None]
        sheen = wet * smooth(.62, .8, n) * smooth(60, 10, dtop) * dry
        sub += (rgb('#8e9bb0') - sub) * (sheen * .5)[..., None]
        # water draining back in thin streaks
        if age > .35:
            ds = self._streak[((yy.astype(int) - int(age * 420)) // 3) % 512, (xx.astype(int) * 2) % 512]
            drain = cv2.GaussianBlur(wet * smooth(.62, .75, ds), (0, 0), 1.0) * float(np.clip(1.2 - (age - .35) / 2.2, 0, 1))
            sub += (rgb('#aebbc6') - sub) * (drain * .45)[..., None]
        c = rgb('#dfe7ea') * (1 - .3 * smooth(.3, .9, wash)[..., None]) + rgb('#9fb0bc') * .3 * smooth(.3, .9, wash)[..., None]
        sub += (c - sub) * smooth(.25, .55, wash)[..., None]
        return img

    # ------------------------------------------------------------------ timing
    def flash(self, f):
        e = int(round(self.t_bolt * 24))
        k = f - e
        return {0: 1.0, 1: .55, 2: .95, 3: .4, 4: .18, 5: .06}.get(k, 0.)

    def big_wave(self, t):
        """the set wave that builds and breaks on the rock: amplitude keys (s, m), with a lean that steepens it"""
        T = self.t_crash
        amp = float(np.interp(t, [0, T - 3.2, T - 1.6, T - .5, T - .1, T + .35, T + .9, T + 1.7, 9], [.0, 1.0, 4.0, 9.0, 9.4, 4.5, 1.8, .7, .3]))
        lean = float(np.interp(t, [0, T - 1.5, T - .3, T], [.1, .25, .55, .75]))
        d = WAVE_DIR / np.linalg.norm(WAVE_DIR)
        p = HIT - d * 8.5 * (T - t) - d * 3.0
        return SEA.ridge(d, p, 8.5, amp, back=16., front=6.5 - 2.5 * min(1, max(0, (t - T + 1.5) / 1.5)), width=44., lean=lean)

    # ------------------------------------------------------------------ frame
    def frame(self, f):
        t = f / 24.
        cam, d = cam_at(f, self.n)
        fl = self.flash(f)
        # sky: the deck drifts downwind and swells toward us
        z = 1 + .045 * t / 8
        ox = 130 - 14 * t
        M = np.float32([[1 / z, 0, ox + (W / 2) * (1 - 1 / z)], [0, 1 / z, 40 + self.hz * (1 - 1 / z)]])
        img = cv2.warpAffine(self.sky, M, (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT_101)
        cov = cv2.warpAffine(self.cov, M, (W, H), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_REFLECT_101)
        if fl > 0:
            g = comp.radial(740, 330, 1700, 1000, 1.1)
            # cloud undersides near the bolt flare cold-white, the far deck less
            under = np.clip(cov, 0, 1) * (.35 + .65 * g)
            img = img + (rgb('#d6e0f8') - img) * (fl * (.20 + .70 * under))[..., None] * .9
            if fl > .3:
                img = ST.draw_bolt(img, self.bolt, amt=min(1, fl * 1.1))
        # sea
        self.sea.A = self.sea.A  # gain applied through amplitude scale below
        gain = .82 + .30 * ease(t / 7.0)
        A0 = self.sea.A.copy(); self.sea.A = A0 * gain
        rg = [self.big_wave(t)]
        G = self.sea.render(cam, t, ridges=rg, h=H // 2, w=W // 2)
        lamp = self.lh.lamp_world(self.at)
        az = self.lh.beam_az(t, az0=math.radians(120))
        dirs = ST.beam_dirs(az)
        bs = SEA.beam_on_surface(G, lamp, dirs, half=.06, reach=300., amt=.8)
        sc, Ms, info = self.sea.paint(G, cam, t, PAL, light=(-.5, .4, .75), flash=fl * .9, beam=bs, fog_col='#5c6474', fog_k=(.0045, .85),
                                       lip=1.0, glass=1.0, caps=(60., .5))
        self.sea.A = A0
        zfull = cv2.resize(G['z'], (W, H), interpolation=cv2.INTER_NEAREST)
        img = img * (1 - Ms[..., None]) + sc * Ms[..., None]
        if fl > 0:     # wave tops facing the bolt catch it
            g2 = comp.radial(780, self.hz, 1900, 700, 1.0)
            k_ = (fl * (.18 + .75 * info['foam']) * (.3 + .7 * g2) * Ms)[..., None]
            img = img + (rgb('#e2eafc') - img) * k_
        img = img + (rgb('#5f6676') - img) * (self.mist * .7)[..., None]
        # island and tower, hidden where a nearer wave stands in front
        R = self.sp_isle.roi(d, cam.cx, cam.cy)
        if R is not None:
            X0, Y0, L, isa = R; hh, ww = L.shape[:2]; zr = zfull[Y0:Y0 + hh, X0:X0 + ww]
            vis = ((zr <= 0) | (zr > self.tdepth - 8)).astype(f32)
            L = L * vis[..., None]
            fogk = .38
            L[..., :3] = L[..., :3] * (1 - fogk) + rgb('#4e5566') * fogk * L[..., 3:4]
            if fl > 0: L[..., :3] += (rgb('#d6e0f8') * L[..., 3:4] - L[..., :3]) * fl * .5
            sub = ST.over(img[Y0:Y0 + hh, X0:X0 + ww], L)
            img[Y0:Y0 + hh, X0:X0 + ww] = SEA.surf(sub, isa, vis * (isa > 0), f, seed=3, up=3, down=2, amt=.35)
        # mid rocks with surf at their feet
        R = self.sp_mid.roi(d, cam.cx, cam.cy)
        if R is not None:
            X0, Y0, L, rd = R; hh, ww = L.shape[:2]; zr = zfull[Y0:Y0 + hh, X0:X0 + ww]
            vis = ((zr <= 0) | (zr > rd - 2.0)).astype(f32)
            sub = ST.over(img[Y0:Y0 + hh, X0:X0 + ww], L * vis[..., None])
            img[Y0:Y0 + hh, X0:X0 + ww] = SEA.surf(sub, L[..., 3], vis, f, seed=2, up=3, down=5, amt=.75)
        # the lamp in the air and the beam in the rain
        lx, ly = self.lh.lamp_px(cam, self.at)
        zl = zfull[int(np.clip(ly + 3, 0, H - 1)), int(np.clip(lx, 0, W - 1))]
        if zl <= 0 or zl > self.tdepth - 8:
            img = self.lh.lamp_glow(img, cam, self.at, amt=.9, col='#ffc070')
        B = ST.beam_volume(cam, lamp, dirs, depth=np.where(zfull > 0, zfull, 0), t=t, reach=330., amt=.75, half=.035, r0=.8)
        cur = self.rain.curtains(f)
        bcol = rgb('#fff2d0')
        img = comp.screen(img, (B * (.55 + .7 * cur))[..., None] * bcol)
        # far rain curtains: paler veils lit a little by the beam
        veil = cur * smooth(self.hz - 520, self.hz + 40, np.arange(H, dtype=f32)[:, None]) * (1 - smooth(self.hz + 40, self.hz + 260, np.arange(H, dtype=f32)[:, None]) * .6)
        img = img + (rgb('#7b8594') - img) * (veil * .22)[..., None]
        # near rock, the wave smashing on it
        R = self.sp_rock.roi(d, cam.cx, cam.cy)
        rka = np.zeros((H, W), f32)
        if R is not None:
            X0, Y0, L, _ = R; hh, ww = L.shape[:2]
            if fl > 0: L[..., :3] += (rgb('#aeb9d6') * L[..., 3:4] - L[..., :3]) * fl * .35
            img[Y0:Y0 + hh, X0:X0 + ww] = ST.over(img[Y0:Y0 + hh, X0:X0 + ww], L)
            rka[Y0:Y0 + hh, X0:X0 + ww] = L[..., 3]
        cvs = Canvas(H, W, layer=True)
        SEA.crest_spray(cvs, info['foam'] * (rka < .3), G, f, wind=(1., -.12), n=110, seed=4, ymax=None)
        age = ((f // 2) * 2) / 24. - self.t_crash
        mist = np.zeros((H, W), f32)
        k = 9. / (9. - d)
        Pw = lambda p: (cam.cx + k * (p[0] - cam.cx), cam.cy + k * (p[1] - cam.cy))
        if age >= -.05:
            img = self._runup(img, rka, max(age, 0.), Pw, k)
        if age >= 0:
            # three seas break up the seaward face of the ledge, each its own shape; the wind tears them to the right
            for (px_, py_, sz, a0, up, n_, dl, sd, lf) in ((975, 1004, 600, -np.pi / 2 - .30, .62, 90, 0., 31, 2.0),
                                                           (1090, 1080, 380, -np.pi / 2 - .02, 1.0, 46, .06, 37, 1.5),
                                                           (830, 952, 290, -np.pi / 2 - .55, .45, 34, .22, 41, 1.6)):
                X, Y = Pw((px_, py_))
                SEA.burst(cvs, X, Y, sz * k, age - dl, seed=sd, wind=(1.3, -.05), life=lf, n=n_, mist=mist, ang0=a0, up=up, tear=1.6)
            img = img + (rgb('#aab5c0') - img) * (mist * .8)[..., None]
        img = ST.over(img, cvs.layer())
        # rain over everything, brighter in the beam and in the flash
        rs = self.rain.streaks(f)
        lit = .55 + 2.2 * np.clip(B, 0, 1) + 1.2 * fl
        img = img + (rgb('#a8b6c4') * np.clip(lit, 0, 2)[..., None] * .9 - img) * (rs * .8)[..., None]
        if fl > 0:
            img = img + (rgb('#dfe7fb') - img) * (fl * .08)
        return np.clip(img, 0, 1.4).astype(f32)
