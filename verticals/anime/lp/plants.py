"""Painted plants: wind-bent pine, ivy, moss, grass tufts (static gouache), and pampas (animated, drawn per frame).

    plants.pine(cv, trunk=[(x, y, w), ...], pads=[(x, y, rx, ry, t), ...], light=(-.7, -.7), seed=1)
    plants.ivy(cv, X, Y, V, seed=1)                     # leaf dabs at points, V 0..1 moonlight
    plants.tuft(cv, x, y, n, h, seed)                   # grass tuft
    P = plants.Pampas([(x, y, height, lean, size), ...], seed=2); cv = layer Canvas; P.draw(cv, bend)   # bend[n] radians at the tip
"""
import numpy as np, math
from .paint import f32, rgb, mix, Canvas, arcs, jit_color, smooth
from .ink import spl, resample, noise1

NIGHT_PINE = ('#1a1e42', '#252d58', '#374573', '#5a6c98', '#a9b7da')     # deep, dark, half, lit, rim
NIGHT_BARK = ('#221f43', '#37335f', '#5c5a8c', '#9a9cc8')
NIGHT_IVY = ('#1b2044', '#262f57', '#384a6f', '#5c7593', '#a9bdd6')


def _pal(p): return np.stack([rgb(c) if isinstance(c, str) else np.asarray(c, f32) for c in p])


def pick(pal, v, r=None, j=.05):
    """colour from a palette by value 0..1 with painterly jitter (hard-ish steps)"""
    pal = _pal(pal) if isinstance(pal[0], str) else np.asarray(pal, f32)
    v = np.asarray(v, f32)
    if r is not None: v = v + r.normal(0, j, v.shape).astype(f32)
    t = np.clip(v, 0, 1) * (len(pal) - 1)
    k = np.clip(np.floor(t).astype(int), 0, len(pal) - 2)
    fr = np.clip((t - k - .3) / .4, 0, 1)[..., None]
    return pal[k] * (1 - fr) + pal[k + 1] * fr


def limb(cv, pts, pal=NIGHT_BARK, light=(-.7, -.7), seed=0, density=1.0):
    """tapering trunk or branch: pts (x, y, full width), bark strokes along it, crisp lit edge"""
    r = np.random.default_rng(seed + 11)
    pts = np.asarray(pts, float)
    c = spl(pts[:, :2], n=10); s = np.r_[0, np.cumsum(np.hypot(*np.diff(c, axis=0).T))]
    sk = np.linspace(0, 1, len(pts)); w = np.interp(s / s[-1], sk, pts[:, 2])
    T = np.gradient(c, axis=0); T /= np.hypot(T[:, 0], T[:, 1])[:, None] + 1e-9
    N = np.c_[-T[:, 1], T[:, 0]]
    L = s[-1]
    # silhouette
    K = 9
    u = np.linspace(0, 1, max(2, int(L / 5)) + 1)
    P = []; W = []; C = []; O = []
    def at(uu, off):
        x = np.interp(uu * L, s, c[:, 0]); y = np.interp(uu * L, s, c[:, 1])
        nx = np.interp(uu * L, s, N[:, 0]); ny = np.interp(uu * L, s, N[:, 1]); ww = np.interp(uu * L, s, w)
        return np.stack([x + nx * off * ww * .5, y + ny * off * ww * .5], -1), ww
    for a, b in zip(u[:-1], u[1:]):
        q, ww = at(np.linspace(a - .4 * (b - a), b + .4 * (b - a), 5).clip(0, 1), 0)
        P.append(q); W.append(max(.6, ww.mean() * .5)); C.append(pick(pal, .16 + r.normal(0, .05)))
    cv.strokes(np.array(P), np.array(W), np.array(C), seed=seed, shape='flat', bristle=.06)
    # bark strokes
    n = int(L * w.mean() / 14 * density) + 4
    uu = r.uniform(0, 1, n); off = r.uniform(-.85, .85, n)
    P = np.empty((n, 5, 2)); W = np.empty(n); V = np.empty(n)
    for i in range(n):
        ln = r.uniform(5, 16) / L
        q, ww = at(np.linspace(uu[i] - ln / 2, uu[i] + ln / 2, 5).clip(0, 1), off[i])
        q[:, 0] += r.normal(0, .5, 5); P[i] = q; W[i] = max(.5, ww.mean() * r.uniform(.08, .2))
        nx = np.interp(uu[i] * L, s, N[:, 0]); ny = np.interp(uu[i] * L, s, N[:, 1])
        V[i] = .34 + .5 * off[i] * (nx * light[0] + ny * light[1])
    cv.strokes(P, W, jit_color(pick(pal, V, r, .07), r), op=r.uniform(.55, .95, n), dry=.2, seed=seed + 1, shape='round')
    # rim
    for sd in (-1, 1):
        for a in np.arange(0, 1, 14 / L):
            uq = np.linspace(a, min(1, a + r.uniform(9, 20) / L), 5)
            q, ww = at(uq, sd * .86)
            m = np.interp(uq[2] * L, s, N[:, 0]) * sd * light[0] + np.interp(uq[2] * L, s, N[:, 1]) * sd * light[1]
            if m > .2 and r.random() < .85:
                cv.strokes(q[None], max(.55, ww.mean() * .085), pick(pal, np.array([.75 + .25 * m]), r, .06), op=r.uniform(.6, 1), seed=seed + int(a * 997), shape='round')


def pad(cv, x, y, rx, ry, light=(-.7, -.7), pal=NIGHT_PINE, seed=0, needle=8., dens=1.0, flag=0.0, rim=1.0):
    """one layered needle clump: flat dark underside, domed lit top, spiky edge.  flag = wind sweep (+ right)"""
    r = np.random.default_rng(seed + 5)
    nb = max(2, int(rx / (ry * 1.1)) + 1)
    bx = np.linspace(-.72, .72, nb) * rx + r.normal(0, .08, nb) * rx; bh = r.uniform(.6, 1.1, nb) * ry; bw = rx / nb * r.uniform(1.0, 1.5, nb)
    def top(u):
        e = np.zeros_like(u)
        for a, b, c in zip(bx, bh, bw): e = np.maximum(e, b * np.sqrt(np.clip(1 - ((u - a) / c) ** 2, 0, 1)))
        return e * np.clip(1.15 - (np.abs(u) / rx) ** 4, .1, 1)
    n = int(rx * ry / (needle * needle) * 3.0 * dens) + 12
    for lay in range(4):
        m = int(n * (1.1, 1., .8, .55)[lay])
        u = r.uniform(-1, 1, m) * rx; tp = top(u)
        q = (r.uniform(-.2, .35, m), r.uniform(0, .75, m), r.uniform(.35, .95, m), r.uniform(.74, 1.02, m))[lay]
        px = x + u + flag * ry * q; py = y - tp * q
        # each tuft = a fan of needles
        k = 6
        an = -np.pi / 2 + flag * .5 + (u / rx) * .5
        A = (an[:, None] + (np.arange(k) / (k - 1) - .5)[None] * r.uniform(1.3, 2.5, (m, 1)) + r.normal(0, .16, (m, k))).ravel()
        if lay == 0: A = np.where(r.random(A.size) < .5, A + np.pi * r.uniform(.6, 1.2, A.size), A)
        ln = (needle * r.uniform(.55, 1.25, (m, k))).ravel()
        bxx = np.repeat(px, k); byy = np.repeat(py, k)
        P = arcs(bxx + np.cos(A) * ln * .5, byy + np.sin(A) * ln * .5, A, ln, r.normal(0, .35, A.size), K=3)
        side = -light[0] * (u / rx) * -1
        v = (.10, .30, .48, .70)[lay] + .16 * (u / rx) * light[0] + .10 * (q - .5) + r.normal(0, .06, m)
        col = jit_color(pick(pal, np.repeat(np.clip(v, 0, 1), k), r, .05), r, .008, .02, .03)
        cv.strokes(P, np.full(len(P), max(.55, needle * .085)), col, op=r.uniform(.75, 1, len(P)), seed=seed + lay * 17, shape='taper', bristle=.03)
    # moonlit rim needles on the sun-side crown
    m = int(n * .8 * rim)
    u = r.uniform(-1, 1, m) * rx; tp = top(u)
    sl = (top(u + 2) - top(u - 2)) / 4
    ok = (sl * -light[0] * -1 * .6 + .35 + .3 * (u / rx) * light[0] + r.normal(0, .2, m)) > .18
    u, tp = u[ok], tp[ok]; k = 4; m = len(u)
    if m:
        A = (-np.pi / 2 + flag * .5 + light[0] * .5 + r.normal(0, .55, (m, k))).ravel(); ln = (needle * r.uniform(.5, 1.05, (m, k))).ravel()
        px = np.repeat(x + u + flag * ry, k); py = np.repeat(y - tp * .98, k)
        P = arcs(px + np.cos(A) * ln * .5, py + np.sin(A) * ln * .5, A, ln, 0, K=3)
        cv.strokes(P, np.full(len(P), max(.5, needle * .07)), jit_color(pick(pal, np.clip(r.normal(.80, .10, len(P)) + np.repeat(.14 * (u / rx) * light[0], k), .5, 1)), r, .006, .02, .03), op=r.uniform(.5, .95, len(P)), seed=seed + 91, shape='taper', bristle=.02)


def pine(cv, trunk, pads, light=(-.7, -.7), pal=NIGHT_PINE, bark=NIGHT_BARK, seed=0, needle=8., flag=.3, rim=1.0, roots=True, bark_light=(-.45, -.9)):
    """pads: (x, y, rx, ry, t) painted back to front; t = where on the trunk (0 base..1 tip) its branch leaves"""
    r = np.random.default_rng(seed)
    trunk = np.asarray(trunk, float)
    c = spl(trunk[:, :2], n=10); s = np.r_[0, np.cumsum(np.hypot(*np.diff(c, axis=0).T))]
    w = np.interp(np.linspace(0, 1, 50), np.linspace(0, 1, len(trunk)), trunk[:, 2])
    back = [p for i, p in enumerate(pads) if i % 3 == 0]; front = [p for i, p in enumerate(pads) if i % 3 != 0]
    for j, p in enumerate(back): pad(cv, p[0], p[1], p[2], p[3], light, pal, seed + 40 + j, needle, flag=flag, rim=rim * .5)
    for j, p in enumerate(pads):
        t = p[4]; bx = np.interp(t * s[-1], s, c[:, 0]); by = np.interp(t * s[-1], s, c[:, 1]); bw = np.interp(t, np.linspace(0, 1, 50), w) * .42
        mx = (bx + p[0]) / 2 + r.normal(0, 4); my = max(by, p[1]) + r.uniform(-4, 6) - .25 * abs(by - p[1])
        limb(cv, [(bx, by, max(1.6, bw)), (mx, my, max(1.3, bw * .7)), (p[0] - .15 * p[2], p[1] - .1 * p[3], max(.9, bw * .35))], bark, light, seed + 300 + j)
    if roots:                                                     # fingers gripping the rock
        bx, by, bw = trunk[0]; dx, dy = trunk[0, :2] - trunk[1, :2]; a0 = math.atan2(dy, dx)
        for j, (da, ln, ww) in enumerate(((-.85, 1.5, .42), (-.3, 1.9, .5), (.25, 2.2, .46), (.8, 1.4, .38), (1.3, 1.2, .3))):
            a = a0 + da + r.normal(0, .12); L = bw * ln * r.uniform(.8, 1.2)
            p0 = np.array([bx - dx * .12, by - dy * .12]); p1 = p0 + np.array([math.cos(a), math.sin(a)]) * L * .55; p2 = p0 + np.array([math.cos(a) * .9, math.sin(a) * .9 + .45]) * L
            limb(cv, [(*p0, bw * .7), (*p1, bw * ww), (*p2, bw * .12)], bark, bark_light, seed + 700 + j)
    limb(cv, trunk, bark, bark_light, seed + 5)
    for j, p in enumerate(front): pad(cv, p[0], p[1], p[2], p[3], light, pal, seed + 140 + j, needle, flag=flag, rim=rim)


def ivy(cv, X, Y, V, seed=0, size=4.0, pal=NIGHT_IVY, lab=None, LAB=None):
    """leaf dabs.  X, Y px, V 0..1 light.  painted dark under, light over, every leaf its own angle and colour"""
    r = np.random.default_rng(seed + 3)
    X, Y, V = [np.asarray(a, f32) for a in (X, Y, V)]
    o = np.argsort(V + r.normal(0, .12, len(V)))
    X, Y, V = X[o], Y[o], V[o]
    n = len(X)
    A = np.pi / 2 + r.normal(0, .75, n); ln = size * r.uniform(1.2, 2.3, n)
    P = arcs(X, Y, A, ln, r.normal(0, .5, n), K=4)
    col = jit_color(pick(pal, V, r, .06), r, .012, .03, .04)
    cv.strokes(P, size * r.uniform(.42, .78, n), col, op=r.uniform(.82, 1, n), seed=seed, shape='leaf', bristle=.04)


def tuft(cv, x, y, n, h, seed=0, spread=14, pal=('#1f2348', '#2f3762', '#4d5a86', '#8f9cc6'), v=.35, lean=.25):
    """grass tuft: n curved tapering blades from (x, y)"""
    r = np.random.default_rng(seed + 17)
    xx = x + r.normal(0, spread * .5, n); A = -np.pi / 2 + lean + r.normal(0, .38, n); ln = h * r.uniform(.45, 1.15, n)
    P = arcs(xx + np.cos(A) * ln / 2, y + np.sin(A) * ln / 2, A, ln, r.normal(.5, .5, n), K=5)
    cv.strokes(P, np.maximum(.6, h * .035) * r.uniform(.7, 1.3, n), jit_color(pick(pal, v + r.normal(0, .16, n)), r), seed=seed, shape='taper')


class Pampas:
    """pampas clump, every stalk and plume hair fixed at birth; draw(cv, bend) bends them as drawn curves.
    stalks: (x, y root, height px, lean rad, size)."""

    def __init__(self, stalks, seed=0, hairs=84, leaves=3, pal=('#1d1a3d', '#2b2854', '#45447c', '#7579b2', '#b9c2e4')):
        self.r = r = np.random.default_rng(seed)
        self.st = np.asarray(stalks, float); self.n = n = len(self.st)
        self.pal = _pal(pal)
        self.hairs = hairs; self.nl = leaves
        self.curl = r.normal(.25, .22, n); self.phase = r.uniform(0, 1, n); self.droop = r.uniform(.45, 1.0, n)
        self.pl = r.uniform(.20, .30, n)                  # plume fraction of the stalk
        self.hu = np.sort(r.uniform(0, 1, (n, hairs)) ** .85, 1)
        self.hs = np.where(r.random((n, hairs)) < .5, -1, 1) * r.uniform(.15, 1.0, (n, hairs))
        self.hl = r.uniform(.5, 1.15, (n, hairs)); self.hc = r.uniform(.2, 1.0, (n, hairs)); self.hj = r.normal(0, 1, (n, hairs)); self.hw = r.uniform(.7, 1.25, (n, hairs))
        self.la = r.normal(0, .30, (n, leaves)); self.ll = r.uniform(.26, .58, (n, leaves)); self.lc = r.uniform(.4, 1.3, (n, leaves)); self.lx = r.normal(0, 7, (n, leaves))
        self.tone = r.normal(0, .05, n)

    def spine(self, i, b, K=22):
        x, y, h, lean, sz = self.st[i]
        u = np.linspace(0, 1, K)
        pf = 1 - self.pl[i]
        dr = np.clip((u - pf * .92) / (1 - pf * .92), 0, 1) ** 1.3 * self.droop[i] * np.sign(lean + 1e-3)
        th = -np.pi / 2 + lean * u ** 1.2 + self.curl[i] * .35 * u ** 2 * np.sign(lean + 1e-3) + b * u ** 1.6 + dr + b * .55 * np.clip((u - pf) / (1 - pf), 0, 1)
        d = h / (K - 1)
        px = x + np.r_[0, np.cumsum(np.cos(th[:-1]) * d)]; py = y + np.r_[0, np.cumsum(np.sin(th[:-1]) * d)]
        return u, px, py, th

    def draw(self, cv, bend, light=-.6, scale=1.0, rim=1.0, seed=0):
        """bend: (n,) or (n, 2) stalk and plume-hair bend in radians"""
        bend = np.asarray(bend, float)
        if bend.ndim == 1: bend = np.stack([bend, bend], 1)
        pal = self.pal
        for i in range(self.n):
            x, y, h, lean, sz = self.st[i]
            b, bh = bend[i]
            u, px, py, th = self.spine(i, b)
            # leaves
            P = []; Wd = []; C = []
            for j in range(self.nl):
                K = 9; t = np.linspace(0, 1, K); L = h * self.ll[i, j]
                a = -np.pi / 2 + lean * .5 + self.la[i, j] + (np.sign(self.la[i, j]) * self.lc[i, j] * .9 + b * 1.1) * t ** 1.6
                dd = L / (K - 1)
                P.append(np.stack([x + self.lx[i, j] * sz + np.r_[0, np.cumsum(np.cos(a[:-1]) * dd)], y + np.r_[0, np.cumsum(np.sin(a[:-1]) * dd)]], -1))
                Wd.append(1.9 * sz); C.append(pick(pal, np.array([.16 + self.tone[i] + .10 * (j % 3 == 0)]))[0])
            if P: cv.strokes(np.array(P), np.array(Wd), np.array(C), seed=seed + i, shape='taper', bristle=.05)
            # stem (tapered, with a moonlit edge)
            S = np.stack([px, py], -1)
            idx = np.linspace(0, len(u) - 1, 12).astype(int)
            cv.strokes(S[idx][None], 1.45 * sz, pick(pal, np.array([.2 + self.tone[i]])), seed=seed + i + 500, shape='round', bristle=.03)
            lit = S[idx[3:]] + np.array([np.sign(light) * .9 * sz, 0])
            cv.strokes(lit[None], .55 * sz, pick(pal, np.array([.62])), op=.6 * rim, seed=seed + i + 900, shape='round')
            # plume
            pf = 1 - self.pl[i]
            hu = pf + (1 - pf) * self.hu[i]
            ax = np.interp(hu, u, px); ay = np.interp(hu, u, py); ath = np.interp(hu, u, th)
            env = np.sin(np.pi * np.clip(self.hu[i] * .86 + .10, 0, 1)) ** .7
            L = h * self.pl[i] * .46 * self.hl[i] * (.45 + .75 * env)
            K = 5; t = np.linspace(0, 1, K)[None]
            side = self.hs[i]
            a0 = ath + side * (.16 + .50 * env)
            sg = np.sign(lean + 1e-3)
            grav = (sg * .55 * self.hc[i] + bh * 1.2)
            A = a0[:, None] + (side * -.12)[:, None] * t + grav[:, None] * t ** 1.5 + (self.hj[i] * .10)[:, None] * t
            dd = (L / (K - 1))[:, None]
            X = ax[:, None] + np.c_[np.zeros(len(ax)), np.cumsum(np.cos(A[:, :-1]) * dd, 1)]
            Y = ay[:, None] + np.c_[np.zeros(len(ax)), np.cumsum(np.sin(A[:, :-1]) * dd, 1)]
            P = np.stack([X, Y], -1)
            # moon side: hairs that lie up and toward the light are paler; the lee side stays dark
            ux, uy = np.cos(ath), np.sin(ath)
            mx, my = X.mean(1) - ax, Y.mean(1) - ay
            lat = (mx * uy - my * ux) * (1 if light < 0 else -1) / (np.abs(L) * .30 + 1e-3)      # + on the moon side of the rachis
            v = .34 + .30 * np.clip(lat, -1, 1) + .10 * (self.hu[i] - .4) + .06 * self.hj[i] + self.tone[i]
            o = np.argsort(v)
            # soft body wash, then dark lee hairs, half, lit
            m = u >= pf - .02
            if m.sum() >= 3:
                q = S[m]; qi = np.linspace(0, m.sum() - 1, 7).astype(int)
                cv.strokes(q[qi][None] + np.array([0, 1.0]), 4.2 * sz, pick(pal, np.array([.26 + self.tone[i]])), op=.55, seed=seed + i + 77, shape='round', bristle=.12, dry=.25)
            col = pick(pal, np.clip(v, 0, 1))
            cv.strokes(P[o], (.95 * sz * self.hw[i] * (.7 + .6 * env))[o], col[o], op=.88, seed=seed + i * 7, shape='taper', bristle=.05)
            # spikelet tips: short brighter flecks along the moon side
            rr = (v > .40) & (self.hj[i] > -.6)
            if rr.any() and rim > 0:
                Q = P[rr][:, 1:] + np.array([np.sign(light) * .7 * sz, -.6 * sz])
                cv.strokes(Q, .55 * sz * self.hw[i][rr], pick(pal, np.clip(.50 + v[rr] * .62, 0, 1)), op=.85 * rim, seed=seed + i * 11, shape='taper', bristle=.02)


def springs(n_frames, force, k=.020, c=.11, sub=2):
    """damped spring response table: force(t)->(n,) array; returns (n_frames, n).  For grass bending under gusts."""
    x = np.zeros_like(force(0), dtype=float); v = np.zeros_like(x); out = []
    for f in range(-60, n_frames):
        for s in range(sub):
            a = k * (force(f + s / sub) - x) - c * v
            v = v + a / sub; x = x + v / sub
        if f >= 0: out.append(x.copy())
    return np.array(out)
