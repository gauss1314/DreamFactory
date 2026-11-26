"""Sumi brush.  Owner: ink lane.

A stroke is a path with belly radius (pressure), writing speed (two-thirds power law), an ink load that runs dry and a
tuft whose tip drags behind the hand.  It is rasterised once on a flat sheet into per-visit maps (arrival time, lateral
bristle coordinate, edge distance) so any fraction of the writing can be shown in O(pixels): the stroke grows with a wet
front that dries.  Self-crossings keep separate visits, so a loop overlaps itself like real ink."""
import numpy as np, cv2, math
from numba import njit
from scipy.interpolate import CubicSpline, PchipInterpolator
from .paint import f32, fbm, smooth


# ------------------------------------------------------------- paper fields
_tiles = {}


def fibre_tile(n=1024, seed=11, count=5200, lmin=14, lmax=64, w=1):
    """tileable 0..1 field of fine curved fibres (the capillaries ink creeps along)"""
    key = (n, seed, count, lmin, lmax, w)
    if key in _tiles: return _tiles[key]
    r = np.random.default_rng(seed)
    acc = np.zeros((n, n), f32)
    for b in range(4):
        im = np.zeros((n, n), np.uint8)
        for _ in range(count // 4):
            x, y = r.uniform(0, n, 2); a = r.uniform(0, math.pi); L = r.uniform(lmin, lmax); c = r.normal(0, .9) / L
            m = max(4, int(L / 5)); t = np.linspace(0, L, m)
            th = a + c * t
            px = x + np.cumsum(np.cos(th)) * L / m; py = y + np.cumsum(np.sin(th)) * L / m
            q = np.c_[px, py]
            for ox in (-n, 0, n):
                for oy in (-n, 0, n):
                    p = q + (ox, oy)
                    if p[:, 0].max() < 0 or p[:, 0].min() > n or p[:, 1].max() < 0 or p[:, 1].min() > n: continue
                    cv2.polylines(im, [np.round(p * 16).astype(np.int32)], False, int(r.integers(90, 255)), w, cv2.LINE_AA, 4)
        acc = np.maximum(acc * .8, im.astype(f32) / 255.)
    acc = cv2.GaussianBlur(np.pad(acc, 8, 'wrap'), (0, 0), .7)[8:-8, 8:-8]
    acc = np.clip(acc / np.percentile(acc, 99), 0, 1)
    _tiles[key] = acc
    return acc


def tile_to(t, h, w, ox=0, oy=0):
    n = t.shape[0]
    return np.tile(t, (h // n + 2, w // n + 2))[oy:oy + h, ox:ox + w]


_br = {}


def _bristles(seed):
    """lateral x along contact-noise texture: rows = bristles, cols = distance"""
    if seed not in _br:
        r = np.random.default_rng(500 + seed)
        R, C = 256, 4096
        out = np.zeros((R, C), f32)
        for nb, ln, wt in ((6, 380, .95), (14, 230, 1.0), (33, 120, .8), (84, 60, .42)):
            g = r.standard_normal((nb, max(8, C // ln))).astype(f32)
            g = np.c_[g, g[:, :1]]
            M = np.float32([[C / (g.shape[1] - 1.), 0, 0], [0, R / (nb - 1.), 0]])
            out += wt * cv2.warpAffine(g, M, (C, R), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REFLECT_101)
        # rank-normalise to 0..1 so a dryness threshold is a coverage fraction
        o = np.argsort(np.argsort(out, axis=None), axis=None).reshape(R, C).astype(f32) / (R * C)
        _br[seed] = o
    return _br[seed]


# ------------------------------------------------------------------ strokes
class Stroke:
    """ctrl: rows (x, y, r[, kind]) with r = belly radius; kind 'c' = corner, 'd' = dwell, 'l' = lifted (dry) point."""

    def __init__(self, ctrl, step=.8, load=(1.0, .35), entry=None, tip=1.35, alpha=.62, dwell=(), vel=None, seed=0,
                 depl=1.0, wet=1.0, dry=1.0, split=0.0, vmax=None):
        P = np.array([[c[0], c[1]] for c in ctrl], float)
        W = np.array([c[2] for c in ctrl], float)
        kinds = [c[3] if len(c) > 3 else '' for c in ctrl]
        cor = [0] + [i for i, k in enumerate(kinds) if 'c' in k and 0 < i < len(P) - 1] + [len(P) - 1]
        xs, ws, marks = [], [], []
        for a, b in zip(cor[:-1], cor[1:]):
            p = P[a:b + 1]
            d = np.hypot(*np.diff(p, axis=0).T) ** alpha
            t = np.r_[0, np.cumsum(np.maximum(d, 1e-3))]
            if len(p) == 2:
                f = lambda q, p=p, t=t: p[0] + (p[1] - p[0]) * (q / t[-1])[:, None]
            else:
                cs = CubicSpline(t, p, bc_type='natural'); f = lambda q, cs=cs: cs(q)
            w = PchipInterpolator(t, W[a:b + 1])
            q = np.linspace(0, t[-1], 60 * len(p))
            x = f(q)
            s = np.r_[0, np.cumsum(np.hypot(*np.diff(x, axis=0).T))]
            n = max(3, int(s[-1] / step) + 1)
            q2 = np.interp(np.linspace(0, s[-1], n), s, q)
            xs.append(f(q2) if not xs else f(q2)[1:]); ws.append(w(q2) if len(ws) == 0 else w(q2)[1:])
        X = np.vstack(xs); R = np.maximum(np.concatenate(ws), 0)
        n = len(X)
        ds = np.r_[0, np.hypot(*np.diff(X, axis=0).T)]
        S = np.cumsum(ds)
        # direction (smoothed) and curvature
        T = np.gradient(X, axis=0); T /= np.hypot(*T.T)[:, None] + 1e-9
        sg = 3.0 / step
        k = int(sg * 3) | 1
        ker = cv2.getGaussianKernel(k, sg)[:, 0]
        Ts = np.c_[np.convolve(np.pad(T[:, 0], k // 2, 'edge'), ker, 'valid'), np.convolve(np.pad(T[:, 1], k // 2, 'edge'), ker, 'valid')]
        Ts /= np.hypot(*Ts.T)[:, None] + 1e-9
        th = np.unwrap(np.arctan2(Ts[:, 1], Ts[:, 0]))
        kap = np.abs(np.gradient(th)) / step
        kk = int(16 / step) | 1
        kap = np.convolve(np.pad(kap, kk // 2, 'edge'), np.ones(kk) / kk, 'valid')
        Rm = max(R.max(), 1e-3)
        v = np.clip(kap * 60, .18, 9) ** (-1 / 3.) * (1 - .42 * np.clip(R / Rm, 0, 1) ** 1.2)
        if vel is not None:                                       # user speed profile over arc fraction
            f = S / S[-1]; v = v * np.interp(f, [a for a, _ in vel], [b for _, b in vel])
        v *= 1 - .6 * np.exp(-S / (Rm * 1.5 + 4)) * (1 if entry is not None else .4)
        dt = ds / v
        for (fr, amount) in dwell:                                # pause near arc fraction
            g = np.exp(-((S / S[-1] - fr) * S[-1] / (Rm * .6 + 5)) ** 2); dt += amount * S[-1] * g / g.sum()
        t = np.cumsum(dt); t /= t[-1]
        vn = np.gradient(S) / np.maximum(np.gradient(t), 1e-9); vn /= np.median(vn)
        kv = int(14 / step) | 1
        vn = np.convolve(np.pad(vn, kv // 2, 'edge'), np.ones(kv) / kv, 'valid')
        # tuft: tip drags behind
        D = np.array([math.cos(entry), math.sin(entry)]) if entry is not None else Ts[0].copy()
        Dl = np.empty_like(Ts)
        for i in range(n):
            lc = max(2.5, R[i] * 1.25)
            D = D + (Ts[i] - D) * min(1., step / lc)
            Dl[i] = D
        Dl /= np.hypot(*Dl.T)[:, None] + 1e-6
        use = np.cumsum(R * ds); use /= use[-1] + 1e-9
        ld = load[0] + (load[1] - load[0]) * use ** depl
        for (cx, cy, *_), kd in zip(ctrl, kinds):                  # 'w' = a press that squeezes ink out
            if 'w' in kd:
                j = int(np.argmin(np.hypot(X[:, 0] - cx, X[:, 1] - cy)))
                ld = ld + (.95 - ld) * np.exp(-((S - S[j]) / (R[j] * 1.6 + 6)) ** 2)
        self.X, self.R, self.S, self.t, self.v, self.load, self.T, self.n = X, R, S, t, vn, ld, Ts, n
        self.tipx = -Dl * (R * tip)[:, None]; self.step, self.seed = step, seed
        self.wet, self.dry, self.split = wet, dry, split


def blob(x, y, r, seed=0, stretch=0.0, ang=0.0, wet=1.0, load=1.0):
    """a drop / dot as a tiny stroke"""
    d = max(.6, r * stretch)
    c, s = math.cos(ang), math.sin(ang)
    S = Stroke([(x - c * d, y - s * d, r * .62), (x, y, r), (x + c * d * .5, y + s * d * .5, r * .9)], step=.35, load=(load, load), tip=.25, seed=seed, wet=wet)
    S.v[:] = .5
    return S


@njit(cache=True, fastmath=True)
def _raster(X, Y, R, TX, TY, DX, DY, GAP, SID, E, I, U, V, A, AM, LAST, CNT, w, h, m, K):
    n = X.shape[0]
    for i in range(n):
        r = R[i]
        if r < .12: continue
        bx = X[i]; by = Y[i]; tx = TX[i]; ty = TY[i]
        rt = r * .16
        L2 = tx * tx + ty * ty + 1e-6
        x0 = min(bx - r, bx + tx - rt) - m; x1 = max(bx + r, bx + tx + rt) + m
        y0 = min(by - r, by + ty - rt) - m; y1 = max(by + r, by + ty + rt) + m
        ix0 = max(0, int(x0)); ix1 = min(w - 1, int(x1) + 1)
        iy0 = max(0, int(y0)); iy1 = min(h - 1, int(y1) + 1)
        for y in range(iy0, iy1 + 1):
            for x in range(ix0, ix1 + 1):
                px = x - bx; py = y - by
                q = (px * tx + py * ty) / L2
                if q < 0: q = 0.0
                if q > 1: q = 1.0
                ex = px - tx * q; ey = py - ty * q
                d = r + (rt - r) * q - math.sqrt(ex * ex + ey * ey)
                if d < -m: continue
                k = CNT[y, x] - 1
                rev = False
                if k >= 0 and k < K - 1 and d > -1.0:
                    j = I[k, y, x]
                    rev = DX[i] * DX[j] + DY[i] * DY[j] < -.25 and E[k, y, x] > .5
                if k < 0 or rev or ((i - LAST[y, x]) > GAP[i] and k < K - 1 and d > -m * .999):
                    if k < 0 or E[k, y, x] > -m * .7:
                        k += 1
                        CNT[y, x] = k + 1
                    E[k, y, x] = -1e6; V[k, y, x] = 1e9; A[k, y, x] = -1; I[k, y, x] = i
                LAST[y, x] = i
                if d > E[k, y, x]:
                    E[k, y, x] = d; AM[k, y, x] = i
                if A[k, y, x] < 0 and d > -.4: A[k, y, x] = i
                v = abs(px * DX[i] + py * DY[i]); lt = px * -DY[i] + py * DX[i]
                v = v + .12 * abs(lt)
                if v < V[k, y, x]:
                    V[k, y, x] = v; I[k, y, x] = i
                    U[k, y, x] = lt / r


class Sheet:
    """flat sheet of paper that gets written on.  add(stroke, f0, f1) in film frames, then bake()."""

    def __init__(self, w, h, K=3, margin=12, seed=0, fib=None):
        self.w, self.h, self.K, self.m, self.seed = w, h, K, margin, seed
        self.items = []
        self.fib = fib

    def add(self, st, f0, f1, ease=None, warp=None):
        """f0..f1: frames over which it is drawn.  warp: optional function of t in 0..1 -> 0..1"""
        self.items.append((st, float(f0), float(f1), warp)); return self

    def bake(self):
        X = np.concatenate([s.X for s, *_ in self.items]); R = np.concatenate([s.R for s, *_ in self.items])
        TI = np.concatenate([s.tipx for s, *_ in self.items]); T = np.concatenate([s.T for s, *_ in self.items])
        fr = np.concatenate([a + (b - a) * (s.t if wp is None else wp(s.t)) for s, a, b, wp in self.items])
        cat = lambda g: np.concatenate([g(s) for s, *_ in self.items]).astype(f32)
        sid = np.concatenate([np.full(s.n, j, np.int32) for j, (s, *_) in enumerate(self.items)])
        GAP = np.concatenate([(2.0 * s.R + 2.2 * self.m + 8) / s.step for s, *_ in self.items]).astype(np.int64)
        K, h, w, m = self.K, self.h, self.w, float(self.m)
        E = np.full((K, h, w), -1e6, f32); I = np.full((K, h, w), -1, np.int32); U = np.zeros((K, h, w), f32)
        V = np.full((K, h, w), 1e9, f32); A = np.full((K, h, w), -1, np.int32); AM = np.full((K, h, w), -1, np.int32)
        LAST = np.full((h, w), -10 ** 8, np.int64); CNT = np.zeros((h, w), np.int32)
        _raster(X[:, 0].astype(np.float64), X[:, 1].astype(np.float64), R.astype(np.float64), TI[:, 0].copy(), TI[:, 1].copy(),
                T[:, 0].copy(), T[:, 1].copy(), GAP, sid, E, I, U, V, A, AM, LAST, CNT, w, h, m, K)
        sp, ld, wt, dr, spl_ = cat(lambda s: s.v), cat(lambda s: s.load), cat(lambda s: np.full(s.n, s.wet)), cat(lambda s: np.full(s.n, s.dry)), cat(lambda s: np.full(s.n, s.split))
        S = cat(lambda s: s.S); sd = cat(lambda s: np.full(s.n, (s.seed * 37) % 251))
        SL = cat(lambda s: np.full(s.n, s.S[-1])); fr = fr.astype(f32); R = R.astype(f32)
        fib = tile_to(self.fib if self.fib is not None else fibre_tile(), h, w)
        fine = fbm(h, w, (2.1, 1.2), (1, .6), self.seed + 41)
        tooth = fbm(h, w, (5.5, 2.8), (1, .7), self.seed + 43)
        tooth = np.clip(.5 + .24 * tooth, 0, 1)
        blot = fbm(h, w, (34, 11), (1, .6), self.seed + 47)
        br = _bristles(self.seed % 7)
        self.D, self.F = [], []
        for k in range(K):
            ok = I[k] >= 0
            if not ok.any(): continue
            i = np.where(ok, I[k], 0); e = np.where(ok, E[k], -1e3)
            s = S[i]; r = np.maximum(R[i], .3); sl = SL[i]; v = sp[i]
            ld_ = ld[i]; u = np.clip(U[k], -1.3, 1.3)
            wetness = np.clip(ld_ * 1.15 - .22 * (v - .6), 0, 1.15) * wt[i]
            # --- bristle contact (kasure): streaks in stroke coordinates, broken by paper tooth
            mx = (s * 1.35 + sd[i] * 173.) % 4095.; my = np.clip((u * .46 + .5) * 255, 0, 255)
            b = cv2.remap(br, mx.astype(f32), my.astype(f32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
            thin = smooth(1.4, 6.0, r)
            dryness = dr[i] * np.clip(.80 * (1 - ld_) ** 1.15 + .30 * np.clip(v - 1.15, 0, 1.6) - .10, 0, 1.15)
            dryness = dryness * (.55 + .45 * np.abs(u) ** 2.0) + dr[i] * .10 * np.clip(v - 1, 0, 2) * np.abs(u) ** 3
            dryness = dryness + spl_[i] * np.exp(-((np.abs(u - .12) - .02) / .10) ** 2) * (1 - ld_)
            c = (.82 * b + .18 * tooth) * thin + (1 - thin) * (.5 * b + .5 * tooth)
            contact = smooth(dryness * 1.02 - .13, dryness * 1.02 + .13, c + .02)
            contact = np.where(dryness < .03, 1.0, contact)
            # --- edge: slight rag, capillary feathering where wet
            rag = .17 * fine + .42 * (b - .5) * np.clip(dryness * 5 + .25, 0, 1.6)
            soft_ = .62 + .5 * np.clip(wetness, 0, 1) ** 2 * thin
            core = smooth(-soft_, soft_, e + rag * np.minimum(1, r * .35) - .05)
            bl = np.clip(wetness, 0, 1.2) ** 1.6 * np.clip(r / 9., .16, 1.0) * wt[i]
            some = smooth(-.2, 1.9, blot)
            reach = (.8 + (1.6 + 6.5 * some) * fib ** 1.4) * bl
            fe = smooth(-reach - .3, -reach * .1 + .5, e)
            feather = fe * (.10 + .55 * fib) * np.clip(bl * 1.35, 0, .8)
            halo = np.exp(np.minimum(e, 0) / (1.1 + 1.8 * bl)) * (.07 + .12 * some) * bl * (e > -m + .5)
            # --- density: wet black core, pooled slow ends, faint tide line, thinner where fast
            pool = np.clip(1.05 - .55 * v, 0, 1) * np.clip(ld_ * 1.2, 0, 1)
            inner = .86 + .10 * pool - .055 * np.clip(v - 1, 0, 2) - .10 * (1 - ld_) + .018 * blot + .035 * (b - .5) + .03 * (tooth - .5)
            tide = .05 * np.exp(-((e - 1.8) / 1.3) ** 2) * np.clip(wetness, 0, 1)
            endd = .05 * np.exp(-(sl - s) / (r * .8 + 3)) + .04 * np.exp(-s / (r * .8 + 3))
            starve = np.clip(dryness * 1.5 - .12, 0, 1)
            d = core * contact * np.clip(inner + tide + endd, 0, .985) * (1 - .34 * starve * (1 - smooth(.25, .95, c)))
            d = np.maximum(d, np.maximum(feather, halo) * (1 - .35 * (1 - contact)))
            d = np.where(ok, np.clip(d, 0, .985), 0).astype(f32)
            a = np.where(A[k] >= 0, A[k], np.maximum(AM[k], 0))
            t = fr[a] + np.where(e < 0, np.minimum(-e, m) * .75 + 1.0, 0) + np.where(core * contact < .4, .5, 0)
            t = np.where(ok, t, 1e4).astype(f32)
            self.D.append(d); self.F.append(t)
        self.pathinfo = (X, R, fr)
        return self

    def maps(self):
        return list(zip(self.D, self.F))

    def tip_at(self, f):
        X, R, fr = self.pathinfo
        i = int(np.clip(np.searchsorted(fr, f), 0, len(fr) - 1)); return X[i], R[i]


# ------------------------------------------------------------- show the ink
def ink_at(maps, f, dry_frames=26., edge=.13):
    """coverage 0..1 and wetness 0..1 at film frame f from [(D, F), ...] (any space)"""
    cov = None
    for D, F in maps:
        age = f - F
        g = np.clip(age / edge + .5, 0, 1)
        d = D * g
        w = d * np.exp(-np.clip(age, 0, 400) / dry_frames) * (g > 0)
        if cov is None: cov, wet = d, w
        else:
            cov = 1 - (1 - cov) * (1 - d); wet = np.maximum(wet, w)
    return np.minimum(cov, .99), wet


class SparseInk:
    """ink maps warped to the screen at ss x, stored sparsely: [(index, D, F), ...] over an ROI"""

    def __init__(self, maps, w, h, ox, oy, ss=2):
        self.w, self.h, self.ox, self.oy, self.ss = w, h, ox, oy, ss
        self.slots = []
        for D, F in maps:
            idx = np.flatnonzero(D > .004)
            if len(idx): self.slots.append((idx.astype(np.int32), D.ravel()[idx].astype(f32), F.ravel()[idx].astype(f32)))

    def at(self, f, dry_frames=26., edge=.13):
        n = self.w * self.ss * self.h * self.ss
        cov = np.zeros(n, f32); wet = np.zeros(n, f32)
        for idx, D, F in self.slots:
            on = F < f + edge
            if not on.any(): continue
            idx, D, age = idx[on], D[on], f - F[on]
            g = np.clip(age / edge + .5, 0, 1); d = D * g
            cov[idx] = 1 - (1 - cov[idx]) * (1 - d)
            wet[idx] = np.maximum(wet[idx], d * np.exp(-np.clip(age, 0, 400) / dry_frames))
        sh = (self.h * self.ss, self.w * self.ss)
        rs = lambda a: cv2.resize(a.reshape(sh), (self.w, self.h), interpolation=cv2.INTER_AREA) if self.ss > 1 else a.reshape(sh)
        return np.minimum(rs(cov), .99), rs(wet)


def transmit(cov, wet=None, hue=(1.05, 1.055, .88), k=3.15):
    """ink coverage -> RGB multiplier on paper.  wet ink is a touch deeper"""
    d = cov ** 1.22 * k
    if wet is not None: d = d * (1 + .10 * wet)
    return np.exp(-d[..., None] * np.asarray(hue, f32))


_brk = {}


def sheen(cov, wet, light=(-.6, -.8), width=1.4):
    """broken wet catchlight along the edges that face the light; only where the ink is fresh"""
    fresh = smooth(.50, .95, wet)
    if fresh.max() < .02: return np.zeros_like(cov)
    b = cv2.GaussianBlur(cov, (0, 0), width)
    gx = cv2.Sobel(b, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(b, cv2.CV_32F, 0, 1, ksize=3)
    sh = np.clip(-(gx * light[0] + gy * light[1]), 0, None)
    sh = cv2.GaussianBlur(sh, (0, 0), .7)
    if cov.shape not in _brk: _brk[cov.shape] = smooth(-.3, 1.1, fbm(cov.shape[0], cov.shape[1], (26, 9), (1, .5), 77))
    B = cv2.GaussianBlur(cov, (0, 0), width * 2.6)
    GX = cv2.Sobel(B, cv2.CV_32F, 1, 0, ksize=3); GY = cv2.Sobel(B, cv2.CV_32F, 0, 1, ksize=3)
    S2 = np.clip(-(GX * light[0] + GY * light[1]), 0, None)
    return (np.clip(sh * 2.4, 0, 1) * smooth(.55, .85, b) + np.clip(S2 * 2.2, 0, 1) ** 1.5 * .45 * smooth(.8, .97, b)) * fresh * _brk[cov.shape]
