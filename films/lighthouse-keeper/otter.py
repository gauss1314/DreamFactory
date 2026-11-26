"""The otter: one model, drawn as cels from any angle.

The character is a puppet of round primitives (ellipsoids and round cones) posed in body space
(f forward, u up, r the otter's right; units: standing height to the crown = 100). Each body part is
one cel "piece": its primitives are smooth-unioned, projected orthographically, and painted as a flat
fill + one hard-edged shadow (from the light direction) + a rim on the lit edge. Its outline is traced
from the fill and inked as tapered pressure strokes that lift where a pencil would. Pieces are
layered back to front like a cel stack. Face features (eyes, mouth, whiskers) are drawn on the head
surface in 3-D and projected, so a turn of the head is a redraw, not a slide.

  out = draw(img, view, pose, env, seed)   # composites into img (float RGB), returns screen points
  view = dict(x=, y=, k=, yaw=, tilt=)     # ground point px, px per unit, view angle (0 = facing
                                           # screen right in side view, pi/2 = facing the camera)
"""
import numpy as np, cv2, math
from lp.ink import Cel, spl, resample
from lp.paint import rgb, mix

f32 = np.float32

PAL = dict(fur='#7a5236', fur_sh='#4e3226', fur_hi='#a8784e', cream='#e9d6b8', cream_sh='#b89c86',
           nose='#2a1e22', nose_sh='#1c1418', scarf='#b8443c', scarf_sh='#7e2a30', inner='#4e3226', inner_sh='#3a2422',
           line='#2f1a17', eye='#1a1114', iris='#3a2420', glint='#fffaf0', mouth='#4a1f22', tongue='#c46a62', pad='#3e2622')
CLS = ['cream', 'nose', 'scarf', 'inner', 'mouth', 'tongue', 'pad', 'glint']


# ------------------------------------------------------------------ transforms
def rot(axis, a):
    c, s = math.cos(a), math.sin(a)
    x, y, z = axis
    return np.array([[c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
                     [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s],
                     [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)]])


def spl3(P, n=8):
    """uniform Catmull-Rom through 3-D points (lp.ink.spl is 2-D only)"""
    P = np.asarray(P, float)
    if len(P) < 3:
        t = np.linspace(0, 1, n)[:, None]; return P[0] * (1 - t) + P[-1] * t
    Q = np.vstack([2 * P[0] - P[1], P, 2 * P[-1] - P[-2]])
    out = []
    t = np.linspace(0, 1, n, endpoint=False)[:, None]
    for i in range(1, len(Q) - 2):
        p0, p1, p2, p3 = Q[i - 1], Q[i], Q[i + 1], Q[i + 2]
        out.append(.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-1:])
    return np.vstack(out)


def unit(v):
    v = np.asarray(v, float); return v / (np.linalg.norm(v) + 1e-9)


class View:
    """body space (f, u, r) -> screen px (x right, y down, z toward the viewer)"""

    def __init__(self, x, y, k, yaw=0.0, tilt=0.0, roll=0.0, flip=False):
        self.o = np.array([x, y, 0.0]); self.k = k
        th = yaw
        F = np.array([math.cos(th), 0, math.sin(th)])
        U = np.array([0, -1.0, 0])
        R = np.array([-math.sin(th), 0, math.cos(th)])
        B = np.stack([F, U, R], 1)                       # columns: images of f, u, r
        c, s = math.cos(tilt), math.sin(tilt)
        T = np.array([[1, 0, 0], [0, c, s], [0, -s, c]])
        c2, s2 = math.cos(roll), math.sin(roll)
        Rz = np.array([[c2, -s2, 0], [s2, c2, 0], [0, 0, 1]])
        self.M = Rz @ T @ B                               # body -> screen direction
        if flip: self.M = self.M @ np.diag([1, 1, -1])    # mirror r (which side the knot is on)

    def p(self, q):
        q = np.asarray(q, float)
        return self.o + self.k * (q @ self.M.T)

    def d(self, v):
        return np.asarray(v, float) @ self.M.T


# ------------------------------------------------------------------ primitives
class Ell:
    """ellipsoid: centre c (body units), local axes Rm (3x3 columns, body space), radii"""

    def __init__(self, c, radii, Rm=None, mat=None, frame=None):
        self.c, self.r = np.asarray(c, float), np.asarray(radii, float)
        self.Rm = np.eye(3) if Rm is None else np.asarray(Rm, float)
        self.mat, self.frame = mat, frame

    def bake(self, V):
        c = V.p(self.c)
        A = (self.Rm.T @ V.M.T) / (self.r[:, None] * V.k)  # screen offset -> unit coords
        Q = A.T @ A
        self.cs, self.A, self.Q = c, A, Q
        S = Q[:2, :2] - np.outer(Q[:2, 2], Q[2, :2]) / Q[2, 2]
        Si = np.linalg.inv(S)
        ex, ey = math.sqrt(max(Si[0, 0], 1e-9)), math.sqrt(max(Si[1, 1], 1e-9))
        self.bb = (c[0] - ex, c[1] - ey, c[0] + ex, c[1] + ey)
        self.S = S
        self.zc = c[2]

    def eval(self, X, Y):
        dx, dy = X - self.cs[0], Y - self.cs[1]
        S, Q = self.S, self.Q
        g2 = S[0, 0] * dx * dx + 2 * S[0, 1] * dx * dy + S[1, 1] * dy * dy
        g = np.sqrt(g2) + 1e-6
        gx, gy = (S[0, 0] * dx + S[0, 1] * dy) / g, (S[0, 1] * dx + S[1, 1] * dy) / g
        d = (g - 1) / (np.sqrt(gx * gx + gy * gy) + 1e-6)
        B = Q[2, 0] * dx + Q[2, 1] * dy
        C = Q[0, 0] * dx * dx + 2 * Q[0, 1] * dx * dy + Q[1, 1] * dy * dy
        disc = np.maximum(B * B - Q[2, 2] * (C - 1), 0)
        dz = (-B + np.sqrt(disc)) / Q[2, 2]
        P = np.stack([dx, dy, dz])
        n = np.tensordot(Q, P, 1)
        n /= np.sqrt((n * n).sum(0)) + 1e-9
        Ul = np.tensordot(self.A, P, 1)
        return d, dz + self.cs[2], n, Ul


class Cone:
    """round cone between body points a, b with radii ra, rb (body units)"""

    def __init__(self, a, b, ra, rb, mat=None, frame=None):
        self.a, self.b, self.ra, self.rb = np.asarray(a, float), np.asarray(b, float), ra, rb
        self.mat, self.frame = mat, frame

    def bake(self, V):
        self.as_, self.bs = V.p(self.a), V.p(self.b)
        self.rap, self.rbp = self.ra * V.k, self.rb * V.k
        x0 = min(self.as_[0] - self.rap, self.bs[0] - self.rbp); x1 = max(self.as_[0] + self.rap, self.bs[0] + self.rbp)
        y0 = min(self.as_[1] - self.rap, self.bs[1] - self.rbp); y1 = max(self.as_[1] + self.rap, self.bs[1] + self.rbp)
        self.bb = (x0, y0, x1, y1)
        self.zc = (self.as_[2] + self.bs[2]) / 2

    def eval(self, X, Y):
        a, b = self.as_, self.bs
        ba = b[:2] - a[:2]; L2 = ba @ ba + 1e-6
        px, py = X - a[0], Y - a[1]
        # slope-aware projection for an uneven capsule (2-D)
        L = math.sqrt(L2)
        dr = (self.rbp - self.rap)
        sl = np.clip(dr / L, -.95, .95)
        t = (px * ba[0] + py * ba[1]) / L2
        qx, qy = px - t * ba[0], py - t * ba[1]
        q = np.sqrt(qx * qx + qy * qy)
        t = np.clip(t - sl * q / L * math.sqrt(1 / (1 - sl * sl)) * .9, 0, 1)
        A3 = a[None, None, :] if False else None
        cx = a[0] + t * ba[0]; cy = a[1] + t * ba[1]; cz = a[2] + t * (b[2] - a[2])
        rr = self.rap + t * dr
        ex, ey = X - cx, Y - cy
        e = np.sqrt(ex * ex + ey * ey)
        d = e - rr
        ez = np.sqrt(np.maximum(rr * rr - e * e, 0))
        n = np.stack([ex, ey, ez]) / (rr + 1e-6)
        n /= np.sqrt((n * n).sum(0)) + 1e-9
        Ul = np.stack([t, e / (rr + 1e-6), np.zeros_like(t)])
        return d, cz + ez, n, Ul


class Sweep:
    """a tube swept along a 3-D polyline with varying radius (tail, limbs, scarf): the closest
    segment wins, so normals stay continuous through the bends"""

    def __init__(self, pts, radii, mat=None, frame=None, n=0):
        pts, radii = np.asarray(pts, float), np.asarray(radii, float)
        if n:
            q = spl3(pts, n)
            s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(pts, axis=0), axis=1))]
            sq = np.r_[0, np.cumsum(np.linalg.norm(np.diff(q, axis=0), axis=1))]
            radii = np.interp(sq / sq[-1] * s[-1], s, radii); pts = q
        self.pts, self.rad = pts, radii
        self.mat, self.frame = mat, frame

    def bake(self, V):
        self.ps = V.p(self.pts); self.rp = self.rad * V.k
        self.bb = ((self.ps[:, 0] - self.rp).min(), (self.ps[:, 1] - self.rp).min(), (self.ps[:, 0] + self.rp).max(), (self.ps[:, 1] + self.rp).max())
        self.zc = self.ps[:, 2].mean()

    def eval(self, X, Y):
        best = None
        P, R = self.ps, self.rp
        m = len(P) - 1
        for i in range(m):
            a, b = P[i], P[i + 1]
            ba = b[:2] - a[:2]; L2 = ba @ ba + 1e-6
            t = np.clip(((X - a[0]) * ba[0] + (Y - a[1]) * ba[1]) / L2, 0, 1)
            cx = a[0] + t * ba[0]; cy = a[1] + t * ba[1]
            rr = R[i] + t * (R[i + 1] - R[i])
            ex, ey = X - cx, Y - cy
            e = np.sqrt(ex * ex + ey * ey)
            d = e - rr
            if best is None:
                best = [d, t + i, cx, cy, a[2] + t * (b[2] - a[2]), rr, ex, ey, e]
            else:
                w = d < best[0]
                for j, v in enumerate([d, t + i, cx, cy, a[2] + t * (b[2] - a[2]), rr, ex, ey, e]):
                    best[j] = np.where(w, v, best[j])
        d, tt, cx, cy, cz, rr, ex, ey, e = best
        ez = np.sqrt(np.maximum(rr * rr - e * e, 0))
        n = np.stack([ex, ey, ez]) / (rr + 1e-6)
        n /= np.sqrt((n * n).sum(0)) + 1e-9
        Ul = np.stack([tt / m, e / (rr + 1e-6), np.zeros_like(tt)])
        return d, cz + ez, n, Ul


# ------------------------------------------------------------------ lighting
class Env:
    """light toward dir (screen dx, dy), colour, strength; ambient tint; dark = silhouette amount"""

    def __init__(self, light=None, amb='#2c2a48', dark=0.0, rim=1.0, thr=.08, glint=None, front=.55, line=None, flat=0.0):
        light = light or dict(dir=(1, -.4), color='#fff2d8', amt=.6)
        dx, dy = light['dir']
        self.L2 = unit([dx, dy])
        self.L = unit([dx, dy, front])
        self.col = rgb(light['color']) if isinstance(light['color'], str) else np.asarray(light['color'], f32)
        self.amt = float(light.get('amt', .7))
        self.amb = rgb(amb) if isinstance(amb, str) else np.asarray(amb, f32)
        self.dark, self.rim, self.thr = dark, rim, thr
        self.glint = rgb(glint) if isinstance(glint, str) else (self.col * .5 + .5 if glint is None else glint)
        self.line = rgb(line or PAL['line'])
        self.flat = flat
        self._cache = {}

    def colors(self, name):
        """(lit, shadow, rim) colours of a material under this light"""
        if name in self._cache: return self._cache[name]
        base = rgb(PAL[name]); sh = rgb(PAL[name + '_sh']) if name + '_sh' in PAL else base * .62
        a = self.amt
        lit = base * (1 - .42 * a) + base * self.col * 1.32 * .42 * a
        shd = sh * .86 + sh * self.amb * 1.9 * .14
        hi = rgb(PAL['fur_hi']) if name == 'fur' else mix(base, np.ones(3, f32), .35)
        rim = mix(hi * (.55 + .7 * self.col), self.col * 1.02, .3 + .2 * a)
        if self.dark > 0:
            dk = self.amb
            lit = mix(lit, dk * (.55 + .5 * lum3(base)), self.dark)
            shd = mix(shd, dk * .55, self.dark)
            rim = mix(rim, self.col * 1.1, self.dark * .6)
        out = (np.clip(lit, 0, 2).astype(f32), np.clip(shd, 0, 2).astype(f32), np.clip(rim, 0, 2).astype(f32))
        self._cache[name] = out
        return out


def lum3(c):
    return float(c[0] * .299 + c[1] * .587 + c[2] * .114)


# ------------------------------------------------------------------ piece renderer
def _sh(s):
    """stable small hash of a name (str hash() changes between processes)"""
    import zlib
    return zlib.crc32(s.encode())


def smin(a, b, k):
    h = np.clip(.5 + .5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def _boil(X, Y, seed, amp, lam):
    r = np.random.default_rng(seed)
    out = 0
    for i in range(3):
        a = r.uniform(0, 2 * np.pi); ph = r.uniform(0, 2 * np.pi); l = lam * r.uniform(.7, 1.4)
        out = out + np.sin((X * math.cos(a) + Y * math.sin(a)) * (2 * np.pi / l) + ph)
    return out * (amp / 1.7)


class Piece:
    """one cel: smooth union of prims, one base material"""

    def __init__(self, name, prims, base='fur', k=2.0, z=None, roots=(), lw=1.0, ink=True, spiky=0.0, rim=1.0, lifts=None,
                 inner_lines=(), shadow=True, kz=1.5):
        self.name, self.prims, self.base, self.ks, self.zkey = name, prims, base, k, z
        self.roots, self.lw, self.ink, self.spiky, self.rim_amt = roots, lw, ink, spiky, rim
        self.lifts, self.inner_lines, self.shadow, self.kz = lifts, inner_lines, shadow, kz


def render_piece(P, V, env, seed, clipfn=None):
    """-> (rgba premult float32 (h, w, 4), ox, oy, info) or None"""
    for q in P.prims: q.bake(V)
    k = V.k
    pad = 4 + P.ks * k + 3
    x0 = min(q.bb[0] for q in P.prims) - pad; y0 = min(q.bb[1] for q in P.prims) - pad
    x1 = max(q.bb[2] for q in P.prims) + pad; y1 = max(q.bb[3] for q in P.prims) + pad
    ox, oy = int(math.floor(x0)), int(math.floor(y0))
    w, h = int(math.ceil(x1)) - ox, int(math.ceil(y1)) - oy
    if w < 2 or h < 2: return None
    g = max(1, int(round(k / 3.6)))
    gw, gh = int(math.ceil(w / g)) + 1, int(math.ceil(h / g)) + 1
    xs = ox + (np.arange(gw, dtype=f32) + .5) * g - .5
    ys = oy + (np.arange(gh, dtype=f32) + .5) * g - .5
    X, Y = np.meshgrid(xs, ys)
    ks = P.ks * k
    kz = P.kz * k
    D = None; Sc = []; At = []
    for q in P.prims:
        d, z, n, Ul = q.eval(X, Y)
        D = d if D is None else smin(D, d, ks)
        score = z / kz - np.maximum(d, 0) / max(ks * .25, 1.0) * 3.0
        fr = q.frame
        if fr is not None:
            O, Rf = fr
            Pw = np.stack([X - O[0], Y - O[1], z - O[2]]) / k
            Pl = np.tensordot(Rf.T, Pw, 1); Nl = np.tensordot(Rf.T, n, 1)
        else:
            Pl = Nl = None
        fields = q.mat(Pl, Nl, Ul) if q.mat is not None else {}
        fields = {c: np.minimum(v, -d / k) for c, v in fields.items()}
        Sc.append(score); At.append((n, fields))
    Sc = np.stack(Sc); Sc -= Sc.max(0, keepdims=True); Wt = np.exp(Sc); Wt /= Wt.sum(0, keepdims=True)
    N = sum(Wt[i][None] * At[i][0] for i in range(len(P.prims)))
    N /= np.sqrt((N * N).sum(0)) + 1e-9
    used = sorted(set(c for _, f in At for c in f))
    F = {}
    for c in used:
        F[c] = sum(Wt[i] * (At[i][1][c] if c in At[i][1] else -4.0) for i in range(len(P.prims)))
    # boil the drawing: whole-cel wobble, seeded by the drawing number
    D = D + _boil(X, Y, seed * 7 + _sh(P.name) % 997, .45, 55.0 + 8 * k)
    if P.spiky > 0:
        cx_ = np.mean([q.bb[0] + q.bb[2] for q in P.prims]) / 2; cy_ = np.mean([q.bb[1] + q.bb[3] for q in P.prims]) / 2
        th_ = np.arctan2(Y - cy_, X - cx_)
        per = 2 * ((x1 - x0) + (y1 - y0))
        nsp = max(6, int(per / (5.5 * k + 6)))
        tri = np.abs(((th_ / (2 * np.pi) * nsp + .37 * np.sin(th_ * 3 + seed % 7)) % 1.0) - .5) * 2
        spike = np.clip(1 - tri * 1.8, 0, 1) ** 1.6
        D = D - P.spiky * (1.4 * k + 1.0) * spike * (D > -3 * k)
    L = env.L
    ndl = N[0] * L[0] + N[1] * L[1] + N[2] * L[2]
    l2 = N[0] * env.L2[0] + N[1] * env.L2[1]
    nz = N[2]
    chans = [D, ndl, l2, nz] + [F[c] for c in used]
    G = np.stack(chans, -1).astype(f32)
    if g > 1:
        G = cv2.resize(G, (gw * g, gh * g), interpolation=cv2.INTER_LINEAR)
        if G.ndim == 2: G = G[..., None]
    G = G[:h, :w]
    D1, ndl1, l21, nz1 = G[..., 0], G[..., 1], G[..., 2], G[..., 3]
    alpha = np.clip(.5 - D1, 0, 1)
    if clipfn is not None:
        alpha = alpha * clipfn(ox, oy, w, h)
    if alpha.max() <= 0: return None
    # hard cel shadow
    aaw = 1.6 / (k * 10)
    if P.shadow:
        sh = np.clip((env.thr - ndl1) / aaw + .5, 0, 1)
    else:
        sh = np.zeros_like(ndl1)
    if env.flat: sh = sh * (1 - env.flat)
    # rim on the lit edge
    rw = min(1.0 * k, 4.0 + .35 * k) + 1.5
    rim = np.clip(D1 + rw + .5, 0, 1) * np.clip(((.62 - nz1) * 6), 0, 1) * np.clip((l21 - .25) * 4, 0, 1) * env.rim * P.rim_amt
    rim = np.clip((rim - .5) / .12 + .5, 0, 1) * (1 - sh)
    lit, shd, rmc = env.colors(P.base)
    col = lit[None, None] * (1 - sh[..., None]) + shd[None, None] * sh[..., None]
    for i, c in enumerate(used):
        a = np.clip(G[..., 4 + i] * k + .5, 0, 1)[..., None]
        if c == 'glint':
            col = col * (1 - a * .85) + env.glint[None, None] * a * .85
            continue
        cl, cs_, cr = env.colors(c)
        cc = cl[None, None] * (1 - sh[..., None]) + cs_[None, None] * sh[..., None]
        col = col * (1 - a) + cc * a
        rmc = rmc if c != 'cream' else rmc
    col = col * (1 - rim[..., None] * .9) + rmc[None, None] * rim[..., None] * .9
    rgba = np.concatenate([col * alpha[..., None], alpha[..., None]], -1).astype(f32)
    info = dict(D=D1, sh=sh, alpha=alpha, ox=ox, oy=oy, w=w, h=h, ndl=ndl1, F={c: G[..., 4 + i] for i, c in enumerate(used)})
    return rgba, ox, oy, info


def _contours(info, step=2.0):
    D = info['D']; a = (D < 0).astype(np.uint8)
    cs, _ = cv2.findContours(a, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    out = []
    gy, gx = np.gradient(D)
    h, w = D.shape
    for c in cs:
        if len(c) < 12: continue
        p = c[:, 0, :].astype(float)
        xi = np.clip(p[:, 0].astype(int), 0, w - 1); yi = np.clip(p[:, 1].astype(int), 0, h - 1)
        d = D[yi, xi]; gxx = gx[yi, xi]; gyy = gy[yi, xi]; gn = gxx * gxx + gyy * gyy + 1e-6
        p[:, 0] -= d * gxx / gn; p[:, 1] -= d * gyy / gn
        # smooth along the loop
        n = len(p); kk = 5
        ker = np.ones(kk) / kk
        p = np.c_[np.convolve(np.r_[p[-kk:, 0], p[:, 0], p[:kk, 0]], ker, 'same')[kk:-kk], np.convolve(np.r_[p[-kk:, 1], p[:, 1], p[:kk, 1]], ker, 'same')[kk:-kk]]
        p = np.vstack([p, p[:1]])
        p = resample(p, step)
        out.append(p + [info['ox'], info['oy']])
    return out


def _strokes(loop, P, info, k, seed, roots, lifts):
    """split a closed outline into pencil strokes; drop the parts inside root joints"""
    n = len(loop)
    keep = np.ones(n, bool)
    for (c, rad) in roots:
        keep &= np.hypot(loop[:, 0] - c[0], loop[:, 1] - c[1]) > rad
    r = np.random.default_rng(1000 + _sh(P.name) % 9973)
    seglen = (90 + 40 * r.random()) * max(1.0, k / 3.3) ** .6
    s = np.r_[0, np.cumsum(np.hypot(*np.diff(loop, axis=0).T))]
    Ltot = s[-1]
    nl = max(2, int(Ltot / seglen)) if lifts is None else lifts
    off = r.random()
    cuts = ((np.arange(nl) + off + np.random.default_rng(seed).uniform(-.04, .04, nl)) / nl * Ltot) % Ltot
    gap = 2.2 + .25 * k
    for cpos in cuts:
        dd = np.abs(s - cpos); dd = np.minimum(dd, Ltot - dd)
        keep &= dd > gap
    # rotate so the loop starts at a dropped point
    if keep.all():
        i0 = 0
        runs = [np.arange(n)]
    else:
        i0 = int(np.argmin(keep))
        idx = np.r_[np.arange(i0, n), np.arange(0, i0)]
        kk = keep[idx]
        runs, cur = [], []
        for j, ok in zip(idx, kk):
            if ok: cur.append(j)
            elif cur: runs.append(np.array(cur)); cur = []
        if cur: runs.append(np.array(cur))
    return [loop[ru] for ru in runs if len(ru) >= 4]


def ink_piece(cel, P, info, env, k, seed, lw):
    if not P.ink: return
    sh = info['sh']; ox, oy = info['ox'], info['oy']; h, w = sh.shape
    for loop in _contours(info):
        for st in _strokes(loop, P, info, k, seed, [(np.asarray(c, float), rad) for c, rad in P.roots], P.lifts):
            # heavier on the shadow side
            ctr = st.mean(0)
            xi = np.clip((st[:, 0] - ox).astype(int), 0, w - 1); yi = np.clip((st[:, 1] - oy).astype(int), 0, h - 1)
            # look slightly inside
            nrm = np.gradient(st, axis=0); nrm = np.c_[-nrm[:, 1], nrm[:, 0]]
            sv = sh[yi, xi]
            for sgn in (-1, 1):
                q = st + sgn * nrm / (np.hypot(*nrm.T)[:, None] + 1e-6) * 3
                xi2 = np.clip((q[:, 0] - ox).astype(int), 0, w - 1); yi2 = np.clip((q[:, 1] - oy).astype(int), 0, h - 1)
                sv = np.maximum(sv, sh[yi2, xi2] * (info['alpha'][yi2, xi2] > .5))
            wt = .78 + .55 * np.convolve(np.pad(sv, 6, 'edge'), np.ones(13) / 13, 'valid')
            tt = np.linspace(0, 1, len(wt))
            cel.line(st, lw * P.lw, env.line, (.18, .18), .3, seed=seed * 31 + int(ctr[0]) % 97, tremor=.25,
                     wfun=lambda t, tt=tt, wt=wt: np.interp(t, tt, wt))


def over_into(buf, ox, oy, rgba, x, y):
    """premult rgba at screen (x, y) over premult buf at screen (ox, oy)"""
    h, w = buf.shape[:2]; sh, sw = rgba.shape[:2]
    a0, b0 = max(0, x - ox), max(0, y - oy); a1, b1 = min(w, x - ox + sw), min(h, y - oy + sh)
    if a1 <= a0 or b1 <= b0: return
    s = rgba[b0 - (y - oy):b1 - (y - oy), a0 - (x - ox):a1 - (x - ox)]
    d = buf[b0:b1, a0:a1]
    buf[b0:b1, a0:a1] = s + d * (1 - s[..., 3:4])


# ------------------------------------------------------------------ the model
def mat_head(cream_line=-3.6, slope=.22):
    def m(Pl, Nl, Ul):
        f, u, r = Pl
        zig = .38 * np.sin(f * 1.25 + r * .35) + .22 * np.sin(r * 1.0 - f * .3)
        cream = (cream_line + slope * f + zig) - u
        # keep the bridge of the muzzle and the brow brown
        return dict(cream=np.minimum(cream, 30))
    return m


def mat_body(Pl, Nl, Ul):
    f, u, r = Pl
    zig = .45 * np.sin(u * 1.1 + r * .3)
    front = (Nl[0] - .34 + .05 * np.sin(u * 1.7)) * 10
    low = (u - 25 + zig) - 18 * np.abs(Nl[2]) ** 1.5
    return dict(cream=np.minimum(front, low))


def mat_nose(Pl, Nl, Ul):
    g = (Nl[0] * .55 + Nl[1] * .75 + .1 * Nl[2]) - .84
    return dict(nose=np.full_like(Ul[0], 10.0), glint=g * 14)


def mat_ear(Pl, Nl, Ul):
    # inner ear: the front face, inside the rim
    inn = np.minimum((Ul[0] - .05) * 6, (.66 - np.sqrt(Ul[1] ** 2 + Ul[2] ** 2)) * 6)
    return dict(inner=inn)


def mat_paw(Pl, Nl, Ul):
    return {}


def mat_scarf(Pl, Nl, Ul):
    return dict(scarf=np.full_like(Ul[0], 10.0))


def mat_mouth(Pl, Nl, Ul):
    t = (.25 - Ul[1]) * 4
    return dict(mouth=np.full_like(Ul[0], 10.0), tongue=np.minimum(t, (Ul[0] + .3) * 4))


def mat_belly(Pl, Nl, Ul):
    return mat_body(Pl, Nl, Ul)


STAND = dict(
    pelvis=(0, 24, 0), chest=(1.5, 51, 0), neck=(2.5, 64, 0), rp=18.5, rc=14.5, rn=10.5,
    head=(4.5, 80.5, 0), hyaw=0.0, hpitch=0.0, hroll=0.0,
    pawL=(10, 40, -8), pawR=(10, 40, 8), elbL=(.2, 1, -.6), elbR=(.2, 1, .6),
    footL=(2.5, 3.0, -8.5), footR=(2.5, 3.0, 8.5), fpL=0.0, fpR=0.0,
    tail=((-13, 14, 0), (-23, 6, 0), (-33, 3.5, 0), (-42, 4.5, 0), (-48, 9, 0)),
    blink=0.0, squint=0.0, ears=0.0, mouth=0.0, look=(0.0, 0.0), whisk=0.0, smile=0.0,
    scarf=(0.0, 0.0), knot=1.0, wet=0.0, grip=0.0)


def pose(base=None, **kw):
    p = dict(STAND if base is None else base); p.update(kw); return p


def lerp(a, b, t):
    out = {}
    for k in a:
        va, vb = a[k], b.get(k, a[k])
        if isinstance(va, (int, float)) and not isinstance(va, bool): out[k] = va + (vb - va) * t
        elif isinstance(va, bool) or va is None: out[k] = va if t < .5 else vb
        else: out[k] = np.asarray(va, float) * (1 - t) + np.asarray(vb, float) * t
    return out


def ik2(a, b, l1, l2, hint):
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = b - a; L = np.linalg.norm(d)
    L = max(L, 1e-6); u = d / L
    L2 = min(L, (l1 + l2) * .999)
    x = (l1 * l1 - l2 * l2 + L2 * L2) / (2 * L2); y = math.sqrt(max(0, l1 * l1 - x * x))
    hv = np.asarray(hint, float); hv = hv - u * (hv @ u); hv = unit(hv) if np.linalg.norm(hv) > 1e-6 else np.array([1., 0, 0])
    e = a + u * x + hv * y
    return e, a + u * L2


def frame_from(f):
    """rotation whose first column is f"""
    f = unit(f); up = np.array([0, 1.0, 0]) if abs(f[1]) < .9 else np.array([1.0, 0, 0])
    r = unit(np.cross(f, up)); u = np.cross(r, f)
    return np.stack([f, u, r], 1)


def head_frame(P):
    """head rotation matrix (columns = head f, u, r in body space)"""
    R = rot((0, 1, 0), P['hyaw']) @ rot((0, 0, 1), P['hpitch']) @ rot((1, 0, 0), P['hroll'])
    return R


def build(P, V):
    """pose -> list of pieces in body space, plus head geometry for the face"""
    hd = np.array(P['head'], float); Rh = head_frame(P)
    H = lambda q: hd + Rh @ np.asarray(q, float)
    HR = lambda Rl: Rh @ Rl
    O = V.p(hd); Rs = V.M @ Rh
    fr_h = (O, Rs)
    fr_b = (V.p([0, 0, 0]), V.M)
    pieces = []
    # ---- torso
    pel, che, nek = np.array(P['pelvis'], float), np.array(P['chest'], float), np.array(P['neck'], float)
    torso = [Cone(pel, che, P['rp'], P['rc'], mat_body, fr_b), Cone(che, nek, P['rc'], P['rn'], mat_body, fr_b),
             Ell(pel + [0, -6, 0], (P['rp'] * .98, P['rp'] * .62, P['rp'] * .92), mat=mat_body, frame=fr_b)]
    pieces.append(Piece('torso', torso, 'fur', k=4.0, spiky=P['wet']))
    # ---- head
    ear_fl = P['ears']
    hp = [Ell(H([0, 0, 0]), (12.6, 11.6, 14.6), HR(np.eye(3)), mat_head(), fr_h),
          Ell(H([2.5, -4.5, 0]), (10.5, 8.0, 13.2), HR(np.eye(3)), mat_head(), fr_h),
          Ell(H([10.5, -3.6, 0]), (8.2, 6.2, 8.8), HR(np.eye(3)), mat_head(), fr_h),
          Ell(H([14.6, -4.0, 4.3]), (4.8, 4.0, 4.6), HR(np.eye(3)), mat_head(), fr_h),
          Ell(H([14.6, -4.0, -4.3]), (4.8, 4.0, 4.6), HR(np.eye(3)), mat_head(), fr_h),
          Ell(H([10.8, -8.4, 0]), (5.5, 3.0, 5.4), HR(np.eye(3)), mat_head(), fr_h),
          Ell(H([18.6, -.6, 0]), (2.3, 2.4, 3.7), HR(np.eye(3)), mat_nose, fr_h)]
    for s in (-1, 1):
        a = -.25 - .95 * ear_fl
        Re = rot((0, 0, 1), a * 1.0) @ rot((1, 0, 0), s * (.45 + .25 * ear_fl))
        ec = [-3.0 - 2.6 * ear_fl, 8.2 - 3.4 * ear_fl, s * (11.6 + .8 * ear_fl)]
        hp.append(Ell(H(ec), (1.8, 4.0 - .6 * ear_fl, 4.5), HR(Re), mat_ear, fr_h))
    pieces.append(Piece('head', hp, 'fur', k=2.6, spiky=P['wet'], kz=1.2))
    # ---- arms
    for s_, key in ((-1, 'L'), (1, 'R')):
        sh_ = che + [1.0, 3.5, s_ * 10.0] + np.array([.6, 1.0, -s_ * .3]) * P.get('shrug' + key, 0.0)
        paw = np.array(P['paw' + key], float)
        ax = P.get('armx' + key, 1.0)                  # a cheat for big reaches (a wave over the head)
        el, pw = ik2(sh_, paw, 9.4 * ax, 8.8 * ax, P['elb' + key])
        fa = unit(pw - el)
        prim = [Sweep([sh_ + [-.5, 2.0, 0], sh_, el, pw], [5.6, 5.3, 4.3, 3.6], None, fr_b),
                Ell(pw + fa * 1.6, (4.2, 3.5, 3.9), frame_from(fa), mat_paw, fr_b)]
        pc = Piece('arm' + key, prim, 'fur', k=1.4, roots=[(sh_, 7.0)], spiky=P['wet'] * .6)
        pc.toes = (pw + fa * 1.6, fa, 4.2)
        pieces.append(pc)
    # ---- legs: a round haunch, a short shin and a big webbed foot
    for s_, key in ((-1, 'L'), (1, 'R')):
        hip = pel + [2.0, -8.0, s_ * 8.5]
        ft = np.array(P['foot' + key], float)
        kn, an = ik2(hip, ft, 8.0, 7.5, (1, .2, s_ * .25))
        fp = P['fp' + key]
        fd = unit([math.cos(fp), math.sin(fp), s_ * .14])
        prim = [Sweep([hip, kn, an], [8.4, 5.6, 3.8], None, fr_b),
                Ell(an + fd * 4.2 + [0, -.4, 0], (6.4, 2.6, 4.3), frame_from(fd), mat_paw, fr_b)]
        pc = Piece('leg' + key, prim, 'fur', k=1.8, roots=[(hip, 10.0)])
        pc.toes = (an + fd * 4.2 + [0, -.4, 0], fd, 6.4)
        pieces.append(pc)
    # ---- tail: thick at the root, tapering, one smooth sweep
    tp = [pel + [-6, -6, 0]] + [np.array(q, float) for q in P['tail']]
    rad = [10.0, 8.2, 6.6, 5.0, 3.3, 1.4]
    pieces.append(Piece('tail', [Sweep(tp, rad, None, fr_b, n=6)], 'fur', k=1.5, roots=[(pel + [-6, -6, 0], 13.0)], spiky=P['wet'], lifts=3))
    # ---- scarf: the visible arc of a knitted ring around the neck, a knot and two ends
    nc = nek + [0.4, .4, 0]
    rn_here = P['rn'] + .3
    pieces.append(scarf_piece(P, V, nc, fr_b, rn_here))
    geo = dict(hd=hd, Rh=Rh, H=H, fr_h=fr_h, nc=nc)
    return pieces, geo


def scarf_piece(P, V, nc, fr_b, rn):
    """a snug knitted band (two rolled rows), a knot on the otter's right front, two short flat ends"""
    R0 = rn + .2; tube = 2.2
    view_dir = V.M.T @ np.array([0, 0, 1.0])          # toward the viewer, in body space
    th = np.linspace(-np.pi, np.pi, 73)
    prims = []
    arcs_ = []
    rr = R0 + .5
    ring = np.stack([nc[0] + rr * np.cos(th), nc[1] - 1.4 * np.maximum(np.cos(th), 0) ** 2 + .25 * np.sin(th * 3), nc[2] + rr * np.sin(th)], 1)
    vis = (ring - nc) @ view_dir > -.5
    if vis.any():
        idx = np.where(vis)[0]
        if vis[0] and vis[-1] and not vis.all():
            j = np.where(~vis)[0]; idx = np.r_[np.arange(j[-1] + 1, len(th) - 1), np.arange(0, j[0])]
        arc = ring[idx]
        arcs_.append(arc)
        for i in range(0, len(arc), 2):
            c = arc[i]; tg = arc[min(i + 1, len(arc) - 1)] - arc[max(i - 1, 0)]
            tg = unit(tg) if np.linalg.norm(tg) > 1e-6 else np.array([1., 0, 0])
            out_ = unit(c - nc - [0, c[1] - nc[1], 0])
            Rm = np.stack([tg, np.array([0, 1.0, 0]), out_], 1)
            prims.append(Ell(c, (2.6, 4.0, 2.3), Rm, mat_scarf, fr_b))
    ka = .55 if P['knot'] >= 0 else -.55
    kn = np.array([nc[0] + R0 * math.cos(ka) * 1.02, nc[1] - .2, nc[2] + R0 * math.sin(ka) * 1.02])
    sw = np.asarray(P['scarf'], float)
    prims.append(Ell(kn, (2.9, 3.0, 2.9), None, mat_scarf, fr_b))
    out = unit([math.cos(ka), 0, math.sin(ka)])
    ends = []
    to = P.get('scarf_to')
    for j, (dx, ln, w0, ph) in enumerate(((-.6, 10.5, 2.1, 0.0), (1.4, 8.0, 1.9, .7))):
        e = [kn, kn + out * 1.2 + [dx * .5 + sw[0] * .25, -ln * .45, 0], kn + out * 1.6 + [dx + sw[0] * .8, -ln + sw[1] * .3, sw[0] * .3 * math.sin(ph + 1)]]
        if j == 0 and to is not None:
            to = np.asarray(to, float) + [1.0, 1.6, 0]
            mid = (kn + to) / 2 + out * 2.0 + [0, -1.5, 0]
            e = [kn, mid, to]
        ends.append(e)
        prims.append(Sweep(e, [w0 * .8, w0, w0 * 1.15], mat_scarf, fr_b, n=4))
    pc = Piece('scarf', prims, 'scarf', k=1.2, lifts=4, kz=4.0)
    pc.arcs, pc.ends, pc.R0 = arcs_, ends, R0
    return pc


def toes(cel, pc, V, env, k, lw):
    """three short strokes splitting the webbed toes at the tip of a paw or foot"""
    c, fa, ln = pc.toes
    Rm = frame_from(fa); lat = Rm[:, 2]; up = Rm[:, 1]
    tip = c + fa * ln * .78
    for j, q in enumerate((-1.25, 0.0, 1.25)):
        a = tip + lat * q * 1.05 - fa * ln * .28 + up * .6
        b = tip + lat * q * 1.2 + fa * ln * .12 + up * .9
        p = V.p(np.array([a, b]))
        nrm = V.d(up * .3 + fa * .7)
        if nrm[2] < -.35: continue
        cel.line(p[:, :2], max(.9, lw * .6), env.line, (.1, .5), .2, seed=500 + j, alpha=.85)


def scarf_ribs(cel, pc, V, env, k, lw):
    """knit ribs across the band and a little fringe at the ends"""
    sh = env.colors('scarf')[1]
    for j, arc in enumerate(pc.arcs):
        rr_ = np.random.default_rng(11 + j)
        for i in np.cumsum(rr_.integers(2, 5, 40)):
            if i >= len(arc) - 2: break
            c = arc[i]
            p = V.p(np.array([c + [0, 3.0, 0], c + [0, -3.0, 0]]))
            if p[:, 2].mean() < V.p(arc[len(arc) // 2])[2] - pc.R0 * V.k * .9: continue
            cel.line(p[:, :2], max(.9, lw * .55), sh, (.3, .3), .2, seed=300 + i + 50 * j, alpha=.8)
    for j, e in enumerate(pc.ends):
        b = np.asarray(e[-1], float); dvec = unit(np.asarray(e[-1]) - np.asarray(e[-2]))
        for q in (-1.4, -.4, .6, 1.5):
            p = V.p(np.array([b + [q, 0, 0] + dvec * 1.5, b + [q * 1.1, 0, 0] + dvec * 3.6]))
            cel.line(p[:, :2], max(.9, lw * .6), sh if q < 1 else env.line, (.1, .6), .2, seed=400 + j * 9 + int(q * 3), alpha=.9)


# ------------------------------------------------------------------ face features
def ell_surface(c, radii, Rm, dirv):
    """point and normal on an ellipsoid (body space) along direction dirv from its centre (local)"""
    d = unit(dirv)
    t = 1 / math.sqrt(((d / radii) ** 2).sum())
    pl = d * t
    nl = unit(pl / radii ** 2)
    return c + Rm @ pl, Rm @ nl


def draw_eye(cel, V, geo, P, env, s, k, zbuf, lw):
    """s = -1 left eye, +1 right eye. zbuf = (z, ox, oy) of the head piece"""
    H, Rh = geo['H'], geo['Rh']
    hd = geo['hd']
    c, n = ell_surface(H([0, 0, 0]), np.array([12.6, 11.6, 14.6]), Rh, [.80, .26, s * .50])
    c = c + n * .25
    ns = V.d(n)
    if ns[2] < .22: return None
    t1 = unit(np.cross(Rh @ [0, 1, 0], n)) * s * -1    # horizontal on the face, pointing forward-ish
    t1 = unit(Rh @ [1, 0, 0] - n * ((Rh @ [1, 0, 0]) @ n))
    t2 = unit(np.cross(n, t1)) * (1 if (np.cross(n, t1) @ (Rh @ [0, 1, 0])) > 0 else -1)
    a, b = 3.25, 3.9
    ph = np.linspace(0, 2 * np.pi, 40, endpoint=False)
    E = lambda u, v: V.p(c[None] + np.outer(u * a, t1) + np.outer(v * b, t2))[:, :2] if np.ndim(u) else V.p(c + u * a * t1 + v * b * t2)[:2]
    outline = E(np.cos(ph), np.sin(ph))
    area = abs(np.sum(outline[:, 0] * np.roll(outline[:, 1], 1) - outline[:, 1] * np.roll(outline[:, 0], 1))) / 2
    if area < 12: return None
    zc = V.p(c)[2]
    bl, sq = P['blink'], P['squint']
    lx, ly = P['look']
    lid = 1 - 2.0 * bl                      # upper lid height in eye coords (+1 open .. -1 shut)
    low = -1 + 1.25 * sq                    # lower lid rising for a squint
    col_fur = env.colors('fur')[0] if True else None
    if bl < .92 and lid - low > .15:
        cel.ctx.save()
        cel.clip(outline)
        cel.fill(outline, env_eye(env, PAL['eye']))
        # iris: a dark brown ring, the pupil and the glints follow the look
        ic = np.array([lx * .32, ly * .25 - .05])
        th = np.linspace(0, 2 * np.pi, 32, endpoint=False)
        iris = E(ic[0] + .86 * np.cos(th), ic[1] + .9 * np.sin(th))
        cel.fill(iris, env_eye(env, PAL['iris']))
        cres = E(ic[0] + .62 * np.cos(th), ic[1] - .30 + .52 * np.sin(th))
        cel.fill(cres, env_eye(env, '#5a3a2c'), .9)
        pup = E(ic[0] + .55 * np.cos(th), ic[1] + .1 + .6 * np.sin(th))
        cel.fill(pup, env_eye(env, PAL['eye']))
        # glints: a big one toward the light and the lamp's small reflection
        L2 = env.L2
        hx = (L2[0] * .45 * (1 if (t1 @ V.M.T[0] if False else 1) else 1))
        gx_s, gy_s = L2[0], L2[1]
        # convert screen direction to eye uv
        J = np.array([V.d(t1)[:2] * a, V.d(t2)[:2] * b]).T
        try:
            uv = np.linalg.solve(J, np.array([gx_s, gy_s]))
            uv = uv / (np.linalg.norm(uv) + 1e-6)
        except np.linalg.LinAlgError:
            uv = np.array([.5, .5])
        g0 = ic * .5 + uv * .42 + [0, .12]
        cel.fill(E(g0[0] + .30 * np.cos(th), g0[1] + .34 * np.sin(th)), env.glint)
        g1 = ic * .5 - uv * .38 + [0, -.32]
        cel.fill(E(g1[0] + .13 * np.cos(th), g1[1] + .11 * np.sin(th)), mix(env.col, env.glint, .4), .9)
        # lids
        if bl > .02 or sq > .02:
            fu, fs_ = env.colors('fur')[:2]
            uu = np.linspace(-1.2, 1.2, 25)
            lidc = lid - .22 * (1 - uu ** 2) * (1 - bl) * 0 + .12 * (1 - uu ** 2) * bl
            top = np.vstack([E(uu, lidc), E(uu[::-1], np.full(25, 1.6))])
            if bl > .02: cel.fill(top, fu)
            if sq > .02:
                lowc = low + .35 * (1 - uu ** 2) * sq
                cream = env.colors('cream')[0]
                bot = np.vstack([E(uu, lowc), E(uu[::-1], np.full(25, -1.6))])
                cel.fill(bot, fu)
        cel.ctx.restore()
        # lid lines
        uu = np.linspace(-1, 1, 23)
        if bl > .02:
            yy = lid + .12 * (1 - uu ** 2) * bl
            ww = np.sqrt(np.clip(1 - (yy / 1.0) ** 2, 0, 1))
            uu2 = uu * np.maximum(ww, .3) * 1.05
            cel.line(E(uu2, yy), lw * 1.6, env.line, (.15, .25), .2, seed=int(s * 7 + 50))
        else:
            topl = E(np.cos(np.linspace(.08, np.pi - .08, 20)) * 1.04, np.sin(np.linspace(.08, np.pi - .08, 20)) * 1.04)
            cel.line(topl, lw * 1.7, env.line, (.2, .3), .2, seed=int(s * 7 + 50), wfun=lambda t: .5 + .9 * np.sin(np.pi * t) ** .6)
        if sq > .02:
            uu2 = uu * .95
            cel.line(E(uu2, low + .35 * (1 - uu2 ** 2) * sq), lw * 1.0, env.line, (.3, .3), .2, seed=int(s * 7 + 51))
    else:
        # shut: one curved stroke, bowed down, with a little lash
        uu = np.linspace(-1.05, 1.05, 23)
        yy = -.15 - .45 * (1 - uu ** 2) + .9 * sq * (1 - uu ** 2)
        cel.line(E(uu, yy), lw * 1.7, env.line, (.25, .25), .2, seed=int(s * 7 + 52), wfun=lambda t: .5 + .9 * np.sin(np.pi * t) ** .6)
    return dict(c=V.p(c)[:2], z=zc)


def env_eye(env, h):
    c = rgb(h)
    if env.dark > 0: c = mix(c, env.amb * .4, env.dark * .5)
    return c


def face_lines(cel, V, geo, P, env, k, lw, zinfo):
    """nose-to-mouth line and the mouth, on the muzzle front"""
    H = geo['H']
    mo = P['mouth']; sm = P['smile']
    z, ox, oy = zinfo

    def visible(q3):
        s = V.p(q3)
        xi, yi = int(s[0] - ox), int(s[1] - oy)
        if 0 <= yi < z.shape[0] and 0 <= xi < z.shape[1]:
            return s[2] >= z[yi, xi] - 1.6 * k
        return False

    def draw3(pts, w, sd, al=1.0, tp=(.3, .3)):
        q = np.array([H(p) for p in spl3(np.array(pts), n=8)])
        s = V.p(q)
        ok = np.array([visible(p) for p in q])
        if ok.mean() < .5: return
        cel.line(s[ok][:, :2] if ok.sum() > 3 else s[:, :2], lw * w, env.line, tp, .2, seed=sd, alpha=al)

    draw3([[18.0, -2.7, 0], [17.3, -4.6, 0], [16.9, -5.6, 0]], .8, 71)
    if mo >= .1:
        w_ = 2.6 + .6 * mo; dp = 1.2 + 3.4 * mo
        rim_ = [[16.9, -5.5, -w_ * .3], [16.6, -5.9, -w_], [15.9, -6.0 - dp * .6, -w_ * .7], [15.6, -6.0 - dp, 0], [15.9, -6.0 - dp * .6, w_ * .7], [16.6, -5.9, w_], [16.9, -5.5, w_ * .3]]
        q = np.array([H(p) for p in rim_]); sp = V.p(q)
        if np.mean([visible(p) for p in q]) > .4:
            poly = spl(sp[:, :2], closed=True)
            cel.fill(poly, env_eye(env, PAL['mouth']))
            cel.clip(poly)
            tg = V.p(np.array([H(p) for p in [[16.0, -6.0 - dp * .55, -w_ * .6], [15.8, -6.0 - dp * 1.1, 0], [16.0, -6.0 - dp * .55, w_ * .6], [16.3, -6.0 - dp * .35, 0]]]))
            cel.fill(spl(tg[:, :2], closed=True), env_eye(env, PAL['tongue']))
            cel.unclip()
            cel.line(np.vstack([poly, poly[:1]]), lw * .8, env.line, (.1, .1), .2, seed=77)
    if mo < .1:
        for s in (-1, 1):
            draw3([[16.9, -5.6, 0], [16.4, -6.6 + .4 * sm, s * 1.6], [15.6, -6.2 - .6 * sm, s * 3.2], [14.6, -5.2 - .9 * sm, s * 4.0]], .75, 72 + s)


def whiskers(cel, V, geo, P, env, k, lw, side, t):
    H = geo['H']
    tw = P['whisk']
    col = mix(rgb('#f3e8d4'), env.col, .25) if env.dark < .5 else mix(rgb('#9aa8c8'), env.col, .4)
    for i, (du, ln, dr) in enumerate(((.8, 21, -.10), (-.4, 23, .02), (-1.6, 19, .16))):
        root = np.array([15.6, -2.6 + du * .9, side * 4.6])
        t = P.get('wph', t)
        ang = dr + tw * (.06 + .03 * i) * math.sin(t * 1.0 + i * .8)
        d = unit([-.15, -ang * 2.2, side * 1.0])
        d2 = unit([-.55, -ang * 2.2 - .35, side * .8])
        pts = [root, root + d * ln * .35 + [0, .2, 0], root + d * ln * .7 + d2 * ln * .1 + [0, -.4, 0], root + d * ln * .8 + d2 * ln * .25 + [0, -1.6, 0]]
        q = V.p(spl3(np.array([H(p) for p in pts]), n=10))[:, :2]
        cel.line(q, max(1.0, lw * .55), col, (.02, .85), .1, seed=90 + i + side * 5, alpha=.9, tremor=.1)


# ------------------------------------------------------------------ draw
def _clipfor(clip, name):
    """clip may be one mask function for every cel, or a dict per piece name (key 'default' for the rest)"""
    if clip is None or callable(clip): return clip
    return clip.get(name, clip.get('default'))


def draw(img, view, P, env, seed=0, lw=None, clip=None, extra=None, ret_layer=False, parts=None):
    """composite the otter into img.  view: View; P: pose; env: Env.
    clip(ox, oy, w, h) -> alpha mask applied to every piece (e.g. the floor edge of a hatch).
    extra: list of (zkey, fn(cel)) prop layers drawn into the stack at depth zkey (screen z px).
    Returns dict of screen points."""
    V = view
    k = V.k
    if lw is None: lw = float(np.clip(1.5 + k * .2, 1.7, 3.4))
    pieces, geo = build(P, V)
    for q in pieces:
        for pr in q.prims: pr.bake(V)
        q.zkey = np.mean([pr.zc for pr in q.prims]) if q.zkey is None else q.zkey
    bias = dict(torso=0, head=3.0 * k, scarf=2.2 * k, tail=-6 * k)
    zo = P.get('zo', {}) or {}
    byn = {q.name: q for q in pieces}
    for q in pieces: q.zkey += bias.get(q.name, 0)
    byn['scarf'].zkey = byn['torso'].zkey + .5
    byn['head'].zkey = max(byn['head'].zkey, byn['scarf'].zkey + .5)
    for q in pieces: q.zkey += zo.get(q.name, 0) * k
    if parts is not None: pieces = [q for q in pieces if q.name in parts]
    hz = byn['head'].zkey
    near = 1 if V.d(geo['Rh'] @ [0, 0, 1])[2] > 0 else -1
    layers = [(q.zkey, 'piece', q) for q in pieces]
    if any(q.name == 'head' for q in pieces):
        layers.append((hz - .5, 'wfar', None))
        layers.append((hz + .5, 'face', None))
    if extra:
        for zk, fn in extra:
            if zk == 'front': zk = hz + .7          # in front of the face, behind a near arm
            layers.append((zk, 'extra', fn))
    layers.sort(key=lambda t: t[0])
    # ROI: everything
    bbs = [pr.bb for q in pieces for pr in q.prims]
    m = 26 * k
    X0 = int(min(b[0] for b in bbs) - m); Y0 = int(min(b[1] for b in bbs) - m)
    X1 = int(max(b[2] for b in bbs) + m); Y1 = int(max(b[3] for b in bbs) + m)
    Hh, Ww = img.shape[:2]
    X0, Y0 = max(X0, -200), max(Y0, -200); X1, Y1 = min(X1, Ww + 200), min(Y1, Hh + 200)
    buf = np.zeros((Y1 - Y0, X1 - X0, 4), f32)
    info_head = None
    out = {}
    t = seed * .5
    for zk, kind, obj in layers:
        if kind == 'piece':
            cf = _clipfor(clip, obj.name)
            r = render_piece(obj, V, env, seed, cf)
            if r is None: continue
            rgba, ox, oy, info = r
            if obj.name == 'head': info_head = info; head_z = _zfield(obj, V, info)
            cel = Cel(info['w'] + 8, info['h'] + 8, ox - 4, oy - 4)
            ink_piece(cel, obj, info, env, k, seed, lw)
            if obj.name == 'scarf': scarf_ribs(cel, obj, V, env, k, lw)
            if getattr(obj, 'toes', None) is not None: toes(cel, obj, V, env, k, lw)
            ln = cel.rgba()
            if cf is not None: ln *= cf(ox - 4, oy - 4, info['w'] + 8, info['h'] + 8)[..., None]
            over_into(buf, X0, Y0, rgba, ox, oy)
            over_into(buf, X0, Y0, ln, ox - 4, oy - 4)
        elif kind == 'wfar' or kind == 'face':
            cel = Cel(X1 - X0, Y1 - Y0, X0, Y0)
            if kind == 'wfar':
                whiskers(cel, V, geo, P, env, k, lw, -near, t)
            else:
                if info_head is None: continue
                zi = (head_z, info_head['ox'], info_head['oy'])
                for s in (-1, 1):
                    e = draw_eye(cel, V, geo, P, env, s, k, zi, lw)
                    if e: out['eye' + ('L' if s < 0 else 'R')] = e['c']
                face_lines(cel, V, geo, P, env, k, lw, zi)
                whiskers(cel, V, geo, P, env, k, lw, near, t)
            ln = cel.rgba()
            cf = _clipfor(clip, 'head')
            if cf is not None: ln *= cf(X0, Y0, X1 - X0, Y1 - Y0)[..., None]
            over_into(buf, X0, Y0, ln, X0, Y0)
        else:
            cel = Cel(X1 - X0, Y1 - Y0, X0, Y0)
            obj(cel)
            ln = cel.rgba()
            over_into(buf, X0, Y0, ln, X0, Y0)
    if ret_layer: return buf, X0, Y0
    # composite into img
    x0, y0 = max(0, X0), max(0, Y0); x1, y1 = min(Ww, X1), min(Hh, Y1)
    if x1 > x0 and y1 > y0:
        s = buf[y0 - Y0:y1 - Y0, x0 - X0:x1 - X0]
        img[y0:y1, x0:x1] = img[y0:y1, x0:x1] * (1 - s[..., 3:4]) + s[..., :3]
    H_ = geo['H']
    out.update(nose=V.p(H_([20.5, -.6, 0]))[:2], head=V.p(geo['hd'])[:2], mouth=V.p(H_([16.5, -6.5, 0]))[:2],
               pawL=V.p(P['pawL'])[:2], pawR=V.p(P['pawR'])[:2], footL=V.p(P['footL'])[:2], footR=V.p(P['footR'])[:2],
               chest=V.p(P['chest'])[:2])
    return out


def _zfield(piece, V, info):
    """front depth of the head piece at 1x, for hiding features behind the muzzle"""
    ox, oy, w, h = info['ox'], info['oy'], info['w'], info['h']
    g = max(1, int(round(V.k / 3.6)))
    gw, gh = int(math.ceil(w / g)) + 1, int(math.ceil(h / g)) + 1
    xs = ox + (np.arange(gw, dtype=f32) + .5) * g - .5
    ys = oy + (np.arange(gh, dtype=f32) + .5) * g - .5
    X, Y = np.meshgrid(xs, ys)
    Z = np.full(X.shape, -1e9, f32)
    for q in piece.prims:
        d, z, n, Ul = q.eval(X, Y)
        Z = np.where(d < 0, np.maximum(Z, z), Z)
    if g > 1: Z = cv2.resize(Z, (gw * g, gh * g), interpolation=cv2.INTER_NEAREST)
    return Z[:h, :w]
