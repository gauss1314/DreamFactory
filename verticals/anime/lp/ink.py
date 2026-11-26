"""Hand-inked cel drawing on 2x supersampled PyCairo surfaces."""
import numpy as np, cv2, cairo, math
from . import W, H
from .paint import rgb, f32


# -------------------------------------------------------------- splines
def _cr(P, n, closed):
    P = np.asarray(P, float)
    m = len(P)
    if m < 3 and not closed:
        t = np.linspace(0, 1, max(2, n))[:, None]
        return P[0] * (1 - t) + P[-1] * t
    out = []
    segs = m if closed else m - 1
    for i in range(segs):
        if closed:
            p0, p1, p2, p3 = P[(i - 1) % m], P[i], P[(i + 1) % m], P[(i + 2) % m]
        else:
            p1, p2 = P[i], P[i + 1]
            p0 = P[i - 1] if i > 0 else 2 * p1 - p2
            p3 = P[i + 2] if i + 2 < m else 2 * p2 - p1
        # centripetal
        d1 = max(np.hypot(*(p1 - p0)), 1e-4) ** .5
        d2 = max(np.hypot(*(p2 - p1)), 1e-4) ** .5
        d3 = max(np.hypot(*(p3 - p2)), 1e-4) ** .5
        m1 = (p2 - p1) + d2 * ((p1 - p0) / d1 - (p2 - p0) / (d1 + d2))
        m2 = (p2 - p1) + d2 * ((p3 - p2) / d3 - (p3 - p1) / (d2 + d3))
        k = max(3, int(n * d2 * d2 / 12) + 3) if n <= 0 else n
        t = np.linspace(0, 1, k, endpoint=False)[:, None]
        h00 = 2 * t ** 3 - 3 * t ** 2 + 1; h10 = t ** 3 - 2 * t ** 2 + t
        h01 = -2 * t ** 3 + 3 * t ** 2; h11 = t ** 3 - t ** 2
        out.append(h00 * p1 + h10 * m1 + h01 * p2 + h11 * m2)
    out = np.concatenate(out)
    if not closed: out = np.vstack([out, P[-1]])
    return out


def spl(P, closed=False, corners=(), n=10):
    """Catmull-Rom through P.  corners = indices where the tangent breaks (sharp tips)."""
    P = np.asarray(P, float)
    c = sorted(set(int(i) % len(P) for i in corners))
    if not c: return _cr(P, n, closed)
    out = []
    if closed:
        for a, b in zip(c, c[1:] + [c[0] + len(P)]):
            seg = P[[k % len(P) for k in range(a, b + 1)]]
            out.append(_cr(seg, n, False)[:-1])
        return np.concatenate(out)
    cs = [0] + [k for k in c if 0 < k < len(P) - 1] + [len(P) - 1]
    for a, b in zip(cs[:-1], cs[1:]):
        out.append(_cr(P[a:b + 1], n, False)[:-1])
    return np.vstack(out + [P[-1:]])


def resample(P, step=2.0):
    P = np.asarray(P, float)
    d = np.hypot(*np.diff(P, axis=0).T)
    keep = np.r_[True, d > 1e-6]
    P = P[keep]
    if len(P) < 2: return P
    s = np.r_[0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]
    n = max(3, int(s[-1] / step) + 1)
    t = np.linspace(0, s[-1], n)
    return np.c_[np.interp(t, s, P[:, 0]), np.interp(t, s, P[:, 1])]


def lin(P, k=1):
    return np.asarray(P, float)


def noise1(n, scale, r):
    """smooth 1-D noise, n samples, feature length `scale` samples, ~unit amplitude"""
    m = max(4, int(n / max(scale, 1)) + 4)
    g = r.standard_normal(m)
    x = np.linspace(0, m - 3.001, n) + 1
    i = x.astype(int); f = x - i; f = f * f * (3 - 2 * f)
    return g[i] * (1 - f) + g[np.minimum(i + 1, m - 1)] * f


def boil(P, amp, seed, scale=3):
    """redraw wobble: jitter control points a little, per drawing"""
    r = np.random.default_rng(abs(int(seed)))
    return np.asarray(P, float) + r.normal(0, amp, np.shape(P))


def xf(P, sx=1, sy=None, rot=0, tx=0, ty=0, pivot=(0, 0)):
    P = np.asarray(P, float) - pivot
    sy = sx if sy is None else sy
    c, s = math.cos(rot), math.sin(rot)
    x = P[..., 0] * sx; y = P[..., 1] * sy
    return np.stack([x * c - y * s + tx + pivot[0], x * s + y * c + ty + pivot[1]], -1)


def ribbon(P, w, taper=(.25, .25), press=.22, seed=0, tremor=.3, closed=False, wfun=None, tmin=.12):
    """variable-width ink polygon.  w = full width px at screen scale."""
    P = resample(P, 1.6)
    n = len(P)
    if n < 3: return None
    r = np.random.default_rng(abs(int(seed)))
    if closed and np.hypot(*(P[0] - P[-1])) > 1e-3: P = np.vstack([P, P[0]]); n += 1
    T = np.gradient(P, axis=0)
    T /= np.hypot(T[:, 0], T[:, 1])[:, None] + 1e-9
    N = np.c_[-T[:, 1], T[:, 0]]
    t = np.linspace(0, 1, n)
    wl = np.ones(n)
    if not closed:
        if taper[0] > 0: wl *= tmin + (1 - tmin) * np.clip(t / taper[0], 0, 1) ** .7
        if taper[1] > 0: wl *= tmin + (1 - tmin) * np.clip((1 - t) / taper[1], 0, 1) ** .7
    wl *= 1 + press * np.clip(noise1(n, 26, r), -1.6, 1.6) * .6
    if wfun is not None: wl *= wfun(t)
    P = P + N * (noise1(n, 22, r) * tremor * .5)[:, None]
    hw = np.maximum(.22, .5 * w * wl)[:, None]
    return np.vstack([P + N * hw, (P - N * hw)[::-1]])


class Cel:
    """One cel.  Coordinates are screen pixels; (ox, oy) is the ROI origin."""

    def __init__(self, w=W, h=H, ox=0, oy=0, ss=2):
        self.w, self.h, self.ox, self.oy, self.ss = int(w), int(h), int(ox), int(oy), ss
        self.surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.w * ss, self.h * ss)
        c = self.ctx = cairo.Context(self.surf)
        c.scale(ss, ss); c.translate(-self.ox, -self.oy)
        c.set_antialias(cairo.ANTIALIAS_BEST)

    def _path(self, pts):
        c = self.ctx
        polys = pts if isinstance(pts, (list, tuple)) and len(pts) and np.ndim(pts[0]) == 2 else [pts]
        c.new_path()
        for p in polys:
            p = np.asarray(p, float)
            if len(p) < 2: continue
            c.move_to(*p[0])
            for q in p[1:]: c.line_to(q[0], q[1])
            c.close_path()

    def _src(self, col, alpha):
        col = rgb(col) if isinstance(col, str) else col
        self.ctx.set_source_rgba(float(col[0]), float(col[1]), float(col[2]), alpha)

    def fill(self, pts, col, alpha=1.0, evenodd=False):
        self._path(pts); self._src(col, alpha)
        self.ctx.set_fill_rule(cairo.FILL_RULE_EVEN_ODD if evenodd else cairo.FILL_RULE_WINDING)
        self.ctx.fill(); return self

    def clip(self, pts):
        self.ctx.save(); self._path(pts); self.ctx.clip(); return self

    def unclip(self):
        self.ctx.restore(); return self

    def shade(self, pts, col, within=None, alpha=1.0):
        """hard-edged cel shadow, optionally clipped to a shape"""
        if within is not None: self.clip(within)
        self.fill(pts, col, alpha)
        if within is not None: self.unclip()
        return self

    def line(self, P, w=2.4, col='#2b1d1c', taper=(.25, .25), press=.22, seed=0, tremor=.3, alpha=1.0,
             closed=False, wfun=None, tmin=.12):
        R = ribbon(P, w, taper, press, seed, tremor, closed, wfun, tmin)
        if R is None: return self
        if closed:
            n = len(R) // 2
            self.fill([R[:n], R[n:]], col, alpha, evenodd=True)
        else:
            self.fill(R, col, alpha)
        return self

    def grad(self, pts, p0, p1, stops):
        """linear gradient fill: use only for airbrush-free glows (eyes), never on body cels"""
        g = cairo.LinearGradient(*p0, *p1)
        for t, col, a in stops:
            col = rgb(col) if isinstance(col, str) else col
            g.add_color_stop_rgba(t, float(col[0]), float(col[1]), float(col[2]), a)
        self._path(pts); self.ctx.set_source(g); self.ctx.fill(); return self

    def group(self):
        self.ctx.push_group(); return self

    def ungroup(self, alpha=1.0, within=None):
        self.ctx.pop_group_to_source()
        if alpha < 1: self.ctx.paint_with_alpha(alpha)
        else: self.ctx.paint()
        return self

    def rgba(self):
        """premultiplied float RGBA of the ROI at 1x"""
        self.surf.flush()
        a = np.ndarray((self.h * self.ss, self.surf.get_stride() // 4, 4), np.uint8, self.surf.get_data())[:, :self.w * self.ss]
        f = cv2.resize(a, (self.w, self.h), interpolation=cv2.INTER_AREA).astype(f32) / 255.
        return f[..., [2, 1, 0, 3]]

    def layer(self, h=H, w=W):
        """premultiplied float RGBA pasted on a full h x w transparent frame"""
        f = self.rgba()
        out = np.zeros((h, w, 4), f32)
        paste(out, f, self.ox, self.oy)
        return out


def paste(dst, src, ox, oy):
    h, w = dst.shape[:2]; sh, sw = src.shape[:2]
    x0, y0 = max(0, ox), max(0, oy); x1, y1 = min(w, ox + sw), min(h, oy + sh)
    if x1 <= x0 or y1 <= y0: return
    dst[y0:y1, x0:x1] = src[y0 - oy:y1 - oy, x0 - ox:x1 - ox]


def over_roi(base, src, ox, oy, opacity=1.0):
    """premult RGBA src over RGB base at offset, in place"""
    h, w = base.shape[:2]; sh, sw = src.shape[:2]
    x0, y0 = max(0, ox), max(0, oy); x1, y1 = min(w, ox + sw), min(h, oy + sh)
    if x1 <= x0 or y1 <= y0: return base
    s = src[y0 - oy:y1 - oy, x0 - ox:x1 - ox] * opacity
    b = base[y0:y1, x0:x1]
    base[y0:y1, x0:x1] = b * (1 - s[..., 3:4]) + s[..., :3]
    return base
