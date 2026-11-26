"""Stand-in for s9_dawn: replace with the real shot."""
import numpy as np, cv2
from lp import W, H
from lp.paint import rgb
import otteract


class Shot:
    n = 312
    finish = dict(hal_amt=.2, vig=.1)
    M = dict(ground=820, x0=700, x1=900, scale=360, light=dict(dir=(1, -0.5), color='#ffe7b8', amt=.7), rail=(500, 820))

    def setup(self):
        y = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
        a, b, c = (rgb(h) for h in ['#8fb6d9', '#f7d9a8', '#ffe7b8'])
        g = np.where(y < .6, a + (b - a) * (y / .6), b + (c - b) * ((y - .6) / .4))
        self.plate = np.broadcast_to(g, (H, W, 3)).astype(np.float32).copy()

    def frame(self, f):
        img = self.plate.copy()
        img = otteract.draw(img, 's9', f, self.M)
        return img

    def actors(self, f):
        return otteract.actors('s9', f, self.M)
