"""The lamp room set, shared by s2, s3, s5 and s7 (interior lane).

World metres, +X right, +Y forward (away from the s2 camera), +Z up, lamp on the origin.
A round room: wooden floor, whitewashed parapet wall, a ring of windows above it, a wooden
ceiling.  In the middle a brass lamp: plinth, column, oil tank (the filler cap is where the
otter pours), a tray, and a drum of Fresnel glass rings around the flame.
"""
import math, os
import numpy as np, cv2
from lp import W, H, cache_path
from lp.paint import rgb, mix, smooth, ramp, fbm, warp_by, repaint, Canvas, arcs, jit_color, mottle, f32, lum, grid
from lp.cam import Camera3D

R_WALL = 2.4          # inner radius of the wall
Z_SILL = .55          # top of the plaster parapet
Z_GLASS0 = .60        # bottom of the glass
Z_TRANSOM = 1.42
Z_GLASS1 = 2.22       # top of the glass
Z_RING = 2.42         # ring beam, then the ceiling cone
Z_APEX = 3.10
N_BAYS = 12
BAY0 = math.radians(9.0)   # azimuth offset of the first mullion
MULL_W = .05               # half width of a mullion, metres
SILL_D = .16               # depth of the window ledge

# lamp (all rotationally symmetric about z)
PLINTH = (.33, 0., .10)         # radius, z0, z1
COLUMN = (.11, .10, .24)
TANK = (.19, .22, .42)          # the oil tank
TRAY = (.28, .42, .465)
LENS = (.25, .465, .94)        # glass drum
CROWN = (.27, .94, 1.0)
CAP = (.09, 1.0, 1.12)
FLAME = np.array([0., 0., .68])
FILLER = np.array([-.12, -.14, .42])      # the filler cap on top of the tank, front left
HATCH = dict(cx=-1.02, cy=-.22, hw=.27, hh=.27)  # floor opening (x, y centre and half sizes)

def _ledge(az_deg, r=.055, h=.17):
    a = math.radians(az_deg); rr = R_WALL - SILL_D * .5
    return ('cyl', (rr * math.cos(a), rr * math.sin(a), r, Z_SILL, Z_SILL + h), 0)


PROPS = [
    ('cyl', (1.55, .95, .21, 0., .64), 17),            # oil drum, red with bands
    ('cyl', (1.02, 1.42, .13, 0., .25), 18),           # bucket
    ('box', (1.42, 1.90, -.62, -.12, 0., .38), 19),     # crate
    ('box', (1.50, 1.84, -.52, -.22, .38, .58), 19),    # a smaller box on it
    ('box', (.72, 1.08, 1.55, 1.85, 0., .36), 21),      # stool (a block, painted as one)
] + [(k, a, 20) for k, a, _ in (_ledge(62), _ledge(66, .045, .13), _ledge(118, .05, .2), _ledge(208), _ledge(213, .04, .12))]
# the hatch lid, opened back against its hinge on the far edge
PROPS.append(('box', (-1.02 - .27, -1.02 + .27, -.22 + .27 + .01, -.22 + .27 + .55, 0., .03), 15))      # lid lying open on the boards


# per-camera layout; s7 shares s5's camera
CAMS = {
    's2': dict(eye=(-.85, -1.85, .56), target=(-.30, .60, .50), f=1100, cx=W * .5, cy=H * .50),
    's5': dict(eye=(-1.75, -1.15, .40), target=(-.60, .55, .58), f=980, cx=W * .5, cy=H * .52),
    's3': dict(eye=(-.55, -.75, .36), target=(-1.9, .55, .70), f=1500, cx=W * .5, cy=H * .5),
}
# the window that blows open (bay index) -- seen in s5/s7 on the left, in s2 left of the lamp
OPEN_BAY = 3


def camera(key):
    c = CAMS['s5' if key == 's7' else key]
    return Camera3D(c['eye'], c['target'], c['f'], W, H, cx=c['cx'], cy=c['cy'])


def bay_az(i):
    return BAY0 + 2 * math.pi * i / N_BAYS


# ------------------------------------------------------------------ ray casting
def _cyl(eye, d, r, z0, z1, inside=False):
    """ray t to a vertical cylinder about z (outside surface, or inside when the camera is in it)"""
    a = d[..., 0] ** 2 + d[..., 1] ** 2
    b = 2 * (eye[0] * d[..., 0] + eye[1] * d[..., 1])
    c = eye[0] ** 2 + eye[1] ** 2 - r * r
    disc = b * b - 4 * a * c
    ok = disc > 0
    sq = np.sqrt(np.maximum(disc, 0))
    t = ((-b + sq) if inside else (-b - sq)) / (2 * a + 1e-9)
    z = eye[2] + t * d[..., 2]
    ok &= (t > .05) & (z >= z0) & (z <= z1)
    return np.where(ok, t, np.inf).astype(f32)


def _disc(eye, d, r, z, r0=0.):
    """ray t to a horizontal disc / annulus at height z (seen from above or below)"""
    with np.errstate(divide='ignore', invalid='ignore'):
        t = (z - eye[2]) / d[..., 2]
    x = eye[0] + t * d[..., 0]; y = eye[1] + t * d[..., 1]
    rr = np.hypot(x, y)
    ok = np.isfinite(t) & (t > .05) & (rr <= r) & (rr >= r0)
    return np.where(ok, t, np.inf).astype(f32)


# material ids
M_FLOOR, M_PLASTER, M_SILL, M_MULL, M_GLASS, M_RING, M_CEIL, M_PLINTH, M_COLUMN, M_TANK, M_TRAY, M_LENS, M_CROWN, M_HATCH, M_LID, M_RAIL, M_DRUM, M_BUCKET, M_CRATE, M_CAN, M_STOOL = range(1, 22)


def geometry(cam):
    """per-pixel material, world position, normal, depth"""
    d = cam.rays()
    eye = cam.eye.astype(f32)
    T = np.full(d.shape[:2], np.inf, f32); mat = np.zeros(d.shape[:2], np.int16)
    N = np.zeros(d.shape, f32)

    def take(t, m, n=None):
        nonlocal T
        k = t < T
        T = np.where(k, t, T); mat[k] = m
        if n is not None:
            N[k] = n[k] if np.ndim(n) == 3 else n

    def radial_n(t, sign=1.):
        p = eye + d * t[..., None]
        r = np.hypot(p[..., 0], p[..., 1]) + 1e-6
        return np.stack([p[..., 0] / r * sign, p[..., 1] / r * sign, np.zeros_like(r)], -1).astype(f32)

    # room shell
    tf = _disc(eye, d, R_WALL, 0.)
    # hatch: a hole in the floor
    p = eye + d * np.where(np.isfinite(tf), tf, 0)[..., None]
    hole = (np.abs(p[..., 0] - HATCH['cx']) < HATCH['hw']) & (np.abs(p[..., 1] - HATCH['cy']) < HATCH['hh'])
    take(np.where(hole, np.inf, tf), M_FLOOR, np.array([0, 0, 1.], f32))
    # inside of the hatch well: a box down to z=-.9
    hx0, hx1 = HATCH['cx'] - HATCH['hw'], HATCH['cx'] + HATCH['hw']
    hy0, hy1 = HATCH['cy'] - HATCH['hh'], HATCH['cy'] + HATCH['hh']
    for ax, v, nn in ((0, hx0, (1, 0, 0)), (0, hx1, (-1, 0, 0)), (1, hy0, (0, 1, 0)), (1, hy1, (0, -1, 0))):
        with np.errstate(divide='ignore', invalid='ignore'):
            t = (v - eye[ax]) / d[..., ax]
        q = eye + d * np.where(np.isfinite(t), t, 0)[..., None]
        o = 1 - ax
        lo, hi = (hy0, hy1) if ax == 0 else (hx0, hx1)
        ok = np.isfinite(t) & (t > .05) & (q[..., 2] < 0) & (q[..., 2] > -.9) & (q[..., o] >= lo) & (q[..., o] <= hi)
        take(np.where(ok, t, np.inf), M_HATCH, np.array(nn, f32))
    tw = _cyl(eye, d, R_WALL, 0, Z_RING, inside=True)
    pw = eye + d * np.where(np.isfinite(tw), tw, 0)[..., None]
    zw = pw[..., 2]
    nin = radial_n(np.where(np.isfinite(tw), tw, 0), -1.)
    m_w = np.where(zw < Z_SILL, M_PLASTER, np.where(zw < Z_GLASS0, M_SILL, np.where(zw < Z_GLASS1, M_GLASS, M_RING)))
    az = np.arctan2(pw[..., 1], pw[..., 0])
    ph = ((az - BAY0) / (2 * math.pi / N_BAYS)) % 1.0
    dm = np.minimum(ph, 1 - ph) * (2 * math.pi * R_WALL / N_BAYS)
    dm2 = np.abs(ph - .5) * (2 * math.pi * R_WALL / N_BAYS)
    mull = (dm < MULL_W) | (dm2 < MULL_W * .55) | (np.abs(zw - Z_TRANSOM) < .03)
    m_w = np.where((m_w == M_GLASS) & mull, M_MULL, m_w)
    k = tw < T
    T = np.where(k, tw, T); mat[k] = m_w[k]; N[k] = nin[k]
    # sill ledge top (a shelf 7 cm deep)
    ts = _disc(eye, d, R_WALL, Z_SILL, R_WALL - SILL_D)
    take(ts, M_SILL, np.array([0, 0, 1.], f32))
    t = _cyl(eye, d, R_WALL - SILL_D, Z_SILL - .05, Z_SILL, inside=True)
    take(t, M_SILL, radial_n(np.where(np.isfinite(t), t, 0), -1.))
    # ceiling cone from the ring beam to the apex (inside surface)
    # cone: z = Z_RING + (R_WALL - r) * k
    kc = (Z_APEX - Z_RING) / R_WALL
    # solve (z - zr) = k (R - r)  ->  r = R - (z - zr)/k ; r^2 = x^2+y^2
    A = d[..., 0] ** 2 + d[..., 1] ** 2 - (d[..., 2] / kc) ** 2
    c0 = R_WALL + (Z_RING - eye[2]) / kc       # r = c0 - t dz/k
    B = 2 * (eye[0] * d[..., 0] + eye[1] * d[..., 1]) + 2 * c0 * d[..., 2] / kc
    C = eye[0] ** 2 + eye[1] ** 2 - c0 ** 2
    disc = B * B - 4 * A * C
    sq = np.sqrt(np.maximum(disc, 0))
    best = np.full(T.shape, np.inf, f32)
    for t in ((-B - sq) / (2 * A), (-B + sq) / (2 * A)):
        z = eye[2] + t * d[..., 2]
        ok = (disc > 0) & (t > .05) & (z > Z_RING) & (z < Z_APEX)
        best = np.where(ok & (t < best), t, best)
    pc = eye + d * np.where(np.isfinite(best), best, 0)[..., None]
    rc = np.hypot(pc[..., 0], pc[..., 1]) + 1e-6
    nc = np.stack([-pc[..., 0] / rc * kc, -pc[..., 1] / rc * kc, -np.ones_like(rc)], -1)
    nc /= np.linalg.norm(nc, axis=-1, keepdims=True)
    take(best, M_CEIL, nc.astype(f32))
    # the lamp
    for (r, z0, z1), m in ((PLINTH, M_PLINTH), (COLUMN, M_COLUMN), (TANK, M_TANK), (TRAY, M_TRAY), (LENS, M_LENS), (CROWN, M_CROWN), (CAP, M_CROWN)):
        t = _cyl(eye, d, r, z0, z1)
        take(t, m, radial_n(np.where(np.isfinite(t), t, 0)))
        if eye[2] > z1:
            take(_disc(eye, d, r, z1), m, np.array([0, 0, 1.], f32))
        elif eye[2] < z0 and z0 > 0:
            take(_disc(eye, d, r, z0), m, np.array([0, 0, -1.], f32))
    # odds and ends: an oil drum, a bucket, a crate, oil cans on the ledge, the hatch lid
    for kind, a, m in PROPS:
        if kind == 'cyl':
            cx, cy, r, z0, z1 = a
            e2 = eye - np.array([cx, cy, 0], f32)
            t = _cyl(e2, d, r, z0, z1)
            p = e2 + d * np.where(np.isfinite(t), t, 0)[..., None]
            rr = np.hypot(p[..., 0], p[..., 1]) + 1e-6
            take(t, m, np.stack([p[..., 0] / rr, p[..., 1] / rr, np.zeros_like(rr)], -1).astype(f32))
            if eye[2] > z1: take(_disc(e2, d, r, z1), m, np.array([0, 0, 1.], f32))
        else:
            take_box = _box(eye, d, *a)
            t, n = take_box
            take(t, m, n)
    T = np.where(np.isfinite(T), T, 50.).astype(f32)
    P = (eye + d * T[..., None]).astype(f32)
    return mat, P, N, T, d


def _box(eye, d, x0, x1, y0, y1, z0, z1):
    """slab test for an axis-aligned box -> (t, normal)"""
    lo = np.array([x0, y0, z0], f32); hi = np.array([x1, y1, z1], f32)
    with np.errstate(divide='ignore', invalid='ignore'):
        inv = 1.0 / d
        ta = (lo - eye) * inv; tb = (hi - eye) * inv
    tmin = np.minimum(ta, tb); tmax = np.maximum(ta, tb)
    tmin = np.nan_to_num(tmin, nan=-np.inf); tmax = np.nan_to_num(tmax, nan=np.inf)
    t0 = tmin.max(-1); t1 = tmax.min(-1)
    ok = (t1 >= t0) & (t0 > .05)
    ax = tmin.argmax(-1)
    n = np.zeros(d.shape, f32)
    sgn = -np.sign(np.take_along_axis(d, ax[..., None], -1)[..., 0])
    for k in range(3): n[..., k] = np.where(ax == k, sgn, 0)
    return np.where(ok, t0, np.inf).astype(f32), n



# ------------------------------------------------------------------ painting the plate
def _h(a, b=0, c=0):
    """hash of integer arrays -> 0..1"""
    n = (np.asarray(a, np.int64) * 374761393 + np.asarray(b, np.int64) * 668265263 + np.asarray(c, np.int64) * 2147483647) & 0xffffffff
    n = ((n ^ (n >> 13)) * 1274126177) & 0xffffffff
    return ((n ^ (n >> 16)) & 0xffff).astype(f32) / 65535.


ALB = {M_FLOOR: '#8c6a54', M_PLASTER: '#ddd5cb', M_SILL: '#86604a', M_MULL: '#55667a', M_GLASS: '#26305e', M_RING: '#6e4e3e',
       M_CEIL: '#76584a', M_PLINTH: '#4c5266', M_COLUMN: '#433d52', M_TANK: '#d29c42', M_TRAY: '#b98638', M_LENS: '#9ab8c8',
       M_CROWN: '#cf9a40', M_HATCH: '#3a2c3a', M_LID: '#7e5c4a', M_RAIL: '#2a2a3a',
       M_DRUM: '#a3444a', M_BUCKET: '#6a7a8c', M_CRATE: '#8a6a4e', M_CAN: '#9aa06a', M_STOOL: '#6e4a3c'}
PLANK = .135


def _elements(mat, P, N):
    """element labels (each plank, each bay of plaster, ...), guide albedo and stroke tangent (world)"""
    h, w = mat.shape
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    az = np.arctan2(y, x); bay = np.floor(((az - BAY0) / (2 * math.pi / N_BAYS)) % N_BAYS).astype(np.int64)
    half = (((az - BAY0) / (2 * math.pi / N_BAYS)) % 1.0 > .5).astype(np.int64)
    lab = np.zeros((h, w), np.int64); jit = np.zeros((h, w), f32); tg = np.zeros((h, w, 3), f32)
    guide = np.zeros((h, w, 3), f32)
    for m, c in ALB.items():
        guide[mat == m] = rgb(c)
    up = np.array([0, 0, 1.], f32)
    azt = np.stack([-np.sin(az), np.cos(az), np.zeros_like(az)], -1).astype(f32)
    # floor: planks run along +Y, butt joints staggered
    k = mat == M_FLOOR
    ix = np.floor(x / PLANK).astype(np.int64)
    off = _h(ix, 7) * 2.0
    iy = np.floor((y + off) / (1.1 + .9 * _h(ix, 3))).astype(np.int64)
    lab[k] = (1000 + ix * 97 + iy)[k]
    v = _h(ix, iy, 1)
    jit[k] = v[k]
    tg[k] = (0, 1, 0)
    # plaster: per bay, vertical brush
    for m, base in ((M_PLASTER, 20000), (M_SILL, 30000), (M_RING, 40000), (M_MULL, 50000)):
        k = mat == m
        lab[k] = (base + bay * 2 + (half if m == M_MULL else 0))[k]
        jit[k] = _h(bay, m)[k]
        tg[k] = up if m in (M_PLASTER,) else azt[k]
    k = (mat == M_MULL) & ((np.abs(z - Z_TRANSOM) < .03))
    tg[k] = azt[k]
    k = (mat == M_MULL) & ~k
    tg[k] = up
    # ceiling: radial boards
    k = mat == M_CEIL
    ib = np.floor((az + math.pi) / (2 * math.pi) * 64).astype(np.int64)
    lab[k] = (60000 + ib)[k]; jit[k] = _h(ib, 11)[k]
    r = np.hypot(x, y) + 1e-6
    tg[k] = np.stack([x / r, y / r, np.full_like(r, (Z_APEX - Z_RING) / R_WALL)], -1)[k] * -1
    for m in (M_PLINTH, M_COLUMN, M_TANK, M_TRAY, M_CROWN, M_HATCH, M_LENS, M_DRUM, M_BUCKET, M_CRATE, M_CAN, M_STOOL, M_LID):
        k = mat == m
        lab[k] = (70000 + m * 100 + (N[..., 2] > .6) + 2 * (N[..., 0] > .6) + 4 * (N[..., 1] < -.6) + 8 * np.floor(az * 2).astype(np.int64) * (m == M_CAN))[k]
        jit[k] = .5
        tg[k] = azt[k] if m != M_HATCH else up
    # every element its own colour: value, a little hue
    j = (jit - .5)[..., None]
    guide = guide * (1 + .12 * j) + .02 * np.concatenate([j, j * .2, -j], -1)
    k = mat == M_FLOOR
    guide[k] *= (1 + .10 * (_h(ix, iy, 5) - .5))[k][:, None] * np.array([1.0, .97, .95], f32)
    return lab.astype(np.int32), np.clip(guide, 0, 1).astype(f32), tg


def _angles(cam, P, tg):
    a, _ = cam.project(P.astype(np.float64))
    b, _ = cam.project((P + tg * .02).astype(np.float64))
    d = b - a
    return np.arctan2(d[..., 1], d[..., 0]).astype(f32)


def _ao(mat, P, N):
    """painted ambient occlusion: wall foot, under the sill, around the lamp foot, hatch well"""
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    r = np.hypot(x, y)
    a = np.ones(mat.shape, f32)
    fl = mat == M_FLOOR
    a -= .30 * fl * np.exp(-(R_WALL - r) / .18)
    a -= .32 * fl * np.exp(-np.maximum(r - PLINTH[0], 0) / .10)
    wall = (mat == M_PLASTER)
    a -= .25 * wall * np.exp(-z / .12) + .38 * wall * np.exp(-(Z_SILL - .05 - z).clip(0) / .07) * (z < Z_SILL)
    a -= .30 * (mat == M_COLUMN) * np.exp(-(TANK[1] - z).clip(0) / .05)
    a -= .25 * (mat == M_RING) + .1 * (mat == M_CEIL) * (1 - np.clip((z - Z_RING) / (Z_APEX - Z_RING), 0, 1))
    for kind, a_, m in PROPS:
        if kind == 'cyl' and a_[3] == 0:
            dd = np.hypot(x - a_[0], y - a_[1]) - a_[2]
            a -= .35 * fl * np.exp(-np.maximum(dd, 0) / .07)
        elif kind == 'box' and a_[4] == 0:
            dd = np.maximum(np.maximum(a_[0] - x, x - a_[1]), np.maximum(a_[2] - y, y - a_[3]))
            a -= .35 * fl * np.exp(-np.maximum(dd, 0) / .07)
    hx = np.abs(x - HATCH['cx']) - HATCH['hw']; hy = np.abs(y - HATCH['cy']) - HATCH['hh']
    a -= .20 * fl * np.exp(-np.maximum(np.maximum(hx, hy), 0) / .05)
    a = np.where(mat == M_HATCH, .35 + .65 * np.clip(1 + z / .35, 0, 1), a)
    return np.clip(a, .2, 1).astype(f32)


def _seams(cv, cam, mat, rng):
    """dark lines that a painter draws between boards: plank edges and butt joints, wall/floor line"""
    P, Wd, C = [], [], []
    def seg(a, b, wd, col, k=5):
        t = np.linspace(0, 1, k)[:, None]
        pts = np.asarray(a, float) + (np.asarray(b, float) - np.asarray(a, float)) * t
        q, z = cam.project(pts)
        if (z < .2).any(): return
        if (q[:, 0].max() < -50) or (q[:, 0].min() > W + 50) or (q[:, 1].max() < -50) or (q[:, 1].min() > H + 50): return
        s = float(cam.scale(pts.mean(0)))
        P.append(q); Wd.append(max(.45, wd * s)); C.append(col)
    dark = rgb('#3a2630')
    for ix in range(-20, 20):
        x0 = ix * PLANK
        for yy in np.arange(-2.4, 2.4, .5):
            if math.hypot(x0, yy) < R_WALL - .05 and math.hypot(x0, yy + .5) < R_WALL - .05:
                if not (HATCH['cx'] - HATCH['hw'] - .02 < x0 < HATCH['cx'] + HATCH['hw'] + .02 and HATCH['cy'] - HATCH['hh'] - .5 < yy < HATCH['cy'] + HATCH['hh']):
                    seg((x0, yy, 0), (x0 + rng.normal(0, .002), yy + .5, 0), .0035, dark * rng.uniform(.8, 1.2))
        off = float(_h(np.array([ix]), 7)[0]) * 2.0; L = 1.1 + .9 * float(_h(np.array([ix]), 3)[0])
        for j in range(-6, 6):
            yb = j * L - off
            if math.hypot(x0 + PLANK / 2, yb) < R_WALL - .05:
                seg((x0, yb, 0), (x0 + PLANK, yb, 0), .004, dark, 3)
                for e in (.25, .75):                             # nails
                    q = (x0 + PLANK * e, yb + .035, 0)
                    seg(q, (q[0] + .004, q[1] + .002, 0), .005, rgb('#3a2a34'), 2)
    if not P: return
    cv.strokes(_pad(P), np.array(Wd), np.array(C), op=.8, dry=.3, seed=5, shape='flat', bristle=.03)


def _pad(P):
    K = max(len(p) for p in P)
    out = []
    for p in P:
        t = np.linspace(0, 1, K); s = np.linspace(0, 1, len(p))
        out.append(np.c_[np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])])
    return np.array(out, f32)


def layout_tag(ck):
    import hashlib
    h = hashlib.md5(repr((CAMS[ck], PROPS, R_WALL, Z_SILL, Z_TRANSOM, LENS, TANK, TRAY, FLAME, HATCH, OPEN_BAY)).encode()).hexdigest()
    return h[:6]


def paint(key, ver="p8"):
    """painted albedo plate + geometry buffers for a camera, cached"""
    ck = 's5' if key == 's7' else key
    path = cache_path(f'lamproom_{ck}_{ver}_{layout_tag(ck)}.npz')
    if os.path.exists(path):
        z = np.load(path)
        return {k: z[k] for k in z.files}
    cam = camera(ck)
    mat, P, N, T, d = geometry(cam)
    lab, guide, tg = _elements(mat, P, N)
    ang = _angles(cam, P, tg)
    ao = _ao(mat, P, N)
    g = guide * ao[..., None]
    # turn the round things: shade by how the surface faces us, a soft window highlight, a brass glint
    V = cam.eye.astype(f32) - P; V[..., 2] = 0; V /= np.linalg.norm(V, axis=-1, keepdims=True) + 1e-6
    fac = (N[..., :2] * V[..., :2]).sum(-1)
    side = N[..., 0] * V[..., 1] - N[..., 1] * V[..., 0]          # + to the left of the facing line
    curved = np.isin(mat, (M_PLINTH, M_COLUMN, M_TANK, M_TRAY, M_CROWN, M_DRUM, M_BUCKET, M_CAN)) & (np.abs(N[..., 2]) < .5)
    sh = .50 + .50 * np.clip(fac, 0, 1) ** .7 + .35 * np.exp(-((side - .55) / .22) ** 2)
    metal = np.isin(mat, (M_TANK, M_TRAY, M_CROWN, M_BUCKET))
    sh = sh + metal * (.55 * np.exp(-((side - .30) / .07) ** 2) - .25 * np.exp(-((side + .6) / .3) ** 2))
    g = np.where(curved[..., None], g * sh[..., None], g)
    z = P[..., 2]
    band = (mat == M_DRUM) & ((np.abs(z - .12) < .025) | (np.abs(z - .50) < .025) | (z > .61))
    g = np.where(band[..., None], g * np.array([.55, .52, .62], f32), g)
    crate = (mat == M_CRATE) | (mat == M_LID) | (mat == M_STOOL)
    gap = crate & ((np.abs(((np.where(mat == M_LID, P[..., 0], z)) / .09) % 1 - .5) > .46))
    g = np.where(gap[..., None], g * .55, g)
    # soft broad modelling inside each element before the brush goes over it
    g = g * (1 + .05 * fbm(H, W, (90, 30), (1, .5), 3)[..., None])
    rng = np.random.default_rng(11)
    img = repaint(g, sizes=(16, 8, 4), seed=21, angle=ang, lab=lab, thr=(0, .012, .016), jit=(.006, .018, .02),
                  op=.9, dry=.18, aspect=4.0, curve=.25, bristle=.06)
    cv = Canvas(H, W, layer=True)
    _seams(cv, cam, mat, rng)
    sm = (mat == M_FLOOR).astype(f32)[..., None] * cv.a[..., None]
    img = img * (1 - sm) + cv.img * sm
    img = mottle(img, .018, 4, .004)
    out = dict(alb=img.astype(np.float16), mat=mat.astype(np.int8), P=P.astype(np.float16), N=N.astype(np.float16), ao=ao.astype(np.float16))
    np.savez(path, **out)
    return out



# ------------------------------------------------------------------ light
LAMP_COL = rgb('#ffb458')
N_PANEL = 8


def _sm(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t)


def lamp_light(P, N, mat):
    """spill of the flame: short falloff, the tray's shadow on the floor, the crown's on the ceiling"""
    v = FLAME[None, None].astype(f32) - P
    d = np.sqrt((v * v).sum(-1)) + 1e-6
    ndl = np.clip((v * N).sum(-1) / d, 0, 1)
    E = (.18 + .82 * ndl ** .8) / (1 + (d / .95) ** 2)
    z = P[..., 2]
    # through the plane of the tray, and of the crown
    for zp, r, soft in ((TRAY[2], TRAY[0], .05), (CROWN[1], CROWN[0], .05)):
        below = (z < zp) if zp < FLAME[2] else (z > zp)
        s = (zp - z) / (FLAME[2] - z + 1e-6)
        q = P + (FLAME - P) * s[..., None]
        rr = np.hypot(q[..., 0], q[..., 1])
        sh = below * (1 - _sm(r - soft, r + soft, rr))
        E = E * (1 - .55 * sh)
    lamp = np.isin(mat, (M_PLINTH, M_COLUMN, M_TANK, M_TRAY, M_CROWN))
    E = np.where(lamp, E * .5 + .12, E)
    E = np.where(mat == M_LENS, 0, E)
    return E.astype(f32)


def stepped(E, tx, gain=1.9):
    """painted steps in the falloff, broken by the brush"""
    e = np.clip(E * gain, 0, 1.3) + tx * np.sqrt(np.clip(E, 0, 1))
    step = np.array([0, .05, .13, .27, .48, .78, 1.15]); lev = np.array([0, .035, .10, .23, .44, .76, 1.08])
    q = np.interp(e, step, lev); hard = np.zeros_like(e)
    for a, l0, l1 in zip(step[1:], lev[:-1], lev[1:]): hard += (l1 - l0) * _sm(a * .86, a * 1.02, e)
    return (.45 * q + .55 * hard).astype(f32)


def window_light(P, N, mat, Ld, open_mask=False):
    """light from outside travelling along Ld (unit, into the room), through the glass, stopped by the mullions"""
    Ld = np.asarray(Ld, f32) / np.linalg.norm(Ld)
    D = -Ld
    # from P go along D until the wall
    a = D[0] ** 2 + D[1] ** 2
    b = 2 * (P[..., 0] * D[0] + P[..., 1] * D[1]); c = P[..., 0] ** 2 + P[..., 1] ** 2 - R_WALL ** 2
    t = (-b + np.sqrt(np.maximum(b * b - 4 * a * c, 0))) / (2 * a)
    Q = P + D * t[..., None]
    zq = Q[..., 2]
    az = np.arctan2(Q[..., 1], Q[..., 0])
    ph = ((az - BAY0) / (2 * math.pi / N_BAYS)) % 1.0
    L = 2 * math.pi * R_WALL / N_BAYS
    dm = np.minimum(ph, 1 - ph) * L; dm2 = np.abs(ph - .5) * L
    g = _sm(MULL_W * .8, MULL_W * 1.3, dm) * _sm(MULL_W * .4, MULL_W * .8, dm2) * _sm(.02, .05, np.abs(zq - Z_TRANSOM))
    g = g * _sm(Z_GLASS0 - .02, Z_GLASS0 + .03, zq) * (1 - _sm(Z_GLASS1 - .03, Z_GLASS1 + .02, zq))
    ndl = np.clip(-(N * Ld).sum(-1), 0, 1)
    wall = np.isin(mat, (M_GLASS, M_MULL, M_RING))
    return (g * ndl * ~wall).astype(f32)


def lens_beams(phi, el, rot, width=1.0, rings=1.0):
    """the bull's-eye panels throw beams: concentric rings of light around each beam axis.
    phi, el: direction from the flame (radians).  -> 0..1"""
    step = 2 * math.pi / N_PANEL
    dp = (phi - rot) % step - step / 2
    rho = np.sqrt((dp * np.cos(el)) ** 2 + el ** 2)
    sig = .11 * width
    core = np.exp(-(rho / sig) ** 2)
    ring = .5 + .5 * np.cos(rho / sig * 9.5 * rings)
    halo = np.exp(-(rho / (sig * 2.4)) ** 2)
    return (core * (.55 + .45 * ring) + .35 * halo * ring).astype(f32)


def lens_bars(phi, el, rot):
    """shadow of the brass panel frames: vertical spokes on walls (1 = lit)"""
    step = 2 * math.pi / N_PANEL
    dp = np.abs((phi - rot) % step - step / 2)
    bar = 1 - _sm(step / 2 - .05, step / 2 - .025, dp)
    hor = np.abs(el) < math.atan2(LENS[2] - FLAME[2], LENS[0]) + .05
    return np.where(hor, .62 + .38 * (1 - bar), 1.0).astype(f32)


# ------------------------------------------------------------------ outside
def sky(key, weather, ver="k4"):
    """what the windows look out on, painted.  weather: 'night' (calm, moon) or 'storm'"""
    ck = 's5' if key == 's7' else key
    path = cache_path(f'lamproom_sky_{ck}_{weather}_{ver}_{layout_tag(ck)}.npy')
    ver = ver
    if os.path.exists(path): return np.load(path).astype(f32)
    cam = camera(ck)
    d = cam.rays(); d = d / np.linalg.norm(d, axis=-1, keepdims=True)
    az = np.arctan2(d[..., 1], d[..., 0]); el = np.arcsin(np.clip(d[..., 2], -1, 1))
    u = az * 3.0; v = el * 3.0
    # noise sampled in direction space (cheap: from screen noise warped by az/el)
    n1 = fbm(H, W, (160, 60, 22), (1, .55, .3), 41, aspect=2.6)
    n2 = fbm(H, W, (300, 90), (1, .5), 42, aspect=3.5)
    eye = cam.eye
    if weather == 'night':
        g = ramp(np.clip(el / .6, 0, 1), [(0, '#34427a'), (.2, '#26305e'), (.6, '#1a2350'), (1, '#121a3a')])
        mo_az, mo_el = math.radians(150), .42
        dm = np.hypot((az - mo_az) * np.cos(el), el - mo_el)
        cl = _sm(.15, .75, n1 * .6 + n2 * .7 + .2 - el * .8)
        ccol = ramp(np.clip(1 - dm / 1.2, 0, 1), [(0, '#262f62'), (.5, '#3e4a88'), (.85, '#6f7ab5'), (1, '#b7bfe0')])
        g = g * (1 - cl[..., None] * .8) + ccol * cl[..., None] * .8
        g = g + np.exp(-(dm / .35) ** 2)[..., None] * rgb('#3a4a85') * .6
        g = np.where((dm < .035)[..., None], rgb('#e6ecff'), g)
        r = np.random.default_rng(3)
        sx, sy = r.uniform(0, W, 900), r.uniform(0, H * .8, 900)
        st = np.zeros((H, W), f32)
        for x_, y_, b_ in zip(sx, sy, r.uniform(.2, 1, 900) ** 2):
            st[int(y_), int(x_)] = b_
        st = cv2.GaussianBlur(st, (0, 0), .8) * 3 * (1 - cl) * (el > .05)
        g = g + st[..., None] * rgb('#dfe6ff')
        sea = ramp(np.clip(-el / .15, 0, 1), [(0, '#22305e'), (1, '#0f1838')])
        glint = np.exp(-((az - mo_az) / .10) ** 2) * (n1 > .6) * .6
        sea = sea + glint[..., None] * rgb('#cfd8ff')
        hz = -.012
        g = np.where((el < hz)[..., None], sea, g)
        rail_c, rim = rgb('#141a30'), rgb('#5a66a6')
    else:
        g = ramp(np.clip(el / .7, 0, 1), [(0, '#6b6f7e'), (.3, '#4a5068'), (1, '#2a2e3e')])
        cl = np.clip(.5 + n1 * .35 + n2 * .45, 0, 1)
        ccol = ramp(cl, [(0, '#33374a'), (.5, '#5a5e70'), (.85, '#8c90a0'), (1, '#a8b0c4')])
        g = mix(g, ccol, .75)
        sea = ramp(np.clip(-el / .15, 0, 1), [(0, '#2f4452'), (1, '#1c2a33')])
        foam = (fbm(H, W, (40, 14), (1, .5), 44, aspect=4) > 1.1) * .5
        sea = sea + foam[..., None] * rgb('#d8e2e6') * .5
        g = np.where((el < -.012)[..., None], sea, g)
        g = g * np.array([.80, .86, 1.0], f32)
        g = mix(g, lum(g)[..., None] * np.array([.85, .92, 1.05], f32), .35) * .72
        rail_c, rim = rgb('#1c2030'), rgb('#6b7690')
    # the gallery railing outside: two rails and posts
    RR = 3.05
    a = d[..., 0] ** 2 + d[..., 1] ** 2; b = 2 * (eye[0] * d[..., 0] + eye[1] * d[..., 1]); c = eye[0] ** 2 + eye[1] ** 2 - RR ** 2
    t = (-b + np.sqrt(np.maximum(b * b - 4 * a * c, 0))) / (2 * a)
    Q = eye + d * t[..., None]; zq = Q[..., 2]; aq = np.arctan2(Q[..., 1], Q[..., 0])
    sc = cam.f / np.maximum(t, .1)
    rail = (np.abs(zq - .98) < .022) | (np.abs(zq - .55) < .012) | ((((aq * RR) % .62) < .03) & (zq < .98))
    rail &= zq > -.2
    rc = rail_c + rim * .25 * (np.abs(zq - .98) < .025)[..., None]
    img = repaint(g, sizes=(14, 7), seed=51, angle=np.full((H, W), .05, f32) + fbm(H, W, (200,), (1,), 3) * .2,
                  thr=(0, .015), jit=(.006, .02, .02), op=.85, dry=.2, aspect=5.0, curve=.3)
    rm = cv2.GaussianBlur(rail.astype(f32), (0, 0), .7)[..., None]
    img = img * (1 - rm) + rc * rm
    np.save(path, img.astype(np.float16))
    return img


class Room:
    """one camera on the lamp room: painted plate, light buffers, and the outside"""

    def __init__(self, key, weather):
        self.key = key
        self.cam = camera(key)
        p = paint(key)
        self.alb = p['alb'].astype(f32); self.mat = p['mat']
        P = p['P'].astype(f32); N = p['N'].astype(f32)
        self.P, self.N = p['P'], p['N']
        ck = 's5' if key == 's7' else key
        path = cache_path(f'lamproom_light_{ck}_l9_{layout_tag(ck)}.npz')
        if os.path.exists(path):
            z = np.load(path); L = {k: z[k] for k in z.files}
        else:
            mat = self.mat
            E = lamp_light(P, N, mat)
            tx = fbm(H, W, (68, 24, 9), (1, .8, .5), 71, aspect=3.2) * .03 + fbm(H, W, (120, 44), (1, .6), 72, aspect=2.2) * .025
            Es = stepped(E, tx)
            v = P - FLAME
            phi = np.arctan2(v[..., 1], v[..., 0]); el = np.arctan2(v[..., 2], np.hypot(v[..., 0], v[..., 1]))
            amb = (.62 + .38 * np.clip(N[..., 2] * .5 + .5, 0, 1)) * p['ao'].astype(f32)
            ow = self.open_center()
            wv = P - ow; wd = np.sqrt((wv * wv).sum(-1)) + 1e-6
            win = np.clip(-(wv * N).sum(-1) / wd * .7 + .3, 0, 1) / (1 + (wd / 1.3) ** 2)
            L = dict(E=Es.astype(np.float16), phi=phi.astype(np.float16), el=el.astype(np.float16), amb=amb.astype(np.float16),
                     moon=window_light(P, N, mat, (-.55, -.62, -.56)).astype(np.float16),
                     flash=window_light(P, N, mat, self.flash_dir()).astype(np.float16), win=win.astype(np.float16))
            np.savez(path, **L)
        self.E = L['E'].astype(f32); self.phi = L['phi'].astype(f32); self.el = L['el'].astype(f32)
        self.amb = L['amb'].astype(f32); self.moon = cv2.GaussianBlur(L['moon'].astype(f32), (0, 0), 1.5)
        self.flash = cv2.GaussianBlur(L['flash'].astype(f32), (0, 0), 2.0); self.win = L['win'].astype(f32)
        self.glass = (self.mat == M_GLASS).astype(f32)
        self.glass = cv2.GaussianBlur(self.glass, (0, 0), .6)[..., None]
        self.sky = sky(key, weather)
        self.lamp = Lamp(self, P, N)
        self.lens_m = (self.mat == M_LENS)

    @staticmethod
    def open_center():
        a = bay_az(OPEN_BAY) + math.pi / N_BAYS * 1.5
        return np.array([R_WALL * math.cos(a), R_WALL * math.sin(a), (Z_GLASS0 + Z_TRANSOM) / 2], f32)

    @staticmethod
    def flash_dir():
        c = Room.open_center(); d = -c / np.linalg.norm(c[:2]); d[2] = -.35
        return d / np.linalg.norm(d)

    def light(self, lamp=1.0, rot=0.0, amb_col='#2c2a48', amb=1.0, moon=0.0, moon_col='#7a8ac8', win=0.0, win_col='#5a6a8a',
              flash=0.0, flash_col='#c8d4f0', beams=0.0, beam_w=1.0, rings=1.0):
        """light buffer (rgb multiplier over the albedo)"""
        C = lambda c: rgb(c) if isinstance(c, str) else np.asarray(c, f32)
        Lt = self.amb[..., None] * (C(amb_col) * 1.6 * amb)
        if moon > 0: Lt = Lt + self.moon[..., None] * C(moon_col) * moon
        if win > 0: Lt = Lt + self.win[..., None] * C(win_col) * win
        if flash > 0: Lt = Lt + (self.flash * .8 + self.win * .6 + .12)[..., None] * C(flash_col) * flash
        if lamp > 0:
            bars = lens_bars(self.phi, self.el, rot)
            e = self.E * bars
            Lt = Lt + e[..., None] * LAMP_COL * (3.2 * lamp)
            if beams > 0:
                b = lens_beams(self.phi, self.el, rot, beam_w, rings)
                Lt = Lt + (b * beams * lamp)[..., None] * rgb('#ffd08a') * 1.6
        return Lt

    def render(self, Lt, outside=None, outside_amt=1.0):
        img = self.alb * Lt
        img = 1 - (1 - np.clip(img, 0, 1.5)) * (1 - rgb('#1c1a30') * .5)       # shadows end in violet
        o = self.sky if outside is None else outside
        return img * (1 - self.glass) + o * outside_amt * self.glass



# ------------------------------------------------------------------ the lamp, drawn every frame
def flame_shape(f, lean=0.0, size=1.0, seed=0):
    """flame outline in metres around the wick top (x right, y up), drawn on twos"""
    d = f // 2
    r = np.random.default_rng(900 + d + seed * 1000)
    hgt = .11 * size * (1 + r.normal(0, .06)); wd = .03 * size * (1 + r.normal(0, .05))
    tip = np.array([lean * hgt * .9 + r.normal(0, .004) * size, hgt])
    P = np.array([[0, -.008 * size], [-wd, .012 * size], [-wd * .8 + lean * hgt * .2, hgt * .38], [tip[0] * .55 - wd * .25, hgt * .72], tip,
                  [tip[0] * .55 + wd * .3, hgt * .70], [wd * .85 + lean * hgt * .25, hgt * .36], [wd, .012 * size]])
    return P


class Lamp:
    """lens drum and flame for one Room"""

    def __init__(self, room, P, N):
        self.room = room
        m = room.mat == M_LENS
        ys, xs = np.nonzero(m)
        pad = 4
        self.box = (max(0, xs.min() - pad), max(0, ys.min() - pad), min(W, xs.max() + pad + 1), min(H, ys.max() + pad + 1))
        x0, y0, x1, y1 = self.box
        S = (slice(y0, y1), slice(x0, x1))
        Pl = P[S]; Nl = N[S]
        self.mask = cv2.GaussianBlur(m[S].astype(f32), (0, 0), .7)
        self.phi = np.arctan2(Pl[..., 1], Pl[..., 0]); self.z = Pl[..., 2]
        V = room.cam.eye.astype(f32) - Pl; V /= np.linalg.norm(V, axis=-1, keepdims=True) + 1e-6
        self.facing = np.clip((V * Nl).sum(-1), 0, 1)
        self.azc = math.atan2(room.cam.eye[1], room.cam.eye[0])          # azimuth that faces the camera
        self.tex = fbm(y1 - y0, x1 - x0, (30, 9, 3.5), (1, .6, .35), 77, aspect=4)
        self.sc = float(room.cam.scale(FLAME))
        self.fpx = room.cam.project(FLAME)[0]

    def draw(self, img, f, rot=0.0, lit=1.0, flame=1.0, lean=0.0, glow=1.0, bloom=0.0, flare=0.0):
        """lit: how much light the glass holds (0..), flame: flame size (0 = out)"""
        x0, y0, x1, y1 = self.box
        t = img[y0:y1, x0:x1]
        z, phi, fac = self.z, self.phi, self.facing
        step = 2 * math.pi / N_PANEL
        dp = (phi - rot) % step - step / 2                   # offset from the panel centre
        u = dp * LENS[0]; v = z - FLAME[2]
        # what is seen through the glass: the dim room, the brass inside, and the flame's light filling it
        inner = rgb('#252840') * (.7 + .3 * fac)[..., None]
        inner = inner + LAMP_COL * (lit * (.30 + .9 * np.exp(-(v / .16) ** 2) * fac ** 2))[..., None]
        base = t * .35 + inner * .9
        # prism rings above and below the belt
        belt = np.abs(v) < .10
        ring = np.where(belt, 0, ((np.abs(v) - .10) / .034) % 1.0)
        edge = np.exp(-((ring - .08) / .07) ** 2) + .5 * np.exp(-((ring - .92) / .05) ** 2)
        glint = np.exp(-(((phi - self.azc + 1.0 + rot * 2.0 + np.floor((np.abs(v) - .10) / .034) * .9) % (2 * math.pi) - math.pi) / .16) ** 2)
        cool = rgb('#9fb0d8') * .30 * (1 - fac * .5)[..., None]
        warm = LAMP_COL * lit
        rings = (edge * (1 - belt))[..., None] * (cool + warm[None, None] * (.45 + .9 * glint[..., None]) * (.3 + fac[..., None]))
        # the bull's-eyes in the belt
        rho = np.hypot(u, v)
        be = belt & (np.abs(u) < step / 2 * LENS[0] * .96)
        bull = np.cos(rho / .0125 * math.pi) * .5 + .5
        bull = bull ** 3 * be * np.exp(-(rho / .11) ** 2)
        centre = np.exp(-(rho / .028) ** 2) * be
        face = np.exp(-((dp + (phi - rot - dp - self.azc + math.pi) % (2 * math.pi) * 0 ) * 0) ** 2)
        look = np.clip(np.cos(phi - self.azc), 0, 1)          # 1 where the panel looks at us
        warm2 = LAMP_COL * lit * (1 + 2.5 * bloom)
        bulls = bull[..., None] * (cool * .8 + warm2 * (.35 + .9 * look[..., None] ** 3)) + centre[..., None] * warm2 * (.6 + 1.8 * look[..., None] ** 4)
        out = base + rings + bulls
        out = out * (1 + .07 * self.tex[..., None])
        # brass: the panel frames and the belt hoops
        bar = np.abs(np.abs(dp) - step / 2) < .012 / LENS[0]
        hoop = (np.abs(np.abs(v) - .10) < .007)
        brass = (bar | hoop) & (fac > .02)
        bcol = rgb('#8a6130') * (.45 + .55 * fac)[..., None] + rgb('#c8963c') * (lit * .6 * fac ** 4)[..., None] + t * .25
        out = np.where(brass[..., None], bcol, out)
        m = self.mask[..., None]
        t[:] = t * (1 - m) + out * m
        # the flame, seen through the glass
        if flame > 0:
            self.flame(img, f, flame, lean, glow)
        return img

    def flame(self, img, f, size, lean, glow):
        from lp.ink import Cel, spl
        s = self.sc
        cx, cy = self.fpx
        cy += .03 * s                                         # the wick top sits a little below the focal point
        P = flame_shape(f, lean, size)
        Q = np.c_[cx + P[:, 0] * s, cy - P[:, 1] * s]
        R = int(.16 * s * max(size, .4) + 8)
        c = Cel(2 * R, 2 * R, int(cx - R), int(cy - R))
        outer = spl(Q, closed=True, corners=(4,))
        c.fill(outer, '#ff9a3c', .95)
        inner = (Q - Q.mean(0)) * .55 + Q.mean(0) + [0, .010 * s]
        c.fill(spl(inner, closed=True, corners=(4,)), '#fff3c8')
        c.fill(spl(np.c_[cx + np.array([-.006, .006, .0]) * s, cy + np.array([.006, .006, -.012]) * s], closed=True), '#5a8ad8', .55)
        lay = c.rgba()
        from lp.ink import over_roi
        over_roi(img, lay, int(cx - R), int(cy - R))
        # light in the air around it, inside the glass
        x0, y0 = int(cx - 3 * R), int(cy - 3 * R)
        x1, y1 = int(cx + 3 * R), int(cy + 3 * R)
        x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
        yy, xx = np.mgrid[y0:y1, x0:x1].astype(f32)
        d = np.hypot((xx - cx) / 1.0, (yy - cy + .03 * s * size) / 1.25)
        g = np.clip(1 - d / (3 * R), 0, 1) ** 2.2 * .55 * glow + np.clip(1 - d / (1.1 * R), 0, 1) ** 2 * .5 * glow
        img[y0:y1, x0:x1] = 1 - (1 - np.clip(img[y0:y1, x0:x1], 0, 1)) * (1 - g[..., None] * rgb('#ffc070') * min(1, size + .2))



# ------------------------------------------------------------------ storm pieces
def sash_corners(theta):
    """the opening casement (right half of the lower pane of OPEN_BAY), hinged on its right-hand mullion,
    swung into the room by theta radians.  -> 4 world corners (hinge-bottom, free-bottom, free-top, hinge-top)"""
    step = 2 * math.pi / N_BAYS
    a_free = bay_az(OPEN_BAY) + step * .5 + .012
    a_hinge = bay_az(OPEN_BAY) + step - .012
    rr = R_WALL - .01
    h = np.array([rr * math.cos(a_hinge), rr * math.sin(a_hinge)])
    p = np.array([rr * math.cos(a_free), rr * math.sin(a_free)])
    v = p - h
    # swinging inward: rotate v about the hinge so that the free edge comes toward the centre
    c, s_ = math.cos(theta), math.sin(theta)
    sgn = 1 if np.cross(np.r_[v, 0], np.r_[-h, 0])[2] > 0 else -1
    vr = np.array([v[0] * c - sgn * v[1] * s_, sgn * v[0] * s_ + v[1] * c])
    q = h + vr
    z0, z1 = Z_GLASS0 - .01, Z_TRANSOM - .02
    return np.array([[h[0], h[1], z0], [q[0], q[1], z0], [q[0], q[1], z1], [h[0], h[1], z1]])


def draw_sash(img, cam, theta, f, lit, sky_img=None, seed=0):
    """the casement as a cel: painted frame, a glazing bar, glass that catches the light, a brass latch.
    lit: rgb light on it."""
    from lp.ink import Cel, spl, over_roi
    C = sash_corners(theta)
    k = np.linspace(0, 1, 2)
    def pt(u, v):          # u along the sash (0 hinge .. 1 free), v up
        b = C[0] + (C[1] - C[0]) * u; t = C[3] + (C[2] - C[3]) * u
        return b + (t - b) * v
    q = lambda pts: cam.project(np.array(pts))[0]
    outer = q([pt(0, 0), pt(1, 0), pt(1, 1), pt(0, 1)])
    fw = .06 / np.linalg.norm(C[1] - C[0]); fh = .06 / np.linalg.norm(C[3] - C[0])
    inner = q([pt(fw, fh), pt(1 - fw, fh), pt(1 - fw, 1 - fh), pt(fw, 1 - fh)])
    x0, y0 = np.floor(outer.min(0)).astype(int) - 12; x1, y1 = np.ceil(outer.max(0)).astype(int) + 12
    x0, y0 = max(0, x0), max(0, y0); x1, y1 = min(W, x1), min(H, y1)
    if x1 - x0 < 4 or y1 - y0 < 4: return img
    r = np.random.default_rng(seed + f // 2)
    bo = lambda P: np.asarray(P) + r.normal(0, .4, np.shape(P))
    c = Cel(x1 - x0, y1 - y0, x0, y0)
    lit = np.asarray(lit, f32)
    wood = np.clip(rgb('#55667a') * lit, 0, 1); wsh = np.clip(rgb('#55667a') * lit * .6, 0, 1)
    # glass: a faint sheen; its reflection catches the light more as the sash turns toward us
    gl = np.clip(rgb('#9fb0d8') * lit * (.25 + .25 * math.sin(min(theta, 1.4))), 0, 1)
    c.fill(bo(inner), gl, .14)
    ring = [bo(outer), bo(inner)[::-1]]
    c.fill(ring, wood, 1.0, evenodd=True)
    # the edge that turns toward us shows its thickness
    if theta > .05:
        e = q([pt(1, 0), pt(1, 1)])
        th = cam.project(np.array([pt(1, 1) + np.array([0, 0, 0])]))[0]
        c.fill(bo([e[0], e[1], e[1] + [-6 * math.sin(theta), 0], e[0] + [-6 * math.sin(theta), 0]]), wsh)
    bar = q([pt(.5 - fw * .25, fh), pt(.5 + fw * .25, fh), pt(.5 + fw * .25, 1 - fh), pt(.5 - fw * .25, 1 - fh)])
    c.fill(bo(bar), wood)
    hb = q([pt(fw, .5 - fh * .2), pt(1 - fw, .5 - fh * .2), pt(1 - fw, .5 + fh * .2), pt(fw, .5 + fh * .2)])
    c.fill(bo(hb), wood)
    lt = q([pt(.95, .48), pt(.99, .48), pt(.99, .55), pt(.95, .55)])
    c.fill(bo(lt), np.clip(rgb('#c8963c') * lit * 1.3, 0, 1))
    for P in (outer, inner):
        c.line(np.vstack([bo(P), bo(P[:1])]), 1.8, '#1e1828', taper=(.05, .05), seed=seed + 3)
    over_roi(img, c.rgba(), x0, y0)
    return img


def rain(img, f, mask, n=260, ang=1.25, speed=60., length=36., col='#a8b6c4', amt=.35, seed=0, region=None, w=1.0):
    """rain streaks: each its own place in a falling loop; mask (H,W,1) says where they are seen"""
    r = np.random.default_rng(seed)
    x0, y0, x1, y1 = region or (0, 0, W, H)
    L = np.zeros((H, W), f32)
    px = r.uniform(x0, x1, n); py = r.uniform(y0, y1, n); sp = r.uniform(.7, 1.3, n); br = r.uniform(.3, 1, n)
    dx, dy = math.cos(ang), math.sin(ang)
    span = (y1 - y0) / max(dy, .2)
    for k in range(n):
        d = (f * speed * sp[k] + py[k] * 7.3) % span
        X = px[k] + dx * d - dx * span * .5; Y = y0 + dy * d
        ln = length * sp[k]
        cv2.line(L, (int(X * 4), int(Y * 4)), (int((X + dx * ln) * 4), int((Y + dy * ln) * 4)), float(br[k]), max(1, int(w)), cv2.LINE_AA, 2)
    L = cv2.GaussianBlur(L, (0, 0), .7)
    return comp_screen(img, (L[..., None] * mask) * rgb(col) * amt)


def comp_screen(b, s):
    return 1 - (1 - np.clip(b, 0, 1.5)) * (1 - np.clip(s, 0, 1))


def smoke(img, x, y, t, s=1.0, seed=0, col='#8a90a8', amt=.5):
    """a thread of smoke from a wick just put out, t frames old (on twos)"""
    t = (t // 2) * 2
    if t < 0 or t > 70: return img
    r = np.random.default_rng(seed)
    pts = []
    for k in range(26):
        u = k / 25.
        hgt = u * (40 + 3.2 * t) * s
        sway = math.sin(u * 5 + t * .07 + seed) * (4 + 26 * u) * s + math.sin(u * 11 - t * .11) * 5 * u * s
        pts.append((x + sway + u * u * 20 * s, y - hgt))
    pts = np.array(pts)
    from lp.ink import Cel, over_roi
    x0, y0 = int(pts[:, 0].min() - 30), int(pts[:, 1].min() - 30)
    x1, y1 = int(pts[:, 0].max() + 30), int(pts[:, 1].max() + 30)
    c = Cel(x1 - x0, y1 - y0, x0, y0)
    fade = max(0., 1 - t / 70.)
    c.line(pts, 5 * s, col, taper=(.1, .5), press=.4, seed=seed, tremor=1.5, alpha=amt * fade)
    lay = c.rgba(); lay = cv2.GaussianBlur(lay, (0, 0), 2.0)
    over_roi(img, lay, x0, y0)
    return img


if __name__ == '__main__':
    import sys
    from lp import comp
    cols = {0: '#000000', M_FLOOR: '#6a4b3c', M_PLASTER: '#d8d0c4', M_SILL: '#7a5a44', M_MULL: '#3a3040', M_GLASS: '#26305e', M_RING: '#5a4038',
            M_CEIL: '#4a3a3a', M_PLINTH: '#5a5a6a', M_COLUMN: '#4a3226', M_TANK: '#c8963c', M_TRAY: '#8a6130', M_LENS: '#9ab8c8', M_CROWN: '#c8963c', M_HATCH: '#1c1a30', M_LID: '#6a4b3c', M_RAIL: '#222222'}
    out = os.path.join(os.path.dirname(__file__), 'qa', 'geo')
    os.makedirs(out, exist_ok=True)
    for key in sys.argv[1:] or ['s2', 's5', 's3']:
        cam = camera(key)
        mat, P, N, T, d = geometry(cam)
        lut = np.stack([rgb(cols.get(i, '#ff00ff')) for i in range(17)])
        img = lut[mat] * (.55 + .45 * np.clip(N @ np.array([.3, -.6, .7], f32), 0, 1))[..., None]
        img = (np.clip(img, 0, 1) * 255).astype(np.uint8).copy()
        for i in range(N_BAYS):
            a = bay_az(i) + math.pi / N_BAYS
            q, z = cam.project(np.array([R_WALL * math.cos(a), R_WALL * math.sin(a), 1.0]))
            if z > 0 and -1e4 < q[0] < 1e4: cv2.putText(img, str(i), (int(q[0]), int(q[1])), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 0), 3)
        for p, c in ((FLAME, (1, .8, .3)), (FILLER, (1, 0, 0))):
            q = cam.project(p)[0]; cv2.circle(img, (int(q[0]), int(q[1])), 8, tuple(int(v * 255) for v in c), -1)
        comp.save(f'{out}/{key}.jpg', img)
        print(key, cam.project(FLAME)[0], cam.project(FILLER)[0], 'otter px', .4 * cam.scale(np.array([0, -.4, 0]))[()])
