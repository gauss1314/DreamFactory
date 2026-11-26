"""Stand-in for s3_otter: replace with the real shot."""
import numpy as np, cv2
from lp import W, H
from lp.paint import rgb
import otteract


class Shot:
    n = 96
    finish = dict(hal_amt=.2, vig=.1)
    M = dict(ground=1400, x0=900, x1=1100, scale=1500, light=dict(dir=(1, 0), color='#ffb458', amt=.9), window=(300, 400))

    def setup(self):
        y = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
        a, b, c = (rgb(h) for h in ['#1c1a30', '#2c2a48', '#ffb458'])
        g = np.where(y < .6, a + (b - a) * (y / .6), b + (c - b) * ((y - .6) / .4))
        self.plate = np.broadcast_to(g, (H, W, 3)).astype(np.float32).copy()

    def frame(self, f):
        img = self.plate.copy()
        img = otteract.draw(img, 's3', f, self.M)
        return img

    def actors(self, f):
        return otteract.actors('s3', f, self.M)
