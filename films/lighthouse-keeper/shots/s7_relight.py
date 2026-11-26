"""s7 Relit (216 f).  Interior lane (the set and the light); the otter lane acts.

The dark lamp room, the casement banging in the storm.  1.5 s the otter shoulders it shut and latches it;
climbs the lamp; 4.0 s strikes a match (a small warm world moves with it); 5.5 s the wick takes;
7.0 s the lens catches the light: rings of light open out through the room, the lens begins to turn,
and the whole room goes from cold to warm.
"""
import math
import numpy as np, cv2
from lp import W, H, comp
from lp.paint import rgb, f32, mix
import otteract
import lamproom as LR

cv2.setNumThreads(2)


def _e(t, k):
    return 1 - math.exp(-max(0., t) / k)


class Shot:
    n = 216
    finish = dict(hal_amt=.24, vig=.15)
    # Same camera as s5.  window: centre of the casement the otter shuts (sill top y 567 at x 581);
    # step: top of the lamp plinth; lamp: the oil filler cap; wick: where the match must go.
    # Report the match head as points['match'] in otteract.actors('s7', f, M): its light is drawn here.
    # run_y: floor y of the way round behind the hatch (over the lid lying open there).
    # lamp is the wick here (nothing is poured in s7): where the match goes.
    M = dict(ground=900, x0=600, x1=1450, scale=290, run_y=850,
             light=dict(dir=(-.85, -.35), color='#8a9ac8', amt=.55),
             lamp_light=dict(dir=(.6, -.8), color='#ffb458', amt=.9),
             window=(563, 415), sill=(581, 567), step=(1499, 801), lamp=(1431, 492), filler=(1463, 607), wick=(1431, 492), lens=(1432, 526))

    def setup(self):
        ev = self.scene.get('events', {}) if hasattr(self, 'scene') else {}
        g = lambda k, d: int(round(ev.get(k, d) * 24))
        self.f_shut, self.f_match, self.f_catch, self.f_bloom = g('shut', 1.5), g('match', 4.0), g('catch', 5.5), g('bloom', 7.0)
        self.room = LR.Room('s7', 'storm')
        gm = np.zeros((H, W), f32)
        wx, wy = self.M['window']
        cv2.fillPoly(gm, [np.array([[wx - 60, wy - 170], [wx + 120, wy - 160], [1500, 520], [1500, 1000], [wx + 60, 980], [wx - 80, 700]], np.int32)], 1.0, cv2.LINE_AA)
        self.inside = cv2.GaussianBlur(gm, (0, 0), 60)[..., None]
        # depth of the lamp from the camera, to put a screen point back into the room
        c = self.room.cam
        self.zl = float(c.cam(LR.FLAME)[2])
        x, y = np.meshgrid(np.arange(W, dtype=f32), np.arange(H, dtype=f32))
        cx, cy = self.M['wick']
        self.ang = np.arctan2((y - cy) * 2.2, x - cx).astype(f32)
        self.rad = np.hypot(x - cx, (y - cy) * 2.2).astype(f32)
        g = np.clip(1 - np.hypot((x - cx) / 1500., (y - cy) / 900.), 0, 1) ** 1.3
        self.warmwash = (g[..., None] * LR.rgb('#ffb458')).astype(f32)
        r = np.random.default_rng(71)
        self.ray_tab = np.convolve(r.uniform(0, 1, 720) ** 3, np.hanning(7) / 3, 'same').astype(f32)

    # ---------------------------------------------------------------- timing
    def theta(self, f):
        fs = self.f_shut
        if f >= fs: return 0.0
        bang = 1.55 + .22 * math.sin(f * .55) + .08 * math.sin(f * 1.3)
        a = fs - 16
        if f < a: return bang
        u = (f - a) / 16.
        k = u ** 2.2                                      # slow against the wind, then home
        return bang * (1 - k)

    def match(self, f):
        """screen position of the match head and its brightness"""
        if f < self.f_match: return None
        pts = None
        for a in otteract.actors('s7', f, self.M):
            pts = (a.get('points') or {}).get('match', pts)
        if pts is None:
            wx, wy = self.M['wick']
            pts = (wx - 70 + 50 * _e(f - self.f_match, 20), wy + 40 - 30 * _e(f - self.f_match, 20))
        u = f - self.f_match
        b = 1.6 * math.exp(-u / 2.5) + .85 + .08 * math.sin(f * 1.7)
        if f >= self.f_catch: b *= math.exp(-(f - self.f_catch) / 6.)
        return pts, b

    def flame(self, f):
        if f < self.f_catch: return 0.0
        u = f - self.f_catch
        r = np.random.default_rng(1700 + f // 2).normal(0, 1)
        s = .18 + .82 * _e(u - 4, 9) + .08 * r * (1 - _e(u, 30))
        if f >= self.f_bloom: s = 1.0 + .04 * r
        return max(.1, s)

    def rot(self, f):
        if f < self.f_bloom: return .55
        u = (f - self.f_bloom) / 24.
        w = 2 * math.pi / 60.                                   # final speed: a turn a minute, as in s2
        return .55 + w * (u - 1.2 * (1 - math.exp(-u / 1.2)))  # spins up from rest

    # ---------------------------------------------------------------- frame
    def frame(self, f):
        R = self.room
        fb = self.f_bloom
        size = self.flame(f)
        ub = f - fb
        warm = _e(ub, 14) if f >= fb else 0.0                    # the room turning from cold to warm
        burst = math.exp(-ub / 7.) if f >= fb else 0.0
        lamp = (.38 * size if f < fb else 1.0 + .45 * burst) * (1 + .02 * math.sin(f * .9))
        amb_col = mix(rgb('#141a2a'), rgb('#2c2a48'), warm)
        beams = (.9 * burst + .35 * warm) if f >= fb else 0.0
        width = (.5 + 1.5 * _e(ub, 6)) if f >= fb else 1.0
        rot = self.rot(f)
        Lt = R.light(lamp=lamp, rot=rot, amb_col=amb_col, amb=1.0, win=.55 * (1 - .6 * warm) + .25 * (f < self.f_shut),
                     win_col='#5a6a8a', beams=beams, beam_w=width)
        m = self.match(f)
        if m is not None:
            Lt = Lt + self.match_light(m[0], m[1])
        sky = R.sky * (1 - .25 * warm)
        img = R.render(Lt, sky)
        img = LR.rain(img, f, R.glass, n=320, ang=1.30, speed=70, length=40, col='#a8b6c4', amt=.26, seed=5)
        lit_s = rgb('#3a3c5a') * (1 + .4 * warm) + rgb('#ffb458') * lamp * .35 * (f >= self.f_catch)
        img = LR.draw_sash(img, R.cam, self.theta(f), f, lit_s, seed=8)
        if f < self.f_shut:
            img = LR.rain(img, f, self.inside, n=150, ang=.32, speed=55, length=46, col='#b8c4d4', amt=.30, seed=9, region=(450, 300, 1400, 980))
        glass = (.30 * size if f < fb else 1.0 + 1.2 * burst)
        R.lamp.draw(img, f, rot=rot, lit=glass, flame=size, glow=min(1.4, .6 + glass), bloom=burst)
        if f >= self.f_catch:
            cx, cy = self.M['wick']
            img = comp.glow(img, cx, cy - 20, 300 + 300 * warm, '#ff9e48', .10 + .12 * warm + .25 * burst, 2.2)
        if f >= fb:
            img = self.rays(img, ub, rot, burst, warm)
            img = self.rings(img, ub)
            img = comp.screen(img, self.warmwash * (.30 * burst))
        img = otteract.draw(img, 's7', f, self.M)
        if m is not None:
            (mx, my), b = m
            img = comp.glow(img, mx, my, 160, '#ffb060', .35 * b, 2.0)
            img = comp.glow(img, mx, my, 34, '#fff0c0', .7 * min(1.5, b), 1.6)
        return img.astype(f32)

    def match_light(self, p, b):
        """a small warm world around the match: short falloff, faces turned toward it lit"""
        R = self.room
        c = R.cam
        rd = np.array([(p[0] - c.cx) / c.f, (p[1] - c.cy) / c.f, 1.]) @ c.R
        P3 = c.eye + rd * (self.zl * .92)
        x0, x1 = int(max(0, p[0] - 700)), int(min(W, p[0] + 700))
        y0, y1 = int(max(0, p[1] - 600)), int(min(H, p[1] + 600))
        out = np.zeros((H, W, 3), f32)
        Pp = R.P[y0:y1, x0:x1].astype(f32); Nn = R.N[y0:y1, x0:x1].astype(f32)
        v = P3.astype(f32) - Pp
        d = np.sqrt((v * v).sum(-1)) + 1e-6
        ndl = np.clip((v * Nn).sum(-1) / d, 0, 1)
        E = (.2 + .8 * ndl) / (1 + (d / .32) ** 2)
        E = LR.stepped(E, 0 * E, 1.6)
        out[y0:y1, x0:x1] = E[..., None] * rgb('#ffb060') * (2.2 * b)
        return out

    def rays(self, img, u, rot, burst, warm):
        """shafts of light thrown through the room's air by the turning panels"""
        q = 4
        a = self.ang[::q, ::q]; rr = self.rad[::q, ::q]
        k = ((a + rot * 1.0) / (2 * np.pi) * 720).astype(np.int32) % 720
        st = self.ray_tab[k]
        reach = 250 + 1300 * (1 - math.exp(-u / 8.))
        fall = np.clip(1 - rr / reach, 0, 1) ** 1.5 * np.clip((rr - 60) / 120, 0, 1)
        L = cv2.GaussianBlur(st * fall, (0, 0), 1.5)
        L = cv2.resize(L, (W, H), interpolation=cv2.INTER_LINEAR)
        return comp.screen(img, L[..., None] * LR.rgb('#ffcf8a') * (.55 * burst + .16 * warm))

    def rings(self, img, u):
        """rings of light opening out from the lens, through the room's air"""
        cx, cy = self.M['wick']
        q = 4
        h, w = H // q, W // q
        L = np.zeros((h, w), f32)
        for k, (delay, amp) in enumerate(((0, 1.0), (3, .8), (7, .65), (12, .5), (18, .38))):
            t = u - delay
            if t < 0: continue
            r = 40 + 1500 * _e(t, 16)
            a = amp * math.exp(-t / 22.) * min(1, t / 2.)
            if a < .01: continue
            cv2.ellipse(L, (int(cx / q * 16), int(cy / q * 16)), (int(r / q * 16), int(r * .42 / q * 16)), 0, 0, 360, a, max(1, int((10 + t * 1.4) / q)), cv2.LINE_AA, 4)
        L = cv2.GaussianBlur(L, (0, 0), 4.0)
        L = cv2.resize(L, (W, H), interpolation=cv2.INTER_LINEAR)
        return comp.screen(img, L[..., None] * rgb('#ffcf8a') * .85)

    def actors(self, f):
        return otteract.actors('s7', f, self.M) + [dict(name='窗扇', prop=True, x=float(self.M['sill'][0]), y=float(self.M['sill'][1]), s=1.0)]
