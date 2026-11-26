"""Compositing, light, optics, finishing."""
import numpy as np, cv2, math
from . import W, H
from .paint import rgb, f32, fbm, lum, smooth, grid


def over(base, layer, op=1.0):
    a = layer[..., 3:4] * op
    return base * (1 - a) + layer[..., :3] * op


def screen(b, s):
    return 1 - (1 - b) * (1 - np.clip(s, 0, 1))


def add(b, s):
    return b + s


def mul(b, s):
    return b * s


def soft(b, s, amt=1.0):
    """soft light"""
    o = np.where(s < .5, b - (1 - 2 * s) * b * (1 - b), b + (2 * s - 1) * (np.sqrt(np.clip(b, 0, 1)) - b))
    return b + (o - b) * amt


def blur(img, s):
    if s <= .3: return img
    if s > 12:
        q = 2 if s < 24 else 4 if s < 60 else 8
        h, w = img.shape[:2]
        sm = cv2.resize(img, (w // q, h // q), interpolation=cv2.INTER_AREA)
        sm = cv2.GaussianBlur(sm, (0, 0), s / q)
        return cv2.resize(sm, (w, h), interpolation=cv2.INTER_LINEAR)
    return cv2.GaussianBlur(img, (0, 0), s)


def radial(cx, cy, rx, ry=None, power=2.0, h=H, w=W):
    ry = rx if ry is None else ry
    x, y = grid(h, w)
    d = np.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2)
    return np.clip(1 - d, 0, 1) ** power


def glow(img, cx, cy, r, col, amt=1.0, power=2.0):
    """painted transmitted light (toukakou): screen glow"""
    g = radial(cx, cy, r, power=power)
    return screen(img, g[..., None] * (rgb(col) if isinstance(col, str) else col) * amt)


def shaft(h, w, quad, soft_px=10, seed=0, streak=.35):
    """volumetric beam mask from a screen quad (4 pts), with soft streaks along its length"""
    m = np.zeros((h, w), f32)
    cv2.fillPoly(m, [np.asarray(quad, np.float32).astype(np.int32)], 1.0, cv2.LINE_AA)
    m = blur(m, soft_px)
    q = np.asarray(quad, float)
    top = (q[0] + q[1]) / 2; bot = (q[2] + q[3]) / 2
    d = bot - top; L = np.hypot(*d); d /= L; nrm = np.array([-d[1], d[0]])
    x, y = grid(h, w)
    u = (x - top[0]) * nrm[0] + (y - top[1]) * nrm[1]
    r = np.random.default_rng(seed)
    g = r.standard_normal(512); g = np.convolve(g, np.hanning(9) / 4, 'same')
    uu = np.clip((u + 600) / 1200 * 511, 0, 511)
    st = np.interp(uu.ravel(), np.arange(512), g).reshape(h, w).astype(f32)
    st = cv2.GaussianBlur(st, (0, 0), 3)
    return np.clip(m * (1 + streak * st), 0, 1.5)


def disc_kernel(radius=7.8, rim=.25):
    n = int(math.ceil(radius)) * 2 + 1
    y, x = np.mgrid[:n, :n] - n // 2
    d = np.sqrt(x * x + y * y)
    k = np.clip(radius + .5 - d, 0, 1) * (1 + rim * np.clip(d / radius, 0, 1) ** 4)
    return (k / k.sum()).astype(f32)


def bokeh(layer, radius=7.8, ca=1.0):
    """disc-aperture defocus of a premultiplied RGBA layer plus ~1px red/blue split"""
    out = cv2.filter2D(layer, -1, disc_kernel(radius), borderType=cv2.BORDER_REPLICATE)
    if ca > 0:
        h, w = out.shape[:2]
        for c, s in ((0, ca), (2, -ca)):
            out[..., c] = cv2.warpAffine(out[..., c], np.float32([[1, 0, s], [0, 1, 0]]), (w, h), borderMode=cv2.BORDER_REPLICATE)
    return out


def cam2d(img, cx=W / 2, cy=H / 2, zoom=1.0, rot=0.0, w=W, h=H, interp=cv2.INTER_LINEAR, border=cv2.BORDER_REFLECT_101):
    """stand camera over a (possibly larger) painting: (cx,cy) in painting px lands at frame centre"""
    c, s = math.cos(rot) / zoom, math.sin(rot) / zoom
    M = np.float32([[c, -s, cx - c * w / 2 + s * h / 2], [s, c, cy - s * w / 2 - c * h / 2]])
    fl = interp | cv2.WARP_INVERSE_MAP
    if zoom < .999 and interp == cv2.INTER_LINEAR: fl = cv2.INTER_AREA | cv2.WARP_INVERSE_MAP
    return cv2.warpAffine(img, M, (w, h), flags=fl, borderMode=border)


# ------------------------------------------------------------- finishing
_gr = {}


def _grain_plate(seed):
    if seed not in _gr:
        r = np.random.default_rng(1000 + seed)
        n = r.standard_normal((H + 64, W + 64)).astype(f32)
        n = cv2.GaussianBlur(n, (0, 0), .75)
        c = r.standard_normal((H + 64, W + 64, 3)).astype(f32)
        c = cv2.GaussianBlur(c, (0, 0), 1.1)
        n = n / n.std() * .85 + c.mean(-1) / c.std() * .2
        _gr[seed] = (n, c / c.std())
    return _gr[seed]


_vig = None


def finish(img, f=0, halation='#ffe9cf', hal_amt=.22, grain=.0105, vig=.10, lift=.018, ca=.7, weave=.35, tape=.004):
    """35mm optics + restrained analog transfer.  img float RGB (may exceed 1)."""
    global _vig
    img = np.maximum(img.astype(f32), 0)
    h, w = img.shape[:2]
    # 1 halation
    L = lum(img)
    hi = np.clip((L - .72) / .28, 0, 1.6)[..., None] * np.clip(img, 0, 1.4)
    q = cv2.resize(hi, (w // 4, h // 4), interpolation=cv2.INTER_AREA)
    hal = .42 * cv2.GaussianBlur(q, (0, 0), 6.5 / 4) + .34 * cv2.GaussianBlur(q, (0, 0), 24 / 4) + .3 * cv2.GaussianBlur(q, (0, 0), 72 / 4)
    hal = cv2.resize(hal, (w, h), interpolation=cv2.INTER_LINEAR) * rgb(halation) * hal_amt
    img = 1 - (1 - np.minimum(img, 1.25)) * (1 - np.clip(hal, 0, .95))
    # 2 corner CA + gate weave
    r = np.random.default_rng(9000 + f)
    wx, wy = r.normal(0, weave * .5, 2)
    for c, s in ((0, 1 + ca / 2000.), (1, 1.0), (2, 1 - ca / 2000.)):
        M = np.float32([[s, 0, (1 - s) * w / 2 + wx], [0, s, (1 - s) * h / 2 + wy]])
        img[..., c] = cv2.warpAffine(img[..., c], M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    if _vig is None or _vig.shape[:2] != (h, w):
        x, y = grid(h, w)
        d = np.sqrt(((x - w / 2) / (w * .62)) ** 2 + ((y - h / 2) / (h * .72)) ** 2)
        _vig = (np.clip(d - .55, 0, 1) ** 1.6)[..., None]
    img *= 1 - vig * 1.6 * _vig
    # 3 black lift + C1 tanh shoulder
    img = lift + img * (1 - lift)
    knee, ceil = .80, .965
    sh = knee + (ceil - knee) * np.tanh((img - knee) / (ceil - knee))
    img = np.where(img > knee, sh, img)
    # 4 grain
    n, _ = _grain_plate(f % 5)
    ox, oy = int(r.integers(0, 64)), int(r.integers(0, 64))
    g = n[oy:oy + h, ox:ox + w]
    env = np.clip(1.12 - .95 * lum(img) ** 1.55, .12, 1.12)
    img = img + (g * env * grain)[..., None]
    # 5 faint transfer patina: chroma softening + sub-perceptual scanline
    if tape > 0:
        Y = lum(img)[..., None]
        C = cv2.GaussianBlur(img - Y, (0, 0), sigmaX=1.0, sigmaY=.01, borderType=cv2.BORDER_REFLECT_101)
        sl = 1 - tape * (np.arange(h) % 2)[:, None, None].astype(f32)
        img = (Y + C) * sl
    return np.clip(img, 0, 1)


def to8(img, f=0):
    r = np.random.default_rng(77 + f)
    d = r.random(img.shape[:2], dtype=f32)[..., None] - .5
    return np.clip(img * 255 + d + .5, 0, 255).astype(np.uint8)


def save(path, img, q=93):
    a = img if img.dtype == np.uint8 else to8(np.clip(img, 0, 1))
    cv2.imwrite(path, a[..., ::-1], [cv2.IMWRITE_JPEG_QUALITY, q])


def ease(t):
    t = np.clip(t, 0, 1); return t * t * (3 - 2 * t)


def ease_in(t, p=2.0):
    return np.clip(t, 0, 1) ** p


def ease_out(t, p=2.0):
    return 1 - (1 - np.clip(t, 0, 1)) ** p


def keyed(f, keys):
    """hard held key poses: keys=[(frame, value)], returns the value of the last key <= f"""
    v = keys[0][1]
    for k, val in keys:
        if f >= k: v = val
    return v


def lerp_keys(f, keys, e=ease):
    """eased inbetween of scalar/array keys [(frame, value), ...]"""
    if f <= keys[0][0]: return np.asarray(keys[0][1], float)
    for (a, va), (b, vb) in zip(keys[:-1], keys[1:]):
        if f < b:
            t = e((f - a) / float(b - a))
            return np.asarray(va, float) * (1 - t) + np.asarray(vb, float) * t
    return np.asarray(keys[-1][1], float)
