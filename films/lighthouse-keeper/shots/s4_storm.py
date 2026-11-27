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

VER = 'v6'
EYE0 = np.array([0., 0., 4.0])
TGT = np.array([8., 120., 13.])
FOC = 1250.
PUSH = .8                  # metres of dolly over the shot
ISLAND = (52., 150., 0.)    # island foot (world); the tower stands on its top
ISLE_TOP = 7.5
HIT = np.array([0.4, 11.0])  # where the big wave meets the near rock (world xy)
WAVE_DIR = np.array([-.75, -.66])
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

    def _lip(self, cvs, cam, t, f):
        """the breaking lip of the big wave: a curl of green water thrown forward off the crest, a dark hollow
        under it, white water fringing the top; it pitches further as the wave nears the rock"""
        T = self.t_crash
        if t < T - 2.2 or t > T + .12: return
        rg = self.big_wave(t)
        d = np.array(rg[:2]); p = np.array(rg[2:4]); amp = rg[4]; wid = rg[7]; lean = rg[8]
        if amp < 2.5: return
        pr = float(np.clip((t - (T - 2.0)) / 2.0, 0, 1)) ** 1.3
        perp = np.array([-d[1], d[0]])
        bs = np.linspace(-1.25, 1.25, 56) * wid
        env = np.exp(-(bs / wid) ** 2)
        B = p[None] + perp[None] * bs[:, None]
        gain = .82 + .30 * min(1., t / 7.0)
        A0 = self.sea.A.copy(); self.sea.A = A0 * gain
        z = self.sea.height(B[:, 0] + d[0] * lean * amp * env, B[:, 1] + d[1] * lean * amp * env, t, [rg])[:, 0]
        self.sea.A = A0
        C = np.c_[B + d[None] * lean * amp * env[:, None], z]
        keep = env > .3
        C, env, z = C[keep], env[keep], z[keep]
        if len(C) < 4: return
        c0, zc = cam.project(C)
        ok = (zc > 1.5)
        if ok.sum() < 4: return
        r = np.random.default_rng(500 + f // 2)
        n = len(C)
        Lt = amp * (.05 + .20 * pr) * env
        up = np.array([0, 0, 1.])
        D3 = np.c_[d[None].repeat(n, 0), np.zeros(n)]
        mid = C + D3 * Lt[:, None] * .6 + up * (Lt * (.25 - .1 * pr))[:, None]
        tip = C + D3 * Lt[:, None] * (.85 + .15 * pr) - up * (Lt * (.10 + .55 * pr))[:, None]
        hol = C + D3 * Lt[:, None] * .3 - up * (Lt * (.6 + .5 * pr))[:, None]
        pm, _ = cam.project(mid); pt, _ = cam.project(tip); ph, _ = cam.project(hol)
        sc = cam.f / np.maximum(zc, 1.5)
        idx = np.nonzero(ok)[0]
        if len(idx) < 4: return
        from lp.paint import arcs

        def bands(Q, wd, cols, ops, dry, sd, shape='round'):
            # strokes that run ALONG the crest, in chunks, so the curl is painted as one surface
            K = 6
            for j in range(0, len(idx) - 1, K - 1):
                seg = idx[j:j + K]
                if len(seg) < 3: continue
                if len(seg) < K: seg = np.r_[seg, [seg[-1]] * (K - len(seg))]
                cvs.strokes(Q[seg][None], float(np.mean(wd[seg])), np.asarray(cols, f32)[None], op=ops, dry=dry, seed=sd + j, shape=shape, bristle=.06)
        # --- the curl as a body of water: rasterise its rings into an ROI (alpha, u from root to edge, stroke direction),
        # colour it back-lit deep green at the root, translucent lighter green up the face, then repaint it in gouache
        allp = np.vstack([c0[idx], pm[idx], pt[idx], ph[idx]])
        x0 = int(max(0, allp[:, 0].min() - 40)); x1 = int(min(W, allp[:, 0].max() + 40))
        y0 = int(max(0, allp[:, 1].min() - 40)); y1 = int(min(H, allp[:, 1].max() + 40))
        if x1 - x0 < 10 or y1 - y0 < 10: return
        hh, ww = y1 - y0, x1 - x0
        A = np.zeros((hh, ww), f32); U = np.zeros((hh, ww), f32); AX = np.zeros((hh, ww), f32); AY = np.zeros((hh, ww), f32)
        HO = np.zeros((hh, ww), f32)
        o = np.array([x0, y0], f32)
        def ring(u, A_, B_, C_=None):
            return (1 - u) ** 2 * A_ + 2 * u * (1 - u) * B_ + u * u * C_ if C_ is not None else A_ + (B_ - A_) * u
        us = np.linspace(0, 1, 7)
        Rs = [ring(u, c0, pm, pt) - o for u in us]
        Hs = [ring(u, c0, ph) - o for u in np.linspace(0, 1, 4)]
        for kq in range(len(us) - 1):
            for jj in range(len(idx) - 1):
                i0, i1 = idx[jj], idx[jj + 1]
                if i1 != i0 + 1: continue
                q = np.round(np.array([Rs[kq][i0], Rs[kq][i1], Rs[kq + 1][i1], Rs[kq + 1][i0]]) * 4).astype(np.int32)
                dv = (Rs[kq + 1][i0] + Rs[kq + 1][i1] - Rs[kq][i0] - Rs[kq][i1]); dv = dv / (np.hypot(*dv) + 1e-6)
                cv2.fillConvexPoly(A, q, 1.0, cv2.LINE_8, 2)
                cv2.fillConvexPoly(U, q, float((us[kq] + us[kq + 1]) / 2), cv2.LINE_8, 2)
                cv2.fillConvexPoly(AX, q, float(dv[0]), cv2.LINE_8, 2); cv2.fillConvexPoly(AY, q, float(dv[1]), cv2.LINE_8, 2)
        for kq in range(len(Hs) - 1):
            for jj in range(len(idx) - 1):
                i0, i1 = idx[jj], idx[jj + 1]
                if i1 != i0 + 1: continue
                q = np.round(np.array([Hs[kq][i0], Hs[kq][i1], Hs[kq + 1][i1], Hs[kq + 1][i0]]) * 4).astype(np.int32)
                cv2.fillConvexPoly(HO, q, 1.0, cv2.LINE_8, 2)
        if A.max() < .5: return
        bw = float(np.median(np.hypot(*(pt[idx] - c0[idx]).T))) + 4
        sm = lambda X, s_: cv2.GaussianBlur(X, (0, 0), s_)
        Ab = sm(A, max(1., bw * .08)) + 1e-4
        Us = sm(U * A, max(1., bw * .12)) / Ab
        ang = np.arctan2(sm(AY * A, bw * .15), sm(AX * A, bw * .15)).astype(f32)
        if not hasattr(self, '_lipn'):
            self._lipn = fbm(512, 512, (60, 22, 8), (1, .6, .35), 91).astype(f32)
        nz_ = self._lipn[np.arange(y0, y1)[:, None] % 512, (np.arange(x0, x1)[None] + int(t * 60)) % 512]
        tt_ = np.clip(Us + .10 * nz_, 0, 1)
        from lp.paint import ramp, repaint
        guide = ramp(tt_, [(0, '#1b3236'), (.3, '#264848'), (.55, '#3b6563'), (.75, '#55827d'), (.9, '#7aa09b'), (1, '#a9c2bf')])
        hol = sm(HO, max(1.5, bw * .12)) * (1 - sm(A, 1.0))
        bws = float(np.clip(bw * .07, 2.5, 10))
        guide = cv2.GaussianBlur(guide, (0, 0), bws * .6)
        painted = repaint(guide, (bws * 2.4, bws * 1.2), seed=f // 2 + 17, angle=ang, mask=(A > .5).astype(f32), thr=(0, .006), density=1.0,
                          aspect=5.0, jit=(.003, .008, .012), op=.8, dry=.12, curve=.5, bristle=.05, shape='leaf')
        a_l = np.clip(sm(A, .9), 0, 1)
        sub_c = cvs.img[y0:y1, x0:x1]; sub_a = cvs.a[y0:y1, x0:x1]
        def put(col, a_):
            na = a_ + sub_a * (1 - a_)
            sub_c[:] = np.where(na[..., None] > 1e-4, (col * a_[..., None] + sub_c * (sub_a * (1 - a_))[..., None]) / np.maximum(na, 1e-4)[..., None], sub_c)
            sub_a[:] = na
        put(np.broadcast_to(rgb('#0f1b23'), (hh, ww, 3)), np.clip(hol * (.6 + .3 * pr), 0, 1))
        put(painted, a_l)
        # white water: clumps of different sizes, broken, curling over along the lip, torn off to the right
        from lp.paint import arcs
        nc = int(len(idx) * 1.2)
        ci = r.choice(idx, nc)
        keepc = r.random(nc) > .3
        ci = ci[keepc]; nc = len(ci)
        if nc:
            uu = r.uniform(.72, 1.0, nc)
            cen = (1 - uu[:, None]) ** 2 * c0[ci] + 2 * (uu * (1 - uu))[:, None] * pm[ci] + (uu ** 2)[:, None] * pt[ci]
            csz = sc[ci] * amp * r.uniform(.006, .03, nc) ** 1.0 * (.6 + .8 * pr)
            m_ = 5
            xs = (cen[:, 0, None] + r.normal(0, 1, (nc, m_)) * csz[:, None] * 1.1).ravel()
            ys = (cen[:, 1, None] + r.normal(0, .6, (nc, m_)) * csz[:, None]).ravel()
            rad = (csz[:, None] * r.uniform(.35, 1.0, (nc, m_))).ravel()
            Pd = arcs(xs, ys, r.uniform(-.4, .4, xs.size), rad * r.uniform(1.0, 2.2, xs.size), r.normal(0, .4, xs.size), K=4)
            cc = np.where(r.random((xs.size, 1)) < .3, rgb('#a9bcc0'), rgb('#e6eef0'))
            cvs.strokes(Pd, rad, cc.astype(f32), op=r.uniform(.6, .95, xs.size), dry=r.uniform(.1, .5, xs.size), seed=f // 2 + 23, shape='round', bristle=.06)
            # spume torn downwind
            nt = nc * 2
            j = r.integers(0, nc, nt)
            L_ = csz[j] * r.uniform(2.5, 7, nt)
            Pt = arcs(cen[j, 0] + L_ * .5, cen[j, 1] - L_ * .12, r.normal(-.18, .12, nt), L_, r.normal(.2, .2, nt), K=5)
            cvs.strokes(Pt, csz[j] * .35, np.broadcast_to(rgb('#d6dfe3'), (nt, 3)), op=r.uniform(.3, .7, nt), dry=r.uniform(.4, .8, nt), seed=f // 2 + 29, shape='taper', bristle=.08)

    def _runup(self, img, rka, age, Pw, k):
        """white water running up the ledge from the impact, then draining back down in streaks; the rock stays wet"""
        Ix, Iy = Pw((960, 1000))
        x0, y0 = 0, int(max(0, Iy - 700 * k))
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
        n = cv2.GaussianBlur(self._caps2[(yy.astype(int) // 3) % 256, (xx.astype(int) // 3) % 256], (0, 0), 2.0)
        front = 520 * (1 - math.exp(-age / .16))
        reach = 520.
        lead = smooth(front + 40, front - 30, u + 70 * (n - .5)) * (u > -80)
        surf = smooth(110, 25, dtop)
        wash = A * lead * surf * float(np.clip(1.1 - age / .9, 0, 1)) * (.35 + .9 * n) * smooth(-80, 40, u)
        wet = A * smooth(reach + 20, reach - 60, u + 90 * (n - .5)) * (u > -90) * smooth(170, 40, dtop) * float(min(1, age / .3))
        # the wet rock: darker, with a cold sheen on the upper planes
        dry = float(np.clip(1 - (age - 1.2) / 4.0, .55, 1))
        sub *= (1 - .22 * wet * dry)[..., None]
        sheen = wet * smooth(.62, .8, n) * smooth(60, 10, dtop) * dry
        sub += (rgb('#8e9bb0') - sub) * (sheen * .5)[..., None]
        # water draining back in thin streaks
        if age > .35:
            ds = self._streak[((yy.astype(int) - int(age * 420)) // 3) % 512, (xx.astype(int) * 2) % 512]
            drain = cv2.GaussianBlur(wet * smooth(.58, .72, ds), (0, 0), 1.0) * float(np.clip(1.3 - (age - .35) / 2.6, 0, 1))
            sub += (rgb('#c3ced6') - sub) * (drain * .75)[..., None]
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
        amp = float(np.interp(t, [0, T - 3.2, T - 1.6, T - .5, T - .1, T + .35, T + .9, T + 1.7, 9], [.0, 1.0, 3.6, 6.6, 7.0, 3.5, 1.5, .6, .3]))
        lean = float(np.interp(t, [0, T - 1.5, T - .3, T], [.1, .22, .40, .45]))
        d = WAVE_DIR / np.linalg.norm(WAVE_DIR)
        # the crest (centre pushed forward by the lean) arrives on the rock at T and stays there as it collapses
        p = HIT - d * (lean * amp * .7 + 1.0) - d * 8.5 * max(T - t, 0.)
        return SEA.ridge(d, p, 8.5, amp, back=14., front=6.0 - 2.5 * min(1, max(0, (t - T + 1.5) / 1.5)), width=22., lean=lean)

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
        self._lip(cvs, cam, t, f)
        SEA.crest_spray(cvs, info['foam'] * (rka < .3), G, f, wind=(1., -.12), n=110, seed=4, ymax=None)
        age = ((f // 2) * 2) / 24. - self.t_crash
        mist = np.zeros((H, W), f32)
        k = 9. / (9. - d)
        Pw = lambda p: (cam.cx + k * (p[0] - cam.cx), cam.cy + k * (p[1] - cam.cy))
        if age >= -.05:
            img = self._runup(img, rka, max(age, 0.), Pw, k)
        if age >= 0:
            # three seas break up the seaward face of the ledge, each its own shape; the wind tears them to the right
            # the sea hits the seaward face of the ledge: it climbs the face, then is thrown up and torn downwind
            for (px_, py_, sz, a0, up, n_, dl, sd, lf, sk) in ((930, 985, 620, -np.pi / 2 - .10, .70, 90, 0., 31, 2.0, 1.4),
                                                               (1010, 1030, 330, -np.pi / 2 + .25, .9, 40, .08, 37, 1.5, 1.0),
                                                               (840, 962, 300, -np.pi / 2 - .45, .5, 34, .2, 41, 1.6, 1.8)):
                X, Y = Pw((px_, py_))
                SEA.burst(cvs, X, Y, sz * k, age - dl, seed=sd, wind=(1.3, -.05), life=lf, n=n_, mist=mist, ang0=a0, up=up, tear=1.8, skew=sk)
            img = img + (rgb('#aab5c0') - img) * (mist * .8)[..., None]
        img = ST.over(img, cvs.layer())
        # rain over everything, brighter in the beam and in the flash
        rs = self.rain.streaks(f)
        lit = .55 + 2.2 * np.clip(B, 0, 1) + 1.2 * fl
        img = img + (rgb('#a8b6c4') * np.clip(lit, 0, 2)[..., None] * .9 - img) * (rs * .8)[..., None]
        if fl > 0:
            img = img + (rgb('#dfe7fb') - img) * (fl * .08)
        return np.clip(img, 0, 1.4).astype(f32)
