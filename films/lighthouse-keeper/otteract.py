"""The otter's acting in every shot.  Owned by the otter lane.

  img = draw(img, key, f, M)    # composite the otter for shot `key` at shot frame f, from the shot's marks M
  acts = actors(key, f, M)      # what the checks need: position on the ground, scale, facing, contact points

Every shot is a function act_<key>(f, M) -> Perf: the view (where and how big), the pose, props drawn
into the cel stack, the clip (a floor edge), and the contact points.  Character animation is on twos
(the pose is evaluated at d = f // 2); the camera of the shot is not ours.  Key poses, holds,
anticipation and overshoot are written out per shot; follow-through (scarf ends, tail, whiskers) is
computed from the motion of the body so it lags behind it.
"""
import math
import numpy as np, cv2
from lp.ink import Cel, spl
from lp.paint import rgb, mix
from lp.comp import ease
import otter as O

cv2.setNumThreads(2)
f32 = np.float32
STAND_H = 330.0          # actors(): s = 1 at a standing height of 330 px
CROWN = 96.0             # model units from the soles to the top of the head


# ------------------------------------------------------------------ timing helpers
def tw(f, n=2):
    """the drawing a frame shows: on twos by default"""
    return f - f % n


def seg(f, a, b, e=ease):
    """eased 0..1 over frames [a, b]"""
    if f <= a: return 0.0
    if f >= b: return 1.0
    return float(e((f - a) / float(b - a)))


def lin(f, a, b):
    return float(np.clip((f - a) / float(b - a), 0, 1))


def out_(t, p=2.0):
    return 1 - (1 - t) ** p


def in_(t, p=2.0):
    return t ** p


def keys(f, ks, e=ease):
    """[(frame, value)] -> eased value; scalars, tuples or pose dicts"""
    if f <= ks[0][0]: return ks[0][1]
    for (a, va), (b, vb) in zip(ks[:-1], ks[1:]):
        if f < b:
            t = float(e((f - a) / float(b - a)))
            if isinstance(va, dict): return O.lerp(va, vb, t)
            return tuple(np.asarray(va, float) * (1 - t) + np.asarray(vb, float) * t) if np.ndim(va) else va + (vb - va) * t
    return ks[-1][1]


def blink_at(f, starts, close=2, hold=2, open_=4):
    """a real blink: lids drop in `close` frames, stay shut `hold`, lift in `open_` (on ones; caller holds twos)"""
    b = 0.0
    for s in starts:
        if s <= f < s + close: b = max(b, (f - s + 1) / (close + 1))
        elif s + close <= f < s + close + hold: b = 1.0
        elif s + close + hold <= f < s + close + hold + open_: b = max(b, 1 - (f - s - close - hold + 1) / (open_ + 1))
    return b


# ------------------------------------------------------------------ pose helpers (body space units)
def lean(P, a, piv=None):
    """tip the upper body forward (a > 0) about the pelvis; paws, head go along"""
    piv = np.array(P['pelvis'] if piv is None else piv, float)
    c, s = math.cos(-a), math.sin(-a)

    def R(q):
        q = np.asarray(q, float).copy(); d = q[:2] - piv[:2]
        q[0], q[1] = piv[0] + d[0] * c - d[1] * s, piv[1] + d[0] * s + d[1] * c
        return q
    Q = dict(P)
    for k_ in ('chest', 'neck', 'head', 'pawL', 'pawR'):
        Q[k_] = tuple(R(P[k_]))
    Q['hpitch'] = P['hpitch'] - a
    return Q


def stretch(P, s):
    """stand tall: the torso lengthens, the head and arms ride up with it"""
    Q = shift(P, du=s, names=('neck', 'head', 'pawL', 'pawR'))
    q = np.asarray(P['chest'], float).copy(); q[1] += s * .7; Q['chest'] = tuple(q)
    Q['rc'] = P['rc'] - s * .12
    return Q


def shift(P, df=0.0, du=0.0, names=('pelvis', 'chest', 'neck', 'head', 'pawL', 'pawR')):
    Q = dict(P)
    for k_ in names:
        q = np.asarray(P[k_], float).copy(); q[0] += df; q[1] += du; Q[k_] = tuple(q)
    return Q


def tail_curve(base=(-13, 14), ang=-.5, curl=.25, ln=40, up=0.0, side=0.0, n=5):
    """tail control points: starts at the rump, heading `ang` (0 = straight back, + = up), bending by curl"""
    pts = []
    p = np.array([base[0], base[1], 0.0])
    a = ang
    for i in range(n):
        seg_ = ln / n
        p = p + np.array([-math.cos(a) * seg_, math.sin(a) * seg_ + up * i / n, side * (i + 1) / n * 6])
        p[1] = max(p[1], 1.8 if i < n - 1 else 1.4)          # lies on the floor, never through it
        pts.append(tuple(p))
        a += curl
    return tuple(pts)


# ------------------------------------------------------------------ props
def oil_can(V, c, tilt, env, k, seed=0):
    """small brass oil can, centre c (body space), tilted forward by `tilt` rad about the r axis.
    Returns (draw fn, points dict: spout tip, grip)"""
    ct, st = math.cos(-tilt), math.sin(-tilt)
    Rt = np.array([[ct, -st, 0], [st, ct, 0], [0, 0, 1]])
    c = np.asarray(c, float)
    C = lambda q: c + np.asarray(q, float) @ Rt.T
    th = np.linspace(0, 2 * np.pi, 28, endpoint=False)
    rad, h = 4.0, 8.4
    bot = C(np.c_[rad * np.cos(th), np.full_like(th, -h / 2), rad * np.sin(th)])
    top = C(np.c_[rad * .78 * np.cos(th), np.full_like(th, h / 2), rad * .78 * np.sin(th)])
    sb, stp = V.p(bot)[:, :2], V.p(top)[:, :2]
    hull = cv2.convexHull(np.vstack([sb, stp]).astype(np.float32))[:, 0, :].astype(float)
    sp0, sp1 = C([3.2, 1.6, 0]), C([11.5, 7.6, 0])
    tip = V.p(sp1)[:2]
    cap = V.p(C([0, h / 2 + 1.2, 0]))[:2]
    hnd = V.p(C([[-3.6, 2.8, 0], [-7.2, 2.0, 0], [-7.6, -1.6, 0], [-3.8, -2.6, 0]]))[:, :2]
    axis = V.d(Rt @ [0, 1, 0])[:2]
    lit = mix(rgb('#c8963c'), env.col, .25 * env.amt) * (1 - env.dark * .8) + env.amb * env.dark * .4
    shd = mix(rgb('#8a6130'), env.amb, .2) * (1 - env.dark * .7)
    dk = rgb('#4a3226')
    lw = float(np.clip(1.4 + k * .2, 1.6, 3.2))

    def fn(cel):
        # handle behind the body, spout in front
        cel.line(spl(hnd), lw * 1.7, env.line, (.1, .1), .2, seed=seed + 1)
        cel.line(spl(hnd), lw * .8, shd, (.15, .15), .2, seed=seed + 2)
        cel.fill(hull, lit)
        # one hard shadow down the side away from the light, a highlight stripe on the lit side
        n2 = np.array([-axis[1], axis[0]]); n2 /= np.hypot(*n2) + 1e-9
        if n2 @ env.L2 > 0: n2 = -n2
        ctr = hull.mean(0); wv = np.abs((hull - ctr) @ n2).max()
        cel.clip(hull)
        q = np.array([ctr + n2 * wv * .15 - axis * 60, ctr + n2 * wv * .15 + axis * 60, ctr + n2 * 200 + axis * 60, ctr + n2 * 200 - axis * 60])
        cel.fill(q, shd)
        q = np.array([ctr - n2 * wv * .55 - axis * 60, ctr - n2 * wv * .55 + axis * 60, ctr - n2 * wv * .75 + axis * 60, ctr - n2 * wv * .75 - axis * 60])
        cel.fill(q, mix(lit, np.ones(3, f32), .45), .9)
        band = V.p(C(np.c_[rad * 1.01 * np.cos(th), np.full_like(th, -h * .18), rad * 1.01 * np.sin(th)]))
        vis = band[:, 2] > V.p(c)[2]
        if vis.sum() > 3: cel.line(band[vis][np.argsort(np.arctan2(*(band[vis][:, :2] - ctr).T[::-1]))][:, :2], lw * .7, dk, (.2, .2), .2, seed=seed + 3, alpha=.6)
        cel.unclip()
        cel.line(np.vstack([hull, hull[:1]]), lw, env.line, (.05, .05), .25, seed=seed + 4)
        # cap and spout
        cel.fill(spl(np.array([cap + [-2.2 * k / 3, 1], cap + [0, -1.4 * k / 3], cap + [2.2 * k / 3, 1]]), closed=True) if False else
                 np.array([cap + [-1.6 * k, .5 * k], cap + [-1.2 * k, -.6 * k], cap + [1.2 * k, -.6 * k], cap + [1.6 * k, .5 * k]]), shd)
        a2, b2 = V.p(sp0)[:2], tip
        d2 = (b2 - a2) / (np.hypot(*(b2 - a2)) + 1e-9); nn = np.array([-d2[1], d2[0]])
        sp = np.array([a2 + nn * 1.3 * k, b2 + nn * .45 * k, b2 - nn * .45 * k, a2 - nn * 1.3 * k])
        cel.fill(sp, lit)
        cel.line(np.vstack([sp, sp[:1]]), lw * .85, env.line, (.05, .05), .2, seed=seed + 5)
    return fn, dict(spout=tip, grip=V.p(C([0, 0, 0]))[:2])


def oil_stream(V, tip, target, f, env, k):
    """a thin amber thread from the spout to the filler, with a slight sag and a bead at the bottom"""
    tip, target = np.asarray(tip, float), np.asarray(target, float)
    t = np.linspace(0, 1, 12)[:, None]
    mid = (tip + target) / 2 + [2, 0]
    q = (1 - t) ** 2 * tip + 2 * t * (1 - t) * (mid + [-3, 4]) + t * t * target
    col = mix(rgb('#ffcf6a'), env.col, .3) * 1.1

    def fn(cel):
        w = max(1.6, k * .45) * (1 + .15 * math.sin(f * 1.7))
        cel.line(q, w, col, (.02, .2), .4, seed=f // 2, alpha=.95, tremor=.6)
        cel.fill(np.array([target + [math.cos(a) * w, math.sin(a) * w * .8] for a in np.linspace(0, 6.28, 12)]), col, .9)
    return fn


def match_and_flame(V, paw, f, lit_t, env, k, d=(1.0, -.25)):
    """a match held in the paw (its head toward d); lit_t: 0 not struck .. 1 burning, flare peaks at ~.15"""
    paw = np.asarray(paw, float); d = np.asarray(d, float); d /= np.hypot(*d)
    nn = np.array([-d[1], d[0]])
    L = 13 * k / 3.3 * 1.0 * 3.3 / 1.0 / 1.0 * .3 * 3.3 if False else 4.4 * k
    a, b = paw - d * 1.2 * k, paw + d * L
    head = b + d * .6 * k
    stick = np.array([a + nn * .45 * k, b + nn * .45 * k, b - nn * .45 * k, a - nn * .45 * k])
    lw = float(np.clip(1.4 + k * .2, 1.6, 3.2))
    out = dict(match=head)

    def fn(cel):
        cel.fill(stick, mix(rgb('#d9b98a'), env.col, .3) * (1 - env.dark * .6))
        cel.line(np.vstack([stick, stick[:1]]), lw * .7, env.line, (.05, .05), .2, seed=7)
        hd = np.array([head + [math.cos(t) * .95 * k, math.sin(t) * .8 * k] for t in np.linspace(0, 6.28, 14)])
        cel.fill(hd, rgb('#6a2a22') if lit_t <= 0 else rgb('#2a1a18'))
        if lit_t > 0:
            flare = math.exp(-((lit_t - .12) / .1) ** 2)
            fl = 1 + .12 * math.sin(f * 2.3) + .08 * math.sin(f * 5.1 + 1)
            up = np.array([0, -1.0])
            hgt = (3.2 + 4.0 * flare) * k * fl
            wid = (1.3 + 1.2 * flare) * k
            sway = (.25 * math.sin(f * .9)) * k
            tipp = head + up * hgt + [sway, 0]
            outer = spl(np.array([head + [-wid, .2 * k], head + [-wid * .7, -hgt * .45], tipp, head + [wid * .7, -hgt * .45], head + [wid, .2 * k], head + [0, wid * .9]]), closed=True, corners=(2,))
            inner = spl(np.array([head + [-wid * .45, 0], head + [-wid * .3, -hgt * .4], head + up * hgt * .62 + [sway * .5, 0], head + [wid * .3, -hgt * .4], head + [wid * .45, 0], head + [0, wid * .5]]), closed=True, corners=(2,))
            cel.fill(outer, rgb('#ff9a3c'), .92)
            cel.fill(inner, rgb('#fff2c4'))
            cel.fill(np.array([head + [math.cos(t) * .5 * k, math.sin(t) * .5 * k + .2 * k] for t in np.linspace(0, 6.28, 10)]), rgb('#6a8ad8'), .7)
    out['flame'] = head + np.array([0, -2.2 * k])
    return fn, out


# ------------------------------------------------------------------ performance record
class Perf:
    def __init__(self, x, y, k, yaw, P, tilt=.08, roll=0.0, props=(), clip=None, points=None, facing=None, env=None, lw=None,
                 parts=None, light=None):
        self.x, self.y, self.k, self.yaw, self.P, self.tilt, self.roll = x, y, k, yaw, P, tilt, roll
        self.props, self.clip, self.points = list(props), clip, dict(points or {})
        self.facing, self.env, self.lw, self.parts, self.light = facing, env, lw, parts, light

    def view(self):
        return O.View(self.x, self.y, self.k, yaw=self.yaw, tilt=self.tilt, roll=self.roll)


def env_from(M, **kw):
    L = M.get('light', dict(dir=(1, -.4), color='#ffb458', amt=.8))
    return O.Env(L, **kw)


# ================================================================== s2: the lamp room
# 1.0 s up out of the hatch with the can hugged to the chest; walk to the lamp; hop on the plinth;
# 4.0 s pour; set the can down; 6.0 s wipe the lens with the end of the scarf, two pats; pleased.
S2 = dict(rise=16, slap=24, heave=28, knee=38, up=44, turn=50, walk=52, hop=86, land=92, lift=93, pour=96, pour_end=120,
          down=128, set=134, reach=138, wipe=144, pat1=166, pat2=174, done=182)


def _hug(P, can_c=(10.5, 46.0)):
    """left arm hugs the can to the chest, right paw under it"""
    return O.pose(P, pawL=(can_c[0] + .5, can_c[1] + 2.0, -5.0), pawR=(can_c[0] + 1.5, can_c[1] - 3.0, 5.2), elbL=(.3, -.6, -1), elbR=(.3, -1, 1))


def _walk(ph, step=9.0, lift=3.4):
    """side-view waddle at cycle phase ph (two steps per cycle).  Feet are planted while in stance."""
    def foot(p, side):
        p = p % 1.0
        if p < .5:
            t = p / .5
            return (step * .5 - step * t + 2.5, 2.8, side * 8.5), -.05
        t = (p - .5) / .5; e = t * t * (3 - 2 * t)
        return (-step * .5 + step * e + 2.5, 2.8 + lift * math.sin(math.pi * t) ** .8, side * 8.5), .35 * math.sin(math.pi * t)
    fL, aL = foot(ph, -1); fR, aR = foot(ph + .5, 1)
    bob = 1.3 * math.cos(4 * math.pi * ph) - .3          # high when passing, low at the contacts
    sway = .05 * math.sin(2 * math.pi * ph)
    P = O.pose(footL=fL, footR=fR, fpL=aL, fpR=aR)
    P = shift(P, du=bob)
    P = lean(P, .10 + .02 * math.cos(4 * math.pi * ph))
    P['hroll'] = sway * .6
    P['tail'] = tail_curve(ang=-.35 + .08 * math.sin(2 * math.pi * ph + 1), curl=.18, side=.25 * math.sin(2 * math.pi * ph - 1.2))
    P['scarf'] = (-1.4 - .6 * math.sin(4 * math.pi * ph - 1.0), .6 * math.cos(4 * math.pi * ph - 1.0))
    P['whisk'] = 1.0
    return P


def _hatch_clip(M):
    q = M.get('hatch_quad')
    if q is None:
        hx, hy = M['hatch']
        q = ((hx - 240, hy + 100), (hx + 200, hy + 60), (hx + 180, hy - 60), (hx - 160, hy - 40))
    q = np.asarray(q, float)
    nl, nr, fr = q[0], q[1], q[2]
    floor_y = M['ground']

    def clip(ox, oy, w, h):
        yy, xx = np.mgrid[oy:oy + h, ox:ox + w].astype(f32)
        # in front of the near edge: under the floor, hidden
        yl = nl[1] + (xx - nl[0]) * (nr[1] - nl[1]) / (nr[0] - nl[0])
        a = np.clip(yl - yy + .5, 0, 1)
        # right of the right edge and below the floor: hidden too
        xr = fr[0] + (yy - fr[1]) * (nr[0] - fr[0]) / (nr[1] - fr[1])
        b = np.clip(xr - xx + .5, 0, 1)
        c = np.clip(floor_y + 6 - yy + .5, 0, 1)
        return a * np.maximum(b, c)
    return clip


def act_s2(f, M):
    d = tw(f)
    k = M['scale'] / CROWN
    T = S2
    env = None
    hx, hy = M['hatch']
    G = M['ground']
    q = np.asarray(M.get('hatch_quad', ((hx - 240, hy + 100), (hx + 200, hy + 60), (hx + 180, hy - 60), (hx - 160, hy - 40))), float)
    rim_x = q[1][0] * .55 + q[2][0] * .45                # the right edge of the opening, at the floor
    stx, sty = M['step']
    lamp = np.asarray(M['lamp'], float)
    can_c = (10.5, 46.0)
    props, pts, facing, clip = [], {}, None, None
    # ---------------- where it stands to pour: spout on the filler cap
    pour_yaw = 0.0
    Ppour = _pour_pose(1.0)
    Vt = O.View(0, 0, k, yaw=pour_yaw, tilt=.08)
    _, cp = oil_can(Vt, Ppour['_can'], Ppour['_tilt'], env_from(M), k)
    ox_pour = lamp[0] - cp['spout'][0]
    oy_pour = lamp[1] - cp['spout'][1]
    plinth_y = sty
    # if the cap is out of reach the otter rises on its toes (never floats)
    toe = float(np.clip((plinth_y - oy_pour) / k, 0, 4.0))
    x_pl = ox_pour
    x_floor_end = min(x_pl - 70, stx - 90)
    walk_x0 = rim_x + 30
    if d < T['up']:
        # ---------------- climbing out of the hatch, 3/4 toward the right
        clip = _hatch_clip(M)
        dep = keys(d, [(0, 150.0), (T['rise'], 118.0), (T['slap'] - 2, 60.0), (T['heave'], 58.0), (T['knee'] - 2, 24.0), (T['knee'], 20.0), (T['up'], (G - hy) / k)],
                   e=lambda t: out_(t, 1.6))
        x = keys(d, [(0, hx + 40.0), (T['heave'], hx + 50.0), (T['knee'], rim_x - 30.0), (T['up'], walk_x0 - 6.0)])
        y = hy + dep * k                                   # on the ladder: straight down below the hatch floor
        yaw = .75
        P = _hug(O.pose(), can_c)
        P = lean(P, keys(d, [(0, .05), (T['slap'], .12), (T['heave'] + 4, .38), (T['knee'], .30), (T['up'], .12)]))
        # right paw: reaches up, slaps on the floor at the rim, hauls; planted in screen space
        V0 = O.View(x, y, k, yaw=yaw, tilt=.08)
        rim_pt = np.array([rim_x + 34.0, G - 2.0])
        if d >= T['slap']:
            # body space point under the planted paw
            pb = _screen_to_body(V0, rim_pt, depth_r=4.0)
            P['pawR'] = tuple(pb)
            P['elbR'] = (0, 1, .6)
        elif d >= T['rise']:
            t = seg(d, T['rise'], T['slap'])
            P['pawR'] = (12 + 6 * t, 70 + 26 * math.sin(math.pi * t * .8), 8.0)
            P['elbR'] = (0, -1, .5)
        P['ears'] = keys(d, [(T['rise'], .3), (T['slap'], 0.0)])
        P['hyaw'] = keys(d, [(T['rise'], -.35), (T['slap'] + 2, .15), (T['heave'], .05)])
        P['hpitch'] = keys(d, [(T['rise'], .25), (T['slap'], .05), (T['heave'] + 4, -.2), (T['up'], -.05)])
        P['blink'] = blink_at(d, [T['slap'] + 2], 2, 2, 2)
        # feet: on the ladder, then a knee and a foot up onto the boards
        if d >= T['knee'] - 2:
            fb = _screen_to_body(V0, np.array([rim_x + 18.0, G]), depth_r=8.5)
            t = seg(d, T['knee'] - 2, T['knee'] + 2)
            P['footR'] = tuple(np.asarray(O.STAND['footR']) * (1 - t) + fb * t)
        P['tail'] = tail_curve(ang=-.9, curl=.1, ln=34)
        P['scarf'] = (keys(d, [(T['slap'], 0.0), (T['heave'] + 4, -1.0), (T['up'], .6)]), keys(d, [(T['slap'], -1.0), (T['heave'] + 4, 1.0), (T['up'], 0.0)]))
        P['whisk'] = 1.0
        tilt_can = 0.0
    elif d < T['hop']:
        # ---------------- the turn to profile, then a brisk waddle to the plinth
        yaw = keys(d, [(T['up'], .75), (T['turn'], 0.0)])
        if d < T['walk']:
            x = walk_x0 - 6.0 + 6.0 * seg(d, T['up'], T['walk'])
            P = _hug(O.pose(), can_c)
            P = shift(P, du=keys(d, [(T['up'], -2.5), (T['up'] + 2, -3.0), (T['turn'], -1.0), (T['walk'], 0.0)]))
            P['tail'] = tail_curve(ang=-.6, curl=.2)
            P['hpitch'] = keys(d, [(T['up'], -.05), (T['turn'], .12), (T['walk'], 0.0)])
            P['scarf'] = (.8, -.4)
        else:
            steps = max(2, int(round((x_floor_end - walk_x0) / (9.0 * k))))
            step = (x_floor_end - walk_x0) / steps / k
            nfr = T['hop'] - T['walk']
            ph = (d - T['walk']) / nfr * steps / 2.0
            x = walk_x0 + (x_floor_end - walk_x0) * (d - T['walk']) / nfr
            P = _walk(ph, step=step)
            P = _hug(P, (can_c[0] + 1.5, can_c[1] + P['chest'][1] - 51))
            P['blink'] = blink_at(d, [T['walk'] + 16], 2, 2, 2)
        y = G
        facing = 'right' if yaw < .05 else None
        tilt_can = 0.0
    elif d < T['land'] + 2:
        # ---------------- hop up onto the plinth: crouch, stretch, land, squash
        t = seg(d, T['hop'] + 2, T['land'], e=lambda u: u)
        x = x_floor_end + (x_pl - x_floor_end) * t
        hgt = (G - plinth_y) + 40 * math.sin(math.pi * t)
        y = G - (G - plinth_y) * t - 40 * math.sin(math.pi * t) * (0 < t < 1)
        yaw = 0.0
        P = _hug(O.pose(), can_c)
        if d < T['hop'] + 2:
            P = shift(P, du=-5.0); P = lean(P, .25); P['ears'] = .25
        elif d < T['land']:
            P = shift(P, du=2.0); P = lean(P, .05)
            P['footL'] = (-1.0, 1.0, -8.5); P['footR'] = (1.0, 0.5, 8.5); P['fpL'] = P['fpR'] = .5
            P['tail'] = tail_curve(ang=.1, curl=-.1)
            P['scarf'] = (-2.0, 1.2)
        else:
            P = shift(P, du=-4.0); P = lean(P, .18); P['scarf'] = (1.0, -1.6); P['blink'] = .5
        facing = 'right'
        tilt_can = 0.0
    else:
        # ---------------- on the plinth: pour, set down, wipe, pat
        x, y, yaw = x_pl, plinth_y, pour_yaw
        facing = 'right'
        if d < T['set']:
            tt = keys(d, [(T['land'] + 2, 0.0), (T['lift'] + 1, .55), (T['pour'], 1.0), (T['pour_end'], 1.0), (T['down'], .3), (T['set'], 0.0)])
            P = _pour_pose(tt, toe=toe)
            if T['pour'] <= d < T['pour_end']:
                P['_tilt'] += .10 * seg(d, T['pour'], T['pour_end'], e=lambda u: u)   # tips a little more as it empties
                P['squint'] = .25
            if d >= T['down']:
                P = lean(P, .12 * seg(d, T['down'], T['set']))
            P['blink'] = blink_at(d, [T['pour_end'] + 2], 2, 2, 2)
            tilt_can = P['_tilt']
        else:
            P = _wipe_pose(d, toe)
            tilt_can = None
    V = O.View(x, y, k, yaw=yaw, tilt=.08)
    envd = env_from(M)
    # the can: hugged while climbing and walking, poured, then left on the plinth
    if tilt_can is not None:
        cc = P.get('_can')
        if cc is None:
            cc = np.array([P['pawL'][0] + 1.0, P['pawL'][1] - 2.5, 2.5])
        cc = np.asarray(cc, float).copy(); cc[2] = max(cc[2], 2.5)
        fn, cp = oil_can(V, cc, tilt_can, envd, k, seed=d // 6)
        if T['lift'] <= d < T['down']:
            # keep the spout on the filler: the paws carry the can the last little way
            w = seg(d, T['lift'], T['pour'])
            df = (lamp[0] - cp['spout'][0]) / k * w; du = (cp['spout'][1] - lamp[1]) / k * w
            cc = cc + [df, du, 0]
            for kk in ('pawL', 'pawR'): P[kk] = (P[kk][0] + df, P[kk][1] + du, P[kk][2])
            fn, cp = oil_can(V, cc, tilt_can, envd, k, seed=d // 6)
        zc = V.p(cc)[2]
        props.append((zc, fn))
        pts['paw'] = V.p(P['pawR'] if d >= T['hop'] else P['pawL'])[:2]
        pts['can'] = _closest(cp['grip'], pts['paw'], k * 4.2)
        if T['pour'] <= d < T['pour_end']:
            pts['spout'] = cp['spout']
            props.append((zc + 1, oil_stream(V, cp['spout'], lamp, d, envd, k)))
    else:
        # standing on the plinth behind it, where it was put down
        Vc = O.View(x_pl, plinth_y, k, yaw=0.0, tilt=.08)
        fn, cp = oil_can(Vc, (-12.0, 4.6, -6.0), 0.0, envd, k, seed=9)
        props.append((-1e9, fn))
    if d >= T['set']:
        cl = _cloth_point(P, V, k)
        if cl is not None and T['wipe'] <= d < T['done']: pts['cloth'] = cl
    return Perf(x, y, k, yaw, P, props=props, clip=clip, points=pts, facing=facing)


def _closest(a, b, r):
    a, b = np.asarray(a, float), np.asarray(b, float)
    v = b - a; L = np.hypot(*v)
    return a + v / L * min(L, r) if L > 1e-6 else a


def _screen_to_body(V, p, depth_r=0.0):
    """body-space point that projects to screen p at the given r (approximately: solves f, u)"""
    p = np.asarray(p, float)
    A = np.stack([V.M[:2, 0], V.M[:2, 1]], 1) * V.k
    rhs = p - V.o[:2] - V.M[:2, 2] * V.k * depth_r
    fu = np.linalg.solve(A, rhs)
    return np.array([fu[0], fu[1], depth_r])


def _pour_pose(t, toe=0.0):
    """t 0 hugging .. 1 can raised to the filler and tipped"""
    can0, can1 = np.array([12.0, 46.0, 0]), np.array([17.0, 63.0, 0])
    c = can0 * (1 - t) + can1 * t
    P = O.pose(pawL=(c[0] - 2.5, c[1] + 2.0, -4.5), pawR=(c[0] + 1.5, c[1] - 1.5, 4.8), elbL=(0, -1, -1), elbR=(0, -1, 1))
    P = shift(P, du=toe * t, names=('pelvis', 'chest', 'neck', 'head', 'pawL', 'pawR'))
    P['footL'] = (2.5, 2.8 + toe * t * .6, -8.5); P['footR'] = (2.5, 2.8 + toe * t * .6, 8.5)
    P['fpL'] = P['fpR'] = -.35 * toe * t / 4
    P['hpitch'] = .30 * t; P['hyaw'] = 0.0
    P['look'] = (0.0, .6 * t)
    P['tail'] = tail_curve(ang=-.5 + .1 * t, curl=.25)
    P['_can'] = c + [0, toe * t, 0]
    P['_tilt'] = .95 * max(0, (t - .5) / .5)
    P['scarf'] = (.3, 0)
    return P


def _wipe_pose(d, toe):
    """reach up with the scarf end in the right paw, rub small circles, two pats, then a pleased squint"""
    T = S2
    up = keys(d, [(T['set'], 0.0), (T['reach'], .3), (T['wipe'] - 2, 1.05), (T['wipe'], 1.0), (T['done'] - 4, 1.0), (T['done'] + 4, 0.0)])
    ang = (d - T['wipe']) / 6.0 * 2 * math.pi if T['wipe'] <= d < T['pat1'] - 2 else 0.0
    rub = np.array([1.6 * math.cos(ang), 1.6 * math.sin(ang)]) if T['wipe'] <= d < T['pat1'] - 2 else np.zeros(2)
    pat = 0.0
    for p in (T['pat1'], T['pat2']):
        if p - 4 <= d < p: pat = max(pat, (d - (p - 4)) / 4 * 3.0)       # draw back
        elif p <= d < p + 2: pat = max(pat, 0.0)                       # contact
    target = np.array([13.0 - pat, 74.0]) + rub
    P = O.pose(pawR=(target[0] * up + 12 * (1 - up), target[1] * up + 44 * (1 - up), 5.5), pawL=(10.0, 44.0, -5.0), elbR=(-.2, -1, 1), elbL=(.2, -1, -1))
    P['shrugR'] = 4.0 * up
    P = stretch(P, 7.0 * up)
    P = shift(P, du=toe * up)
    P['footL'] = (2.5, 2.8 + toe * up * .6, -8.5); P['footR'] = (2.5, 2.8 + toe * up * .6, 8.5)
    P = lean(P, -.06 * up)
    P['hpitch'] = .38 * up; P['look'] = (0.0, .7 * up)
    P['scarf_to'] = P['pawR'] if d >= T['reach'] else None
    P['tail'] = tail_curve(ang=-.5 + .25 * math.sin((d - T['set']) / 10.0), curl=.25 + .1 * up)
    P['whisk'] = 1.0
    if d >= T['done']:
        P['squint'] = seg(d, T['done'], T['done'] + 4) * .75; P['smile'] = 1.0; P['hpitch'] = .1
        P['ears'] = 0.0
    if T['pat1'] <= d < T['pat1'] + 2 or T['pat2'] <= d < T['pat2'] + 2:
        P['blink'] = .6
    P['scarf'] = (.5 * math.sin(d / 3.0), 0)
    return P


def _cloth_point(P, V, k):
    if P.get('scarf_to') is None: return None
    return V.p(np.asarray(P['scarf_to'], float) + [1.8, 2.4, 0])[:2]


# ================================================================== dispatch
ACTS = {'s2': act_s2}


def _stand_in(key, f, M):
    x = M['x0'] + (M['x1'] - M['x0']) * .5
    k = M['scale'] / CROWN
    return Perf(x, M['ground'], k, .8, O.pose())


def perf(key, f, M):
    fn = ACTS.get(key)
    return fn(f, M) if fn else _stand_in(key, f, M)


def draw(img, key, f, M):
    p = perf(key, f, M)
    if p is None: return img
    env = p.env or env_from(M)
    O.draw(img, p.view(), p.P, env, seed=tw(f) // 2 + 17 * hash(key) % 101, lw=p.lw, clip=p.clip, extra=p.props, parts=p.parts)
    return img


def actors(key, f, M):
    p = perf(key, f, M)
    if p is None: return []
    a = dict(name='水獭', x=float(p.x), y=float(p.y), s=float(p.k * CROWN / STAND_H))
    if p.facing: a['facing'] = p.facing
    if p.points: a['points'] = {k_: [float(v[0]), float(v[1])] for k_, v in p.points.items()}
    return [a]
