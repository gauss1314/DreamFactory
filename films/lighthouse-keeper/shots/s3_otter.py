"""s3 The otter (96 f).  Interior lane: the background and the light; the otter lane draws the otter.

Close-up at the otter's eye level.  Behind it the lamp room is thrown out of focus: the whitewash and
the ledge warm from the lamp just off the right of frame, a window on the left with the night in it.
2.8 s: far off, lightning; cold light comes in from the window side and the whole picture lifts and falls.
"""
import math, os
import numpy as np, cv2
from lp import W, H, comp, cache_path
from lp.paint import rgb, f32, fbm, mottle
import otteract
import lamproom as LR

cv2.setNumThreads(2)
VER = 'b6'


class Shot:
    n = 96
    finish = dict(hal_amt=.24, vig=.15)
    # Close-up marks.  ground is below the frame so the head sits in the upper middle; light: the lamp,
    # off the right of frame; flash: the lightning (frame `f`, from the window on the left).
    M = dict(ground=1720, x0=980, x1=980, scale=1500,
             light=dict(dir=(1, -.25), color='#ffb458', amt=.85),
             flash=dict(f=67, dir=(-1, -.3), color='#c8d4f0', amt=1.0),
             window=(430, 330), lamp=(2300, 520))

    def setup(self):
        ev = self.scene.get('events', {}) if hasattr(self, 'scene') else {}
        self.f_flash = int(round(ev.get('flash', 2.8) * 24))
        p = cache_path(f'lamproom_s3_bokeh_{VER}_{LR.layout_tag("s3")}.npz')
        if os.path.exists(p):
            z = np.load(p); self.base = z['base'].astype(f32); self.fl = z['fl'].astype(f32)
        else:
            R = LR.Room('s3', 'night')
            base = R.render(R.light(lamp=1.0, rot=.4, moon=.12, beams=.35))
            dark = R.render(R.light(lamp=0.0, amb=0.0))
            fl = R.render(R.light(lamp=0.0, amb=0.0, flash=1.0), R.sky * 1.3 + rgb('#c8d4f0') * .22) - dark
            self.base = self.defocus(base); self.fl = self.defocus(np.maximum(fl, 0))
            np.savez(p, base=self.base.astype(np.float16), fl=self.fl.astype(np.float16))
        r = np.random.default_rng(33)
        # glints out of focus: the lens and brass just off frame right, a few on the ledge
        self.discs = [(r.uniform(1560, 2150), r.uniform(380, 860), r.uniform(36, 95), r.uniform(.25, .6)) for _ in range(7)]
        self.discs += [(r.uniform(700, 1500), r.uniform(560, 700), r.uniform(18, 40), r.uniform(.1, .3)) for _ in range(6)]
        x, y = np.meshgrid(np.arange(W, dtype=f32), np.arange(H, dtype=f32))
        g = np.clip(1 - np.hypot((x - 2250) / 1500., (y - 760) / 900.), 0, 1) ** 1.6
        self.warm = (g[..., None] * rgb('#ffb458')).astype(f32)
        sh = np.clip(1 - np.hypot((x - 300) / 1700., (y - 300) / 1300.), 0, 1)
        self.grade = (.62 + .25 * (1 - sh))[..., None].astype(f32) * np.array([.95, .93, 1.0], f32)

    @staticmethod
    def defocus(img):
        q = 2
        sm = cv2.resize(np.clip(img, 0, 3), (W // q, H // q), interpolation=cv2.INTER_AREA)
        lay = np.dstack([sm, np.ones(sm.shape[:2], f32)])
        b = comp.bokeh(lay, 13.0, .8)[..., :3]
        b = cv2.GaussianBlur(b, (0, 0), 1.5)
        b = cv2.resize(b, (W, H), interpolation=cv2.INTER_CUBIC)
        return mottle(np.clip(b, 0, 1), .010, 6, .004).astype(f32)

    def flash(self, f):
        u = f - self.f_flash
        if u < 0: return 0.0
        v = 1.25 * math.exp(-u / 2.2) + .18 * math.exp(-u / 14.)
        if 2 <= u < 6: v += .40 * math.sin((u - 2) / 4 * math.pi)        # the flicker that follows
        return v

    def frame(self, f):
        z = 1.0 + .02 * f / 95.
        fl = 1 + .03 * math.sin(f / 3 * 1.1) * math.sin(f / 3 * .37 + 1)
        img = comp.cam2d(self.base, W / 2 + 6, H / 2 + 4, z * 1.01) * self.grade
        img = comp.screen(img, self.warm * (.55 * fl))
        k = self.flash(f)
        if k > 0:
            img = img + comp.cam2d(self.fl, W / 2 + 6, H / 2 + 4, z * 1.01) * k
            img = self.bolt(img, f - self.f_flash, k)
        img = self.glints(img, f, fl, k)
        img = otteract.draw(img, 's3', f, self.M)
        return img.astype(f32)

    def glints(self, img, f, fl, k):
        q = 4
        L = np.zeros((H // q, W // q), f32)
        for (x, y, r, a) in self.discs:
            cv2.circle(L, (int(x / q * 16), int(y / q * 16)), int(r / q * 16), a, -1, cv2.LINE_AA, 4)
        L = cv2.GaussianBlur(L, (0, 0), 1.0)
        L = cv2.resize(L, (W, H), interpolation=cv2.INTER_LINEAR)
        return img + np.minimum(L, .8)[..., None] * rgb('#ff9a40') * (.30 * fl) * (1 - .3 * min(1, k))

    def bolt(self, img, u, k):
        """far lightning in the window, out of focus"""
        if u > 6: return img
        r = np.random.default_rng(67)
        x, y = self.M['window'][0] + 60, 120
        pts = [(x, y)]
        while y < 520:
            y += r.uniform(30, 60); x += r.normal(-8, 22); pts.append((x, y))
        L = np.zeros((H, W), f32)
        cv2.polylines(L, [np.array(pts, np.int32)], False, 1.0, 5, cv2.LINE_AA)
        L = cv2.GaussianBlur(L, (0, 0), 24) * 6
        return comp.screen(img, L[..., None] * rgb('#e8f0ff') * min(1, k) * .8 * max(0., 1 - u / 6.))

    def actors(self, f):
        return otteract.actors('s3', f, self.M)
