"""Sound effects, each from its mechanism: grains, flaps, stick-slip, bristles, struck wood and copper, moving air."""
import numpy as np
import numba as nb
from core import *
from inst import modes, min_phase


# ================================================================ grain engines
@nb.njit(cache=True)
def poisson_env(rate, dec, atk, seed, tail):
    """Heavy-tailed impulses at `rate` per second through a fast-attack / exponential-decay follower."""
    np.random.seed(seed)
    n = len(rate)
    out = np.empty(n)
    g = np.exp(-1 / (dec * 48000.0))
    ga = 1 - np.exp(-1 / (atk * 48000.0))
    s = 0.0
    y = 0.0
    for i in range(n):
        if np.random.random() < rate[i] / 48000.0:
            s += min((1 - np.random.random()) ** (-1.0 / tail), 12.0)
        s *= g
        y += (s - y) * ga
        out[i] = y
    return out


@nb.njit(cache=True)
def scatter(out, bank, t, g, pan, idx, rate):
    """Add bank[idx] (mono protos) at sample times with gain, pan and resampling rate."""
    L = bank.shape[1]
    n = out.shape[1]
    for k in range(len(t)):
        a = (pan[k] + 1) * 0.7853981
        gl, gr = g[k] * np.cos(a) * 1.4142, g[k] * np.sin(a) * 1.4142
        x = 0.0
        i = int(t[k])
        b = idx[k]
        r = rate[k]
        while x < L - 1:
            if i >= n:
                break
            j = int(x)
            v = bank[b, j] + (bank[b, j + 1] - bank[b, j]) * (x - j)
            if i >= 0:
                out[0, i] += gl * v
                out[1, i] += gr * v
            i += 1
            x += r


def times(rate, seed, rate_hz=1000):
    """Poisson event times (samples) for a rate curve sampled at rate_hz."""
    r = rng(seed)
    k = r.poisson(np.maximum(rate, 0) / rate_hz)
    t = np.repeat(np.arange(len(rate)), k) / rate_hz + r.uniform(0, 1 / rate_hz, k.sum())
    return np.sort(t)


def _crackle_bank(seed, lo, hi, t_lo, t_hi, K=64, L=720, nmode=(4, 9)):
    r = rng(seed)
    out = np.zeros((K, L))
    for b in range(K):
        k = r.integers(*nmode)
        f = np.exp(r.uniform(np.log(lo), np.log(hi), k))
        a = r.normal(0, 1, k) * (f / lo) ** -.35
        T = np.interp(np.log(f), [np.log(lo), np.log(hi)], [t_lo, t_hi]) * r.uniform(.5, 1.6, k)
        x = modes(L, f, a, T, seed * 100 + b, att=.00006)
        c = int(r.uniform(6, 30))
        x[:c] += r.normal(0, 1, c) * np.linspace(1, 0, c) * r.uniform(.2, 1.0)
        x *= fade(L, .0001, .004)
        out[b] = x / np.sqrt((x ** 2).sum())
    return out


_BK = {}


def bank(kind):
    if kind not in _BK:
        _BK[kind] = dict(
            thin=lambda: _crackle_bank(1, 1300, 9500, .006, .0016),
            thick=lambda: _crackle_bank(2, 420, 5200, .014, .003, L=960),
            crease=lambda: _crackle_bank(3, 1800, 12000, .005, .0012),
            dust=lambda: _crackle_bank(4, 4200, 14000, .0016, .0008, L=200),
            leather=lambda: _crackle_bank(5, 240, 2400, .026, .006, L=2400),
            grass=lambda: _crackle_bank(6, 2600, 11000, .004, .0016, L=420))[kind]()
    return _BK[kind]


def crackle(dur, rate, seed, kind='thin', tail=1.7, pan=0.0, width=.5, gcap=9.0, rr=(.7, 1.5), gain=None):
    """Poisson crackle cloud. rate: scalar or [(t,v)] (per second). Returns stereo."""
    n = ns(dur)
    nk = int(dur * 1000) + 1
    rc = np.full(nk, float(rate)) if np.isscalar(rate) else curve(rate, nk, 0, 1000)
    t = times(rc, seed)
    r = rng(seed + 5)
    g = np.minimum((1 - r.random(len(t))) ** (-1 / tail), gcap) * r.choice([-1, 1], len(t))
    if gain is not None:
        g *= np.interp(t, [p[0] for p in gain], [p[1] for p in gain])
    pc = np.full(len(t), float(pan)) if np.isscalar(pan) else np.interp(t, [p[0] for p in pan], [p[1] for p in pan])
    out = np.zeros((2, n))
    scatter(out, bank(kind), t * SR, g, np.clip(pc + r.normal(0, width * .5, len(t)), -1, 1),
            r.integers(0, 64, len(t)), np.exp(r.uniform(np.log(rr[0]), np.log(rr[1]), len(t))))
    return out * .1


def noise2(n, seed, corr=.3):
    a, b, c = white(n, seed), white(n, seed + 1), white(n, seed + 2)
    k, q = np.sqrt(corr), np.sqrt(1 - corr)
    return np.stack([k * c + q * a, k * c + q * b])


# ================================================================ air
WB = ((48, 120, .75, -4, .55), (105, 330, 1.0, -1, .42), (330, 950, 1.3, -5.5, .30), (950, 2900, 1.65, -13, .22), (2900, 9500, 2.1, -22, .12))


def wind(t0, t1, gust, seed, tilt=0.0, whistle=0.0, wf=(520, 900), low=0.0):
    """gust: breakpoints 0..1 (abs time). Five bands whose loudness follows the gust with rising exponents, a travelling
    stereo image and an optional window whistle."""
    n = ns(t1 - t0)
    cr = 400
    m = int((t1 - t0) * cr) + 2
    g = np.clip(curve(gust, m, t0, cr, 'cos'), 0, 1.4)
    g = g * (1 + .30 * slow(m, .55, seed, cr) + .18 * slow(m, 1.7, seed + 1, cr) + .10 * slow(m, 4.2, seed + 2, cr))
    g = np.clip(g, 0, None)
    tc = np.arange(m) / cr
    ts = np.arange(n) / SR
    out = np.zeros((2, n))
    for b, (lo, hi, ex, dbg, cor) in enumerate(WB):
        z = noise2(n, seed * 17 + b * 5, cor)
        z = np.stack([bp(z[0], lo, hi, 2), bp(z[1], lo, hi, 2)])
        z /= z.std()
        for ch in range(2):
            lag = (.09 + .05 * b) * (1 if ch else -1) * .5
            e = np.interp(tc - lag, tc, g) ** ex
            e = e * (1 + .25 * slow(m, 2 + 2.5 * b, seed * 19 + b * 3 + ch, cr) + .12 * slow(m, 9 + 4 * b, seed * 23 + b * 3 + ch, cr))
            z[ch] *= np.interp(ts, tc, np.maximum(e, 0))
        out += z * db(dbg + tilt * (b - 2) + (low if b < 1 else 0))
    if whistle:
        for k in range(2):
            f = wf[0] + (wf[1] - wf[0]) * np.clip(np.interp(ts, tc, g), 0, 1.2) + 40 * np.interp(ts, tc, slow(m, 1.2, seed + 40 + k, cr))
            f = f * (1.0 if k == 0 else 1.493)
            w = svf(white(n, seed + 50 + k), f, 26)
            w *= np.interp(ts, tc, np.clip(g, 0, 1.5) ** 2.6) * (1 + .5 * np.interp(ts, tc, slow(m, 2.2, seed + 60 + k, cr)))
            out += pan2(w, -.35 + .6 * k) * whistle * (.9 if k == 0 else .35)
    return out * .1


def grass(t0, t1, gust, seed, dens=2200, g=1.0):
    """Pampas hiss: thousands of dry blade contacts whose rate follows the gust, over a soft feather hiss."""
    dur = t1 - t0
    nk = int(dur * 1000) + 1
    gc = np.clip(curve(gust, nk, t0, 1000, 'cos') * (1 + .35 * slow(nk, .8, seed, 1000) + .25 * slow(nk, 2.6, seed + 1, 1000)), 0, 1.5)
    n = ns(dur)
    t = times(dens * gc ** 1.6, seed + 2)
    r = rng(seed + 3)
    out = np.zeros((2, n))
    ph = np.interp(t, np.arange(nk) / 1000, slow(nk, .5, seed + 4, 1000))
    scatter(out, bank('grass'), t * SR, np.minimum((1 - r.random(len(t))) ** (-1 / 2.2), 5) * r.choice([-1, 1], len(t)),
            np.clip(ph * .6 + r.normal(0, .5, len(t)), -1, 1), r.integers(0, 64, len(t)), r.uniform(.6, 1.25, len(t)))
    ts = np.arange(n) / SR
    z = noise2(n, seed + 9, .1)
    for ch in range(2):
        e = np.interp(ts - .05 * ch, np.arange(nk) / 1000, gc ** 1.9)
        z[ch] = svf(z[ch], 3300 + 2600 * np.clip(e, 0, 1.2), .55) * e
        z[ch] *= 1 + .35 * slow(n, 14, seed + 12 + ch)
    return (out * .012 + hp(z, 1200, 1) * .030) * g


def whoosh(dur, fc, q, amp, pan, seed, corr=.35, kind='bp', air=.25):
    """Moving air: breakpoints over local time. fc in Hz, amp linear, pan -1..1."""
    n = ns(dur)
    z = noise2(n, seed, corr)
    f = np.exp(curve([(t, np.log(v)) for t, v in fc], n))
    qq = np.full(n, float(q)) if np.isscalar(q) else curve(q, n)
    a = curve(amp, n, kind='cos')
    p = curve(pan, n, kind='cos') if not np.isscalar(pan) else np.full(n, float(pan))
    out = np.zeros((2, n))
    for ch in range(2):
        y = svf(z[ch], f * (1 + .05 * slow(n, 5, seed + 11 + ch)), qq, kind)
        y = y + air * svf(z[ch], np.minimum(f * 3.1, 14000), .7)
        y *= 1 + .22 * slow(n, 9, seed + 21 + ch) + .12 * slow(n, 27, seed + 31 + ch)
        out[ch] = y * a
    th = (p + 1) * np.pi / 4
    return out * np.stack([np.cos(th), np.sin(th)]) * 1.4142 * fade(n, .004, .02)


# ================================================================ steps, lantern, breath
def paw(seed, vel=.5, surf='wood', claws=True):
    r = rng(seed)
    n = ns(.28)
    t = np.arange(n) / SR
    k = r.uniform(.9, 1.12)
    if surf == 'wood':
        x = modes(n, np.array([78, 112, 163, 221, 305, 410, 585]) * k, np.array([.6, 1, .85, .6, .4, .22, .12]) * db(r.normal(0, 2, 7)),
                  np.array([.10, .12, .09, .07, .055, .04, .03]), seed, att=.0028, phase=0) * .30
        pad = bp(white(n, seed + 1), 180, 1300, 1) * np.exp(-t / .013) * (1 - np.exp(-t / .004)) * .22
    elif surf == 'paper':
        x = modes(n, np.array([68, 95, 140, 210, 320]) * k, np.array([.8, 1, .6, .3, .12]), np.array([.07, .07, .05, .04, .03]), seed, att=.004, phase=0) * .26
        pad = bp(white(n, seed + 1), 260, 2600, 1) * np.exp(-t / .022) * (1 - np.exp(-t / .005)) * .18
        cr = crackle(.28, [(0, 900), (.05, 300), (.2, 0)], seed + 3, 'thick', width=.1).mean(0)
        pad = pad + cr * np.exp(-t / .06) * .9
    else:
        x = modes(n, np.array([95, 150, 240]) * k, np.array([1, .6, .3]), np.array([.05, .04, .03]), seed, att=.003, phase=0) * .2
        pad = bp(white(n, seed + 1), 220, 1700, 1) * np.exp(-t / .012) * (1 - np.exp(-t / .004)) * .2
    y = x + pad
    # toes roll: a second, fainter contact
    d = ns(r.uniform(.018, .03))
    y[d:] += .28 * pad[:-d]
    if claws:
        for q in range(r.integers(1, 4)):
            m = ns(.02)
            o = ns(r.uniform(.004, .032))
            tick = modes(m, np.exp(r.uniform(np.log(2300), np.log(7600), 4)), r.normal(0, 1, 4), r.uniform(.004, .010, 4), seed + 9 + q, att=.0001)
            y[o:o + m] += tick * .022 * r.uniform(.4, 1.3) * (1 if surf == 'wood' else .25)
    return y * vel ** 1.2 * fade(n, .0005, .03)


def stickslip(dur, rate, modef, modea, modet, seed, jitter=.25, gain=None, tilt=0.0):
    """Friction creak: irregular slips ringing a resonant body. rate = slips per second breakpoints."""
    n = ns(dur)
    r = rng(seed)
    rc = curve(rate, n)
    wob = 1 + .35 * slow(n, 4.0, seed + 1) + .2 * slow(n, 11, seed + 2)
    ph = np.cumsum(rc * wob) / SR
    k = np.diff(np.floor(ph), prepend=0) > 0
    idx = np.flatnonzero(k)
    idx = np.clip(idx + (r.normal(0, jitter, len(idx)) * SR / np.maximum(rc[idx], 1)).astype(int) * 1, 0, n - 1)
    imp = np.zeros(n)
    g = r.uniform(.25, 1.0, len(idx)) ** 1.5 * np.minimum((40 / np.maximum(rc[idx], 5)) ** .5, 2.2) * r.choice([1, 1, 1, -1], len(idx))
    if gain is not None:
        g *= np.interp(idx / SR, [p[0] for p in gain], [p[1] for p in gain])
    np.add.at(imp, idx, g)
    # each slip is a short scrape, not a delta
    s = ns(.0035)
    scr = r.normal(0, 1, s) * np.exp(-np.arange(s) / (s / 4.0))
    scr[0] += 2
    L = ns(max(modet) * 1.1 + .02)
    h = modes(L, modef, modea, modet, seed + 3, att=.0003) * fade(L, 0, .03)
    y = conv(imp, scr)[:n]
    y = conv(y, h)
    return y / max(np.abs(y).max(), 1e-9) * fade(len(y), .003, .05)


def wood_modes(seed, f0=70, K=34, hi=4200, T=.16):
    r = rng(seed)
    f = np.exp(np.sort(r.uniform(np.log(f0), np.log(hi), K)))
    a = r.normal(0, 1, K) * (f / f0) ** -.45
    t = T * (f / 200) ** -.45 * r.uniform(.6, 1.4, K)
    return f, a, np.clip(t, .006, .5)


def squeak(seed, f0=1900, dur=.15, up=.12):
    """Small iron handle on its pin."""
    r = rng(seed)
    n = ns(dur)
    t = np.arange(n) / SR
    f = f0 * (1 + up * np.sin(np.pi * t / dur) + .02 * slow(n, 30, seed))
    buzz = 1 + .55 * np.sin(2 * np.pi * np.cumsum(95 + 25 * slow(n, 12, seed + 1)) / SR)
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(ph) + .35 * np.sin(2.02 * ph + 1) + .18 * np.sin(3.1 * ph)
    e = np.sin(np.pi * t / dur) ** 1.5 * (1 + .4 * slow(n, 22, seed + 2))
    return (y * buzz * e + .2 * bp(white(n, seed + 3), f0 * .8, f0 * 2.4, 1) * e) * .02


def lantern_down(seed):
    n = ns(.5)
    x = modes(n, np.array([142, 236, 388, 520, 760, 1180, 1730]), [.7, 1, .7, .5, .3, .18, .1], [.11, .10, .08, .06, .05, .035, .02], seed, att=.0012, phase=0) * .30
    t = np.arange(n) / SR
    x += bp(white(n, seed + 1), 500, 3000, 1) * np.exp(-t / .006) * .07
    # second foot of the base, then the handle falls and rings a little
    for d, g in ((.052, .42), (.097, .15)):
        o = ns(d)
        x[o:] += g * x[:-o]
    h = modes(n, np.array([1480, 2213, 3071, 4390, 5820]), [.6, 1, .6, .4, .2], [.16, .20, .13, .09, .06], seed + 2, att=.0002)
    o = ns(.155)
    x[o:] += h[:-o] * .05
    o = ns(.215)
    x[o:] += h[:-o] * .022
    return x * fade(n, .0002, .1)


def flame(dur, seed, lean=None):
    n = ns(dur)
    L = curve(lean, n, kind='cos') if lean else np.zeros(n)
    z = noise2(n, seed, .6)
    am = np.clip(.5 + .5 * slow(n, 9, seed + 4) + .4 * slow(n, 17, seed + 5), 0, 2)
    lo = np.stack([bp(z[0], 45, 260, 1), bp(z[1], 45, 260, 1)]) * (am ** 2) * (.25 + 1.6 * L)
    mid = np.stack([bp(z[0], 260, 1400, 1), bp(z[1], 260, 1400, 1)]) * am * (.05 + .35 * L)
    flap = np.clip(slow(n, 13, seed + 6) + .2, 0, 1) ** 2 * L
    lo = lo + np.stack([bp(z[0], 70, 420, 2)] * 2) * flap * 2.2
    c = crackle(dur, 3.0, seed + 7, 'thin', tail=2.0, width=.2) * .35
    return (lo * .5 + mid * .5) * .1 + c * .25


def sniff(seed, vel=1.0):
    n = ns(.11)
    t = np.arange(n) / SR
    e = smoothstep(t / .022) * np.exp(-np.maximum(t - .03, 0) / .020)
    z = white(n, seed)
    f = 2100 + 2600 * np.clip(t / .07, 0, 1)
    y = svf(z, f, 1.3) + .45 * svf(z, np.full(n, 5600.0), 1.0) + .3 * svf(z, np.full(n, 900.0), 1.5)
    return y * e * .10 * vel * fade(n, .002, .02)


def fur(dur, seed, f=2600, vel=1.0):
    """Ear or tail: soft brushed air with a little hair grain."""
    n = ns(dur)
    t = np.arange(n) / SR
    e = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 2
    z = white(n, seed)
    y = svf(z, f * (.7 + .6 * e), .7) * e * (1 + .6 * slow(n, 40, seed + 1))
    y += lp(white(n, seed + 2), 350, 1) * e * .5
    return y * .05 * vel


# ================================================================ paper
def page_proto(seed, dur=.9, flut=16.0, big=0.0):
    """One sheet fluttering: flap pulses, each a spread of stiff-paper crackle over a thrum of moved air."""
    r = rng(seed)
    n = ns(dur)
    t = np.arange(n) / SR
    f = flut * (1 + .22 * slow(n, 3.5, seed + 1) + .12 * slow(n, 9, seed + 2))
    ph = np.cumsum(f) / SR + r.uniform()
    fr = ph % 1
    cyc = np.floor(ph).astype(int)
    ga = r.uniform(.35, 1.0, cyc.max() + 2)[cyc]
    sharp = r.uniform(.05, .11)
    pulse = (1 - np.exp(-fr / sharp)) * np.exp(-fr / r.uniform(.16, .30)) * ga
    life = np.sin(np.pi * np.clip(t / dur, 0, 1) ** r.uniform(.6, 1.1)) ** 1.2
    lo, hi = r.uniform(420, 1300) * (1 - .55 * big), np.exp(r.uniform(np.log(2200), np.log(6800))) * (1 - .4 * big)
    z = white(n, seed + 3)
    body = bp(z, lo, hi, 1)
    res = svf(z, np.full(n, r.uniform(900, 3600)), r.uniform(2, 5))
    y = (body * .8 + res * 1.2) * pulse
    thr = bp(white(n, seed + 4), 90, 420, 1) * pulse * (1.5 + 2 * big)
    cr = lp(poisson_env(pulse * life * r.uniform(1500, 4200), .0007, .00008, seed + 5, 1.8) * hp(z, 1500, 1), 8500, 1)
    y = (y * .62 + thr * .6 + cr * .17) * life
    y = y / (np.sqrt((y ** 2).mean()) + 1e-9)
    return np.tanh(y / 5.5) * 5.5 * fade(n, .003, .03)


_PP = {}


def page_bank(K=44, big=0.0, seed=700):
    key = (K, big, seed)
    if key not in _PP:
        r = rng(seed)
        L = ns(1.0)
        out = np.zeros((K, L))
        for k in range(K):
            d = r.uniform(.35, .98)
            p = page_proto(seed + k * 11, d, r.uniform(7, 30), big)
            out[k, :len(p)] = p
        _PP[key] = out
    return _PP[key]


def flock(t0, t1, rate, gain, seed, pan=None, width=.8, speed=(.75, 1.4), big=0.0, sg=.75):
    """Crowd of fluttering sheets. rate/gain/pan are absolute-time breakpoints; pan may be a callable(t)->centre."""
    dur = t1 - t0
    nk = int(dur * 1000) + 1
    t = times(curve(rate, nk, t0, 1000), seed)
    r = rng(seed + 1)
    g = np.exp(r.normal(0, sg, len(t))) * curve(gain, nk, t0, 1000)[np.minimum((t * 1000).astype(int), nk - 1)]
    pc = np.zeros(len(t)) if pan is None else (pan(t + t0) if callable(pan) else np.interp(t + t0, [p[0] for p in pan], [p[1] for p in pan]))
    out = np.zeros((2, ns(dur) + ns(1.5)))
    wd = width(t + t0) if callable(width) else width
    scatter(out, page_bank(big=big), t * SR, g * r.choice([-1, 1], len(t)), np.clip(pc + r.normal(0, 1, len(t)) * wd * .5, -1, 1),
            r.integers(0, 44, len(t)), np.exp(r.uniform(np.log(speed[0]), np.log(speed[1]), len(t))))
    return out * .02


def slap(seed, weight=.5):
    """A book cover thrown open against its neighbour."""
    r = rng(seed)
    n = ns(.34)
    t = np.arange(n) / SR
    k = r.uniform(.8, 1.3) * (1.35 - .7 * weight)
    x = modes(n, np.array([92, 148, 232, 355, 540, 830, 1300]) * k, np.array([.9, 1, .9, .7, .5, .35, .2]) * db(r.normal(0, 3, 7)),
              np.array([.12, .11, .08, .06, .045, .03, .02]), seed, att=.0008, phase=0) * .5
    x += bp(white(n, seed + 1), 400, 6500, 1) * np.exp(-t / .008) * .35
    x += lp(white(n, seed + 2), 700, 1) * np.exp(-t / .020) * .5
    return x * fade(n, .0002, .06)


def snap(seed, size=.5):
    """Sharp fold: a crackling slide into a hard crease, double transient."""
    r = rng(seed)
    n = ns(.16)
    t = np.arange(n) / SR
    pre = ns(.030)
    z = white(n, seed)
    run = np.clip(t / .030, 0, 1) ** 3 * (t < .030)
    ch = poisson_env(np.where(t < .030, 900 + 5000 * run, 40), .0005, .00005, seed + 1, 1.8) * hp(z, 1500, 1) * .10
    y = ch * (run + .05)
    k = r.uniform(.8, 1.35) * (1.25 - .5 * size)
    for d, g in ((0, 1.0), (r.uniform(.006, .013), .5 * r.uniform(.5, 1)), (r.uniform(.018, .028), .22)):
        o = pre + ns(d)
        m = n - o
        tt = np.arange(m) / SR
        b = modes(m, np.array([780, 1250, 1900, 2750, 3900, 5400, 7600]) * k, np.array([.5, .8, 1, .9, .7, .5, .35]) * r.normal(0, 1, 7),
                  np.array([.020, .018, .014, .011, .009, .007, .005]), seed + 7 + int(d * 1e5), att=.0001) * .55
        b += hp(white(m, seed + 8 + int(d * 1e5)), 1100, 1) * np.exp(-tt / .0032) * .75
        b += bp(white(m, seed + 9), 240, 900, 1) * np.exp(-tt / .012) * .5 * size
        y[o:] += g * b
    return y * fade(n, .001, .03), .030


def flap(seed, size=.2, vel=1.0, up=False):
    """One wing stroke of a paper bird."""
    r = rng(seed)
    d = .10 + .16 * size
    n = ns(d * 2.4)
    t = np.arange(n) / SR
    e = (1 - np.exp(-t / (.012 + .02 * size))) * np.exp(-t / (d * .42))
    z = white(n, seed)
    y = svf(z, (1500 - 800 * size) * np.exp(-t / (d * 1.2)) + 260, .7, 'lp') * 1.5 * e
    y += bp(z, 900, 6000, 1) * e ** 2 * .35
    cr = poisson_env(3800 * e ** 2 + 30, .0008, .00008, seed + 3, 1.7) * hp(z, 1600, 1) * .16
    y += cr * e
    p = ns(.02)
    y[:p] += bp(white(p, seed + 5), 500, 5000, 1) * np.exp(-np.arange(p) / SR / .003) * .35
    return y * vel * (.45 if up else 1.0) * .25 * fade(n, .001, .03)


def rustle(dur, seed, amt=1.0, kind='thin', shape=None):
    n = ns(dur)
    t = np.arange(n) / SR
    sh = shape or [(0, 0), (dur * .3, 1), (dur * .6, .5), (dur, 0)]
    e = curve(sh, n, kind='cos') * np.clip(.6 + .7 * slow(n, 9, seed), 0, 2)
    c = crackle(dur, [(a, 2600 * b) for a, b in sh], seed + 1, kind, width=.25)
    z = noise2(n, seed + 2, .5)
    h = np.stack([bp(z[0], 900, 7000, 1), bp(z[1], 900, 7000, 1)]) * e * .035
    return (c * .55 + h) * amt


def brush(strokes, seed, size=1.0, t1=None):
    """Wet bristles on tooth: strokes [(t, dur, press, pan0, pan1)] local times."""
    end = max(s[0] + s[1] for s in strokes) + .25
    n = ns(end)
    out = np.zeros((2, n))
    for q, (t0, d, pr, p0, p1) in enumerate(strokes):
        m = ns(d + .12)
        t = np.arange(m) / SR
        u = np.clip(t / d, 0, 1)
        r = rng(seed + q * 7)
        sp = np.sin(np.pi * u ** r.uniform(.6, .95)) ** .8 * (1 + .25 * slow(m, 7, seed + q * 7 + 1))
        sp = np.clip(sp, 0, None) * (u < 1)
        sp = lp(sp, 30, 1)
        z = white(m, seed + q * 7 + 2)
        bris = poisson_env(400 + 2600 * sp, .0016, .0002, seed + q * 7 + 3, 2.4)
        bris = bris / (bris.mean() + 1e-9)
        fric = svf(z, (850 + 2300 * sp) * size ** -.4, .8) * (.45 + .55 * bris) * sp ** 1.15
        tooth = bp(z, 3000, 9000, 1) * poisson_env(200 + 1500 * sp, .0006, .00008, seed + q * 7 + 4, 1.8) * sp * .030
        wet = svf(white(m, seed + q * 7 + 5), 420 + 380 * sp + 120 * slow(m, 11, seed + q * 7 + 6), 2.2) * sp ** .7 * .55 * pr
        # contact: the loaded tip touches
        c = ns(.05)
        tc = np.arange(c) / SR
        con = modes(c, np.array([210, 340, 620]), [1, .6, .25], [.03, .02, .012], seed + q * 7 + 8, att=.002, phase=0) * .20
        con += bp(white(c, seed + q * 7 + 9), 700, 3600, 1) * np.exp(-tc / .006) * .10
        y = (lp(fric, 7500, 1) * .34 + tooth + wet * .34) * pr
        y[:c] += con * pr * .8
        pc = curve([(0, p0), (d, p1)], m)
        o = ns(t0)
        st = pan2(y * fade(m, .001, .04), pc)
        e2 = min(n - o, m)
        out[:, o:o + e2] += st[:, :e2]
    return out * .16


def peel(dur, seed):
    n = ns(dur)
    t = np.arange(n) / SR
    u = t / dur
    a = crackle(dur, [(0, 150), (dur * .5, 1500), (dur * .92, 5200), (dur, 200)], seed, 'thick', rr=(.8, 1.4), width=.2)
    b = crackle(dur, [(0, 50), (dur * .4, 900), (dur * .95, 6500), (dur, 100)], seed + 1, 'thin', rr=(.8, 1.7), width=.3)
    z = noise2(n, seed + 2, .6)
    e = u ** 1.4 * (1 - smoothstep((u - .93) / .07)) * (1 + .4 * slow(n, 35, seed + 5))
    h = np.stack([svf(z[c], 900 + 3800 * u ** 1.5, 1.1) for c in (0, 1)]) * e * .05
    return a * .5 + b * .35 + h


# ================================================================ books, wood, metal, big air
def rattle(t0, t1, rate, gain, seed, pan=(-.6, .6), n_books=14, kind='leather', f=(260, 1500)):
    """Books knocking on their shelf: every book has its own pitch, rate and place."""
    tr = Track(t0, t1 + .5)
    for b in range(n_books):
        r = rng(seed * 100 + b)
        p = pan[0] + (pan[1] - pan[0]) * (b + r.uniform(-.3, .3)) / max(n_books - 1, 1)
        fm = np.exp(r.uniform(np.log(f[0]), np.log(f[1]), 5))
        L = ns(.12)
        hit = modes(L, np.concatenate([[r.uniform(95, 170)], fm]), np.concatenate([[.7], r.uniform(.3, 1, 5) * (fm / f[0]) ** -.4]),
                    np.concatenate([[.06], r.uniform(.016, .05, 5)]), seed * 100 + b, att=.0005, phase=0)
        hit += bp(white(L, seed * 100 + b + 1), 700, 5000, 1) * np.exp(-np.arange(L) / SR / .0035) * .35
        hit *= fade(L, .0002, .02)
        t = t0 + r.uniform(0, .12) * 2
        while t < t1:
            rr = np.interp(t, [a[0] for a in rate], [a[1] for a in rate])
            g = np.interp(t, [a[0] for a in gain], [a[1] for a in gain])
            if rr > .5 and g > 1e-3:
                tr.add(t, hit, g * r.uniform(.25, 1.0) ** 1.3 * .12, p)
            # a light book bounces: pairs of close taps
            t += (1 / max(rr, 1)) * r.uniform(.55, 1.5) if r.uniform() > .28 else .022 * r.uniform(.8, 1.6)
    return tr.x


def jolt(seed, weight=1.0):
    """Dry wooden thud of the whole case shifting."""
    r = rng(seed)
    n = ns(.5)
    t = np.arange(n) / SR
    k = r.uniform(.94, 1.06)
    x = modes(n, np.array([46, 67, 98, 141, 205, 298, 430, 640, 960, 1500, 2300]) * k,
              np.array([.8, 1, .95, .8, .7, .5, .4, .3, .2, .13, .08]) * db(r.normal(0, 2, 11)),
              np.array([.16, .15, .13, .11, .09, .07, .05, .04, .03, .02, .014]), seed, att=.0006, phase=0) * .55
    x += bp(white(n, seed + 1), 300, 4500, 1) * np.exp(-t / .007) * .42
    x += lp(white(n, seed + 2), 240, 2) * np.exp(-t / .035) * 1.0
    # loose boards answer
    for q in range(4):
        o = ns(r.uniform(.014, .09))
        m = ns(.08)
        x[o:o + m] += modes(m, np.exp(r.uniform(np.log(300), np.log(1900), 4)), r.normal(0, 1, 4), r.uniform(.01, .03, 4), seed + 5 + q, att=.0003, phase=0)[:m] * .16
    return x * weight * fade(n, .0002, .1)


def subhit(dur=1.8, f0=78, f1=31, drop=.09, dec=.55, seed=1, drive=1.6):
    n = ns(dur)
    t = np.arange(n) / SR
    f = f1 + (f0 - f1) * np.exp(-t / drop)
    ph = 2 * np.pi * np.cumsum(f) / SR
    y = np.sin(ph) * (1 - np.exp(-t / .0035)) * np.exp(-t / dec)
    y = np.tanh(y * drive) / np.tanh(drive)
    return y * fade(n, .0005, .3)


def metal_modes(seed, f0=180, K=46, hi=9000, T=1.1):
    r = rng(seed)
    f = np.sort(np.exp(r.uniform(np.log(f0), np.log(hi), K)))
    a = r.normal(0, 1, K) * (f / f0) ** -.28
    t = T * (f / 400) ** -.55 * r.uniform(.5, 1.6, K)
    return f, a, np.clip(t, .03, 2.5)


def clang(seed, f0=180, T=1.0, vel=1.0):
    f, a, tt = metal_modes(seed, f0=f0, T=T)
    n = ns(min(tt.max() * 1.1, 2.4))
    x = modes(n, f, a, tt, seed + 1, att=.0004)
    q = ns(.05)
    x[:q] += bp(white(q, seed + 2), 500, 9000, 1) * np.exp(-np.arange(q) / SR / .006) * 3.0
    return x / np.abs(x).max() * vel * fade(n, .0002, .3)


def ride(x, t0, pts, win=.45, rate=200):
    """Level a texture: divide by its own slow RMS, then follow a dBFS target curve (absolute seconds)."""
    n = x.shape[1]
    hop = SR // rate
    p = (x ** 2).mean(0)
    k = n // hop + 1
    e = np.add.reduceat(p, np.arange(0, n, hop)) / hop
    w = np.hanning(int(win * rate) | 1)
    w /= w.sum()
    e = np.convolve(np.pad(e, len(w) // 2, mode='edge'), w, 'valid')[:len(e)]
    tc = (np.arange(len(e)) + .5) * hop
    n_ = np.arange(n)
    inv = np.interp(n_, tc, 1 / np.sqrt(np.maximum(e, e.max() * 1e-5)))
    g = np.interp(n_, tc, db(curve(pts, len(e), t0 + .5 * hop / SR, rate)))
    # sheets that fly too close are bent back, so the crowd stays a crowd
    return 3.3 * np.tanh(x * inv / 3.3) * g


def mass(x, seed, depth=.45, f=(5.5, 13)):
    """Correlated beating of a crowd: each side breathes on its own."""
    n = x.shape[1]
    a = [np.exp(depth * (slow(n, f[0], seed + k) + .7 * slow(n, f[1], seed + 5 + k))) for k in (0, 1)]
    c = np.exp(.5 * depth * slow(n, f[0] * .6, seed + 11))
    return x * np.stack(a) * c


def near(t0, t1, rate, seed, size=(.15, .5), sp=(.055, .11), pan=1.0, gain=None):
    """Single sheets flapping past the ear."""
    r = rng(seed)
    nk = int((t1 - t0) * 1000) + 1
    tt = times(curve(rate, nk, t0, 1000), seed + 1)
    tr = Track(t0, t1 + 1.2)
    for q, t in enumerate(tt):
        k = r.integers(3, 8)
        p0, p1 = r.uniform(-pan, pan, 2)
        dt = r.uniform(*sp)
        sz = r.uniform(*size)
        a = np.exp(r.normal(0, .55)) * (np.interp(t + t0, [g[0] for g in gain], [g[1] for g in gain]) if gain else 1)
        fc = r.uniform(3500, 13000)
        for j in range(k):
            u = (j + .5) / k
            y = lp(flap(seed * 50 + q * 9 + j, sz, 1.0), fc * (.35 + .65 * np.sin(np.pi * u)), 1)
            tr.add(t0 + t + j * dt * r.uniform(.9, 1.1), y, a * np.sin(np.pi * u) ** 1.2, np.clip(p0 + (p1 - p0) * u, -1, 1))
    return tr.x


def brush_path(t, v, r, x, seed, p0=-.4, p1=.4, size=1.0, tail=.18):
    """One continuous stroke driven by the drawn line itself: time (s), tip speed 0..1, belly radius 0..1 (0 = lifted), x 0..1.
    Returns (t0, stereo)."""
    t, v, r, x = (np.asarray(a, float) for a in (t, v, r, x))
    t0 = t[0] - .03
    n = ns(t[-1] - t0 + tail)
    ts = t0 + np.arange(n) / SR
    sp = np.interp(ts, t, v, left=0, right=0)
    rr = np.interp(ts, t, r, left=0, right=0)
    touch = smoothstep((rr - .012) / .05)
    sm = lambda a, f: np.maximum(signal.sosfiltfilt(signal.butter(2, f, fs=SR, output='sos'), a), 0)
    sp, rr, touch = sm(sp, 24), sm(rr, 18), sm(touch, 40)
    sp = sp * (1 + .14 * slow(n, 9, seed + 1))
    z = white(n, seed + 2)
    bris = poisson_env(500 + 2800 * sp * touch, .0018, .0002, seed + 3, 2.3)
    bris = bris / (bris.mean() + 1e-9)
    e = sp ** 1.05 * touch * (.28 + .72 * rr ** .6)
    fric = lp(svf(z, (620 + 2500 * sp) * (1.25 - .55 * rr) * size ** -.4, .8), 7000, 1) * (.4 + .6 * np.minimum(bris, 4)) * e
    hair = bp(z, 2600, 9000, 1) * poisson_env(250 + 1900 * sp * touch, .0007, .00008, seed + 4, 1.8) * e * .045
    wet = svf(white(n, seed + 5), 300 + 420 * sp + 130 * slow(n, 13, seed + 6), 2.4) * (rr ** 1.2) * (.25 + .75 * sp) * touch
    sq = svf(white(n, seed + 7), 900 + 1400 * rr, 5) * np.clip(np.gradient(rr) * SR * .12, 0, 1) * touch      # belly spreading: a small wet kiss
    y = fric * .36 + hair + wet * .24 + sq * .30
    # tip contacts where the brush comes down
    on = np.flatnonzero((touch[1:] > .35) & (touch[:-1] <= .35))
    for k, i in enumerate(on):
        c = ns(.05)
        tc = np.arange(c) / SR
        con = modes(c, np.array([205, 330, 610]), [1, .6, .25], [.03, .02, .012], seed + 20 + k, att=.002, phase=0) * .14
        con += bp(white(c, seed + 40 + k), 600, 3200, 1) * np.exp(-tc / .006) * .07
        m = min(c, n - i)
        y[i:i + m] += con[:m]
    pan = p0 + (p1 - p0) * np.interp(ts, t, x)
    return t0, pan2(y * fade(n, .004, .03), pan) * .17


def whoomph(seed, size=1.0, dur=1.2):
    """A wing of paper pushing a body of air: soft attack, low pressure pulse, then the spill."""
    n = ns(dur)
    t = np.arange(n) / SR
    z = noise2(n, seed, .5)
    fc = 170 + 1300 * np.exp(-t / .09) + 340 * np.exp(-t / .5)
    e = (1 - np.exp(-t / .022)) * (np.exp(-t / .16) + .16 * np.exp(-t / .5))
    y = np.stack([svf(z[c], fc, .75, 'lp') for c in (0, 1)]) * e
    return hp(y, 45, 1) * size * fade(n, .002, .2)
