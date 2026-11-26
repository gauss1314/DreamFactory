"""The Lighthouse Keeper: score and effects.

build(ctx) -> dict(music=(2, N) float array at 48 kHz, sfx=(2, N), cues=[{name, t, stem, band}])
ctx: film, duration, shots [{id, start, end, scene}], events {'s2.pour': 12.0, ...}, eventList.

Music is in sound_score.py, effects in sound_sfx.py (generators in sound_fx.py), plumbing in sound_mix.py.
The parts run in worker processes; here they are summed per (stem, epoch, room), put through their rooms and mixed.
"""
import os
import sys
import time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
for _k in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMBA_NUM_THREADS'):
    os.environ.setdefault(_k, '1')

import core  # noqa: E402
from core import *  # noqa: E402,F401
import rooms  # noqa: E402

SR = 48000

# every declared event: which stem carries its onset, and the band where that onset is plainest
CUES = {
    's2.hatch': ('sfx', [1500, 5000]),       # paw kicks the iron hatch rim
    's2.pour': ('sfx', [300, 900]),          # first gulp of oil
    's2.wipe': ('sfx', [1500, 5000]),        # scarf touches the glass
    's3.blink': ('sfx', [2500, 7000]),       # lids: a tiny tick
    's3.flash': ('music', [150, 600]),        # the uneasy low piano note
    's4.lightning': ('sfx', [1500, 6000]),   # the crack of a near strike
    's4.crash': ('sfx', [40, 160]),          # wave boom on the rock
    's5.window': ('sfx', [150, 1200]),       # casement slams the wall
    's5.out': ('sfx', [120, 600]),           # the flame's last puff
    's6.horn': ('sfx', [300, 1200]),          # the boat's uneasy horn
    's6.hit': ('sfx', [40, 200]),            # the wave on the bow
    's7.shut': ('sfx', [60, 300]),           # window pushed home
    's7.match': ('sfx', [2500, 8000]),       # match head on the striker
    's7.catch': ('sfx', [80, 400]),          # the wick takes the flame
    's7.bloom': ('music', [300, 1200]),        # the chord arrives, low strings and drums
    's8.sweep': ('sfx', [700, 3000]),      # the beam's glint crossing the lens (music: crash on the peak note)
    's8.turn': ('sfx', [400, 2000]),       # the bow biting into the turn (music: timpani and drum)
    's9.horn.1': ('sfx', [450, 1400]),        # friendly horn, first blast
    's9.horn.2': ('sfx', [450, 1400]),        # and the second
    's9.wave': ('sfx', [400, 2000]),         # a small wave laps the shore
    's9.lampoff': ('music', [380, 560]),     # one piano note, Bb4
}

# stem levels and rides (absolute seconds, dB)
MUSIC_DB = 0.0
SFX_DB = 0.0
# per-shot faders (dB); music ramps across a cut over RAMP seconds, effects step with the cut
SHOT_M = dict(s1=6, s2=9, s3=5, s4=-2, s5=4, s6=6, s7=-1, s8=-2.5, s9=8)
SHOT_S = dict(s1=10, s2=10, s3=10, s4=6, s5=7, s6=9, s7=12, s8=4, s9=10)
RAMP = .4
END_FADE = (68.0, 70.0)
START_FADE = (0.0, 1.5)


def _job(name, E):
    import sound_score
    import sound_sfx
    mod, fn = name.split('.')
    m = {'score': sound_score, 'sfx': sound_sfx}[mod]
    t = time.time()
    d = getattr(m, fn)(E)
    return name, d, time.time() - t


def parts_list():
    import sound_score
    import sound_sfx
    jobs = ['score.' + f.__name__ for f in sound_score.PARTS] + ['sfx.' + f.__name__ for f in sound_sfx.PARTS]
    heavy = ['score.m_s8a', 'score.m_s8b', 'score.m_s4', 'score.m_s7', 'score.m_s5', 'score.m_dark']
    return [j for j in heavy if j in jobs] + [j for j in jobs if j not in heavy]


def render_parts(E, workers=4, log=print):
    import multiprocessing as mp
    from concurrent.futures import ProcessPoolExecutor
    jobs = parts_list()
    acc, tim = {}, {}
    if workers > 1:
        ctx = mp.get_context('fork')
        with ProcessPoolExecutor(workers, mp_context=ctx) as ex:
            res = list(ex.map(_job, jobs, [E] * len(jobs)))
    else:
        res = [_job(j, E) for j in jobs]
    for name, d, t in res:
        tim[name] = t
        for k, v in d.items():
            acc.setdefault(k, []).append(v)
    log('parts: ' + ', '.join(f'{k.split(".")[1]} {v:.1f}s' for k, v in sorted(tim.items(), key=lambda a: -a[1])))
    return acc


def rides(shots):
    m, x = [], []
    for k, sh in enumerate(shots):
        a, b, i = sh['start'], sh['end'], sh['id']
        m += [(a + (RAMP / 2 if k else 0), SHOT_M.get(i, 0)), (b - (RAMP / 2 if k < len(shots) - 1 else 0), SHOT_M.get(i, 0))]
        x += [(a, SHOT_S.get(i, 0)), (b - 1e-4, SHOT_S.get(i, 0))]
    return m, x


def mixdown(acc, N, shots):
    from sound_mix import ep_window
    irs = rooms.all_rooms()
    bus = {'music': np.zeros((2, N)), 'sfx': np.zeros((2, N))}
    for (stem, e, room), segs in acc.items():
        i0, i1, w = ep_window(stem, e, N)
        buf = np.zeros((2, i1 - i0))
        for a, x in segs:
            lo, hi = max(a, i0), min(a + x.shape[1], i1)
            if hi > lo:
                buf[:, lo - i0:hi - i0] += x[:, lo - a:hi - a]
        if room != 'dry':
            h = irs[room]
            buf = np.stack([conv(buf[c], h[c])[:buf.shape[1]] for c in (0, 1)])
        bus[stem][:, i0:i1] += buf * w
    rm, rs = rides(shots)
    bus['music'] *= float(db(MUSIC_DB)) * curve(rm, N, kind='db')
    bus['sfx'] *= float(db(SFX_DB)) * curve(rs, N, kind='db')
    for k in bus:
        bus[k] = hp(bus[k], 22, 2)
    bus['music'] = eq(bus['music'], 9000, 1.5, .7, 'hs')
    # one centre for the low end
    for k, f in dict(music=130, sfx=95).items():
        mid, side = (bus[k][0] + bus[k][1]) / 2, (bus[k][0] - bus[k][1]) / 2
        side = hp(side, f, 2) * .9
        bus[k] = np.stack([mid + side, mid - side])
    t = np.arange(N) / SR
    edge = smoothstep((t - START_FADE[0]) / (START_FADE[1] - START_FADE[0])) ** .5
    edge *= np.cos(np.pi / 2 * np.clip((t - END_FADE[0]) / (END_FADE[1] - END_FADE[0]), 0, 1)) ** 2
    for k in bus:
        bus[k] *= edge
    return bus


def finish(bus, log=print):
    """Bring the mix to -14 LUFS under a soft limiter (the same gain on both stems), so the driver's limiter has no work."""
    mix = bus['music'] + bus['sfx']
    I0 = core.loudness(mix)[0]
    g = float(db(-14.0 - I0))
    lg = core.limiter_gain(mix * g, -2.6, look=.006, rel=.25)
    red = -20 * np.log10(lg.min())
    hit = np.flatnonzero(lg < .84)
    secs = sorted(set((hit // (SR // 10)).tolist()))
    log(f'pre {I0:.1f} LUFS, gain {20 * np.log10(g):+.1f} dB, limiter max {red:.1f} dB, >1.5 dB at {[round(s / 10, 1) for s in secs][:30]}')
    return {k: v * g * lg for k, v in bus.items()}


def build(ctx):
    T0 = time.time()
    log = lambda s: print('[sound] ' + s, file=sys.stderr)
    E = dict(ctx['events'])
    N = int(round(ctx['duration'] * SR))
    acc = render_parts(E, int(os.environ.get('LK_SOUND_JOBS', 4)), log)
    bus = mixdown(acc, N, ctx['shots'])
    out = finish(bus, log)
    cues = []
    for name, t in sorted(E.items(), key=lambda a: a[1]):
        if name in CUES:
            stem, band = CUES[name]
            cues.append(dict(name=name, t=float(t), stem=stem, band=list(band)))
        else:
            log(f'warning: event {name} at {t:.2f}s has no sound')
    log(f'build {time.time() - T0:.1f}s')
    return dict(music=out['music'].astype(np.float32), sfx=out['sfx'].astype(np.float32), cues=cues)
