"""Model sheet for the otter: three views and the expressions, under neutral and lamp light.
  .venv/bin/python films/lighthouse-keeper/otter_sheet.py [name] [--crop x,y]"""
import sys, os, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', 'verticals', 'anime')); sys.path.insert(0, HERE)
import numpy as np, cv2
cv2.setNumThreads(2)
from lp import W, H, comp
from lp.paint import rgb
import otter as O

OUT = os.path.join(HERE, 'qa', 'otter')
os.makedirs(OUT, exist_ok=True)


def bg(top='#d9cdb8', bot='#bfae98'):
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    return np.broadcast_to(rgb(top) * (1 - y) + rgb(bot) * y, (H, W, 3)).astype(np.float32).copy()


def sheet_views(name='views'):
    img = bg()
    env = O.Env(dict(dir=(1, -.5), color='#fff1dc', amt=.5), amb='#6a5a7a')
    k = 3.3 * 1.5
    yaws = [0.0, .55, 1.0, 1.5708, 2.6]
    t0 = time.time()
    for i, yw in enumerate(yaws):
        V = O.View(220 + i * 400, 900, k, yaw=yw, tilt=.12)
        O.draw(img, V, O.pose(), env, seed=3)
    print('views', (time.time() - t0) / len(yaws))
    comp.save(os.path.join(OUT, name + '.jpg'), img)


def sheet_faces(name='faces'):
    img = bg('#cdbfb0', '#b4a493')
    env = O.Env(dict(dir=(1, -.4), color='#ffcf8a', amt=.7), amb='#4a3a5a')
    k = 7.0
    ex = [dict(), dict(blink=.5), dict(blink=1.0), dict(squint=.7, smile=1.0), dict(ears=1.0, look=(-1, 0)), dict(mouth=.8, ears=.6)]
    t0 = time.time()
    for i, e in enumerate(ex):
        V = O.View(330 + (i % 3) * 680, 300 + (i // 3) * 540 + 80.5 * k, k, yaw=.85, tilt=.1)
        P = O.pose(**e)
        O.draw(img, V, P, env, seed=5, parts=('head',))
    print('faces', (time.time() - t0) / len(ex))
    comp.save(os.path.join(OUT, name + '.jpg'), img)


def sheet_big(name='big', **kw):
    img = bg('#3a3550', '#2c2a48')
    env = O.Env(dict(dir=(1, -.3), color='#ffb458', amt=.8), amb='#2c2a48')
    t0 = time.time()
    for i, (yw, x) in enumerate(((.8, 560), (1.5708, 1450))):
        k = 15.0
        V = O.View(x, 330 + 80.5 * k, k, yaw=yw, tilt=.08)
        O.draw(img, V, O.pose(**kw), env, seed=5, parts=('head', 'scarf', 'torso', 'armL', 'armR'))
    print('big', (time.time() - t0) / 2)
    comp.save(os.path.join(OUT, name + '.jpg'), img)


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'all'
    if what in ('all', 'views'): sheet_views()
    if what in ('all', 'faces'): sheet_faces()
    if what in ('all', 'big'): sheet_big()
