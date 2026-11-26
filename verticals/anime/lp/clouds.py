"""Painted cumulus and cloud seas.  A cloud is a stack of hand-placed lobes, each lobe painted with a
crisp sun edge and a lost shadow edge, then gone over with gouache strokes that follow the lobes."""
import numpy as np, math, cv2
from numba import njit
from .paint import f32, rgb, mix, _vn, Canvas, repaint, fbm, jit_color, arcs, smooth, lum


@njit(cache=True, fastmath=True)
def _lobes(img, A, ang, X, Y, RX, RY, TONE, lx, ly, crisp, fade, wob, S, op):
    """TONE[n,4,3]: light, halftone, shadow, deep.  lost lower edge via fade."""
    h, w = img.shape[0], img.shape[1]
    for i in range(X.shape[0]):
        cx = X[i]; cy = Y[i]; rx = RX[i]; ry = RY[i]; s = S[i]
        x0 = max(0, int(cx - rx * 1.25)); x1 = min(w - 1, int(cx + rx * 1.25) + 1)
        y0 = max(0, int(cy - ry * 1.25)); y1 = min(h - 1, int(cy + ry * 1.25) + 1)
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                dx = (x - cx) / rx; dy = (y - cy) / ry
                d = math.sqrt(dx * dx + dy * dy)
                if d > 1.25: continue
                th = math.atan2(dy, dx)
                n = _vn(math.cos(th) * 2.2 + 10, math.sin(th) * 2.2 + 10, s) * .6 + _vn(math.cos(th) * 5.5 + 30, math.sin(th) * 5.5 + 30, s + 1) * .4
                R = 1 + wob * (n - .5) * 2
                q = d / R
                if q >= 1.02: continue
                # crisp edge on sun side, soft on the other
                side = (dx * lx + dy * ly) / (d + 1e-6)
                ew = crisp + (fade - crisp) * (0.5 - 0.5 * side) ** 1.3
                ea = (1 - q) / ew
                if ea > 1: ea = 1.0
                if ea <= 0: continue
                ea = ea * ea * (3 - 2 * ea) if ew > .2 else ea
                # shading from a flattened sphere normal with painterly wobble
                nz = math.sqrt(max(0.0, 1 - q * q * .95))
                sh = (dx * lx + dy * ly) * .85 + nz * .22
                wn = _vn(x * .035, y * .045, 91) * .6 + _vn(x * .11, y * .13, 97) * .4
                sh += (wn - .5) * .55
                # 4 tones with short painted transitions
                t = (sh + .62) / 1.45 * 3
                if t < 0: t = 0.0
                if t > 3: t = 3.0
                k = int(t)
                if k > 2: k = 2
                fr = (t - k)
                fr = (fr - .28) / .44
                if fr < 0: fr = 0.0
                if fr > 1: fr = 1.0
                a0 = 3 - k; a1 = 2 - k
                a = ea * op[i]
                for c in range(3):
                    col = TONE[i, a0, c] * (1 - fr) + TONE[i, a1, c] * fr
                    img[y, x, c] += (col - img[y, x, c]) * a
                A[y, x] += (1 - A[y, x]) * a
                if a > .25:
                    ang[y, x] = th + 1.5708


def lobes(img, A, ang, L, tones, light=(.5, -.86), crisp=.035, fade=.9, wob=.075, seed=0, op=1.0):
    """L: (n,4) x,y,rx,ry.  tones: (4,3) or (n,4,3)"""
    L = np.asarray(L, f32); n = len(L)
    T = np.broadcast_to(np.asarray(tones, f32), (n, 4, 3)).copy()
    S = (np.arange(n) * 613 + seed * 977).astype(np.int64) & 0xffffff
    lx, ly = np.asarray(light, float) / np.hypot(*light)
    _lobes(img, A, ang, L[:, 0], L[:, 1], L[:, 2], L[:, 3], T, float(lx), float(ly), float(crisp), float(fade), float(wob), S,
           np.broadcast_to(np.asarray(op, f32), (n,)).copy())


def grow(x, y, rx, ry, r, levels=3, kids=(7, 6, 5), up=1.0, shrink=.5):
    """hierarchical lobes around a parent: children ride the upper rim"""
    out = [(x, y, rx, ry, 0)]
    front = [(x, y, rx, ry)]
    for lv in range(levels):
        nxt = []
        for (px, py, prx, pry) in front:
            k = kids[min(lv, len(kids) - 1)]
            for j in range(k):
                a = -math.pi / 2 + r.normal(0, 1.05) * up
                q = r.uniform(.62, 1.0)
                cx, cy = px + math.cos(a) * prx * q, py + math.sin(a) * pry * q
                s = shrink * r.uniform(.62, 1.25)
                nxt.append((cx, cy, prx * s, pry * s * r.uniform(.85, 1.1)))
        out += [(a, b, c, d, lv + 1) for a, b, c, d in nxt]
        front = nxt
    return out


def cumulus(img, A, ang, x, base, width, height, tones, r, light=(.5, -.86), n=9, crisp=.035, levels=3, seed=0, op=1.0, profile=None):
    """a standing cumulus mass: base line y=base, towering to base-height"""
    L = []
    for i in range(n):
        t = (i + .5) / n + r.normal(0, .03)
        env = math.sin(math.pi * np.clip(t, .02, .98)) ** .8 if profile is None else profile(t)
        hh = height * env * r.uniform(.55, 1.0)
        rx = width / n * r.uniform(.9, 1.6); ry = max(hh * .5, rx * .5)
        L += grow(x + (t - .5) * width, base - hh * .55, rx, ry, r, levels)
    L = np.array(L)
    # back to front: higher and bigger first, then small rim lobes, then low front lobes
    o = np.lexsort((L[:, 1], L[:, 4]))
    L = L[o]
    lobes(img, A, ang, L[:, :4], tones, light, crisp, .95, .08, seed, op)


def sea(img, horizon, bottom, tone_fn, r, rows=26, light=(.5, -.86), lobe=150, gap_fn=None, seed=0, xr=None, squash=.42, levels=2, crisp=.05):
    """sea of cloud from horizon down to bottom.  tone_fn(depth 0 far..1 near) -> (4,3) tones + mist rgb"""
    h, w = img.shape[:2]
    A = np.zeros((h, w), f32); ang = np.zeros((h, w), f32)
    xr = (-100, w + 100) if xr is None else xr
    for k in range(rows):
        d = ((k + .5) / rows)
        dep = d ** 2.1
        y = horizon + (bottom - horizon) * dep
        scale = .045 + .955 * dep ** .9
        R = lobe * scale
        tones, mist = tone_fn(d)
        m = int((xr[1] - xr[0]) / (R * 1.25)) + 1
        L = []
        ph = r.uniform(0, 100)
        for j in range(m):
            x = xr[0] + (j + r.uniform(-.4, .4)) * R * 1.25
            und = math.sin(x / (R * 7.3) + ph) * .5 + math.sin(x / (R * 2.9) + ph * 2.1) * .3
            if r.random() < .12: continue
            yy = y + und * R * .34 + r.normal(0, R * .12)
            rr = R * r.uniform(.55, 1.25) * (1 + .3 * max(0, -und))
            L += grow(x, yy, rr, rr * squash * r.uniform(.8, 1.25), r, levels, (5, 4), 1.1, .5)
        if not L: continue
        L = np.array(L); o = np.lexsort((L[:, 1], L[:, 4])); L = L[o]
        T = np.asarray(tones, f32)[None] * (1 + r.normal(0, .018, (len(L), 1, 1))).astype(f32)
        lobes(img, A, ang, L[:, :4], T, light, crisp, 1.0, .07, seed + k * 37)
        # mist pooled at the feet of this bank
        yy0 = int(max(0, y + R * .12)); yy1 = int(min(h, y + R * .95 + 3))
        if yy1 > yy0:
            t = np.linspace(0, 1, yy1 - yy0)[:, None, None]
            band = np.sin(np.pi * np.clip(t, 0, 1)) * .42
            img[yy0:yy1] += (np.asarray(mist, f32) - img[yy0:yy1]) * band.astype(f32)
    return A, ang


# =====================================================================================================
#  DESIGNED CLOUDS (use these).  A bank is built from tiers of domes in 2.5D, lit as one mass, then laid in
#  four gouache tones: crisp sunlit crowns, quiet smooth shadow, foot lost in mist.
#
#  USAGE
#      from lp import clouds
#      S = clouds.Sky(H, W, sky_rgb, light=(-.62, -.70, .36), seed=3)   # light: screen x, y(up is -), z(to viewer)
#      S.deck(676, ('#a5a3cc','#9a96c6','#8c8bc0'), ('#7f89c6','#5560a2','#39447f'), seed=2)   # calm rolling floor
#      S.strata(600, 640, n=40, cols=['#c9a2b8', '#9d97c6'])             # flat bars at the horizon
#      S.sea(horizon=676, bottom=1200, far=T_far, near=T_near, mist_far='#a5a3cc', mist_near='#4a5592', seed=1)
#      S.bank(x=430, base=735, width=520, height=150, tones=T_far, mist='#a5a3cc', detail=1.0, seed=7)   # one mass
#      S.mist(y=780, x=500, w=900, h=60, col='#8a90c8', amt=.6, seed=2)  # still pool of mist
#      img = S.paint(seed=5)                                             # gouache pass -> HxWx3
#      layer = clouds.bank_layer(1200, 700, 600, 640, 900, 420, T, '#f3d2ae', light=(.5,-.8,.3), seed=4)  # premult RGBA
#  tones = 4 colours (light, half, shadow, deep) as hex or rgb; T = clouds.tones('#fff1d4', '#f3c9a6', ...).
#  light: z < 0 = sun behind the clouds (rims only), e.g. dawn (.25, -.85, -.10).  lit=.22, half=.32, deep=.10 are the SHARES
#  of a mass painted in each tone: lower `lit` for quiet near masses.  Everything is seeded.  `detail` 0..1: crown lobes,
#  `soft`: edge softness px (near masses 1..2, with levels=3, ss=1), contrast: lobe modelling, pool: mist at the foot.
#  profile(t) 0..1 -> relative crown height, e.g. clouds.peak(.3) for a summit at 30 % of the width.
#  Transparent layer: S = clouds.Sky(H, W, under_rgb, light, layered=True); ...banks...; rgba = S.layer(S.paint(seed))
#  Full examples: shots/s1.py back_plate()/front_plate() (night), qa/t_dawn.py (sunrise).
# =====================================================================================================
def tones(*c):
    return np.stack([rgb(v) if isinstance(v, str) else np.asarray(v, f32) for v in c])


def peak(c=.5, w=.22, floor=.35, c2=None, h2=.6, w2=.16):
    """crown profile with one (or two) summits"""
    def p(t):
        e = floor + (1 - floor) * math.exp(-((t - c) / w) ** 2)
        if c2 is not None: e = max(e, floor + (h2 - floor) * math.exp(-((t - c2) / w2) ** 2))
        return e * (math.sin(math.pi * min(max(t, .03), .97)) ** .3)
    return p


@njit(cache=True, fastmath=True)
def _zsplat(Z, NX, NY, NZ, LV, X, Y, ZC, RX, RY, LEV, S, wob):
    h, w = Z.shape
    for i in range(X.shape[0]):
        cx = X[i]; cy = Y[i]; rx = RX[i]; ry = RY[i]; s = S[i]
        rz = min(rx, ry)
        x0 = max(0, int(cx - rx * 1.2)); x1 = min(w - 1, int(cx + rx * 1.2) + 1)
        y0 = max(0, int(cy - ry * 1.2)); y1 = min(h - 1, int(cy + ry * 1.2) + 1)
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                dx = (x - cx) / rx; dy = (y - cy) / ry
                d2 = dx * dx + dy * dy
                if d2 > 1.4: continue
                zt = ZC[i] + rz
                if zt <= Z[y, x]: continue
                d = math.sqrt(d2)
                c = dx / (d + 1e-6); sn = dy / (d + 1e-6)
                n = _vn(c * 1.9 + 10, sn * 1.9 + 10, s) * .62 + _vn(c * 4.6 + 30, sn * 4.6 + 30, s + 1) * .38
                q = d / (1 + wob * (n - .5) * 2)
                if q >= 1: continue
                nz = math.sqrt(1 - q * q)
                z = ZC[i] + rz * nz
                if z > Z[y, x]:
                    Z[y, x] = z
                    NX[y, x] = c * q; NY[y, x] = sn * q; NZ[y, x] = nz
                    LV[y, x] = LEV[i]


@njit(cache=True, fastmath=True)
def _cast(Z, lx, ly, lz, steps, step, soft):
    """screen-space shadow: 0 lit .. 1 fully shadowed"""
    h, w = Z.shape
    out = np.zeros((h, w), np.float32)
    for y in range(h):
        for x in range(w):
            z = Z[y, x]
            if z < -1e5: continue
            occ = 0.0
            for k in range(1, steps + 1):
                t = k * step
                xx = int(x + lx * t); yy = int(y + ly * t)
                if xx < 0 or yy < 0 or xx >= w or yy >= h: break
                dz = Z[yy, xx] - (z + lz * t) - step * .4
                if dz > 0:
                    o = dz / (soft + t * .25)
                    if o > occ: occ = o
                    if occ >= 1: break
            out[y, x] = occ if occ < 1 else 1.0
    return out


def heap(x, base, width, height, r, profile=None, tiers=3, n=5, levels=3, kids=(9, 8, 6), detail=1.0, bend=0.0):
    """sphere list (x, y, z, rx, ry, level) of one cumulus bank: tiers of domes, small crowns riding big ones"""
    prof = profile or peak(r.uniform(.3, .7), r.uniform(.2, .34), r.uniform(.3, .5), r.uniform(.1, .9), r.uniform(.5, .8))
    out = []
    r2 = np.random.default_rng(int(abs(x) * 13 + height * 7 + width * 3) % (2 ** 31))

    def dome(cx, cy, zc, rx, ry, r):
        out.append((cx, cy, zc, rx, ry, 0))
        if cy + ry * .4 < base:                           # body under the dome
            out.append((cx + r.normal(0, .15) * rx, (cy + base) / 2 + ry * .1, zc - .05 * height, rx * 1.15, max((base - cy) * .62, ry * .5), 0))
        front = [(cx, cy, zc, rx, ry)]
        for lv in range(levels):
            nxt = []
            kk = kids[min(lv, len(kids) - 1)] * (detail if lv > 0 else (.5 + .5 * detail))
            for (px, py, pz, prx, pry) in front:
                nk = int(kk + r.random())
                for j_ in range(nk):
                    a = -math.pi / 2 + ((j_ + r.uniform(.1, .9)) / nk - .5) * (3.7 if lv == 0 else 4.2)
                    el = r.uniform(.0, 1.0) ** (1.0 if lv == 0 else 1.9)    # 0 on the rim, 1 facing viewer
                    cr = math.cos(el * 1.2)
                    ux, uy, uz = math.cos(a) * cr, math.sin(a) * cr, math.sin(el * 1.2)
                    s = (r.uniform(.26, .52) if lv == 0 else r.uniform(.24, .5)) * (1 - .12 * lv)
                    ko = r.uniform(.66, .92)
                    rp = min(prx, pry)
                    crx = (prx * .5 + rp * .5) * s * r.uniform(.95, 1.25); cry = (pry * .5 + rp * .5) * s
                    nxt.append((px + ux * prx * ko, py + uy * pry * ko, pz + uz * rp * ko, crx, cry))
            out.extend((a_, b_, c_, d_, e_, lv + 1) for a_, b_, c_, d_, e_ in nxt)
            r.shuffle(nxt)
            front = [v for v in nxt if v[3] > 3.2]
            if not front: break

    for k in range(tiers):
        q = k / max(1, tiers - 1)                         # 0 back (tall) .. 1 front (low)
        hh = height * (1 - .62 * q)
        m = max(2, int(round(n * (1 + .35 * q))))
        ph = r.uniform(-.3, .3) / m
        for j in range(m):
            t = (j + .5) / m + ph + r.normal(0, .18 / m)
            e = prof(min(max(t, 0.), 1.)) * r.uniform(.78, 1.06)
            if q > 0: e = .55 * e + .45 * r.uniform(.35, .95)
            top = base - hh * e + bend * (t - .5) ** 2 * height
            rx = width / m * r.uniform(.48, .86)
            ry = min(max(rx * r.uniform(.62, .9), hh * e * .42), hh * e * .95 + 4)
            rx = min(rx, ry * 1.9)
            cx = x + (t - .5) * width * (1 + .05 * q); cy = top + ry
            zc = q * height * .95 + r.normal(0, .06) * height
            dome(cx, cy, zc, rx, ry, r)
            if k == 0 and e > .55 and hh * e > rx * 1.5:  # shoulders, so a summit is a cauliflower and not a chimney
                for sd in (-1, 1):
                    for (dxs, dh) in ((r2.uniform(.75, 1.0), r2.uniform(.66, .82)), (r2.uniform(1.25, 1.7), r2.uniform(.36, .58))):
                        sx = rx * r2.uniform(.62, .9); sy = min(sx * r2.uniform(.8, 1.0), hh * e * dh * .5)
                        dome(cx + sd * rx * dxs, base - hh * e * dh + sy, zc + r2.uniform(.02, .16) * height, sx, sy, r2)
    return np.array(out, np.float64)


def shade(L, x0, y0, w, h, base, height, T, mist, light=(-.62, -.70, .36), seed=0, ss=2, detail=1.0, soft=0.0, foot=.42,
          rim=None, rim_amt=.0, shadow=.85, wob=.1, lost=.8, contrast=1.0, lit=.22, half=.32, deep=.10):
    """lay a sphere list in four gouache tones.  returns straight rgb, alpha, stroke angle (ROI x0,y0,w,h)"""
    lv = np.asarray(light, float); lv = lv / np.linalg.norm(lv)
    sh, sw = int(h * ss), int(w * ss)
    Z = np.full((sh, sw), -1e6, f32); NX = np.zeros((sh, sw), f32); NY = np.zeros_like(NX); NZ = np.zeros_like(NX); LV = np.zeros_like(NX)
    n = len(L)
    _zsplat(Z, NX, NY, NZ, LV, ((L[:, 0] - x0) * ss).astype(f32), ((L[:, 1] - y0) * ss).astype(f32), (L[:, 2] * ss).astype(f32),
            (L[:, 3] * ss).astype(f32), (L[:, 4] * ss).astype(f32), L[:, 5].astype(f32), (np.arange(n) * 613 + seed * 977).astype(np.int64) & 0xffffff, wob)
    M = (Z > -1e5)
    if not M.any(): return None
    Mf = M.astype(f32)
    # big form: normalised blur of depth
    zf = np.where(M, Z, 0)
    sg = max(3., height * ss * .06)
    def nb(a, s):
        q = max(1, int(s / 4))
        if q > 1:
            aa = cv2.resize(a, (max(1, sw // q), max(1, sh // q)), interpolation=cv2.INTER_AREA); mm = cv2.resize(Mf, (aa.shape[1], aa.shape[0]), interpolation=cv2.INTER_AREA)
            o = cv2.GaussianBlur(aa, (0, 0), s / q) / (cv2.GaussianBlur(mm, (0, 0), s / q) + 1e-3)
            return cv2.resize(o, (sw, sh), interpolation=cv2.INTER_LINEAR)
        return cv2.GaussianBlur(a, (0, 0), s) / (cv2.GaussianBlur(Mf, (0, 0), s) + 1e-3)
    zb = nb(zf, sg)
    bx = nb(NX * Mf, sg * 1.1); by = nb(NY * Mf, sg * 1.1); bz = nb(NZ * Mf, sg * 1.1)
    bl = np.sqrt(bx * bx + by * by + bz * bz) + 1e-4
    vb = (bx * lv[0] + by * lv[1] + bz * lv[2]) / bl
    vl = NX * lv[0] + NY * lv[1] + NZ * lv[2]
    q = 2
    Zs = cv2.resize(Z, (max(1, sw // q), max(1, sh // q)), interpolation=cv2.INTER_NEAREST)
    st = max(2., height * ss / q * .045)
    cs = _cast(Zs, float(lv[0]), float(lv[1]), float(lv[2]), 16, float(st), float(height * ss / q * .10))
    cs = cv2.GaussianBlur(cs, (0, 0), max(.8, height * ss / q * (.018 + .012 * soft)))
    cs = cv2.resize(cs, (sw, sh), interpolation=cv2.INTER_LINEAR)
    cav = np.clip((zb - Z) / (height * ss * .16), -1, 1) * Mf      # >0 in crevices
    yy = (np.arange(sh, dtype=f32)[:, None] / ss + y0)
    up = np.clip((base - yy) / max(height, 1), 0, 1.2)             # 0 foot .. 1 crown
    lz = smooth(-.15, .5, vb * .8 + .2 * (up - .4))
    v = .62 * vb + (.14 + .34 * lz) * (vl - vb * .5) * contrast * (.45 + .55 * detail)
    v = v + .30 * (up - .45)
    v = v - shadow * .42 * cs - .07 * np.clip(cav, 0, 1) + .05 * np.clip(-cav, 0, 1)
    wn = fbm(sh, sw, (46 * ss, 17 * ss, 7 * ss), (1, .6, .4), seed + 5)
    v = v + .035 * wn * (1 - .4 * lz)
    if soft > 0: v = cv2.GaussianBlur(v, (0, 0), soft * ss * 1.6)
    T = np.asarray(T, f32)
    # tone areas are DESIGNED: fixed shares of the mass above the foot (lit, half, shadow, deep)
    smp = v[::3, ::3][(M[::3, ::3]) & (np.broadcast_to(up, v.shape)[::3, ::3] > foot * .55)]
    if smp.size < 20: smp = v[M]
    if soft > 0 or True:
        p_hi, p_lit, p_half, p_deep = np.percentile(smp, [100 - lit * 38, 100 * (1 - lit), 100 * (1 - lit - half), 100 * deep])
    sd = max(1e-3, p_lit - p_half)
    def tone(th, s): return smooth(th - s, th + s, v)[..., None]
    c = T[3] + (T[2] - T[3]) * tone(p_deep, sd * .55)
    c = c + (T[1] - c) * tone(p_half, sd * (.30 + .12 * soft))
    c = c + (T[0] - c) * tone(p_lit, sd * (.13 + .12 * soft))
    c = c + (np.minimum(T[0] * 1.06, 1.0) - c) * tone(p_hi, sd * .2) * .7
    # alpha
    a = Mf.copy()
    if rim_amt > 0:
        sx = -lv[0] * 2.2 * ss; sy = -lv[1] * 2.2 * ss
        Ms = cv2.warpAffine(Mf, np.float32([[1, 0, sx], [0, 1, sy]]), (sw, sh))
        rr = np.clip(Mf - Ms, 0, 1) * smooth(.25, .6, up) * smooth(-.6, .9, wn)
        rr = cv2.GaussianBlur(rr, (0, 0), .7 * ss)
        rc = T[0] * 1.05 if rim is None else (rgb(rim) if isinstance(rim, str) else np.asarray(rim, f32))
        c = c + (rc - c) * (rr * rim_amt)[..., None]
    if ss > 1:
        c = cv2.resize(c * a[..., None], (w, h), interpolation=cv2.INTER_AREA); a = cv2.resize(a, (w, h), interpolation=cv2.INTER_AREA)
        c = c / np.maximum(a, 1e-3)[..., None]
        bxs, bys, vs = [cv2.resize(m, (w, h), interpolation=cv2.INTER_AREA) for m in (bx * .5 + NX * .5, by * .5 + NY * .5, v)]
    else:
        bxs, bys, vs = bx * .5 + NX * .5, by * .5 + NY * .5, v
    # lost edges: on the dark side the silhouette melts, on the light side it stays cut
    s2 = max(1.5, height * .022) + soft * 2
    ab = cv2.GaussianBlur(a, (0, 0), s2)
    ls = np.clip(lost * smooth(p_half + sd * .35, p_half - sd * .7, vs + sd * .35 * fbm(h, w, (60, 24), (1, .5), seed + 8)), 0, 1)
    if soft > 0: ls = np.maximum(ls, min(1., soft * .12))
    a = a * (1 - ls) + np.minimum(a, np.clip(ab * 2 - .75, 0, 1)) * ls
    # foot dissolves in mist
    yy = np.arange(h, dtype=f32)[:, None] + y0
    fn = fbm(h, w, (height * .5 + 12, height * .2 + 6), (1, .5), seed + 12, aspect=3.2)
    ft = smooth(base - height * foot * 1.15, base - height * foot * .08, yy + fn * height * .045)
    mc = rgb(mist) if isinstance(mist, str) else np.asarray(mist, f32)
    c = c + (mc - c) * (ft ** 1.1)[..., None]
    a = a * (1 - smooth(base - height * foot * .35, base + 1, yy + fn * height * .035))
    ang = np.arctan2(bys, bxs + 1e-5) + np.pi / 2
    return c.astype(f32), np.clip(a, 0, 1).astype(f32), ang.astype(f32)


def bank_roi(x, base, width, height, T, mist, light=(-.62, -.70, .36), seed=0, profile=None, detail=1.0, tiers=3, n=5, levels=3, pad=.25, **kw):
    r = np.random.default_rng(seed * 7919 + 13)
    L = heap(x, base, width, height, r, profile, tiers, n, levels, detail=detail)
    x0 = int(min((L[:, 0] - L[:, 3]).min(), x - width / 2) - 12); x1 = int(max((L[:, 0] + L[:, 3]).max(), x + width / 2) + 12)
    y0 = int((L[:, 1] - L[:, 4]).min() - 12); y1 = int(base + 4)
    return L, x0, y0, x1 - x0, y1 - y0


def bank_layer(h, w, x, base, width, height, T, mist, light=(-.62, -.70, .36), seed=0, profile=None, detail=1.0, tiers=3, n=5, levels=3, ss=2, **kw):
    """one bank as a premultiplied RGBA layer of size h x w (no gouache pass)"""
    S = Sky(h, w, rgb(mist) if isinstance(mist, str) else mist, light, layered=True)
    S.bank(x, base, width, height, T, mist, seed=seed, profile=profile, detail=detail, tiers=tiers, n=n, levels=levels, ss=ss, **kw)
    return S.layer()


@njit(cache=True, fastmath=True)
def _deck(h, w, hz, cx, K, sx, seed, lx, lz):
    """perspective swell field: (value, slope toward the light)"""
    out = np.zeros((h, w), np.float32); slo = np.zeros((h, w), np.float32)
    for y in range(h):
        d = y - hz
        if d < .75: continue
        Z = K / d
        dZ = K / (d * d)                        # metres per px in depth
        for x in range(w):
            X = (x - cx) * Z * sx
            v = 0.0; g = 0.0; amp = 1.0; fr = 1.0
            for o in range(4):
                px = 1.0 / (fr * dZ + 1e-9)     # depth wavelength in px
                at = (px - 1.2) / 5.0
                if at <= 0: break
                if at > 1: at = 1.0
                a = X * fr + o * 17.3; b = Z * fr * 1.25 + o * 9.1
                # slow warp so swells meander
                wa = _vn(a * .31 + 3, b * .31 + 8, seed + 40 + o) * 1.6
                n = _vn(a + wa, b - wa, seed + o); n2 = _vn(a + wa + lx * .30, b - wa + lz * .30, seed + o)
                n = 1 - abs(2 * n - 1); n2 = 1 - abs(2 * n2 - 1)
                n = n * n * (3 - 2 * n); n2 = n2 * n2 * (3 - 2 * n2)
                v += amp * at * (n - .5); g += amp * at * (n - n2)
                amp *= .52; fr *= 2.07
            out[y, x] = v; slo[y, x] = g
    return out, slo


class Sky:
    """cloud painting built back to front.  img guide, A alpha (1 everywhere unless layered), cov cloud coverage,
    ang stroke direction, lab paint-edge labels.  layered=True starts transparent: use .layer(painted) for premult RGBA."""

    def __init__(self, h, w, sky, light=(-.62, -.70, .36), seed=0, layered=False):
        self.h, self.w = h, w
        sky = rgb(sky) if isinstance(sky, str) else np.asarray(sky, f32)
        self.img = np.broadcast_to(sky, (h, w, 3)).copy() if sky.ndim == 1 else np.array(sky, f32, order='C')
        self.A = np.zeros((h, w), f32) if layered else np.ones((h, w), f32)
        self.cov = np.zeros((h, w), f32)
        self.ang = np.zeros((h, w), f32) + fbm(h, w, (200,), None, seed + 3) * .06
        self.lab = np.zeros((h, w), np.int32); self.soft = np.zeros((h, w), f32)
        self.light = light; self.seed = seed; self.k = 0; self.layered = layered

    def _comp(self, dl, c, a):
        """straight-alpha over, works for opaque and layered paintings"""
        if not self.layered:
            d = self.img[dl]; d += (c - d) * a[..., None]; return
        A0 = self.A[dl]; A1 = A0 + a - A0 * a
        k = np.where(A1 > 1e-4, a / np.maximum(A1, 1e-4), 0)[..., None]
        d = self.img[dl]; d += (c - d) * k
        self.A[dl] = A1

    def bank(self, x, base, width, height, T, mist, seed=0, profile=None, detail=1.0, tiers=3, n=5, levels=3, ss=2, pool=.5, light=None, op=1.0, **kw):
        lt = self.light if light is None else light
        T = tones(*T) if isinstance(T[0], str) else np.asarray(T, f32)
        L, x0, y0, rw, rh = bank_roi(x, base, width, height, T, mist, lt, seed, profile, detail, tiers, n, levels)
        cx0, cy0 = max(x0, -40), max(y0, -40); cx1, cy1 = min(x0 + rw, self.w + 40), min(y0 + rh, self.h + 40)
        if cx1 - cx0 < 4 or cy1 - cy0 < 4: return self
        res = shade(L, cx0, cy0, cx1 - cx0, cy1 - cy0, base, height, T, mist, lt, seed, ss, detail, **kw)
        if res is None: return self
        c, a, an = res
        a = a * op
        self.k += 1
        X0, Y0 = max(0, cx0), max(0, cy0); X1, Y1 = min(self.w, cx1), min(self.h, cy1)
        if X1 <= X0 or Y1 <= Y0: return self
        sl = (slice(Y0 - cy0, Y1 - cy0), slice(X0 - cx0, X1 - cx0)); dl = (slice(Y0, Y1), slice(X0, X1))
        c, a, an = c[sl], a[sl], an[sl]
        self._comp(dl, c, a)
        self.cov[dl] = np.maximum(self.cov[dl], a)
        self.ang[dl] = np.where(a > .3, an, self.ang[dl])
        self.lab[dl] = np.where(a > .5, self.k, self.lab[dl])
        self.soft[dl] = np.where(a > .5, kw.get('soft', 0.), self.soft[dl])
        if pool > 0: self.mist(base - height * .02, x, width * 1.15, height * .30, mist, pool, seed + 50)
        return self

    def mist(self, y, x, w, h, col, amt=.5, seed=0):
        """soft horizontal pool of mist"""
        col = rgb(col) if isinstance(col, str) else np.asarray(col, f32)
        y0, y1 = max(0, int(y - h * 2)), min(self.h, int(y + h * 2)); x0, x1 = max(0, int(x - w * .75)), min(self.w, int(x + w * .75))
        if y1 <= y0 or x1 <= x0: return self
        yy = np.arange(y0, y1, dtype=f32)[:, None]; xx = np.arange(x0, x1, dtype=f32)[None]
        n = fbm(y1 - y0, x1 - x0, (h * 1.2 + 6, h * .5 + 4), (1, .5), seed + 1, aspect=4.0)
        g = np.exp(-(((yy - y) / (h * .8)) + n * .22) ** 2) * np.clip(1 - np.abs((xx - x) / (w * .62)) ** 2.4, 0, 1)
        a = (np.clip(g * amt * (1 + .18 * n), 0, 1) * np.clip((2 - np.abs(yy - y) / h) * 1.6, 0, 1)).astype(f32)
        dl = (slice(y0, y1), slice(x0, x1))
        self._comp(dl, np.broadcast_to(col, a.shape + (3,)), a)
        return self

    def layer(self, painted=None):
        c = self.img if painted is None else painted
        return np.dstack([c * self.A[..., None], self.A])

    def strata(self, y0, y1, n=40, cols=('#c9a2b8', '#9d97c6'), seed=0, x=None, w=(.06, .34), th=(.8, 3.2), op=(.3, .8), power=1.6):
        """flat cloud bars, thin and long near y0 (horizon), thicker toward y1"""
        r = np.random.default_rng(seed + 71)
        cv = Canvas(self.h, self.w, img=self.img)
        x = (0, self.w) if x is None else x
        for i in range(n):
            q = r.uniform(0, 1) ** power
            yy = y0 + (y1 - y0) * q
            L = self.w * r.uniform(*w) * (.45 + .55 * q); cx = r.uniform(*x)
            c = rgb(cols[r.integers(len(cols))]) if isinstance(cols[0], str) else np.asarray(cols[r.integers(len(cols))], f32)
            K = 7; t = np.linspace(-.5, .5, K)
            P = np.stack([cx + t * L, yy + np.cumsum(r.normal(0, .35, K)) * (1 + 2 * q)], -1)[None]
            cv.strokes(P, r.uniform(*th) * (.5 + 1.2 * q), np.clip(c * (1 + r.normal(0, .02)), 0, 1)[None], op=r.uniform(*op), dry=.12 * r.random(), seed=seed + i, shape='round', bristle=.03)
        self.img = cv.img
        return self

    def deck(self, horizon, cols_far, cols_near, seed=0, scale=1.0, amt=1.0, cx=None, sx=1.0, light=(-.8, .6), fade=.10, focal=1900.):
        """the calm cloud floor between banks: soft rolling swells in perspective, three quiet tones.
        cols_* = (lit, half, shadow) hex/rgb at the horizon and at the bottom edge.  scale>1 = bigger swells"""
        f3 = np.stack([rgb(c) if isinstance(c, str) else np.asarray(c, f32) for c in cols_far]); n3 = np.stack([rgb(c) if isinstance(c, str) else np.asarray(c, f32) for c in cols_near])
        cx = self.w * .55 if cx is None else cx
        v, g = _deck(self.h, self.w, float(horizon), float(cx), focal / scale, float(sx) / focal, seed, light[0], light[1])
        y = np.arange(self.h, dtype=f32)[:, None]
        q = np.clip((y - horizon) / (self.h - horizon), 0, 1)
        s = .55 * v + 1.25 * g + .03 * fbm(self.h, self.w, (40, 14), (1, .5), seed + 3, aspect=2.5)
        s = s * amt
        t = q ** .6
        c = [(f3[i] + (n3[i] - f3[i]) * t[..., None]) for i in range(3)]
        out = c[2] + (c[1] - c[2]) * smooth(-.42, -.02, s)[..., None]
        out = out + (c[0] - out) * smooth(.08, .46, s)[..., None]
        m = smooth(horizon - 1, horizon + fade * (self.h - horizon) * .2 + 2, y)[..., None]
        self.img = self.img * (1 - m) + out.astype(f32) * m
        return self

    def sea(self, horizon, bottom, far, near, mist_far, mist_near, seed=0, rows=10, size=.42, cover=.78, x=None, calm=None, detail=1.0, near_soft=1.0, gap=1.5, **kw):
        """a whole sea of cloud in perspective: row spacing and size shrink geometrically toward the horizon.
        size = bank height / distance below the horizon.  calm(x, y) -> 0..1 chance to leave a quiet mist lake."""
        far = np.asarray(far, f32); near = np.asarray(near, f32)
        mf = rgb(mist_far) if isinstance(mist_far, str) else np.asarray(mist_far, f32); mn = rgb(mist_near) if isinstance(mist_near, str) else np.asarray(mist_near, f32)
        r = np.random.default_rng(seed * 31 + 7)
        x = (-.06 * self.w, 1.06 * self.w) if x is None else x
        D = bottom - horizon
        ys = [D * (.016 ** (1 - k / (rows - 1.))) for k in range(rows)]
        for k, dy in enumerate(ys):
            q = (dy / D); y = horizon + dy
            tq = q ** .55
            T = far + (near - far) * tq; m = mf + (mn - mf) * tq
            cx = x[0] + r.uniform(-1, 1) * dy
            while cx < x[1]:
                wd = dy * r.uniform(1.6, 4.4) + 26
                hh = dy * size * r.uniform(.6, 1.35) + 3
                by = y + r.normal(0, .10) * dy
                if r.random() < cover and not (calm is not None and r.random() < calm(cx + wd / 2, by)):
                    dt = detail * (1 - .35 * smooth(.45, 1.0, q) * near_soft)
                    self.bank(cx + wd / 2, by + hh * .35, wd * 1.1, hh, T * (1 + r.normal(0, .012)), m, seed=seed * 100 + self.k, detail=float(dt), levels=3 if hh > 26 else 2 if hh > 9 else 1,
                              tiers=3 if hh > 14 else 2, n=int(np.clip(wd / max(hh, 1) * .95, 4, 9)), soft=float(near_soft * 1.5 * smooth(.35, 1.0, q)), ss=2 if q < .6 else 1, **kw)
                cx += wd * r.uniform(.75, gap)
            self.mist(y + dy * .10, self.w * .5 + r.uniform(-.3, .3) * self.w, self.w * 1.5, dy * .12 + 1.5, m, .28, seed + k)
        return self

    def paint(self, seed=1, sizes=(13, 6.5, 3.4), amt=.8, jit=(.004, .012, .010), thr=(0, .010, .014), density=1.05, op=.85, mask=None, **kw):
        """gouache pass: small strokes that follow the lobes, never crossing a bank's silhouette"""
        a = self.ang + fbm(self.h, self.w, (70,), None, seed + 1) * .22
        out = repaint(self.img, sizes, seed=seed, angle=a, lab=self.lab, thr=thr, density=density, aspect=3.4, jit=jit, op=op, dry=.14, curve=.7, bristle=.03, mask=mask, **kw)
        # keep calm, soft areas calmer
        k = amt * (1 - .35 * np.clip(self.soft / 3, 0, 1))[..., None]
        return self.img * (1 - k) + out * k
