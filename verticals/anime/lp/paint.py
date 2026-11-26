"""Gouache paint engine.  Float32 RGB in 0..1, display space, deterministic.

The unit of everything is a brush mark: a curved, bristled, tapered flat-brush
stroke rasterised by distance to a polyline.  Nothing here blurs to hide form.
"""
import numpy as np, cv2, math
from numba import njit, prange
from . import W, H

f32 = np.float32


# ------------------------------------------------------------------ colour
def rgb(h):
    h = h.lstrip('#')
    return np.array([int(h[i:i + 2], 16) / 255. for i in (0, 2, 4)], f32)


def mix(a, b, t):
    return a * (1 - t) + b * t


def smooth(a, b, x):
    t = np.clip((x - a) / (b - a + 1e-9), 0, 1)
    return t * t * (3 - 2 * t)


def lum(img):
    return img[..., 0] * .299 + img[..., 1] * .587 + img[..., 2] * .114


def ramp(t, stops):
    """t array -> colour.  stops = [(pos, '#hex'|rgb), ...]"""
    ps = np.array([s[0] for s in stops], f32)
    cs = np.stack([rgb(s[1]) if isinstance(s[1], str) else np.asarray(s[1], f32) for s in stops])
    t = np.asarray(t, f32)
    out = np.empty(t.shape + (3,), f32)
    for c in range(3):
        out[..., c] = np.interp(t, ps, cs[:, c])
    return out


def grid(h=H, w=W):
    y, x = np.mgrid[0:h, 0:w].astype(f32)
    return x, y


# ------------------------------------------------------------------- noise
def fbm(h, w, scales=(72, 26, 10.5, 4.5), weights=None, seed=0, aspect=1.0):
    """zero-mean unit-variance bicubic-upsampled gaussian noise"""
    r = np.random.default_rng(seed)
    if weights is None:
        weights = [0.55 ** i for i in range(len(scales))]
    out = np.zeros((h, w), f32)
    for s, wt in zip(scales, weights):
        gh, gw = max(2, int(h / s) + 3), max(2, int(w / (s * aspect)) + 3)
        g = r.standard_normal((gh, gw)).astype(f32)
        M = np.array([[w / (gw - 1.), 0, 0], [0, h / (gh - 1.), 0]], f32)
        up = cv2.resize(g, (w, h), interpolation=cv2.INTER_CUBIC)
        out += wt * up
    out -= out.mean()
    out /= out.std() + 1e-6
    return out


def warp_by(img, amp, scale=40, seed=0, border=cv2.BORDER_REFLECT_101):
    """hand-cut edge: displace an image by smooth noise"""
    h, w = img.shape[:2]
    x, y = grid(h, w)
    nx = fbm(h, w, (scale, scale * .35), (1, .45), seed)
    ny = fbm(h, w, (scale, scale * .35), (1, .45), seed + 1)
    return cv2.remap(img, x + nx * amp, y + ny * amp, cv2.INTER_LINEAR, borderMode=border)


# ------------------------------------------------------- brush rasteriser
@njit(cache=True, fastmath=True)
def _h2(ix, iy, s):
    n = (ix * 374761393 + iy * 668265263 + s * 1274126177) & 0xffffffff
    n = ((n ^ (n >> 13)) * 1274126177) & 0xffffffff
    return ((n ^ (n >> 16)) & 0xffff) / 65535.0


@njit(cache=True, fastmath=True)
def _vn(x, y, s):
    ix = int(math.floor(x)); iy = int(math.floor(y))
    fx = x - ix; fy = y - iy
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy)
    a = _h2(ix, iy, s); b = _h2(ix + 1, iy, s); c = _h2(ix, iy + 1, s); d = _h2(ix + 1, iy + 1, s)
    return (a + (b - a) * fx) * (1 - fy) + (c + (d - c) * fx) * fy


@njit(cache=True, fastmath=True)
def _strokes(img, alpha, P, WD, COL, OP, DRY, SEED, lab, LAB, hasA, shape, K, bristle):
    """Sequential painter.  P[n,K,2] polylines, WD[n] half width, COL[n,3].
    lab: int32 label image or size 0; LAB[n] label the stroke belongs to (-1 free).
    shape: 0 flat brush, 1 round brush (tapered both ends), 2 leaf, 3 taper-out."""
    h, w = img.shape[0], img.shape[1]
    n = P.shape[0]
    useL = lab.shape[0] > 0
    for i in range(n):
        hw = WD[i]
        x0 = 1e9; y0 = 1e9; x1 = -1e9; y1 = -1e9
        tot = 0.0
        for k in range(K):
            px = P[i, k, 0]; py = P[i, k, 1]
            if px < x0: x0 = px
            if px > x1: x1 = px
            if py < y0: y0 = py
            if py > y1: y1 = py
            if k > 0:
                tot += math.sqrt((px - P[i, k - 1, 0]) ** 2 + (py - P[i, k - 1, 1]) ** 2)
        if tot < 0.5: tot = 0.5
        m = hw + 2
        ix0 = max(0, int(x0 - m)); ix1 = min(w - 1, int(x1 + m) + 1)
        iy0 = max(0, int(y0 - m)); iy1 = min(h - 1, int(y1 + m) + 1)
        if ix0 > ix1 or iy0 > iy1: continue
        s = SEED[i]
        op = OP[i]; dry = DRY[i]
        cr = COL[i, 0]; cg = COL[i, 1]; cb = COL[i, 2]
        for y in range(iy0, iy1 + 1):
            for x in range(ix0, ix1 + 1):
                if useL and LAB[i] >= 0 and lab[y, x] != LAB[i]: continue
                best = 1e18; bt = 0.0; bs = 0.0
                acc = 0.0
                for k in range(K - 1):
                    ax = P[i, k, 0]; ay = P[i, k, 1]
                    dx = P[i, k + 1, 0] - ax; dy = P[i, k + 1, 1] - ay
                    L2 = dx * dx + dy * dy + 1e-9
                    L = math.sqrt(L2)
                    tr = ((x - ax) * dx + (y - ay) * dy) / L2
                    t = tr
                    if k > 0 and t < 0: t = 0.0
                    if k < K - 2 and t > 1: t = 1.0
                    if shape != 0:
                        if t < 0: t = 0.0
                        if t > 1: t = 1.0
                    qx = ax + dx * t - x; qy = ay + dy * t - y
                    d2 = qx * qx + qy * qy
                    if d2 < best:
                        best = d2
                        bt = (acc + t * L) / tot
                        side = (x - ax) * dy - (y - ay) * dx
                        bs = math.sqrt(d2)
                        if side < 0: bs = -bs
                    acc += L
                if shape == 0:
                    wloc = hw
                    end_j = 0.10 * (_vn(bs / hw * 3.1 + 50, i * 0.37, s) - .5) + hw / tot * 0.25
                    e = min(bt + 0.02 + end_j, 1.02 - bt + end_j)
                    ea = e * tot / 1.6 + 0.4
                elif shape == 1:
                    tt = min(1.0, max(0.0, bt))
                    wloc = hw * (0.35 + 0.65 * math.sqrt(max(0.0, math.sin(3.14159 * (0.06 + .88 * tt)))))
                    ea = 1.0
                elif shape == 2:
                    tt = min(1.0, max(0.0, bt))
                    wloc = hw * max(0.0, math.sin(3.14159 * tt ** 0.75)) ** 0.8 + 0.15
                    ea = 1.0
                else:
                    tt = min(1.0, max(0.0, bt))
                    wloc = hw * (1 - tt) ** 0.7 + 0.25
                    ea = 1.0
                if ea <= 0: continue
                if ea > 1: ea = 1.0
                au = abs(bs)
                # ragged edge
                rag = (_vn(bt * tot / (3.0 + hw * .5), 7.0 if bs > 0 else 19.0, s) - .5) * min(1.6, hw * .28)
                a = (wloc + rag - au) / 1.15 + 0.5
                if a <= 0: continue
                if a > 1: a = 1.0
                a *= ea
                u = bs / (hw + 1e-6)
                # bristle streaks
                br = _vn(u * (3.0 + hw * 0.42), bt * tot / (hw * 4 + 10), s + 3)
                br2 = _vn(u * (7.0 + hw * 0.9), bt * tot / (hw * 7 + 14), s + 5)
                b = (br * .62 + br2 * .38 - .5) * 2
                if dry > 0:
                    thr = dry * (0.25 + 1.0 * bt)
                    k2 = (0.5 + b * .5 - thr * .78) * 5 + .5
                    if k2 < 0: k2 = 0.0
                    if k2 > 1: k2 = 1.0
                    a *= k2
                a *= op
                if a <= 0.003: continue
                v = 1 + b * bristle
                r_ = cr * v; g_ = cg * v; b_ = cb * v
                img[y, x, 0] += (r_ - img[y, x, 0]) * a
                img[y, x, 1] += (g_ - img[y, x, 1]) * a
                img[y, x, 2] += (b_ - img[y, x, 2]) * a
                if hasA:
                    alpha[y, x] += (1 - alpha[y, x]) * a


_NOLAB = np.zeros((0, 0), np.int32)
_NOA = np.zeros((1, 1), f32)


class Canvas:
    """Opaque canvas, or transparent layer (straight colour + alpha)."""

    def __init__(self, h=H, w=W, color=None, img=None, layer=False):
        self.h, self.w = h, w
        if img is not None:
            self.img = np.array(img, f32, order='C')
        else:
            self.img = np.zeros((h, w, 3), f32)
            if color is not None:
                self.img[:] = rgb(color) if isinstance(color, str) else color
        self.a = np.zeros((h, w), f32) if layer else None

    def strokes(self, P, wd, col, op=1.0, dry=0.0, seed=0, shape='flat', lab=None, LAB=None, bristle=0.05):
        P = np.asarray(P, f32)
        n, K, _ = P.shape
        if n == 0: return self
        wd = np.broadcast_to(np.asarray(wd, f32), (n,)).copy()
        col = np.broadcast_to(np.asarray(col, f32), (n, 3)).copy()
        op = np.broadcast_to(np.asarray(op, f32), (n,)).copy()
        dry = np.broadcast_to(np.asarray(dry, f32), (n,)).copy()
        sd = (np.arange(n) * 7919 + seed * 104729).astype(np.int64) & 0x7ffffff
        L = _NOLAB if lab is None else lab.astype(np.int32)
        LA = np.full(n, -1, np.int32) if LAB is None else np.broadcast_to(np.asarray(LAB, np.int32), (n,)).copy()
        sh = {'flat': 0, 'round': 1, 'leaf': 2, 'taper': 3}[shape]
        _strokes(self.img, self.a if self.a is not None else _NOA, P, wd, col, op, dry, sd, L, LA,
                 self.a is not None, sh, K, bristle)
        return self

    def layer(self):
        """premultiplied RGBA"""
        a = self.a if self.a is not None else np.ones((self.h, self.w), f32)
        return np.dstack([self.img * a[..., None], a])


def arcs(x, y, ang, length, curve=0.0, K=5):
    """polylines of K points: centred at x,y, heading ang, given length & curvature (radians total)"""
    x, y, ang, length, curve = np.broadcast_arrays(*[np.asarray(v, f32) for v in (x, y, ang, length, curve)])
    t = np.linspace(-.5, .5, K, dtype=f32)
    P = np.empty((x.size, K, 2), f32)
    cx = np.zeros((x.size, K), f32); cy = np.zeros((x.size, K), f32)
    th = ang.ravel()[:, None] + curve.ravel()[:, None] * t[None]
    step = length.ravel()[:, None] / (K - 1)
    px = np.cumsum(np.cos(th) * step, 1); py = np.cumsum(np.sin(th) * step, 1)
    px -= px.mean(1, keepdims=True); py -= py.mean(1, keepdims=True)
    P[..., 0] = px + x.ravel()[:, None]; P[..., 1] = py + y.ravel()[:, None]
    return P


def jit_color(col, r, hue=.012, sat=.03, val=.035):
    """painterly colour variation on (n,3) rgb"""
    c = np.asarray(col, f32).copy()
    n = c.shape[0]
    v = r.normal(0, val, (n, 1)).astype(f32)
    warm = r.normal(0, hue, (n, 1)).astype(f32) * np.array([[1.2, .2, -1.2]], f32)
    g = c.mean(1, keepdims=True)
    s = 1 + r.normal(0, sat, (n, 1)).astype(f32) * 4
    c = g + (c - g) * s
    return np.clip(c * (1 + v) + v * .15 + warm, 0, 1)


def repaint(guide, sizes=(30, 14, 7), seed=1, angle=None, lab=None, mask=None, thr=(0, .02, .02),
            density=1.0, aspect=4.5, jit=(.012, .03, .03), op=.92, dry=.12, start=None, curve=.5,
            bristle=.05, shape='flat'):
    """Hertzmann-style gouache repaint of a guide picture with real strokes.
    angle: HxW stroke direction (radians) or None = follow image gradient + noise.
    lab: HxW int labels; strokes never cross label edges (masked paint edges)."""
    g = np.asarray(guide, f32)
    h, w = g.shape[:2]
    cv = Canvas(h, w, img=start if start is not None else g)
    r = np.random.default_rng(seed)
    if angle is None:
        L = cv2.GaussianBlur(lum(g), (0, 0), 6)
        gx = cv2.Sobel(L, cv2.CV_32F, 1, 0); gy = cv2.Sobel(L, cv2.CV_32F, 0, 1)
        jxx = cv2.GaussianBlur(gx * gx, (0, 0), 14); jyy = cv2.GaussianBlur(gy * gy, (0, 0), 14)
        jxy = cv2.GaussianBlur(gx * gy, (0, 0), 14)
        angle = .5 * np.arctan2(2 * jxy, jxx - jyy) + np.pi / 2
        coh = np.sqrt((jxx - jyy) ** 2 + 4 * jxy ** 2) / (jxx + jyy + 1e-6)
        angle = angle + fbm(h, w, (160, 60), (1, .5), seed + 9) * (0.15 + .6 * (1 - coh))
    for li, hw in enumerate(sizes):
        ref = cv2.GaussianBlur(g, (0, 0), max(.6, hw * .28)) if lab is None else g
        step = hw * 1.35 / math.sqrt(density)
        gy_, gx_ = np.mgrid[step * .5:h:step, step * .5:w:step].astype(f32)
        x = (gx_ + r.uniform(-.6, .6, gx_.shape) * step).ravel().clip(0, w - 1)
        y = (gy_ + r.uniform(-.6, .6, gx_.shape) * step).ravel().clip(0, h - 1)
        ix, iy = x.astype(int), y.astype(int)
        keep = np.ones(x.size, bool)
        if mask is not None: keep &= mask[iy, ix] > .3
        if li > 0 or thr[0] > 0:
            e = np.abs(cv2.GaussianBlur(cv.img, (0, 0), max(.8, hw * .4)) - ref).mean(-1)
            keep &= e[iy, ix] > thr[min(li, len(thr) - 1)] * r.uniform(.4, 1.6, x.size)
        ix, iy, x, y = ix[keep], iy[keep], x[keep], y[keep]
        if x.size == 0: continue
        o = r.permutation(x.size)
        ix, iy, x, y = ix[o], iy[o], x[o], y[o]
        col = jit_color(ref[iy, ix], r, *jit)
        ln = hw * aspect * r.uniform(.6, 1.35, x.size)
        an = angle[iy, ix] + r.normal(0, .16, x.size)
        P = arcs(x, y, an, ln, r.normal(0, curve, x.size))
        LAB = None if lab is None else lab[iy, ix]
        cv.strokes(P, hw * r.uniform(.6, 1.2, x.size), col, op=op * r.uniform(.75, 1, x.size),
                   dry=dry * r.uniform(0, 2, x.size), seed=seed + li * 31, lab=lab, LAB=LAB, bristle=bristle, shape=shape)
    return cv.img


def scatter_mask(mask, n, r):
    """n random points inside mask (weights = mask)"""
    ys, xs = np.nonzero(mask > .02)
    if len(xs) == 0: return np.zeros(0, f32), np.zeros(0, f32)
    p = mask[ys, xs].astype(np.float64); p /= p.sum()
    k = r.choice(len(xs), n, p=p)
    return (xs[k] + r.uniform(0, 1, n)).astype(f32), (ys[k] + r.uniform(0, 1, n)).astype(f32)


def tooth(h=H, w=W, seed=5, amt=.012):
    """cold-press paper tooth multiplier"""
    n = fbm(h, w, (3.2, 1.6), (1, .7), seed)
    return 1 + amt * n[..., None]


def mottle(img, amt=.02, seed=3, hue=.008, scales=(72, 26, 10.5, 4.5)):
    """gouache pigment mottling (isotropic)"""
    h, w = img.shape[:2]
    n = fbm(h, w, scales, None, seed); m = fbm(h, w, (110, 40), (1, .5), seed + 7)
    out = img * (1 + amt * n[..., None])
    out = out + hue * m[..., None] * np.array([1, .1, -1], f32)
    return np.clip(out, 0, 1)


def flat_dabs(img, n=90, seed=2, amt=.03, rmin=60, rmax=220):
    """large soft convex flat-brush dabs at quarter res, random angles"""
    h, w = img.shape[:2]
    r = np.random.default_rng(seed)
    q = np.zeros((h // 4, w // 4), f32)
    for _ in range(n):
        cx, cy = r.uniform(0, w / 4), r.uniform(0, h / 4)
        L, B = r.uniform(rmin, rmax) / 4, r.uniform(rmin, rmax) / 10
        a = r.uniform(0, np.pi)
        c, s = math.cos(a), math.sin(a)
        pts = []
        for (u, v) in ((-1, -.8), (-.2, -1), (1, -.7), (.9, .8), (0, 1), (-1, .9)):
            u *= L * r.uniform(.85, 1.1); v *= B * r.uniform(.8, 1.1)
            pts.append((cx + u * c - v * s, cy + u * s + v * c))
        l = np.zeros_like(q)
        cv2.fillConvexPoly(l, np.array(pts, np.float32).astype(np.int32), 1.0, cv2.LINE_AA)
        q += cv2.GaussianBlur(l, (0, 0), r.uniform(1.0, 3)) * r.normal(0, 1)
    q = cv2.resize(q, (w, h), interpolation=cv2.INTER_CUBIC)
    return np.clip(img * (1 + amt * q[..., None]), 0, 1)
