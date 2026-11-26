"""s2 The lamp room (192 f).  Interior lane.

Warm and quiet: the flame in its drum of glass rings, the lens turning slowly, amber light on the
brass, the boards and the whitewash; a cold blue night in every window.  The otter climbs up out of
the hatch (1.0 s), pours oil into the tank (4.0 s) and wipes the lens with the end of its scarf (6.0 s).
"""
import math
import numpy as np, cv2
from lp import W, H, comp
from lp.paint import rgb, f32
import otteract
import lamproom as LR

cv2.setNumThreads(2)


def flicker(f, amt=.035):
    """slow breathing of an oil flame, changed on threes so it never pops"""
    d = f / 3.0
    k = int(d); t = d - k
    a = np.random.default_rng(310 + k).normal(0, 1); b = np.random.default_rng(311 + k).normal(0, 1)
    t = t * t * (3 - 2 * t)
    return 1 + amt * (a * (1 - t) + b * t)


class Shot:
    n = 192
    finish = dict(hal_amt=.24, vig=.14)
    # Marks for the otter, in frame pixels at the shot's own (very slow) camera; the push-in is applied
    # to the finished picture, so draw in these coordinates.
    #   ground: floor y in front of the lamp; hatch: centre of the floor opening (its floor y is 940);
    #   hatch_quad: the opening's corners (near-left, near-right, far-right, far-left): clip the climbing
    #   body to above the near edge; step: top of the lamp's round plinth (z = 10 cm) in front of the tank;
    #   filler: the mouth of the funnel on the brass filler pipe; lamp: where to hold the spout to pour
    #   (a little above the funnel: the oil thread from points['spout'] into the funnel is drawn here); wick: the flame inside the glass;
    #   lens: where to wipe (lowest glass ring, within reach); hatch_lip: the near edge of the opening (left to
    #   right): below this line the body is inside the well and hidden.
    M = dict(ground=950, x0=660, x1=1110, scale=290,
             light=dict(dir=(.45, -.89), color='#ffb458', amt=.85),
             hatch=(660, 940), hatch_quad=((381, 1045), (862, 1002), (838, 876), (499, 898)),
             step=(1206, 845), lamp=(1208, 606), filler=(1211, 652), wick=(1259, 500), lens=(1160, 596), window=(653, 416),
             hatch_lip=((381, 1045), (862, 1002)))

    def setup(self):
        self.room = LR.Room('s2', 'night')
        r = np.random.default_rng(404)
        n = 70
        # motes hang in the warm air round the lamp, each with its own size and drift
        self.motes = np.c_[r.normal(1250, 330, n), r.normal(560, 230, n), r.choice([.6, .9, 1.3, 1.8, 3.2], n, p=[.34, .3, .2, .1, .06]),
                           r.normal(.05, .12, n), r.normal(-.06, .07, n), r.uniform(0, 6.28, n), r.uniform(.35, 1., n)]
        self.cam_c = (1180., 640.)

    # ------------------------------------------------------------------
    def zoom(self, f):
        t = f / (self.n - 1)
        return 1.0 + .032 * (.35 * t + .65 * comp.ease(t))

    def rot(self, f):
        return .55 + f * (2 * math.pi / (24 * 60))          # one turn a minute

    def frame(self, f):
        R = self.room
        fl = flicker(f)
        rot = self.rot(f)
        Lt = R.light(lamp=fl, rot=rot, amb=1.0, moon=.10, beams=.10)
        img = R.render(Lt)
        img = self.shadow(img, f, fl)
        R.lamp.draw(img, f, rot=rot, lit=.95 * fl, flame=1.0, glow=fl)
        img = self.air(img, f, fl)
        img = otteract.draw(img, 's2', f, self.M)
        img = self.oil(img, f)
        self.dust(img, f)
        z = self.zoom(f)
        cx, cy = self.cam_c
        return comp.cam2d(img, W / 2 + (cx - W / 2) * (1 - 1 / z), H / 2 + (cy - H / 2) * (1 - 1 / z), z).astype(f32)

    def shadow(self, img, f, fl):
        """the otter's contact shadow and its long soft shadow thrown away from the flame"""
        acts = otteract.actors('s2', f, self.M)
        if not acts: return img
        a = acts[0]
        x, y, s = a['x'], a['y'], a['s'] * 290
        q = np.array(self.M['hatch_quad'], np.float32)
        if cv2.pointPolygonTest(q, (float(x), float(y)), True) > -25 or y > 1000:
            return img                                                     # still on the ladder: no floor under it
        fx, fy = self.M['wick']
        dx, dy = x - fx, y - fy
        L = math.hypot(dx, dy) + 1e-6
        ang = math.degrees(math.atan2(dy * .35, dx))
        m = np.zeros((H, W), f32)
        ln = s * .9
        cx, cy = x + dx / L * ln * .5, y + dy / L * ln * .12
        cv2.ellipse(m, (int(cx), int(cy)), (int(ln * .55), int(s * .10)), ang, 0, 360, .55, -1, cv2.LINE_AA)
        m = cv2.GaussianBlur(m, (0, 0), 9)
        c = np.zeros((H, W), f32)
        cv2.ellipse(c, (int(x), int(y)), (int(s * .20), int(s * .045)), 0, 0, 360, 1.0, -1, cv2.LINE_AA)
        c = cv2.GaussianBlur(c, (0, 0), 4)
        k = np.clip(m * fl + .6 * c, 0, .85)[..., None]
        return img * (1 - k * (1 - rgb('#3a2a48')))

    def oil(self, img, f):
        """a thin amber thread from the can's spout into the funnel while it pours"""
        sp = None
        for a in otteract.actors('s2', f, self.M):
            sp = (a.get('points') or {}).get('spout', sp)
        if sp is None: return img
        from lp.ink import Cel, over_roi
        tx, ty = self.M['filler']
        sx, sy = sp
        if ty - sy < 6: return img
        x0, y0 = int(min(sx, tx) - 20), int(sy - 20)
        c = Cel(int(abs(tx - sx) + 40), int(ty - sy + 40), x0, y0)
        t = np.linspace(0, 1, 14)[:, None]
        p0, p1 = np.array([sx, sy]), np.array([tx, ty - 2])
        mid = p0 + (p1 - p0) * .5 + [3, -2]
        q = (1 - t) ** 2 * p0 + 2 * t * (1 - t) * mid + t * t * p1
        w = 2.4 + .4 * math.sin(f * 1.7)
        c.line(q, w, '#ffc45a', taper=(.05, .1), press=.3, seed=f // 2, tremor=.5, alpha=.95)
        c.line(q + [-.6, 0], w * .35, '#fff0b8', taper=(.1, .3), press=.2, seed=f // 2 + 1, tremor=.3, alpha=.9)
        over_roi(img, c.rgba(), x0, y0)
        return img

    def air(self, img, f, fl):
        """warm light hanging in the air round the glass"""
        cx, cy = self.M['wick']
        img = comp.glow(img, cx, cy - 20, 520, '#ff9e48', .16 * fl, 2.2)
        img = comp.glow(img, cx, cy - 20, 200, '#ffc878', .16 * fl, 1.8)
        return img

    def dust(self, img, f):
        d = f // 2
        cx, cy = self.M['wick']
        for (x, y, s, vx, vy, ph, a) in self.motes:
            X = x + vx * 2 * d + 6 * math.sin(ph + d * .05); Y = y + vy * 2 * d + 3 * math.sin(ph * 2 + d * .07)
            ix, iy = int(X), int(Y)
            if not (6 < ix < W - 6 and 6 < iy < H - 6): continue
            near = math.exp(-((X - cx) ** 2 + ((Y - cy) * 1.3) ** 2) / (2 * 380 ** 2))
            br = a * near * (.7 + .3 * math.sin(ph * 3 + d * .3))
            if br < .04: continue
            Rr = int(s * 2 + 3); yy, xx = np.mgrid[iy - Rr:iy + Rr + 1, ix - Rr:ix + Rr + 1].astype(f32)
            e = 1 + .3 * math.sin(ph)
            q = np.hypot((xx - X) * e, (yy - Y) / e)
            g = np.clip(s + .6 - q, 0, 1) if s < 3 else np.clip((s + 1.2 - q) / 2.2, 0, 1) * .35
            img[iy - Rr:iy + Rr + 1, ix - Rr:ix + Rr + 1] += g[..., None] * rgb('#ffd9a0') * min(.6, .55 * br)
        return img

    def actors(self, f):
        z = self.zoom(f)
        cx, cy = self.cam_c
        ox = W / 2 + (cx - W / 2) * (1 - 1 / z); oy = H / 2 + (cy - H / 2) * (1 - 1 / z)
        T = lambda x, y: ((x - ox) * z + W / 2, (y - oy) * z + H / 2)
        out = []
        for a in otteract.actors('s2', f, self.M):
            a = dict(a)
            a['x'], a['y'] = T(a['x'], a['y'])
            a['s'] = a['s'] * z
            if 'points' in a:
                a['points'] = {k: T(*v) for k, v in a['points'].items()}
            out.append(a)
        return out
