"""THE LIGHTHOUSE KEEPER, music.

The lamp's theme, Eb major, in 3/4. A question that climbs like a lit wick and settles on the fifth:

    Bb | Eb . F G | F Eb C | Bb - -        (5 | 1 . 2 3 | 2 1 6 | 5)

s2 a lonely felt piano states it; s3 breaks it off after three notes; s4-s5 the storm turns its head to C minor in the
horns (G | C . D Eb); s6 bends it out of shape (G | C . Db E); s7 a chord blooms from nothing; s8 the whole orchestra
sings it to its peak (Bb5) and lets it come home to Eb; s9 the piano says it once more, softly, and the last note waits
until the lamp goes out.
"""
import numpy as np
from core import *
from inst import *
from sound_mix import *


def mel(t_bar1, beat, items, base_v, art=None):
    """[(beat, dur, name[, vel])] relative to bar 1's downbeat -> strings/brass notes."""
    out = []
    for it in items:
        b, d, nm = it[:3]
        v = it[3] if len(it) > 3 else base_v
        o = {} if art is None else dict(art=art)
        out.append((t_bar1 + b * beat, d * beat, K(nm), v, o))
    return out


# ================================================================== s1 night: almost nothing
def m_s1(E):
    out = Out()
    # one far harmonic in the violins as the lamp's beam passes, barely there
    S(out, 'vn1', [(3.2, 4.3, K('Bb5'), (.06, .16), dict(art='harm'))], -14, 11, n=6, sord=True, art='harm',
      expr=[(3.0, -30), (4.5, -6), (6.6, 0), (7.4, -12)], tail=.6)
    S(out, 'vn2', [(4.4, 3.0, K('Eb5'), (.06, .14), dict(art='harm'))], -16, 12, n=6, sord=True, art='harm',
      expr=[(4.2, -30), (5.5, -6), (6.8, 0), (7.4, -14)], tail=.6)
    return out.pack()


# ================================================================== s2 the theme on a lonely felt piano
def m_s2(E):
    out = Out()
    b = .72
    t1 = E['s2.hatch'] + .55 + b          # bar 1 downbeat: the otter is up and walking to the lamp
    M = [(-1, 1, 'Bb4', .40), (0, 1.5, 'Eb5', .46), (1.5, .5, 'F5', .38), (2, 1, 'G5', .44),
         (3, 1, 'F5', .40), (4, 1, 'Eb5', .38), (5, 1, 'C5', .36), (6, 3.2, 'Bb4', .40)]
    L = [(0, 'Eb2', .26, 2.9), (0.02, 'Bb2', .22, 2.8), (1, 'G3', .20, 1.9), (2, 'Bb3', .19, .95),
         (3, 'Ab2', .25, 2.9), (4, 'Eb3', .20, 1.9), (5, 'C4', .18, .95),
         (6, 'Bb2', .24, 4.0), (6.5, 'F3', .19, 3.4), (7, 'Eb4', .18, .95), (8, 'D4', .20, 3.0)]
    notes = [(t1 + x * b, nm, v, d * b + .15) for x, d, nm, v in M] + [(t1 + x * b, nm, v, h * b + .1) for x, nm, v, h in L]
    piano(out, notes, 4.0, 40, peds=((t1 - b - .2, .9), (t1 + 3 * b - .05, .7), (t1 + 6 * b - .05, .7)))
    return out.pack()


# ================================================================== s3 a fragment, cut off by the far lightning
def m_s3(E):
    out = Out()
    fl = E['s3.flash']
    piano(out, [(16.30, 'Bb4', .30, .7), (16.86, 'Eb5', .34, .5), (17.32, 'F5', .34, .38),
                (16.86, 'Ab3', .16, .5), (16.86, 'C4', .15, .5)], 4.0, 70, peds=((16.15, .6),))
    # the uneasy low note: a dark open fifth with a tritone in it, struck once
    piano(out, [(fl, 'C2', .62, 2.6), (fl + .004, 'C1', .40, 2.6), (fl + .012, 'F#2', .34, 2.4)], 6.0, 90, wet=-10)
    S(out, 'cb', [(fl + .05, 1.6, K('C2'), (.08, .38), dict(art='trem'))], -6, 91, n=5, art='trem', expr=[(fl, -20), (19.0, 0)])
    S(out, 'vc', [(fl + .15, 1.5, K('F#2'), (.06, .30), dict(art='trem'))], -9, 92, n=5, art='trem', bright=1.3,
      expr=[(fl, -24), (19.0, 0)])
    return out.pack()


# ================================================================== s4 the storm comes: C minor
def m_s4(E):
    out = Out()
    T0, bar = 19.0, 2.0
    e8 = bar / 8
    # cellos drive in eighths; the bass in quarters
    cel = []
    pats = [['C3', 'G2', 'C3', 'Eb3', 'D3', 'G2', 'C3', 'G2'], ['Ab2', 'Eb2', 'Ab2', 'C3', 'Bb2', 'Eb2', 'Ab2', 'Eb2'],
            ['F2', 'C3', 'F2', 'Ab2', 'G2', 'C3', 'F2', 'C3'], ['G2', 'D3', 'G2', 'B2', 'C3', 'D3', 'B2', 'D3']]
    for k, p in enumerate(pats):
        for j, nm in enumerate(p):
            v = .52 + .07 * k + (.12 if j % 4 == 0 else 0)
            cel.append((T0 + k * bar + j * e8, e8 * .85, K(nm), v, dict(art='marc' if j % 4 == 0 else 'spic')))
    ex = [(19.0, -10), (21.0, -5), (23.0, -2), (25.0, 0), (27.0, 1)]
    S(out, 'vc', cel, -1, 120, art='spic', bright=1.15, expr=ex)
    S(out, 'vla', [(a, b, m + 12, v * .8, o) for a, b, m, v, o in cel if a >= 23.0], -6, 121, n=6, art='spic', expr=ex)
    bass = []
    for k, ms in enumerate((['C2', 'C2', 'G1', 'C2'], ['Ab1', 'Ab1', 'Eb1', 'Ab1'], ['F1', 'F1', 'C2', 'F1'], ['G1', 'G1', 'D2', 'G1'])):
        for j, nm in enumerate(ms):
            bass.append((T0 + k * bar + j * bar / 4, bar / 4 * .9, K(nm), .6 + .07 * k, dict(art='det')))
    S(out, 'cb', bass, 0, 122, art='det', expr=ex)
    # tremolo sul ponticello chords, each bar swelling
    ch = [('G4', 'C5', 'Eb5'), ('Ab4', 'C5', 'Eb5'), ('F4', 'Ab4', 'C5'), ('G4', 'B4', 'D5')]
    for v_, (nm, sd) in enumerate((('vn2', 123), ('vn1', 124), ('vn1', 125))):
        S(out, nm, [(T0 + k * bar, bar * .97, K(ch[k][v_]) + (12 if nm == 'vn1' and v_ == 2 else 0), (.18 + .05 * k, .45 + .08 * k), dict(art='trem'))
                    for k in range(4)], -7, sd, n=7, art='trem', bright=1.35, expr=ex)
    # horns: the theme's head turned to C minor, then a step higher, then the dominant held
    hn = [(20.5, .5, K('G3'), .62, dict(art='ten')), (21.0, .75, K('C4'), (.70, .74), dict(art='leg')), (21.75, .25, K('D4'), .72, dict(art='leg')),
          (22.0, 1.0, K('Eb4'), (.78, .6), dict(art='leg')),
          (22.75, .25, K('Bb3'), .6, dict(art='ten')), (23.0, .75, K('D4'), (.72, .76), dict(art='leg')), (23.75, .25, K('Eb4'), .76, dict(art='leg')),
          (24.0, 1.0, K('F4'), (.8, .84), dict(art='leg')), (25.0, 2.0, K('G4'), (.85, .95), dict(art='leg'))]
    BRS(out, 'horn', hn, -1, 126, expr=[(20, 0), (27, 2)])
    BRS(out, 'horn', [(a, b, m - 12, v, o) for a, b, m, v, o in hn], -6, 127, n=2)
    BRS(out, 'tbn', [(23.0, 2.0, K('F2'), (.4, .6)), (25.0, 2.0, K('G2'), (.55, .8))], -8, 128, n=2, art='swell')
    BRS(out, 'tbn', [(23.0, 2.0, K('C3'), (.4, .6)), (25.0, 2.0, K('D3'), (.55, .8))], -9, 129, n=2, art='swell')
    BRS(out, 'tuba', [(25.0, 2.0, K('G1'), (.5, .8))], -8, 130)
    # timpani: a roll that grows out of the dark, then downbeats, then the dominant roll
    roll(out, 'timp', 19.0, 20.95, lambda v, s: timp(K('C2'), v, s, 1.4), .08, .45, -6, seed=740)
    for k, t in enumerate((21.0, 21.5, 22.0, 23.0, 23.5, 24.0, 24.5)):
        hit(out, 'timp', t, timp(K('C2') if t < 23 else K('F2') if t < 25 else K('G2'), .55 + .05 * k, 760 + k, 1.6), -5)
    roll(out, 'timp', 25.0, 27.0, lambda v, s: timp(K('G2'), v, s, 1.4), .25, .70, -5, seed=780)
    return out.pack()


# ================================================================== s5 the window, the flame, and the cut
def m_s5(E):
    out = Out()
    w, o = E['s5.window'], E['s5.out']
    # the storm's chord falls onto C with a Db above it as the latch goes
    for nm, ms, g in (('cb', ['C2'], 0), ('vc', ['C3', 'G2'], 0), ('vla', ['Db4', 'G3'], -3), ('vn2', ['Db5', 'G4'], -3), ('vn1', ['C6', 'Db6'], -5)):
        for j, m in enumerate(ms):
            S(out, nm, [(w, o - w, K(m), (.95, .55), dict(art='marc' if nm in ('cb', 'vc') else 'trem'))], g, 140 + len(nm) * 3 + j,
              n=PL[nm] // len(ms) + 1, art='trem', bright=1.2, expr=[(w - .1, 0), (w + .3, -2), (w + 1.0, -6), (o - 1.0, -4), (o, 2)], tail=.3)
    # before: the dominant from s4 rolls on into the room
    S(out, 'vn1', [(27.0, 1.45, K('D6'), (.4, .55), dict(art='trem'))], -8, 150, n=7, art='trem', bright=1.3)
    S(out, 'vn2', [(27.0, 1.45, K('B5'), (.4, .55), dict(art='trem'))], -8, 151, n=7, art='trem', bright=1.3)
    S(out, 'vla', [(27.0, 1.45, K('G4'), (.4, .55), dict(art='trem'))], -6, 152, n=6, art='trem')
    S(out, 'cb', [(27.0, 1.45, K('G1'), (.55, .6))], -2, 153, n=5)
    roll(out, 'timp', 27.0, 28.45, lambda v, s: timp(K('G2'), v, s, 1.0), .6, .4, -6, seed=800, shape=.8)
    BRS(out, 'tbn', [(w, .5, K('C2'), .95, dict(art='marc'))], -4, 154, n=3)
    BRS(out, 'tbn', [(w, .5, K('Db3'), .95, dict(art='marc'))], -6, 155, n=2)
    BRS(out, 'horn', [(w, .4, K('Db4'), .9, dict(art='marc'))], -4, 156, n=3)
    hit(out, 'timp', w, timp(K('C2'), 1.0, 157, 2.0), -2)
    hit(out, 'bd', w, bassdrum(.9, 158), -2)
    # the flame struggling: a violin line flickers up by semitones, tremolo, faster and faster
    up = ['G5', 'Ab5', 'A5', 'Bb5', 'B5', 'C6', 'C#6', 'D6']
    t, dt = w + .5, .26
    fl = []
    for i, m in enumerate(up):
        if t > o - .05:
            break
        fl.append((t, dt, K(m), .3 + .06 * i, dict(art='trem')))
        t += dt
        dt *= .93
    S(out, 'vn1', fl, -6, 160, n=8, art='trem', bright=1.4)
    S(out, 'vla', [(a, b, m - 17, v, x) for a, b, m, v, x in fl], -8, 161, n=6, art='trem', bright=1.4)
    roll(out, 'timp', o - 1.2, o, lambda v, s: timp(K('C2'), v, s, 1.0), .2, .7, -5, seed=820)
    return out.pack()


# ================================================================== dark, then the lost boat (epoch 1)
def m_dark(E):
    out = Out()
    o = E['s5.out']
    # the one very low sound left in the dark
    S(out, 'cb', [(o + .3, 34.6 - o - .3, K('C1'), (.25, .32))], 2, 170, n=4, ep=1, sord=True, expr=[(o, -40), (o + 1.2, -6), (33.5, 0), (34.5, 2)], tail=.4)
    S(out, 'vc', [(o + .8, 34.6 - o - .8, K('C2'), (.12, .2), dict(art='harm'))], -8, 171, n=3, ep=1, sord=True, art='harm',
      expr=[(o, -40), (o + 1.8, -10), (34.5, 0)], tail=.4)
    # s6: a cluster in the high violins over the tritone, swelling around the horn and the wave
    h, x = E['s6.horn'], E['s6.hit']
    ex = [(34.0, -12), (35.5, -6), (h, -3), (h + .6, -8), (x - .4, -2), (x + .3, 0), (39.6, -10), (40.0, -30)]
    for nm, m, sd in (('vn1', 'B5', 172), ('vn1', 'C6', 173), ('vn2', 'C#6', 174), ('vn2', 'F5', 175), ('vla', 'E4', 176), ('vla', 'F4', 177)):
        S(out, nm, [(34.0, 5.8, K(m), (.3, .45), dict(art='trem'))], -7, sd, n=6, ep=1, art='trem', bright=1.5, expr=ex, tail=.2)
    S(out, 'vc', [(34.0, 5.8, K('F#2'), (.45, .55))], -2, 178, n=6, ep=1, expr=ex, tail=.2)
    S(out, 'cb', [(34.0, 5.8, K('C1'), (.5, .6))], 0, 179, n=5, ep=1, expr=ex, tail=.2)
    # the theme's head, lost: G | C . Db E, stopped horns, far
    BRS(out, 'horn', [(36.9, .4, K('G3'), .5, dict(art='ten')), (37.3, .6, K('C4'), (.55, .6), dict(art='leg')), (37.9, .2, K('Db4'), .6, dict(art='leg')),
                      (38.1, .9, K('E4'), (.62, .3), dict(art='leg'))], -8, 180, n=3, ep=1)
    for k, (t, v) in enumerate(((34.9, .35), (35.75, .45), (h + .02, .5), (37.6, .4), (x, .8), (39.1, .45))):
        hit(out, 'timp', t, timp(K('C2') if k % 2 == 0 else K('F#2'), v, 190 + k, 1.6), -6, ep=1)
    return out.pack()


# ================================================================== s7 relit: a chord out of nothing
def m_s7(E):
    out = Out()
    c, bl = E['s7.catch'], E['s7.bloom']
    up = [(c + .1, -40), (c + .8, -24), (bl - .6, -10), (bl - .16, -3), (bl - .04, -26), (bl - .005, -30), (bl, 0), (bl + 1.2, 0), (48.4, -3)]
    # only the high strings rise: nothing low may sound before the bloom
    S(out, 'vn1', [(c + .1, bl - c - .1, K('D5'), (.18, .65)), (bl, 1.4, K('Eb5'), (.8, .6))], 1, 200, ep=2, expr=up, tail=.5)
    S(out, 'vn1', [(c + .3, bl - c - .3, K('Bb5'), (.15, .6), dict(art='trem')), (bl, 1.4, K('G5'), (.75, .55))], -4, 201, n=8, ep=2, expr=up, tail=.5)
    S(out, 'vn2', [(c + .2, bl - c - .2, K('F5'), (.16, .62)), (bl, 1.4, K('G5'), (.8, .6))], -1, 202, ep=2, expr=up, tail=.5)
    S(out, 'vla', [(c + .4, bl - c - .4, K('Ab4'), (.14, .58)), (bl, 1.4, K('Bb4'), (.8, .6))], -2, 203, ep=2, expr=up, tail=.5)
    # the bloom: Eb major with its ninth, low strings, horns, choir, harp, glock and drums all arrive together
    ex = [(bl - .02, 0), (bl + .4, 0), (bl + 1.3, -4), (48.3, -6)]
    S(out, 'vc', [(bl, 1.4, K('Eb3'), (.95, .6), dict(art='marc'))], 3, 204, ep=2, expr=ex, tail=.5)
    S(out, 'vc', [(bl, 1.4, K('Bb2'), (.9, .6), dict(art='marc'))], 1, 205, n=5, ep=2, expr=ex, tail=.5)
    S(out, 'cb', [(bl, 1.4, K('Eb2'), (1.0, .6), dict(art='marc'))], 4, 206, ep=2, expr=ex, tail=.5)
    for j, (m, sd) in enumerate((('Bb3', 210), ('Eb4', 211), ('G4', 212), ('F4', 213))):
        BRS(out, 'horn', [(bl, 1.3, K(m), (.85, .55), dict(art='ten'))], -3, sd, n=1, ep=2, expr=ex)
    BRS(out, 'tbn', [(bl, 1.3, K('Eb3'), (.8, .5))], -6, 214, n=2, ep=2, expr=ex)
    BRS(out, 'tbn', [(bl, 1.3, K('Bb2'), (.8, .5))], -6, 215, n=2, ep=2, expr=ex)
    BRS(out, 'tuba', [(bl, 1.3, K('Eb1'), (.85, .5))], -4, 216, ep=2, expr=ex)
    for p, m, sd in (('S', 'G5', 220), ('A', 'Eb5', 221), ('T', 'Bb3', 222), ('B', 'Eb3', 223)):
        CH(out, p, [(bl, 1.3, K(m), (.75, .5), dict(vowel='o>a'))], 0, sd, n=9, ep=2, expr=ex, tail=.5)
    hit(out, 'timp', bl, timp(K('Eb2'), 1.0, 230, 3.0), 2, ep=2)
    hit(out, 'bd', bl, bassdrum(1.0, 231), 3, ep=2)
    crash(out, bl, -10, 232, ep=2)
    sw = cymbal_roll(bl - c - .3, 233)
    out.put('music', c + .3, sw[:, :ns(bl - c - .3 + .02)] * fade(ns(bl - c - .3 + .02), .01, .02), -15, room='stage', wet=-10, ep=2)
    harp(out, [(bl + .13 + i * .055, K(m), .5 - .01 * i) for i, m in enumerate(['Eb2', 'Bb2', 'Eb3', 'G3', 'Bb3', 'Eb4', 'F4', 'G4', 'Bb4', 'Eb5', 'F5', 'G5', 'Bb5', 'Eb6'])], 1, 240, ep=2)
    glock(out, [(bl + .0, K('G6'), .5), (bl + .35, K('Bb6'), .35), (bl + .7, K('Eb7'), .25)], -2, 245, ep=2)
    return out.pack()


# ================================================================== s8 the beam: the theme at full size
def s8_grid(E):
    bar = E['s8.turn'] - E['s8.sweep']
    return E['s8.sweep'] - bar, bar / 3            # bar 1 downbeat, beat


# melody: Bb | Eb . F G | Bb5 - Ab | G F Eb | C . Bb D | Eb
TH8 = [(-1, 1, 'Bb4'), (0, 1.5, 'Eb5'), (1.5, .5, 'F5'), (2, 1, 'G5'), (3, 2, 'Bb5'), (5, 1, 'Ab5'),
       (6, 1, 'G5'), (7, 1, 'F5'), (8, 1, 'Eb5'), (9, 1.5, 'C5'), (10.5, .5, 'Bb4'), (11, 1, 'D5'), (12, 3.5, 'Eb5')]
# harmony per segment: (beat, dur, bass, [tenor, alto, soprano-ish inner])
HAR = [(0, 3, 'Eb2', ['Bb3', 'Eb4', 'G4']), (3, 2, 'Ab1', ['Ab3', 'C4', 'Eb4']), (5, 1, 'F1', ['Ab3', 'C4', 'F4']),
       (6, 1, 'C2', ['G3', 'C4', 'Eb4']), (7, 1, 'Ab1', ['Ab3', 'C4', 'F4']), (8, 1, 'Bb1', ['G3', 'Bb3', 'Eb4']),
       (9, 1.5, 'Ab1', ['Ab3', 'C4', 'Eb4']), (10.5, 1.5, 'Bb1', ['Ab3', 'D4', 'F4']), (12, 3.5, 'Eb2', ['Bb3', 'Eb4', 'G4'])]
VV8 = [.78, .86, .84, (.88, .92), (.95, 1.05), .95, 1.0, .94, .9, .84, .78, .74, (.6, .25)]
X8B = [(48.2, -4), (49.0, 0), (54.6, 0), (55.4, -1.5), (56.6, -5), (57.2, -11), (58.2, -20), (59.4, -40)]


def breaths(base, at, depth=-26):
    pts = list(base)
    for t in at:
        pts = [p for p in pts if not (t - .2 < p[0] < t + .02)]
        pts += [(t - .15, 0), (t - .06, depth * .55), (t - .012, depth), (t + .004, 0)]
    return sorted(pts)


X8 = X8B          # replaced per call with the event times (see x8)


def x8(E):
    return breaths(X8B, (E['s8.sweep'], E['s8.turn']))


def m_s8a(E):
    """strings"""
    out = Out()
    t1, b = s8_grid(E)
    M = [(t1 + x * b, d * b, K(nm), VV8[i], dict(swell=.12 if d > 1 else .05)) for i, (x, d, nm) in enumerate(TH8)]
    S(out, 'vn1', M, 4.0, 300, ep=2, expr=x8(E), vib=1.25, loose=.8)
    S(out, 'vn1', [(a, d, m + 12, v, dict(art='trem')) for a, d, m, v, o in M if a > 49.5 and a < 56.5], -8, 301, n=8, ep=2, art='trem', expr=x8(E))
    S(out, 'vn2', [(a, d, m - 12, v, o) for a, d, m, v, o in M], 2.0, 302, ep=2, expr=x8(E), vib=1.2, loose=.8)
    # violas and cellos: the inner chord, cellos with a tenor counter-line
    S(out, 'vla', [(t1 + x * b, d * b, K(v[1]), .85) for x, d, bs, v in HAR], 0, 303, ep=2, expr=x8(E))
    S(out, 'vla', [(t1 + x * b, d * b, K(v[0]), .8) for x, d, bs, v in HAR], -2, 304, n=6, ep=2, expr=x8(E))
    ct = [(0, 1, 'G3'), (1, 1, 'Ab3'), (2, 1, 'Bb3'), (3, 1.5, 'C4'), (4.5, .5, 'Bb3'), (5, 1, 'Ab3'), (6, 1, 'G3'), (7, 1, 'Ab3'), (8, 1, 'Bb3'),
          (9, 1.5, 'Eb4'), (10.5, 1.5, 'D4'), (12, 3.5, 'Eb3')]
    S(out, 'vc', [(t1 + x * b, d * b, K(nm), .88 if x < 12 else (.7, .3)) for x, d, nm in ct], 0, 305, ep=2, expr=x8(E), vib=1.2)
    bl = [(t1 + x * b - (.02 if x else 0), d * b * .98, K(bs), .95 if x < 12 else (.75, .3), dict(art='det')) for x, d, bs, v in HAR]
    S(out, 'cb', bl, 3, 306, ep=2, art='det', expr=x8(E))
    S(out, 'cb', [(a, d, m + 12, v, o) for a, d, m, v, o in bl], -2, 307, n=4, ep=2, art='det', expr=x8(E))
    return out.pack()


def m_s8b(E):
    """brass, choir, drums"""
    out = Out()
    t1, b = s8_grid(E)
    M = [(t1 + x * b, d * b, K(nm), VV8[i], dict(art='leg' if i else 'ten')) for i, (x, d, nm) in enumerate(TH8)]
    BRS(out, 'horn', [(a, d, m - 12, v, o) for a, d, m, v, o in M], 0, 310, ep=2, expr=x8(E))
    BRS(out, 'tpt', [(a, d * .97, m - 12, (v if np.isscalar(v) else v[0]) * .9, dict(art='ten')) for a, d, m, v, o in M if a > 49.5 and a < 56.5], -3, 311, ep=2, expr=x8(E), n=3)
    for j in range(3):
        BRS(out, 'tbn', [(t1 + x * b, d * b * .96, K(v[j]) - 12, .8 if x < 12 else (.55, .2), dict(art='ten')) for x, d, bs, v in HAR], -7, 312 + j, n=2, ep=2, expr=x8(E))
    BRS(out, 'tuba', [(t1 + x * b, d * b * .96, K(bs), .9 if x < 12 else (.55, .2)) for x, d, bs, v in HAR], -5, 315, ep=2, expr=x8(E))
    sop = [(t1 + x * b, d * b, K(nm), .9 if i < 12 else (.6, .2), dict(vowel='a' if i < 12 else 'a>u')) for i, (x, d, nm) in enumerate(TH8) if x >= 0]
    CH(out, 'S', sop, 0, 320, n=10, ep=2, expr=x8(E))
    for p, j, sd in (('A', 2, 321), ('T', 1, 322)):
        CH(out, p, [(t1 + x * b, d * b, K(v[j]), .85 if x < 12 else (.55, .2), dict(vowel='a')) for x, d, bs, v in HAR], -1, sd, n=10, ep=2, expr=x8(E))
    CH(out, 'B', [(t1 + x * b, d * b, K(bs) + 12, .85 if x < 12 else (.55, .2), dict(vowel='a')) for x, d, bs, v in HAR], -1, 323, n=10, ep=2, expr=x8(E))
    sweep, turn = E['s8.sweep'], E['s8.turn']
    for t, m, v in ((t1, 'Eb2', .85), (sweep, 'Ab2', 1.0), (turn, 'C2', 1.0), (t1 + 9 * b, 'Ab2', .7), (t1 + 10.5 * b, 'Bb2', .75)):
        hit(out, 'timp', t, timp(K(m), v, 330 + int(t * 10), 2.4), 0, ep=2)
    roll(out, 'timp', t1 + 10.5 * b + .1, t1 + 12 * b - .05, lambda v, s: timp(K('Bb1'), v, s, 1.2), .35, .55, -6, seed=340, ep=2)
    hit(out, 'timp', t1 + 12 * b, timp(K('Eb2'), .5, 345, 3.0), -3, ep=2)
    hit(out, 'bd', t1, bassdrum(.7, 350), -2, ep=2)
    hit(out, 'bd', sweep, bassdrum(1.0, 351), 1, ep=2)
    hit(out, 'bd', turn, bassdrum(1.0, 352), 1, ep=2)
    crash(out, sweep, -4, 355, ep=2)
    crash(out, turn, -10, 356, ep=2)
    harp(out, gliss(sweep - .62, sweep - .08, 'Eb3', 'Bb6', [3, 5, 7, 8, 10, 0, 2], .4, .7)
         + [(t1 + 12 * b + i * .11, K(m), .4 - .015 * i) for i, m in enumerate(['Eb2', 'Bb2', 'Eb3', 'G3', 'Bb3', 'Eb4', 'G4', 'Bb4', 'Eb5', 'G5'])], 1, 360, ep=2)
    glock(out, [(t1 + x * b, K(nm) + 12, .5 if x < 12 else .3) for x, d, nm in TH8 if x >= 0], -4, 370, ep=2)
    return out.pack()


# ================================================================== s9 dawn: the piano once more, and the last note
def m_s9(E):
    out = Out()
    lo = E['s9.lampoff']
    # morning air in muted strings, gone before the lamp goes out
    px = [(57.6, -30), (58.8, -8), (62.0, -6), (64.6, -9), (lo - .45, -30), (lo - .2, -60)]
    for nm, m, sd, g in (('vn1', 'G5', 400, -2), ('vn2', 'Bb4', 401, -3), ('vla', 'Eb4', 402, -4), ('vc', 'Eb3', 403, -4), ('vn2', 'F5', 404, -6)):
        S(out, nm, [(57.6, lo - 57.6 - .2, K(m), (.3, .3))], g, sd, n=6, ep=2, sord=True, expr=px, tail=.3)
    b = .7
    p0 = 61.2
    M = [(0, 'Bb4', .30, .9), (1, 'Eb5', .34, 1.6), (2.5, 'F5', .27, .45), (3, 'G5', .31, .9),
         (4, 'F5', .29, .85), (5, 'Eb5', .28, .85), (6, 'C5', .26, .42)]
    L = [(1, 'Eb3', .17, 2.6), (1.02, 'Bb3', .15, 2.5), (4, 'Ab2', .16, 1.95), (4.02, 'Eb3', .14, 1.9)]
    notes = [(p0 + x * b, nm, v, h) for x, nm, v, h in M] + [(p0 + x * b, nm, v, h) for x, nm, v, h in L]
    piano(out, notes, 4.0, 500, ep=2, peds=((p0 + b - .2, .7),))
    # the lamp goes out: one note, the theme's last, alone
    piano(out, [(lo, 'Bb4', .36, 6.0)], 4.0, 520, ep=2, wet=-11, halo=-18)
    return out.pack()


PARTS = [m_s1, m_s2, m_s3, m_s4, m_s5, m_dark, m_s7, m_s8a, m_s8b, m_s9]
