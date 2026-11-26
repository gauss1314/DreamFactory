"""Shared DSP: time curves, noise, filters, synthesised rooms, panning, meters, limiter."""
import os
import numpy as np
import numba as nb
from scipy import signal, fft as sfft

SR = 48000
# the film's length: the driver sets it before importing
DUR = float(os.environ.get('DF_AUDIO_DUR', 65.0))
N = int(SR * DUR)
FPS = 24.0


def rng(seed):
    return np.random.default_rng(int(seed) & 0x7FFFFFFF)


def db(x):
    return 10.0 ** (np.asarray(x, float) / 20.0)


def ns(t):
    return int(round(t * SR))


def mtof(m):
    return 440.0 * 2.0 ** ((np.asarray(m, float) - 69.0) / 12.0)


_NN = dict(C=0, D=2, E=4, F=5, G=7, A=9, B=11)


def nt(name):
    """'F#4' / 'Bb3' -> midi."""
    s = name
    v = _NN[s[0]]
    i = 1
    while s[i] in '#b':
        v += 1 if s[i] == '#' else -1
        i += 1
    return v + 12 * (int(s[i:]) + 1)


# ---------------------------------------------------------------- curves
def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def curve(pts, n, t0=0.0, rate=SR, kind='lin'):
    """Breakpoint curve sampled at `rate`; pts [(t,v),...] in absolute seconds. kind: lin | db (v are dB) | cos."""
    t = t0 + np.arange(n) / rate
    p = np.asarray(pts, float)
    if kind == 'cos':
        idx = np.clip(np.searchsorted(p[:, 0], t, side='right') - 1, 0, len(p) - 2)
        a, b = p[idx], p[idx + 1]
        u = smoothstep((t - a[:, 0]) / np.maximum(b[:, 0] - a[:, 0], 1e-9))
        return a[:, 1] + (b[:, 1] - a[:, 1]) * u
    v = np.interp(t, p[:, 0], p[:, 1])
    return db(v) if kind == 'db' else v


def slow(n, hz, seed, rate=SR, lo=-1.0, hi=1.0):
    """Smooth random curve: new target `hz` times a second, cubic interpolated (Catmull-Rom)."""
    r = rng(seed)
    step = rate / float(hz)
    k = int(n / step) + 5
    p = r.uniform(lo, hi, k)
    x = np.arange(n) / step + 1
    i = x.astype(int)
    u = x - i
    p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[np.minimum(i + 2, k - 1)]
    return .5 * (2 * p1 + (p2 - p0) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (3 * p1 - p0 - 3 * p2 + p3) * u ** 3)


def fade(n, a=.002, b=.005, rate=SR):
    """Raised cosine in / out window."""
    w = np.ones(n)
    na, nbb = min(int(a * rate), n // 2), min(int(b * rate), n // 2)
    if na > 0:
        w[:na] = .5 - .5 * np.cos(np.pi * np.arange(na) / na)
    if nbb > 0:
        w[-nbb:] = .5 + .5 * np.cos(np.pi * np.arange(nbb) / nbb)
    return w


# ---------------------------------------------------------------- noise and filters
def white(n, seed):
    return rng(seed).standard_normal(n)


def shaped(n, seed, fpts, gdb):
    """Gaussian noise with an arbitrary log-frequency magnitude curve (dB), unit-ish RMS before shaping."""
    m = sfft.next_fast_len(n, real=True)
    X = sfft.rfft(rng(seed).standard_normal(m))
    f = np.fft.rfftfreq(m, 1 / SR)
    g = db(np.interp(np.log2(np.maximum(f, 1.0)), np.log2(np.asarray(fpts, float)), np.asarray(gdb, float)))
    return sfft.irfft(X * g, m)[:n]


def bp(x, lo, hi, order=2):
    if lo and hi and hi < SR / 2 * .98:
        s = signal.butter(order, [lo, hi], 'bandpass', fs=SR, output='sos')
    elif lo and not hi:
        s = signal.butter(order, lo, 'highpass', fs=SR, output='sos')
    elif lo:
        s = signal.butter(order, lo, 'highpass', fs=SR, output='sos')
    else:
        s = signal.butter(order, hi, 'lowpass', fs=SR, output='sos')
    return signal.sosfilt(s, x, axis=-1)


def lp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, 'lowpass', fs=SR, output='sos'), x, axis=-1)


def hp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, 'highpass', fs=SR, output='sos'), x, axis=-1)


def eq(x, f, gain, q=.7, kind='peak'):
    """RBJ biquad."""
    A = 10 ** (gain / 40)
    w = 2 * np.pi * f / SR
    al = np.sin(w) / (2 * q)
    c = np.cos(w)
    if kind == 'peak':
        b = [1 + al * A, -2 * c, 1 - al * A]
        a = [1 + al / A, -2 * c, 1 - al / A]
    elif kind == 'hs':
        s = 2 * np.sqrt(A) * al
        b = [A * ((A + 1) + (A - 1) * c + s), -2 * A * ((A - 1) + (A + 1) * c), A * ((A + 1) + (A - 1) * c - s)]
        a = [(A + 1) - (A - 1) * c + s, 2 * ((A - 1) - (A + 1) * c), (A + 1) - (A - 1) * c - s]
    else:
        s = 2 * np.sqrt(A) * al
        b = [A * ((A + 1) - (A - 1) * c + s), 2 * A * ((A - 1) - (A + 1) * c), A * ((A + 1) - (A - 1) * c - s)]
        a = [(A + 1) + (A - 1) * c + s, -2 * ((A - 1) + (A + 1) * c), (A + 1) + (A - 1) * c - s]
    b, a = np.array(b) / a[0], np.array(a) / a[0]
    return signal.lfilter(b, a, x, axis=-1)


@nb.njit(cache=True, fastmath=True)
def svf_bp(x, fc, q, mode):
    """Time-varying state variable filter (TPT). fc per sample, q per sample. mode 0 band (unit peak), 1 low, 2 high."""
    y = np.empty_like(x)
    s1 = 0.0
    s2 = 0.0
    for i in range(x.shape[0]):
        g = np.tan(np.pi * min(fc[i], 22000.0) / 48000.0)
        k = 1.0 / q[i]
        a1 = 1.0 / (1.0 + g * (g + k))
        a2 = g * a1
        a3 = g * a2
        v3 = x[i] - s2
        v1 = a1 * s1 + a2 * v3
        v2 = s2 + a2 * s1 + a3 * v3
        s1 = 2.0 * v1 - s1
        s2 = 2.0 * v2 - s2
        if mode == 0:
            y[i] = v1 * k
        elif mode == 1:
            y[i] = v2
        else:
            y[i] = x[i] - k * v1 - v2
    return y


def arr(v, n):
    return np.full(n, float(v)) if np.isscalar(v) else np.asarray(v, float)


def svf(x, fc, q=1.0, kind='bp'):
    n = len(x)
    return svf_bp(np.asarray(x, float), arr(fc, n), arr(q, n), {'bp': 0, 'lp': 1, 'hp': 2}[kind])


def conv(x, h):
    return signal.oaconvolve(x, h, axes=-1)


# ---------------------------------------------------------------- panning
def pan2(x, p):
    """Equal-power pan with a small inter-channel delay. p in -1..1, scalar or per-sample curve."""
    if np.isscalar(p):
        a = (p + 1) * np.pi / 4
        L, R = x * np.cos(a) * 1.4142, x * np.sin(a) * 1.4142
        d = int(abs(p) * 22)
        if d:
            if p > 0:
                L = np.concatenate([np.zeros(d), L[:-d]]) if len(L) > d else L
            else:
                R = np.concatenate([np.zeros(d), R[:-d]]) if len(R) > d else R
        return np.stack([L, R])
    a = (np.asarray(p) + 1) * np.pi / 4
    return np.stack([x * np.cos(a) * 1.4142, x * np.sin(a) * 1.4142])


def widen(x2, seed, amt=.35):
    """Decorrelate L/R with short random allpass-like diffusers (keeps spectrum)."""
    r = rng(seed)
    out = []
    for ch in range(2):
        m = 2048
        ph = r.uniform(-np.pi, np.pi, m // 2 + 1)
        ph[0] = ph[-1] = 0
        f = np.linspace(0, SR / 2, m // 2 + 1)
        ph *= amt * smoothstep((f - 150) / 900)
        h = np.roll(np.fft.irfft(np.exp(1j * ph)), m // 8) * 1.0
        out.append(conv(x2[ch], h)[m // 8:m // 8 + x2.shape[1]])
    return np.stack(out)


class Track:
    """Absolute-time stereo accumulator."""

    def __init__(self, t0=0.0, t1=DUR):
        self.t0, self.i0 = t0, ns(t0)
        self.x = np.zeros((2, ns(t1) - ns(t0)), np.float64)

    def add(self, t, x, g=1.0, p=0.0):
        if x.ndim == 1:
            x = pan2(x, p)
        i = ns(t) - self.i0
        a, b = max(i, 0), min(i + x.shape[1], self.x.shape[1])
        if b > a:
            self.x[:, a:b] += g * x[:, a - i:b - i]
        return self

    def mono(self):
        return self.x.mean(0)


# ---------------------------------------------------------------- rooms
_BF = np.array([31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000])


def late_ir(seed, rt, length, gain_db=None, onset=.035, pre=0.0, corr_hz=220.0, rough=0.0):
    """Stereo late tail: gaussian noise, octave-band decays, frequency dependent inter-channel coherence."""
    n = int(length * SR)
    t = np.arange(n) / SR
    r = rng(seed)
    f = np.fft.rfftfreq(n, 1 / SR)
    lf = np.log2(np.maximum(f, 1))
    c, a, b = (sfft.rfft(r.standard_normal(n)) for _ in range(3))
    coh = 1.0 / (1 + (f / corr_hz) ** 2)
    XL = c * np.sqrt(coh) + a * np.sqrt(1 - coh)
    XR = c * np.sqrt(coh) + b * np.sqrt(1 - coh)
    g = np.zeros(10) if gain_db is None else np.asarray(gain_db, float)
    out = np.zeros((2, n))
    for i, fb in enumerate(_BF):
        d = lf - np.log2(fb)
        w = np.where(np.abs(d) < 1, np.cos(d * np.pi / 2) ** 2, 0)
        if i == 0:
            w = np.where(d < 0, 1, w)
        if i == 9:
            w = np.where(d > 0, 1, w)
        e = np.exp(-6.9078 * t / rt[i]) * db(g[i])
        out[0] += sfft.irfft(XL * w, n) * e
        out[1] += sfft.irfft(XR * w, n) * e
    out *= (1 - np.exp(-t / onset)) ** 2
    if rough:
        out *= 1 + rough * slow(n, 35, seed + 7) * np.exp(-t / .25)
    out *= fade(n, 0, length * .15)
    out /= np.sqrt((out ** 2).sum() / 2)
    p = ns(pre)
    return np.concatenate([np.zeros((2, p)), out], 1) if p else out


def _sinc_add(buf, pos, amp):
    i = int(np.floor(pos))
    fr = pos - i
    k = np.arange(-7, 9)
    w = np.sinc(k - fr) * (0.5 + 0.5 * np.cos(np.pi * (k - fr) / 8.5))
    a, b = i - 7, i + 9
    if a >= 0 and b < len(buf):
        buf[a:b] += amp * w


def seat_ir(src, dims, seed, refl=.78, order=3, mics=None, length=.16, er_db=0.0, lpf=9000.0, depth=1.0):
    """Direct sound + image-source early reflections for a source at `src` in a shoebox, seen by an angled stereo pair.
    Direct is normalised to unit energy and time aligned to 0; reflections keep their physical delays."""
    r = rng(seed)
    if mics is None:
        mics = [(-1.1, 0, 2.8, -38.0), (1.1, 0, 2.8, 38.0)]
    n = int(length * SR)
    bufs = [np.zeros((2, n)) for _ in range(order + 1)]
    Lx, Ly, Lz = dims
    off = np.array([Lx / 2, 5.0, 0.0])
    s = np.array(src, float) + off
    ms = [(np.array(m[:3]) + off, np.deg2rad(m[3])) for m in mics]
    d0 = min(np.linalg.norm(s - m) for m, _ in ms)
    for a in range(-order, order + 1):
        for b in range(-order, order + 1):
            for c in range(-order, order + 1):
                for u in range(2):
                    for v in range(2):
                        for w in range(2):
                            q = abs(a - u) + abs(a) + abs(b - v) + abs(b) + abs(c - w) + abs(c)
                            if q > order:
                                continue
                            im = np.array([(1 - 2 * u) * s[0] + 2 * a * Lx, (1 - 2 * v) * s[1] + 2 * b * Ly,
                                           (1 - 2 * w) * s[2] + 2 * c * Lz])
                            if q:
                                im = im + r.normal(0, .35, 3)
                            rr = refl ** q * r.uniform(.75, 1.15) if q else 1.0
                            for ch, (m, az) in enumerate(ms):
                                dv = im - m
                                d = np.linalg.norm(dv)
                                ca = (dv[1] * np.cos(az) + dv[0] * np.sin(az)) / max(np.hypot(dv[0], dv[1]), 1e-6)
                                card = .42 + .58 * ca
                                pos = (d - d0) / 343.0 * SR + 8
                                if pos < n - 12:
                                    _sinc_add(bufs[q][ch], pos, rr * max(card, .08) * d0 / d)
    e = np.sqrt((bufs[0] ** 2).sum() / 2)
    out = bufs[0] / e
    for q in range(1, order + 1):
        h = bufs[q] / e * db(er_db)
        k = int(SR * .0012 * q)
        dif = r.standard_normal(k) * np.exp(-np.arange(k) / (k / 3))
        dif[0] += 1.5
        dif /= np.sqrt((dif ** 2).sum())
        h = np.stack([np.convolve(h[0], dif)[:n], np.convolve(h[1], dif)[:n]])
        out = out + lp(h, lpf / (1 + .55 * (q - 1)), 1) * depth
    return out[:, 8:]


# ---------------------------------------------------------------- meters and limiter
def k_weight(x):
    b1, a1 = [1.53512485958697, -2.69169618940638, 1.19839281085285], [1, -1.69065929318241, .73248077421585]
    b2, a2 = [1.0, -2.0, 1.0], [1, -1.99004745483398, .99007225036621]
    return signal.lfilter(b2, a2, signal.lfilter(b1, a1, x, axis=-1), axis=-1)


def loudness(x):
    """Integrated LUFS (BS.1770-4), short-term max, momentary curve at 100 ms."""
    y = k_weight(x)
    p = (y ** 2).sum(0)
    cs = np.concatenate([[0], np.cumsum(p)])

    def blocks(win, hop):
        w, h = int(win * SR), int(hop * SR)
        i = np.arange(0, len(p) - w + 1, h)
        return (cs[i + w] - cs[i]) / w
    z = blocks(.4, .1)
    L = -0.691 + 10 * np.log10(np.maximum(z, 1e-12))
    g1 = z[L > -70]
    if len(g1) == 0:
        return -99, -99, L
    rel = -0.691 + 10 * np.log10(g1.mean()) - 10
    g2 = z[(L > -70) & (L > rel)]
    st = -0.691 + 10 * np.log10(np.maximum(blocks(3.0, .1), 1e-12))
    return -0.691 + 10 * np.log10(g2.mean()), st.max(), L


def lra(x):
    y = k_weight(x)
    p = (y ** 2).sum(0)
    cs = np.concatenate([[0], np.cumsum(p)])
    w, h = 3 * SR, SR // 10
    i = np.arange(0, len(p) - w + 1, h)
    L = -0.691 + 10 * np.log10(np.maximum((cs[i + w] - cs[i]) / w, 1e-12))
    L = L[L > -70]
    rel = 10 * np.log10(np.mean(10 ** (L / 10))) - 20
    L = L[L > rel]
    return np.percentile(L, 95) - np.percentile(L, 10)


def true_peak(x):
    m = 0.0
    for ch in x:
        m = max(m, np.abs(signal.resample_poly(ch, 4, 1)).max())
    return 20 * np.log10(max(m, 1e-9))


@nb.njit(cache=True)
def _minfilt(g, w):
    n = len(g)
    out = np.empty(n)
    dq = np.empty(n, np.int64)
    h = 0
    t = 0
    for i in range(n):
        while t > h and g[dq[t - 1]] >= g[i]:
            t -= 1
        dq[t] = i
        t += 1
        if dq[h] <= i - w:
            h += 1
        out[i] = g[dq[h]]
    return out


@nb.njit(cache=True)
def _release(g, a):
    out = np.empty(len(g))
    s = 1.0
    for i in range(len(g)):
        s = g[i] if g[i] < s else s + (g[i] - s) * a
        out[i] = s
    return out


def limiter_gain(x, ceil_db=-1.3, look=.005, rel=.14):
    """Look-ahead true-peak limiter: returns a smooth per-sample gain (apply to all stems alike)."""
    n = x.shape[1]
    pk = np.zeros(n)
    for ch in x:
        u = np.abs(signal.resample_poly(ch, 4, 1))[:4 * n].reshape(n, 4).max(1)
        pk = np.maximum(pk, u)
    pk = np.maximum(pk, np.maximum(np.roll(pk, 1), np.roll(pk, -1)))
    c = float(db(ceil_db))
    g = np.minimum(1.0, c / np.maximum(pk, 1e-9))
    w = int(look * SR)
    g = _minfilt(np.concatenate([g, np.ones(w)]), w)[w - 1:][:n]
    g = _release(g, 1 - np.exp(-1 / (rel * SR)))
    win = np.hanning(w + 2)[1:-1]
    win /= win.sum()
    pad = np.concatenate([np.full(w, g[0]), g, np.full(w, g[-1])])
    sm = signal.oaconvolve(pad, win, mode='full')
    # g already looks `w` samples ahead; a causal window of w samples lands the full reduction on the peak
    return np.minimum(sm[w:w + n], 1.0)


def write_wav(path, x):
    import soundfile as sf
    os.makedirs(os.path.dirname(path), exist_ok=True)
    sf.write(path, np.asarray(x.T, np.float32), SR, subtype='FLOAT')
