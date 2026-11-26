"""The fishing boat of 守灯人: a small wooden boat with a wheelhouse aft, a mast forward and a hanging lantern that
swings.  Cel drawing (flat colour, one hard shadow, a lit edge, warm-dark pressure line, boil per drawing).
Owned by the sea lane; s6 and s8 (storm) and the island lane's s9 (calm dawn) use it.

USAGE

    import boat
    # 1) where the boat is and how it sits on the water (world metres, any Camera3D):
    pose = boat.place(cam, X, Y, heading, hfun, t=0., L=9.0, beam=3.2)
        # hfun(xs, ys) -> zs : sea height (m) at world points (arrays).  Calm sea: lambda x, y: .15*np.sin(.4*x + t)
        # heading: world angle (rad) the bow points to (0 = +X, pi/2 = +Y, away from a camera that looks along +Y).
        # The hull's height is the mean of the sea under bow, middle and stern; pitch comes from the slope
        # between bow and stern (atan2(z_bow - z_stern, L)), roll from port minus starboard over the beam.
        # pose = dict(x, y, scale, pitch, roll, facing, fore, z, bow_px, stern_px)   (screen px / radians)
    # 2) draw it:
    img = boat.draw(img, pose['x'], pose['y'], pose['scale'], pose['pitch'], pose['roll'],
                    lantern_swing=0.3, palette='storm'|'dawn', facing=pose['facing'], f=f, fore=pose['fore'],
                    lamp=1.0, wet=0.0, cut=True)
        # x, y  : screen px of the middle of the waterline;  scale: hull length in px (bow to stern, unforeshortened)
        # pitch : radians on screen, + = bow up;  roll: radians, + = deck tipped toward the camera (shows the deck)
        # lantern_swing: pendulum angle of the lantern (radians, + = toward the bow); drive it as a damped
        #   pendulum from pitch, e.g. swing = -0.8 * d(pitch)/dt * 0.25 + small sway
        # facing: +1 bow to the right of the frame, -1 bow to the left;  fore: 0.3..1 foreshortening along the hull
        #   (1 = broadside; place() computes it)
        # f: frame number, used only to seed the line boil (on twos: pass f // 2 * 2 if you animate on twos)
        # lamp: 0..1 the lantern is lit (glow drawn too);  cut: hide the hull below the waterline (with a wavy cut)
        # returns img; boat.lantern_px(...) with the same arguments gives the lantern's screen point.
    boat.actor(pose) -> dict(name='渔船', prop=True, x=, y=)   for Shot.actors

Hull 9 m long, 3.2 m beam; the wheelhouse stands aft, the mast 1/3 from the bow, the lantern hangs from the mast arm.
"""
import math
import numpy as np, cv2
from lp import W, H
from lp.paint import f32, rgb
from lp.ink import Cel, spl, boil, over_roi

PAL = {
    'storm': dict(hull='#5e3438', hull_sh='#3c2434', strake='#a9aab0', strake_sh='#6c7084', rail='#3a2a30', deck='#6b5a52',
                  cabin='#b2ad9f', cabin_sh='#6d6a7c', roof='#3e4c5c', roof_sh='#2a3446', mast='#5e4a40', line='#1f161c',
                  win='#ffc070', glass='#ffc070', rim='#8e9ab4', lamp='#ffc070', metal='#3a3440'),
    'dawn': dict(hull='#a4463e', hull_sh='#6e3446', strake='#f1e4d0', strake_sh='#b7a0aa', rail='#5a3a3c', deck='#b08a70',
                 cabin='#efe0c8', cabin_sh='#b29aa6', roof='#5d7f8a', roof_sh='#46607a', mast='#8a6a50', line='#3a2430',
                 win='#ffe2b0', glass='#f6e8c8', rim='#ffe2b8', lamp='#ffd890', metal='#4a4058'),
}

L_M, BEAM_M = 9.0, 3.2


# ------------------------------------------------------------------ geometry (local units: hull length 1)
def _parts(roll):
    k = max(.35, math.cos(roll))                    # superstructure seen tipped toward / away from us
    dk = .07 * math.sin(roll)                        # how much deck shows
    sheer = np.array([[-.50, .17], [-.30, .155], [0, .16], [.25, .185], [.42, .22], [.53, .27]])
    keel = np.array([[.53, .27], [.50, .10], [.44, -.02], [.30, -.07], [0, -.08], [-.35, -.07], [-.48, -.04], [-.50, .06]])
    hull = np.vstack([spl(sheer, n=6), spl(keel, n=6)])
    strake = np.vstack([spl(sheer, n=6), spl(sheer[::-1] - [0, .055], n=6)])
    boot = spl(np.array([[-.50, .035], [-.2, .02], [.2, .025], [.46, .05]]), n=6)
    deck = None
    if dk > .004:
        deck = np.vstack([spl(sheer, n=6), spl((sheer + [0, dk])[::-1], n=6)])
    ch = .24 * k
    cab = np.array([[-.34, .158], [-.34, .158 + ch], [-.08, .16 + ch], [-.08, .163]]) + [0, dk * .5]
    roof = np.array([[-.37, .158 + ch], [-.355, .158 + ch + .035 * k], [-.06, .16 + ch + .035 * k], [-.05, .16 + ch]]) + [0, dk * .5]
    win = np.array([[-.15, .158 + ch * .55], [-.15, .158 + ch * .86], [-.10, .158 + ch * .86], [-.10, .158 + ch * .55]]) + [0, dk * .5]
    win2 = np.array([[-.29, .158 + ch * .55], [-.29, .158 + ch * .86], [-.21, .158 + ch * .86], [-.21, .158 + ch * .55]]) + [0, dk * .5]
    mx = .16
    mtop = .17 + .62 * k
    mast = np.array([[mx - .007, .18], [mx - .005, mtop], [mx + .005, mtop], [mx + .007, .18]]) + [0, dk * .5]
    arm = np.array([[mx, .17 + .46 * k], [mx + .085, .17 + .44 * k]]) + [0, dk * .5]
    return dict(hull=hull, strake=strake, boot=boot, deck=deck, cab=cab, roof=roof, win=win, win2=win2, mast=mast, arm=arm,
                mtop=np.array([mx, mtop + dk * .5]), bow=np.array([.53, .27]), stern=np.array([-.5, .17]), k=k)


def _xf(P, x, y, scale, pitch, facing, fore):
    P = np.asarray(P, float)
    u = P[..., 0] * fore; v = P[..., 1]
    c, s = math.cos(pitch), math.sin(pitch)
    X = x + facing * (u * c - v * s) * scale
    Y = y - (u * s + v * c) * scale
    return np.stack([X, Y], -1)


def lantern_px(x, y, scale, pitch, roll=0., lantern_swing=0., facing=1, fore=1.0, **_):
    p = _parts(roll)
    a = p['arm'][1]
    cord = .075 * p['k']
    lp = a + cord * np.array([math.sin(lantern_swing), -math.cos(lantern_swing)])
    return _xf(lp, x, y, scale, pitch, facing, fore)


def draw(img, x, y, scale, pitch=0., roll=0., lantern_swing=0., palette='storm', facing=1, f=0, fore=1.0, lamp=1.0, wet=0.0,
         cut=True, light=None):
    pal = PAL[palette] if isinstance(palette, str) else palette
    p = _parts(roll)
    T = lambda P: _xf(P, x, y, scale, pitch, facing, fore)
    bo = lambda P, k=0: boil(P, .35, f * 7 + k)
    lw = float(np.clip(scale * .011, 1.0, 3.0))
    pad = int(scale * .9 + 20)
    x0, y0 = int(x - pad), int(y - pad); w_, h_ = 2 * pad, int(pad * 1.4)
    c = Cel(w_, h_, x0, y0, ss=2)
    hull = bo(T(p['hull']), 1)
    if cut:      # the sea closes over the hull: a wavy waterline cut
        uu = np.linspace(-.6, .6, 61)
        vv = .007 * np.sin(uu * 17 + f * .5) + .003 * np.sin(uu * 43 - f * 1.1)
        top = np.c_[uu, vv + .0]
        clip = np.vstack([top, [[.6, 1.2], [-.6, 1.2]]])
        c.clip(T(clip))
    # mast and lines behind the hull
    mast = bo(T(p['mast']), 2)
    c.fill(mast, pal['mast'])
    mt = T(p['mtop'])
    for end, k in ((p['bow'] + [-.02, 0], 3), (p['stern'] + [.04, .0], 4)):
        P = bo(T(np.array([p['mtop'], (p['mtop'] + end) / 2 + [0, -.01], end])), k)
        c.line(P, max(.7, lw * .45), pal['line'], (.05, .05), .1, seed=k, alpha=.85)
    # hull
    c.fill(hull, pal['hull'])
    c.shade(T(np.array([[-.6, -.2], [.6, -.2], [.6, .075], [-.6, .065]])), pal['hull_sh'], within=hull)
    if p['deck'] is not None:
        c.fill(bo(T(p['deck']), 5), pal['deck'])
    c.fill(bo(T(p['strake']), 6), pal['strake'])
    c.shade(T(np.array([[-.6, 0], [-.18, 0], [-.18, .4], [-.6, .4]])), pal['strake_sh'], within=T(p['strake']), alpha=.55)
    c.line(bo(T(p['boot']), 7), lw * .8, pal['rail'], (.1, .1), .2, seed=7, alpha=.8)
    # wheelhouse
    cab = bo(T(p['cab']), 8)
    c.fill(cab, pal['cabin'])
    c.shade(T(np.array([[-.36, 0], [-.27, 0], [-.27, .8], [-.36, .8]])), pal['cabin_sh'], within=cab)
    for wn, k in (('win', 9), ('win2', 10)):
        wp = bo(T(p[wn]), k)
        c.fill(wp, pal['win'] if lamp > 0 else pal['cabin_sh'], .55 + .45 * min(1., lamp))
        c.line(wp, lw * .6, pal['line'], (0, 0), .1, seed=k, closed=True)
    roof = bo(T(p['roof']), 11)
    c.fill(roof, pal['roof'])
    c.shade(T(np.array([[-.4, .0], [-.04, 0], [-.04, .2], [-.4, .2]]) + [0, p['roof'][0, 1] - .005]), pal['roof_sh'], within=roof, alpha=.8)
    # ink
    c.line(hull, lw, pal['line'], (.06, .06), .25, seed=12, closed=True)
    c.line(bo(T(spl(np.array([[-.5, .115], [0, .105], [.3, .13], [.5, .21]]), n=6)), 13), lw * .7, pal['line'], (.15, .2), .25, seed=13, alpha=.9)
    c.line(cab, lw * .9, pal['line'], (.05, .05), .2, seed=14, closed=True)
    c.line(roof, lw * .9, pal['line'], (.05, .05), .2, seed=15, closed=True)
    c.line(mast, lw * .6, pal['line'], (.1, .1), .2, seed=16, closed=True)
    # lit edge along the sheer and the roof (from the sky / beam)
    c.line(bo(T(spl(np.array([[-.48, .175], [-.2, .162], [.15, .17], [.4, .21]]), n=6)), 17), lw * .6, pal['rim'], (.3, .3), .3, seed=17, alpha=.7)
    # arm and lantern
    arm = T(p['arm'])
    c.line(arm, lw * .8, pal['metal'], (0, .1), .1, seed=18)
    a = p['arm'][1]; cord = .075 * p['k']
    sw = lantern_swing
    lpos = a + cord * np.array([math.sin(sw), -math.cos(sw)])
    c.line(T(np.array([a, lpos])), max(.6, lw * .4), pal['line'], (0, 0), .05, seed=19)
    r = .022
    ca, sa = math.cos(sw), math.sin(sw)
    rot = lambda q: lpos + np.array([q[0] * ca + q[1] * sa, -q[0] * sa + q[1] * ca])
    body = np.array([rot(q) for q in ((-r * .8, -.004), (-r, -r * 1.8), (r, -r * 1.8), (r * .8, -.004))])
    capP = np.array([rot(q) for q in ((-r * 1.1, -.002), (0, .012), (r * 1.1, -.002))])
    c.fill(T(body), pal['glass'] if lamp > 0 else pal['metal'], 1.0)
    c.fill(T(capP), pal['metal'])
    c.line(T(body), max(.7, lw * .5), pal['line'], (0, 0), .1, seed=20, closed=True)
    if cut: c.unclip()
    L = c.rgba()
    if wet > 0:
        L[..., :3] = L[..., :3] * (1 - .15 * wet)
    over_roi(img, L, x0, y0)
    if lamp > 0:
        lx, ly = T(lpos + np.array([0, -r]))
        R = int(scale * .35) + 6
        X0, X1, Y0, Y1 = max(0, int(lx - R)), min(img.shape[1], int(lx + R)), max(0, int(ly - R)), min(img.shape[0], int(ly + R))
        if X1 > X0 and Y1 > Y0:
            yy, xx = np.mgrid[Y0:Y1, X0:X1].astype(f32)
            d = np.sqrt((xx - lx) ** 2 + (yy - ly) ** 2) / (scale * .03 + 1)
            g = (.7 * np.exp(-(d / .8) ** 2) + .3 * np.exp(-(d / 3.) ** 2) + .1 * np.exp(-(d / 8.) ** 2)) * lamp
            col = rgb(pal['lamp'])
            img[Y0:Y1, X0:X1] = 1 - (1 - img[Y0:Y1, X0:X1]) * (1 - np.clip(g[..., None] * col, 0, .97))
    return img


# ------------------------------------------------------------------ riding the sea
def place(cam, X, Y, heading, hfun, L=L_M, beam=BEAM_M, freeboard=0.0):
    """screen pose of a boat whose middle is at world (X, Y), bow toward `heading`, floating on hfun."""
    dx, dy = math.cos(heading), math.sin(heading)
    px, py = -dy, dx
    xs = np.array([X + dx * L / 2, X, X - dx * L / 2, X + px * beam / 2, X - px * beam / 2])
    ys = np.array([Y + dy * L / 2, Y, Y - dy * L / 2, Y + py * beam / 2, Y - py * beam / 2])
    z = np.asarray(hfun(xs, ys), float)
    zb, zm, zs, zp, zq = z
    zc = (zb + 2 * zm + zs) / 4 + freeboard
    pitch_w = math.atan2(zb - zs, L)
    roll_w = math.atan2(zp - zq, beam)
    # project bow and stern of the waterline to get screen angle, scale, facing and foreshortening
    B = np.array([X + dx * L / 2, Y + dy * L / 2, zc + math.sin(pitch_w) * L / 2])
    S = np.array([X - dx * L / 2, Y - dy * L / 2, zc - math.sin(pitch_w) * L / 2])
    M = np.array([X, Y, zc])
    (bp, sp, mp), _ = cam.project(np.stack([B, S, M]))
    full = float(cam.scale(M)) * L                    # px length if broadside
    v = bp - sp
    facing = 1 if v[0] >= 0 else -1
    fore = float(np.clip(abs(v[0]) / max(full, 1e-3), .3, 1.0))
    ang = math.atan2(-(v[1]), abs(v[0]) + 1e-6)       # screen angle of the hull line, + = bow up
    # which side faces the camera decides the sign of the roll on screen
    cam_side = np.array([cam.eye[0] - X, cam.eye[1] - Y]) @ np.array([px, py])
    roll = roll_w if cam_side > 0 else -roll_w
    return dict(x=float(mp[0]), y=float(mp[1]), scale=full, pitch=ang, roll=roll, facing=facing, fore=fore, z=zc,
                bow_px=bp, stern_px=sp, pitch_w=pitch_w)


def actor(pose):
    return dict(name='渔船', prop=True, x=float(pose['x']), y=float(pose['y']))
