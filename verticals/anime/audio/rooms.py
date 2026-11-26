"""Spaces: the scoring stage seats, and the film's rooms (reading hall, tower, open sky, small piano room)."""
import os
import numpy as np
from core import *

DIMS = (23.0, 33.0, 14.0)
SEATS = dict(
    vn1=[(-6.2, 3.2, 1.2), (-4.9, 4.3, 1.2), (-3.7, 5.4, 1.2), (-2.9, 6.6, 1.3)],
    vn2=[(-2.4, 3.1, 1.2), (-1.5, 4.3, 1.2), (-.7, 5.5, 1.3), (.1, 6.6, 1.3)],
    vla=[(1.0, 3.2, 1.2), (1.9, 4.3, 1.2), (2.6, 5.3, 1.3), (3.1, 6.5, 1.3)],
    vc=[(3.2, 2.7, .9), (4.5, 3.4, .9), (5.3, 4.6, 1.0), (5.8, 5.9, 1.0)],
    cb=[(6.5, 5.0, 1.2), (7.2, 6.0, 1.2), (6.6, 7.2, 1.3), (7.6, 7.6, 1.3)],
    horn=[(-5.6, 9.0, 1.4), (-4.4, 9.3, 1.4), (-3.3, 9.6, 1.4), (-2.3, 9.9, 1.4)],
    tpt=[(.6, 10.2, 1.6), (1.5, 10.3, 1.6), (2.4, 10.4, 1.6)],
    tbn=[(3.4, 9.7, 1.5), (4.5, 9.8, 1.5), (5.5, 9.9, 1.5)],
    tuba=[(6.6, 9.4, 1.5)],
    choir=[(-6.5, 13.5, 2.4), (-2.4, 14.0, 2.4), (2.4, 14.0, 2.4), (6.5, 13.5, 2.4)],
    harp=[(-7.2, 6.4, 1.2)], timp=[(-.8, 11.0, 1.3)], glock=[(-3.2, 11.4, 1.4)], cym=[(2.6, 11.8, 1.8)], bd=[(.9, 12.0, 1.2)],
    piano=[(-1.6, 6.0, 1.2)])
WET = dict(vn1=-11, vn2=-11, vla=-11, vc=-12, cb=-13, horn=-8, tpt=-9, tbn=-10, tuba=-12, choir=-6, harp=-9, timp=-11, glock=-8, cym=-11,
           bd=-13, piano=-9)


def all_rooms():
    """name -> stereo impulse response used on the sends."""
    def er(dims, src, seed, refl, length, order=3):
        h = seat_ir(src, dims, seed, refl=refl, order=order, length=length)
        d = seat_ir(src, dims, seed, refl=refl, order=0, length=length)
        return h - d

    def mix(e, l, ge, gl):
        n = max(e.shape[1], l.shape[1])
        o = np.zeros((2, n))
        o[:, :e.shape[1]] += e * db(ge) / np.sqrt((e ** 2).sum() / 2)
        o[:, :l.shape[1]] += l * db(gl)
        return o
    return dict(
        stage=late_ir(101, [2.2, 2.3, 2.4, 2.35, 2.25, 2.15, 1.9, 1.5, .95, .55], 3.6, [-9, -5, -1.5, 0, 0, 0, -.5, -1.5, -4, -8], .045, .026),
        hall=mix(er((15, 22, 19), (0.5, 4, 1.0), 102, .74, .2), late_ir(103, [1.5, 1.8, 2.2, 2.5, 2.4, 2.1, 1.6, 1.1, .65, .4], 3.2,
                 [-8, -4, -1, 0, 0, -.5, -2, -4, -8, -13], .05, .022), -2.5, -1.5),
        tower=mix(er((12, 12, 34), (0.8, 3, 1.0), 104, .80, .26), late_ir(105, [2.4, 2.8, 3.3, 3.3, 3.0, 2.7, 2.2, 1.6, 1.0, .55], 4.4,
                  [-8, -4, -1, 0, 0, 0, -1, -2.5, -5, -9], .06, .03, rough=.2), -3.0, -1.2),
        sky=late_ir(106, [.9, 1.0, 1.2, 1.5, 1.6, 1.4, 1.1, .75, .45, .3], 2.4, [-10, -6, -2, 0, 0, 0, -1, -3, -6, -10], .16, .07, rough=.4),
        room=mix(er((6.5, 8, 3.6), (0.2, 1.6, 1.1), 107, .62, .1), late_ir(108, [.6, .7, .75, .75, .7, .62, .5, .4, .3, .2], 1.0,
                 [-6, -3, 0, 0, 0, 0, -1, -3, -6, -10], .015, .008), -2, -3))


_C = {}


def seat(name):
    if name not in _C:
        k = sum(ord(c) for c in name)
        _C[name] = [seat_ir(p, DIMS, 300 + k + i, refl=.76, order=3, length=.13, er_db=-1.5) for i, p in enumerate(SEATS[name])]
    return _C[name]


# epochs: the two silences separate three worlds; nothing rings across them
EP = [(0.0, 20.70), (20.55, 31.50), (31.95, DUR), (20.5, 32.1)]     # 3 = heard inside the silences


def epoch_of(t):
    return 0 if t < 20.58 else 1 if t < 31.6 else 2


class Out:
    """Per-stem, per-epoch, per-room accumulators (dry and sends)."""

    def __init__(self):
        self.d = {}

    def tr(self, key):
        if key not in self.d:
            self.d[key] = Track(*EP[key[1]])
        return self.d[key]

    def put(self, stem, t, x, gdb=0.0, p=0.0, room=None, wet=-12.0, ep=None, dry=0.0):
        if x.ndim == 1:
            x = pan2(x, p)
        e = epoch_of(t) if ep is None else ep
        g = float(db(gdb))
        if dry is not None:
            self.tr((stem, e, 'dry')).add(t, x, g * float(db(dry)))
        if room:
            self.tr((stem, e, room)).add(t, x, g * float(db(wet)))

    def pack(self):
        return {k: v.x.astype(np.float32) for k, v in self.d.items()}
