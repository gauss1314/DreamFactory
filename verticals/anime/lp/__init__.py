"""Anime engine: gouache paint, ink cels, a metric camera, compositing and 35 mm optics.

The engine modules (paint, ink, cam, comp, clouds, plants, brush, props, ink_letters) come from
The Last Page by ChetasLua (github.com/ChetasLua/the-last-page), used here for personal exploration.
"""
import os

W, H = 2048, 1152
FPS = 24

# Plates painted in a shot's setup() are cached here, per film, as float16 .npy.
CACHE = os.environ.get('DF_ANIME_CACHE', os.path.join(os.path.dirname(__file__), '..', '..', '..', '.cache', 'anime'))


def cache_path(name):
    """Where to keep a cached plate. Put a version in `name` and change it when the plate changes."""
    os.makedirs(CACHE, exist_ok=True)
    return os.path.join(CACHE, name)
