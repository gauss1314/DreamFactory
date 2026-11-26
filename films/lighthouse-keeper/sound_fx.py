"""Effects for The Lighthouse Keeper, each from its mechanism: sea, rain, thunder, bells, horns, flame, oil, cloth, iron.

All generators return mono or stereo float arrays starting at the sound's onset (t = 0 is the moment it begins).
"""
import numpy as np
from core import *
from inst import modes
import sfx as SX


def gate_times(t, avoid, pad=.16):
    """Drop event times that fall near any of `avoid` (absolute seconds) so textures never mask a cue's onset."""
    t = np.asarray(t, float)
    if not len(avoid) or not len(t):
        return t
    a = np.asarray(avoid, float)
    keep = np.all(np.abs(t[:, None] - a[None, :]) > pad, axis=1)
    return t[keep]


# ================================================================ sea
def sea(t0, t1, waves, seed, storm=0.0, bed=1.0):
    """Swell on rocks: a low bed plus one rush-and-wash per wave. waves [(t, size, pan)] absolute seconds. Stereo."""
    n = ns(t1 - t0)
    out = np.zeros((2, n))
    # the body of the ocean: low, slowly breathing
    z = np.stack([shaped(n, seed + k, [20, 40, 80, 160, 320, 700, 1500, 4000, 20000],
                         [-30, -6, 0, -2, -6, -12, -20, -30, -60]) for k in (0, 1)])
    z /= z.std() + 1e-12
    br = 1 + .35 * slow(n, .18, seed + 3) + .2 * slow(n, .6, seed + 4)
    out += z * br * .05 * bed * (1 + 1.6 * storm)
    r = rng(seed + 9)
    for q, (tw, s, p) in enumerate(waves):
        rise = r.uniform(.5, .9) * (1.2 - .4 * storm)
        dur = rise + r.uniform(2.2, 3.2) * (.7 + .3 * s)
        f_hi = 900 + 1600 * s + 1800 * storm
        y = SX.whoosh(dur, [(0, 220), (rise, f_hi), (rise + .6, f_hi * .55), (dur, 260)], .55,
                      [(0, 0), (rise * .8, .65), (rise, 1.0), (rise + .5, .55), (dur, 0)], p, seed * 31 + q, corr=.25, kind='lp', air=.35)
        # the wash: foam fizz trailing the break
        m = y.shape[1]
        fz = SX.crackle(dur, [(0, 0), (rise, 1800 * s), (rise + 1.2, 900 * s), (dur, 0)], seed * 37 + q, 'dust', width=.6, pan=p)
        y = y * .5 * s + fz[:, :m] * .9 * s
        i = ns(tw - t0)
        if i >= n:
            continue
        a, b = max(i, 0), min(i + m, n)
        out[:, a:b] += y[:, a - i:b - i]
    return out


def storm_sea(t0, t1, seed, level=1.0):
    """Heavy sea: rumble, roar and constant breaking."""
    n = ns(t1 - t0)
    z = np.stack([shaped(n, seed + k, [15, 30, 60, 120, 250, 500, 1000, 2000, 5000, 20000],
                         [-24, -4, 0, -1, -4, -8, -13, -19, -28, -55]) for k in (0, 1)])
    z /= z.std() + 1e-12
    e = 1 + .5 * slow(n, .35, seed + 5) + .3 * slow(n, 1.1, seed + 6)
    return z * np.clip(e, .2, 3) * .08 * level


def rain(t0, t1, seed, level=1.0, gust=None):
    """Rain on water and rock: a dense, even hiss of countless drops (never a single drop that stands out)."""
    n = ns(t1 - t0)
    z = np.stack([shaped(n, seed + k, [100, 300, 800, 2000, 5000, 9000, 14000, 20000],
                         [-40, -22, -12, -5, 0, -2, -8, -20]) for k in (0, 1)])
    z /= z.std() + 1e-12
    e = 1 + .18 * slow(n, .7, seed + 3) + .1 * slow(n, 3, seed + 4)
    if gust is not None:
        e = e * curve(gust, n, t0, kind='cos')
    c = SX.crackle(t1 - t0, 5000, seed + 7, 'dust', width=.9, tail=3.0, gcap=3.0)
    return (z * .03 + c[:, :n] * .25) * e * level


_GT = {}


def _glass_bank():
    if 'g' not in _GT:
        r = rng(4401)
        K, L = 48, 1400
        b = np.zeros((K, L))
        for k in range(K):
            f = np.exp(r.uniform(np.log(1800), np.log(7500), 5))
            x = modes(L, f, r.normal(0, 1, 5), r.uniform(.004, .014, 5), 4400 + k, att=.00008)
            x += r.normal(0, 1, L) * np.exp(-np.arange(L) / 30.0) * .3
            b[k] = x * fade(L, .0001, .005) / np.sqrt((x ** 2).sum())
        _GT['g'] = b
    return _GT['g']


def rain_glass(t0, t1, rate, seed, avoid=(), gain=.012, wash=1.0):
    """Drops tapping a window pane, and the water sheeting down it. rate: drops per second (scalar or [(t, v)] absolute)."""
    n = ns(t1 - t0)
    nk = int((t1 - t0) * 1000) + 1
    rc = np.full(nk, float(rate)) if np.isscalar(rate) else curve(rate, nk, t0, 1000)
    tt = SX.times(rc, seed) + t0
    tt = gate_times(tt, avoid, .2) - t0
    r = rng(seed + 1)
    out = np.zeros((2, n))
    g = np.minimum((1 - r.random(len(tt))) ** (-1 / 3.0), 4.0) * r.choice([-1, 1], len(tt))
    SX.scatter(out, _glass_bank(), tt * SR, g, np.clip(r.normal(0, .5, len(tt)), -1, 1), r.integers(0, 48, len(tt)),
               r.uniform(.8, 1.25, len(tt)))
    z = np.stack([shaped(n, seed + 5 + k, [200, 600, 1500, 3500, 8000, 20000], [-30, -16, -8, -6, -10, -30]) for k in (0, 1)])
    z /= z.std() + 1e-12
    return out * gain + z * .004 * wash * (1 + .2 * slow(n, 1.3, seed + 8))


# ================================================================ sky
def thunder(seed, near=1.0, dur=5.0):
    """Near: a ripping crack, then the roll. Far (near ~ 0): only the low roll with a soft onset."""
    r = rng(seed)
    n = ns(dur)
    t = np.arange(n) / SR
    out = np.zeros((2, n))
    # the roll: rumbling low noise, lumpy
    lump = np.clip(.6 + .5 * slow(n, 3.5, seed + 1) + .4 * slow(n, 9, seed + 2), 0, None) ** 1.5
    for ch in range(2):
        z = shaped(n, seed + 10 + ch, [12, 25, 50, 100, 200, 400, 1000, 3000, 20000], [-20, -3, 0, -2, -6, -12, -20, -32, -70])
        z /= z.std() + 1e-12
        att = (1 - np.exp(-t / (.012 + .25 * (1 - near))))
        env = att * np.exp(-t / (1.2 + .9 * (1 - near))) + .35 * att * np.exp(-t / 2.8)
        out[ch] = z * env * lump * .5
    if near > .2:
        # crack: a burst of discharge crackles over a broadband rip
        m = ns(.7)
        tm = np.arange(m) / SR
        z = SX.noise2(m, seed + 20, .5)
        rip = np.stack([svf(z[c], 9000 * np.exp(-tm / .12) + 600, .6, 'lp') for c in (0, 1)])
        rip *= (1 - np.exp(-tm / .0008)) * (np.exp(-tm / .045) + .25 * np.exp(-tm / .25))
        cr = SX.crackle(.7, [(0, 9000), (.08, 4000), (.3, 600), (.7, 0)], seed + 21, 'crease', width=.8, tail=2.2, gcap=6)
        cr = cr[:, :m] * np.exp(-tm / .2)
        k = rip * 1.8 + cr * 2.2
        out[:, :m] += k * near
        # the N wave of the nearest stroke: a hard low thump
        th = SX.subhit(.5, 90, 35, .05, .14, seed + 22, 2.0)
        out[:, :len(th)] += th * .5 * near
    return out * fade(n, .0003, .8)


def wave_crash(seed, size=1.0):
    """A big wave slams the rock: the impact boom, a slap of water, then spray falling back."""
    r = rng(seed)
    dur = 3.6
    n = ns(dur)
    t = np.arange(n) / SR
    out = np.zeros((2, n))
    boom = SX.subhit(1.6, 95, 32, .07, .42, seed + 1, 1.8)
    out[:, :len(boom)] += boom * .9
    z = SX.noise2(n, seed + 2, .4)
    slap = np.stack([svf(z[c], 3500 * np.exp(-t / .08) + 380 + 300 * np.exp(-t / .6), .7, 'lp') for c in (0, 1)])
    slap *= (1 - np.exp(-t / .0015)) * (np.exp(-t / .09) + .45 * np.exp(-t / .7))
    out += slap * 1.2
    sp = SX.crackle(dur, [(0, 0), (.06, 6000), (.6, 4500), (1.8, 1500), (dur, 0)], seed + 3, 'dust', width=1.0, tail=2.6)
    hiss = np.stack([bp(z[c], 2500, 11000, 1) for c in (0, 1)]) * curve([(0, 0), (.08, .9), (.7, .6), (2.0, .2), (dur, 0)], n)
    out += sp[:, :n] * .9 + hiss * .35
    return out * size * fade(n, .0002, .5)


# ================================================================ boat and buoy
def bell(seed, f0=392.0, vel=1.0, dur=6.0):
    """A bell buoy: a heavy bronze bell struck by a swinging clapper. Minor-third bell partials, long hum."""
    r = rng(seed)
    n = ns(dur)
    ra = np.array([.5, 1.0, 1.19, 1.5, 2.0, 2.51, 2.66, 3.01, 4.17, 5.43])
    a = np.array([.55, .8, .6, .35, 1.0, .5, .3, .35, .2, .12]) * db(r.normal(0, 1.5, 10))
    T = np.array([9, 5.5, 4.5, 3.5, 3.0, 2.0, 1.8, 1.4, .9, .6])
    f = f0 * ra
    x = modes(n, np.concatenate([f, f * 1.0016]), np.concatenate([a, a * .4]), np.concatenate([T, T * .9]), seed, att=.0008)
    q = ns(.03)
    x[:q] += bp(white(q, seed + 1), 1500, 7000, 1) * np.exp(-np.arange(q) / SR / .003) * .5
    return x / (np.abs(x).max() + 1e-9) * vel * fade(n, .0003, 1.5)


def horn(f0, dur, seed, rough=0.0, sag=0.0, release=.06, chord=(1.0,), atk=.03):
    """A ship's air horn: buzzing reeds into a flared pipe. rough adds a detuned second reed and flutter; sag bends down."""
    r = rng(seed)
    n = ns(dur + release + .05)
    t = np.arange(n) / SR
    env = smoothstep(t / atk) * (1 - smoothstep((t - dur) / release))
    env *= 1 + (.05 + .25 * rough) * slow(n, 7 + 10 * rough, seed + 1)
    out = np.zeros(n)
    for j, cr in enumerate(chord):
        reeds = [(0.0, 1.0)] + ([(-38 * rough / 1200, .8 * rough)] if rough else [])
        for d, g in reeds:
            f = f0 * cr * 2 ** d * (1 + .004 * slow(n, 3, seed + 3 + j) - sag * smoothstep((t - .05) / max(dur, .1)) * .06
                                    - .03 * np.exp(-t / .03))
            ph = 2 * np.pi * np.cumsum(f) / SR
            K = int(min(40, 9000 / (f0 * cr)))
            k = np.arange(1, K + 1)
            amp = 1 / k ** .9 * (1 + (k * f0 * cr / 1600) ** 2) ** -.7
            # a pipe resonance around 450-700 Hz gives the horn its vowel
            amp *= 1 + 1.8 * np.exp(-((np.log2(k * f0 * cr) - np.log2(560)) / .45) ** 2)
            y = np.zeros(n)
            for kk, aa in zip(k, amp):
                y += aa * np.sin(kk * ph + r.uniform(0, 6.28))
            out += y * g
    out += bp(white(n, seed + 9), 300, 3000, 1) * .05
    out *= env
    return out / (np.abs(out).max() + 1e-9) * fade(n, .0005, .01)


def hull_hit(seed, size=1.0):
    """A wave breaks over a wooden bow: the planks boom, water slaps and showers."""
    r = rng(seed)
    w = SX.jolt(seed, 1.0)
    out = np.zeros((2, ns(2.8)))
    out[:, :len(w)] += w * 1.3
    sp = wave_crash(seed + 5, .7)[:, :out.shape[1]]
    out[:, :sp.shape[1]] += sp * .8
    return out * size


# ================================================================ room, wood, iron
def window_bang(seed):
    """Latch bursts, the casement flies open and slams the wall: iron snap, wooden slam, glass shiver."""
    r = rng(seed)
    n = ns(1.4)
    t = np.arange(n) / SR
    out = np.zeros(n)
    snap = SX.clang(seed + 1, f0=1200, T=.12, vel=.35)
    out[:len(snap)] += snap
    j = SX.jolt(seed + 2, 1.0)
    out[:len(j)] += j * 1.5
    s2 = SX.slap(seed + 3, .9)
    o = ns(.012)
    out[o:o + len(s2)] += s2 * .9
    f, a, T = SX.metal_modes(seed + 4, f0=1400, K=40, hi=9000, T=.35)
    gl = modes(n, f, a, T, seed + 5, att=.0003)
    gl = gl / (np.abs(gl).max() + 1e-9) * (1 + .6 * np.sin(2 * np.pi * 31 * t)) * np.exp(-t / .25)
    o = ns(.02)
    out[o:] += gl[:n - o] * .22
    return out * fade(n, .0002, .1)


def latch(seed, vel=1.0):
    """An iron latch dropping into its keeper: two small hard clicks."""
    r = rng(seed)
    n = ns(.15)
    out = np.zeros(n)
    for q, (d, g) in enumerate(((0, 1.0), (r.uniform(.022, .034), .55))):
        m = ns(.05)
        f = np.exp(r.uniform(np.log(1800), np.log(7000), 6))
        x = modes(m, f, r.normal(0, 1, 6), r.uniform(.006, .02, 6), seed + q * 3, att=.00005)
        x /= np.abs(x).max() + 1e-9
        o = ns(d)
        out[o:o + m] += x[:n - o] * g
    return out * vel * fade(n, .0002, .02)


def thump(seed, f0=90, vel=1.0):
    """A body pushing a wooden frame home."""
    w = SX.jolt(seed, 1.0)
    n = len(w)
    t = np.arange(n) / SR
    b = SX.subhit(.4, f0 * 1.6, f0, .03, .09, seed + 1, 1.2)
    w[:len(b)] += b[:n] * .5
    return w * vel


def iron_step(seed, vel=.5):
    """A paw on an iron ladder rung: a dull clink and the pad."""
    r = rng(seed)
    n = ns(.5)
    f, a, T = SX.metal_modes(seed, f0=320, K=24, hi=6000, T=.25)
    x = modes(n, f, a, T, seed + 1, att=.0006)
    x /= np.abs(x).max() + 1e-9
    p = SX.paw(seed + 2, .8, 'wood', claws=True)
    y = x * .25 * np.exp(-np.arange(n) / SR / .12)
    y[:len(p)] += p * 1.4
    return y * vel * fade(n, .0003, .05)


def clank(seed, vel=1.0):
    """Hatch rim or rung struck firmly: a brighter clank."""
    f, a, T = SX.metal_modes(seed, f0=520, K=36, hi=8000, T=.4)
    n = ns(.9)
    x = modes(n, f, a, T, seed + 1, att=.0002)
    x /= np.abs(x).max() + 1e-9
    q = ns(.02)
    x[:q] += bp(white(q, seed + 2), 1500, 8000, 1) * np.exp(-np.arange(q) / SR / .002) * 1.2
    return x * vel * fade(n, .0002, .2)


# ================================================================ lamp, oil, glass
def gears(t0, t1, seed, period=.42, avoid=(), level=1.0):
    """The lens clockwork: a pawl ticking over a ratchet, and the gear train's low grumble."""
    n = ns(t1 - t0)
    r = rng(seed)
    tk = np.arange(t0 + r.uniform(0, period), t1, period)
    tk = tk + r.normal(0, .004, len(tk))
    tk = gate_times(tk, avoid, .18)
    out = np.zeros((2, n))
    for q, t in enumerate(tk):
        m = ns(.06)
        f = np.array([2300, 3450, 5100, 6900]) * r.uniform(.97, 1.03)
        x = modes(m, f, [1, .7, .5, .3], [.02, .015, .01, .007], seed + q, att=.0001)
        x2 = modes(m, f * .52, [1, .6, .3, .2], [.03, .02, .015, .01], seed + q + 999, att=.0003)
        y = x * .6 + x2 * .4
        i = ns(t - t0)
        e = min(n, i + m)
        out[:, i:e] += pan2(y[:e - i], .15) * r.uniform(.7, 1.0)
    z = SX.noise2(n, seed + 7, .6)
    hum = np.stack([bp(z[c], 70, 320, 2) for c in (0, 1)]) * (1 + .3 * np.sin(2 * np.pi * np.arange(n) / SR / period))
    return (out * .03 + hum * .02) * level


def wick(t0, t1, seed, level=1.0):
    """The lamp burning: a quiet soft roar and a fine hiss, very steady."""
    n = ns(t1 - t0)
    fl = SX.flame(t1 - t0, seed)[:, :n]
    z = SX.noise2(n, seed + 3, .7)
    hs = np.stack([bp(z[c], 2500, 9000, 1) for c in (0, 1)]) * (1 + .15 * slow(n, 6, seed + 4))
    return (fl * .6 + hs * .004) * level


def glug(seed, f0=420, vel=1.0):
    """One gulp of oil from a can spout: a bubble ringing up in pitch, and the can's hollow answer."""
    r = rng(seed)
    n = ns(.16)
    t = np.arange(n) / SR
    out = np.zeros(n)
    for q in range(r.integers(1, 3)):
        o = ns(r.uniform(0, .03)) if q else 0
        m = n - o
        tt = t[:m]
        f = f0 * r.uniform(.85, 1.2) * (1 + .7 * (1 - np.exp(-tt / .025)))
        ph = 2 * np.pi * np.cumsum(f) / SR
        y = np.sin(ph) * (1 - np.exp(-tt / .0008)) * np.exp(-tt / r.uniform(.022, .04))
        out[o:] += y * (1.0 if q == 0 else .5)
    can = modes(n, np.array([180, 310, 470, 720]) * r.uniform(.95, 1.05), [1, .6, .4, .2], [.05, .04, .03, .02], seed + 7, att=.001, phase=0)
    out += can * .35
    return out * vel * fade(n, .0002, .02)


def pour(dur, seed, rate=6.5):
    """A thin stream of oil into the trough with glugs from the spout."""
    n = ns(dur)
    t = np.arange(n) / SR
    z = white(n, seed)
    e = smoothstep(t / .08) * (1 - smoothstep((t - dur + .25) / .25))
    stream = svf(z, 900 + 300 * slow(n, 7, seed + 1), 1.4) * (1 + .5 * slow(n, 23, seed + 2)) * e * .05
    trick = SX.crackle(dur, [(0, 0), (.05, 600), (dur - .3, 500), (dur, 0)], seed + 3, 'thick', width=.2).mean(0)[:n] * .5
    out = stream + trick
    r = rng(seed + 4)
    tg = 0.0
    q = 0
    while tg < dur - .3:
        g = glug(seed + 10 + q, r.uniform(360, 520), 1.0 if q == 0 else r.uniform(.4, .75))
        i = ns(tg)
        m = min(len(g), n - i)
        out[i:i + m] += g[:m]
        tg += r.uniform(.6, 1.4) / rate
        q += 1
    return out


def wipe(strokes, seed):
    """Wool scarf on glass: rubs (each a soft contact, rasp and faint squeak) and two pats. strokes [(t, dur)] local."""
    end = max(a + b for a, b in strokes) + .3
    n = ns(end)
    out = np.zeros(n)
    r = rng(seed)
    for q, (t0, d) in enumerate(strokes):
        m = ns(d + .1)
        tt = np.arange(m) / SR
        u = np.clip(tt / d, 0, 1)
        sp = np.sin(np.pi * u) ** .7 * (u < 1)
        z = white(m, seed + q * 5)
        rub = svf(z, 1400 + 2600 * sp, .9) * sp * (1 + .4 * slow(m, 25, seed + q * 5 + 1)) * .25
        sq = SX.squeak(seed + q * 5 + 2, r.uniform(2100, 2700), d * .8, .08)
        y = rub
        y[:len(sq)] += sq * 1.5
        # the touch of the cloth: a soft glassy tock
        c = ns(.03)
        tok = modes(c, np.array([1650, 2480, 3900]) * r.uniform(.95, 1.05), [1, .6, .3], [.012, .009, .006], seed + q * 5 + 3, att=.0001, phase=0)
        tok += bp(white(c, seed + q * 5 + 4), 1500, 6000, 1) * np.exp(-np.arange(c) / SR / .003) * .5
        y[:c] += tok * (1.0 if q == 0 else .5)
        i = ns(t0)
        e = min(n, i + m)
        out[i:e] += y[:e - i]
    return out * fade(n, .0002, .05)


def pat(seed, vel=1.0):
    """A paw patting the glass through cloth."""
    n = ns(.12)
    t = np.arange(n) / SR
    x = lp(white(n, seed), 500, 2) * np.exp(-t / .012) * (1 - np.exp(-t / .001)) * 1.5
    x += modes(n, np.array([1300, 2100, 3300]), [1, .5, .25], [.02, .015, .01], seed + 1, att=.0004, phase=0) * .25
    return x * vel


def match_strike(seed):
    """Match head dragged on the striker: a short rasp, the flare blooming, the little flame settling."""
    r = rng(seed)
    n = ns(1.6)
    t = np.arange(n) / SR
    out = np.zeros(n)
    m = ns(.09)
    tm = np.arange(m) / SR
    rasp = poisson_env(np.full(m, 7000.0), .0004, .00004, seed, 1.6) * hp(white(m, seed + 1), 1800, 2)
    rasp *= (1 - np.exp(-tm / .001)) * (1 - smoothstep((tm - .06) / .03)) * .35
    rasp[:ns(.004)] += hp(white(ns(.004), seed + 2), 2000, 1) * 1.2
    out[:m] += rasp
    o = ns(.05)
    k = n - o
    tk = t[:k]
    fl = svf(white(k, seed + 3), 1200 + 3500 * np.exp(-tk / .12), .7) * (1 - np.exp(-tk / .008)) * (np.exp(-tk / .12) + .1)
    fl += SX.crackle(k / SR, [(0, 1500), (.2, 300), (k / SR, 40)], seed + 4, 'thin', width=.2).mean(0)[:k] * .6
    out[o:] += fl * .5
    lo = lp(white(n, seed + 5), 300, 2) * (1 - np.exp(-t / .02)) * np.exp(-t / .3) * .4
    out += lo
    return out * fade(n, .0002, .2)


def poisson_env(rate, dec, atk, seed, tail):
    return SX.poisson_env(rate, dec, atk, seed, tail)


def flame_catch(seed):
    """The wick takes the flame: a soft whump of air, then the steady burn arrives."""
    w = SX.whoomph(seed, 1.0, 1.4)
    n = w.shape[1]
    t = np.arange(n) / SR
    z = SX.noise2(n, seed + 1, .7)
    hs = np.stack([bp(z[c], 1200, 6000, 1) for c in (0, 1)]) * (1 - np.exp(-t / .03)) * (.3 + .7 * np.exp(-t / .3)) * .05
    th = SX.subhit(.35, 160, 70, .03, .07, seed + 2, 1.2) * .25
    out = w + hs
    out[:, :len(th)] += th
    # the leading edge: a quick puff so the catch reads on the beat
    m = ns(.03)
    out[:, :m] += lp(white(m, seed + 3), 600, 2) * np.exp(-np.arange(m) / SR / .006) * .8
    return out


def flame_puff(seed, size=1.0):
    """The flame's last breath: a short low 'pff' as it tears off the wick."""
    n = ns(.5)
    t = np.arange(n) / SR
    z = white(n, seed)
    y = svf(z, 260 + 900 * np.exp(-t / .03), .8, 'lp') * (1 - np.exp(-t / .0012)) * (np.exp(-t / .055) + .12 * np.exp(-t / .2))
    th = SX.subhit(.3, 170, 80, .02, .05, seed + 1, 1.0)
    y[:len(th)] += th * .35
    return y * size * fade(n, .0002, .1)


# ================================================================ birds
def gull(seed, f0=1500, vel=1.0, calls=3):
    """Herring gull: nasal 'kyow' calls, each a fast upward then long falling glide, rough at the top."""
    r = rng(seed)
    gap = r.uniform(.24, .34)
    n = ns(calls * gap + .5)
    out = np.zeros(n)
    for c in range(calls):
        d = r.uniform(.2, .32)
        m = ns(d)
        t = np.arange(m) / SR
        u = t / d
        fc = f0 * r.uniform(.92, 1.08) * (1 + .45 * np.sin(np.pi * np.clip(u / .35, 0, 1) * .5) - .55 * np.clip((u - .3) / .7, 0, 1) ** 1.2)
        fc *= 1 + .015 * np.sin(2 * np.pi * 70 * t)
        ph = 2 * np.pi * np.cumsum(fc) / SR
        y = np.zeros(m)
        for k, a in ((1, 1), (2, .8), (3, .5), (4, .35), (5, .2), (6, .1)):
            y += a * np.sin(k * ph + k)
        y *= 1 + .5 * np.sin(2 * np.pi * 55 * t)
        e = smoothstep(u / .12) * (1 - smoothstep((u - .6) / .4))
        y = bp(y * e, 900, 6000, 1)
        i = ns(c * gap * r.uniform(.85, 1.15))
        out[i:i + m] += y[:n - i] * r.uniform(.6, 1.0)
    return out / (np.abs(out).max() + 1e-9) * vel * fade(n, .002, .05)


def lap(seed, size=1.0):
    """A small wave laps the shore below: a quick splash, a fizz of foam, the draw back over pebbles."""
    r = rng(seed)
    dur = 2.4
    n = ns(dur)
    t = np.arange(n) / SR
    z = SX.noise2(n, seed, .3)
    s = np.stack([svf(z[c], 700 + 1400 * np.exp(-t / .12), .8) for c in (0, 1)])
    s *= (1 - np.exp(-t / .004)) * (np.exp(-t / .12) + .35 * np.exp(-t / .6))
    fz = SX.crackle(dur, [(0, 0), (.03, 2500), (.5, 1200), (1.6, 300), (dur, 0)], seed + 1, 'dust', width=.6)[:, :n]
    pb = SX.crackle(dur, [(0, 0), (.9, 0), (1.3, 200), (2.1, 60), (dur, 0)], seed + 2, 'thick', width=.8)[:, :n]
    return (s * .9 + fz * .5 + pb * .35) * size * fade(n, .0002, .4)
