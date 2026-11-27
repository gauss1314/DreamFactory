"""Storm sea seen through a metric Camera3D (+X right, +Y forward, +Z up, metres).  Owned by the sea lane.

The surface is a sum of Gerstner swells (each with its own direction, length and wave-group envelope, so no two
waves are alike) plus "ridges": single named waves (s4's big breaker, s6's bow wave) with a steep front.
It is drawn column by column, front to back, like a voxel-space renderer, so a near crest hides the trough
behind it.  Every pixel gets the surface point, its normal, the Gerstner Jacobian (foam where the crest folds)
and the swell phase; the paint pass turns those into four gouache tones whose edges are brush marks that run
along the crests and travel with them.

  S = Sea(seed, wind=(dx, dy), comps=...)        # a sea state
  G = S.render(cam, t, ridges=[...])              # per-pixel buffers (dict of HxW float32)
  img, A = S.paint(G, cam, t, pal, ...)           # straight rgb + coverage (0 where sky)
  z, nx, ny = S.height(x, y, t, ridges)           # height and slope of the surface at world points (for boats)
"""
import math
import numpy as np, cv2
from numba import njit, prange
from lp import W, H
from lp.paint import f32, rgb, mix, smooth, fbm, _vn, Canvas, arcs, repaint

G_ACC = 9.81


@njit(cache=True, fastmath=True)
def _wave(bx, by, t, KX, KY, A, Q, OM, PH, GRP, RG, fade_s, env_amt, seed):
    """surface point displaced from base point (bx, by): returns px, py, pz, nx, ny, nz, J, phase0"""
    px = bx; py = by; pz = 0.0
    nx = 0.0; ny = 0.0; nz = 1.0
    jxx = 1.0; jyy = 1.0; jxy = 0.0
    ph0 = 0.0
    n = KX.shape[0]
    for i in range(n):
        k = math.sqrt(KX[i] * KX[i] + KY[i] * KY[i])
        lam = 6.2831853 / k
        at = (lam - fade_s * 2.5) / (fade_s * 4.0 + 1e-6)
        if at <= 0: continue
        if at > 1: at = 1.0
        dx = KX[i] / k; dy = KY[i] / k
        a = A[i] * at
        if GRP[i] > 0:
            # wave groups: the envelope drifts with the group velocity, so a big set comes through and passes
            cg = .5 * OM[i] / k
            gu = (bx * dx + by * dy - cg * t) / (lam * GRP[i]); gv = (-bx * dy + by * dx) / (lam * GRP[i] * 1.7)
            e = _vn(gu + 40.0 + i * 7.1, gv + 11.0, seed + i) * .65 + _vn(gu * 2.3 + 5.0, gv * 2.1 + 3.0, seed + 50 + i) * .35
            a *= 1.0 + env_amt * (e - .5) * 2.0
        th = KX[i] * bx + KY[i] * by - OM[i] * t + PH[i]
        s = math.sin(th); c = math.cos(th)
        q = Q[i] * at
        px += q * a * dx * c; py += q * a * dy * c; pz += a * s
        wa = k * a
        nx -= dx * wa * c; ny -= dy * wa * c; nz -= q * wa * s
        jxx -= q * wa * dx * dx * s; jyy -= q * wa * dy * dy * s; jxy -= q * wa * dx * dy * s
        if i == 0: ph0 = th
    for r in range(RG.shape[0]):
        dx = RG[r, 0]; dy = RG[r, 1]
        ua = (bx - RG[r, 2]) * dx + (by - RG[r, 3]) * dy
        ub = -(bx - RG[r, 2]) * dy + (by - RG[r, 3]) * dx
        L = RG[r, 5] if ua < 0 else RG[r, 6]
        ex = (ua / L) ** 2 + (ub / RG[r, 7]) ** 2
        if ex > 12: continue
        z = RG[r, 4] * math.exp(-ex)
        ga = -2 * ua / (L * L) * z; gb = -2 * ub / (RG[r, 7] ** 2) * z
        gx = ga * dx - gb * dy; gy = ga * dy + gb * dx
        lean = RG[r, 8]
        px += dx * lean * z; py += dy * lean * z; pz += z
        nx -= gx; ny -= gy
        jxx += lean * ga * .22
    J = jxx * jyy - jxy * jxy
    ln = math.sqrt(nx * nx + ny * ny + nz * nz)
    return px, py, pz, nx / ln, ny / ln, nz / ln, J, ph0


@njit(cache=True, fastmath=True, parallel=True)
def _march(ex, ey, ez, R, foc, cx, cy, h, w, KX, KY, A, Q, OM, PH, GRP, RG, t, s0, s1, env_amt, seed, out):
    """out[k, y, x]: 0 depth(z_cam, 0 = sky) 1 bx 2 by 3 pz 4 nx 5 ny 6 nz 7 J 8 phase 9 px 10 py"""
    NA = 11
    for i in prange(w):
        u = (i + .5 - cx) / foc
        a1 = R[0, 0] - u * R[2, 0]; b1 = R[0, 1] - u * R[2, 1]; c1 = (R[0, 2] - u * R[2, 2]) * ez
        a2 = R[2, 0]; b2 = R[2, 1]
        det = a1 * b2 - b1 * a2
        if abs(det) < 1e-9: continue
        # G(s) - eye = (ga0 + ga1 s, gb0 + gb1 s, -ez)
        c2_0 = R[2, 2] * ez
        ga0 = (c1 * b2 - b1 * c2_0) / det; gb0 = (a1 * c2_0 - c1 * a2) / det
        ga1 = (-b1) / det; gb1 = a1 / det
        top = h            # first unfilled row from the bottom: rows >= top are done
        ybuf = 1e9
        prev = np.zeros(NA); cur = np.zeros(NA)
        psy = 0.0
        first = True
        s = s0
        while s < s1:
            bx = ex + ga0 + ga1 * s; by = ey + gb0 + gb1 * s
            fade_s = s * s / (foc * max(ez, 1.0)) * .9 + s / foc * .5   # metres per pixel, ~vertical
            px, py, pz, nx, ny, nz, J, ph = _wave(bx, by, t, KX, KY, A, Q, OM, PH, GRP, RG, fade_s, env_amt, seed)
            dX = px - ex; dY = py - ey; dZ = pz - ez
            cz = R[2, 0] * dX + R[2, 1] * dY + R[2, 2] * dZ
            cyv = R[1, 0] * dX + R[1, 1] * dY + R[1, 2] * dZ
            ds = s * min(.03, max(.006, s / (foc * max(ez, 1.0)) * .9))
            if cz < .05:
                s += ds; continue
            sy = cyv / cz * foc + cy
            cur[0] = cz; cur[1] = bx; cur[2] = by; cur[3] = pz; cur[4] = nx; cur[5] = ny; cur[6] = nz; cur[7] = J; cur[8] = ph
            cur[9] = px; cur[10] = py
            if first:
                r0 = int(math.ceil(sy))
                if r0 < 0: r0 = 0
                for r in range(r0, h):
                    for k in range(NA): out[k, r, i] = cur[k]
                if r0 < top: top = r0
                ybuf = sy; first = False
            elif sy < ybuf:
                r0 = int(math.ceil(sy))
                if r0 < 0: r0 = 0
                den = sy - psy
                for r in range(r0, top):
                    wgt = 1.0
                    if abs(den) > 1e-6:
                        wgt = (r - psy) / den
                        if wgt < 0: wgt = 0.0
                        if wgt > 1: wgt = 1.0
                    for k in range(NA): out[k, r, i] = prev[k] + (cur[k] - prev[k]) * wgt
                if r0 < top: top = r0
                ybuf = sy
            for k in range(NA): prev[k] = cur[k]
            psy = sy
            if top <= 0: break
            s += ds
        for r in range(0, top):
            out[0, r, i] = 0.0


@njit(cache=True, fastmath=True)
def _heights(X, Y, t, KX, KY, A, Q, OM, PH, GRP, RG, env_amt, seed, out):
    for j in range(X.shape[0]):
        # invert the horizontal Gerstner shift by fixed point so the answer is at the world point itself
        bx = X[j]; by = Y[j]
        for it in range(3):
            px, py, pz, nx, ny, nz, J, ph = _wave(bx, by, t, KX, KY, A, Q, OM, PH, GRP, RG, 0.0, env_amt, seed)
            bx += X[j] - px; by += Y[j] - py
        px, py, pz, nx, ny, nz, J, ph = _wave(bx, by, t, KX, KY, A, Q, OM, PH, GRP, RG, 0.0, env_amt, seed)
        out[j, 0] = pz; out[j, 1] = nx; out[j, 2] = ny; out[j, 3] = nz; out[j, 4] = J


@njit(cache=True, fastmath=True)
def _tex(T, ch, u, v):
    th = T.shape[0]; tw = T.shape[1]
    u = u % tw; v = v % th
    i0 = int(u); j0 = int(v); fu = u - i0; fv = v - j0
    i1 = i0 + 1
    if i1 >= tw: i1 = 0
    j1 = j0 + 1
    if j1 >= th: j1 = 0
    if i0 >= tw: i0 = 0
    if j0 >= th: j0 = 0
    a = T[j0, i0, ch] + (T[j0, i1, ch] - T[j0, i0, ch]) * fu
    b = T[j1, i0, ch] + (T[j1, i1, ch] - T[j1, i0, ch]) * fu
    return a + (b - a) * fv


@njit(cache=True, fastmath=True)
def _sm(a, b, x):
    t = (x - a) / (b - a)
    if t < 0: t = 0.0
    if t > 1: t = 1.0
    return t * t * (3 - 2 * t)


@njit(cache=True, fastmath=True, parallel=True)
def _tone(V, LAM, FOLD, FAR, MPP, ALONG, FU, FV, MF, CR, GL, BM, T, C, thr, prm, out, FOAM):
    h, w = V.shape
    hasb = BM.shape[0] == h
    e = .014
    for y in prange(h):
        for x in range(w):
            mf = MF[y, x]
            if mf <= 0:
                FOAM[y, x] = 0.0
                for k in range(3): out[y, x, k] = 0.0
                continue
            mpp = MPP[y, x]
            nw = _sm(.5, .12, mpp)
            bn = _tex(T, 0, CR[y, x] * 23., ALONG[y, x] * 46.)
            bf = _tex(T, 0, x * .55 + 300, y * 2.4)
            b = bn * nw + bf * (1 - nw) * .85
            vb = V[y, x] + b * prm[4]
            s1 = _sm(thr[0] - e, thr[0] + e, vb); s2 = _sm(thr[1] - e, thr[1] + e, vb); s3 = _sm(thr[2] - e, thr[2] + e, vb)
            lam = LAM[y, x]
            fold = FOLD[y, x]
            st = _tex(T, 1, FU[y, x] * 26., FV[y, x] * 70.) * _sm(.15, .45, _tex(T, 0, FU[y, x] * 3.1 + 200., FV[y, x] * 4.3) + .25)
            wn = _sm(.35, .08, mpp)
            foam = fold * prm[0] * (.8 + .6 * b) + st * _sm(.3, .02, fold) * wn * .55 * prm[1]
            foam = min(1.0, max(0.0, foam)) * mf * prm[5]
            hard = _sm(.30, .50, foam + b * .3)
            fl = _sm(-.2, .6, lam + .3 * b)
            bmv = 0.0
            if hasb: bmv = BM[y, x] * (.4 + .6 * min(1.0, max(0.0, lam + .4)))
            fk = 0.0
            if prm[2] > 0: fk = min(1.4, max(0.0, .45 + .5 * V[y, x] + .9 * hard)) * prm[2] * .55
            fg = FAR[y, x] * prm[3]
            for k in range(3):
                c = C[0, k]
                c += (C[1, k] - c) * s1
                c += (C[2, k] - c) * s2
                c += (C[3, k] - c) * s3
                c *= 1 + (.05 + .06 * nw) * b
                c += (C[9, k] - c) * min(1.0, GL[y, x] * (.8 + .5 * b))
                c += bmv * (C[6, k] * .6 - c * .3)
                fc = C[5, k] + (C[4, k] - C[5, k]) * fl
                c += (fc - c) * (hard * .92 + foam * .06)
                c += (C[7, k] * 1.05 - c) * fk
                c += (C[8, k] - c) * fg
                out[y, x, k] = c
            FOAM[y, x] = hard


def ridge(direction, p0, speed, amp, back=14., front=6., width=40., lean=.35):
    """one named wave: centre p0 (world xy) at amp, travelling `direction` at `speed` m/s (caller moves p0)"""
    d = np.asarray(direction, float); d /= np.linalg.norm(d)
    return [d[0], d[1], p0[0], p0[1], amp, back, front, width, lean]


class Sea:
    def __init__(self, seed=1, wind=(1., -.35), heading=None, n=11, lmax=70., lmin=2.6, steep=.10, Q=.62, spread=.55,
                 env_amt=.42, group=3.2, scale=1.0):
        r = np.random.default_rng(seed)
        self.wind = np.asarray(wind, float) / np.linalg.norm(wind)
        base = math.atan2(self.wind[1], self.wind[0]) if heading is None else heading
        lam = lmax * (lmin / lmax) ** (np.arange(n) / (n - 1.))
        lam = lam * r.uniform(.9, 1.1, n)
        ang = base + r.normal(0, spread, n) * np.linspace(.45, 1.0, n)
        ang[0] = base
        k = 2 * np.pi / lam
        a = steep * lam / (2 * np.pi) * np.linspace(1., .55, n) * scale
        a[0] *= 1.25
        self.KX = (k * np.cos(ang)).astype(np.float64); self.KY = (k * np.sin(ang)).astype(np.float64)
        self.A = a.astype(np.float64)
        q = Q / (k * a * n)             # sum Q k a < 1 keeps the crests from looping
        self.Q = np.minimum(q * 1.0, 1.6).astype(np.float64)
        self.OM = np.sqrt(G_ACC * k).astype(np.float64)
        self.PH = r.uniform(0, 2 * np.pi, n)
        self.GRP = np.where(lam > 6, group * r.uniform(.8, 1.3, n), 0.).astype(np.float64)
        self.env_amt = env_amt; self.seed = seed
        self.lam0 = lam[0]; self.k0 = (self.KX[0], self.KY[0])
        self._tex = None

    # --------------------------------------------------------------- geometry
    def _rg(self, ridges):
        return np.zeros((0, 9)) if not ridges else np.asarray(ridges, np.float64).reshape(-1, 9)

    def render(self, cam, t, ridges=None, s0=1.0, s1=6000., h=None, w=None):
        h = cam.h if h is None else h; w = cam.w if w is None else w
        out = np.zeros((11, h, w), np.float32)
        ex, ey, ez = cam.eye
        foc = cam.f * (w / cam.w)
        cx = cam.cx * (w / cam.w); cy = cam.cy * (h / cam.h)
        _march(float(ex), float(ey), float(ez), cam.R.astype(np.float64), float(foc), float(cx), float(cy), h, w,
               self.KX, self.KY, self.A, self.Q, self.OM, self.PH, self.GRP, self._rg(ridges), float(t), s0, s1,
               self.env_amt, self.seed, out)
        keys = ('z', 'bx', 'by', 'pz', 'nx', 'ny', 'nz', 'J', 'ph', 'px', 'py')
        return {k: out[i] for i, k in enumerate(keys)}

    def height(self, x, y, t, ridges=None):
        """-> (n,5): z, nx, ny, nz, J at world points"""
        X = np.atleast_1d(np.asarray(x, np.float64)); Y = np.atleast_1d(np.asarray(y, np.float64))
        o = np.zeros((X.size, 5))
        _heights(X.ravel(), Y.ravel(), float(t), self.KX, self.KY, self.A, self.Q, self.OM, self.PH, self.GRP, self._rg(ridges), self.env_amt, self.seed, o)
        return o

    # ------------------------------------------------------------------ paint
    def textures(self, seed=0):
        """brush tiles painted once: crest-wise stroke field (u along the crest, v across) and wind foam streaks"""
        if self._tex is not None: return self._tex
        from lp import cache_path
        import os
        p = cache_path(f'lk_sea_tex_{self.seed}_{seed}_v3.npy')
        if os.path.exists(p):
            self._tex = np.load(p).astype(f32); return self._tex
        r = np.random.default_rng(seed + 77)
        N = 1024
        cv = Canvas(N, N, color=np.array([.5, .5, .5], f32))
        # long flat strokes along the crest, three sizes; values are offsets around .5
        for (n, wd, ln, cur) in ((900, 10, 120, .25), (1800, 6, 70, .35), (3200, 3.4, 38, .45)):
            x = r.uniform(-40, N + 40, n); y = r.uniform(-20, N + 20, n)
            P = arcs(x, y, r.normal(0, .07, n), ln * r.uniform(.6, 1.4, n), r.normal(0, cur, n), K=6)
            v = np.clip(.5 + r.normal(0, .22, n), 0, 1)
            cv.strokes(P, wd * r.uniform(.6, 1.2, n), np.stack([v, v, v], 1), op=r.uniform(.5, .95, n), dry=r.uniform(0, .5, n), seed=seed + n, shape='flat', bristle=.08)
        a = cv.img[..., 0] - .5
        # foam streak tile: thin lacy streaks along x (wind)
        cf = Canvas(N, N, color=np.zeros(3, f32))
        n = 2600
        x = r.uniform(-40, N + 40, n); y = r.uniform(-10, N + 10, n)
        P = arcs(x, y, r.normal(0, .05, n), r.uniform(20, 160, n), r.normal(0, .5, n), K=6)
        v = r.uniform(.35, 1, n)
        cf.strokes(P, r.uniform(.8, 3.2, n), np.stack([v, v, v], 1), op=r.uniform(.4, 1, n), dry=r.uniform(.2, .9, n), seed=seed + 3, shape='round', bristle=.1)
        b = cf.img[..., 0]
        # make both tiles wrap: cross-fade edges
        def wrap(t):
            m = 96; o = t.copy()
            ramp = np.linspace(0, 1, m, dtype=f32)
            o[:, :m] = t[:, :m] * ramp[None] + t[:, -m:] * (1 - ramp[None])
            o[:m, :] = o[:m, :] * ramp[:, None] + o[-m:, :] * (1 - ramp[:, None])
            return o[:N - m, :N - m]
        T = np.stack([wrap(a), wrap(b)], -1).astype(f32)
        np.save(p, T.astype(np.float16))
        self._tex = T
        return T

    def sample(self, tex, u, v):
        th, tw = tex.shape[:2]
        return cv2.remap(tex, (np.mod(u, tw)).astype(f32), (np.mod(v, th)).astype(f32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)

    def paint(self, G, cam, t, pal, light=(-.4, .5, .75), flash=0.0, beam=None, fog_col=None, fog_k=(.0015, 1.0),
              crest_foam=1.0, streak=1.0, out_hw=(H, W), lip=0.0, caps=None, glass=0.0):
        """gouache pass.  Geometry G may be at a lower resolution: smooth fields are shaded there, then the tone
        edges are cut at full resolution against brush tiles that run along the crests and travel with them.
        pal: deep, body, face, sky_lo, foam, foam_sh, beam, thr.  beam: warm light on the surface (G's size)."""
        z = G['z']; M = z > 0
        h, w = z.shape; Hh, Ww = out_hw
        T = self.textures()
        nx, ny, nz = G['nx'], G['ny'], G['nz']
        sc = w / cam.w
        foc = cam.f * sc
        y, x = np.mgrid[0:h, 0:w].astype(f32)
        Rm = cam.R.astype(f32)
        dx_ = (x - cam.cx * sc) / foc; dy_ = (y - cam.cy * sc) / foc
        d0 = dx_ * Rm[0, 0] + dy_ * Rm[1, 0] + Rm[2, 0]; d1 = dx_ * Rm[0, 1] + dy_ * Rm[1, 1] + Rm[2, 1]; d2 = dx_ * Rm[0, 2] + dy_ * Rm[1, 2] + Rm[2, 2]
        dl = np.sqrt(d0 * d0 + d1 * d1 + d2 * d2); d0 /= dl; d1 /= dl; d2 /= dl
        dn = d0 * nx + d1 * ny + d2 * nz
        rz = d2 - 2 * dn * nz
        cosv = np.clip(-dn, 0, 1)
        F = .03 + .97 * (1 - cosv) ** 4
        L = np.asarray(light, f32); L = L / np.linalg.norm(L)
        lam = np.clip(nx * L[0] + ny * L[1] + nz * L[2], -1, 1)
        sky_ref = smooth(.55, -.02, rz)
        crest = smooth(.0, 1.0, G['pz'] / (self.A[0] * 1.8))
        v = .30 * F * (.5 + .8 * sky_ref) + .22 * (lam * .5 + .5) + .18 * smooth(.25, .9, nz) * F + .10 * crest * smooth(.2, .8, cosv)
        v = v + .26 * smooth(.25, .85, G['pz'] / (self.A[0] * 2.2)) * smooth(.95, .55, nz) * smooth(.1, .5, cosv)
        v = v - .10 * smooth(0, -1, G['pz'] / self.A[0])                 # troughs sink
        v = v + .10 * smooth(-1.2, 1.2, G['pz'] / self.A[0]) * smooth(.3, .05, z * z / (foc * max(cam.eye[2], 1.)) / sc)   # near: faces grade from trough to crest
        J = G['J']
        fold = smooth(.70, .20, J) * smooth(-.3, .4, G['pz'] / (self.A[0] + 1e-3))
        if caps is not None:      # white caps come in patches: where a wave group is breaking, not everywhere
            csc, camt = caps
            if not hasattr(self, '_caps'):
                self._caps = np.clip(fbm(256, 256, (40, 16), (1, .5), self.seed + 333) * .5 + .5, 0, 1).astype(f32)
            cf = cv2.remap(self._caps, (G['bx'] / csc * 2.56).astype(f32) % 256, (G['by'] / csc * 2.56).astype(f32) % 256, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
            cf = smooth(.42, .75, cf)
            fold = fold * ((1 - camt) + camt * 1.8 * cf)
            v = v + .05 * camt * (cf - .5)
        if lip > 0:               # the lip: foam riding the top edge of every near crest that hides the sea behind it
            zab = np.vstack([z[:1], z[:-1]])
            edge = (M & ((zab > z * 1.3) | (zab <= 0)) & (z < 40)).astype(f32) * smooth(40, 12, z) * smooth(.35, .8, G['pz'] / self.A[0]) * smooth(.95, .8, nz)
            band = cv2.dilate(edge, np.ones((4, 1), np.uint8), anchor=(0, 0))
            band = np.maximum(band, cv2.dilate(edge * smooth(30, 10, z), np.ones((20, 1), np.uint8), anchor=(0, 0)) * .7)
            if not hasattr(self, '_caps'):
                self._caps = np.clip(fbm(256, 256, (40, 16), (1, .5), self.seed + 333) * .5 + .5, 0, 1).astype(f32)
            yy_, xx_ = np.mgrid[0:h, 0:w].astype(f32)
            nn = cv2.remap(self._caps, (xx_ * .9 + G['bx'] * 3) % 256, (yy_ * .5 + G['by']) % 256, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
            band = cv2.GaussianBlur(band * smooth(.35, .6, nn), (0, 0), 1.2)
            fold = np.maximum(fold, band * lip)
        gl = (smooth(.25, .9, G['pz'] / (self.A[0] * 2.0)) * smooth(.92, .45, nz) * smooth(.12, .55, cosv) * glass).astype(f32)
        far = 1 - np.exp(-z * fog_k[0])
        mpp = z * z / (foc * max(cam.eye[2], 1.)) / sc           # metres per full-res pixel, vertically
        k0x, k0y = self.k0; k0 = math.hypot(k0x, k0y)
        along = (G['bx'] * k0x + G['by'] * k0y) / k0 - self.OM[0] / k0 * t
        cross = (-G['bx'] * k0y + G['by'] * k0x) / k0
        fu = (G['bx'] * self.wind[0] + G['by'] * self.wind[1]) - t * 1.6
        fv = (-G['bx'] * self.wind[1] + G['by'] * self.wind[0])
        lst = [v, lam, fold, far, mpp, along, fu, fv, M.astype(f32), cross, gl] + ([beam] if beam is not None else [])
        for i_ in (0, 1, 2):          # the column renderer is not antialiased across columns: soften before cutting tones
            lst[i_] = cv2.GaussianBlur(np.asarray(lst[i_], f32), (0, 0), .8)
        if (h, w) != (Hh, Ww):
            lst = [cv2.resize(np.asarray(q, f32), (Ww, Hh), interpolation=cv2.INTER_LINEAR) for q in lst]
        v, lam, fold, far, mpp, along, fu, fv, Mf, cross, gl = lst[:11]
        bm = lst[11] if beam is not None else None
        bm = np.zeros((1, 1), f32) if bm is None else np.ascontiguousarray(bm, f32)
        P = lambda k, d: (rgb(pal[k]) if isinstance(pal[k], str) else np.asarray(pal[k], f32)) if k in pal else rgb(d)
        cols = np.stack([P('deep', '#16222b'), P('body', '#1c2a33'), P('face', '#2f4452'), P('sky_lo', '#5d6672'), P('foam', '#d8e2e6'),
                         P('foam_sh', '#8d9aa6'), P('beam', '#fff2d0'), rgb('#e8f0ff'), P('fog', '#5a5f6e') if fog_col is None else (rgb(fog_col) if isinstance(fog_col, str) else np.asarray(fog_col, f32)), P('glass', '#2f5652')]).astype(f32)
        thr = np.asarray(pal.get('thr', (.25, .36, .48)), f32)
        prm = np.array([crest_foam, streak, flash, fog_k[1] if fog_col is not None else 0., pal.get('bamt', .17), pal.get('foam_amt', 1.0)], f32)
        c = np.empty((Hh, Ww, 3), f32); foam = np.empty((Hh, Ww), f32)
        _tone(*(np.ascontiguousarray(a_, f32) for a_ in (v, lam, fold, far, mpp, along, fu, fv, Mf, cross, gl)), bm, T, cols, thr, prm, c, foam)
        return c, Mf, dict(foam=foam, far=far, lam=lam, mpp=mpp)


def beam_on_surface(G, lamp, dirs, half=.06, reach=1600., amt=1.0):
    """warm light where beam cones meet the sea surface.  dirs: list of unit horizontal beam directions"""
    px, py, pz = G['px'], G['py'], G['pz']
    out = np.zeros_like(px)
    for (dx, dy, dz) in dirs:
        vx = px - lamp[0]; vy = py - lamp[1]; vz = pz - lamp[2]
        al = vx * dx + vy * dy + vz * dz
        rx = vx - al * dx; ry = vy - al * dy; rz = vz - al * dz
        rr = np.sqrt(rx * rx + ry * ry + rz * rz)
        R = 1.2 + np.maximum(al, 0) * half
        k = np.clip(1 - (rr / R) ** 2, 0, 1) * (al > 0) / (1 + al / reach)
        out += k
    return np.clip(out * amt, 0, 1.5) * (G['z'] > 0)


# ============================================================================ rocks
def rock(w, h, top, seed=0, pal=('#1d2030', '#2a2e42', '#3c4157', '#5a6078', '#7c8299'), light=(-.6, -.8), cell=60, wet=.8, layer=True):
    """a painted sea rock: silhouette from `top` (polyline of the upper contour in sprite px, the rock fills
    below it), cut into facets that each take one tone from the light, then gone over with strokes along the
    facet and a few wet glints on the upper edges.  returns premultiplied RGBA (h, w, 4)."""
    from lp.cam import voronoi_crevice
    r = np.random.default_rng(seed)
    top = np.asarray(top, float)
    m = np.zeros((h, w), np.uint8)
    poly = np.vstack([top, [[top[-1, 0], h + 5], [top[0, 0], h + 5]]])
    cv2.fillPoly(m, [(poly * 4).astype(np.int32)], 255, cv2.LINE_AA, 2)
    A = m.astype(f32) / 255.
    yy, xx = np.mgrid[0:h, 0:w].astype(f32)
    wx = xx + fbm(h, w, (cell * .8, cell * .3), (1, .5), seed + 1) * cell * .25
    wy = yy + fbm(h, w, (cell * .8, cell * .3), (1, .5), seed + 2) * cell * .25
    cr, cid = voronoi_crevice(wx, wy, (cell * 1.25, cell * .75), seed=seed, jitter=.85)
    lab = (cid * 4000).astype(np.int32)
    # facet normal per cell: mostly tilted up (ledges), some vertical faces turned to or from the light
    tabn = r.normal(0, 1, (4001, 2)) * .45
    tabn[:, 1] -= .35
    nxm = tabn[lab, 0]; nym = tabn[lab, 1]
    lx, ly = np.asarray(light, float) / np.hypot(*light)
    # big form: the band under the top contour is the lit upper plane, deeper in is the dark wet face
    dist = cv2.distanceTransform((A > .5).astype(np.uint8), cv2.DIST_L2, 5).astype(f32)
    dn = dist + fbm(h, w, (cell * 1.5, cell * .5), (1, .5), seed + 3) * cell * .35
    big = cv2.GaussianBlur(A, (0, 0), max(4, cell * .6))
    gy = cv2.Sobel(big, cv2.CV_32F, 0, 1, ksize=5); gx = cv2.Sobel(big, cv2.CV_32F, 1, 0, ksize=5)
    gl = np.sqrt(gx * gx + gy * gy) + 1e-4
    side = np.clip(-(gx * lx + gy * ly) / gl, -1, 1)
    v = .50 * smooth(cell * 1.1, cell * .25, dn) * (.6 + .4 * side) + .10 * np.clip(nxm * lx + nym * ly, -1, 1) - .08
    v -= .20 * smooth(cell * 1.5, cell * 4, dn)
    v -= .25 * smooth(.08, .0, cr) * smooth(cell * .2, cell * .6, dist)              # crevices
    P = np.stack([rgb(c) for c in pal])
    t = np.clip(v + .38, 0, 1)
    idx = np.clip(t * (len(pal) - 1), 0, len(pal) - 1.001)
    i0 = idx.astype(int); fr = smooth(.4, .6, idx - i0)[..., None]
    col = P[i0] * (1 - fr) + P[i0 + 1] * fr
    ang = np.arctan2(nym, nxm) * .3 + np.pi * .5 * 0 + fbm(h, w, (cell, ), None, seed + 6) * .2
    out = repaint(col.astype(f32), (max(3., cell * .14), max(2., cell * .07)), seed=seed + 7, angle=ang.astype(f32), lab=lab, mask=A, thr=(0, .01), density=1.0, aspect=3.2,
                  jit=(.004, .014, .02), op=.85, dry=.2, curve=.3, bristle=.06)
    # wet glints along upper facet edges
    edge = smooth(.05, .0, cr) * smooth(.15, .4, v) * wet
    gl_ = np.clip(edge * (fbm(h, w, (12, 5), (1, .5), seed + 9) > .4), 0, 1)
    out = out + (rgb('#9aa3b8') - out) * (gl_ * .5)[..., None]
    out = out * A[..., None]
    return np.dstack([out, A]).astype(f32)


# ============================================================================ spray
def burst(cv_img, cx, cy, size, age, seed=0, wind=(1., 0.), col='#d8e2e6', shade='#8c98a6', life=1.6, up=1.0, n=60, mist=None, ang0=-np.pi / 2, tear=1.0, skew=0.0):
    """a wave smashing on rock: white water thrown up as a fan of tongues that arc over, break into drops at the
    tips, detach from the rock and fall downwind, while a veil of spray hangs and drifts.  age in seconds.
    Draws strokes on a Canvas layer; if `mist` (HxW float) is given, adds the veil there."""
    if age < 0 or age > life * 1.8: return cv_img
    r = np.random.default_rng(seed)
    T = life
    grow = 1 - math.exp(-age / .22)
    gpx = 2 * size / (.62 * T) ** 2            # the top is reached around .6 life
    c1, c2 = rgb(col), rgb(shade)
    # tongues
    ang = ang0 + (r.normal(0, .42, n) + skew * np.abs(r.normal(0, .42, n))) * up + .18 * wind[0]
    sp = r.uniform(.45, 1.0, n) ** .6
    v0 = gpx * .62 * T * sp
    vx = np.cos(ang) * v0; vy = np.sin(ang) * v0
    tt = (age + .12) * r.uniform(.9, 1.1, n)
    K = 7
    P = np.zeros((n, K, 2), f32)
    s0 = np.clip((tt - .30) / (T * .9), 0, .92)          # the base lets go of the rock after a beat
    for k in range(K):
        q = s0 + (1 - s0) * k / (K - 1)
        ts = tt * q
        P[:, k, 0] = cx + vx * ts + wind[0] * size * .18 * tear * ts ** 2
        P[:, k, 1] = cy + vy * ts + .5 * gpx * ts ** 2
    P[:, :, 0] += (r.normal(0, size * .07, n))[:, None]
    fade = np.clip(1 - (tt - T * .5) / (T * .9), 0, 1)
    wd = size * r.uniform(.035, .09, n) * (1 - .5 * s0) * (.5 + .5 * sp)
    keep = fade > .02
    if keep.any():
        t_ = np.clip(r.uniform(0, .5, n) + np.clip(-np.sin(ang), 0, 1) * 0 + (np.abs(ang + np.pi / 2) > .5) * .35, 0, 1)[:, None]
        C = c1 * (1 - t_) + c2 * t_
        cv_img.strokes(P[keep], wd[keep], C[keep].astype(f32), op=np.clip(fade[keep] * .82, 0, 1), dry=np.clip(.15 + .5 * s0[keep], 0, .9), seed=seed, shape='taper', bristle=.06)
    # drops at the tips
    m = n * 4
    i = r.integers(0, n, m)
    tq = tt[i] * r.uniform(.8, 1.15, m)
    dx = r.normal(0, size * .06, m) * (1 + 2 * tq); dy = r.normal(0, size * .05, m) * (1 + 2 * tq)
    x = cx + vx[i] * tq + wind[0] * size * .2 * tear * tq ** 2 + dx
    y = cy + vy[i] * tq + .5 * gpx * tq ** 2 + dy
    fd = np.clip(1 - (tq - T * .4) / (T * 1.0), 0, 1) * (tq > .06)
    rad = size * r.uniform(.002, .006, m) * (1 + tq)
    ok = fd > .03
    if ok.any():
        vyy = vy[i] + gpx * tq
        Pd = arcs(x[ok], y[ok], np.arctan2(vyy[ok], vx[i][ok] + wind[0] * size * tq[ok]), rad[ok] * 4.5, 0., K=3)
        cv_img.strokes(Pd, rad[ok], np.broadcast_to(c1, (ok.sum(), 3)), op=np.clip(fd[ok], 0, 1) * .9, seed=seed + 1, shape='round', bristle=.03)
    if mist is not None:
        h, w = mist.shape
        g = np.clip(age / .35, 0, 1) * np.clip(1 - (age - T * .4) / (T * 1.2), 0, 1)
        if g > 0:
            mx = cx + wind[0] * size * .25 * tear * age + wind[0] * size * .2 * tear * age * age; my = cy - size * (.45 + .25 * min(age, 1.2))
            R = size * (.35 + .45 * grow + .25 * age)
            x0, x1 = int(max(0, mx - R * 3.2)), int(min(w, mx + R * 3.2)); y0, y1 = int(max(0, my - R * 2.6)), int(min(h, my + R * 2.8))
            if x1 > x0 and y1 > y0:
                yy, xx = np.mgrid[y0:y1, x0:x1].astype(f32)
                nn = fbm(y1 - y0, x1 - x0, (R * .35 + 4, R * .12 + 2), (1, .5), seed + 7)
                e = np.exp(-(((xx - mx) / (R * 1.1)) ** 2 + ((yy - my) / (R * .85)) ** 2) * np.maximum(.4, 1 + .35 * nn))
                mist[y0:y1, x0:x1] = np.maximum(mist[y0:y1, x0:x1], np.clip(e * g * .75, 0, 1))
    return cv_img


def crest_spray(cv_img, foam, G, f, wind=(1., -.1), n=260, seed=0, scale=1.0, ymax=None, col='#d0dae0'):
    """spume torn off the crest tops by the wind: short tapered dry strokes leaving the foam downwind.
    foam: full-res hard-foam map; only near water (large drawing) gets it.  on twos."""
    h, w = foam.shape
    d = f // 2
    r = np.random.default_rng(seed + d * 31)
    sub = foam[::4, ::4]
    pz = cv2.resize(G['pz'], (w, h))[::4, ::4] if G['pz'].shape != foam.shape else G['pz'][::4, ::4]
    wgt = (sub > .5) * np.clip(pz - np.percentile(pz, 85), 0, None)
    if ymax is not None: wgt[int(ymax / 4):] = 0
    s = wgt.sum()
    if s <= 1e-3: return cv_img
    p = (wgt / s).ravel()
    k = r.choice(p.size, n, p=p)
    y = (k // sub.shape[1]) * 4. + r.uniform(0, 4, n); x = (k % sub.shape[1]) * 4. + r.uniform(0, 4, n)
    near = np.clip((y - h * .45) / (h * .55), .15, 1.0) * scale
    L = r.uniform(18, 70, n) * near
    ang = math.atan2(wind[1], wind[0]) + r.normal(-.25, .2, n)
    x = x + np.cos(ang) * L * .5; y = y + np.sin(ang) * L * .5 - L * .15
    P = arcs(x, y, ang, L, r.normal(.25, .2, n), K=5)
    c = rgb(col)
    cv_img.strokes(P, r.uniform(1.0, 3.2, n) * near, np.broadcast_to(c, (n, 3)), op=r.uniform(.3, .75, n), dry=r.uniform(.3, .8, n), seed=seed + d, shape='taper', bristle=.08)
    return cv_img


_SURF = {}


def surf(img, A, vis, f, seed=0, up=7, down=14, col='#cfd9de', amt=.9, swell=1.0):
    """white water at a rock's waterline: A = rock alpha, vis = 1 where the rock is in front of the sea.
    a band of foam just in front of the waterline and a wash a little way up the rock, both broken by a
    foam tile that churns on twos."""
    rv = A * vis; hid = A * (1 - vis)
    if hid.max() < .1: return img
    kd = np.ones((int(down * swell) + 1, 1), np.uint8)
    below = cv2.dilate(rv, kd, anchor=(0, kd.shape[0] - 1)) * hid
    ku = np.ones((int(up * swell) + 1, 1), np.uint8)
    above = cv2.dilate(hid, ku, anchor=(0, 0)) * rv
    if seed not in _SURF:
        _SURF[seed] = np.clip(fbm(512, 512, (14, 6, 2.5), (1, .6, .4), seed + 900) * .5 + .5, 0, 1).astype(f32)
    T = _SURF[seed]
    d = f // 2
    h, w = A.shape
    M = np.float32([[1, 0, -d * 7.], [0, 1, d * 3.]])
    n = cv2.warpAffine(T, M, (512, 512), borderMode=cv2.BORDER_WRAP)
    n = cv2.resize(np.tile(n, (h // 512 + 1, w // 512 + 1))[:h, :w], (w, h))
    m = np.clip(below * 1.1 + above * .8, 0, 1)
    m = cv2.GaussianBlur(m, (0, 0), 1.2)
    k = smooth(.35, .55, m * (.55 + .8 * n)) * amt
    c = rgb(col)
    return img + (c - img) * k[..., None]
