"""Shared hand-drawn props: paper lantern."""
import numpy as np, math
from .ink import Cel, spl, xf
from .paint import rgb, mix


def lantern(cel, x, y, s=1.0, rot=0.0, lean=0.0, lit=1.0, seed=0, lw=2.0, dim=False):
    """small paper lantern.  (x, y) = bottom centre when standing, 100 units tall at s=1.  lean: flame lean -1..1"""
    r = np.random.default_rng(700 + seed)
    T = lambda P: xf(np.asarray(P, float) + r.normal(0, .35, np.shape(P)), s, None, rot, x, y)
    ink = '#3a1f1a'
    paper, paper_sh, paper_hi = ('#f2b04c', '#cf7a35', '#ffe3a0') if not dim else ('#b97f4c', '#8c5a44', '#e0b27a')
    # handle
    cel.line(spl(T([[-15, -78], [-12, -96], [0, -104], [12, -96], [15, -78]])), 1.3 * lw, ink, (.05, .05), seed=seed)
    body = T([[-17, -74], [-27, -64], [-31, -44], [-29, -24], [-19, -11], [19, -11], [29, -24], [31, -44], [27, -64], [17, -74]])
    b = spl(body, closed=True, corners=(0, 4, 5, 9))
    cel.fill(b, paper)
    cel.shade(spl(T([[-40, -80], [-17, -76], [-20, -60], [-23, -42], [-20, -22], [-12, -8], [-40, -8]]), closed=True, corners=(0, 5, 6)), paper_sh, within=b)
    cel.shade(spl(T([[30, -80], [22, -66], [25, -44], [22, -22], [14, -8], [40, -8], [40, -80]]), closed=True, corners=(0, 4, 5, 6)), mix(rgb(paper_sh), rgb(paper), .4), within=b)
    # glow core
    cel.shade(spl(T([[-11, -24], [-15, -40], [-9 + 6 * lean, -60], [0 + 8 * lean, -68], [9 + 6 * lean, -60], [15, -40], [11, -24], [0, -18]]), closed=True), paper_hi, within=b)
    fl = spl(T([[-5, -22], [-7, -32], [-3 + 5 * lean, -44], [3 + 16 * lean, -58 + 5 * abs(lean)], [5 + 6 * lean, -42], [7, -31], [5, -22]]), closed=True, corners=(3,))
    cel.fill(fl, '#fffbe6', lit)
    # ribs
    for yy in (-63, -53, -43, -33, -23):
        k = math.sqrt(max(0, 1 - ((yy + 43) / 44.) ** 2)) * 31
        cel.line(spl(T([[-k, yy - 1], [-k * .5, yy + 2.2], [0, yy + 3], [k * .5, yy + 2.2], [k, yy - 1]])), .55 * lw, '#9c5528', (.1, .1), seed=seed + 3 + yy, alpha=.75)
    for P in (([-17, -74], [-27, -64], [-31, -44], [-29, -24], [-19, -11]), ([19, -11], [29, -24], [31, -44], [27, -64], [17, -74])):
        cel.line(spl(T(P)), .95 * lw, ink, (.05, .05), seed=seed + 20)
    for (yt, w_, h_) in ((-80, 19, 9), (-12, 21, 11)):
        cp = spl(T([[-w_, yt], [w_, yt], [w_ * .95, yt + h_], [-w_ * .95, yt + h_]]), closed=True, corners=(0, 1, 2, 3))
        cel.fill(cp, '#4a2f2a'); cel.shade(spl(T([[-w_, yt + h_ * .5], [w_, yt + h_ * .5], [w_, yt + h_ + 1], [-w_, yt + h_ + 1]]), closed=True, corners=(0, 1, 2, 3)), '#352025', within=cp)
        cel.line(np.vstack([cp, cp[:1]]), .85 * lw, ink, (0, 0), seed=seed + 30)
    cel.line(T([[0, -1], [0, 8]]), .8 * lw, '#7c2f2a', (0, .3), seed=seed + 40)
    return b
