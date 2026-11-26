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
    rad, h = 4.8, 9.6
    bot = C(np.c_[rad * np.cos(th), np.full_like(th, -h / 2), rad * np.sin(th)])
    top = C(np.c_[rad * .78 * np.cos(th), np.full_like(th, h / 2), rad * .78 * np.sin(th)])
    sb, stp = V.p(bot)[:, :2], V.p(top)[:, :2]
    hull = cv2.convexHull(np.vstack([sb, stp]).astype(np.float32))[:, 0, :].astype(float)
    sp0, sp1 = C([3.8, 1.8, 0]), C([13.0, 8.6, 0])
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
    L = 6.5 * k
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
            hgt = (5.0 + 6.0 * flare) * k * fl
            wid = (1.8 + 1.6 * flare) * k
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
S2 = dict(rise=16, slap=24, heave=28, knee=38, up=44, turn=52, walk=56, hop=86, land=92, lift=93, pour=96, pour_end=120,
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


def _lip_clip(L0, L1):
    """hide what is below the near lip of the opening: it is inside the well"""
    def clip(ox, oy, w, h):
        yy, xx = np.mgrid[oy:oy + h, ox:ox + w].astype(f32)
        yl = L0[1] + (xx - L0[0]) * (L1[1] - L0[1]) / (L1[0] - L0[0])
        return np.clip(yl - yy + .5, 0, 1)
    return clip


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
    funnel = np.asarray(M.get('filler', M['lamp']), float)
    lamp = np.asarray(M['lamp'], float)                     # where the spout hovers while pouring
    if lamp[1] > funnel[1] - 25: lamp = funnel - [0, 34.0]   # high enough above the funnel for the oil to show
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
    lip = np.asarray(M.get('hatch_lip', (q[0], q[1])), float)
    L0_, L1_ = lip[0], lip[-1]
    lip_y = lambda xx: L0_[1] + (xx - L0_[0]) * (L1_[1] - L0_[1]) / (L1_[0] - L0_[0])
    x_c = L0_[0] + .66 * (L1_[0] - L0_[0])                 # climbs up inside the opening, toward its right side
    y_front = lip_y(x_c + 10) + 30.0                        # on the boards just in front of the lip
    can_floor = np.array([x_c + 62.0, lip_y(x_c + 40) + 24.0])
    walk_x0 = x_c + 14.0
    can_state = 'hug'
    if d < T['up'] + 6:
        # ---------------- up the ladder inside the opening, paws over the near lip, out onto the boards
        yaw = keys(d, [(0, 1.15), (T['knee'], 1.05), (T['up'] + 4, .9)])
        dep = keys(d, [(0, 140.0), (T['rise'], 108.0), (T['slap'] - 2, 60.0), (T['heave'], 58.0), (T['knee'] - 2, 26.0), (T['knee'], 20.0)],
                   e=lambda t: out_(t, 1.6))
        inside = d < T['knee'] + 2
        x = x_c if inside else x_c + 10.0 * seg(d, T['knee'], T['up'])
        y = (lip_y(x_c) - 22.0 + dep * k) if inside else y_front
        clip = _lip_clip(L0_, L1_) if inside else None
        P = O.pose()
        V0 = O.View(x, y, k, yaw=yaw, tilt=.08)
        if d < T['rise'] + 2:
            P = _hug(P, can_c)
        elif d < T['slap']:
            # the right paw lifts the can over the lip and sets it on the boards; the left reaches up
            t = seg(d, T['rise'] + 2, T['slap'] - 2)
            cs = np.array([x_c + 20.0, lip_y(x_c) - 60.0]) * (1 - t) + can_floor * t
            P['pawR'] = tuple(_reach(P, 'R', _screen_to_body(V0, cs + [0, -4.0 * k], depth_r=5.0)))
            P['pawL'] = (10.0, 70.0, -7.0); P['elbL'] = (0, -1, -1)
            pr = V0.p(P['pawR'])[:2]                               # the can hangs from the paw that really holds it
            can_state = ('air', pr + [0, 4.0 * k]) if t < 1 else 'floor'
        if d >= T['slap'] and inside:
            # both paws over the lip, planted; the body hauls up between them
            for kk, dx_, r_ in (('L', -18.0, -6.0), ('R', 20.0, 6.0)):
                tgt = _screen_to_body(V0, np.array([x_c + dx_, lip_y(x_c + dx_) - 3.0]), depth_r=r_)
                P['paw' + kk] = tuple(_reach(P, kk, tgt))
            P['elbL'] = (0, .6, -1); P['elbR'] = (0, .6, 1)
            P = lean(P, keys(d, [(T['slap'], .08), (T['heave'] + 4, .34), (T['knee'], .28)]))
            for kk, dx_, r_ in (('L', -18.0, -6.0), ('R', 20.0, 6.0)):      # keep the paws on the lip after the lean
                tgt = _screen_to_body(V0, np.array([x_c + dx_, lip_y(x_c + dx_) - 3.0]), depth_r=r_)
                P['paw' + kk] = tuple(_reach(P, kk, tgt))
            can_state = 'floor'
            if d >= T['knee'] - 2:
                fb = _screen_to_body(V0, np.array([x_c + 14.0, lip_y(x_c + 14.0) - 2.0]), depth_r=8.5)
                t = seg(d, T['knee'] - 2, T['knee'] + 2)
                P['footR'] = tuple(np.asarray(O.STAND['footR']) * (1 - t) + fb * t)
        elif not inside:
            # out: straighten up, then bend for the can
            can_state = 'floor'
            up_ = seg(d, T['knee'] + 2, T['up'])
            P = shift(P, du=-5.0 * (1 - up_))
            P = lean(P, .25 * (1 - up_))
            if d >= T['up']:
                # squat for the can, then come up with it
                bend = keys(d, [(T['up'], .6), (T['up'] + 2, 1.0), (T['up'] + 4, .45)])
                P = lean(P, .55 * bend); P = shift(P, du=-13.0 * bend)
                P['footL'] = (5.0, 2.8, -9.5); P['footR'] = (5.0, 2.8, 9.5)
                lift_ = seg(d, T['up'] + 2, T['up'] + 4)
                at_ = can_floor * (1 - lift_) + (can_floor + [-6.0, -40.0]) * lift_
                cb = _screen_to_body(V0, at_ + [0, -5.0 * k], depth_r=0.0)
                P['pawL'] = tuple(_reach(P, 'L', cb + [-1.0, 0.0, -3.5])); P['pawR'] = tuple(_reach(P, 'R', cb + [1.0, 0.0, 3.5]))
                pr = (V0.p(P['pawL'])[:2] + V0.p(P['pawR'])[:2]) / 2
                can_state = ('air', pr + [0, 5.0 * k])
        P['ears'] = keys(d, [(T['rise'], .3), (T['slap'], 0.0)])
        P['hyaw'] = keys(d, [(T['rise'], -.3), (T['slap'] + 2, .1), (T['heave'], 0.0)])
        P['hpitch'] = keys(d, [(T['rise'], .2), (T['slap'], .05), (T['heave'] + 4, -.2), (T['up'], -.05)])
        P['blink'] = blink_at(d, [T['slap'] + 2], 2, 2, 2)
        P['tail'] = tail_curve(ang=-.9, curl=.1, ln=34)
        P['scarf'] = (keys(d, [(T['slap'], 0.0), (T['heave'] + 4, -1.0), (T['up'], .6)]), keys(d, [(T['slap'], -1.0), (T['heave'] + 4, 1.0), (T['up'], 0.0)]))
        P['whisk'] = 1.0
        tilt_can = 0.0
    elif d < T['hop']:
        # ---------------- the turn to profile, then a brisk waddle to the plinth
        yaw = keys(d, [(T['up'] + 6, .9), (T['turn'] + 2, 0.0)])
        if d < T['walk']:
            x = walk_x0
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
            # the far arm keeps the can, the near arm swings against the stride
            sw = math.sin(2 * math.pi * ph + .6)
            P['pawR'] = (P['chest'][0] + 2.0 + 6.0 * sw, P['chest'][1] - 14.0 + 1.5 * abs(sw), 10.5)
            P['elbR'] = (-.4, -.2, 1)
            P['blink'] = blink_at(d, [T['walk'] + 16], 2, 2, 2)
        y = y_front + (G - y_front) * (0.0 if d < T['walk'] else (d - T['walk']) / float(T['hop'] - T['walk']))
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
        # a hop is not a walk along the ground: its y is the feet in the air, so no walking direction
        facing = None
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
            # the scarf corner goes onto the glass ring: aim the paw so the cloth lands on M['lens']
            if P['_up'] > 0 and 'lens' in M:
                Vw = O.View(x, y, k, yaw=yaw, tilt=.08)
                tgt_s = np.asarray(M['lens'], float) + np.array([P['_rub'][0], -P['_rub'][1]]) * k - [P['_pat'] * k, 0]
                tb = _screen_to_body(Vw, tgt_s, depth_r=6.0) - [1.8, 2.4, 0]
                cur = np.asarray(P['pawR'], float)
                w = min(1.0, P['_up'])
                P['pawR'] = tuple(_reach(P, 'R', cur * (1 - w) + tb * w))
                if P.get('scarf_to') is not None: P['scarf_to'] = P['pawR']
            # turned three-quarters away, toward the glass, so the stretched paw is on the lens
            if d >= T['done']:
                # pleased: the head comes round toward us with a squint
                P['hyaw'] = -.7 * seg(d, T['done'], T['done'] + 6)
    V = O.View(x, y, k, yaw=yaw, tilt=.08)
    envd = env_from(M)
    # the can: hugged while climbing and walking, poured, then left on the plinth
    if can_state == 'floor' or (isinstance(can_state, tuple) and can_state[0] == 'air'):
        at = can_floor if can_state == 'floor' else can_state[1]
        Vc = O.View(at[0], at[1], k, yaw=.3, tilt=.08)
        fn, cp = oil_can(Vc, (0.0, 4.8, 0.0), 0.0, envd, k, seed=3)
        props.append((-1e9 if can_state == 'floor' else 1e9, fn))
        if can_state != 'floor':
            pts['paw'] = V.p(P['pawR'])[:2]; pts['can'] = _closest(cp['grip'], pts['paw'], k * 4.6)
    elif tilt_can is not None:
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
        zc = V.p(cc)[2] if d < T['lift'] else 'front'
        props.append((zc, fn))
        pts['paw'] = V.p(P['pawR'] if d >= T['hop'] else P['pawL'])[:2]
        pts['can'] = _closest(cp['grip'], pts['paw'], k * 4.2)
        if T['pour'] <= d < T['pour_end']:
            pts['spout'] = cp['spout']
            props.append(('front', oil_stream(V, cp['spout'], funnel, d, envd, k)))
    else:
        # standing on the plinth behind it, where it was put down
        Vc = O.View(x_pl, plinth_y, k, yaw=0.0, tilt=.08)
        fn, cp = oil_can(Vc, (-12.0, 4.6, -6.0), 0.0, envd, k, seed=9)
        props.append((-1e9, fn))
    if d >= T['set']:
        cl = _cloth_point(P, V, k)
        if cl is not None and T['wipe'] <= d < T['done']: pts['cloth'] = cl
    return Perf(x, y, k, yaw, P, props=props, clip=clip, points=pts, facing=facing)


def _dpoly(p, R):
    best = 1e9
    for a, b in zip(R[:-1], R[1:]):
        t = np.clip(np.dot(p - a, b - a) / np.dot(b - a, b - a), 0, 1)
        best = min(best, float(np.hypot(*(p - (a + t * (b - a))))))
    return best


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
    can0, can1 = np.array([12.0, 46.0, 0]), np.array([21.5, 60.0, 0])
    c = can0 * (1 - t) + can1 * t
    P = O.pose(pawL=(c[0] - 2.5, c[1] + 2.0, -4.5), pawR=(c[0] + 1.5, c[1] - 1.5, 4.8), elbL=(0, -1, -1), elbR=(0, -1, 1))
    P = shift(P, du=toe * t, names=('pelvis', 'chest', 'neck', 'head', 'pawL', 'pawR'))
    P['footL'] = (2.5, 2.8 + toe * t * .6, -8.5); P['footR'] = (2.5, 2.8 + toe * t * .6, 8.5)
    P['fpL'] = P['fpR'] = -.35 * toe * t / 4
    P['hpitch'] = .55 * t; P['hyaw'] = -.25 * t
    P['head'] = (P['head'][0] - 6.5 * t, P['head'][1] + .5 * t, 0.0)
    P['neck'] = (P['neck'][0] - 3.0 * t, P['neck'][1], 0.0)
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
    target = np.array([16.0 - pat, 66.0]) + rub * 1.6
    P = O.pose(pawR=(target[0] * up + 12 * (1 - up), target[1] * up + 44 * (1 - up), 6.0), pawL=(10.0 + 4 * up, 48.0 + 10 * up, -6.0), elbR=(-.2, -1, 1), elbL=(.2, -1, -1))
    P['shrugR'] = 4.0 * up
    P = stretch(P, 7.0 * up)
    P = shift(P, du=toe * up)
    P['footL'] = (2.5, 2.8 + toe * up * .6, -8.5); P['footR'] = (2.5, 2.8 + toe * up * .6, 8.5)
    P = lean(P, -.06 * up)
    P['hpitch'] = .62 * up; P['look'] = (.3, .9 * up)
    P['head'] = (P['head'][0] - 5.0 * up, P['head'][1] - 1.0 * up, 0.0)
    P['neck'] = (P['neck'][0] - 2.5 * up, P['neck'][1], 0.0)
    P['_up'], P['_rub'], P['_pat'] = up, rub, pat
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



def mixlight(a, b, t):
    """blend two light dicts (direction, colour, strength)"""
    da, db = np.asarray(a['dir'], float), np.asarray(b['dir'], float)
    d = da / np.hypot(*da) * (1 - t) + db / np.hypot(*db) * t
    if np.hypot(*d) < 1e-3: d = db
    ca, cb = rgb(a['color']), rgb(b['color'])
    return dict(dir=tuple(d), color=ca * (1 - t) + cb * t, amt=a.get('amt', .7) * (1 - t) + b.get('amt', .7) * t)


# ================================================================== s3: the close-up
# whiskers, a real blink at 1.0 s, the eyes then the head go to the window; 2.8 s lightning: cold light
# from the window side, the ears go down.
def act_s3(f, M):
    k = M['scale'] / CROWN
    ff = int(M['flash']['f']) if 'flash' in M else 67
    d = tw(f)
    P = O.pose()
    br = .45 * math.sin(2 * math.pi * f / 46.0)                     # breathing (on ones: tiny)
    P = shift(P, du=br * .5, names=('chest', 'neck', 'head', 'pawL', 'pawR'))
    # the eyes go first, the head leads, the body follows round to three-quarters toward the window
    P['hyaw'] = keys(d, [(0, .05), (44, .05), (48, -.25), (54, -.55), (62, -.12), (66, -.16)], e=ease)
    byaw = keys(d, [(0, .72), (48, .72), (62, 2.30), (66, 2.26)], e=ease)
    P['hroll'] = keys(d, [(0, 0.0), (32, 0.0), (38, .08), (46, .04), (58, -.04)])
    P['hpitch'] = keys(d, [(0, .02), (44, .02), (56, .08), (ff, .06), (ff + 4, -.04)])
    lx = keys(f, [(0, .25), (42, .25), (44, -.6), (46, -1.0), (56, -.4), (62, .35)], e=lambda t: t)
    P['look'] = (lx, keys(d, [(0, .1), (44, .1), (50, .25)]))
    # the blink is on ones: two frames closing, three shut, three opening
    fb = int(round(M.get('blink', 1.0) * 24)) if isinstance(M.get('blink', None), (int, float)) else 24
    P['blink'] = blink_at(f, [fb], 2, 3, 3)
    P['ears'] = keys(d, [(0, 0.0), (ff, 0.0), (ff + 2, .55), (ff + 6, 1.0), (ff + 8, .9)])
    P['squint'] = keys(d, [(ff, 0.0), (ff + 2, .35), (ff + 8, .12)])
    P['mouth'] = keys(d, [(ff + 2, 0.0), (ff + 8, .16), (ff + 20, .12)])
    P['squint'] = 0.0 if f >= ff + 8 else P['squint']
    P['whisk'] = 1.0
    # whiskers twitch in little bursts (held drawings in between)
    P['wph'] = keys(tw(f, 3), [(0, 0.0), (9, 1.4), (15, 1.2), (51, 1.2), (57, 3.0), (ff, 3.0), (ff + 3, 5.5), (ff + 9, 5.0)], e=lambda t: t)
    P['scarf'] = (0.0, 0.0)
    P['pawL'] = (9.0, 38.0, -6.0); P['pawR'] = (9.0, 38.0, 6.0)
    # light: the lamp from the right; the flash from the window side, then falling back
    L0 = M['light']; Lf = M.get('flash', dict(dir=(-1, -.3), color='#c8d4f0', amt=1.0))
    # the flash: full for two frames, then gone in about 0.3 s; a hard cold key from the window side
    t = 0.0
    if f >= ff: t = 1.0 if f < ff + 2 else math.exp(-(f - ff - 1) / 3.0)
    fx = M.get('flash')
    if callable(fx):
        r_ = fx(f)
        t = float(r_['amt']) if isinstance(r_, dict) else float(r_)
    if t > .22:
        L = dict(dir=Lf['dir'], color=Lf['color'], amt=Lf.get('amt', 1.0) * min(1.0, .35 + t))
        env = O.Env(L, amb='#1c2238', rim=.6, thr=.18, front=.35, glint='#f4f8ff')
    else:
        # once turned to the window the lamp is behind it: the face sits in shadow with a warm rim
        fr = .55 - .5 * seg(byaw, .9, 2.2, e=lambda u: u)
        env = O.Env(L0, amb='#2c2a48', rim=1.0 + .4 * (.55 - fr), front=fr)
    return Perf(M['x0'], M['ground'], k, byaw, P, tilt=.03, env=env, parts=('torso', 'head', 'scarf', 'armL', 'armR'))


# ================================================================== s5: the light goes out
# By the lamp, looking toward the rattling window.  1.5 s the casement slams: a start (up), then a
# cringe.  It turns to the lamp and runs to shield it; 3.5 s the flame dies.  Dark: a silhouette and two
# eye glints; the still beat; then the head comes round toward the window.
STILL = (116, 142)


def act_s5(f, M):
    k = M['scale'] / CROWN
    d = tw(f)
    fo, fx = 36, 84
    G = M['ground']
    x0 = M['x1'] - 110.0          # right of the hatch, in front of the plinth
    xl = M['x1'] + 10.0
    P = O.pose()
    yaw = math.pi                                     # profile, facing the window (left)
    facing = 'left'
    x = x0
    P['scarf'] = (.4 * math.sin(d / 5.0), 0)
    if d < fo:
        P['ears'] = keys(d, [(0, .15), (10, .15), (12, .35), (16, .1), (24, .1), (26, .4), (30, .15)])
        P['hpitch'] = .08
        P['look'] = (.3, .2)
        P['pawL'] = (8.0, 40.0, -6.0); P['pawR'] = (8.0, 40.0, 6.0)
        P['blink'] = blink_at(d, [18], 2, 2, 2)
    elif d < 60:
        # the start: squash, then a stretched jolt off the floor, then a cringe with the paws up
        t = d - fo
        if t < 2:
            P = shift(P, du=-4.0); P['ears'] = .4; P['blink'] = .4
        elif t < 6:
            P = stretch(P, 6.0); P = shift(P, du=6.0 if t < 4 else 3.0, names=('pelvis', 'chest', 'neck', 'head', 'pawL', 'pawR'))
            P['footL'] = (1.0, 2.8 + (8.0 if t < 4 else 3.0), -8.5); P['footR'] = (3.0, 2.8 + (8.0 if t < 4 else 3.0), 8.5)
            P['pawL'] = (6.0, 58.0, -9.0); P['pawR'] = (8.0, 60.0, 9.0)
            P['mouth'] = .7; P['ears'] = 0.0
            P['tail'] = tail_curve(ang=.4, curl=-.1)
            P['scarf'] = (-2.0, 2.5)
        else:
            c = seg(d, fo + 6, fo + 12)
            P = shift(P, du=-7.0 * c); P = lean(P, -.15 * c)
            P['pawL'] = (10.0, 62.0 - 6 * c, -7.0); P['pawR'] = (11.0, 63.0 - 6 * c, 7.0)
            P['elbL'] = (.2, -1, -1); P['elbR'] = (.2, -1, 1)
            P['ears'] = .5 + .5 * c; P['mouth'] = .35 * (1 - c); P['squint'] = .4 * c
            P['hpitch'] = -.15 * c
            P['tail'] = tail_curve(ang=-.9, curl=.45)
            P['scarf'] = (1.2 * math.sin(d / 2.0), 1.0)
    else:
        # turn and run to the lamp (on the right); reach up as it dies; then freeze
        if d < 66:
            yaw = keys(d, [(60, math.pi), (66, 0.0)])
            facing = None
            P = shift(P, du=-4.0)
            P['ears'] = .6
            P['pawL'] = (9.0, 50.0, -6.0); P['pawR'] = (9.0, 50.0, 6.0)
        elif d < 78:
            yaw = 0.0; facing = 'right'
            steps = 2
            ph = (d - 66) / 12.0 * steps / 2
            x = x0 + (xl - x0) * (d - 66) / 12.0
            P = _walk(ph, step=(xl - x0) / steps / k, lift=4.0)
            P = lean(P, .2)
            P['ears'] = .5
            P['pawL'] = (P['chest'][0] + 6, P['chest'][1] + 2, -7.0); P['pawR'] = (P['chest'][0] + 7, P['chest'][1] + 3, 7.0)
        else:
            yaw = 0.0; facing = 'right'; x = xl
            reach = seg(d, 78, fx)
            P = stretch(P, 5.0 * reach)
            P['pawL'] = (12.0, 50 + 18 * reach, -6.0); P['pawR'] = (14.0, 52 + 20 * reach, 6.0)
            P['shrugL'] = P['shrugR'] = 3 * reach
            P['elbL'] = (0, -1, -1); P['elbR'] = (0, -1, 1)
            P['hpitch'] = .45 * reach; P['look'] = (.3, .9)
            P['ears'] = .3
            P['footL'] = (2.5, 2.8 + 3 * reach, -8.5); P['footR'] = (2.5, 2.8 + 3 * reach, 8.5)
            P = shift(P, du=3 * reach)
            if d >= fx:
                # the dark: a slow sink of the arms, then complete stillness, then the head turns to the window
                sink = seg(d, fx + 4, STILL[0] - 6)
                P['pawL'] = (12.0 - 2 * sink, 68 - 20 * sink, -6.0); P['pawR'] = (14.0 - 2 * sink, 72 - 22 * sink, 6.0)
                P['hpitch'] = .45 - .35 * sink
                P['look'] = (.3 - .2 * sink, .9 - .7 * sink)
                P['ears'] = .3 + .5 * sink
                if d >= STILL[1]:
                    tt = seg(d, STILL[1] + 2, STILL[1] + 14)
                    P['hyaw'] = 1.0 * tt; P['look'] = (.1 + .6 * tt, .1)
                    P['blink'] = blink_at(d, [STILL[1] + 16], 2, 2, 4)
    # tail and whiskers settle with the body; nothing moves inside the still beat
    if d >= STILL[0] and d < STILL[1]:
        d = STILL[0]
    P['wph'] = 0.4 * (d // 6) if d < fx else 0.4 * (fx // 6)
    # light: the lamp (warm, guttering) until it dies; then the storm through the open window, dark
    Lw = M.get('lamp_light', dict(dir=(.6, -.8), color='#ffb458', amt=.8)); Ls = M['light']
    if d < fx:
        gut = 1.0 if d < fo else .55 + .35 * abs(math.sin(d * 1.3)) * (1 - (d - fo) / (fx - fo))
        L = dict(Lw); L['amt'] = Lw.get('amt', .8) * gut
        env = O.Env(L, amb='#2c2a48' if d < fo else '#232a44', dark=0.0 if d < fo else .25 * (d - fo) / (fx - fo))
    else:
        env = O.Env(Ls, amb='#141a2a', dark=.9, rim=1.4, glint='#e8f0ff', line='#0c0e18')
    seed = None if not (STILL[0] <= tw(f) < STILL[1]) else STILL[0] // 2
    p = Perf(x, G, k, yaw, P, env=env, facing=facing)
    p.seed = seed
    return p


# ================================================================== s7: relit
# On the window ledge, shouldering the casement shut against the wind (1.5 s, latch); down, across the
# room, up the plinth and the brass tank to the flange; 4.0 s strikes a match on the brass and cups it;
# 5.5 s the match to the wick; 7.0 s the light opens out and it stands and looks.
S7 = dict(shut=36, latch=42, jump=48, land=56, run=58, hop=76, climb=82, top=92, strike=96, catch=132, back=142, bloom=168)


def _casement_edge(M, f, push):
    """the casement's free edge in frame px: from the set if it gives one, else a stand-in swing"""
    c = M.get('casement')
    if callable(c):
        e = c(f)
        if isinstance(e, dict) and e.get('edge') is not None: return np.asarray(e['edge'], float), True
    wx, wy = M['window']
    return np.array([wx + 75.0 + 95.0 * (1 - push), wy + 25.0]), False


def _shoulder(P, side):
    ch = np.asarray(P['chest'], float)
    return ch + [1.0, 3.5, side * 10.0] + np.array([.6, 1.0, -side * .3]) * P.get('shrug' + ('L' if side < 0 else 'R'), 0.0)


def _reach(P, key, target, V=None):
    """where a paw really ends up (arm length clamps it), body space"""
    side = -1 if key == 'L' else 1
    ax = P.get('armx' + key, 1.0)
    _, pw = O.ik2(_shoulder(P, side), target, 9.4 * ax, 8.8 * ax, P['elb' + key])
    return pw


def act_s7(f, M):
    k = M['scale'] / CROWN
    d = tw(f)
    T = S7
    G = M['ground']
    wx, wy = M['window']
    sx, sy = M['sill']
    stx, sty = M['step']
    wkx, wky = M['wick']
    fil = M.get('filler', M['lamp'])
    lg = M.get('ledge')
    if lg is None: lg = (wkx - 150.0, wkx - 40.0, float(fil[1]))
    lg_x0, lg_x1, lg_y = float(lg[0]), float(lg[1]), float(lg[2])
    run_y = M.get('run_y', G - 80.0)
    props, pts, facing = [], {}, None
    P = O.pose()
    yaw = math.pi
    md = np.array([1.0, -.55]); md /= np.hypot(*md)            # the match points up and forward
    if d < T['jump']:
        # ---------------- on the sill: shoulder and both paws against the casement, feet braced
        facing = 'left'
        push = keys(d, [(0, .15), (8, .5), (12, .3), (16, .32), (26, .8), (30, .7), (T['shut'], 1.0), (T['latch'] + 6, 1.0)])
        strain = 1.0 if d < T['shut'] else 1 - seg(d, T['shut'] + 2, T['latch'] + 6)
        E, _ = _casement_edge(M, f, push)
        P = lean(P, .48 * strain + .06)
        # braced shuffle: as the casement gives, the feet take short pushing steps (planted while in stance)
        E0, _ = _casement_edge(M, 0, .15)
        moved = max(0.0, (E0[0] - E[0]) / k)
        W_ = _walk(moved / 16.0, step=8.0, lift=2.5)
        P['footL'] = (W_['footL'][0] - 10.0 * strain, W_['footL'][1], -8.5); P['footR'] = (W_['footR'][0] - 15.0 * strain, W_['footR'][1], 8.5)
        P['fpL'] = W_['fpL'] - .2 * strain; P['fpR'] = W_['fpR'] - .45 * strain
        P['shrugL'] = P['shrugR'] = 3.0 * strain
        P['elbL'] = (0, -1, -1); P['elbR'] = (0, -1, 1)
        y = sy
        x = E[0] + 20.0 * k                                    # facing left: arm's length from the edge
        for _ in range(3):                                     # walk the body until the paws reach it
            V0 = O.View(x, y, k, yaw=yaw, tilt=.08)
            S = V0.p(_shoulder(P, 1))[:2]
            dd = np.hypot(*(E - S)); want = 16.5 * k
            if abs(dd - want) < 1: break
            x += (dd - want) * (1 if E[0] > S[0] else -1) * (abs(E[0] - S[0]) / (dd + 1e-6))
        V0 = O.View(x, y, k, yaw=yaw, tilt=.08)
        tR = _screen_to_body(V0, E, depth_r=6.0)
        tL = _screen_to_body(V0, E + [0, 9.0 * k], depth_r=-4.0)
        if d >= T['shut']:
            # the latch: the near paw slides down the frame and presses it home
            l_ = seg(d, T['shut'], T['latch'])
            tR = _screen_to_body(V0, E + [0, 2.5 * k * l_], depth_r=6.0)
        P['pawR'] = tuple(_reach(P, 'R', tR)); P['pawL'] = tuple(_reach(P, 'L', tL))
        P['squint'] = .7 * strain; P['ears'] = .9 * strain
        P['mouth'] = (.25 if (d // 4) % 2 else .1) * strain
        P['hpitch'] = .05; P['hyaw'] = -.15 * strain
        P['tail'] = tail_curve(ang=-.35 + .25 * strain, curl=.12)
        P['scarf'] = (-2.5 * strain - .3, 1.2 * math.sin(d / 2.0) * strain)
        if d < T['latch'] + 4: pts['push'] = V0.p(P['pawR'])[:2]
        if d >= T['shut']: P['blink'] = blink_at(d, [T['latch'] + 2], 2, 2, 2)
        x_ledge = x
    elif d < T['hop']:
        # ---------------- jump down, dash behind the hatch to the lamp
        x_start = sx + 95.0
        V0 = None
        x_land = sx + 150.0
        x_run1 = stx - 110.0
        if d < T['land']:
            t = seg(d, T['jump'], T['land'], e=lambda u: u)
            x = x_start * (1 - t) + x_land * t
            y = sy * (1 - t) + run_y * t - 90 * math.sin(math.pi * t)
            if t < .6: P = stretch(P, 4.0)
            P['footL'] = (-2.0, 1.0, -8.5); P['footR'] = (0.0, .5, 8.5)
            P['pawL'] = (14.0, 56.0, -6.0); P['pawR'] = (15.0, 58.0, 6.0)
            P['tail'] = tail_curve(ang=.5, curl=-.15)
            P['scarf'] = (-2.0, 2.5)
        else:
            nfr = T['hop'] - T['land']
            t = (d - T['land']) / float(nfr)
            x = x_land + (x_run1 - x_land) * t
            y = run_y
            steps = 6
            P = _walk(t * steps / 2, step=(x_run1 - x_land) / steps / k, lift=5.0)
            P = lean(P, .32)
            if d < T['run']: P = shift(P, du=-5.0)
            P['pawL'] = (P['chest'][0] + 8, P['chest'][1] - 6, -8.0); P['pawR'] = (P['chest'][0] + 7, P['chest'][1] - 5, 8.0)
            P['ears'] = .7
        yaw = 0.0; facing = 'right'
    else:
        # ---------------- where to stand on the ledge so the match reaches the wick
        yaw = 0.0
        Vt = O.View(0.0, lg_y, k, yaw=0.0, tilt=.08)
        hold_t = np.array([13.0, 44.0, -3.0])                    # the far paw, holding the match out
        ps = Vt.p(hold_t)[:2]
        wick_paw = np.array([wkx, wky]) - md * 7.1 * k           # paw position that puts the head on the wick
        x_st = float(np.clip(wick_paw[0] - 15.0 * k, lg_x0 + 10, lg_x1 - 10))   # the wick an easy forearm's reach away
        if d < T['top']:
            facing = 'right'
            if d < T['climb']:
                t = seg(d, T['hop'], T['climb'], e=lambda u: u)
                x = (stx - 110.0) * (1 - t) + (x_st - 20) * t
                y = run_y * (1 - t) + sty * t - 40 * math.sin(math.pi * t)
                P['footL'] = (-1.0, 1.0, -8.5); P['footR'] = (1.0, .5, 8.5)
                P['tail'] = tail_curve(ang=.1, curl=-.1)
            else:
                # paw over paw up the brass to the ledge
                t = seg(d, T['climb'], T['top'] - 2)
                x = (x_st - 20) * (1 - t) + x_st * t
                y = sty * (1 - t) + lg_y * t
                ph = (d - T['climb']) / 4.0
                P = lean(P, .25)
                P['pawL'] = (14.0, 64 + 6 * math.sin(ph * math.pi), -6.0); P['pawR'] = (14.0, 64 - 6 * math.sin(ph * math.pi), 6.0)
                P['footL'] = (8.0, 6 + 5 * max(0, math.sin(ph * math.pi)), -8.5); P['footR'] = (8.0, 6 + 5 * max(0, -math.sin(ph * math.pi)), 8.5)
                P['tail'] = tail_curve(ang=-1.1, curl=.1, ln=36)
                P['ears'] = .6
            lit = None
        else:
            x, y = x_st, lg_y
            facing = 'right'
            V0 = O.View(x, y, k, yaw=yaw, tilt=.08)
            wick = np.array([wkx, wky], float)
            P['elbL'] = (.3, -.5, -1); P['elbR'] = (.2, -.6, 1)
            if d < T['strike']:
                # anticipation: the match drawn back against the brass
                a = seg(d, T['top'], T['strike'])
                P['pawL'] = (6.0 + 6 * a, 40.0 - 4 * a, -4.0); P['pawR'] = (9.0, 44.0, 6.0)
                P = lean(P, .1 * a); P['squint'] = .3 * a; P['ears'] = .4
                lit = 0.0
            elif d < T['catch'] - 6:
                # struck: held in the far paw, the body curled over it, the near paw cupped round the flame
                P['pawL'] = (11.0, 44.0, -3.0)
                P['pawR'] = (14.5, 47.0, 4.0)
                P = lean(P, .26)
                P['hpitch'] = -.3; P['look'] = (.4, -.6)
                P['ears'] = keys(d, [(T['strike'], .2), (T['strike'] + 2, .9), (T['strike'] + 8, .5)])
                P['squint'] = keys(d, [(T['strike'], .7), (T['strike'] + 6, .2)])
                P['blink'] = blink_at(d, [T['strike']], 1, 2, 2)
                P['scarf'] = (1.2, .4 * math.sin(d / 3.0))
                lit = (d - T['strike']) / 36.0
            else:
                reach = seg(d, T['catch'] - 6, T['catch'])
                back = seg(d, T['back'], T['back'] + 6)
                pb = _screen_to_body(V0, wick - md * 7.1 * k, depth_r=-3.0)
                hold = np.array([11.0, 44.0, -3.0])
                q = hold * (1 - reach) + pb * reach
                q = q * (1 - back) + np.array([8.0, 42.0, -6.0]) * back
                P = lean(P, (.26 * (1 - reach) + .12 * reach) * (1 - back))
                P['pawL'] = tuple(q)
                P['armxL'] = 1.0 + .2 * reach * (1 - back)        # the last little stretch to the wick
                P['pawR'] = (14.5 + 3 * reach, 47.0 + 2 * reach, 4.0)
                P['hpitch'] = .05 * reach; P['look'] = (.6, .1)
                P['ears'] = .2
                lit = 1.0 if d < T['back'] + 8 else 0.0
                if d >= T['back'] + 8:
                    P['pawR'] = (9.0, 42.0, 6.0)
                if d >= T['bloom']:
                    tb = seg(d, T['bloom'], T['bloom'] + 10)
                    P['hpitch'] = .35 * tb; P['look'] = (.2, .8 * tb)
                    P['squint'] = .55 * tb; P['smile'] = 1.0 * tb
                    P['ears'] = 0.0
                    P['pawR'] = (9.0, 42.0, 6.0); P['pawL'] = (9.0, 42.0, -6.0)
            Vm = O.View(x, y, k, yaw=yaw, tilt=.08)
            pw = Vm.p(P['pawL'])[:2]
            if lit is not None and (lit > 0 or d < T['strike']):
                fn, mp = match_and_flame(Vm, pw, d, min(lit, .99) if lit > 0 else 0.0, O.Env(M['light']), k, d=tuple(md))
                # between the far paw that holds it and the near paw that shields it
                zL, zR = Vm.p(P['pawL'])[2], Vm.p(P['pawR'])[2]
                props.append(((zL + zR) / 2.0 + 2.0 * k, fn))
                if lit > 0 and d < T['back'] + 8: pts['match'] = mp['match']
    # light: storm (cold, dark) until the match; the match warms the face; then the lamp
    Ls = M['light']; Lw = M.get('lamp_light', dict(dir=(.6, -.8), color='#ffb458', amt=.9))
    if d < T['strike']:
        env = O.Env(Ls, amb='#141a2a', dark=.55, rim=1.3, glint='#e8f0ff')
    elif d < T['catch']:
        env = O.Env(dict(dir=(.9, .2), color='#ffb070', amt=.75), amb='#1a1a2e', dark=.25, rim=1.2)
    else:
        t = seg(f, T['catch'], T['bloom'] + 12)
        L = mixlight(dict(dir=(.9, .2), color='#ffb070', amt=.7), Lw, t)
        env = O.Env(L, amb='#2c2a48', dark=.25 * (1 - t))
    return Perf(x, y, k, yaw, P, props=props, points=pts, facing=facing, env=env)


# ================================================================== s9: dawn
# Draped over the rail, wet and tired.  3.0 s and 3.6 s the horn: the ears, the head comes up, a paw
# waves; then it settles, squints into the sun; the tail curls.
def _rail_y(R, x):
    R = np.asarray(R, float)
    return float(np.interp(x, R[:, 0], R[:, 1]))


def _rail_clip(R, half):
    """hide what is behind the bar (the body leaning on it); arms and head lie over it"""
    R = np.asarray(R, float)

    def clip(ox, oy, w, h):
        yy, xx = np.mgrid[oy:oy + h, ox:ox + w].astype(f32)
        yr = np.interp(xx, R[:, 0], R[:, 1]).astype(f32)
        return np.clip(np.abs(yy - yr) - half + .5, 0, 1)
    return clip


def act_s9(f, M):
    k = M['scale'] / CROWN
    d = tw(f, 3) if f > 160 else tw(f)
    rail = np.asarray(M.get('lean_rail', M['rail']), float)
    rw = float(M.get('rail_w', 2.2 * k))
    h1, h2 = 72, 86
    # stands on the walkway behind the bar, forearms folded over it, chest against it
    x = float(M['x0'] + M['x1']) / 2 if 'x0' in M else float(rail[len(rail) // 2][0])
    ry = _rail_y(rail, x)
    feet = float(M['deck']) if 'deck' in M else float(M['ground'])
    yaw = .42
    V0 = O.View(x, feet, k, yaw=yaw, tilt=.10)
    P = O.pose()
    P = lean(P, .16)
    lift = keys(d, [(0, 0.0), (h1 + 2, 0.0), (h1 + 8, 1.0), (140, 1.0), (152, .35)])
    br = .5 * math.sin(2 * math.pi * f / 60.0)
    P = shift(P, du=br * .4, names=('chest', 'neck', 'head'))
    # head: resting on the forearms, then up at the horn
    P['head'] = (P['head'][0] + 3.0 - 1.0 * lift, P['head'][1] - 7.0 * (1 - lift), 0.0)
    P['hpitch'] = -.32 * (1 - lift) + .12 * lift
    P['hyaw'] = -.15 * lift
    # forearms over the bar: paws a little past it, elbows on it
    bar = _screen_to_body(V0, np.array([x + 2.0 * k, ry - .55 * rw]), depth_r=0.0)
    P['pawL'] = (bar[0] + 9.0, bar[1] - 1.0, -5.0); P['pawR'] = (bar[0] + 9.0, bar[1] + .5, 5.0)
    P['elbL'] = (-.3, -1, -.6); P['elbR'] = (-.3, -1, .6)
    wv = seg(d, h2 + 2, h2 + 8) * (1 - seg(d, 128, 136))
    if wv > 0:
        # a clear wave: the paw goes up over the head and swings twice
        sw = math.sin((d - (h2 + 8)) / 10.0 * 2 * math.pi) if d >= h2 + 8 else 0.0
        keepL = P['pawL']
        P = stretch(P, 5.0 * wv)
        P['pawL'] = (keepL[0], keepL[1] - 2.0 * wv, keepL[2])   # the other forearm stays on the bar
        P['shrugR'] = 7.0 * wv
        P['armxR'] = 1.0 + .38 * wv
        up_ = _shoulder(P, 1) + np.array([-3.0 + 7.0 * sw, 24.0 - 2.0 * abs(sw), 8.0])
        P['pawR'] = tuple(np.array(P['pawR'], float) * (1 - wv) + up_ * wv)
        P['elbR'] = (.2, -.3, 1)
        P['mouth'] = .35 if h2 + 4 <= d < 110 else 0.0
    P['footL'] = (2.0, 2.8, -8.5); P['footR'] = (4.0, 2.8, 8.5)
    curl = keys(d, [(0, .2), (210, .2), (228, .7), (246, .45), (264, .8)])
    P['tail'] = tail_curve(ang=-.25, curl=.15 + .35 * curl, ln=40)
    P['ears'] = keys(d, [(0, .45), (h1, .45), (h1 + 2, 0.0), (150, 0.0), (160, .3), (216, .3), (218, 0.0), (224, .3)])
    P['squint'] = keys(d, [(0, .45), (h1, .45), (h1 + 2, 0.0), (140, 0.0), (170, .4), (190, .8)])
    P['blink'] = keys(d, [(0, .5), (h1, .5), (h1 + 2, 0.0)]) if d < h1 + 2 else blink_at(d, [112, 176], 2, 3, 3)
    P['smile'] = keys(d, [(96, 0.0), (104, 1.0)])
    P['look'] = keys(d, [(0, (0.0, -.3)), (h2, (0.0, -.3)), (h2 + 4, (-.3, -.7)), (140, (-.3, -.7)), (160, (.7, .3))])
    P['wet'] = keys(d, [(0, 1.0), (312, .6)], e=lambda t: t)
    P['wph'] = .5 * (d // 8)
    P['scarf'] = (.3, -.6)
    env = O.Env(M['light'], amb='#8d7a98', rim=1.2, thr=.02)
    # the set draws the bar over the otter, so the body needs no clip of its own
    p = Perf(x, feet, k, yaw, P, tilt=.10, env=env)
    # contact: the near forearm where it crosses the bar
    sh = _shoulder(P, 1)
    el, pw = O.ik2(sh, np.asarray(P['pawR'] if wv <= 0 else P['pawL'], float), 9.4, 8.8, P['elbR'] if wv <= 0 else P['elbL'])
    a2, b2 = V0.p(el)[:2], V0.p(pw)[:2]
    best = min((a2 * (1 - t) + b2 * t for t in np.linspace(0, 1, 21)), key=lambda q: _dpoly(q, rail))
    p.points = {'elbow': best}
    return p


# ================================================================== dispatch
ACTS = {'s2': act_s2, 's3': act_s3, 's5': act_s5, 's7': act_s7, 's9': act_s9}


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
    sd = getattr(p, 'seed', None)
    sd = (tw(f) // 2 if sd is None else sd) + 17 * (sum(map(ord, key)) % 101)
    between = M.get('between')
    if callable(between):
        # body, far arm, head, tail -> whatever the set puts between (a rail) -> the near forearm over it
        near = getattr(p, 'near_arm', 'armR')
        allp = ('torso', 'head', 'scarf', 'armL', 'armR', 'legL', 'legR', 'tail')
        base = tuple(q for q in (p.parts or allp) if q != near)
        O.draw(img, p.view(), p.P, env, seed=sd, lw=p.lw, clip=p.clip, extra=p.props, parts=base)
        img = between(img, f)
        if p.parts is None or near in p.parts:
            O.draw(img, p.view(), p.P, env, seed=sd, lw=p.lw, clip=p.clip, parts=(near,))
        return img
    O.draw(img, p.view(), p.P, env, seed=sd, lw=p.lw, clip=p.clip, extra=p.props, parts=p.parts)
    return img


def actors(key, f, M):
    p = perf(key, f, M)
    if p is None: return []
    a = dict(name='水獭', x=float(p.x), y=float(p.y), s=float(p.k * CROWN / STAND_H))
    if p.facing: a['facing'] = p.facing
    if p.points: a['points'] = {k_: [float(v[0]), float(v[1])] for k_, v in p.points.items()}
    return [a]
