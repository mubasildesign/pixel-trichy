"""Isometric pixel renderer.  render_tile(tx, ty) returns a 512x512 RGB image at the deepest level.

Style: flat colours, 1px outlines, no anti-aliasing.  Painter's algorithm: ground, land cover, trees, water, roads,
rail, then buildings sorted from far (top of image) to near.
"""
from __future__ import annotations
import hashlib
import numpy as np
import shapely
from PIL import Image, ImageDraw
from shapely.geometry import box

from config import TILE, K, VK, WIDTH, HEIGHT, iso, iso_from_metres, to_metres, LON0, LAT0, M_PER_DEG_LON, M_PER_DEG_LAT
from landmarks import GOPURAMS, ROCKS

MAX_H_PX = int(45 * VK) + 8  # tallest building we draw, in px, bounds the query margin below a tile

PAL = dict(
    ground=(222, 205, 160),
    sand=(232, 214, 168),
    crop=(190, 205, 120), crop2=(176, 196, 108),
    grass=(160, 196, 108), shrub=(140, 178, 96), forest=(116, 164, 84), wetland=(150, 190, 150),
    barren=(214, 192, 150), urban=(212, 196, 156),
    residential=(218, 200, 158), park=(150, 192, 104),
    water=(92, 160, 196), water_dark=(70, 134, 176), water_hi=(150, 204, 224), shore=(206, 220, 190),
    road_case=(150, 128, 100), road={"motorway": (250, 214, 130), "trunk": (250, 214, 130), "primary": (250, 226, 160),
                                     "secondary": (252, 236, 190), "tertiary": (250, 240, 214)},
    road_minor=(242, 234, 218), path=(214, 188, 150), rail=(120, 112, 112), rail_tie=(176, 160, 140),
    settled=(216, 198, 160), outline=(70, 50, 48),
)
WALLS = [(244, 226, 190), (240, 196, 170), (232, 214, 130), (170, 208, 200), (214, 170, 160), (236, 236, 226),
         (200, 214, 232), (226, 180, 120), (246, 210, 214), (190, 220, 160)]
ROOFS = [(190, 120, 96), (176, 168, 156), (200, 192, 180), (160, 104, 88), (112, 140, 168), (184, 150, 100)]
ROAD_RANK = {"footway": 0, "path": 0, "steps": 0, "cycleway": 0, "track": 1, "service": 2, "living_street": 2, "pedestrian": 2,
             "unknown": 3, "residential": 3, "unclassified": 4, "tertiary": 5, "secondary": 6, "primary": 7, "trunk": 8, "motorway": 9}


def _shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


def _h(*args) -> int:
    return int(hashlib.md5("|".join(map(str, args)).encode()).hexdigest()[:8], 16)


def _rings(geom):
    """Yield (exterior_coords, [interior_coords]) for any polygonal geometry."""
    if geom.is_empty:
        return
    gt = geom.geom_type
    if gt == "Polygon":
        yield list(geom.exterior.coords), [list(r.coords) for r in geom.interiors]
    elif gt in ("MultiPolygon", "GeometryCollection"):
        for g in geom.geoms:
            yield from _rings(g)


class Renderer:
    def __init__(self, scene, trees):
        self.scene, self.trees = scene, trees

    def _query(self, key, rect, extra_down=0):
        geoms, meta = self.scene[key]
        q = box(rect[0], rect[1], rect[2], rect[3] + extra_down)
        idx = self.trees[key].query(q)
        return geoms, meta, np.sort(idx)

    # ---------------------------------------------------------------------------------------------
    def render_tile(self, tx, ty, size=TILE, ox=0, oy=0):
        x0, y0 = tx * TILE + ox, ty * TILE + oy
        rect = (x0 - 2, y0 - 2, x0 + size + 2, y0 + size + 2)
        im = Image.new("RGB", (size, size), PAL["ground"])
        d = ImageDraw.Draw(im)

        def P(coords):
            return [(x - x0, y - y0) for x, y in coords]

        def fill(geom, color, outline=None, width=1):
            for ext, holes in _rings(geom):
                if len(ext) < 3:
                    continue
                d.polygon(P(ext), fill=color, outline=outline)
                for h in holes:
                    d.polygon(P(h), fill=PAL["ground"] if color != PAL["ground"] else color)

        # -- land use + cover
        if "land_use" in self.scene:
            g, m, idx = self._query("land_use", rect)
            for i in idx:
                sub, cls = m[i]
                col = PAL["park"] if (sub in ("park", "recreation", "golf") or cls in ("park", "garden", "playground", "golf_course")) else \
                    PAL["residential"] if sub == "residential" else None
                if col:
                    fill(g[i], col)
        if "land_cover" in self.scene:
            g, m, idx = self._query("land_cover", rect)
            order = {"barren": 0, "urban": 0, "grass": 1, "crop": 2, "shrub": 3, "wetland": 3, "forest": 4}
            for i in sorted(idx, key=lambda i: order.get(m[i], 0)):
                sub = m[i]
                col = PAL.get(sub, PAL["ground"])
                if sub == "urban":
                    continue
                fill(g[i], col)
                if sub == "crop":
                    self._hatch(d, g[i], x0, y0, size, PAL["crop2"])
        smask = self._settled_mask(x0, y0, size)
        if smask is not None:
            im.paste(Image.new("RGB", im.size, PAL["settled"]), (0, 0), smask)
            d = ImageDraw.Draw(im)
        # -- water
        if "water" in self.scene:
            g, m, idx = self._query("water", rect)
            for i in idx:
                for ext, holes in _rings(g[i]):
                    if len(ext) < 3:
                        continue
                    d.polygon(P(ext), fill=PAL["water"], outline=PAL["shore"])
                    for h in holes:
                        d.polygon(P(h), fill=PAL["ground"], outline=PAL["shore"])
            self._water_ripples(d, im, x0, y0, size)
        # -- trees
        self._trees(d, rect, x0, y0, size)
        # -- infrastructure like bridges are rendered through roads
        # -- roads (casing, then fill, small to large)
        if "segments" in self.scene:
            g, m, idx = self._query("segments", rect)
            roads = [i for i in idx if m[i][0] == "road"]
            roads.sort(key=lambda i: ROAD_RANK.get(m[i][1], 3))
            for i in roads:
                for ext, _ in _rings(g[i]):
                    if len(ext) >= 3:
                        d.polygon(P(ext), fill=PAL["road_case"], outline=PAL["road_case"], width=2)
            for i in roads:
                cls = m[i][1]
                col = PAL["road"].get(cls, PAL["path"] if ROAD_RANK.get(cls, 3) <= 1 else PAL["road_minor"])
                for ext, _ in _rings(g[i]):
                    if len(ext) >= 3:
                        d.polygon(P(ext), fill=col)
            for i in idx:
                if m[i][0] == "rail":
                    for ext, _ in _rings(g[i]):
                        if len(ext) >= 3:
                            d.polygon(P(ext), fill=PAL["rail_tie"], outline=PAL["rail"])
        # -- buildings
        if "buildings" in self.scene:
            self._buildings(d, rect, x0, y0)
        return im

    # ---------------------------------------------------------------------------------------------
    def _settled_mask(self, x0, y0, size):
        dens, cell = self.scene["settled"]
        cx0, cy0 = int(x0 // cell) - 1, int(y0 // cell) - 1
        n = size // cell + 4
        if cx0 + n < 0 or cy0 + n < 0 or cx0 >= dens.shape[1] or cy0 >= dens.shape[0]:
            return None
        sub = np.zeros((n, n), dtype=np.float32)
        ys, xs = max(cy0, 0), max(cx0, 0)
        ye, xe = min(cy0 + n, dens.shape[0]), min(cx0 + n, dens.shape[1])
        sub[ys - cy0:ye - cy0, xs - cx0:xe - cx0] = dens[ys:ye, xs:xe]
        if sub.max() < 0.10:
            return None
        big = Image.fromarray(sub, mode="F").resize((n * cell, n * cell), Image.BILINEAR)
        ox, oy = int(x0 - cx0 * cell), int(y0 - cy0 * cell)
        big = big.crop((ox, oy, ox + size, oy + size))
        a = (np.asarray(big) > 0.10).astype(np.uint8) * 255
        return Image.fromarray(a, mode="L")

    def _hatch(self, d, geom, x0, y0, size, col):
        """Field furrows: short iso-aligned dashes, anchored to world coordinates so tiles line up."""
        step = 24
        gx0, gy0 = int((x0 - step) // step), int((y0 - step) // step)
        pts = [(gx * step + 6, gy * step + 6) for gx in range(gx0, gx0 + size // step + 3) for gy in range(gy0, gy0 + size // step + 3)]
        if not pts:
            return
        arr = np.array(pts, dtype=float)
        ok = shapely.contains_xy(geom, arr[:, 0], arr[:, 1])
        for (px, py), k in zip(arr, ok):
            if k:
                X, Y = px - x0, py - y0
                d.line([(X, Y), (X + 8, Y + 4)], fill=col)

    def _water_ripples(self, d, im, x0, y0, size):
        """Sparse light dashes on the water pixels, deterministic by world position."""
        a = np.asarray(im)
        mask = (a[:, :, 0] == PAL["water"][0]) & (a[:, :, 1] == PAL["water"][1]) & (a[:, :, 2] == PAL["water"][2])
        if not mask.any():
            return
        step = 14
        for gy in range(int(y0 // step), int((y0 + size) // step) + 1):
            for gx in range(int(x0 // step), int((x0 + size) // step) + 1):
                hv = _h(gx, gy, "w")
                if hv % 5:
                    continue
                X = gx * step + hv % 7 - x0
                Y = gy * step + (hv >> 4) % 7 - y0
                if 0 <= X < size - 6 and 0 <= Y < size and mask[int(Y), int(X)]:
                    d.line([(X, Y), (X + 5, Y)], fill=PAL["water_hi"] if hv % 2 else PAL["water_dark"])

    def _trees(self, d, rect, x0, y0, size):
        """Tree sprites scattered inside forest/grass/wetland cover (not on water). World-anchored grid so tiles agree."""
        if "land_cover" not in self.scene:
            return
        g, m, idx = self._query("land_cover", (x0 - 12, y0 - 12, x0 + size + 12, y0 + size + 12))
        polys = [(g[i], m[i]) for i in idx if m[i] in ("forest", "shrub", "grass", "wetland")]
        if not polys:
            return
        cell = 20
        gx0, gy0 = int((x0 - 12) // cell), int((y0 - 12) // cell)
        n = (size + 24) // cell + 2
        pts, kinds = [], []
        for gy in range(gy0, gy0 + n):
            for gx in range(gx0, gx0 + n):
                hv = _h(gx, gy, "t")
                pts.append((gx * cell + hv % cell, gy * cell + (hv >> 8) % cell))
                kinds.append(hv >> 16)
        arr = np.array(pts, dtype=float)
        dens = {"forest": 0.85, "shrub": 0.3, "grass": 0.08, "wetland": 0.25}
        ok = np.zeros(len(arr), dtype=bool)
        for geom, sub in polys:
            inside = shapely.contains_xy(geom, arr[:, 0], arr[:, 1])
            thr = dens[sub]
            ok |= inside & (np.array([(k % 1000) / 1000 for k in kinds]) < thr)
        if "water" in self.scene:
            gw, _, iw = self._query("water", (x0 - 12, y0 - 12, x0 + size + 12, y0 + size + 12))
            for i in iw:
                ok &= ~shapely.contains_xy(gw[i], arr[:, 0], arr[:, 1])
        order = np.argsort(arr[:, 1])
        for j in order:
            if not ok[j]:
                continue
            X, Y = arr[j][0] - x0, arr[j][1] - y0
            k = kinds[j]
            r = 5 + k % 3
            crown = (88 + k % 20, 150 + (k >> 3) % 24, 72 + k % 16)
            d.ellipse([X - r + 2, Y + 1, X + r + 2, Y + 4], fill=(120, 150, 90))  # shadow
            d.line([(X, Y), (X, Y - 4)], fill=(110, 80, 60))
            d.ellipse([X - r, Y - 4 - r * 2 + 2, X + r, Y - 3], fill=crown, outline=_shade(crown, 0.72))
            d.ellipse([X - r + 2, Y - 4 - r * 2 + 3, X, Y - 4 - r], fill=_shade(crown, 1.18))

    def _sprites_for(self, rect):
        if not hasattr(self, "_sprites"):
            self._sprites = []
            for name, lat, lon, bw, bd, hh, tiers, col in GOPURAMS:
                cx, cy = to_metres(lon, lat)
                px, py = iso_from_metres(cx, cy)
                self._sprites.append(dict(kind="gopuram", cx=cx, cy=cy, bw=bw, bd=bd, h=hh, tiers=tiers, col=col,
                                          box=(px - bw * K, py - hh * VK - 20, px + bw * K, py + bd * K), y=py + bd * K / 2))
            for name, lat, lon, r, hh, temple in ROCKS:
                cx, cy = to_metres(lon, lat)
                px, py = iso_from_metres(cx, cy)
                self._sprites.append(dict(kind="rock", cx=cx, cy=cy, r=r, h=hh, temple=temple, seed=_h(name),
                                          box=(px - r * K * 1.5, py - hh * VK - 30, px + r * K * 1.5, py + r * K), y=py + r * K * 0.5))
        x0, y0, x1, y1 = rect
        return [s for s in self._sprites if s["box"][0] < x1 and s["box"][2] > x0 and s["box"][1] < y1 and s["box"][3] > y0]

    def _draw_gopuram(self, d, sp, x0, y0):
        cx, cy, bw, bd, H, n, col = sp["cx"], sp["cy"], sp["bw"], sp["bd"], sp["h"], sp["tiers"], sp["col"]

        def pt(x, y, z):
            px, py = iso_from_metres(x, y, z)
            return (px - x0, py - y0)
        # a low enclosure plinth, then a gateway block, then tapering tiers
        tiers = [(1.0, 0.0, H * 0.22)]
        body = H * 0.78
        for k in range(n):
            f = 0.78 * (1 - k / (n + 0.5)) + 0.08
            tiers.append((f, H * 0.22 + body * k / n, H * 0.22 + body * (k + 1) / n))
        for f, z0, z1 in tiers:
            hw, hd = bw * f / 2, bd * f / 2
            # south face (normal -y) and west face (normal -x) are the visible ones from the south-west
            south = [pt(cx - hw, cy - hd, z0), pt(cx + hw, cy - hd, z0), pt(cx + hw, cy - hd, z1), pt(cx - hw, cy - hd, z1)]
            west = [pt(cx - hw, cy + hd, z0), pt(cx - hw, cy - hd, z0), pt(cx - hw, cy - hd, z1), pt(cx - hw, cy + hd, z1)]
            top = [pt(cx - hw, cy - hd, z1), pt(cx + hw, cy - hd, z1), pt(cx + hw, cy + hd, z1), pt(cx - hw, cy + hd, z1)]
            band = tuple(int(c * (0.9 + 0.1 * ((tiers.index((f, z0, z1)) % 2)))) for c in col)
            d.polygon(south, fill=band, outline=_shade(band, 0.62))
            d.polygon(west, fill=_shade(band, 0.8), outline=_shade(band, 0.55))
            d.polygon(top, fill=(214, 120, 90) if z1 > H * 0.22 + 1 else (200, 188, 170), outline=_shade(col, 0.6))
            # little windows on the south face
            if z1 - z0 > 3 and f < 0.95:
                wx = [(cx - hw * 0.5 + hw * j / 1.0, cy - hd, (z0 + z1) / 2) for j in range(2)]
                for x, y, z in wx:
                    px, py = pt(x, y, z)
                    d.rectangle([px - 1, py - 2, px + 1, py + 1], fill=(110, 60, 50))
        # golden kalasams on the crown
        kx, ky = pt(cx, cy, H)
        for j in (-3, 0, 3):
            d.ellipse([kx + j - 1, ky - 6, kx + j + 1, ky - 3], fill=(240, 200, 70), outline=(150, 110, 30))

    def _draw_rock(self, d, sp, x0, y0):
        cx, cy, R, H, seed = sp["cx"], sp["cy"], sp["r"], sp["h"], sp["seed"]
        rng = np.random.default_rng(seed)
        ph = rng.uniform(0, 6.28, 4)
        ang = np.linspace(0, 2 * np.pi, 36, endpoint=False)
        steps = 24
        for k in range(steps + 1):
            t = k / steps
            rr = R * (1 - t ** 2.8) * 0.98 + 2
            wob = 1 + 0.18 * np.sin(2 * ang + ph[0]) + 0.1 * np.sin(3 * ang + ph[1]) + 0.05 * np.sin(5 * ang + ph[2])
            xs = cx + 1.25 * rr * wob * np.cos(ang)       # elongated east-west
            ys = cy + 0.8 * rr * wob * np.sin(ang)
            z = H * t
            pts = [(iso_from_metres(x, y, z)[0] - x0, iso_from_metres(x, y, z)[1] - y0) for x, y in zip(xs, ys)]
            base = (150, 128, 108)
            top = (190, 172, 148)
            c = tuple(int(base[i] + (top[i] - base[i]) * t ** 0.8) for i in range(3))
            d.polygon(pts, fill=c, outline=_shade(c, 0.74) if k % 2 == 0 else None)
        if sp["temple"]:
            px, py = iso_from_metres(cx, cy, H)
            X, Y = px - x0, py - y0
            d.polygon([(X - 7, Y + 2), (X + 7, Y + 2), (X + 7, Y - 8), (X - 7, Y - 8)], fill=(238, 226, 200), outline=(120, 90, 70))
            d.polygon([(X - 8, Y - 8), (X + 8, Y - 8), (X, Y - 16)], fill=(214, 120, 90), outline=(120, 70, 60))
            d.rectangle([X - 1, Y - 5, X + 1, Y + 2], fill=(110, 60, 50))

    def _buildings(self, d, rect, x0, y0):
        g, m, idx = self._query("buildings", rect, extra_down=MAX_H_PX)
        sprites = self._sprites_for((rect[0], rect[1], rect[2], rect[3] + MAX_H_PX))
        if not len(idx) and not sprites:
            return
        if len(idx):
            miny = shapely.bounds(g[idx])  # xmin, ymin, xmax, ymax
            keys = list(miny[:, 3])
        else:
            keys = []
        items = [(k, 0, int(idx[j])) for j, k in enumerate(keys)] + [(sp["y"], 1, sp) for sp in sprites]
        items.sort(key=lambda t: t[0])
        for _, is_sprite, ref in items:
            if is_sprite:
                (self._draw_gopuram if ref["kind"] == "gopuram" else self._draw_rock)(d, ref, x0, y0)
                continue
            i = ref
            geom = g[i]
            h, known, cls, name, roof_shape = m[i]
            hp = h * VK
            hv = _h(i)
            wall = WALLS[hv % len(WALLS)]
            if cls in ("temple", "church", "mosque", "place_of_worship"):
                wall = (240, 226, 200)
            roof = ROOFS[(hv >> 5) % len(ROOFS)] if h < 9 else ROOFS[1 + (hv >> 5) % 2]
            if cls in ("temple", "church", "mosque"):
                roof = (226, 200, 160)
            ring = list(geom.exterior.coords)[:-1]
            n = len(ring)
            if n < 3:
                continue
            xs = np.array([p[0] for p in ring]); ys = np.array([p[1] for p in ring])
            area2 = np.sum(xs * np.roll(ys, -1) - np.roll(xs, -1) * ys)
            sgn = 1.0 if area2 > 0 else -1.0
            # walls facing the viewer (outward normal pointing down the screen)
            faces = []
            for a in range(n):
                p0, p1 = ring[a], ring[(a + 1) % n]
                dx, dy = p1[0] - p0[0], p1[1] - p0[1]
                nx, ny = dy * sgn, -dx * sgn
                if ny > 1e-6:
                    faces.append((p0, p1, nx / (np.hypot(nx, ny) + 1e-9)))
            for p0, p1, nxn in faces:
                shade = 0.82 if nxn < 0 else 1.0
                quad = [(p0[0] - x0, p0[1] - y0), (p1[0] - x0, p1[1] - y0),
                        (p1[0] - x0, p1[1] - y0 - hp), (p0[0] - x0, p0[1] - y0 - hp)]
                d.polygon(quad, fill=_shade(wall, shade))
            roof_pts = [(x - x0, y - y0 - hp) for x, y in ring]
            d.polygon(roof_pts, fill=roof, outline=_shade(roof, 0.7))
            if h > 14 and hv % 6 == 0:  # rooftop water tank / stair-head
                cx = sum(p[0] for p in roof_pts) / n; cy = sum(p[1] for p in roof_pts) / n
                d.rectangle([cx - 2, cy - 4, cx + 2, cy], fill=(70, 110, 160), outline=(40, 70, 110))
