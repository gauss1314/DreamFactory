"""Metric 3D layout rig.  +X right, +Y forward, +Z up, metres."""
import numpy as np, cv2, math
from . import W, H
from .paint import f32

NEAR = 0.05


class Camera3D:
    def __init__(self, eye, target, focal=1500., w=W, h=H, cx=None, cy=None, roll=0.0):
        self.eye = np.asarray(eye, float); self.w, self.h = w, h
        self.f = float(focal)
        self.cx = w * .5 if cx is None else cx
        self.cy = h * .5 if cy is None else cy
        fwd = np.asarray(target, float) - self.eye
        fwd /= np.linalg.norm(fwd)
        up = np.array([0, 0, 1.])
        if abs(fwd @ up) > .999: up = np.array([0, 1., 0])
        right = np.cross(fwd, up); right /= np.linalg.norm(right)
        upv = np.cross(right, fwd)
        if roll:
            c, s = math.cos(roll), math.sin(roll)
            right, upv = right * c + upv * s, upv * c - right * s
        self.R = np.stack([right, -upv, fwd])        # world -> cam (x right, y down, z fwd)
        self.K = np.array([[self.f, 0, self.cx], [0, self.f, self.cy], [0, 0, 1.]])

    def cam(self, P):
        return (np.asarray(P, float) - self.eye) @ self.R.T

    def project(self, P):
        """-> (..., 2) screen px, (...) z_cam"""
        c = self.cam(P)
        z = c[..., 2]
        zz = np.where(z > NEAR, z, NEAR)
        return np.stack([c[..., 0] / zz * self.f + self.cx, c[..., 1] / zz * self.f + self.cy], -1), z

    def scale(self, P):
        """px per metre at world point(s)"""
        z = self.cam(P)[..., 2]
        return self.f / np.maximum(z, NEAR)

    def clip_seg(self, a, b):
        a, b = np.asarray(a, float), np.asarray(b, float)
        za, zb = self.cam(a)[2], self.cam(b)[2]
        if za < NEAR and zb < NEAR: return None
        if za < NEAR: a = a + (b - a) * (NEAR - za) / (zb - za)
        elif zb < NEAR: b = b + (a - b) * (NEAR - zb) / (za - zb)
        return self.project(np.stack([a, b]))[0]

    def rays(self, h=None, w=None):
        h = self.h if h is None else h; w = self.w if w is None else w
        y, x = np.mgrid[0:h, 0:w].astype(f32)
        d = np.stack([(x - self.cx) / self.f, (y - self.cy) / self.f, np.ones_like(x)], -1)
        return (d @ self.R.astype(f32)).astype(f32)          # unnormalised, z_cam = t

    def plane_t(self, p0, n, rays=None):
        """ray parameter (= z_cam) of plane hit per pixel; <=0 where behind"""
        d = self.rays() if rays is None else rays
        n = np.asarray(n, float)
        den = d @ n.astype(f32)
        num = float((np.asarray(p0, float) - self.eye) @ n)
        with np.errstate(divide='ignore', invalid='ignore'):
            t = num / den
        return np.where(np.isfinite(t) & (t > NEAR), t, 0).astype(f32)

    def H_plane(self, p0, e1, e2, tw, th, mw, mh):
        """3x3 homography: texture px (u,v) -> screen px.  Texture spans mw metres along e1, mh along e2."""
        e1, e2 = np.asarray(e1, float), np.asarray(e2, float)
        A = np.array([[mw / tw, 0, 0], [0, mh / th, 0], [0, 0, 1.]])
        M = np.stack([self.R @ e1, self.R @ e2, self.R @ (np.asarray(p0, float) - self.eye)], 1)
        return self.K @ M @ A

    def warp_plane(self, tex, p0, e1, e2, mw, mh, fog=None, interp=cv2.INTER_LINEAR):
        """premultiplied RGBA texture on a plane -> premult RGBA screen layer.
        fog=(rgb, start, density) exponential ray-distance fog."""
        th, tw = tex.shape[:2]
        if tex.shape[2] == 3: tex = np.dstack([tex, np.ones((th, tw), f32)])
        Hm = self.H_plane(p0, e1, e2, tw, th, mw, mh)
        n = np.cross(np.asarray(e1, float), np.asarray(e2, float))
        t = self.plane_t(p0, n)
        # minification antialias
        out = cv2.warpPerspective(tex.astype(f32), Hm, (self.w, self.h), flags=interp, borderMode=cv2.BORDER_CONSTANT)
        out = out * (t > NEAR)[..., None]
        if fog is not None:
            col, st, dn = fog
            rd = self.rays(); dist = t * np.linalg.norm(rd, axis=-1)
            k = 1 - np.exp(-np.maximum(0, dist - st) * dn)
            out[..., :3] = out[..., :3] * (1 - k[..., None]) + np.asarray(col, f32) * (k * out[..., 3])[..., None]
        return out

    def uv(self, p0, e1, e2):
        """per-pixel metric (u, v, z_cam) on a plane"""
        d = self.rays()
        n = np.cross(np.asarray(e1, float), np.asarray(e2, float))
        t = self.plane_t(p0, n, d)
        X = self.eye.astype(f32) + d * t[..., None] - np.asarray(p0, f32)
        return X @ np.asarray(e1, f32), X @ np.asarray(e2, f32), t


def voronoi_crevice(u, v, cell, seed=0, jitter=.75, warp=.12):
    """d2-d1 over a 3x3 jittered metric neighbourhood.  returns (crevice distance, cell id hash 0..1)"""
    r = np.random.default_rng(seed)
    tab = r.random((4096, 2)).astype(f32)
    tid = r.random(4096).astype(f32)
    cu, cv_ = (cell, cell) if np.isscalar(cell) else cell
    x = u / cu; y = v / cv_
    ix = np.floor(x).astype(np.int64); iy = np.floor(y).astype(np.int64)
    d1 = np.full(x.shape, 9., f32); d2 = np.full(x.shape, 9., f32); idd = np.zeros(x.shape, f32)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            jx, jy = ix + dx, iy + dy
            k = ((jx * 73856093) ^ (jy * 19349663)) & 4095
            px = jx + .5 + (tab[k, 0] - .5) * jitter
            py = jy + .5 + (tab[k, 1] - .5) * jitter
            d = np.sqrt((x - px) ** 2 + (y - py) ** 2).astype(f32)
            m = d < d1
            d2 = np.where(m, d1, np.minimum(d2, d)); idd = np.where(m, tid[k], idd); d1 = np.where(m, d, d1)
    return d2 - d1, idd


def rot_z(a):
    c, s = math.cos(a), math.sin(a); return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.]])


def rot_x(a):
    c, s = math.cos(a), math.sin(a); return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(a):
    c, s = math.cos(a), math.sin(a); return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
