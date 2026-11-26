"""Stand-in for s6_boat: replace with the real shot."""
import numpy as np, cv2
from lp import W, H
from lp.paint import rgb



class Shot:
    n = 144
    finish = dict(hal_amt=.2, vig=.1)


    def setup(self):
        y = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
        a, b, c = (rgb(h) for h in ['#2a2e3e', '#1c2a33', '#2f4452'])
        g = np.where(y < .6, a + (b - a) * (y / .6), b + (c - b) * ((y - .6) / .4))
        self.plate = np.broadcast_to(g, (H, W, 3)).astype(np.float32).copy()

    def frame(self, f):
        img = self.plate.copy()

        return img

