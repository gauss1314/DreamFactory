"""Shared plumbing for the Lighthouse Keeper soundtrack: epochs, the per-part accumulator, orchestral seating.

Every part (a music section or a shot's effects) is a function E -> Out.pack(), where E maps event names to film seconds.
Parts run in worker processes; sound.py sums them, puts every (stem, epoch, room) bus through its room and mixes.
"""
import numpy as np
from core import *
from inst import *
import rooms

K = nt

# ------------------------------------------------------------------ epochs
# Music lives in three worlds: everything up to the flame going out (a hard cut, reverb and all), the dark and the lost
# boat, and the relit lamp to the end. Effects cut with the picture: one epoch per shot (s2 and s3 share the lamp room).
MUSIC_EP = [(0.0, 30.5), (30.5, 40.0), (40.0, 70.0)]
MUSIC_FADE = [(.0, .012), (.004, .20), (.01, .05)]          # fade in / out lengths at each window's edges
SFX_EP = [(0.0, 7.0), (7.0, 19.0), (19.0, 27.0), (27.0, 34.0), (34.0, 40.0), (40.0, 49.0), (49.0, 57.0), (57.0, 70.0)]
SFX_FADE = .012


def ep_of(stem, t):
    eps = MUSIC_EP if stem == 'music' else SFX_EP
    for i, (a, b) in enumerate(eps):
        if t < b - 1e-6:
            return i
    return len(eps) - 1


def ep_window(stem, e, n_total):
    """(start sample, end sample, gain window) for epoch e of a stem; the window covers [start, end)."""
    eps = MUSIC_EP if stem == 'music' else SFX_EP
    a, b = eps[e]
    fi, fo = (MUSIC_FADE[e] if stem == 'music' else (SFX_FADE, SFX_FADE))
    if e == 0:
        fi = 0
    if e == len(eps) - 1:
        fo = 0
    i0 = max(0, ns(a - fi * .5))
    i1 = min(n_total, ns(b + fo * .5) + 1)
    t = np.arange(i0, i1) / SR
    w = np.ones(len(t))
    if fi > 0:
        w *= smoothstep((t - (a - fi * .5)) / fi)
    if fo > 0:
        w *= 1 - smoothstep((t - (b - fo * .5)) / fo)
    return i0, i1, w


class Out:
    """Collects (stem, epoch, room) contributions as positioned segments; pack() returns compact float32 arrays."""

    def __init__(self):
        self.d = {}

    def _add(self, key, t, x):
        self.d.setdefault(key, []).append((ns(t), x))

    def put(self, stem, t, x, gdb=0.0, p=0.0, room=None, wet=-12.0, ep=None, dry=0.0):
        x = np.asarray(x, float)
        if x.ndim == 1:
            x = pan2(x, p)
        e = ep_of(stem, t) if ep is None else ep
        g = float(db(gdb))
        if dry is not None:
            self._add((stem, e, 'dry'), t, x * (g * float(db(dry))))
        if room:
            self._add((stem, e, room), t, x * (g * float(db(wet))))

    def pack(self):
        out = {}
        for k, segs in self.d.items():
            a = min(i for i, _ in segs)
            b = max(i + x.shape[1] for i, x in segs)
            buf = np.zeros((2, b - a), np.float64)
            for i, x in segs:
                buf[:, i - a:i - a + x.shape[1]] += x
            out[k] = (a, buf.astype(np.float32))
        return out


# ------------------------------------------------------------------ orchestra (after The Last Page's score.py)
PL = dict(vn1=14, vn2=12, vla=10, vc=8, cb=6)
KD = dict(vn1='vn', vn2='vn', vla='va', vc='vc', cb='cb')
BAL = dict(timp=9.0, bd=8.0, glock=8.0, harp=-2.5, choir=2.5)


def seatput(out, name, t0, g, gdb, ep=None, wet=None, room='stage'):
    s = rooms.seat(name)
    gdb = gdb + BAL.get(name, 0.0)
    acc = None
    for i in range(len(g)):
        h = s[i % len(s)]
        st = np.stack([conv(g[i], h[0]), conv(g[i], h[1])])
        acc = st if acc is None else acc + st
    out.put('music', t0, acc, gdb, room=room, wet=(rooms.WET[name] if wet is None else wet), ep=ep)


def S(out, name, notes, gdb=0.0, seed=1, n=None, ep=None, wet=None, **kw):
    t0, g = strings(notes, KD[name], n or PL[name], 4, seed=seed, **kw)
    gdb = gdb + (9.0 if kw.get('art') == 'spic' else 0.0)
    seatput(out, name, t0, g, gdb, ep, wet)


def BRS(out, name, notes, gdb=0.0, seed=1, n=None, ep=None, **kw):
    n = n or len(rooms.SEATS[name])
    t0, g = brass(notes, name, n, seed, **kw)
    seatput(out, name, t0, g, gdb, ep)


def CH(out, part, notes, gdb=0.0, seed=1, n=9, ep=None, **kw):
    t0, g = choir(notes, part, n, 4, seed=seed, **kw)
    if part in 'TB':
        g = g[::-1]
    seatput(out, 'choir', t0, g, gdb, ep)


def hit(out, name, t, x, gdb=0.0, ep=None):
    seatput(out, name, t, x[None] if x.ndim == 1 else x, gdb, ep)


def harp(out, notes, gdb=0.0, seed=500, ep=None):
    """[(t, midi, vel)] into one buffer"""
    t0 = min(n[0] for n in notes) - .01
    t1 = max(n[0] for n in notes) + 4.5
    b = np.zeros(ns(t1 - t0))
    for q, (t, m, v) in enumerate(notes):
        x = harp_note(m, v, seed + q)
        i = ns(t - t0)
        e = min(len(b), i + len(x))
        b[i:e] += x[:e - i]
    seatput(out, 'harp', t0, b[None], gdb, ep)


def glock(out, notes, gdb=0.0, seed=600, ep=None, soft=False):
    t0 = min(n[0] for n in notes) - .01
    t1 = max(n[0] for n in notes) + 3.5
    b = np.zeros(ns(t1 - t0))
    for q, (t, m, v) in enumerate(notes):
        x = glock_note(m, v, seed + q, soft=soft)
        i = ns(t - t0)
        e = min(len(b), i + len(x))
        b[i:e] += x[:e - i]
    seatput(out, 'glock', t0, b[None], gdb, ep)


def gliss(t0, t1, lo, hi, scale, v0, v1, curve_=1.15):
    ms = [m for m in range(K(lo), K(hi) + 1) if m % 12 in [x % 12 for x in scale]]
    u = np.linspace(0, 1, len(ms)) ** (1 / curve_)
    r = rng(int(t0 * 100))
    return [(t0 + (t1 - t0) * a + r.normal(0, .004), m, v0 + (v1 - v0) * a) for a, m in zip(u, ms)]


def roll(out, name, t0, t1, fn, v0, v1, gdb=0.0, rate=14.0, seed=700, ep=None, shape=1.6):
    b = np.zeros(ns(t1 - t0 + 4.0))
    r = rng(seed)
    t = 0.0
    q = 0
    while t < t1 - t0:
        u = t / (t1 - t0)
        v = v0 + (v1 - v0) * u ** shape
        x = fn(v * r.uniform(.82, 1.1), seed + q)
        i = ns(t)
        b[i:i + len(x)] += x[:len(b) - i]
        t += 1 / rate * r.uniform(.88, 1.12)
        q += 1
    seatput(out, name, t0, b[None], gdb, ep)


_CY = {}


def cym(kind=0):
    if kind not in _CY:
        _CY[kind] = cymbal_ir(31) if kind == 0 else cymbal_ir(33, lo=90, hi=9000, K=800, t_lo=8, t_hi=1.2, L=7.0, bloom=.10)
    return _CY[kind]


def cymbal_roll(dur, seed, dark=0):
    """Soft mallets on a suspended cymbal, brightness blooming with level."""
    r = rng(seed)
    n = ns(dur + 3.0)
    ex = np.zeros(n)
    t = 0.0
    while t < dur:
        u = t / dur
        i = ns(t)
        m = ns(.006)
        ex[i:i + m] += r.normal(0, 1, m) * np.hanning(m) * (.04 + u ** 2.2) * r.uniform(.6, 1.1)
        t += r.uniform(.028, .05)
    c = cym(dark)
    y = np.stack([conv(ex, c[k])[:n] for k in (0, 1)])
    br = curve([(0, 1500), (dur * .6, 4500), (dur, 16000), (dur + .2, 16000), (dur + 3, 6000)], n)
    y = np.stack([svf(y[k], br, .6, 'lp') for k in (0, 1)])
    return y * 11.0 * fade(n, .01, 1.0)


def crash(out, t, gdb, seed, dark=0, ep=None, bright=15000):
    m = ns(.004)
    ex = rng(seed).normal(0, 1, m) * np.hanning(m)
    c = cym(dark)
    y = np.stack([conv(ex, c[k]) for k in (0, 1)])
    y = lp(y, bright, 1)
    out.put('music', t, y * 10.0, gdb, room='stage', wet=-11, ep=ep)


# ------------------------------------------------------------------ piano bus
_SB = {}


def piano(out, notes, gdb=0.0, seed=40, felt=1.0, ep=None, wet=-13.0, halo=-21.0, peds=()):
    """[(t, midi or name, vel, hold)] close felt piano: strings + soundboard + open-string halo, small room and stage."""
    if not _SB:
        _SB['b'], _SB['s'] = soundboard_ir(), sympathetic_ir()
    notes = [(t, K(m) if isinstance(m, str) else m, v, h) for t, m, v, h in notes]
    t0 = min([n[0] for n in notes] + [p[0] for p in peds]) - .05
    t1 = max(n[0] + min(n[3] + 1.5, 17) for n in notes)
    tr = Track(t0, t1 + 1.0)
    for q, (t, m, v, h) in enumerate(notes):
        tr.add(t, piano_note(m, v, h, seed + q * 5, felt))
    n = tr.x.shape[1]
    br = np.zeros((2, n))
    for q, (t, v) in enumerate(peds):
        k = ns(.4)
        th = modes(k, np.array([56, 81, 119, 168, 260]), [1, .9, .6, .35, .15], [.12, .11, .09, .07, .05], seed + 400 + q, att=.004, phase=0) * .010 * v
        th += bp(white(k, seed + 410 + q), 150, 1800, 1) * np.exp(-np.arange(k) / SR / .030) * (1 - np.exp(-np.arange(k) / SR / .012)) * .0035 * v
        tr.add(t, th, 1.0, -.1)
        i = ns(t - t0)
        e = ns(.06)
        br[:, i:i + e] += bp(white(e, seed + 420 + q), 120, 1600, 1) * np.hanning(e) * .020 * v
    y = tr.x
    b = np.stack([conv(y[c], _SB['b'][c])[:n] for c in (0, 1)])
    w = np.stack([conv(y.mean(0) + br[c], _SB['s'][c])[:n] for c in (0, 1)])
    z = .80 * y + .34 * b + float(db(halo)) * w
    z = hp(z, 48, 2)
    z = eq(z, 240, 1.5, .8)
    if felt > .5:
        z = eq(z, 3200, -1.5, .7)
        z = eq(z, 7500, 4.0, .7, 'hs')
    mid, side = (z[0] + z[1]) / 2, (z[0] - z[1]) / 2
    z = np.stack([mid + .62 * side, mid - .62 * side])
    out.put('music', t0, z, gdb, room='stage', wet=wet, ep=ep)
    out.put('music', t0, z, gdb, room='room', wet=-13.0, ep=ep, dry=None)
