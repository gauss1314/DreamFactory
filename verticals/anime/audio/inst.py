"""Instruments. Every sound is built from a physical description: strings, bars, membranes, bows, lips, voices."""
import numpy as np
import numba as nb
from core import *

HOP = 32
CR = SR / HOP


# ================================================================ modal bank
@nb.njit(cache=True, fastmath=True)
def modal_bank(n, f, a, d, ph, att):
    """sum a*(exp(-d t) - exp(-(d+1/att) t))*sin(2 pi f t + ph)"""
    out = np.zeros(n)
    for k in range(len(f)):
        if f[k] > 21000.0 or f[k] <= 0:
            continue
        w = 2 * np.pi * f[k] / 48000.0
        for s in range(2):
            if s == 1 and att[k] <= 0:
                continue
            dd = d[k] if s == 0 else d[k] + 1.0 / att[k]
            amp = a[k] if s == 0 else -a[k]
            r = np.exp(-dd / 48000.0)
            cr, ci = r * np.cos(w), r * np.sin(w)
            re, im = amp * np.cos(ph[k]), amp * np.sin(ph[k])
            lim = n if dd <= 0 else min(n, int(48000.0 * np.log(max(abs(amp), 1e-9) / 1e-7) / dd) + 1)
            for i in range(lim):
                out[i] += im
                t = re * cr - im * ci
                im = re * ci + im * cr
                re = t
    return out


def modes(n, f, a, t60, seed=0, att=0.0, phase=None):
    f = np.asarray(f, float)
    k = len(f)
    ph = rng(seed).uniform(0, 2 * np.pi, k) if phase is None else np.full(k, float(phase))
    return modal_bank(n, f, np.broadcast_to(np.asarray(a, float), (k,)).copy(),
                      6.9078 / np.broadcast_to(np.asarray(t60, float), (k,)), ph,
                      np.broadcast_to(np.asarray(att, float), (k,)).copy())


def min_phase(mag_db_f, n=4096, f=None):
    """Minimum phase FIR from a dB curve sampled on rfft bins of 2n."""
    m = 2 * n
    L = np.concatenate([mag_db_f, mag_db_f[-2:0:-1]]) * np.log(10) / 20
    c = np.fft.ifft(L).real
    w = np.zeros(m)
    w[0] = 1
    w[1:m // 2] = 2
    w[m // 2] = 1
    h = np.fft.ifft(np.exp(np.fft.fft(c * w))).real[:n]
    h[-n // 4:] *= np.cos(np.linspace(0, np.pi / 2, n // 4)) ** 2
    return h


def body_fir(fpts, gdb, seed, rough=4.5, dens=9.0, n=3072):
    """Resonant body: a broad response curve plus a seeded texture of wood modes."""
    m = n
    f = np.linspace(0, SR / 2, m + 1)
    lf = np.log2(np.maximum(f, 20))
    base = np.interp(lf, np.log2(np.asarray(fpts, float)), np.asarray(gdb, float))
    r = rng(seed)
    g = np.linspace(np.log2(40), np.log2(20000), int(dens * np.log2(500)))
    g = g + r.normal(0, .3 / dens, len(g))
    tex = np.zeros_like(f)
    for c in g:
        wd = .42 / dens * r.uniform(.6, 1.5)
        tex += r.normal(0, rough) / (1 + ((lf - c) / wd) ** 2)
    return min_phase(base + tex, n)


# ================================================================ piano
def _board(f, seed=5):
    """Smooth deterministic soundboard mobility ripple, dB."""
    r = rng(seed)
    lf = np.log2(np.maximum(f, 20.0))
    y = np.zeros_like(lf)
    for k in range(14):
        y += r.normal(0, .9) * np.sin(lf * r.uniform(2, 16) + r.uniform(0, 6.28))
    y += np.interp(lf, np.log2([40, 70, 110, 160, 260, 400, 1000, 2500, 5000, 10000]), [-18, -10, -6, -3.5, -.5, 0, -1, -3, -6, -14])
    return y


def piano_note(m, vel, hold, seed, felt=1.0, tail=None):
    """Two-stage decaying unison strings struck by a felt hammer. Returns stereo, starts at t=0 (hammer contact)."""
    r = rng(seed)
    f0 = float(mtof(m))
    B = 1.0e-4 * 2 ** ((m - 40) / 11) if m >= 40 else 1.0e-4 * (1 + ((40 - m) / 15) ** 2)
    npar = 1
    top = 9500 if felt > .5 else 14500
    while npar < 70:
        k = npar + 1
        if k * f0 * np.sqrt(1 + B * k * k) > top:
            break
        npar = k
    k = np.arange(1, npar + 1)
    fk = k * f0 * np.sqrt(1 + B * k * k) / np.sqrt(1 + B)
    strike = .118 + .02 * r.uniform(-1, 1)
    # felt: contact time ~5-6 ms mid register -> steep roll off; harder hammer opens the spectrum
    fh = (270 + 520 * vel) * (f0 / 262) ** .42 if felt > .5 else (900 + 2900 * vel ** 1.3) * (f0 / 262) ** .3
    roll = (1 + (fk / fh) ** 2) ** (-.95 if felt > .5 else -.94)
    amp = (np.abs(np.sin(k * np.pi * strike)) + .06) / np.sin(np.pi * strike) * roll * db(_board(fk)) * k ** .12
    amp *= db(r.normal(0, 1.2, npar))
    amp /= np.sqrt((amp ** 2).sum())
    T1 = 7.4 * 2 ** (-(m - 60) / 19.0)
    tk = T1 / (1 + .13 * (k - 1) + .006 * (k - 1) ** 2 + (fk / 5200) ** 2)
    n = ns(min(tail if tail else T1 * 3.0, 16.0))
    out = np.zeros((2, n))
    nstr = 1 if m < 33 else 2 if m < 45 else 3
    det = {1: [0], 2: [-.28, .34], 3: [-.27, .02, .24]}[nstr]
    wts = {1: [1], 2: [.56, .44], 3: [.46, .33, .21]}[nstr]
    hard = .0016 if felt > .5 else .0006
    tau = hard * (1 + 1.0 * (1 - vel)) * (262 / f0) ** .25
    cen = [c * r.uniform(.75, 1.3) for c in det]
    for ch in range(2):
        ff, aa, tt, pp, at = [], [], [], [], []
        for s in range(nstr):
            cents = cen[s]
            # fast prompt stage and the slow aftersound of the coupled unison
            for stage, (g, mul) in enumerate(((1.0, 1.0), (.24 if nstr > 1 else .14, 3.0))):
                ff.append(fk * 2 ** ((cents + (.25 * stage)) / 1200))
                aa.append(amp * wts[s] * g * db(r.normal(0, .8, npar)))
                tt.append(tk * mul * r.uniform(.9, 1.1))
                pp.append(r.normal(0, .25, npar) + .9 * stage * r.uniform(-1, 1, npar))
                at.append(np.full(npar, tau) * (1 + .4 * (k < 3)))
        out[ch] = modal_bank(n, np.concatenate(ff), np.concatenate(aa), 6.9078 / np.concatenate(tt),
                             np.concatenate(pp), np.concatenate(at))
    # damper
    h = ns(hold)
    if h < n:
        t = np.arange(n - h) / SR
        td = .09 + .16 * max(0, (60 - m) / 30) + .04
        dk = np.exp(-t / td)
        dull = lp(out[:, h:], 420, 1)
        mix = np.exp(-t / .03)
        out[:, h:] = (out[:, h:] * mix + dull * (1 - mix)) * dk
        n2 = min(n, h + ns(1.2))
        out = out[:, :n2]
        out *= fade(n2, 0, .05)
    else:
        out *= fade(n, 0, .6)
    g = vel ** 1.55
    out *= g * .5
    # mechanics: hammer knock through the soundboard, felt rub, key bed
    nn = ns(.35)
    kf = np.array([71, 96, 128, 163, 205, 248, 305, 372, 455, 560, 690, 860]) * r.uniform(.97, 1.03, 12)
    ka = np.array([.5, .9, 1, .8, .9, .7, .5, .42, .3, .2, .14, .08]) * r.uniform(.6, 1.3, 12)
    knock = modes(nn, kf, ka, np.linspace(.16, .05, 12), seed + 1, att=.0012, phase=0)
    knock *= .019 * (vel ** 1.25) * (1 if felt > .5 else .7)
    rub = bp(white(nn, seed + 2), 400, 5200, 1) * np.exp(-np.arange(nn) / SR / .011) * (1 - np.exp(-np.arange(nn) / SR / .002))
    rub *= .052 * vel ** 1.1
    bed = modes(nn, np.array([104, 149, 231, 338, 512]) * r.uniform(.96, 1.04, 5), [1, .9, .6, .35, .2],
                [.07, .06, .05, .04, .03], seed + 3, att=.001, phase=0) * .011 * vel
    mech = np.zeros((2, max(out.shape[1], nn + ns(.03))))
    o = np.zeros_like(mech)
    o[:, :out.shape[1]] = out
    d = ns(.014 + .02 * (1 - vel))
    for ch in range(2):
        o[ch, :nn] += knock * (1 + .15 * (ch * 2 - 1)) + rub * r.uniform(.8, 1.2)
        o[ch, d:d + nn] += bed
    if h + ns(.4) < o.shape[1] and hold < 14:
        rl = bp(white(nn, seed + 4), 180, 1500, 1) * np.exp(-np.arange(nn) / SR / .03) * (1 - np.exp(-np.arange(nn) / SR / .012))
        m2 = min(nn, o.shape[1] - h)
        o[:, h:h + m2] += rl[:m2] * .006
    # keyboard image: bass slightly left
    p = np.clip((m - 64) / 60, -.42, .42)
    o[0] *= np.cos((p + 1) * np.pi / 4) * 1.4142
    o[1] *= np.sin((p + 1) * np.pi / 4) * 1.4142
    return o


def soundboard_ir(seed=11, L=.22):
    n = ns(L)
    r = rng(seed)
    k = 90
    f = np.exp(r.uniform(np.log(62), np.log(5200), k))
    out = []
    for ch in range(2):
        a = db(np.interp(np.log2(f), np.log2([60, 150, 350, 1200, 5200]), [-16, -8, -3, -8, -19])) * r.normal(0, 1, k)
        out.append(modes(n, f, a, np.interp(np.log2(f), np.log2([60, 300, 1500, 5200]), [.30, .17, .07, .03]), seed + ch,
                         att=.0008))
    out = np.stack(out)
    return out / np.sqrt((out ** 2).sum() / 2)


def sympathetic_ir(seed=12, L=4.5):
    """All undamped strings answering: a bank of decaying partials at equal-tempered pitches."""
    n = ns(L)
    r = rng(seed)
    ff, aa, tt = [], [], []
    for m in range(28, 92):
        f0 = float(mtof(m))
        for k in range(1, 7):
            f = k * f0 * np.sqrt(1 + 3e-4 * k * k)
            if f > 5000:
                break
            ff.append(f * 2 ** (r.normal(0, .7) / 1200))
            aa.append(1 / k ** .9 * (220 / max(f, 90)) ** .55)
            tt.append(4.6 * (200 / max(f, 120)) ** .38)
    out = []
    for ch in range(2):
        a = np.array(aa) * r.normal(0, 1, len(ff))
        out.append(modes(n, np.array(ff), a, np.array(tt), seed + 3 + ch, att=.02))
    out = np.stack(out) * fade(n, 0, 1.2)
    return out / np.sqrt((out ** 2).sum() / 2)


# ================================================================ bowed strings
def _saw_tables():
    size = 4096
    tabs, tops = [], []
    f = 30.0
    while f < 4200:
        hi = f * 2 ** .5
        nh = max(1, int(19500 / hi))
        nh = min(nh, size // 2 - 2)
        X = np.zeros(size // 2 + 1, complex)
        k = np.arange(1, nh + 1)
        X[1:nh + 1] = -1j * (size / 2) * (2 / np.pi) / k * np.cos(np.pi * k / (2 * (nh + 1))) ** .5
        w = np.fft.irfft(X, size)
        tabs.append(np.concatenate([w, w[:1]]))
        tops.append(f)
        f = hi
    return np.stack(tabs)


SAW = _saw_tables()


@nb.njit(cache=True, fastmath=True)
def bow_kernel(out, f, amp, fc, noi, tab, seed, ph0, jit):
    """One bowed player. Control arrays at CR. Wavetable Helmholtz motion, two dynamic one-poles, pitch-synchronous bow noise."""
    np.random.seed(seed)
    ntab, sz = tab.shape[0], tab.shape[1] - 1
    ph = ph0
    z1 = z2 = 0.0
    j = 0.0
    nc = f.shape[0]
    L = out.shape[0]
    nz = 0.0
    for c in range(nc - 1):
        if amp[c] < 1e-6 and amp[c + 1] < 1e-6:
            z1 *= .5
            z2 *= .5
            continue
        j += (np.random.normal(0, 1) * jit - j) * .25
        f0 = f[c] * (1 + j)
        ti = int(2 * np.log2(max(f0, 30.0) / 30.0))
        ti = min(max(ti, 0), ntab - 1)
        g0 = 1 - np.exp(-2 * np.pi * fc[c] / 48000.0)
        g1 = 1 - np.exp(-2 * np.pi * min(fc[c] * 2.2, 18000.0) / 48000.0)
        da = (amp[c + 1] - amp[c]) / 32.0
        df = (f[c + 1] - f[c]) / 32.0
        a = amp[c]
        ff = f0
        nn = noi[c]
        for i in range(32):
            k = c * 32 + i
            if k >= L:
                return
            ph += ff / 48000.0
            if ph >= 1:
                ph -= 1
            x = ph * sz
            i0 = int(x)
            s = tab[ti, i0] + (tab[ti, i0 + 1] - tab[ti, i0]) * (x - i0)
            nz += (np.random.normal(0, 1) - nz) * .75
            gate = .3 + .7 * (1 - ph) * (1 - ph)
            s += nz * nn * gate
            z1 += g0 * (s - z1)
            z2 += g1 * (z1 - z2)
            out[k] += z2 * a
            a += da
            ff += df


BODY = dict(
    vn=([120, 180, 230, 280, 350, 460, 550, 700, 950, 1300, 1800, 2400, 3200, 4200, 5600, 8000, 12000, 20000],
        [-30, -15, -5, 1, -4, 3, 2, -3, -4, -4, -2, 1, 2, -.5, -4, -9, -16, -28]),
    va=([90, 130, 180, 220, 300, 390, 480, 650, 850, 1100, 1600, 2100, 2800, 3800, 5200, 8000, 12000, 20000],
        [-30, -13, -2, 2, -2, 3, 1, -2, -1, -3, -4, -2, -2, -5, -9, -15, -22, -34]),
    vc=([45, 62, 85, 105, 150, 190, 260, 380, 520, 700, 950, 1400, 2000, 2800, 4000, 6000, 9000, 20000],
        [-24, -12, -3, 2, 1, 2, 0, -1, -1, -2, -3, -4, -4, -5, -9, -15, -23, -36]),
    cb=([30, 40, 55, 75, 100, 140, 200, 300, 450, 700, 1100, 1800, 2800, 4500, 8000, 20000],
        [-16, -6, 0, 2, 2, 0, -1, -3, -5, -7, -9, -12, -16, -24, -36, -50]))
VIB = dict(vn=(17, 5.7), va=(16, 5.4), vc=(18, 5.2), cb=(7, 4.8))


def _note(n):
    return (n + ({},))[:5] if len(n) == 4 else n


def strings(notes, kind='vn', players=12, groups=4, seed=1, art='leg', expr=None, bright=1.0, vib=1.0, sord=False,
            tail=.9, loose=1.0, t0=None):
    """notes: (t, dur, midi, dyn or (dyn0, dyn1) [, {art, glide}]) monophonic line. Returns (t0, array[groups, n])."""
    notes = [_note(tuple(n)) for n in notes]
    t0 = notes[0][0] - .3 if t0 is None else t0
    t1 = max(n[0] + n[1] for n in notes) + tail
    nc = int((t1 - t0) * CR) + 2
    n = nc * HOP
    tc = t0 + np.arange(nc) / CR
    ex = np.ones(nc) if expr is None else curve(expr, nc, t0, CR, 'db')
    ex = np.maximum(ex, 1e-4)
    R = rng(seed)
    out = np.zeros((groups, n))
    vd, vr = VIB[kind]
    for p in range(players):
        r = rng(seed * 1000 + p)
        bias = r.normal(0, 2.6) * loose
        lag = r.normal(0, .009) * loose
        pt, pv = [], []     # pitch points
        at, av = [], []     # dyn points
        dips = []
        trem = np.ones(nc)
        noi = np.full(nc, .060 * r.uniform(.7, 1.3))
        vdep = np.zeros(nc)
        prev_end = -9
        prev_m = None
        for q, (t, d, m, v, o) in enumerate(notes):
            a_ = o.get('art', art)
            v0, v1 = v if isinstance(v, tuple) else (v, v)
            on = t + lag + r.normal(0, .010 if a_ in ('spic', 'marc') else .018) * loose
            pm = m + (bias + r.normal(0, 3.0) * loose) / 100
            leg = (t - prev_end) < .06 and prev_m is not None and a_ in ('leg', 'slur', 'det')
            gl = o.get('glide', (.022 if r.uniform() < .45 else (.034 if a_ == 'det' else .055)) * r.uniform(.7, 1.4) * (1 + abs(m - (prev_m or m)) / 18))
            if leg:
                g0 = on - gl * r.uniform(.45, .75)
                pt += [g0, g0 + gl]
                pv += [prev_pm, pm]
            else:
                pt += [on - .02]
                pv += [pm]
            end = t + d
            nxt = notes[q + 1][0] if q + 1 < len(notes) else 1e9
            cont = nxt - end < .06
            if a_ == 'spic':
                atk, rel = .010, .075
                at += [on - .004, on + atk, on + atk + .03, on + min(d, .5) * .8 + rel]
                av += [0, v0, v0 * .82, 0]
                i = np.abs(tc - on) < .03
                noi[i] += .25
            elif a_ == 'marc':
                at += [on - .004, on + .016, on + .09, end - .03, end + .10]
                av += [0, min(v0 * 1.12, 1.25), v0 * .86, v1 * .86, 0]
                noi[np.abs(tc - on) < .025] += .22
            else:
                base = dict(leg=.13, slur=.10, det=.06, trem=.12, harm=.35, slow=.5).get(a_, .12)
                atk = min(base * r.uniform(.75, 1.35) * (1.5 - .7 * v0), d * .6)
                if not leg:
                    at += [on - .01, on + atk * .45, on + atk]
                    av += [0, v0 * .62, v0]
                    noi[np.abs(tc - on - .02) < .04] += .10
                else:
                    at += [on + .03]
                    av += [v0]
                    dips.append((on, .46 if a_ == 'det' else .15))
                    if a_ == 'det':
                        noi[np.abs(tc - on) < .022] += .16 * r.uniform(.5, 1.2)
                at += [max(end - .02, at[-1] + .01)]
                av += [v1]
                if not cont:
                    at += [at[-1] + (.22 if a_ != 'harm' else .4) * r.uniform(.8, 1.3)]
                    av += [0]
            if a_ == 'trem':
                i = (tc > on - .05) & (tc < end + .3)
                rate = r.uniform(11.0, 14.0)
                ph = np.cumsum(rate * (1 + .12 * slow(nc, 5, seed * 31 + p * 7 + q, CR))) / CR + r.uniform()
                fr = np.abs(np.sin(np.pi * ph)) ** .55
                trem = np.where(i, .42 + .58 * fr * (1 + .12 * slow(nc, 12, seed * 37 + p, CR)), trem)
                noi = np.where(i, noi + .06 * (fr < .35), noi)
            if a_ in ('leg', 'slur', 'det', 'slow') and d > .16:
                i = (tc > on) & (tc < end + .25)
                rampv = smoothstep((tc - on - .05 - .1 * r.uniform()) / (.22 + .25 * r.uniform())) * min(1, (d / .45) ** .7)
                vdep = np.where(i, np.maximum(vdep * (tc < on + .1), rampv), vdep)
            prev_end, prev_m, prev_pm = end, m, pm
        pit = np.interp(tc, pt, pv)
        k = int(.010 * CR) | 1
        w = np.hanning(k + 2)[1:-1]
        pit = np.convolve(np.pad(pit, k // 2, mode='edge'), w / w.sum(), 'valid')[:nc]
        dyn = np.interp(tc, at, av)
        k2 = 9 if art in ('spic', 'marc') else 33
        w = np.hanning(k2 + 2)[1:-1]
        dyn = np.convolve(np.pad(dyn, k2 // 2, mode='edge'), w / w.sum(), 'valid')[:nc]
        for (td, dd) in dips:
            dyn *= 1 - dd * np.exp(-((tc - td) / .028) ** 2) * r.uniform(.6, 1.3)
        vrate = vr * r.uniform(.93, 1.07) * (1 + .05 * slow(nc, 2, seed * 41 + p, CR))
        vph = 2 * np.pi * np.cumsum(vrate) / CR + r.uniform(0, 6.28)
        dep = vd * r.uniform(.6, 1.35) * (1 + .35 * slow(nc, 1.5, seed * 43 + p, CR)) * vdep * vib
        # vibrato leans to the flat side, like a rolled finger
        cents = dep * (np.sin(vph) - .25 + .12 * np.sin(2 * vph)) + 2.2 * slow(nc, 2.5, seed * 47 + p, CR)
        fr = mtof(pit + cents / 100)
        for (t, d, m, v, o) in notes:
            if d > .4 and o.get('art', art) in ('leg', 'slur', 'det', 'slow'):
                u = np.clip((tc - t - lag) / d, 0, 1)
                dyn *= 1 + o.get('swell', .10) * np.sin(np.pi * u ** .8) - .02 * u
        bowv = 1 + .15 * slow(nc, 2.6, seed * 53 + p, CR) + .08 * slow(nc, 9, seed * 59 + p, CR) + .04 * slow(nc, 28, seed * 67 + p, CR)
        amp = np.maximum(dyn, 0) ** 1.6 * ex * bowv * trem
        bd = np.clip(dyn * ex ** .35 * (.94 + .06 * trem), 0, 1.3)
        fc = 800 * 9.0 ** bd * bright * r.uniform(.8, 1.25) * (1 + .08 * slow(nc, 4, seed * 61 + p, CR))
        if sord:
            fc *= .55
        bow_kernel(out[p % groups], fr, amp, fc, noi * (1.25 - .5 * np.clip(dyn, 0, 1)), SAW, seed * 97 + p, r.uniform(), .0011)
    out *= 1 / np.sqrt(players)
    fp, gd = BODY[kind]
    for g in range(groups):
        h = body_fir(fp, gd, seed % 7 * 100 + g + {'vn': 0, 'va': 11, 'vc': 22, 'cb': 33}[kind])
        out[g] = conv(out[g], h)[:n]
        if sord:
            out[g] = eq(out[g], 1500, 3, 1.2)
            out[g] = lp(out[g], 3600, 1)
    return t0, out


# ================================================================ brass
BR = dict(horn=dict(f1=165, k=15.0, form=((430, 5, .8), (900, 1.5, .7)), hp=170, rad=1.0),
          tbn=dict(f1=260, k=15.0, form=((520, 4, .7), (1400, 3, .8), (2500, 2, .6)), hp=120, rad=1.0),
          tuba=dict(f1=130, k=11.0, form=((240, 4, .8), (480, 2, .8)), hp=60, rad=1.0),
          tpt=dict(f1=480, k=11.0, form=((1150, 4, .7), (2200, 4, .7), (3300, 2, .5)), hp=300, rad=1.0))
NLEV = 9


def _brass_tables(kind, f0):
    b = BR[kind]
    size = 2048
    nh = int(min(17000 / f0, 180))
    k = np.arange(1, nh + 1)
    f = k * f0
    tabs = []
    for q in range(NLEV):
        dy = q / (NLEV - 1)
        fc = b['f1'] * b['k'] ** dy
        g = -(f / fc) * 8.686 * .95
        g = np.maximum(g, -26 - 14 * np.log2(np.maximum(f / fc, 1)) * 1.0) if dy > .6 else g
        for (ff, gg, q_) in b['form']:
            g = g + gg / (1 + (np.log2(f / ff) / q_) ** 2)
        g = g - 10 * np.log10(1 + (b['hp'] / f) ** 4)
        a = db(g)
        a /= np.sqrt((a ** 2).sum() / 2)
        X = np.zeros(size // 2 + 1, complex)
        X[1:nh + 1] = a * np.exp(1j * (-np.pi / 2 - .035 * k ** 1.45)) * size / 2
        w = np.fft.irfft(X, size)
        tabs.append(np.concatenate([w, w[:1]]))
    return np.stack(tabs)


@nb.njit(cache=True, fastmath=True)
def brass_kernel(out, f, amp, lev, noi, tab, seed, ph0):
    np.random.seed(seed)
    nl, sz = tab.shape[0], tab.shape[1] - 1
    ph = ph0
    j = 0.0
    z = 0.0
    z2 = 0.0
    L = out.shape[0]
    for c in range(f.shape[0] - 1):
        j += (np.random.normal(0, 1) * .0012 - j) * .2
        da = (amp[c + 1] - amp[c]) / 32
        a = amp[c]
        if a < 1e-6 and amp[c + 1] < 1e-6:
            continue
        x = min(max(lev[c], 0.0), .9999) * (nl - 1)
        l0 = int(x)
        lf = x - l0
        inc = f[c] * (1 + j) / 48000.0
        for i in range(32):
            k = c * 32 + i
            if k >= L:
                return
            ph += inc
            if ph >= 1:
                ph -= 1
            xx = ph * sz
            i0 = int(xx)
            fr = xx - i0
            s0 = tab[l0, i0] + (tab[l0, i0 + 1] - tab[l0, i0]) * fr
            s1 = tab[l0 + 1, i0] + (tab[l0 + 1, i0 + 1] - tab[l0 + 1, i0]) * fr
            w = np.random.normal(0, 1)
            z += (w - z) * .35
            z2 += (z - z2) * .05
            out[k] += ((s0 + (s1 - s0) * lf) + (z - z2) * noi[c] * (.5 + s0 * .3)) * a
            a += da


def brass(notes, kind='horn', players=4, seed=1, art='ten', expr=None, tail=.7, groups=None, loose=1.0):
    notes = [_note(tuple(n)) for n in notes]
    groups = groups or players
    t0 = notes[0][0] - .2
    t1 = max(n[0] + n[1] for n in notes) + tail
    nc = int((t1 - t0) * CR) + 2
    n = nc * HOP
    tc = t0 + np.arange(nc) / CR
    ex = np.ones(nc) if expr is None else curve(expr, nc, t0, CR, 'db')
    out = np.zeros((groups, n))
    for p in range(players):
        r = rng(seed * 1000 + p)
        bias = r.normal(0, 3.2) * loose
        lag = r.normal(.004, .008)
        prev_end, prev_m = -9, None
        for q, (t, d, m, v, o) in enumerate(notes):
            a_ = o.get('art', art)
            v0, v1 = v if isinstance(v, tuple) else (v, v)
            vp = o.get('peak', None)
            on = t + lag + r.normal(0, .009) * loose
            slur = (t - prev_end) < .05 and prev_m is not None and a_ == 'leg'
            atk = {'ten': .060, 'leg': .075, 'marc': .028, 'swell': .25}.get(a_, .06) * r.uniform(.8, 1.3)
            end = t + d + (.0 if q + 1 >= len(notes) or notes[q + 1][0] > t + d + .05 else -.012)
            if a_ == 'marc':
                P = [(on - .01, 0), (on + atk, v0 * 1.1), (on + atk + .09, v0 * .82), (end - .04, v1 * .85), (end + .07, 0)]
            elif vp is not None:
                P = [(on - .01, 0), (on + atk, v0), (t + d * o.get('at', .6), vp), (end - .05, v1), (end + .12, 0)]
            else:
                P = [(on - .012, 0.0 if not slur else v0 * .5), (on + atk * .4, v0 * .55), (on + atk, v0 * 1.02), (on + atk + min(.22, d * .3), v0 * .93),
                     (on + d * .62, (v0 * .4 + v1 * .6) * 1.03), (end - .07, v1 * .97), (end + .02, v1 * .55), (end + .17, 0)]
            P = np.array(P)
            P[:, 0] = np.maximum.accumulate(P[:, 0] + np.arange(len(P)) * 1e-5)
            dyn = np.interp(tc, P[:, 0], P[:, 1], left=0, right=0)
            w = np.hanning(23)[1:-1]
            dyn = np.convolve(dyn, w / w.sum(), 'same')
            i = dyn > 1e-4
            i0 = max(np.argmax(i) - 4, 0)
            i1 = min(len(i) - np.argmax(i[::-1]) + 4, nc)
            if i1 <= i0:
                continue
            s = slice(i0, i1)
            cents = bias + r.normal(0, 2.5) - (32 if a_ == 'marc' else 18) * np.exp(-np.maximum(tc[s] - on, 0) / .030)
            k = i1 - i0
            cents = cents + 2.5 * slow(k, 3, seed * 31 + p * 13 + q, CR) + (4.0 if kind == 'horn' else 3.0) * smoothstep((tc[s] - on - .35) / .5) * np.sin(
                2 * np.pi * (4.9 + r.uniform(-.3, .3)) * tc[s] + r.uniform(0, 6.28))
            dy = dyn[s] * (1 + .035 * slow(k, 7, seed * 37 + p * 13 + q, CR) + .025 * slow(k, 19, seed * 39 + p + q, CR) + .03 * slow(k, 2.2, seed * 35 + p * 3 + q, CR))
            lvl = np.clip(dy * np.clip(ex[s], 0, 2) ** .4 - .03, 0, 1)
            # brightness trails loudness a little at the attack
            lvl = signal.lfilter([.06], [1, -.94], lvl)
            amp = np.maximum(dy, 0) ** 1.6 * ex[s]
            nz = .05 + .30 * np.exp(-np.maximum(tc[s] - on, 0) / .03)
            brass_kernel(out[p % groups][i0 * HOP:i1 * HOP], mtof(m + cents / 100), amp, lvl, nz, _brass_tables(kind, float(mtof(m))),
                         seed * 91 + p * 17 + q, r.uniform())
            prev_end, prev_m = t + d, m
    return t0, out / np.sqrt(players)


# ================================================================ choir
FORM = dict(
    S=dict(a=((800, 1150, 2900, 3900, 4950), (0, -6, -28, -22, -44), (80, 90, 120, 130, 140)),
           o=((450, 800, 2830, 3800, 4950), (0, -11, -22, -22, -44), (70, 80, 100, 130, 135)),
           u=((330, 700, 2700, 3800, 4950), (0, -16, -33, -38, -56), (60, 70, 150, 180, 200))),
    A=dict(a=((760, 1150, 2800, 3500, 4950), (0, -5, -22, -34, -52), (80, 90, 120, 130, 140)),
           o=((430, 800, 2830, 3500, 4950), (0, -9, -18, -28, -50), (70, 80, 100, 130, 135)),
           u=((325, 700, 2530, 3500, 4950), (0, -12, -30, -40, -60), (60, 70, 150, 180, 200))),
    T=dict(a=((650, 1080, 2650, 2900, 3250), (0, -6, -9, -10, -24), (80, 90, 120, 130, 140)),
           o=((400, 800, 2600, 2800, 3000), (0, -10, -14, -14, -28), (70, 80, 100, 130, 135)),
           u=((350, 600, 2700, 2900, 3300), (0, -20, -19, -16, -28), (60, 60, 100, 120, 120))),
    B=dict(a=((600, 1040, 2250, 2450, 2750), (0, -7, -11, -11, -22), (70, 80, 100, 130, 135)),
           o=((400, 750, 2400, 2600, 2900), (0, -11, -23, -22, -38), (50, 80, 100, 120, 120)),
           u=((350, 600, 2400, 2675, 2950), (0, -20, -30, -26, -34), (50, 80, 100, 120, 120))))


@nb.njit(cache=True, fastmath=True)
def voice_kernel(out, f, amp, tilt, asp, F, G, BW, tab, seed, ph0):
    """F,G,BW: [nc,5]. Saw source -> glottal tilt -> 5 parallel resonators."""
    np.random.seed(seed)
    ntab, sz = tab.shape[0], tab.shape[1] - 1
    ph = ph0
    z1 = z2 = 0.0
    y1 = np.zeros(5)
    y2 = np.zeros(5)
    j = 0.0
    hpz = 0.0
    L = out.shape[0]
    for c in range(f.shape[0] - 1):
        j += (np.random.normal(0, 1) * .0016 - j) * .2
        ti = min(max(int(2 * np.log2(max(f[c], 30.0) / 30.0)), 0), ntab - 1)
        g0 = 1 - np.exp(-2 * np.pi * tilt[c] / 48000.0)
        a = amp[c]
        da = (amp[c + 1] - amp[c]) / 32
        inc = f[c] * (1 + j) / 48000.0
        b0 = np.empty(5)
        c1 = np.empty(5)
        c2 = np.empty(5)
        for m in range(5):
            R = np.exp(-np.pi * BW[c, m] / 48000.0)
            c1[m] = 2 * R * np.cos(2 * np.pi * F[c, m] / 48000.0)
            c2[m] = -R * R
            b0[m] = G[c, m] * (1 - R) * np.sqrt(1 - 2 * R * np.cos(4 * np.pi * F[c, m] / 48000.0) + R * R) * 1.0
        for i in range(32):
            k = c * 32 + i
            if k >= L:
                return
            ph += inc
            if ph >= 1:
                ph -= 1
            xx = ph * sz
            i0 = int(xx)
            s = tab[ti, i0] + (tab[ti, i0 + 1] - tab[ti, i0]) * (xx - i0)
            z1 += g0 * (s - z1)
            src = (z1 * 1.0 + .12 * s)
            w = np.random.normal(0, 1)
            nz = (w - hpz) * asp[c] * (.4 + .6 * ph)
            hpz += (w - hpz) * .12
            src = (src + nz) * a
            o = 0.0
            for m in range(5):
                y = b0[m] * src + c1[m] * y1[m] + c2[m] * y2[m]
                y2[m] = y1[m]
                y1[m] = y
                o += y if m % 2 == 0 else -y
            out[k] += o
            a += da


def choir(notes, part='S', singers=8, groups=4, seed=1, vowel='a', expr=None, tail=1.0):
    """notes (t,dur,midi,dyn[,{vowel:'u>a'}])"""
    notes = [_note(tuple(n)) for n in notes]
    t0 = notes[0][0] - .4
    t1 = max(n[0] + n[1] for n in notes) + tail
    nc = int((t1 - t0) * CR) + 2
    tc = t0 + np.arange(nc) / CR
    ex = np.ones(nc) if expr is None else curve(expr, nc, t0, CR, 'db')
    out = np.zeros((groups, nc * HOP))
    for p in range(singers):
        r = rng(seed * 1000 + p)
        bias = r.normal(0, 5)
        pt, pv, at, av = [], [], [], []
        va = np.zeros((nc, 3))
        prev_end, prev = -9, None
        vowels = np.zeros((nc, 5)), np.zeros((nc, 5)), np.zeros((nc, 5))
        cur = {k: FORM[part][k] for k in 'aou'}
        mixv = np.zeros((nc, 3))
        for q, (t, d, m, v, o) in enumerate(notes):
            v0, v1 = v if isinstance(v, tuple) else (v, v)
            on = t + r.normal(0, .035)
            pm = m + (bias + r.normal(0, 5)) / 100
            leg = t - prev_end < .06 and prev is not None
            gl = .11 * r.uniform(.7, 1.4)
            if leg:
                pt += [on - gl * .6, on + gl * .4]
                pv += [prev, pm]
                at += [on + .06]
                av += [v0]
            else:
                pt += [on - .15, on - .02, on + .10]
                pv += [pm - .5, pm - .25, pm]
                at += [on - .06, on + .10, on + .32]
                av += [0, v0 * .5, v0]
            end = t + d
            at += [max(end - .04, at[-1] + .02)]
            av += [v1]
            if q + 1 >= len(notes) or notes[q + 1][0] - end > .06:
                at += [at[-1] + .4 * r.uniform(.8, 1.2)]
                av += [0]
            vw = o.get('vowel', vowel)
            i = tc >= on - .1
            if '>' in vw:
                x, y = vw.split('>')
                u = smoothstep((tc - on) / max(d * .7, .1))
                mv = np.zeros((nc, 3))
                mv[:, 'aou'.index(x)] += 1 - u
                mv[:, 'aou'.index(y)] += u
            else:
                mv = np.zeros((nc, 3))
                mv[:, 'aou'.index(vw)] = 1
            mixv[i] = mv[i]
            prev_end, prev = end, pm
        mixv[:np.argmax(mixv.sum(1) > 0)] = mixv[np.argmax(mixv.sum(1) > 0)]
        w = np.hanning(int(.12 * CR) | 1)
        w /= w.sum()
        mixv = np.stack([np.convolve(np.pad(mixv[:, c], len(w) // 2, mode='edge'), w, 'valid')[:nc] for c in range(3)], 1)
        sc = r.normal(1, .035)
        F = sum(mixv[:, i:i + 1] * np.array(cur[k][0]) for i, k in enumerate('aou')) * sc
        G = db(sum(mixv[:, i:i + 1] * np.array(cur[k][1]) for i, k in enumerate('aou')))
        BW = sum(mixv[:, i:i + 1] * np.array(cur[k][2]) for i, k in enumerate('aou')) * 1.25
        F = F * (1 + .012 * np.stack([slow(nc, 3, seed * 71 + p * 5 + c, CR) for c in range(5)], 1))
        pit = np.interp(tc, pt, pv)
        w2 = np.hanning(91)[1:-1]
        pit = np.convolve(np.pad(pit, len(w2) // 2, mode='edge'), w2 / w2.sum(), 'valid')[:nc]
        dyn = np.interp(tc, at, av)
        dyn = np.convolve(np.pad(dyn, len(w2) // 2, mode='edge'), w2 / w2.sum(), 'valid')[:nc]
        vib = np.sin(2 * np.pi * np.cumsum(r.uniform(5.0, 6.0) * (1 + .06 * slow(nc, 2, seed * 73 + p, CR))) / CR + r.uniform(0, 6.28))
        dep = r.uniform(12, 30) * smoothstep(dyn * 1.5) * (1 + .4 * slow(nc, 1, seed * 79 + p, CR))
        cents = dep * vib + 5 * slow(nc, 3, seed * 83 + p, CR)
        f = mtof(pit + cents / 100)
        # sopranos tune the first formant up to the pitch
        F[:, 0] = np.maximum(F[:, 0], f * 1.04)
        F[:, 1] = np.maximum(F[:, 1], F[:, 0] * 1.25)
        amp = np.maximum(dyn, 0) ** 1.5 * ex * (1 + .08 * slow(nc, 4, seed * 89 + p, CR)) * (1 + .06 * vib)
        tilt = 350 * 7 ** np.clip(dyn * ex ** .3, 0, 1.1)
        asp = .040 + .05 * (1 - np.clip(dyn, 0, 1))
        voice_kernel(out[p % groups], f, amp, tilt, asp, F, G, BW, SAW, seed * 97 + p, r.uniform())
    return t0, out * 1.6 / np.sqrt(singers)


# ================================================================ plucked, struck
def harp_note(m, vel, seed, hold=4.0):
    r = rng(seed)
    f0 = float(mtof(m))
    B = 3e-5
    K = int(min(11000 / f0, 60))
    k = np.arange(1, K + 1)
    fk = k * f0 * np.sqrt(1 + B * k * k)
    pos = r.uniform(.36, .46)
    fc = (1100 + 2600 * vel) * (f0 / 262) ** .25
    a = np.abs(np.sin(k * np.pi * pos)) / k ** 1.25 / (1 + (fk / fc) ** 2) ** .8
    a = a + .02 / k
    a *= db(r.normal(0, 1.5, K))
    T = np.clip(3.6 * (262 / f0) ** .55, .5, 6.0)
    tk = T / (1 + .22 * (k - 1) + (fk / 3800) ** 1.6)
    n = ns(min(T * 1.3, hold + .5))
    x = modes(n, fk, a, tk, seed, att=.0007, phase=.2)
    x += .35 * modes(n, fk[:10] * 2 ** (r.normal(0, .8, len(fk[:10])) / 1200), a[:10], tk[:10] * 1.8, seed + 1, att=.004)
    # pluck: skin leaving gut, and the soundbox
    q = ns(.12)
    tt = np.arange(q) / SR
    nz = bp(white(q, seed + 2), 900, 5500, 1) * np.exp(-tt / .006) * .10 * vel
    box = modes(q, np.array([118, 170, 235, 330, 470]), [.6, 1, .8, .5, .3], [.10, .09, .07, .06, .05], seed + 3, att=.0015, phase=0) * .10
    x[:min(q, n)] += (nz + box)[:min(q, n)]
    return x * vel ** 1.2 * .55 * fade(n, 0, .25)


def glock_note(m, vel, seed, soft=False):
    r = rng(seed)
    f0 = float(mtof(m))
    ra = np.array([1, 2.756, 5.404, 8.933, 13.34])
    if soft:
        a, t, n = np.array([1, .12, .035, .01, 0]), np.array([2.2, .8, .3, .1, .05]), ns(2.6)
    else:
        a, t, n = np.array([1, .42, .18, .08, .03]), np.array([3.2, 1.6, .7, .3, .15]), ns(3.2)
    T = (1200 / f0) ** .35
    x = modes(n, f0 * ra, a * db(r.normal(0, 1.5, 5)), t * T, seed, att=.0004 if not soft else .0015, phase=.3)
    x += .12 * modes(n, f0 * ra[:2] * 2 ** (np.array([1.6, -1.3]) / 1200), a[:2], t[:2] * T * 1.3, seed + 1, att=.002)
    q = ns(.03)
    x[:q] += hp(white(q, seed + 2), 3500) * np.exp(-np.arange(q) / SR / .0018) * (.05 if not soft else .012)
    return x * vel ** 1.3 * .4 * fade(n, 0, .3)


def bowed_bar(m, dur, vel, seed):
    """Bowed vibraphone bar: slow stick-slip swell, 1:4:10 tuning, gentle beating."""
    r = rng(seed)
    n = ns(dur + 2.4)
    t = np.arange(n) / SR
    f0 = float(mtof(m))
    e = smoothstep(t / (dur * .75)) ** 1.4 * np.where(t > dur, np.exp(-(t - dur) / .75), 1)
    x = np.zeros((2, n))
    for ch in range(2):
        for ra, a in ((1, 1), (4.01, .06), (9.9, .012), (1.0012, .18)):
            x[ch] += a * np.sin(2 * np.pi * f0 * ra * t + r.uniform(0, 6.28)) * (1 + .12 * slow(n, 4, seed + ch + int(ra * 10)))
    nz = bp(white(n, seed + 9), f0 * .97, f0 * 1.03, 1) * .25
    return (x + nz) * e * vel * fade(n, .03, .5) * .4


def timp(m, vel, seed, tail=3.0):
    r = rng(seed)
    f0 = float(mtof(m))
    ra = np.array([1.0, 1.504, 1.742, 2.0, 2.245, 2.494, 2.8, 2.98, 3.46, 3.9, 4.4])
    a = np.array([1.0, .62, .25, .40, .18, .22, .10, .12, .08, .05, .04]) * db(r.normal(0, 2, 11))
    a *= np.array([1, 1, .8, 1, .8, 1, 1, 1, 1, 1, 1]) * (.35 + .65 * vel) ** (np.arange(11) * .16)
    t = np.array([2.9, 2.3, .9, 1.7, .6, 1.2, .5, .8, .4, .3, .25]) * (100 / f0) ** .25
    n = ns(tail)
    x = modes(n, f0 * ra, a, t, seed, att=.0025, phase=.4)
    x += modes(n, f0 * np.array([.52, .83, 1.36]), [.35, .5, .3], [.16, .22, .20], seed + 1, att=.002, phase=0)
    q = ns(.06)
    tq = np.arange(q) / SR
    x[:q] += lp(white(q, seed + 2), 600 + 1800 * vel, 2) * np.exp(-tq / .007) * .5 * vel
    return x * vel ** 1.4 * .5 * fade(n, 0, .5)


def bassdrum(vel, seed, tail=2.6, tune=1.0):
    n = ns(tail)
    t = np.arange(n) / SR
    f = np.array([38, 61, 84, 104, 131, 162, 205, 260]) * tune
    x = modes(n, f, [1, .8, .5, .4, .25, .18, .1, .06], [1.5, 1.1, .7, .55, .4, .3, .22, .18], seed, att=.004, phase=.3)
    q = ns(.1)
    x[:q] += lp(white(q, seed + 1), 900, 2) * np.exp(-np.arange(q) / SR / .012) * .5
    return x * vel * .6 * fade(n, 0, .6)


def cymbal_ir(seed, lo=240, hi=15500, K=900, t_lo=6.5, t_hi=1.6, L=6.0, bloom=.0):
    r = rng(seed)
    n = ns(L)
    u = np.sort(r.uniform(0, 1, K))
    f = (lo ** .55 + (hi ** .55 - lo ** .55) * u) ** (1 / .55)
    t = np.interp(np.log2(f), np.log2([lo, 1200, 5000, hi]), [t_lo, t_lo * .8, t_lo * .45, t_hi])
    out = []
    for ch in range(2):
        a = r.normal(0, 1, K) * db(np.interp(np.log2(f), np.log2([lo, 500, 2000, 6000, hi]), [-8, -2, 0, 1, -5]))
        out.append(modes(n, f, a, t * r.uniform(.7, 1.2, K), seed + ch, att=.0005 + bloom * (f / 6000)))
    out = np.stack(out) * fade(n, 0, 2.0)
    return out / np.sqrt((out ** 2).sum() / 2)
