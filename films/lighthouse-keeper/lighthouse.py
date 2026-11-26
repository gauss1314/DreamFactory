"""The lighthouse of 守灯人: a stone tower, white with two red bands, a glazed lantern, a verdigris dome, an outer gallery
with an iron railing, and the keeper's cottage at its foot.  Laid out in metres and painted through any lp.cam.Camera3D,
stone by stone (every block its own polygon and pigment), then gone over with small gouache strokes inside each block.
Owned by the island lane.

USAGE (other lanes: s4, s8 read this)

    import lighthouse as lh
    from lp.cam import Camera3D
    cam = Camera3D(eye, target, focal)                       # +X right, +Y forward, +Z up, metres
    L = lh.paint_tower(cam, palette='night', lamp=1.0, at=(0, 60, 0))      # (H, W, 4) premultiplied RGBA
    L, m = lh.paint_tower(cam, 'storm', lamp=0.0, at=(0, 60, 0), masks=True)
        # m['glass']  (H, W) 0..1 the lantern panes (brighten them per frame for a flash / relight)
        # m['lamp']   (x, y) lamp centre px, m['r'] lantern glass radius px, m['box'] (x0, y0, x1, y1) of the painting
    x, y = lh.lamp_px(cam, at)          # lamp centre on screen (px)
    r = lh.lamp_radius_px(cam, at)      # lantern glass radius on screen (px)
    lh.lamp_world(at) -> np.array([x, y, z])   lh.top_world(at), lh.HEIGHT (21.4 m to the rod tip)
    az = lh.beam_az(t, az0=0.)          # world azimuth (rad, 0 = +X, pi/2 = +Y) of beam 1 at t seconds; beam 2 = az + pi
    I, d = lh.beam_field(cam, az, at)   # (H, W) volumetric beam intensity (0..~3, brightest looking down the beam) and
                                        #  the depth along the view ray (use d > tower depth to hide it behind the tower)
    img = lh.lamp_glow(img, cam, at, amt=1.0, col='#ffc46b')   # painted glow of the lantern in the air

  paint_tower(cam, palette='night'|'storm'|'dawn', lamp=0..1, at=(x, y, z_ground), light=None, seed=7,
              house=True, rail='all'|'back'|'none', masks=False, gouache=True)
    light: world unit vector toward the key light (moon / sky / sun); None = upper left, a little behind the camera.
    house: the keeper's cottage (whitewashed stone, slate roof, a warm window when lamp>0 at night) sits at
           at + (4.2, -2.6) with its long wall facing -Y.  rail='back' leaves out the near half of the railing
           (s9 paints its own foreground railing).
    Cost: 2-6 s per call (paint once in setup and cache).  Deterministic for a given seed.

  Tower dimensions (metres above `at`): plinth 0-0.9 (r 3.25), shaft 0.9-15.0 (r 2.85 -> 2.05), red bands 5.2-7.0 and
  10.6-12.4, corbelled cornice 15.0-15.6, gallery deck 15.6-15.85 (r 2.95), railing r 2.85 up to 16.85, lantern wall
  15.85-16.6, glass 16.6-18.4 (r 1.5, 10 sides), lamp centre 17.5, dome 18.4-19.95, ball and rod to 21.4.
"""
import numpy as np, cv2, math
from lp import W, H
from lp.paint import f32, rgb, mix, smooth, fbm, jit_color, repaint, mottle, Canvas, arcs
from lp.ink import Cel, spl, ribbon
from lp import plants

# ------------------------------------------------------------------ dimensions (m)
Z_PLINTH = .9
Z_SHAFT = 15.0
Z_CORN = 15.6
Z_DECK = 15.85
R_DECK = 2.95
R_RAIL = 2.85
Z_RAIL = (15.98, 16.42, 16.85)
Z_LWALL = 16.6
Z_GLASS = 18.4
R_GLASS = 1.5
Z_LAMP = 17.5
Z_DOME = 18.4
Z_TOP = 19.95
HEIGHT = 21.4
BANDS = ((5.2, 7.0), (10.6, 12.4))
NSIDE = 10
BEAM_PERIOD = 8.0
HOUSE_AT = (4.2, -2.6)


def R_shaft(z):
    return float(np.interp(z, [Z_PLINTH, Z_SHAFT], [2.85, 2.05]))


def R_dome(z):
    t = np.clip((z - Z_DOME) / (Z_TOP - Z_DOME), 0, 1)
    return float(1.66 * (1 - t ** 1.9) ** .62 + .26 * t)


PAL = {
    'night': dict(stone=['#262b55', '#343a66', '#464c80', '#5c6394', '#7a80b2', '#9aa0c8', '#c3c9e8'],
                  red=['#2c1a34', '#40213a', '#5a2a3c', '#723240', '#8e3a44', '#a85862'],
                  copper=['#1c2c4c', '#2b4a63', '#36606f', '#3f6f7d', '#5a8c90', '#78a8a4', '#a9cdc8'],
                  iron='#171a36', iron_hi='#5c6394', glass='#1c2350', sky='#3a4a85', mortar='#262b55',
                  roof=['#1c1f40', '#262a52', '#323866', '#454c7e', '#6a70a2'], warm='#ffc46b', door='#2a2440',
                  grime='#2c3a5c', rust='#4a2a3c'),
    'storm': dict(stone=['#23283a', '#2e3346', '#3c4256', '#4d5266', '#626678', '#7c8092', '#a2a6b4'],
                  red=['#22202c', '#33232e', '#46283a', '#5a3040', '#6e3a46', '#84505a'],
                  copper=['#1c2830', '#263a44', '#30505a', '#3d6068', '#517a7e', '#6a9294', '#92b2b2'],
                  iron='#161a24', iron_hi='#5a5e70', glass='#1e2632', sky='#454a5c', mortar='#23283a',
                  roof=['#1a1e28', '#232834', '#2e3442', '#3e4454', '#5a5e70'], warm='#ffc070', door='#24242e',
                  grime='#2a3a3e', rust='#3e2a30'),
    'dawn': dict(stone=['#6a5a7e', '#8d7a98', '#a48c9e', '#b89a9c', '#d0b2aa', '#e6d0b8', '#f7e7d0'],
                 red=['#5a3044', '#723a4a', '#8a4450', '#a45056', '#bc6460', '#d27e70'],
                 copper=['#3e5a6e', '#4c6e7c', '#5e8488', '#709a96', '#88b0a4', '#a8c8b6', '#d0e4cc'],
                 iron='#4a4058', iron_hi='#a08ca0', glass='#6a6a8c', sky='#e9c6c8', mortar='#8d7a98',
                 roof=['#4e4460', '#5e5270', '#706280', '#8a7a94', '#b0a0b2'], warm='#ffb458', door='#5a4458',
                 grime='#7a7a8e', rust='#8a5a5a'),
}


def lamp_world(at=(0, 0, 0)):
    return np.asarray(at, float) + (0, 0, Z_LAMP)


def top_world(at=(0, 0, 0)):
    return np.asarray(at, float) + (0, 0, HEIGHT)


def lamp_px(cam, at=(0, 0, 0)):
    p, _ = cam.project(lamp_world(at))
    return float(p[0]), float(p[1])


def lamp_radius_px(cam, at=(0, 0, 0)):
    return float(cam.scale(lamp_world(at)) * R_GLASS)


def beam_az(t, az0=0.):
    return az0 + 2 * math.pi * t / BEAM_PERIOD


def beam_field(cam, az, at=(0, 0, 0), spread=.055, r0=.55, fade=180., dip=.05, step=4, cap=3.0):
    """volumetric beam: per pixel, a gaussian across the beam at the closest approach of the view ray, times the chord
    the ray cuts through the cone (so the beam flares when it looks at us).  Computed on a coarse grid, upsampled."""
    h, w = cam.h, cam.w
    ys, xs = np.mgrid[step / 2:h:step, step / 2:w:step].astype(f32)
    d = np.stack([(xs - cam.cx) / cam.f, (ys - cam.cy) / cam.f, np.ones_like(xs)], -1) @ cam.R.astype(f32)
    u = d / np.linalg.norm(d, axis=-1, keepdims=True)
    O = lamp_world(at)
    D = np.array([math.cos(az), math.sin(az), -dip]); D /= np.linalg.norm(D)
    w0 = (cam.eye - O).astype(f32)
    b = u @ D.astype(f32); dd = u @ w0; e = float(D @ w0)
    den = np.maximum(1 - b * b, 1e-5)
    t = (b * e - dd) / den
    s = (e - b * dd) / den
    s = np.maximum(s, 0)                       # behind the lamp: measure to the lamp itself
    Q = O.astype(f32) + D.astype(f32)[None, None] * s[..., None]
    t = np.maximum(((Q - cam.eye.astype(f32)) * u).sum(-1), 0)
    P = cam.eye.astype(f32) + u * t[..., None]
    dist = np.linalg.norm(P - Q, axis=-1)
    wd = r0 + s * math.tan(spread)
    chord = np.minimum(cap, 1 / np.sqrt(den))
    I = np.exp(-(dist / wd) ** 2) * chord * np.exp(-s / fade)
    I = cv2.resize(I.astype(f32), (w, h), interpolation=cv2.INTER_LINEAR)
    T = cv2.resize(np.where(t > 0, t, 0).astype(f32), (w, h), interpolation=cv2.INTER_LINEAR)
    return I, T


def lamp_glow(img, cam, at=(0, 0, 0), amt=1.0, col='#ffc46b', size=1.0):
    x, y = lamp_px(cam, at); r = lamp_radius_px(cam, at)
    R = int(r * 26 * size) + 4
    x0, x1, y0, y1 = max(0, int(x - R)), min(img.shape[1], int(x + R)), max(0, int(y - R)), min(img.shape[0], int(y + R))
    if x1 <= x0 or y1 <= y0: return img
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(f32)
    q = np.sqrt((xx - x) ** 2 + (yy - y) ** 2) / (r * size)
    g = (.55 * np.exp(-(q / 1.1) ** 2) + .30 * np.exp(-(q / 3.2) ** 2) + .12 * np.exp(-(q / 8.) ** 2)) * amt
    c = rgb(col) if isinstance(col, str) else np.asarray(col, f32)
    img[y0:y1, x0:x1] = 1 - (1 - img[y0:y1, x0:x1]) * (1 - np.clip(g[..., None] * c, 0, .98))
    return img


# ------------------------------------------------------------------ painter
class _P:
    def __init__(self, cam, at, pal, light, seed, box):
        self.cam, self.A, self.pal = cam, np.asarray(at, float), pal
        self.r = np.random.default_rng(seed)
        self.L = np.asarray(light, float) / np.linalg.norm(light)
        x0, y0, x1, y1 = box
        self.x0, self.y0, self.w, self.h = x0, y0, x1 - x0, y1 - y0
        self.c = Cel(self.w, self.h, x0, y0, ss=2)
        self.lab = np.zeros((self.h, self.w), np.int32); self.k = 0
        self.glass = np.zeros((self.h, self.w), f32)
        self.ink = np.zeros((self.h, self.w), f32)
        e = cam.eye - self.A
        self.phc = math.atan2(e[1], e[0])                 # world azimuth of the camera seen from the axis
        self.dh = math.hypot(e[0], e[1])
        self.ez = e[2]
        self.pxm = float(cam.scale(self.A + (0, 0, 8)))   # px per metre at the tower

    # geometry
    def W(self, th, z, r, ax=(0, 0)):
        """tower-local (theta from the camera direction, z, radius) -> world"""
        th, z, r = np.broadcast_arrays(np.asarray(th, float), np.asarray(z, float), np.asarray(r, float))
        a = self.phc + th
        return np.stack([self.A[0] + ax[0] + r * np.cos(a), self.A[1] + ax[1] + r * np.sin(a), self.A[2] + z], -1)

    def S(self, P):
        return self.cam.project(P)[0]

    def T(self, th, z, r):
        return self.S(self.W(th, z, r))

    def vis(self, r):
        return math.acos(min(.999, r / max(self.dh, r + 1e-3)))

    def shade(self, n, amb=.26, k=.62, sky=.08):
        n = np.asarray(n, float)
        lam = max(0., float(n @ self.L))
        return amb + k * lam ** .85 + sky * max(0., n[2])

    def ncyl(self, th):
        a = self.phc + th
        return np.array([math.cos(a), math.sin(a), 0.])

    def col(self, pal, v, j=.03):
        v = float(np.clip(v + self.r.normal(0, j), 0, 1))
        c = plants.pick(pal, np.array([v]))
        L = float(c.mean())
        return jit_color(c, self.r, .002 + .008 * L * L, .012, .014)[0]

    def fill(self, P, col, a=1.0, lab=True):
        polys = [np.asarray(q, float) for q in P] if isinstance(P, list) else [np.asarray(P, float)]
        self.c.fill(polys if len(polys) > 1 else polys[0], col, a, evenodd=len(polys) > 1)
        if lab:
            self.k += 1
            q = [np.round((g - (self.x0, self.y0)) * 8).astype(np.int32) for g in polys]
            cv2.fillPoly(self.lab, q, self.k, cv2.LINE_8, 3)

    def line(self, P, w, col, a=1.0, taper=(.2, .2), seed=None, ink=False):
        """ink=True: forged iron, a steady line kept out of the gouache pass"""
        P = np.asarray(P, float)
        sd = self.k if seed is None else seed
        if ink:
            self.c.line(P, w, col, taper, .06, seed=sd, tremor=.08, alpha=a)
            R = ribbon(P, w + 1.5, taper, .06, sd, .08)
            if R is not None:
                cv2.fillPoly(self.ink, [np.round((R - (self.x0, self.y0)) * 8).astype(np.int32)], 1.0, cv2.LINE_AA, 3)
        else:
            self.c.line(P, w, col, taper, .3, seed=sd, alpha=a)

    # --- cylindrical masonry
    def courses(self, R, z0, z1, pal, hrow=(.42, .6), wr=(1.4, 2.6), vadd=lambda th, z: 0., gap=.02, jit=.035, skip=None, edge=True):
        r = self.r
        z = z0
        while z < z1 - .05:
            h = min(r.uniform(*hrow), z1 - z)
            if z1 - (z + h) < hrow[0] * .5: h = z1 - z
            rr = R(z + h / 2)
            lim = self.vis(rr) + .02
            th = -lim - r.uniform(0, .3)
            rowv = r.normal(0, .02)
            while th < lim:
                dth = h * r.uniform(*wr) / rr
                a, b = max(th, -lim), min(th + dth, lim)
                th += dth
                if b - a < .01: continue
                if skip is not None and skip((a + b) / 2, z + h / 2): continue
                ga = gap / rr
                g = gap
                m1, m2 = a + (b - a) * r.uniform(.3, .45), a + (b - a) * r.uniform(.55, .7)
                wv = lambda zz: zz + r.normal(0, .012)
                q = [(a + ga, wv(z + g)), (m1, wv(z + g)), (m2, wv(z + g)), (b - ga, wv(z + g)), (b - ga, wv(z + h * .5)),
                     (b - ga, wv(z + h - g)), (m2, wv(z + h - g)), (m1, wv(z + h - g)), (a + ga, wv(z + h - g)), (a + ga, wv(z + h * .5))]
                P = np.array([self.T(t, zz, R(zz)) for t, zz in q])
                mth = (a + b) / 2
                v = self.shade(self.ncyl(mth)) + vadd(mth, z + h / 2) + rowv + r.normal(0, jit)
                if r.random() < .05: v += r.choice([-.06, .06])
                c = self.col(pal, v, .008)
                u = r.random()
                if u < .08: c = c * np.array([1.03, .99, .975], f32)
                elif u < .16: c = c * np.array([.975, 1.0, 1.02], f32)
                self.fill(spl(P, closed=True, corners=(0, 3, 5, 8), n=3), c)
                lv = self.shade(self.ncyl(mth)) - .26
                if edge and lv > .12 and r.random() < .7:     # worn lit arris on the upper edge
                    e = np.array([self.T(a + ga * 2, z + h - g * 2, R(z + h)), self.T(m1, z + h - g * 1.5, R(z + h)), self.T(m2, z + h - g * 1.8, R(z + h))])
                    self.line(e, r.uniform(.5, 1.0) * max(.6, self.pxm / 22), self.col(pal, min(1, v + .12), .02), r.uniform(.35, .7))
            z += h

    def shell(self, R, z0, z1, pal, v=.0, nth=36, nz=12, vadd=lambda th, z: 0.):
        lim = self.vis(R((z0 + z1) / 2)) + .02
        ths = np.linspace(-lim, lim, nth); zs = np.linspace(z0, z1, nz)
        for a, b in zip(ths[:-1], ths[1:]):
            for u, w_ in zip(zs[:-1], zs[1:]):
                q = np.array([self.T(a - .004, u, R(u)), self.T(b + .004, u, R(u)), self.T(b + .004, w_ + .02, R(w_)), self.T(a - .004, w_ + .02, R(w_))])
                vv = self.shade(self.ncyl((a + b) / 2)) + v + vadd((a + b) / 2, (u + w_) / 2)
                self.c.fill(q, self.col(pal, vv, .005))

    def ring(self, z, r, n=48, lim=None):
        lim = self.vis(r) if lim is None else lim
        return np.array([self.T(t, z, r) for t in np.linspace(-lim, lim, n)])

    def disc_ring(self, z, r0, r1, n=72):
        """annulus on a horizontal plane (all around), as an even-odd polygon pair"""
        t = np.linspace(-math.pi, math.pi, n, endpoint=False)
        return [self.T(t, z, r1), self.T(t, z, r0)]


def _box(cam, at, house):
    pts = []
    A = np.asarray(at, float)
    for z in (-1.0, 8, HEIGHT + .3):
        for a in np.linspace(0, 2 * math.pi, 12, endpoint=False):
            pts.append(A + (3.4 * math.cos(a), 3.4 * math.sin(a), z))
    if house:
        for dx in (-3.2, 3.2):
            for dy in (-2.2, 2.2):
                for z in (-.5, 5.2):
                    pts.append(A + (HOUSE_AT[0] + dx, HOUSE_AT[1] + dy, z))
    P, z = cam.project(np.array(pts))
    P = P[z > .1]
    if len(P) == 0: return None
    x0, y0 = np.floor(P.min(0)).astype(int) - 24; x1, y1 = np.ceil(P.max(0)).astype(int) + 24
    x0, y0 = max(x0, -64), max(y0, -64); x1, y1 = min(x1, cam.w + 64), min(y1, cam.h + 64)
    if x1 - x0 < 8 or y1 - y0 < 8: return None
    return x0, y0, x1, y1


def paint_tower(cam, palette='night', lamp=1.0, at=(0, 0, 0), light=None, seed=7, house=True, rail='all', masks=False, gouache=True):
    pal = PAL[palette] if isinstance(palette, str) else palette
    if light is None:
        light = -cam.R[0] * .55 + (-cam.R[1]) * .55 - cam.R[2] * .25
        light = light + np.array([0, 0, .25])
    box = _box(cam, at, house)
    out = np.zeros((cam.h, cam.w, 4), f32)
    if box is None:
        return (out, dict(glass=np.zeros((cam.h, cam.w), f32), lamp=lamp_px(cam, at), r=lamp_radius_px(cam, at), box=None)) if masks else out
    p = _P(cam, at, pal, light, seed, box)
    hp = np.asarray(at, float) + (HOUSE_AT[0], HOUSE_AT[1], 0)
    house_front = house and np.linalg.norm(cam.eye[:2] - hp[:2]) < np.linalg.norm(cam.eye[:2] - p.A[:2])
    if house and not house_front: _house(p, lamp)
    _tower(p, lamp, rail)
    if house and house_front: _house(p, lamp)
    rgba = p.c.rgba()
    a = rgba[..., 3]
    col = rgba[..., :3] / np.maximum(a[..., None], 1e-4)
    if gouache and p.pxm > 6:
        hw = max(1.2, min(4.5, p.pxm * .09))
        g = repaint(col, (hw * 1.6, hw * .8), seed=seed + 3, lab=p.lab, mask=((a > .5) & (p.glass < .05) & (p.ink < .05)).astype(f32), thr=(0, .012), density=.9, aspect=2.6,
                    jit=(.004, .012, .014), op=.55, dry=.2, curve=.25, bristle=.05)
        g = mottle(g, .012, seed + 5, .003, scales=(40, 14, 5))
        keep = np.clip(1 - cv2.GaussianBlur(np.maximum(p.glass, p.ink), (0, 0), 1.0) * 1.5, 0, 1)[..., None]
        col = np.where((a > .02)[..., None], g * keep + col * (1 - keep), col)
    rgba = np.dstack([col * a[..., None], a])
    x0, y0 = p.x0, p.y0
    X0, Y0, X1, Y1 = max(0, x0), max(0, y0), min(cam.w, x0 + p.w), min(cam.h, y0 + p.h)
    out[Y0:Y1, X0:X1] = rgba[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0]
    if not masks: return out
    gm = np.zeros((cam.h, cam.w), f32)
    gm[Y0:Y1, X0:X1] = p.glass[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0]
    return out, dict(glass=gm, lamp=lamp_px(cam, at), r=lamp_radius_px(cam, at), box=(X0, Y0, X1, Y1))


# ------------------------------------------------------------------ the tower
def _tower(p, lamp, rail):
    r = p.r; pal = p.pal; c = p.c
    st, red = pal['stone'], pal['red']
    px = p.pxm

    def grime(th, z):          # salt and weather: darker toward the base and under the gallery
        return -.10 * smooth(2.6, 0.4, z) - .13 * smooth(13.6, 14.9, z) + .03 * math.sin(th * 3 + z * .7) * 0

    win = [(-.35, 3.2), (.42, 8.6), (-.15, 13.2)]        # stair windows (theta, z0); h 1.0, w .55
    door_th = math.atan2(HOUSE_AT[1], HOUSE_AT[0]) - p.phc
    door_th = (door_th + math.pi) % (2 * math.pi) - math.pi

    # plinth: big rough blocks
    Rp = lambda z: 3.25 - .08 * z
    p.shell(Rp, -.6, Z_PLINTH + .02, st, -.14)
    p.courses(Rp, -.6, Z_PLINTH, st, hrow=(.42, .55), wr=(1.6, 2.8), vadd=lambda t, z: -.10, gap=.035, jit=.05)
    # plinth top lip
    lim = p.vis(3.2)
    top = np.vstack([p.ring(Z_PLINTH + .06, 3.22), p.ring(Z_PLINTH - .08, 3.2)[::-1]])
    p.fill(top, p.col(st, p.shade(np.array([0, 0, 1.])) + .1, .01))
    # shaft
    def band_of(z):
        return any(a - .02 <= z <= b + .02 for a, b in BANDS)
    p.shell(R_shaft, Z_PLINTH, Z_SHAFT, st, -.07, vadd=grime)
    for a, b in BANDS:
        p.shell(R_shaft, a, b, red, -.05)
    zs = [Z_PLINTH] + sorted([q for ab in BANDS for q in ab]) + [Z_SHAFT]
    for k, (z0, z1) in enumerate(zip(zs[:-1], zs[1:])):
        isred = k % 2 == 1
        p.courses(R_shaft, z0, z1, red if isred else st, hrow=(.44, .6), wr=(1.5, 2.7), vadd=grime, gap=.016 if not isred else .02, jit=.03)
    # rust streaks running down from the gallery, salt bloom near the base
    for _ in range(int(26 * min(1, px / 12) + 8)):
        th = r.uniform(-p.vis(2.2) * .95, p.vis(2.2) * .95); L = r.uniform(.8, 4.5); z1 = Z_SHAFT - r.uniform(0, .3)
        q = np.array([p.T(th + r.normal(0, .002) * k, z1 - L * k / 4, R_shaft(z1 - L * k / 4) + .01) for k in range(5)])
        p.line(q, max(.6, px * r.uniform(.03, .08)), rgb(pal['rust']), r.uniform(.10, .26), (.05, .8))
    for _ in range(int(30 * min(1, px / 12) + 6)):
        th = r.uniform(-p.vis(2.8) * .95, p.vis(2.8) * .95); z0 = Z_PLINTH + r.uniform(0, .5); L = r.uniform(.5, 2.4)
        q = np.array([p.T(th, z0 + L * k / 4, R_shaft(z0 + L * k / 4) + .01) for k in range(5)])
        p.line(q, max(.6, px * r.uniform(.05, .12)), rgb(pal['grime']), r.uniform(.08, .2), (.6, .05))
    # stair windows and the door
    for th, z0 in win:
        _opening(p, th, z0, .55, 1.0, lamp=0)
    if abs(door_th) < p.vis(2.85) * .85:
        _opening(p, door_th, Z_PLINTH, .95, 2.05, lamp=0, door=True)
    # limb rim on the key-light side
    for s in (-1, 1):
        th = s * p.vis(R_shaft(8)) * .985
        if p.shade(p.ncyl(th)) - .26 > .25:
            z = Z_PLINTH
            while z < Z_SHAFT - .2:
                hh = r.uniform(.5, 1.8); zz = np.linspace(z, min(Z_SHAFT, z + hh), 4)
                if r.random() < .8:
                    q = np.array([p.T(th, u, R_shaft(u)) for u in zz])
                    vv = p.shade(p.ncyl(th)) + .15
                    p.line(q, max(.8, px * .06) * r.uniform(.7, 1.2), p.col(red if band_of(z + hh / 2) else st, min(1, vv), .02), r.uniform(.6, .95))
                z += hh + r.uniform(.05, .2)
    # cornice: corbels under the gallery
    lim = p.vis(2.1)
    shadow = np.vstack([p.ring(Z_SHAFT + .02, R_shaft(Z_SHAFT)), p.ring(Z_SHAFT - .55, R_shaft(Z_SHAFT - .55))[::-1]])
    c.fill(shadow, rgb(pal['stone'][0]), .45)
    p.fill(np.vstack([p.ring(Z_CORN, 2.25), p.ring(Z_SHAFT - .02, R_shaft(Z_SHAFT))[::-1]]), p.col(st, p.shade(np.array([0, 0, -1.])) + .02, .01))
    nC = 22
    for k in range(nC):
        th = -math.pi + 2 * math.pi * (k + .5) / nC
        th = (th + math.pi) % (2 * math.pi) - math.pi
        if abs(th) > p.vis(2.6) * .98: continue
        w = .26 / 2.4
        face = np.array([p.T(th - w, Z_CORN, 2.78), p.T(th + w, Z_CORN, 2.78), p.T(th + w, Z_CORN - .22, 2.7), p.T(th + w * .9, Z_SHAFT + .02, 2.12),
                         p.T(th - w * .9, Z_SHAFT + .02, 2.12), p.T(th - w, Z_CORN - .22, 2.7)])
        v = p.shade(p.ncyl(th) * .7 + np.array([0, 0, -.7])) + .04
        p.fill(spl(face, closed=True, corners=(0, 1, 3, 4), n=3), p.col(st, v, .03))
        side = 1 if float(p.ncyl(th + .3) @ p.L) < float(p.ncyl(th - .3) @ p.L) else -1
        e = face[[1, 2, 3]] if side > 0 else face[[0, 5, 4]]
        p.line(e, max(.7, px * .05), p.col(st, max(0, v - .2), .02), .6)
    # gallery deck: underside, top (when seen from above), edge
    if p.ez < Z_CORN:
        p.fill(p.disc_ring(Z_CORN, 2.2, R_DECK), p.col(st, .2, .01))
        for k in range(nC):           # the corbel ends against the soffit
            pass
    edge_lit = lambda th: p.shade(p.ncyl(th))
    if p.ez > Z_DECK:
        t = np.linspace(-math.pi, math.pi, 90, endpoint=False)
        p.fill(p.T(t, Z_DECK, R_DECK), p.col(st, p.shade(np.array([0, 0, 1.])) - .02, .01))
        # flagstones on the deck
        nf = 28
        for k in range(nf):
            a0 = -math.pi + 2 * math.pi * k / nf + r.normal(0, .02); a1 = a0 + 2 * math.pi / nf
            for (r0, r1) in ((1.55, 2.2), (2.2, R_DECK - .03)):
                q = np.array([p.T(a0 + .006, Z_DECK + .003, r0 + .02), p.T(a1 - .006, Z_DECK + .003, r0 + .02), p.T(a1 - .006, Z_DECK + .003, r1 - .02), p.T(a0 + .006, Z_DECK + .003, r1 - .02)])
                p.fill(q, p.col(st, p.shade(np.array([0, 0, 1.])) - .04 + r.normal(0, .04), .01))
    ths = np.linspace(-p.vis(R_DECK), p.vis(R_DECK), 60)
    for a, b in zip(ths[:-1:2], ths[2::2]):
        q = np.array([p.T(a, Z_CORN, R_DECK), p.T(b, Z_CORN, R_DECK), p.T(b, Z_DECK, R_DECK), p.T(a, Z_DECK, R_DECK)])
        p.fill(q, p.col(st, edge_lit((a + b) / 2) + .04, .02))
    p.line(p.ring(Z_DECK, R_DECK + .01), max(.8, px * .05), p.col(st, .95, .01), .7)
    # railing, far half
    if rail != 'none':
        _railing(p, back=True)
    # lantern wall (low drum, iron plates with a little door)
    Rl = lambda z: 1.6
    plate = [pal['iron'], mix(rgb(pal['iron']), rgb(st[2]), .5), pal['iron_hi'], st[3]]
    p.shell(Rl, Z_DECK, Z_LWALL, plate, -.1)
    nP = 10
    for k in range(nP):
        a0 = -math.pi + 2 * math.pi * k / nP + .1; a1 = a0 + 2 * math.pi / nP
        a0, a1 = max(a0, -p.vis(1.6)), min(a1, p.vis(1.6))
        if a1 - a0 < .02: continue
        v = p.shade(p.ncyl((a0 + a1) / 2)) - .1
        q = np.array([p.T(a0 + .012, Z_DECK + .04, 1.61), p.T(a1 - .012, Z_DECK + .04, 1.61), p.T(a1 - .012, Z_LWALL - .04, 1.61), p.T(a0 + .012, Z_LWALL - .04, 1.61)])
        p.fill(q, p.col(plate, v * .8, .02))
        if p.pxm > 60:
            for zz in (Z_DECK + .1, Z_LWALL - .1):
                for u in np.linspace(a0 + .05, a1 - .05, 5):
                    x, y = p.T(u, zz, 1.62); rr = max(.8, p.pxm * .01)
                    tt = np.linspace(0, 2 * math.pi, 10)
                    c.fill(np.c_[x + rr * np.cos(tt), y + rr * np.sin(tt)], p.col(plate, min(1, v * .8 + .2), .02), .8)
        p.line(np.array([p.T(a0 + .006, Z_DECK + .03, 1.615), p.T(a0 + .006, Z_LWALL - .03, 1.615)]), max(.6, p.pxm * .012), rgb(pal['iron']), .8, (0, 0), ink=True)
    dth = math.radians(150) - p.phc        # a low iron door to the gallery
    dth = (dth + math.pi) % (2 * math.pi) - math.pi
    if abs(dth) < p.vis(1.6) * .8:
        q = np.array([p.T(dth - .17, Z_DECK + .02, 1.62), p.T(dth + .17, Z_DECK + .02, 1.62), p.T(dth + .17, Z_LWALL + .25, 1.62), p.T(dth - .17, Z_LWALL + .25, 1.62)])
        p.fill(q, p.col(plate, .2, .01))
        p.line(q[[0, 3, 2, 1]], max(.6, p.pxm * .015), rgb(pal['iron']), .9, (0, 0), ink=True)
    p.line(p.ring(Z_LWALL - .02, 1.63), max(.8, p.pxm * .03), p.col(plate, .7, .02), .8, (0, 0), ink=True)
    # lantern glass
    _lantern(p, lamp)
    # dome
    _dome(p)
    if rail == 'all':
        _railing(p, back=False)


def _opening(p, th, z0, w, h, lamp=0., door=False):
    r = p.r; pal = p.pal; st = pal['stone']
    R = R_shaft(z0 + h / 2)
    def arch(dr, grow=0.):
        pts = []
        a = w / 2 + grow
        hs = h - w / 2
        pts += [(-a, -grow), (-a, hs)]
        for t in np.linspace(math.pi, 0, 9)[1:-1]:
            pts.append((a * math.cos(t), hs + (w / 2 + grow) * math.sin(t)))
        pts += [(a, hs), (a, -grow)]
        return np.array([p.T(th + u / R, z0 + v, R + dr) for u, v in pts])
    lv = p.shade(p.ncyl(th))
    # trim stones
    hs = h - w / 2
    for j in range(7):
        t0, t1 = math.pi * j / 7, math.pi * (j + 1) / 7
        q = []
        for t, e in ((t0, 0), (t1, 0), (t1, .22), (t0, .22)):
            q.append(((w / 2 + e) * math.cos(t), hs + (w / 2 + e) * math.sin(t)))
        P = np.array([p.T(th + u / R, z0 + v, R + .02) for u, v in q])
        p.fill(P, p.col(st, lv + .08, .03))
    o = arch(0.0); i = arch(-.3, -.04)
    p.fill(o, p.col(st, .12 + .1 * lv, .01))
    p.fill(i, rgb(pal['door']) if door else rgb(pal['glass']))
    if door:
        for k in range(1, 4):
            u = -w / 2 + w * k / 4
            P = np.array([p.T(th + u / R, z0 + .05, R - .29), p.T(th + u / R, z0 + h - .3, R - .29)])
            p.line(P, max(.6, p.pxm * .03), mix(rgb(pal['door']), rgb('#000000'), .35), .6)
    else:
        P = np.array([p.T(th, z0 + .05, R - .29), p.T(th, z0 + h - .1, R - .29)])
        p.line(P, max(.6, p.pxm * .03), rgb(pal['iron']), .8)
    sill = np.array([p.T(th + u / R, z0 + v, R + .1) for u, v in ((-w / 2 - .12, 0), (w / 2 + .12, 0), (w / 2 + .1, -.14), (-w / 2 - .1, -.14))])
    p.fill(sill, p.col(st, lv + .12, .02))


def _lantern(p, lamp):
    r = p.r; pal = p.pal; c = p.c
    warm = rgb(pal['warm'])
    lim = p.vis(R_GLASS)
    # interior seen through the glass: sky through the far panes, darker toward the floor
    sil = np.vstack([p.ring(Z_LWALL, R_GLASS, 40), p.ring(Z_GLASS, R_GLASS, 40)[::-1]])
    p.fill(sil, rgb(pal['glass']))
    gl = np.zeros((p.h * 2, p.w * 2), np.uint8)
    cv2.fillPoly(gl, [np.round((sil - (p.x0, p.y0)) * 2 * 8).astype(np.int32)], 255, cv2.LINE_AA, 3)
    p.glass = np.maximum(p.glass, cv2.resize(gl.astype(f32) / 255, (p.w, p.h), interpolation=cv2.INTER_AREA))
    c.clip(sil)
    # far panes: sky tint varying pane to pane
    for k in range(NSIDE):
        a0 = -math.pi + 2 * math.pi * k / NSIDE + .5 * 2 * math.pi / NSIDE; a1 = a0 + 2 * math.pi / NSIDE
        q = np.array([p.T(a0, Z_LWALL, R_GLASS), p.T(a1, Z_LWALL, R_GLASS), p.T(a1, Z_GLASS, R_GLASS), p.T(a0, Z_GLASS, R_GLASS)])
        cc = mix(rgb(pal['glass']), rgb(pal['sky']), r.uniform(.15, .55))
        c.fill(q, cc, .5)
    # lamp light inside: a soft warm bloom in the room
    if lamp > 0:
        cx, cy = p.S(lamp_world(p.A)); rp = R_GLASS * p.pxm
        t = np.linspace(0, 2 * math.pi, 48)
        for gg in np.linspace(1, 0, 14):
            rr = rp * (.3 + 1.6 * (1 - gg))
            c.fill(np.c_[cx + rr * np.cos(t), cy + rr * .95 * np.sin(t)], mix(warm, rgb('#fff0c8'), gg ** 2), (.07 + .07 * gg) * lamp)
    _lens(p, lamp)
    c.unclip()
    # near panes: reflections, mullions, glazing bar
    for k in range(NSIDE):
        a0 = -math.pi + 2 * math.pi * k / NSIDE; a1 = a0 + 2 * math.pi / NSIDE
        a0c, a1c = max(a0, -lim), min(a1, lim)
        if a1c - a0c < .02: continue
        q = np.array([p.T(a0c, Z_LWALL, R_GLASS), p.T(a1c, Z_LWALL, R_GLASS), p.T(a1c, Z_GLASS, R_GLASS), p.T(a0c, Z_GLASS, R_GLASS)])
        refl = max(0., float(p.ncyl((a0c + a1c) / 2) @ p.L))
        c.fill(q, rgb(pal['sky']) * 1.15, (.06 + .18 * refl * r.uniform(.5, 1.3)) * (1 - .6 * lamp))
        if r.random() < .5:      # a diagonal glint
            u = r.uniform(.2, .6)
            g0 = p.T(a0c + (a1c - a0c) * u, Z_LWALL + .2, R_GLASS + .01); g1 = p.T(a0c + (a1c - a0c) * (u + .25), Z_GLASS - .3, R_GLASS + .01)
            p.line([g0, g1], max(.6, p.pxm * .05), mix(rgb(pal['sky']), rgb('#ffffff'), .4), .14 + .2 * refl)
    for k in range(NSIDE):
        a = -math.pi + 2 * math.pi * k / NSIDE
        if abs(a) > lim: continue
        P = np.array([p.T(a, Z_LWALL, R_GLASS + .02), p.T(a, Z_GLASS, R_GLASS + .02)])
        v = p.shade(p.ncyl(a))
        p.line(P, max(.9, p.pxm * .055), rgb(pal['iron']), 1.0, (.0, .0), ink=True)
        if v > .45: p.line(P + [[-max(.6, p.pxm * .02), 0]], max(.5, p.pxm * .018), rgb(pal['iron_hi']), .7, (.1, .1), ink=True)
    p.line(p.ring((Z_LWALL + Z_GLASS) / 2 + .1, R_GLASS + .02, 40), max(.7, p.pxm * .04), rgb(pal['iron']), .9, (0, 0), ink=True)
    p.line(p.ring(Z_LWALL + .02, R_GLASS + .03, 40), max(1.0, p.pxm * .07), rgb(pal['iron']), 1.0, (0, 0), ink=True)
    p.line(p.ring(Z_GLASS - .02, R_GLASS + .03, 40), max(1.0, p.pxm * .07), rgb(pal['iron']), 1.0, (0, 0), ink=True)
    if lamp > 0:          # warm rim the lamp throws on the iron glazing frame
        p.line(p.ring(Z_LWALL + .08, R_GLASS + .04, 40), max(.5, p.pxm * .02), warm, .35 * lamp, (0, 0), ink=True)


def _lens(p, lamp):
    """the Fresnel lens: a barrel of glass prism rings on a brass frame, a belt of bull's-eye panels round the lamp"""
    r = p.r; pal = p.pal; c = p.c
    warm = rgb(pal['warm']); brass = rgb('#8a6130'); glass = rgb(pal['glass']); sky = rgb(pal['sky'])
    Rl = lambda z: .6 * (1 - .12 * ((z - Z_LAMP) / .8) ** 2)
    z0, z1 = Z_LAMP - .82, Z_LAMP + .82
    core = mix(warm, rgb('#fff8e4'), .85)
    def tone(zc, th, belt=False):
        d = abs(zc - Z_LAMP) / .82
        if lamp > 0:
            k = (1 - d) ** 1.3 * (1 - .5 * abs(th) / 1.6) * lamp
            cc = mix(mix(rgb('#c87a3a'), warm, .5 + .5 * k), core, k ** 1.5 * (1.0 if belt else .75))
            return mix(cc, glass, (1 - lamp) * .85)
        v = .25 + .4 * max(0., math.cos(th + .6)) * (1 - d * .5)
        return mix(mix(glass, sky, v), rgb('#ffffff'), .05 * (zc > Z_LAMP))
    lim = p.vis(Rl(Z_LAMP))
    # base wash of the barrel
    sil = np.vstack([p.ring(z0, Rl(z0), 30, lim), p.ring(z1, Rl(z1), 30, lim)[::-1]])
    c.fill(sil, tone(Z_LAMP, 0) * .8 if lamp == 0 else mix(rgb('#b8743a'), warm, .5), .9)
    nb = 8
    edges = np.linspace(-math.pi, math.pi, nb + 1) + .2
    rings = list(np.linspace(z1, Z_LAMP + .2, 7)) + [Z_LAMP - .2] + list(np.linspace(Z_LAMP - .2, z0, 6))[1:]
    for k in range(nb):
        a, b = max(edges[k], -lim), min(edges[k + 1], lim)
        if b - a < .03: continue
        m = (a + b) / 2
        for j, (za, zb) in enumerate(zip(rings[:-1], rings[1:])):
            belt = za > Z_LAMP and zb < Z_LAMP
            zc = (za + zb) / 2
            q = np.array([p.T(a + .02, za, Rl(za)), p.T(b - .02, za, Rl(za)), p.T(b - .02, zb, Rl(zb)), p.T(a + .02, zb, Rl(zb))])
            col = tone(zc, m, belt) * (1 + .06 * (j % 2) + r.normal(0, .02))
            c.fill(q, np.clip(col, 0, 1.2), .95)
            if not belt:       # prism edge: a bright line along the ring's lower lip
                e = np.array([p.T(a + .03, zb + .03, Rl(zb) + .005), p.T(m, zb + .03, Rl(zb) + .005), p.T(b - .03, zb + .03, Rl(zb) + .005)])
                p.line(e, max(.5, p.pxm * .012), mix(col, rgb('#ffffff'), .5), .55, (.2, .2))
            else:              # bull's-eye: concentric rings on the panel
                cx, cy = p.T(m, Z_LAMP, Rl(Z_LAMP) + .01)
                wpx = abs(p.T(b, Z_LAMP, Rl(Z_LAMP))[0] - p.T(a, Z_LAMP, Rl(Z_LAMP))[0]) * .5
                hpx = abs(p.T(m, za, Rl(za))[1] - p.T(m, zb, Rl(zb))[1]) * .5
                tt = np.linspace(0, 2 * math.pi, 28)
                for qq in (.85, .6, .35):
                    p.line(np.c_[cx + wpx * qq * np.cos(tt), cy + hpx * qq * np.sin(tt)], max(.5, p.pxm * .01), mix(col, rgb('#ffffff') if lamp else sky, .45), .5, (0, 0))
                if lamp > 0:
                    c.fill(np.c_[cx + wpx * .22 * np.cos(tt), cy + hpx * .22 * np.sin(tt)], rgb('#fffaf0'), .9 * lamp)
    # brass frame: vertical bars and the belt rims
    for e_ in edges:
        if abs(e_) > lim: continue
        P = np.array([p.T(e_, z, Rl(z) + .01) for z in np.linspace(z0, z1, 6)])
        p.line(P, max(.6, p.pxm * .022), brass * (1.15 if lamp else .7), .95, (0, 0), ink=True)
    for z in (z0, Z_LAMP - .2, Z_LAMP + .2, z1):
        p.line(p.ring(z, Rl(z) + .01, 24, lim), max(.6, p.pxm * .02), brass * (1.15 if lamp else .7), .95, (0, 0), ink=True)
    # pedestal under the lens
    q = np.vstack([p.ring(z0 - .02, .3, 12, p.vis(.3)), p.ring(Z_LWALL - .1, .22, 12, p.vis(.22))[::-1]])
    c.fill(q, brass * (.9 if lamp else .55), .95)


def _dome(p):
    r = p.r; pal = p.pal; c = p.c
    cu = pal['copper']
    zs = np.linspace(Z_DOME, Z_TOP, 8)
    # eave ring
    p.fill(np.vstack([p.ring(Z_DOME - .14, 1.72), p.ring(Z_DOME + .05, 1.72)[::-1]]), p.col(cu, .25, .02))
    lim = p.vis(1.7)
    def dn(th, z):
        dr = (R_dome(z + .05) - R_dome(z - .05)) / .1
        nh = 1 / math.hypot(1, dr); nz = -dr / math.hypot(1, dr)
        return p.ncyl(th) * nh + np.array([0, 0, nz])
    sil = np.vstack([np.array([p.T(-p.vis(R_dome(z)), z, R_dome(z)) for z in zs]), np.array([p.T(p.vis(R_dome(z)), z, R_dome(z)) for z in zs[::-1]])])
    p.fill(sil, p.col(cu, .15, .01))
    ng = 16
    gore = r.normal(0, .012, ng)
    for i in range(ng):
        a0 = -math.pi + 2 * math.pi * i / ng; a1 = a0 + 2 * math.pi / ng
        for j, (z0, z1) in enumerate(zip(zs[:-1], zs[1:])):
            l0, l1 = p.vis(R_dome(z0)), p.vis(R_dome(z1))
            aa, bb = max(a0, -min(l0, l1)), min(a1, min(l0, l1))
            if bb - aa < .01: continue
            mt = (aa + bb) / 2
            q = np.array([p.T(aa, z0, R_dome(z0)), p.T(mt, z0 - .02, R_dome(z0)), p.T(bb, z0, R_dome(z0)), p.T(bb, z1 + .03, R_dome(z1)), p.T(aa, z1 + .03, R_dome(z1))])
            v = p.shade(dn(mt, (z0 + z1) / 2), amb=.22, k=.66, sky=.16) + gore[i] + r.normal(0, .012)
            cc = p.col(cu, v, .01)
            if r.random() < .12: cc = mix(cc, rgb(pal['stone'][2]), .2)
            p.fill(q, cc)
    for i in range(ng):
        a = -math.pi + 2 * math.pi * i / ng
        L = np.array([p.T(a, z, R_dome(z) + .02) for z in np.linspace(Z_DOME, Z_TOP - .05, 10) if abs(a) < p.vis(R_dome(z))])
        if len(L) < 3: continue
        v = p.shade(dn(a, Z_DOME + .5), amb=.22, k=.66, sky=.16)
        p.line(L, max(.5, p.pxm * .022), p.col(cu, max(0, v - .18), .02), .55, (.02, .3), ink=True)
        p.line(L + [-max(.5, p.pxm * .02), 0], max(.4, p.pxm * .012), p.col(cu, min(1, v + .15), .02), .45, (.02, .4), ink=True)
    # ball ventilator, rod
    cx, cy = p.S(p.A + (0, 0, Z_TOP + .26)); rb = .3 * p.pxm
    t = np.linspace(0, 2 * math.pi, 24)
    p.fill(np.c_[cx + rb * np.cos(t), cy + rb * np.sin(t)], p.col(cu, .25, .01))
    lx, ly = -p.cam.R[0] @ p.L, p.cam.R[1] @ p.L
    nrm = math.hypot(lx, ly) + 1e-6
    c.shade(np.c_[cx + rb * .75 * np.cos(t) + rb * .25 * (-lx / nrm), cy + rb * .75 * np.sin(t) - rb * .25 * (ly / nrm)], p.col(cu, .7, .01), within=np.c_[cx + rb * np.cos(t), cy + rb * np.sin(t)])
    a0 = p.S(p.A + (0, 0, Z_TOP + .5)); a1 = p.S(p.A + (0, 0, HEIGHT))
    p.line([a0, a1], max(.8, p.pxm * .04), rgb(pal['iron']), 1.0, (0, .6), ink=True)


def _railing(p, back):
    pal = p.pal
    iron = rgb(pal['iron'])
    e = p.cam.eye - p.A
    nposts = 36
    def far(th):
        return math.cos(th) < 0          # theta measured from the camera direction
    lw = lambda z, th: max(.7, float(p.cam.scale(p.W(th, z, R_RAIL))) * .045)
    for k in range(nposts):
        th = -math.pi + 2 * math.pi * (k + .5) / nposts
        if far(th) != back: continue
        P = np.array([p.T(th, Z_DECK, R_RAIL), p.T(th, Z_RAIL[2], R_RAIL)])
        p.line(P, lw(16.4, th), iron, 1.0, (0, .1), ink=True)
    for z in Z_RAIL:
        th = np.linspace(-math.pi, math.pi, 181)
        sel = np.array([far(t) == back for t in th])
        # split into contiguous runs
        idx = np.nonzero(sel)[0]
        if len(idx) < 2: continue
        runs = np.split(idx, np.nonzero(np.diff(idx) > 1)[0] + 1)
        if back and len(runs) == 2 and runs[0][0] == 0 and runs[1][-1] == 180:
            runs = [np.r_[runs[1], runs[0][1:] + 181]]
        for run in runs:
            tt = np.where(run > 180, th[run % 181] + 2 * math.pi, th[run % 181])
            for c0 in range(0, len(tt) - 1, 6):
                ts = tt[c0:c0 + 7]
                if len(ts) < 2: continue
                P = p.T(ts, z, R_RAIL)
                wv = lw(z, float(ts.mean()))
                p.line(P, wv * (1.25 if z == Z_RAIL[2] else .8), iron, 1.0, (0, 0), ink=True)
                if z == Z_RAIL[2]:
                    hi = mix(iron, rgb(pal['iron_hi']), .8)
                    p.line(P + [0, -wv * .35], wv * .4, hi, .6, (0, 0), ink=True)


# ------------------------------------------------------------------ the keeper's cottage
def _house(p, lamp):
    r = p.r; pal = p.pal; c = p.c
    st = pal['stone']
    O = p.A + (HOUSE_AT[0], HOUSE_AT[1], -.15)
    Lx, Dy, Hw, Hr = 4.4, 3.0, 2.5, 3.9            # length (x), depth (y), wall height, ridge height
    ex, ey, ez = np.array([1., 0, 0]), np.array([0, 1., 0]), np.array([0, 0, 1.])
    C = lambda u, v, w: O + ex * u + ey * v + ez * w
    walls = [  # (origin, e1, e2, width, height, normal, gable)
        (C(-Lx / 2, -Dy / 2, 0), ex, ez, Lx, Hw, -ey, False),
        (C(Lx / 2, Dy / 2, 0), -ex, ez, Lx, Hw, ey, False),
        (C(Lx / 2, -Dy / 2, 0), ey, ez, Dy, Hw, ex, True),
        (C(-Lx / 2, Dy / 2, 0), -ey, ez, Dy, Hw, -ex, True),
    ]
    E = p.cam.eye
    S = p.S
    for (o, e1, e2, wd, ht, n, gable) in walls:
        ctr = o + e1 * wd / 2 + e2 * ht / 2
        if (E - ctr) @ n <= 0: continue
        v0 = p.shade(n, amb=.28, k=.6)
        outline = [o, o + e1 * wd, o + e1 * wd + e2 * ht]
        if gable: outline.append(o + e1 * wd / 2 + e2 * Hr)
        outline.append(o + e2 * ht)
        p.fill(S(np.array(outline)), p.col(st, v0 - .12, .01))
        # whitewashed rubble: courses on the face
        vv = 0.
        while vv < (Hr if gable else ht) - .05:
            hh = r.uniform(.28, .4)
            u = -r.uniform(0, .5)
            while u < wd:
                ww = r.uniform(.45, .85)
                a, b = max(0, u), min(wd, u + ww)
                u += ww
                if b - a < .06: continue
                top = min(vv + hh, Hr if gable else ht)
                if gable and vv > ht:
                    lim_u = (top - ht) / (Hr - ht) * wd / 2
                    a, b = max(a, lim_u), min(b, wd - lim_u)
                    if b - a < .06: continue
                g = .018
                q = [o + e1 * (a + g) + e2 * (vv + g), o + e1 * (b - g) + e2 * (vv + g + r.normal(0, .01)), o + e1 * (b - g) + e2 * (top - g), o + e1 * (a + g) + e2 * (top - g + r.normal(0, .01))]
                p.fill(spl(S(np.array(q)), closed=True, corners=(0, 1, 2, 3), n=3), p.col(st, v0 + r.normal(0, .03) - .1 * smooth(.6, 0, vv), .01))
            vv += hh
        # window(s) and door on the long front wall; a small window on the gable
        ops = [(.75, .95, .75, .9, 'win'), (2.1, 0., .85, 1.85, 'door'), (3.25, .95, .75, .9, 'win')] if not gable else [(Dy / 2 - .3, 1.1, .6, .7, 'win')]
        if n @ ey > .5: ops = [(1.4, .95, .8, .9, 'win')]
        for (u, v, w_, h_, kind) in ops:
            q = np.array([o + e1 * u + e2 * v, o + e1 * (u + w_) + e2 * v, o + e1 * (u + w_) + e2 * (v + h_), o + e1 * u + e2 * (v + h_)])
            # stone surround
            qq = np.array([o + e1 * (u - .12) + e2 * (v - .1), o + e1 * (u + w_ + .12) + e2 * (v - .1), o + e1 * (u + w_ + .12) + e2 * (v + h_ + .14), o + e1 * (u - .12) + e2 * (v + h_ + .14)])
            p.fill(S(qq), p.col(st, v0 + .04, .02))
            if kind == 'door':
                p.fill(S(q), rgb(pal['door']))
                for j in range(1, 4):
                    a = o + e1 * (u + w_ * j / 4) + e2 * (v + .05); b = a + e2 * (h_ - .1)
                    p.line(S(np.array([a, b])), max(.5, p.pxm * .02), mix(rgb(pal['door']), rgb('#000000'), .3), .6)
                continue
            lit = lamp > 0 and kind == 'win'
            if lit:
                p.fill(S(q), mix(rgb('#7a3e3a'), rgb(pal['warm']), .85))
                inner = np.array([o + e1 * (u + .08) + e2 * (v + .08) + n * .01, o + e1 * (u + w_ - .08) + e2 * (v + .08) + n * .01,
                                  o + e1 * (u + w_ - .08) + e2 * (v + h_ - .1) + n * .01, o + e1 * (u + .08) + e2 * (v + h_ - .1) + n * .01])
                c.fill(S(inner), rgb('#ffe2a4'), .55)
                # curtain on one side, a pot on the sill: dark against the warm
                cur = np.array([o + e1 * (u + w_ * .62) + e2 * (v + h_ - .04), o + e1 * (u + w_ - .02) + e2 * (v + h_ - .04), o + e1 * (u + w_ - .02) + e2 * (v + .04), o + e1 * (u + w_ * .78) + e2 * (v + .04)])
                c.fill(S(cur), mix(rgb('#c47a48'), rgb(pal['warm']), .3), .9)
                pot = np.array([o + e1 * (u + .14) + e2 * (v + .02), o + e1 * (u + .3) + e2 * (v + .02), o + e1 * (u + .32) + e2 * (v + .2), o + e1 * (u + .12) + e2 * (v + .2)])
                c.fill(S(pot), rgb('#4a2a30'), .9)
            else:
                p.fill(S(q), rgb(pal['glass']))
            mx = o + e1 * (u + w_ / 2); my = o + e2 * (v + h_ / 2) - o
            p.line(S(np.array([mx + e2 * v, mx + e2 * (v + h_)])), max(.6, p.pxm * .035), rgb('#3a2a30') if lit else rgb(pal['iron']), .9)
            p.line(S(np.array([o + e1 * u + my, o + e1 * (u + w_) + my])), max(.6, p.pxm * .035), rgb('#3a2a30') if lit else rgb(pal['iron']), .9)
            sill = np.array([o + e1 * (u - .1) + e2 * v + n * .12, o + e1 * (u + w_ + .1) + e2 * v + n * .12, o + e1 * (u + w_ + .1) + e2 * (v - .1), o + e1 * (u - .1) + e2 * (v - .1)])
            p.fill(S(sill), p.col(st, v0 + .16, .02))
    # roof: two slate planes, eaves overhang
    ov = .3
    ridge0, ridge1 = C(-Lx / 2 - ov, 0, Hr), C(Lx / 2 + ov, 0, Hr)
    for s in (-1, 1):
        e0 = C(-Lx / 2 - ov, s * (Dy / 2 + ov), Hw - .22); e1_ = C(Lx / 2 + ov, s * (Dy / 2 + ov), Hw - .22)
        n = np.cross(e1_ - e0, ridge0 - e0) * (-s)
        n = n / np.linalg.norm(n)
        if n[2] < 0: n = -n
        ctr = (e0 + e1_ + ridge0 + ridge1) / 4
        if (E - ctr) @ n <= 0: continue
        v0 = p.shade(n, amb=.24, k=.55, sky=.12)
        p.fill(S(np.array([e0, e1_, ridge1, ridge0])), p.col(pal['roof'], v0 - .1, .01))
        rows = 9
        for j in range(rows):
            t0, t1 = j / rows, (j + 1) / rows + .02
            u = -r.uniform(0, .3)
            while u < 1:
                du = r.uniform(.05, .09)
                a, b = max(0, u), min(1, u + du); u += du
                if b - a < .01: continue
                P = lambda uu, tt: e0 + (e1_ - e0) * uu + (ridge0 - e0) * tt
                q = np.array([P(a + .002, t0), P(b - .002, t0), P(b - .002, t1), P(a + .002, t1)])
                p.fill(S(q), p.col(pal['roof'], v0 + r.normal(0, .05) - .06 * (j == 0), .01))
            p.line(S(np.array([e0 + (ridge0 - e0) * t0, e1_ + (ridge1 - e1_) * t0])), max(.5, p.pxm * .03), p.col(pal['roof'], max(0, v0 - .3)), .5, (0, 0))
        p.line(S(np.array([e0, e1_])), max(.7, p.pxm * .05), p.col(pal['roof'], max(0, v0 - .35)), .8, (0, 0))
    p.line(S(np.array([ridge0, ridge1])), max(.8, p.pxm * .07), p.col(pal['roof'], .8), .8, (.05, .05))
    # chimney on the gable end nearest the tower, a little smoke is the shot's business
    ch = [C(-Lx / 2 + .25, -.3, 3.2), C(-Lx / 2 + .8, -.3, 3.2), C(-Lx / 2 + .8, -.3, 4.5), C(-Lx / 2 + .25, -.3, 4.5)]
    p.fill(S(np.array(ch)), p.col(st, p.shade(-ey) - .05, .02))
    cap = [C(-Lx / 2 + .18, -.35, 4.45), C(-Lx / 2 + .87, -.35, 4.45), C(-Lx / 2 + .87, -.35, 4.6), C(-Lx / 2 + .18, -.35, 4.6)]
    p.fill(S(np.array(cap)), p.col(st, .3, .02))


def house_window_px(cam, at=(0, 0, 0)):
    """screen centre of the cottage's warm front window (for a glow in the shot)"""
    O = np.asarray(at, float) + (HOUSE_AT[0], HOUSE_AT[1], -.15)
    P = O + (-2.2 + .75 + .375, -1.5, .95 + .45)
    q, _ = cam.project(P)
    return float(q[0]), float(q[1])
