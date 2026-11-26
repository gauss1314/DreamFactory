"""Storm weather for s4, s6, s8: painted storm sky, slanted rain in depth layers, forked lightning, mist, and the
lighthouse beam made visible by the rain and fog.  Owned by the sea lane.

Everything takes the same wind: WIND_SCREEN is the rain's lean on screen (dx per dy, + = to the right),
and the sea uses the matching world wind.

  sky_plate(h, w, hz, seed, ...)          -> rgb plate, cloud coverage                    (setup, cache it)
  Rain(h, w, seed, lean, layers)          .draw(f, light) -> (rgb add, alpha)             (per frame)
  bolt(x0, y0, x1, y1, seed)              -> list of polylines (trunk + branches, width)
  draw_bolt(img, segs, amt)               -> img
  beam_volume(cam, lamp, dirs, depth, t)  -> HxW volumetric beam intensity (quarter res inside)
  flare(img, x, y, amt)                   -> img  (beam sweeping across the lens)
"""
import math, os
import numpy as np, cv2
from numba import njit, prange
from lp import W, H, cache_path, comp, clouds
from lp.paint import f32, rgb, mix, smooth, fbm, _vn, Canvas, arcs, repaint, mottle, ramp, grid

STORM = dict(sky=('#2a2e3e', '#454a5c', '#6b6f7e'), cloud=('#8c90a0', '#5a5e70', '#33374a'), sea=('#1c2a33', '#2f4452'),
             foam='#d8e2e6', rain='#a8b6c4', bolt='#e8f0ff', beam='#fff2d0', lamp='#ffc070')
LEAN = .30           # rain: screen dx per dy (wind blows left -> right)


def cached(name, fn):
    p = cache_path(name)
    if os.path.exists(p):
        return np.load(p).astype(f32)
    a = fn()
    tmp = p + f'.{os.getpid()}.npy'
    np.save(tmp, np.asarray(a).astype(np.float16)); os.replace(tmp, p)
    return np.asarray(a, f32)


# =========================================================================== sky
def sky_plate(h, w, hz, seed=1, light=(-.55, .62, .55), banks=None, break_x=None, moon=None, low=None, scud=True):
    """storm sky: gradient, then hanging cloud masses (banks painted upside down so their lobes droop), a
    low roll of shelf cloud on the horizon, gouache pass.  returns rgb (h,w,3), coverage (h,w)."""
    y = np.arange(h, dtype=f32)[:, None] / max(hz, 1)
    a, b, c = STORM['sky']
    base = ramp(np.clip(y, 0, 1.2), [(0, a), (.55, '#383c4e'), (.85, b), (1.0, c), (1.2, c)])
    base = np.broadcast_to(base, (h, w, 3)).copy()
    x = np.arange(w, dtype=f32)[None]
    if break_x is not None:          # a thin paler seam in the overcast, where the moon will come
        g = np.exp(-((x - break_x) / (w * .22)) ** 2) * np.exp(-((y * hz - hz * .35) / (hz * .35)) ** 2)
        base += g[..., None] * (rgb('#7d8494') - base) * .35
    ang = fbm(h, w, (260, 90), (1, .4), seed + 3) * .08 - .05
    base = repaint(base, (52, 24), seed=seed + 4, angle=ang, thr=(0, .004), density=.9, aspect=6.0, jit=(.002, .006, .01), op=.6, dry=.2, curve=.15, bristle=.02)
    # cloud masses: a layered Sky painted with light from below, flipped so the lobes hang down
    S = clouds.Sky(h, w, base[::-1].copy(), light=(light[0], -light[1], light[2]), seed=seed, layered=True)
    T1 = clouds.tones('#7e8294', '#5e6274', '#43475b', '#30344a')
    T2 = clouds.tones('#6c7083', '#4e5266', '#3a3e52', '#2a2e40')
    T3 = clouds.tones('#8c90a0', '#6e7284', '#53576a', '#3c4054')
    r = np.random.default_rng(seed)
    if banks is None:
        banks = []
        # far deck just above the horizon: long, low, soft
        xx = -100.
        while xx < w + 100:
            wd = r.uniform(380, 700)
            banks.append((xx + wd / 2, h - hz * r.uniform(.40, .52), wd, r.uniform(70, 120), 'T3', r.integers(1e6), .5))
            xx += wd * r.uniform(.6, .85)
        xx = -200.
        while xx < w + 200:
            wd = r.uniform(700, 1100)
            banks.append((xx + wd / 2, h - hz * r.uniform(.05, .22), wd, r.uniform(200, 320), 'T1', r.integers(1e6), .6))
            xx += wd * r.uniform(.55, .75)
        xx = -300.
        while xx < w + 300:
            wd = r.uniform(1000, 1500)
            banks.append((xx + wd / 2, h + 60 + hz * r.uniform(-.04, .06), wd, r.uniform(300, 420), 'T2', r.integers(1e6), .7))
            xx += wd * r.uniform(.55, .7)
    TT = dict(T1=T1, T2=T2, T3=T3)
    for (bx, bb, bw, bh, tk, sd, dt) in banks:
        S.bank(bx, bb, bw, bh, TT[tk], '#41455a', seed=int(sd), n=4, levels=2, tiers=2, detail=dt * .6, soft=1.4, pool=.0, lit=.14, half=.30,
               lost=1.0, foot=.75, contrast=.8)
    out = S.paint(seed + 9, sizes=(22, 11, 5))
    L = S.layer(out)[::-1]
    cov = S.A[::-1].copy()
    img = base * (1 - L[..., 3:4]) + L[..., :3]
    # shelf of rain-cloud on the horizon: dark, soft, lost into the rain
    if low is not False:
        yy = np.arange(h, dtype=f32)[:, None]
        n = fbm(h, w, (180, 60), (1, .5), seed + 21, aspect=3.5)
        band = smooth(hz - 120, hz - 20, yy + n * 26) * smooth(hz + 6, hz - 6, yy)
        img += (rgb('#3c4052') - img) * (band * .55)[..., None]
    img = mottle(img, .010, seed + 5, .002)
    return img.astype(f32), cov.astype(f32)


# =========================================================================== rain
class Rain:
    """slanted rain in depth: far curtains (scrolling sheets), mid hair-lines, near long soft streaks.
    Each streak is a straight hand-ruled line with tapered ends; positions are a pure function of f."""

    def __init__(self, h=H, w=W, seed=3, lean=LEAN, dens=1.0, speed=1.0):
        self.h, self.w, self.lean, self.seed = h, w, lean, seed
        r = np.random.default_rng(seed)
        self.layers = []
        # (count, length px, width px, speed px/frame, opacity, blur)
        for k, (n, L, wd, sp, op, bl) in enumerate(((2600, 26, 1, 46, .22, 0), (1400, 60, 1, 80, .30, 0), (420, 150, 2, 150, .30, 1.2), (70, 380, 3, 260, .22, 2.4))):
            n = int(n * dens)
            self.layers.append(dict(x=r.uniform(-.3, 1.3, n) * w, y=r.uniform(0, 1, n) * (h + L * 2), L=L * r.uniform(.6, 1.3, n), wd=wd,
                                    sp=sp * speed * r.uniform(.85, 1.15, n), op=op * r.uniform(.4, 1, n), bl=bl))
        # far curtains: noise stretched along the fall, rotated by the lean
        g = fbm(h * 2, w * 2, (260, 70, 18), (1, .6, .35), seed + 1, aspect=.10)
        u = (np.arange(h, dtype=f32) / h)[:, None]
        g = g[h:] * (1 - u) + g[:h] * u                      # periodic in y: T(0) = T(h) = g[h]
        v = (np.arange(w, dtype=f32) / w)[None]
        g = g[:, w:] * (1 - v) + g[:, :w] * v                # and in x
        g = g / (g.std() + 1e-6)
        g = np.clip(g * .5 + .5, 0, 1)
        self.sheet = g.astype(f32)

    def curtains(self, f):
        """0..1 sheet density, scrolling down along the lean"""
        h, w = self.h, self.w
        dy = (f * 34.) % (h)
        M = np.float32([[1, -self.lean, 0], [0, 1, -dy]])
        out = cv2.warpAffine(self.sheet, M, (w, h), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP, borderMode=cv2.BORDER_WRAP)
        return out

    def streaks(self, f, which=(0, 1, 2, 3), lit=None, scale=1.0):
        """single-channel streak alpha at full res"""
        h, w = self.h, self.w
        acc = np.zeros((h, w), f32)
        for k in which:
            Lr = self.layers[k]
            buf = np.zeros((h, w), np.uint8)
            y = (Lr['y'] + Lr['sp'] * f) % (h + Lr['L'] * 2) - Lr['L']
            x = Lr['x'] + y * self.lean + Lr['sp'] * f * self.lean * 0
            x = (x % (w * 1.6)) - w * .3
            dx = Lr['L'] * self.lean / math.hypot(1, self.lean); dy = Lr['L'] / math.hypot(1, self.lean)
            op = (Lr['op'] * 255 * scale).astype(np.int32)
            for i in range(len(x)):
                cv2.line(buf, (int(x[i] * 4), int(y[i] * 4)), (int((x[i] + dx[i]) * 4), int((y[i] + dy[i]) * 4)), int(op[i]), Lr['wd'], cv2.LINE_AA, 2)
            a = buf.astype(f32) / 255.
            if Lr['bl'] > 0:
                a = cv2.GaussianBlur(a, (0, 0), Lr['bl'])
            acc = 1 - (1 - acc) * (1 - a)
        return acc


# ====================================================================== lightning
def bolt(x0, y0, x1, y1, seed=0, depth=6, rough=.22, branch=.55):
    """forked lightning by midpoint displacement: [(polyline Nx2, width), ...] trunk first"""
    r = np.random.default_rng(seed)

    def mid(P, rough, lev):
        if lev == 0: return P
        out = [P[0]]
        for a, b in zip(P[:-1], P[1:]):
            L = np.hypot(*(b - a)); nrm = np.array([-(b - a)[1], (b - a)[0]]) / (L + 1e-6)
            m = (a + b) / 2 + nrm * r.normal(0, rough * L)
            out += [m, b]
        return mid(np.array(out), rough * .92, lev - 1)

    trunk = mid(np.array([[x0, y0], [x1, y1]], float), rough, depth)
    segs = [(trunk, 3.4)]

    def grow(P, wd, lev):
        n = len(P)
        for _ in range(int(2 + 2 * lev)):
            if r.random() > branch: continue
            i = r.integers(int(n * .1), int(n * .8))
            a = P[i]; d = P[min(n - 1, i + 3)] - P[i]
            ang = math.atan2(d[1], d[0]) + r.choice([-1, 1]) * r.uniform(.35, .9)
            L = np.hypot(*(P[-1] - P[0])) * r.uniform(.18, .42)
            b = a + L * np.array([math.cos(ang), math.sin(ang)])
            Q = mid(np.array([a, b]), rough * 1.1, max(3, depth - 2))
            segs.append((Q, wd * .5))
            if lev > 0: grow(Q, wd * .5, lev - 1)
    grow(trunk, 3.4, 1)
    return segs


def draw_bolt(img, segs, amt=1.0, col=STORM['bolt'], glow=1.0):
    h, w = img.shape[:2]
    m = np.zeros((h, w), np.uint8)
    for P, wd in segs:
        pts = (np.asarray(P) * 4).astype(np.int32)
        cv2.polylines(m, [pts], False, 255, max(1, int(round(wd))), cv2.LINE_AA, 2)
    a = m.astype(f32) / 255.
    core = cv2.GaussianBlur(a, (0, 0), .6)
    g = comp.blur(a, 10) * 1.6 + comp.blur(a, 40) * 1.2
    c = rgb(col)
    img = img + (c * 1.2 - img) * np.clip(core * amt, 0, 1)[..., None]
    img = comp.screen(img, (g * amt * .35 * glow)[..., None] * c)
    return img


# ===================================================================== the beam
@njit(cache=True, fastmath=True, parallel=True)
def _beam(ex, ey, ez, R, foc, cx, cy, h, w, LX, LY, LZ, D, half, r0, reach, depth, tmax, t, seed, lean, out):
    nb = D.shape[0]
    for j in prange(h):
        for i in range(w):
            ux = (i + .5 - cx) / foc; uy = (j + .5 - cy) / foc
            dx = ux * R[0, 0] + uy * R[1, 0] + R[2, 0]
            dy = ux * R[0, 1] + uy * R[1, 1] + R[2, 1]
            dz = ux * R[0, 2] + uy * R[1, 2] + R[2, 2]
            dl = math.sqrt(dx * dx + dy * dy + dz * dz)
            tm = depth[j, i]
            if tm <= 0: tm = tmax
            acc = 0.0
            for b in range(nb):
                ax = D[b, 0]; ay = D[b, 1]; az = D[b, 2]
                # closest approach of the view ray (param t = z_cam) to the beam axis
                wx = ex - LX; wy = ey - LY; wz = ez - LZ
                aa = dx * dx + dy * dy + dz * dz
                bb = dx * ax + dy * ay + dz * az
                cc = 1.0
                dd = dx * wx + dy * wy + dz * wz
                ee = ax * wx + ay * wy + az * wz
                den = aa * cc - bb * bb
                if den < 1e-9: den = 1e-9
                tc = (bb * ee - cc * dd) / den
                sc = (aa * ee - bb * dd) / den
                if sc < 0: sc = 0.0
                Rc = r0 + sc * half
                sinang = math.sqrt(max(1e-6, den / aa))
                win = Rc * 3.0 / (sinang * dl) + 2.0
                ta = max(.3, tc - win); tb = min(tm, tc + win)
                if tb <= ta: continue
                n = 22
                dt = (tb - ta) / n
                for k in range(n):
                    tt = ta + (k + .5) * dt
                    px = ex + dx * tt; py = ey + dy * tt; pz = ez + dz * tt
                    vx = px - LX; vy = py - LY; vz = pz - LZ
                    al = vx * ax + vy * ay + vz * az
                    if al <= 0: continue
                    rx = vx - al * ax; ry = vy - al * ay; rz = vz - al * az
                    rr = math.sqrt(rx * rx + ry * ry + rz * rz)
                    Rb = r0 + al * half
                    q = rr / Rb
                    if q > 1.6: continue
                    prof = math.exp(-q * q * 2.2)
                    # rain and drifting mist inside the beam: streaks along the fall, slanted by the wind
                    s1 = _vn((px - pz * lean) * .12 + t * .6, py * .12, seed)
                    s2 = _vn(px * .03 + t * .2, (py + pz * .3) * .03, seed + 2)
                    dens = .45 + .55 * s1 * (.4 + s2)
                    acc += prof * dens * dt * dl / (1.0 + al / reach) / (Rb * .9 + 1.0)
            out[j, i] = acc


def beam_volume(cam, lamp, dirs, depth=None, t=0., half=.055, r0=1.2, reach=500., tmax=3000., q=4, seed=5, lean=LEAN, amt=1.0):
    """visible beam: line integral through two cones.  depth: HxW z_cam of the nearest surface (0 = open sky)."""
    h, w = cam.h // q, cam.w // q
    foc = cam.f / q
    dep = np.zeros((h, w), np.float32) if depth is None else cv2.resize(depth, (w, h), interpolation=cv2.INTER_NEAREST).astype(np.float32)
    out = np.zeros((h, w), np.float32)
    D = np.asarray(dirs, np.float64).reshape(-1, 3)
    D = D / np.linalg.norm(D, axis=1, keepdims=True)
    _beam(*map(float, cam.eye), cam.R.astype(np.float64), float(foc), cam.cx / q, cam.cy / q, h, w, float(lamp[0]), float(lamp[1]), float(lamp[2]), D,
          half, r0, reach, dep, tmax, float(t), seed, lean, out)
    out = 1 - np.exp(-np.maximum(out, 0) * 1.2)          # a long chord through the cone saturates softly, never clips
    out = cv2.resize(out, (cam.w, cam.h), interpolation=cv2.INTER_CUBIC)
    return np.maximum(out, 0) * amt


def flare(img, x, y, amt, col=STORM['beam'], r=900):
    """the beam crossing the lens: the lamp swells into a disc of light and the whole frame washes warm"""
    if amt <= 1e-3: return img
    h, w = img.shape[:2]
    core = comp.radial(x, y, 60 + 120 * amt, power=1.6, h=h, w=w)
    halo = comp.radial(x, y, r * (.6 + .6 * amt), power=2.2, h=h, w=w)
    c = rgb(col)
    img = comp.screen(img, (core * 1.2 + halo * .7)[..., None] * c * amt)
    img = img + (c * 1.0 - img) * (amt ** 1.3 * .55)
    return img


def beam_dirs(az, tilt=-.012):
    """two opposite beams at azimuth az (radians, world, 0 = +X, counter-clockwise)"""
    out = []
    for a in (az, az + math.pi):
        out.append((math.cos(a) * math.cos(tilt), math.sin(a) * math.cos(tilt), math.sin(tilt)))
    return out


# ========================================================================= mist
def mist_band(h, w, y, thick, seed, amt=.5, aspect=5.0):
    """a soft horizontal pool of mist: alpha map"""
    yy = np.arange(h, dtype=f32)[:, None]
    n = fbm(h, w, (thick * 2 + 20, thick * .8 + 8), (1, .5), seed, aspect=aspect)
    g = np.exp(-(((yy - y) / thick) + n * .35) ** 2)
    return np.clip(g * amt * (1 + .25 * n), 0, 1).astype(f32)



def dolly_warp(layer, depth, d, cx=W / 2, cy=H / 2, interp=cv2.INTER_LINEAR):
    """a layer painted from the reference camera, seen after the camera dollied `d` metres along its axis:
    every point at camera depth `depth` moves away from the principal point by depth / (depth - d)."""
    k = depth / max(depth - d, 1e-3)
    if abs(k - 1) < 1e-5: return layer
    M = np.float32([[k, 0, cx - k * cx], [0, k, cy - k * cy]])
    return cv2.warpAffine(layer, M, (layer.shape[1], layer.shape[0]), flags=interp, borderMode=cv2.BORDER_CONSTANT)


def over(base, layer, op=1.0):
    a = layer[..., 3:4] * op
    return base * (1 - a) + layer[..., :3] * op


class Sprite:
    """a painted layer kept only inside its bounding box; placed per frame after a dolly of d metres"""

    def __init__(self, rgba, depth, extra=None, pad=6):
        a = rgba[..., 3]
        ys, xs = np.nonzero(a > .003)
        if len(xs) == 0:
            self.empty = True; return
        self.empty = False
        y0, y1, x0, x1 = max(0, ys.min() - pad), min(rgba.shape[0], ys.max() + pad + 1), max(0, xs.min() - pad), min(rgba.shape[1], xs.max() + pad + 1)
        self.x0, self.y0 = x0, y0
        self.L = np.ascontiguousarray(rgba[y0:y1, x0:x1])
        self.E = None if extra is None else np.ascontiguousarray(extra[y0:y1, x0:x1])
        self.depth = depth

    def roi(self, d, cx=W / 2, cy=H / 2, h=H, w=W):
        """-> (X0, Y0, layer, extra) warped and clipped to the frame"""
        k = self.depth / max(self.depth - d, 1e-3)
        hh, ww = self.L.shape[:2]
        ox = cx + k * (self.x0 - cx); oy = cy + k * (self.y0 - cy)
        X0, Y0 = int(math.floor(ox)), int(math.floor(oy))
        X1, Y1 = int(math.ceil(ox + ww * k)) + 1, int(math.ceil(oy + hh * k)) + 1
        X0c, Y0c, X1c, Y1c = max(0, X0), max(0, Y0), min(w, X1), min(h, Y1)
        if X1c <= X0c or Y1c <= Y0c: return None
        M = np.float32([[k, 0, ox - X0c], [0, k, oy - Y0c]])
        L = cv2.warpAffine(self.L, M, (X1c - X0c, Y1c - Y0c), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        E = None if self.E is None else cv2.warpAffine(self.E, M, (X1c - X0c, Y1c - Y0c), flags=cv2.INTER_NEAREST, borderMode=cv2.BORDER_CONSTANT)
        return X0c, Y0c, L, E
