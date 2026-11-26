"""s5 The light goes out (168 f).  Interior lane.

The storm rattles the windows.  The casement shivers twice (the anticipation), then at 1.5 s the latch
gives and it slams open; wind and rain pour in, the flame leans and fights, and at 3.5 s it dies.
Then only the cold blue of the storm, a thread of smoke, and a beat of complete stillness.
"""
import math
import numpy as np, cv2
from lp import W, H, comp
from lp.paint import rgb, f32, mix
import otteract
import lamproom as LR

cv2.setNumThreads(2)

STILL = (116, 142)          # the beat of complete stillness (frames)


class Shot:
    n = 168
    finish = dict(hal_amt=.20, vig=.16)
    # Marks (frame px).  ground: floor y between the window and the lamp; window: centre of the casement
    # that blows open (its sill top is at y 567, x 581); step: top of the lamp plinth; wick: the flame.
    # light: the storm light through the open window after 1.5 s (the lamp's warm light comes from `lamp_light`
    # until it dies at 3.5 s).
    M = dict(ground=900, x0=700, x1=1450, scale=290,
             light=dict(dir=(-.85, -.35), color='#8a9ac8', amt=.6),
             lamp_light=dict(dir=(.6, -.8), color='#ffb458', amt=.8),
             window=(563, 415), sill=(581, 567), step=(1499, 801), lamp=(1463, 607), wick=(1431, 492), lens=(1432, 526))

    def setup(self):
        ev = self.scene.get('events', {}) if hasattr(self, 'scene') else {}
        self.f_open = int(round(ev.get('window', 1.5) * 24))
        self.f_out = int(round(ev.get('out', 3.5) * 24))
        self.room = LR.Room('s5', 'storm')
        r = self.room
        self.win_mask = r.glass
        g = np.zeros((H, W), f32)
        # where rain driven in through the open casement is seen: a wedge from the window toward the lamp
        wx, wy = self.M['window']
        cv2.fillPoly(g, [np.array([[wx - 60, wy - 170], [wx + 120, wy - 160], [1500, 520], [1500, 1000], [wx + 60, 980], [wx - 80, 700]], np.int32)], 1.0, cv2.LINE_AA)
        self.inside = cv2.GaussianBlur(g, (0, 0), 60)[..., None]
        # the open casement's hole: the plate pane is glass anyway; nothing to cut

    # ---------------------------------------------------------------- timing
    def t_(self, f):
        """visual time: hold everything during the beat of stillness"""
        a, b = STILL
        if f < a: return f
        if f < b: return a
        return f - (b - a)

    def theta(self, f):
        """casement angle (radians, into the room)"""
        fo = self.f_open
        if f < fo:
            th = .004 * math.sin(f * 1.9) + .003 * math.sin(f * 3.1)
            for k0 in (fo - 14, fo - 7):                  # it shivers twice against the latch
                u = f - k0
                if 0 <= u < 5: th += .045 * math.sin(u / 5 * math.pi) * (1 if k0 == fo - 7 else .7)
            return th
        u = f - fo
        # slams open past the stop, bounces, and is then worried by the wind
        if u < 4: return [.35, .95, 1.55, 1.95][u]
        tt = u - 4
        base = 1.62 + .30 * math.exp(-tt / 5.) * math.cos(tt * .9)
        return base + .06 * math.sin(f * .35) + .03 * math.sin(f * .83)

    def flash(self, f):
        """storm light through the glass: a soft distant flicker early, a crack of lightning at the latch"""
        fo = self.f_open
        v = .25 * max(0, 1 - abs(f - 12) / 6.) ** 2
        if f >= fo:
            u = f - fo
            v += 1.6 * math.exp(-u / 2.0) + .45 * math.exp(-u / 12.)
            if 2 <= u < 6: v += .35 * math.sin((u - 2) / 4 * math.pi)
        return v

    def flame(self, f):
        """(size, lean) of the flame"""
        fo, fx = self.f_open, self.f_out
        r = lambda k: np.random.default_rng(700 + k).normal(0, 1)
        if f < fo:
            return 1.0 + .04 * r(f // 3), .05 * math.sin(f * .4)
        if f >= fx: return 0.0, 0.0
        u = (f - fo) / float(fx - fo)
        d = f // 2
        lean = .9 + .35 * math.sin(d * 1.3) + .2 * r(d)
        size = (1 - .55 * u) * (1 + .25 * math.sin(d * 1.7) + .12 * r(d + 50))
        # it nearly goes twice and comes back
        for c in (.45, .78):
            size *= 1 - .5 * math.exp(-((u - c) / .09) ** 2)
        return max(.12, size), lean

    def lamp_amt(self, f):
        s, _ = self.flame(f)
        return 0.0 if f >= self.f_out else .25 + .75 * s

    # ---------------------------------------------------------------- frame
    def frame(self, f):
        R = self.room
        t = self.t_(f)
        fo, fx = self.f_open, self.f_out
        size, lean = self.flame(t)
        lamp = self.lamp_amt(t)
        fl = self.flash(t)
        dark = 1.0 if t >= fx else 0.0
        amb_col = mix(rgb('#22223c'), rgb('#141a2a'), dark)
        win = .35 + (.55 if t >= fo else 0) + .25 * dark
        Lt = R.light(lamp=lamp * .78, rot=.55, amb_col=amb_col, amb=1.0 - .15 * dark, win=win, win_col='#5a6a8a', flash=fl * .55)
        sky = R.sky * (1 + .9 * fl) + rgb('#c8d4f0') * fl * .18
        sky = sky + (np.roll(R.sky, int(t * 2), axis=1) - R.sky) * .0     # clouds held: they move with the rain
        img = R.render(Lt, sky)
        img = LR.rain(img, t, self.win_mask * (1 - .3 * dark), n=320, ang=1.30, speed=70, length=40, col='#a8b6c4', amt=.30, seed=5)
        # the casement
        th = self.theta(t)
        lit = rgb('#3a3c5a') * (1.0 + 1.4 * fl) + rgb('#ffb458') * lamp * .35
        img = LR.draw_sash(img, R.cam, th, t, lit, seed=8)
        if t >= fo:
            k = min(1.0, (t - fo) / 6.)
            img = LR.rain(img, t, self.inside * k, n=170, ang=.32, speed=55, length=46, col='#b8c4d4', amt=.32 * (1 + fl), seed=9,
                          region=(450, 300, 1400, 980), w=1)
        if size > 0 and t < fx:
            R.lamp.draw(img, t, rot=.55, lit=.9 * lamp, flame=size, lean=lean, glow=lamp)
            cx, cy = self.M['wick']
            img = comp.glow(img, cx, cy - 20, 480, '#ff9e48', .14 * lamp, 2.2)
        else:
            R.lamp.draw(img, t, rot=.55, lit=0.0, flame=0)
            cx, cy = self.M['wick']
            img = LR.smoke(img, cx, cy + 6, t - fx, 1.0, seed=3)
            # the last ember on the wick
            e = math.exp(-(t - fx) / 10.)
            if e > .02: img = comp.glow(img, cx, cy + 8, 14, '#ff7a30', .9 * e, 1.5)
        img = otteract.draw(img, 's5', f, self.M)
        # cold light in the air by the window after it opens
        wx, wy = self.M['window']
        img = comp.glow(img, wx + 40, wy, 700, '#5a6a8a', (.10 + .25 * fl) * (t >= fo), 1.8)
        return img.astype(f32)

    def actors(self, f):
        return otteract.actors('s5', f, self.M) + [dict(name='窗扇', prop=True, x=float(self.M['sill'][0]), y=float(self.M['sill'][1]), s=1.0)]
