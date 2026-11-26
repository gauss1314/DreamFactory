"""Driver for anime films: picture, sound, stills and single-shot renders.

A film directory holds film.json (the shot list, as in every DreamFactory film), shots/<type>.py
(one module per shot type, each with a `Shot` class), the film's own modules (characters, props)
and sound.py (the score and effects).

  python film.py picture <film> --out <dir> [--draft] [--no-video] [--jobs 4]
  python film.py sound   <film> --out <dir>
  python film.py still   <film> <scene id> <frame> [<frame> ...] [--crop x,y[,w,h]] [--sheet] [--raw]
  python film.py render  <film> <scene id> [--draft] [--jobs 4]

Shot interface (shots/<type>.py):

  class Shot:
      n = 168                       # frames; must equal the scene's duration x 24
      finish = dict(hal_amt=.2)     # kwargs for lp.comp.finish, applied by the driver
      scene = {...}                 # set by the driver before setup(): id, duration, events, ...
      cues = [('step1', 0.5, 'step', {})]   # optional: (name, local seconds, kind, extra) for sound
      def setup(self): ...          # paint plates once; cache with lp.cache_path()
      def frame(self, f): ...       # -> float32 (H, W, 3) display RGB; a pure function of f
      def actors(self, f): ...      # optional: [{name, x, y, s, facing, points, air, ballistic, from, prop}]
"""
import argparse
import importlib
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.dirname(HERE)
sys.path.insert(0, ENGINE)
os.environ.setdefault('NUMBA_NUM_THREADS', '1')

import numpy as np  # noqa: E402
import cv2  # noqa: E402
from multiprocessing import get_context  # noqa: E402
from lp import W, H, FPS  # noqa: E402

SR = 48000


def load_film(film_dir):
    film_dir = os.path.abspath(film_dir)
    if film_dir not in sys.path:
        sys.path.insert(0, film_dir)
    with open(os.path.join(film_dir, 'film.json'), encoding='utf8') as fh:
        film = json.load(fh)
    t = 0.0
    spans = []
    for sc in film['scenes']:
        n = int(round(sc['duration'] * FPS))
        spans.append(dict(scene=sc, start=t, n=n, f0=int(round(t * FPS))))
        t += sc['duration']
    return film_dir, film, spans, t


def make_shot(span):
    sc = span['scene']
    S = importlib.import_module('shots.' + sc['type']).Shot()
    S.scene = sc
    if getattr(S, 'n', span['n']) != span['n']:
        raise SystemExit(f"shot {sc['id']}: module {sc['type']} has n={S.n}, but film.json says {sc['duration']} s = {span['n']} frames")
    S.n = span['n']
    return S


def fade_of(S, f):
    """Fades belong to the cut list (film.json), not to the shot: 0 is black, 1 is the picture."""
    sc = getattr(S, 'scene', {}) or {}
    t, dur = f / FPS, S.n / FPS
    k = 1.0
    if sc.get('fadeIn'):
        k = min(k, max(0.0, t / sc['fadeIn']))
    if sc.get('fadeOut'):
        k = min(k, max(0.0, (dur - t) / sc['fadeOut']))
    return k * k * (3 - 2 * k)


def finished(S, f):
    from lp import comp
    im = np.clip(comp.finish(S.frame(f), f, **getattr(S, 'finish', {})), 0, 1) * fade_of(S, f)
    return comp.to8(im, f)


# ---------------------------------------------------------------- parallel frame workers
_S = None


def _init(film_dir, idx):
    global _S
    cv2.setNumThreads(1)
    _, _, spans, _ = load_film(film_dir)
    _S = make_shot(spans[idx])
    _S.setup()


def _one(args):
    f, scale = args
    im = finished(_S, f)
    if scale != 1:
        im = cv2.resize(im, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    return im


def render_frames(film_dir, spans, idx, frames, scale, jobs):
    """Yield finished uint8 frames of one shot, in order, rendered in parallel."""
    if jobs <= 1:
        _init(film_dir, idx)
        for f in frames:
            yield _one((f, scale))
        return
    # spawn, not fork: by now this process has OpenCV and numba threads running, and a child forked
    # from a threaded parent can deadlock on a lock some thread held at the fork
    with get_context('spawn').Pool(jobs, _init, (film_dir, idx)) as pool:
        yield from pool.imap(_one, [(f, scale) for f in frames], chunksize=2)


def ffmpeg_writer(out, w, h, fps, crf='12'):
    return subprocess.Popen(['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{w}x{h}', '-r', str(fps), '-i', '-',
                             '-c:v', 'libx264', '-preset', 'medium', '-crf', crf, '-pix_fmt', 'yuv420p', out], stdin=subprocess.PIPE)


# ---------------------------------------------------------------- picture
def cmd_picture(a):
    film_dir, film, spans, dur = load_film(a.film)
    out = os.path.abspath(a.out)
    os.makedirs(os.path.join(out, 'build'), exist_ok=True)
    t0 = time.time()
    track, events, repeat, sheet = [], [], [], []
    every = max(2, int(np.ceil(dur / 24)))
    for k, sp in enumerate(spans):
        S = make_shot(sp)
        S.setup()
        sc = sp['scene']
        for c in getattr(S, 'cues', []):
            name, at, kind = c[0], c[1], c[2]
            extra = c[3] if len(c) > 3 else {}
            events.append(dict(name=f"{sc['id']}.{name}", t=sp['start'] + at, kind=kind, **extra))
        if hasattr(S, 'actors'):
            for f in range(0, sp['n'], 2):
                track.append(dict(t=sp['start'] + f / FPS, actors=json.loads(json.dumps(S.actors(f)))))
        # every two seconds a still for the contact sheet
        for sec in range(int(np.ceil(sp['start'])), int(np.ceil(sp['start'] + sp['n'] / FPS))):
            if sec % every == 0:
                f = int(round((sec - sp['start']) * FPS))
                if 0 <= f < sp['n']:
                    sheet.append(cv2.resize(finished(S, f), (480, 270), interpolation=cv2.INTER_AREA))
        # a frame is a pure function of its number: draw one, others in between, then it again
        if k in (0, len(spans) // 2, len(spans) - 1):
            f = sp['n'] // 2
            a1 = finished(S, f)
            S.frame(max(0, f - 17))
            S.frame(min(sp['n'] - 1, f + 23))
            a2 = finished(S, f)
            changed = int((np.abs(a1.astype(int) - a2.astype(int)).max(axis=2) > 24).sum())
            repeat.append(dict(t=sp['start'] + f / FPS, changed=changed / (a1.shape[0] * a1.shape[1])))
        print(f"probe {sc['id']} {time.time() - t0:.0f}s", file=sys.stderr, flush=True)
    if sheet:
        cols = 4
        rows = [np.hstack((sheet[i:i + cols] + [np.full_like(sheet[0], 32)] * cols)[:cols]) for i in range(0, len(sheet), cols)]
        cv2.imwrite(os.path.join(out, 'contact.jpg'), cv2.cvtColor(np.vstack(rows), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
    scale, fps = (0.5, FPS // 2) if a.draft else (1.0, FPS)
    info = dict(track=track, events=events, repeat=repeat, sheetFrames=len(sheet), pageErrors=[], samples=[],
                fps=fps, width=int(W * scale), height=int(H * scale))
    with open(os.path.join(out, 'build', 'picture.json'), 'w') as fh:
        json.dump(info, fh)
    if a.no_video:
        return
    video = os.path.join(out, 'video.mp4')
    p = ffmpeg_writer(video, info['width'], info['height'], fps, '18' if a.draft else '12')
    step = 2 if a.draft else 1
    for k, sp in enumerate(spans):
        t = time.time()
        # draft: every other drawing, which keeps animation on twos intact
        frames = list(range(0, sp['n'], step))
        for im in render_frames(film_dir, spans, k, frames, scale, a.jobs):
            p.stdin.write(np.ascontiguousarray(im).tobytes())
        print(f"render {sp['scene']['id']} {len(frames)} frames {time.time() - t:.0f}s", file=sys.stderr, flush=True)
    p.stdin.close()
    if p.wait() != 0:
        raise SystemExit('ffmpeg failed')


# ---------------------------------------------------------------- sound
def write_wav16(path, x):
    import soundfile as sf
    sf.write(path, np.clip(x, -1, 1).T if x.ndim == 2 else np.clip(x, -1, 1), SR, subtype='PCM_16')


def cmd_sound(a):
    film_dir, film, spans, dur = load_film(a.film)
    os.environ['DF_AUDIO_DUR'] = str(dur)
    sys.path.insert(0, os.path.join(ENGINE, 'audio'))
    out = os.path.abspath(a.out)
    os.makedirs(os.path.join(out, 'audio'), exist_ok=True)
    ev_file = os.path.join(out, 'build', 'events.json')
    if os.path.exists(ev_file):
        with open(ev_file) as fh:
            events = json.load(fh)
    else:
        # run on its own: the events declared in film.json, plus the cues the shots report
        events = []
        for sp in spans:
            for name, at in (sp['scene'].get('events') or {}).items():
                many = isinstance(at, list)
                for k, t in enumerate(at if many else [at]):
                    # the same names the pipeline uses: s9.horn.1, s9.horn.2 for a list of moments
                    events.append(dict(name=f"{sp['scene']['id']}.{name}" + (f'.{k + 1}' if many else ''), t=sp['start'] + t, kind='declared'))
            S = make_shot(sp)
            for c in getattr(S, 'cues', []):
                events.append(dict(name=f"{sp['scene']['id']}.{c[0]}", t=sp['start'] + c[1], kind=c[2], **(c[3] if len(c) > 3 else {})))
        events.sort(key=lambda e: e['t'])
    os.makedirs(os.path.join(out, 'build'), exist_ok=True)
    sound = importlib.import_module('sound')
    shots = [dict(id=sp['scene']['id'], start=sp['start'], end=sp['start'] + sp['n'] / FPS, scene=sp['scene']) for sp in spans]
    r = sound.build(dict(film=film, duration=dur, shots=shots, events={e['name']: e['t'] for e in events}, eventList=events))
    n = int(round(dur * SR))

    def fit(x):
        x = np.asarray(x, np.float64)
        if x.ndim == 1:
            x = np.stack([x, x])
        y = np.zeros((2, n))
        m = min(n, x.shape[1])
        y[:, :m] = x[:, :m]
        return y

    music, fx = fit(r['music']), fit(r['sfx'])
    # mono stems for the checks; their level relative to each other is kept
    write_wav16(os.path.join(out, 'audio', 'music.wav'), music.mean(0))
    write_wav16(os.path.join(out, 'audio', 'sfx.wav'), fx.mean(0))
    # the stereo master for the finished film, at -14 LUFS under a -1.5 dBTP ceiling
    import core
    raw = music + fx
    gain_db = -14 - core.loudness(raw)[0]
    for _ in range(4):
        # the limiter trims a little loudness on loud films, so aim again until it lands
        mix = raw * 10 ** (gain_db / 20)
        mix = mix * core.limiter_gain(mix, ceil_db=-2.0)
        off = -14 - core.loudness(mix)[0]
        if abs(off) < 0.3:
            break
        gain_db += off
    write_wav16(os.path.join(out, 'audio', 'master.wav'), mix)
    with open(os.path.join(out, 'build', 'cues.json'), 'w') as fh:
        json.dump(r.get('cues', []), fh)
    print(f'sound {dur:.1f}s master {core.loudness(mix)[0]:.1f} LUFS', file=sys.stderr)


# ---------------------------------------------------------------- stills and single shots
def find_span(spans, sid):
    for k, sp in enumerate(spans):
        if sp['scene']['id'] == sid:
            return k, sp
    raise SystemExit(f'no scene {sid}; scenes are {[sp["scene"]["id"] for sp in spans]}')


def cmd_still(a):
    film_dir, film, spans, dur = load_film(a.film)
    k, sp = find_span(spans, a.scene)
    S = make_shot(sp)
    t = time.time()
    S.setup()
    print(f'setup {time.time() - t:.1f}s')
    d = a.out or os.path.join(film_dir, 'qa', a.scene)
    os.makedirs(d, exist_ok=True)
    tiles = []
    from lp import comp
    for f in a.frames:
        t = time.time()
        im = S.frame(f)
        dt = time.time() - t
        im8 = comp.to8(np.clip(im if a.raw else comp.finish(im, f, **getattr(S, 'finish', {})), 0, 1), f)
        print(f'{f} {dt:.2f}s')
        if a.sheet:
            tiles.append(cv2.resize(im8, (640, 360), interpolation=cv2.INTER_AREA))
        else:
            cv2.imwrite(f'{d}/f{f:04d}.jpg', cv2.cvtColor(im8, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 90])
        for j, c in enumerate(a.crop):
            v = [int(q) for q in c.split(',')]
            w, h = (v[2], v[3]) if len(v) > 2 else (600, 450)
            cv2.imwrite(f'{d}/f{f:04d}_c{j}.jpg', cv2.cvtColor(im8[v[1]:v[1] + h, v[0]:v[0] + w], cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 92])
    if tiles:
        cols = 3
        rows = [np.hstack((tiles[i:i + cols] + [np.zeros_like(tiles[0])] * cols)[:cols]) for i in range(0, len(tiles), cols)]
        cv2.imwrite(f'{d}/sheet.jpg', cv2.cvtColor(np.vstack(rows), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 88])
        print(f'{d}/sheet.jpg')


def cmd_frames(a):
    """Finished frames at film times, plus 1:1 close-ups around each character, for review."""
    film_dir, film, spans, dur = load_film(a.film)
    os.makedirs(a.out, exist_ok=True)
    want = sorted(float(t) for t in a.at.split(','))
    index = []
    shot = None
    for n, t in enumerate(want, 1):
        k = max(i for i, sp in enumerate(spans) if sp['start'] <= t + 1e-6)
        sp = spans[k]
        f = min(sp['n'] - 1, int(round((t - sp['start']) * FPS)))
        if shot is None or shot[0] != k:
            S = make_shot(sp)
            S.setup()
            shot = (k, S)
        S = shot[1]
        im = finished(S, f)
        name = f'full-{n:02d}.jpg'
        cv2.imwrite(os.path.join(a.out, name), cv2.cvtColor(im, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 85])
        entry = dict(file=name, t=t, shot=sp['scene']['id'], closeups=[])
        acts = [x for x in (S.actors(f) if hasattr(S, 'actors') else []) if not x.get('prop') and x.get('points')]
        for x in acts:
            pts = np.array(list(x['points'].values()), float)
            cx, cy = pts.mean(0)
            w, h = 900, 560
            x0 = int(min(W - w, max(0, cx - w / 2)))
            y0 = int(min(H - h, max(0, cy - h / 2)))
            cname = f'near-{n:02d}-{x["name"]}.jpg'
            cv2.imwrite(os.path.join(a.out, cname), cv2.cvtColor(im[y0:y0 + h, x0:x0 + w], cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 88])
            entry['closeups'].append(dict(file=cname, name=x['name']))
        index.append(entry)
    with open(os.path.join(a.out, 'index.json'), 'w') as fh:
        json.dump(index, fh, ensure_ascii=False)


def cmd_render(a):
    film_dir, film, spans, dur = load_film(a.film)
    k, sp = find_span(spans, a.scene)
    scale, fps, step = (0.5, FPS // 2, 2) if a.draft else (1.0, FPS, 1)
    out = a.out or os.path.join(film_dir, 'qa', f'{a.scene}.mp4')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    p = ffmpeg_writer(out, int(W * scale), int(H * scale), fps, '16')
    t = time.time()
    for im in render_frames(film_dir, spans, k, list(range(0, sp['n'], step)), scale, a.jobs):
        p.stdin.write(np.ascontiguousarray(im).tobytes())
    p.stdin.close()
    p.wait()
    print(f'{out} {time.time() - t:.0f}s')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('picture')
    p.add_argument('film')
    p.add_argument('--out', required=True)
    p.add_argument('--draft', action='store_true')
    p.add_argument('--no-video', action='store_true')
    p.add_argument('--jobs', type=int, default=4)
    p = sub.add_parser('sound')
    p.add_argument('film')
    p.add_argument('--out', required=True)
    p = sub.add_parser('still')
    p.add_argument('film')
    p.add_argument('scene')
    p.add_argument('frames', nargs='+', type=int)
    p.add_argument('--crop', action='append', default=[])
    p.add_argument('--sheet', action='store_true')
    p.add_argument('--raw', action='store_true')
    p.add_argument('--out', default=None)
    p = sub.add_parser('render')
    p.add_argument('film')
    p.add_argument('scene')
    p.add_argument('--draft', action='store_true')
    p.add_argument('--jobs', type=int, default=4)
    p.add_argument('--out', default=None)
    p = sub.add_parser('frames')
    p.add_argument('film')
    p.add_argument('--at', required=True)
    p.add_argument('--out', required=True)
    a = ap.parse_args()
    {'frames': cmd_frames, 'picture': cmd_picture, 'sound': cmd_sound, 'still': cmd_still, 'render': cmd_render}[a.cmd](a)
