"""Tiny 3D-to-pixel-art toolkit used to build the monuments (gopurams, walls, rock hill, stadium ...).

A Canvas holds one baked sprite. You add solids in *metres* (east, north, height, in the global metre frame from
config.py), then bake(). Solids are drawn back to front, using the same camera as the map tiles:
  east -> screen right and up, north -> screen left and up, up -> straight up. The viewer sees the SOUTH and WEST
  faces, and light comes from the east, so the south face is bright and the west face is darker.
"""
from __future__ import annotations
import math
import numpy as np
from PIL import Image, ImageDraw
from shapely.geometry import MultiPoint

from config import K, VK, iso_from_metres

SHADOW_DIR = (-0.8, 0.28)  # screen px of shadow per px of height (same as render.py)


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def fp(q, u, v):
    """Point on a face quad (b0, b1, t1, t0) at u along the bottom edge and v up the face."""
    b = lerp(q[0], q[1], u)
    t = lerp(q[3], q[2], u)
    return lerp(b, t, v)


def frect(q, u0, u1, v0, v1):
    return [fp(q, u0, v0), fp(q, u1, v0), fp(q, u1, v1), fp(q, u0, v1)]


def flen(q):
    return math.hypot(q[1][0] - q[0][0], q[1][1] - q[0][1])


def fhgt(q):
    return math.hypot(q[3][0] - q[0][0], q[3][1] - q[0][1])


class Canvas:
    def __init__(self, foot, zmax, pad=8):
        """foot = (x0, y0, x1, y1) ground rectangle in metres that the sprite may cover; zmax = tallest point in metres."""
        pts = [iso_from_metres(x, y) for x in (foot[0], foot[2]) for y in (foot[1], foot[3])]
        self.ox = int(min(p[0] for p in pts)) - pad
        self.oy = int(min(p[1] for p in pts) - zmax * VK) - pad - 4
        w = int(max(p[0] for p in pts)) - self.ox + pad
        h = int(max(p[1] for p in pts)) - self.oy + pad
        self.w, self.h = w, h
        self.im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        self.d = ImageDraw.Draw(self.im)
        self.sh = Image.new("L", (w, h), 0)
        self.sd = ImageDraw.Draw(self.sh)
        self.objs = []     # (footprint, z0, drawfn)
        self.foot = foot
        self.dz = 0.0   # lifts everything drawn with P() (used for temples standing on a hill)
        self.ymax = max(p[1] for p in pts)

    # --------------------------------------------------------------------------------------------- projection
    def P(self, x, y, z=0.0):
        px, py = iso_from_metres(x, y, z + self.dz)
        return (px - self.ox, py - self.oy)

    def poly_m(self, pts_m, z=0.0):
        return [self.P(x, y, z) for x, y in pts_m]

    def _shadow(self, base_px, hpx):
        if hpx < 2:
            return
        dx, dy = SHADOW_DIR[0] * hpx, SHADOW_DIR[1] * hpx
        pts = list(base_px) + [(x + dx, y + dy) for x, y in base_px]
        hull = MultiPoint(pts).convex_hull
        if hull.geom_type == "Polygon":
            self.sd.polygon(list(hull.exterior.coords), fill=255)

    # --------------------------------------------------------------------------------------------- queue
    def add(self, foot, z0, fn):
        self.objs.append((foot, z0, fn))

    def bake(self):
        """Draw queued solids back to front, then return (RGBA, shadow L)."""
        n = len(self.objs)
        order = _toposort(self.objs)
        for i in order:
            self.objs[i][2]()
        return self.im, self.sh

    # --------------------------------------------------------------------------------------------- solids (draw now)
    def frustum(self, cx, cy, hw0, hd0, z0, hw1, hd1, z1, wall, roof=None, outline=True, shadow=True):
        """Four-sided truncated pyramid. Returns (S face quad, W face quad, top polygon)."""
        P = self.P
        S = (P(cx - hw0, cy - hd0, z0), P(cx + hw0, cy - hd0, z0), P(cx + hw1, cy - hd1, z1), P(cx - hw1, cy - hd1, z1))
        W = (P(cx - hw0, cy - hd0, z0), P(cx - hw0, cy + hd0, z0), P(cx - hw1, cy + hd1, z1), P(cx - hw1, cy - hd1, z1))
        top = [P(cx - hw1, cy - hd1, z1), P(cx + hw1, cy - hd1, z1), P(cx + hw1, cy + hd1, z1), P(cx - hw1, cy + hd1, z1)]
        if shadow:
            base = [P(cx - hw0, cy - hd0, 0), P(cx + hw0, cy - hd0, 0), P(cx + hw0, cy + hd0, 0), P(cx - hw0, cy + hd0, 0)]
            self._shadow(base, z1 * VK)
        d = self.d
        d.polygon(list(S), fill=shade(wall, 1.0), outline=shade(wall, 0.58) if outline else None)
        d.polygon(list(W), fill=shade(wall, 0.76), outline=shade(wall, 0.46) if outline else None)
        rc = roof if roof is not None else shade(wall, 1.12)
        d.polygon(top, fill=rc, outline=shade(rc, 0.66) if outline else None)
        return S, W, top

    def box(self, x0, y0, x1, y1, z0, z1, wall, roof=None, outline=True, shadow=True):
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        return self.frustum(cx, cy, (x1 - x0) / 2, (y1 - y0) / 2, z0, (x1 - x0) / 2, (y1 - y0) / 2, z1, wall, roof, outline, shadow)

    def extrude(self, ring_m, z0, z1, wall, roof, holes=(), outline=True, shadow=True, top=True):
        """Prism over an arbitrary polygon (list of (x, y) metres). Visible side faces are those facing south or west."""
        P = self.P
        rings = [(ring_m, 1)] + [(h, -1) for h in holes]
        for ring, sgn in rings:
            pts = list(ring)
            if pts[0] == pts[-1]:
                pts = pts[:-1]
            area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))
            ccw = 1 if area > 0 else -1
            segs = []
            for i in range(len(pts)):
                a, b = pts[i], pts[(i + 1) % len(pts)]
                dx, dy = b[0] - a[0], b[1] - a[1]
                nx, ny = dy * ccw * sgn, -dx * ccw * sgn          # outward normal in the metre frame
                # screen-space downward component of a normal (nx, ny): south (0,-1) and west (-1,0) face the viewer
                facing = -(nx + ny)
                if facing > 1e-9:
                    segs.append((facing, a, b, nx, ny))
            # far edges first
            segs.sort(key=lambda s: -(s[1][0] + s[1][1] + s[2][0] + s[2][1]))
            for facing, a, b, nx, ny in segs:
                f = 0.76 + 0.24 * (-ny) / max(1e-9, -(nx + ny))
                q = [P(a[0], a[1], z0), P(b[0], b[1], z0), P(b[0], b[1], z1), P(a[0], a[1], z1)]
                self.d.polygon(q, fill=shade(wall, f), outline=shade(wall, 0.5 * f) if outline else None)
        if shadow:
            self._shadow([P(x, y, 0) for x, y in ring_m], z1 * VK)
        if top:
            self.fill_poly([P(x, y, z1) for x, y in ring_m], [[P(x, y, z1) for x, y in h] for h in holes], roof, outline=shade(roof, 0.66) if outline else None)

    def fill_poly(self, ring_px, holes_px, colour, outline=None):
        """Filled polygon with holes, composited without disturbing what is already drawn inside the holes."""
        if not holes_px:
            self.d.polygon(ring_px, fill=colour, outline=outline)
            return
        m = Image.new("L", self.im.size, 0)
        md = ImageDraw.Draw(m)
        md.polygon(ring_px, fill=255)
        for h in holes_px:
            md.polygon(h, fill=0)
        self.im.paste(tuple(colour[:3]) + (255,), (0, 0), m)
        if outline:
            self.d.line(ring_px + ring_px[:1], fill=outline)
            for h in holes_px:
                self.d.line(h + h[:1], fill=outline)

    def ground(self, ring_m, colour, holes=(), z=0.0, outline=None):
        self.fill_poly([self.P(x, y, z) for x, y in ring_m], [[self.P(x, y, z) for x, y in h] for h in holes], colour, outline)


def _toposort(objs):
    n = len(objs)
    if n <= 1:
        return list(range(n))
    foot = [o[0] for o in objs]
    z0 = [o[1] for o in objs]
    after = [[] for _ in range(n)]   # i -> objects that must be drawn after i
    indeg = [0] * n
    for i in range(n):
        a = foot[i]
        for j in range(i + 1, n):
            b = foot[j]
            a_front = a[2] <= b[0] + 1e-6 or a[3] <= b[1] + 1e-6   # a is west or south of b, so nearer the viewer
            b_front = b[2] <= a[0] + 1e-6 or b[3] <= a[1] + 1e-6
            if a_front and b_front:
                continue                                           # cannot overlap on screen
            if a_front:
                e = (j, i)
            elif b_front:
                e = (i, j)
            elif z0[i] == z0[j]:
                continue
            else:
                e = (i, j) if z0[i] < z0[j] else (j, i)
            after[e[0]].append(e[1])
            indeg[e[1]] += 1
    # Kahn, farthest first among the ready ones
    key = [-(foot[i][0] + foot[i][1]) for i in range(n)]
    ready = sorted([i for i in range(n) if indeg[i] == 0], key=lambda i: key[i])
    out = []
    while ready:
        i = ready.pop(0)
        out.append(i)
        for j in after[i]:
            indeg[j] -= 1
            if indeg[j] == 0:
                ready.append(j)
        ready.sort(key=lambda i: key[i])
    if len(out) < n:  # cycle (should not happen): append the rest by depth
        rest = [i for i in range(n) if i not in set(out)]
        rest.sort(key=lambda i: key[i])
        out += rest
    return out
