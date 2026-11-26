"""The lighthouse's rock: a granite islet built of weathered slabs (each an extruded, hand-cut prism with a faceted top),
painted through a Camera3D block by block, wet and dark at the waterline, grass and sea thrift on the tops.
Also the animated sea thrift and grass for close foreground rocks.  Owned by the island lane.

    import island
    L, info = island.paint_island(cam, palette='night'|'dawn'|'storm', at=(x, y, z_top), light=None, seed=3)
        # L (H, W, 4) premult RGBA.  `at` is the tower foot (same `at` as lighthouse.paint_tower); z_top is the plateau.
        # info['foam']: [(screen polyline, depth m)] the waterline seen from the camera, for animated foam
        # info['top']:  (H, W) mask of the slab tops (where grass grows)
    L, info = island.paint_rocks(cam, rocks, palette, light, seed)       # any list of island.prism(...) rocks
    T = island.Thrift(clumps=[(x, y, size), ...], palette='night', seed=1)  # screen px, foreground
    T.draw(canvas, f, wind=1.0)   # paints the clumps for frame f into an lp.paint.Canvas (layer=True), held on threes
"""
import numpy as np, cv2, math
from lp import W, H
from lp.paint import f32, rgb, mix, smooth, fbm, jit_color, repaint, mottle, Canvas, arcs, scatter_mask
from lp.ink import Cel, spl
from lp import plants

PAL = {
    'night': dict(rock=['#11152e', '#181d3c', '#20274a', '#2b3360', '#3b4476', '#525c92', '#7882b4', '#a6aed6'],
                  wet='#0e1430', weed='#16243a', grass=['#10162a', '#161e34', '#1e2a40', '#2a3a54', '#46587a'],
                  thrift=['#2a2038', '#3e2c4c', '#5a3e66', '#74547e', '#9a7aa2'], foam='#b8c4ee', lichen='#3e4a6a'),
    'dawn': dict(rock=['#4e4462', '#64566e', '#7a6a84', '#8d7a98', '#a38c9e', '#b89a9c', '#d4b8aa', '#ecd6bc'],
                 wet='#4a4058', weed='#5a5a52', grass=['#4e5a52', '#62725e', '#7a8c6a', '#98a87c', '#c2c898'],
                 thrift=['#9a5a74', '#c06e88', '#dc8ca0', '#eeaab8', '#fad0d4'], foam='#fff2e0', lichen='#c8a870'),
    'storm': dict(rock=['#14181e', '#1a2028', '#222a34', '#2c3540', '#3a4450', '#4c5662', '#66707c', '#8a94a0'],
                  wet='#12161c', weed='#1a2422', grass=['#182024', '#202c2e', '#2c3a3a', '#3e504c', '#5a6e66'],
                  thrift=['#2e2630', '#42323e', '#5a4250', '#745866', '#927684'], foam='#d8e2e6', lichen='#3a4440'),
}


def prism(cx, cy, rx, ry, z0, z1, r, k=9, inset=.30, tilt=(0, 0), rot=0.0, dome=.35, rough=.22, flare=.28):
    """one weathered slab: hand-cut footprint (k vertices), straight-ish sides, a faceted, slightly domed top"""
    a = np.linspace(0, 2 * math.pi, k, endpoint=False) + r.uniform(-.25, .25, k) * 2 * math.pi / k + rot
    rad = 1 + r.uniform(-rough, rough, k)
    fl = 1 + flare * r.uniform(.5, 1.5, k)
    bx = cx + rx * rad * fl * np.cos(a); by = cy + ry * rad * fl * np.sin(a)
    mb = 1 + flare * .25 * r.uniform(0, 1.2, k) - inset * .2
    mz = z0 + (z1 - z0) * r.uniform(.5, .72, k)
    mx = cx + rx * rad * mb * np.cos(a) + r.normal(0, .05, k) * rx; my = cy + ry * rad * mb * np.sin(a) + r.normal(0, .05, k) * ry
    ins = 1 - inset * r.uniform(.5, 1.4, k)
    tx = cx + rx * rad * ins * np.cos(a) + r.normal(0, .06, k) * rx; ty = cy + ry * rad * ins * np.sin(a) + r.normal(0, .06, k) * ry
    tz = z1 + tilt[0] * (tx - cx) + tilt[1] * (ty - cy) - r.uniform(0, .12, k) * (z1 - z0)
    top_c = np.array([tx.mean(), ty.mean(), z1 + dome * min(rx, ry) * .3])
    b = np.stack([bx, by, np.full(k, z0)], -1); m = np.stack([mx, my, mz], -1); t = np.stack([tx, ty, tz], -1)
    return dict(b=b, t=t, rings=[b, m, t], c=top_c, z0=z0, z1=z1)


def layout(at, r):
    """the islet around the tower foot `at` (tower plateau top = at z)"""
    bx, by, bz = at
    R = []
    P = lambda *a, **k: R.append(prism(*a, r=r, **k))
    # the plateau the tower and cottage stand on (flat, a little crowned)
    P(bx + 1.6, by - .6, 8.6, 6.8, -.08, bz, k=14, inset=.12, dome=.04, rough=.08, flare=.4)
    # shoulders stepping down toward us and to the sides
    for (dx, dy, rx, ry, z1) in ((-6.5, -6.2, 3.6, 2.8, bz - 1.6), (-1.5, -7.4, 4.2, 2.6, bz - 2.4), (4.6, -7.8, 3.8, 2.4, bz - 2.9), (9.2, -5.6, 3.2, 3.0, bz - 1.8),
                                 (11.4, -1.0, 3.4, 4.0, bz - 1.2), (-9.6, -1.6, 3.4, 4.2, bz - 2.0), (-12.2, -4.8, 3.0, 2.4, bz - 3.4), (7.8, -10.0, 3.0, 2.0, bz - 4.0),
                                 (-4.2, -10.2, 3.4, 1.8, bz - 4.3), (1.4, -10.8, 2.6, 1.6, bz - 4.6), (13.8, -6.2, 2.4, 2.2, bz - 3.6), (14.8, 2.6, 3.0, 3.0, bz - 2.6)):
        P(bx + dx, by + dy, rx, ry, -.08, z1 + r.uniform(0, 1.2), k=9, tilt=(r.normal(0, .05), r.normal(.04, .03)))
    # the low spit to the left, a lone stack to the right, scattered waterline rocks
    for (dx, dy, rx, ry, z1) in ((-16.5, -3.4, 3.6, 2.2, 1.6), (-21.0, -1.8, 3.0, 1.8, 1.0), (-25.0, -3.0, 2.2, 1.4, .55), (-29.5, -1.0, 1.6, 1.0, .35),
                                 (19.5, -3.0, 2.0, 2.0, 3.4), (22.4, -4.8, 1.3, 1.1, 1.1), (-14.0, -9.0, 1.8, 1.1, .7), (10.8, -12.0, 1.6, .9, .6), (-8.0, -12.6, 1.4, .8, .45),
                                 (17.0, -9.4, 1.2, .8, .5), (4.0, -13.2, 1.0, .6, .3), (-18.6, -7.0, 1.2, .7, .4)):
        P(bx + dx, by + dy, rx, ry, -.08, z1 + r.uniform(0, .5), k=8, tilt=(r.normal(0, .06), r.normal(.03, .04)))
    return R


class _RP:
    def __init__(self, cam, pal, light, seed):
        self.cam, self.pal = cam, pal
        self.r = np.random.default_rng(seed)
        self.L = np.asarray(light, float) / np.linalg.norm(light)
        self.c = Cel(cam.w, cam.h, 0, 0, ss=2)
        self.lab = np.zeros((cam.h, cam.w), np.int32); self.k = 0
        self.ang = np.zeros((cam.h, cam.w), f32)
        self.top = np.zeros((cam.h, cam.w), np.uint8)

    def S(self, P):
        return self.cam.project(np.asarray(P, float))[0]

    def col(self, pal, v, j=.03):
        v = float(np.clip(v + self.r.normal(0, j), 0, 1))
        c = plants.pick(pal, np.array([v]))
        return jit_color(c, self.r, .006, .014, .018)[0]

    def fill(self, P, col, ang=None, a=1.0, top=False):
        P = np.asarray(P, float)
        self.c.fill(P, col, a)
        self.k += 1
        q = np.round(P * 8).astype(np.int32)
        cv2.fillPoly(self.lab, [q], self.k, cv2.LINE_8, 3)
        if ang is not None: cv2.fillPoly(self.ang, [q], float(ang), cv2.LINE_8, 3)
        cv2.fillPoly(self.top, [q], 255 if top else 0, cv2.LINE_8, 3)

    def shade(self, n):
        lam = max(0., float(n @ self.L))
        return .14 + .62 * lam ** .9 + .10 * max(0., n[2])


def paint_rocks(cam, rocks, palette='night', light=None, seed=3, gouache=True, wet=.55):
    pal = PAL[palette] if isinstance(palette, str) else palette
    if light is None:
        light = -cam.R[0] * .55 - cam.R[1] * .55 - cam.R[2] * .25 + np.array([0, 0, .25])
    p = _RP(cam, pal, light, seed)
    r = p.r; E = cam.eye
    rocks = sorted(rocks, key=lambda q: -np.linalg.norm(q['c'][:2] - E[:2]))
    foam = []
    rk = pal['rock']
    for q in rocks:
        b, t = q['b'], q['t']
        k = len(b)
        if cam.cam(q['c'])[2] < .5: continue
        # sides
        faces = []
        rings = q.get('rings', [b, t])
        for li, (lo, hi) in enumerate(zip(rings[:-1], rings[1:])):
            for i in range(k):
                j = (i + 1) % k
                quad = np.array([lo[i], lo[j], hi[j], hi[i]])
                n = np.cross(lo[j] - lo[i], hi[i] - lo[i]) + np.cross(hi[j] - hi[i], hi[i] - lo[i]); n /= np.linalg.norm(n) + 1e-9
                ctr = quad.mean(0)
                if n[:2] @ (ctr[:2] - q['c'][:2]) < 0: n = -n
                if (E - ctr) @ n <= 0: continue
                faces.append((quad, n, li))
        for quad, n, li in faces:
            v = p.shade(n) + r.normal(0, .035)
            P = p.S(quad)
            d = P[3] - P[0]
            p.fill(P, p.col(rk, v, .01), ang=math.atan2(d[1], d[0]))
            # vertical facets: break the face with one or two joint lines and a second tone on part of it
            for _ in range(r.integers(1, 3)):
                u = r.uniform(.2, .8)
                a0 = quad[0] + (quad[1] - quad[0]) * u; a1 = quad[3] + (quad[2] - quad[3]) * (u + r.normal(0, .08))
                m = np.array([a0, (a0 + a1) / 2 + r.normal(0, .08, 3), a1])
                p.c.line(spl(p.S(m), n=4), max(.6, float(cam.scale(a1)) * .05), p.col(rk, max(0, v - .22), .02), (.3, .3), .4, seed=p.k, alpha=.7)
                if r.random() < .6:
                    half = np.array([a0, quad[1] if u < .5 else quad[0], quad[2] if u < .5 else quad[3], a1])
                    p.c.fill(p.S(half), p.col(rk, v + r.choice([-.07, .06]), .01), .55)
            # horizontal bedding lines
            for _ in range(r.integers(0, 3)):
                h = r.uniform(.25, .85)
                a0 = quad[0] + (quad[3] - quad[0]) * h; a1 = quad[1] + (quad[2] - quad[1]) * (h + r.normal(0, .05))
                p.c.line(p.S(np.array([a0, (a0 + a1) / 2 + r.normal(0, .05, 3), a1])), max(.5, float(cam.scale(a1)) * .04), p.col(rk, max(0, v - .18), .02), (.3, .3), .4, seed=p.k + 3, alpha=.5)
            # wet band at the waterline, weed
            def at_h(z):
                f0 = (z - quad[0][2]) / (quad[3][2] - quad[0][2] + 1e-9); f1 = (z - quad[1][2]) / (quad[2][2] - quad[1][2] + 1e-9)
                return quad[0] + (quad[3] - quad[0]) * np.clip(f0, 0, 1), quad[1] + (quad[2] - quad[1]) * np.clip(f1, 0, 1)
            if li == 0:
                l0, r0 = at_h(-.6); l1, r1 = at_h(wet + r.uniform(-.1, .3))
                p.c.fill(p.S(np.array([l0, r0, r1, l1])), rgb(pal['wet']), .75)
                l2, r2 = at_h(wet * .45)
                p.c.fill(p.S(np.array([l0, r0, r2, l2])), rgb(pal['weed']), .6)
            # lit edge along the top rim of sides facing the light
            if v > .45 and li == len(rings) - 2:
                p.c.line(p.S(np.array([quad[3], quad[2]])), max(.6, float(cam.scale(quad[2])) * .06), p.col(rk, min(1, v + .2), .02), (.2, .2), .3, seed=p.k + 5, alpha=.8)
            # waterline
            wl, wr = at_h(0.0)
            if li == 0: foam.append((p.S(np.array([wl, wr])), float(cam.cam((wl + wr) / 2)[2])))
        # top: a fan of facets around a raised centre
        if q['c'][2] < E[2] + 30:
            ctr = q['c']
            for i in range(k):
                j = (i + 1) % k
                tri = np.array([t[i], t[j], ctr])
                n = np.cross(t[j] - t[i], ctr - t[i]); n /= np.linalg.norm(n) + 1e-9
                if n[2] < 0: n = -n
                if (E - tri.mean(0)) @ n <= 0: continue
                v = p.shade(n) + .04 + r.normal(0, .03)
                P = p.S(tri)
                p.fill(P, p.col(rk, v, .01), ang=0., top=True)
            # rim highlight on the lit lip
            for i in range(k):
                j = (i + 1) % k
                e = np.array([t[i], t[j]]); n = np.cross(t[j] - t[i], [0, 0, 1.]); n /= np.linalg.norm(n) + 1e-9
                if (E - e.mean(0)) @ n <= 0: continue
                if p.shade(n * .7 + np.array([0, 0, .7])) > .5 and r.random() < .8:
                    p.c.line(p.S(e), max(.6, float(cam.scale(e[0])) * .045), p.col(rk, .92, .03), (.25, .25), .4, seed=p.k + i, alpha=r.uniform(.5, .9))
    rgba = p.c.rgba()
    a = rgba[..., 3]
    col = rgba[..., :3] / np.maximum(a[..., None], 1e-4)
    if gouache:
        x0, y0, x1, y1 = _bbox(a)
        if x1 > x0:
            sl = (slice(y0, y1), slice(x0, x1))
            g = repaint(col[sl], (7, 3.5, 1.8), seed=seed + 1, lab=p.lab[sl], mask=(a[sl] > .5).astype(f32), thr=(0, .015, .02), density=1.0, aspect=2.8,
                        angle=p.ang[sl] + fbm(y1 - y0, x1 - x0, (60,), None, seed) * .25, jit=(.006, .02, .022), op=.75, dry=.25, curve=.35, bristle=.06)
            col[sl] = mottle(g, .018, seed + 4, .004, scales=(40, 14, 5))
    out = np.dstack([col * a[..., None], a])
    return out, dict(foam=foam, top=cv2.GaussianBlur((p.top > 0).astype(f32), (0, 0), .7) * (a > .5))


def _bbox(a):
    ys, xs = np.nonzero(a > .01)
    if len(xs) == 0: return 0, 0, 0, 0
    return max(0, xs.min() - 4), max(0, ys.min() - 4), min(a.shape[1], xs.max() + 5), min(a.shape[0], ys.max() + 5)


def vegetate(L, top, cam, palette, seed=5, keep=None, density=1.0, thrift=.25):
    """grass and sea thrift on the slab tops: short blades and cushions, a few pink heads"""
    pal = PAL[palette] if isinstance(palette, str) else palette
    r = np.random.default_rng(seed)
    m = top.copy()
    if keep is not None: m *= keep
    m = cv2.erode(m, np.ones((3, 3), np.uint8))
    m *= smooth(.2, .6, fbm(cam.h, cam.w, (60, 22), (1, .5), seed + 2) * .5 + .5)
    n = int(m.sum() / 9 * density)
    if n < 10: return L
    cv = Canvas(cam.h, cam.w, img=L[..., :3] / np.maximum(L[..., 3:], 1e-4))
    x, y = scatter_mask(m, n, r)
    yd = np.clip(y.astype(int), 0, cam.h - 1)
    s = np.clip(np.interp(y, [0, cam.h], [.5, 1.6]), .5, 3)
    A = -np.pi / 2 + r.normal(.15, .4, n); ln = r.uniform(3, 8, n) * s
    P = arcs(x + np.cos(A) * ln / 2, y + np.sin(A) * ln / 2, A, ln, r.normal(.3, .5, n), K=4)
    v = r.uniform(.15, .75, n)
    cv.strokes(P, r.uniform(.6, 1.2, n) * s, jit_color(plants.pick(pal['grass'], v), r), seed=seed, shape='taper', bristle=.05)
    k = int(n * thrift * .15)
    if k > 0:
        i = r.choice(n, k)
        P = arcs(x[i], y[i] - ln[i] * .7, r.uniform(0, 3.14, k), r.uniform(1.2, 2.4, k) * s[i], 0, K=3)
        cv.strokes(P, r.uniform(.9, 1.6, k) * s[i], jit_color(plants.pick(pal['thrift'], r.uniform(.4, 1, k)), r), seed=seed + 9, shape='round', bristle=.03)
    a = L[..., 3]
    return np.dstack([cv.img * a[..., None], a])


def paint_island(cam, palette='night', at=(0, 0, 5), light=None, seed=3, gouache=True, veg=True):
    r = np.random.default_rng(seed)
    rocks = layout(at, r)
    L, info = paint_rocks(cam, rocks, palette, light, seed, gouache)
    if veg:
        L = vegetate(L, info['top'], cam, palette, seed + 7)
    return L, info


# ------------------------------------------------------------------ animated foreground plants
class Thrift:
    """foreground sea-thrift cushions with grass: every leaf and flower stalk fixed at birth, bent per drawing.
    clumps: (x, y root px, size px ~ cushion width)."""

    def __init__(self, clumps, palette='night', seed=1, heads=6, blades=60):
        self.pal = PAL[palette] if isinstance(palette, str) else palette
        r = self.r = np.random.default_rng(seed)
        self.cl = []
        for (x, y, s) in clumps:
            nb = int(blades * (s / 120) ** .7) + 8
            bl = dict(x=x + r.normal(0, s * .22, nb), y=y + r.uniform(-s * .06, s * .04, nb), a=-np.pi / 2 + r.normal(0, .55, nb),
                      L=s * r.uniform(.15, .42, nb), c=r.normal(.0, .5, nb), v=r.uniform(0, 1, nb), w=r.uniform(.9, 1.6, nb) * s / 120 * 2.2,
                      ph=r.uniform(0, 6.28, nb))
            nh = max(1, int(heads * s / 120 * r.uniform(.6, 1.3)))
            hd = dict(x=x + r.normal(0, s * .2, nh), a=-np.pi / 2 + r.normal(.05, .2, nh), L=s * r.uniform(.45, .8, nh), c=r.normal(.1, .25, nh),
                      R=s * r.uniform(.028, .042, nh), ph=r.uniform(0, 6.28, nh), v=r.uniform(.3, 1, nh))
            # cushion body dabs
            nc = int(30 * s / 120) + 6
            cu = dict(x=x + r.normal(0, s * .2, nc), y=y - np.abs(r.normal(0, s * .06, nc)), v=r.uniform(.0, .5, nc), a=r.uniform(-.5, .5, nc) - np.pi / 2)
            self.cl.append((x, y, s, bl, hd, cu))

    def draw(self, cv, f, wind=1.0, ox=0, oy=0, scale=1.0, light=-1, rim=.0):
        """light: -1 key light from the left, +1 from the right"""
        d = (f // 3) * 3
        r = np.random.default_rng(1000 + d)
        pal = self.pal
        for ci, (x, y, s, bl, hd, cu) in enumerate(self.cl):
            X = lambda q: (q - ox) * scale
            g = wind * (.10 * np.sin(d * .11 + x * .004) + .06 * np.sin(d * .27 + x * .011 + 1.3) + .05)
            # cushion
            P = arcs(X(cu['x']), (cu['y'] - oy) * scale, cu['a'], s * .16 * scale, .3, K=3)
            cv.strokes(P, s * .07 * scale, jit_color(plants.pick(pal['grass'], cu['v'] * .6), r, .002, .005, .01), seed=ci * 7, shape='leaf', bristle=.06)
            # leaves / grass blades, each bends with the gust and its own flutter
            n = len(bl['x'])
            bend = g * (bl['L'] / s * 2.2) + .04 * wind * np.sin(d * .35 + bl['ph'])
            K = 5; t = np.linspace(0, 1, K)
            A = bl['a'][:, None] + (bl['c'][:, None] * .5 + bend[:, None] * 1.6) * t[None] ** 1.4
            dd = (bl['L'] / (K - 1))[:, None] * scale
            px = X(bl['x'])[:, None] + np.c_[np.zeros(n), np.cumsum(np.cos(A[:, :-1]) * dd, 1)]
            py = ((bl['y'] - oy) * scale)[:, None] + np.c_[np.zeros(n), np.cumsum(np.sin(A[:, :-1]) * dd, 1)]
            Pb = np.stack([px, py], -1)
            lat = np.cos(A[:, 2]) * (-light)              # blades leaning toward the light catch it
            v = np.clip(bl['v'] * .55 + .25 * lat + .05, 0, 1)
            o = np.argsort(v)
            cv.strokes(Pb[o], (bl['w'] * scale)[o], plants.pick(pal['grass'], v[o]), seed=ci * 13, shape='taper', bristle=.04)
            # flower stalks and heads
            nh = len(hd['x'])
            bend = g * 1.3 + .05 * wind * np.sin(d * .23 + hd['ph'])
            A = hd['a'][:, None] + (hd['c'][:, None] * .4 + bend[:, None]) * t[None] ** 1.5
            dd = (hd['L'] / (K - 1))[:, None] * scale
            px = X(hd['x'])[:, None] + np.c_[np.zeros(nh), np.cumsum(np.cos(A[:, :-1]) * dd, 1)]
            py = ((y - oy) * scale) + np.c_[np.zeros(nh), np.cumsum(np.sin(A[:, :-1]) * dd, 1)]
            cv.strokes(np.stack([px, py], -1), .9 * s / 120 * 1.6 * scale, plants.pick(pal['grass'], np.full(nh, .45)), seed=ci * 17, shape='round', bristle=.02)
            for k in range(nh):
                hx, hy, R = px[k, -1], py[k, -1], hd['R'][k] * scale
                m = 16
                rk = np.random.default_rng(ci * 101 + k)          # the head's florets are fixed; only the light moves
                aa = rk.uniform(0, 6.28, m); rr = R * np.sqrt(rk.uniform(0, 1, m))
                fx = hx + rr * np.cos(aa); fy = hy + rr * np.sin(aa) * .85
                side = (-(fx - hx) * light - (fy - hy) * .6) / (R + 1e-3)
                vv = np.clip(hd['v'][k] * .35 + .35 * side + .2 + .15 * rk.normal(0, 1, m), 0, 1)
                o = np.argsort(vv)
                P = arcs(fx[o], fy[o], aa[o], R * .45, .4, K=3)
                cv.strokes(P, R * .36, plants.pick(pal['thrift'], vv[o]), seed=ci * 31 + k, shape='round', bristle=.03)
