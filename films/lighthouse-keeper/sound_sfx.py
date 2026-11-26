"""The sound of every shot, placed in its space. Event times come from film.json through E; nothing is retyped here."""
import numpy as np
from core import *
from inst import modes
import sfx as SX
import sound_fx as FX
from sound_mix import Out


def env_gain(x, t0, pts, kind='db'):
    return x * curve(pts, x.shape[-1], t0, SR, kind)


def ev(E, prefix=''):
    return [t for k, t in E.items() if k.startswith(prefix)]


# ================================================================ s1 night on the island
def x_s1(E):
    o = Out()
    w = SX.wind(0, 7.02, [(0, .35), (1.5, .45), (3.0, .3), (4.6, .55), (6.0, .4), (7.0, .45)], 1001, whistle=.06, wf=(380, 520))
    o.put('sfx', 0, env_gain(w, 0, [(0, -40), (1.6, 0), (7.0, 0)]), -4, room='sky', wet=-12)
    waves = [(-1.0, .8, -.4), (1.6, .7, .3), (4.4, .9, -.2), (6.6, .6, .4)]
    s = FX.sea(0, 7.02, waves, 1010)
    o.put('sfx', 0, env_gain(s, 0, [(0, -40), (1.4, 0), (7.0, 0)]), 2, room='sky', wet=-10)
    # the bell buoy far out on the swell, rocking: two strokes close together, then a long wait
    for k, (t, v) in enumerate(((1.15, .7), (1.62, .45), (4.05, .8), (4.38, .4), (6.4, .55))):
        b = FX.bell(1020 + k, 392.0 * (1 if k % 2 == 0 else 1.0), v, 5.5)
        b = lp(hp(b, 200, 1), 3200, 2)
        o.put('sfx', t, b, -21, p=.55, room='sky', wet=-4)
    return o.pack()


# ================================================================ s2 / s3 the lamp room (one epoch)
def x_room(E):
    o = Out()
    avoid = ev(E, 's2.') + ev(E, 's3.')
    # the room: the lamp, its clockwork, wind round the glass, the sea far below
    o.put('sfx', 7.0, FX.wick(7.0, 19.02, 1101), -2, room='room', wet=-14)
    o.put('sfx', 7.0, env_gain(FX.gears(7.0, 15.0, 1102, .45, avoid), 7.0, [(7, 0), (14.6, 0), (15.0, -14)]), -6, p=.1, room='room', wet=-10)
    w = SX.wind(7.0, 19.02, [(7, .35), (9.5, .5), (12, .35), (14.5, .55), (17, .4), (19, .6)], 1103, whistle=.10, wf=(600, 800))
    o.put('sfx', 7.0, lp(w, 1800, 2), -9, room='room', wet=-10)
    s = FX.sea(7.0, 19.02, [(8.5, .6, -.3), (13.5, .7, .3), (17.6, .7, 0)], 1104, bed=.8)
    o.put('sfx', 7.0, lp(s, 700, 2), -2)
    return o.pack()


def x_s2(E):
    o = Out()
    h, p, wp = E['s2.hatch'], E['s2.pour'], E['s2.wipe']
    r = rng(1200)
    # paws on the iron ladder, coming up
    for k, t in enumerate((7.25, 7.52, 7.79)):
        o.put('sfx', t, FX.iron_step(1201 + k, .45 + .08 * k), -9 + 2 * k, p=-.35, room='room', wet=-10)
    # the hatch: a hind paw kicks the iron rim as she climbs out
    o.put('sfx', h, FX.clank(1210, 1.0), -14, p=-.3, room='room', wet=-8)
    o.put('sfx', h + .02, SX.paw(1211, .7, 'wood'), 2, p=-.3, room='room', wet=-10)
    # the walk to the lamp, oil can held up
    for k, t in enumerate(np.arange(h + .55, p - .7, .3)):
        o.put('sfx', t, SX.paw(1220 + k, .45 + .05 * r.normal(), 'wood', claws=bool(k % 2)), 0, p=-.25 + .06 * k, room='room', wet=-10)
    o.put('sfx', p - .45, SX.fur(.3, 1240, 2200), -2, p=0, room='room', wet=-12)
    # oil: first gulp at the moment it pours
    pr = FX.pour(1.5, 1250)
    o.put('sfx', p, pr, -8, p=.05, room='room', wet=-11)
    o.put('sfx', p, FX.glug(1251, 470, 1.0), -4, p=.05, room='room', wet=-11)
    o.put('sfx', p + 1.6, SX.lantern_down(1252) * .5, -10, p=.0, room='room', wet=-10)
    # the scarf on the lens, then two pats
    o.put('sfx', wp, FX.wipe([(0, .42), (.5, .38), (.95, .42)], 1260), -2, p=.12, room='room', wet=-12)
    for k, t in enumerate((wp + 1.55, wp + 1.78)):
        o.put('sfx', t, FX.pat(1270 + k, .8), -6, p=.12, room='room', wet=-12)
    o.put('sfx', wp + 2.1, SX.fur(.25, 1275, 2400), -4, p=.1, room='room', wet=-12)
    return o.pack()


def x_s3(E):
    o = Out()
    b, f = E['s3.blink'], E['s3.flash']
    # whiskers twitch
    o.put('sfx', 15.35, SX.fur(.18, 1301, 3600), -6, p=.1, room='room', wet=-14)
    # the blink: lids meeting, a tiny moist tick
    n = ns(.08)
    t = np.arange(n) / SR
    tick = modes(n, np.array([2900, 4300, 6100]), [1, .6, .3], [.006, .004, .003], 1302, att=.00008, phase=0)
    tick += hp(white(n, 1303), 2500, 1) * np.exp(-t / .002) * .5
    o.put('sfx', b, tick * .05, 0, p=0, room='room', wet=-14)
    # ears flattening after the far flash
    o.put('sfx', f + .25, SX.fur(.22, 1305, 2000), -6, p=.15, room='room', wet=-14)
    # very far thunder, late
    o.put('sfx', f + 1.3, lp(FX.thunder(1306, 0.0, 3.0), 300, 2), -8, room='room', wet=-10)
    return o.pack()


# ================================================================ s4 the storm arrives
def x_s4(E):
    o = Out()
    L, C = E['s4.lightning'], E['s4.crash']
    rn = FX.rain(19.0, 27.02, 1401, 1.0, [(19, .55), (21, .8), (24, 1.0), (27, 1.1)])
    o.put('sfx', 19.0, rn, -8, room='sky', wet=-14)
    o.put('sfx', 19.0, FX.storm_sea(19.0, 27.02, 1402, 1.0), -1, room='sky', wet=-14)
    w = SX.wind(19.0, 27.02, [(19, .5), (20.5, .8), (22, .6), (23.5, 1.0), (25, .7), (26.5, 1.1)], 1403, whistle=.12, wf=(500, 900), low=3)
    o.put('sfx', 19.0, w, -3, room='sky', wet=-12)
    o.put('sfx', 19.0, FX.sea(19.0, 27.02, [(19.6, .9, -.4), (21.2, 1.0, .4), (22.9, .8, -.2), (26.0, 1.0, .3)], 1404, storm=1.0, bed=.5), -1, room='sky', wet=-12)
    # far rolls before the strike
    o.put('sfx', 19.3, FX.thunder(1405, 0.0, 3.5), -4, p=-.4, room='sky', wet=-6)
    # the strike is close: crack on the flash, roll after
    o.put('sfx', L, FX.thunder(1406, 1.0, 4.5), -2, p=.2, room='sky', wet=-9)
    # the big wave on the rocks
    o.put('sfx', C, FX.wave_crash(1407, 1.0), -1, p=-.1, room='sky', wet=-10)
    return o.pack()


# ================================================================ s5 the window bursts, the flame dies
def x_s5(E):
    o = Out()
    W, O = E['s5.window'], E['s5.out']
    avoid = [W, O]
    # outside the glass: storm, rain on the panes
    w0 = SX.wind(27.0, 34.02, [(27, .7), (W - .2, .9), (W + .2, 1.25), (W + 1.0, 1.05), (O - .8, .95), (O - .35, .5), (O, .22), (O + 1.0, .16), (34, .2)],
                 1501, whistle=.35, wf=(520, 860))
    # muffled before the window opens, wide open after: the room fills with the storm
    pre = lp(w0, 700, 2)
    mix = np.where(np.arange(w0.shape[1]) / SR + 27.0 < W, 1.0, 0.0)
    k = smoothstep((np.arange(w0.shape[1]) / SR + 27.0 - W) / .12)
    wroom = pre * (1 - k) * .9 + w0 * k * 1.15
    o.put('sfx', 27.0, wroom, -2, room='room', wet=-8)
    rg = FX.rain_glass(27.0, 34.02, [(27, 40), (W, 50), (W + .2, 90), (O, 70), (34, 55)], 1502, avoid)
    o.put('sfx', 27.0, rg, -2, room='room', wet=-12)
    rn = FX.rain(27.0, 34.02, 1503, 1.0, [(27, .3), (W, .3), (W + .15, 1.0), (O - .5, .8), (O, .55), (34, .5)])
    o.put('sfx', 27.0, rn, -14, room='room', wet=-10)
    o.put('sfx', 27.0, lp(FX.storm_sea(27.0, 34.02, 1504, .7), 400, 2), -6)
    # the window
    o.put('sfx', W, FX.window_bang(1505), -3, p=-.45, room='room', wet=-8)
    # the flame struggling: it gutters and flaps until it tears off
    fl = SX.flame(O - 27.0, 1506, lean=[(0, .05), (W - 27.0, .1), (W - 27.0 + .3, 1.0), (O - 27.0 - .4, .8), (O - 27.0, .5)])
    fl = env_gain(fl, 27.0, [(27, 0), (O - .25, 0), (O - .02, -8), (O, -60)])
    o.put('sfx', 27.0, fl, 8, p=.05, room='room', wet=-14)
    o.put('sfx', 27.0, env_gain(FX.wick(27.0, O, 1507), 27.0, [(27, 0), (W, 0), (W + .3, -8), (O - .02, -12), (O, -60)]), -2, room='room', wet=-14)
    o.put('sfx', O, FX.flame_puff(1508, 1.0), 2, p=.05, room='room', wet=-12)
    # the otter shrinking back, fur
    o.put('sfx', W + .4, SX.fur(.3, 1509, 1800), -2, p=.2, room='room', wet=-12)
    return o.pack()


# ================================================================ s6 the lost boat
def x_s6(E):
    o = Out()
    h, x = E['s6.horn'], E['s6.hit']
    o.put('sfx', 34.0, FX.rain(34.0, 40.02, 1601, 1.0), -8, room='sky', wet=-14)
    o.put('sfx', 34.0, FX.storm_sea(34.0, 40.02, 1602, 1.0), -1, room='sky', wet=-14)
    w = SX.wind(34.0, 40.02, [(34, .8), (35.5, 1.0), (h - .3, .7), (37.5, 1.1), (x - .3, .9), (39.5, 1.0)], 1603, whistle=.15, wf=(450, 800), low=3)
    o.put('sfx', 34.0, w, -3, room='sky', wet=-12)
    o.put('sfx', 34.0, FX.sea(34.0, 40.02, [(34.4, 1.0, .3), (35.9, .9, -.3), (37.4, 1.0, .2), (39.2, .9, -.2)], 1604, storm=1.0, bed=.5), -1, room='sky', wet=-12)
    # the boat: creaking planks, the lantern swinging on its hook
    cr = SX.stickslip(5.8, [(0, 25), (2, 40), (4, 20), (5.8, 35)], *SX.wood_modes(1605, 90, 20, 1800, .08), 1606, gain=[(0, .6), (1, .2), (2.2, .8), (3.0, .1), (5.0, .5), (5.8, .2)])
    o.put('sfx', 34.2, cr * .03, 0, p=-.1, room='sky', wet=-8)
    # the horn: short, sagging, two reeds out of tune
    o.put('sfx', h, FX.horn(118.0, .55, 1610, rough=1.0, sag=1.0, release=.08, atk=.015), 2, p=-.15, room='sky', wet=-6)
    o.put('sfx', x, FX.hull_hit(1611, 1.0), -2, p=-.1, room='sky', wet=-9)
    return o.pack()


# ================================================================ s7 relit
def x_s7(E):
    o = Out()
    sh, m, c, bl = E['s7.shut'], E['s7.match'], E['s7.catch'], E['s7.bloom']
    avoid = [sh, m, c, bl]
    # the storm outside, now behind glass again once the window is shut
    w0 = SX.wind(40.0, 49.02, [(40, .5), (41, .7), (sh, .5), (43, .5), (45, .6), (47, .5), (49, .55)], 1701, whistle=.3, wf=(520, 820))
    k = smoothstep((np.arange(w0.shape[1]) / SR + 40.0 - sh) / .05)
    wroom = w0 * (1 - k) * .7 + lp(w0, 650, 2) * k * .8
    o.put('sfx', 40.0, wroom, -6, room='room', wet=-8)
    o.put('sfx', 40.0, FX.rain_glass(40.0, 49.02, [(40, 60), (sh, 45), (49, 35)], 1702, avoid), -2, room='room', wet=-12)
    o.put('sfx', 40.0, lp(FX.storm_sea(40.0, 49.02, 1703, .6), 380, 2), -8)
    # she throws herself at the window: scrabble, push, shut, latch
    for k_, t in enumerate((40.55, 40.72, 40.86, 41.0, 41.12)):
        o.put('sfx', t, SX.paw(1710 + k_, .55, 'wood'), -1, p=-.4, room='room', wet=-10)
    o.put('sfx', 40.9, SX.fur(.5, 1716, 1700, 1.4), -1, p=-.4, room='room', wet=-12)
    o.put('sfx', sh, FX.thump(1717, 85, 1.0), 0, p=-.4, room='room', wet=-8)
    o.put('sfx', sh + .16, FX.latch(1718, .8), -16, p=-.4, room='room', wet=-8)
    # up the iron steps of the lamp stand
    for k_, t in enumerate((42.15, 42.45, 42.75, 43.05, 43.32)):
        o.put('sfx', t, FX.iron_step(1720 + k_, .5), -8, p=-.1 + .05 * k_, room='room', wet=-10)
    o.put('sfx', 43.55, SX.fur(.3, 1726, 2200), -3, p=.05, room='room', wet=-12)
    # the match
    o.put('sfx', m, FX.match_strike(1730), -8, p=.05, room='room', wet=-12)
    o.put('sfx', m + .5, env_gain(SX.flame(c - m - .5, 1731), m + .5, [(m + .5, -10), (c - .1, -6), (c, -40)]) * .5, 0, p=.05, room='room', wet=-14)
    # the wick catches; the lamp burns steady
    o.put('sfx', c, FX.flame_catch(1732), 0, p=.0, room='room', wet=-12)
    o.put('sfx', c + .2, env_gain(FX.wick(c + .2, 49.02, 1733), c + .2, [(c + .2, -30), (c + 1.0, 0), (49, 0)]), -2, room='room', wet=-14)
    # the lens takes the light and the clockwork starts
    o.put('sfx', bl + .25, env_gain(FX.gears(bl + .25, 49.02, 1740, .42, avoid), bl + .25, [(bl + .25, -10), (bl + 1.0, 0), (49, 0)]), -2, p=.15, room='room', wet=-10)
    return o.pack()


# ================================================================ s8 the beam over the storm
def x_s8(E):
    o = Out()
    sw, tu = E['s8.sweep'], E['s8.turn']
    o.put('sfx', 49.0, FX.rain(49.0, 57.02, 1801, .9, [(49, 1.0), (54, .8), (57, .5)]), -9, room='sky', wet=-14)
    o.put('sfx', 49.0, FX.storm_sea(49.0, 57.02, 1802, .8), -2, room='sky', wet=-14)
    w = SX.wind(49.0, 57.02, [(49, .8), (51, .9), (53, .7), (55, .55), (57, .4)], 1803, whistle=.1, low=2)
    o.put('sfx', 49.0, w, -4, room='sky', wet=-12)
    # the beam swinging past: a long air-shaped swish
    o.put('sfx', sw - .7, SX.whoosh(1.6, [(0, 500), (.7, 2600), (1.6, 700)], .9, [(0, 0), (.62, .9), (.72, 1.0), (1.6, 0)], [(0, -.7), (1.6, .7)], 1804) * .06, 0, room='sky', wet=-8)
    # far: the boat heels over, her wake hissing in a curve
    o.put('sfx', tu, FX.lap(1805, 1.0), -6, p=.35, room='sky', wet=-6)
    o.put('sfx', tu + .2, SX.whoosh(2.2, [(0, 700), (.8, 2200), (2.2, 900)], .8, [(0, 0), (.6, .8), (2.2, 0)], [(0, .5), (2.2, .1)], 1806) * .03, 0, room='sky', wet=-6)
    return o.pack()


# ================================================================ s9 dawn
def x_s9(E):
    o = Out()
    h1, h2, wv, lo = E['s9.horn.1'], E['s9.horn.2'], E['s9.wave'], E['s9.lampoff']
    fo = [(57.0, 0), (68.0, 0), (70.0, -60)]
    s = FX.sea(57.0, 70.02, [(57.8, .45, .4), (61.4, .4, -.3), (66.8, .45, .2)], 1901, bed=.55)
    o.put('sfx', 57.0, env_gain(s, 57.0, fo), -3, room='sky', wet=-12)
    w = SX.wind(57.0, 70.02, [(57, .22), (61, .3), (65, .2), (70, .25)], 1902)
    o.put('sfx', 57.0, env_gain(lp(w, 2500, 2), 57.0, fo), -10, room='sky', wet=-12)
    # gulls, kept clear of the horns and the wave
    for k, (t, f, v, pn, n_) in enumerate(((57.6, 1500, .6, .6, 3), (61.9, 1700, .35, -.6, 2), (64.4, 1450, .5, .7, 3), (67.2, 1600, .3, -.5, 2))):
        o.put('sfx', t, FX.gull(1910 + k, f, v, n_), -14, p=pn, room='sky', wet=-6)
    # the boat says thank you: two clean blasts, a warm major third
    for k, (t, d) in enumerate(((h1, h2 - h1 - .2), (h2, 1.0))):
        x = FX.horn(155.6, d, 1920 + k, rough=0.0, release=.04, chord=(1.0, 1.26), atk=.015)
        o.put('sfx', t, x, -1, p=.35, room='sky', wet=-19)
    o.put('sfx', wv, FX.lap(1930, 1.0), -4, p=-.2, room='sky', wet=-10)
    # the lamp behind her goes out: a small sigh of the wick
    o.put('sfx', lo, FX.flame_puff(1940, .3), -12, p=-.2, room='room', wet=-12)
    # her tail curling
    o.put('sfx', lo + 1.2, SX.fur(.4, 1941, 1800), -6, p=-.1, room='sky', wet=-12)
    return o.pack()


PARTS = [x_s1, x_room, x_s2, x_s3, x_s4, x_s5, x_s6, x_s7, x_s8, x_s9]
