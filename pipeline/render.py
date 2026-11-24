"""Detailed isometric pixel renderer (v2). render_tile(tx, ty) returns a 512x512 RGB image at the deepest level.

Builds on render_v1 (land cover, water, roads, landmark sprites) and adds: cast shadows, asphalt roads with markings,
sidewalks, rail ballast, street trees and yard trees, traffic (autos, scooters, cars, buses), pedestrians, and detailed
buildings (windows, shopfronts with awnings, pitched tile roofs, textured flat roofs with water tanks and stair-heads).

Everything is anchored to world coordinates (hash of position or of the feature), and tiles are drawn on a padded canvas, so
neighbouring tiles agree at their seams.
"""
from __future__ import annotations
import math
import numpy as np
import shapely
from PIL import Image, ImageDraw, ImageFilter
from shapely.geometry import box

import render_v1 as V1
import sprites as SP
from config import TILE, K, VK, iso
from render_v1 import _rings, _shade, _h, PAL, WALLS, ROAD_RANK, MAX_H_PX

PAD = 40
HEIGHT_TRIM = 0.74
BAKE_VEHICLES = False   # vehicles are animated in the viewer (web/traffic.js), not baked into tiles
SHADOW = np.array([0.78, 0.81, 0.90], dtype=np.float32)
SHADOW_DIR = (-0.8, 0.28)  # screen px of shadow per px of height (sun in the east)

ASPHALT = {"motorway": (92, 90, 94), "trunk": (92, 90, 94), "primary": (98, 95, 98), "secondary": (110, 105, 104),
           "tertiary": (132, 124, 116), "unclassified": (150, 140, 128), "residential": (154, 143, 130),
           "living_street": (156, 146, 132), "service": (164, 154, 138), "track": (190, 168, 132), "pedestrian": (196, 184, 164),
           "unknown": (146, 136, 124)}
FOOT = (206, 190, 156)
CURB = (210, 202, 184)
CURB_LINE = (96, 86, 80)

ROOF_FLAT = [(204, 192, 174), (214, 206, 190), (192, 180, 164), (206, 194, 170), (196, 184, 170), (222, 212, 196)]
ROOF_TILE = [(184, 100, 72), (170, 90, 66), (196, 118, 84), (156, 84, 64)]
ROOF_TIN = [(120, 150, 170), (150, 160, 150), (170, 90, 70), (110, 130, 160)]
SHOP = [(200, 60, 50), (50, 120, 180), (232, 170, 40), (60, 150, 90), (210, 90, 150)]
# wall colour with a matching trim colour (cornice, floor slabs, window surrounds), as in painted Indian streets
WALL_SETS = [((236, 214, 160), (252, 244, 220)), ((232, 168, 120), (250, 226, 196)), ((226, 196, 92), (252, 240, 190)),
             ((132, 190, 186), (232, 244, 236)), ((206, 128, 118), (244, 214, 200)), ((226, 226, 214), (250, 250, 242)),
             ((150, 180, 222), (232, 240, 252)), ((220, 150, 84), (246, 214, 160)), ((236, 170, 188), (252, 232, 236)),
             ((156, 204, 120), (236, 248, 214)), ((190, 120, 70), (232, 196, 150)), ((120, 146, 196), (222, 232, 248))]
GLASS_SETS = [(66, 92, 120), (58, 84, 104), (84, 110, 130), (50, 70, 96)]
SHUTTER = [(60, 120, 80), (150, 96, 60), (70, 100, 150), (170, 70, 60)]
HERITAGE = {"train_station", "college", "university", "library", "civic", "school", "hospital", "government", "public_building"}
TOWER_CLS = {"train_station", "college", "university", "library", "civic"}
GOODS_C = [(236, 120, 60), (210, 50, 50), (110, 170, 70), (244, 210, 80), (170, 90, 150), (250, 250, 240)]
SIGN = [(214, 60, 50), (40, 110, 190), (240, 190, 40), (50, 150, 100), (190, 70, 160), (250, 250, 240)]

_NOISE = np.random.default_rng(7).normal(size=(256, 256)).astype(np.float32)


def _lowfreq(n, sigma, seed):
    from scipy.ndimage import gaussian_filter
    a = gaussian_filter(np.random.default_rng(seed).normal(size=(n, n)).astype(np.float32), sigma, mode="wrap")
    return a / a.std()


_LO3 = _lowfreq(997, 15, 11)


def _lo3(x0, y0, S):
    n = _LO3.shape[0]
    return _LO3[np.ix_((np.arange(S) + y0).astype(int) % n, (np.arange(S) + x0).astype(int) % n)]


_LO = [_lowfreq(1021, 34, 3), _lowfreq(1531, 52, 5)]  # two large-scale fields with different periods (no visible repeat)


def _lo(x0, y0, S):
    """Large-scale noise (sum of two fields) for world window [x0, x0+S) x [y0, y0+S)."""
    out = 0
    for f in _LO:
        n = f.shape[0]
        out = out + f[np.ix_((np.arange(S) + y0).astype(int) % n, (np.arange(S) + x0).astype(int) % n)]
    return out / math.sqrt(2)

# traffic by road class: (step px along the line, chance a slot is used, vehicles allowed)
TRAFFIC = {
    "motorway": (24, 0.85), "trunk": (24, 0.85), "primary": (22, 0.85), "secondary": (28, 0.75), "tertiary": (34, 0.62),
    "unclassified": (48, 0.45), "residential": (50, 0.42), "living_street": (80, 0.3), "service": (80, 0.3),
}


def _lane_kind(hv, cls):
    r = (hv >> 8) % 100
    big = cls in ("motorway", "trunk", "primary", "secondary")
    if r < 36:
        return "scooter"
    if r < 58:
        return "auto"
    if r < 78:
        return "car"
    if r < 84:
        return "cycle"
    if big and r < 92:
        return "bus"
    if big and r < 97:
        return "truck"
    return "scooter"


class Renderer(V1.Renderer):
    def __init__(self, scene, trees):
        super().__init__(scene, trees)
        self._pts_cache = {}
        self._mon = None
        self._mon_imgs = {}
        # Heights without survey data are footprint-based guesses and read too tall next to the monuments: trim them.
        bg_, bm_ = scene["buildings"]
        scene["buildings"] = (bg_, [((m_[0] if m_[1] else m_[0] * HEIGHT_TRIM),) + tuple(m_[1:]) for m_ in bm_])
        # institutional buildings (colleges, schools, hospitals, the station) get the colonial cream-and-red treatment
        self._classify_institutions(scene, trees)
        # Srirangam island: agraharam streets of small tile-roofed houses between the temple walls
        ax0, ay0 = iso(78.665, 10.882)
        ax1, ay1 = iso(78.722, 10.838)
        self._agr = (min(ax0, ax1), min(ay0, ay1), max(ax0, ax1), max(ay0, ay1))

    def _classify_institutions(self, scene, trees):
        bg_, bm_ = scene["buildings"]
        lg, lm = scene["land_use"]
        want = {("education", "college"): "college", ("education", "university"): "university", ("education", "school"): "school",
                ("medical", "hospital"): "hospital", ("transportation", "railway"): "train_station", ("developed", "works"): None}
        for gi, mi in zip(lg, lm):
            cls = want.get((mi[0], mi[1]))
            if cls is None or gi.area / (K * K) > 600000:
                continue
            for bi in trees["buildings"].query(gi):
                m_ = bm_[bi]
                if m_[2] is not None:
                    continue
                gb = bg_[bi]
                a = gb.area / (K * K)
                if a < 220 or not gi.contains(gb.representative_point()):
                    continue
                if cls == "train_station" and a < 900:
                    continue
                bm_[bi] = (m_[0], m_[1], cls, m_[3], m_[4])

    # ------------------------------------------------------------------------------------- monuments
    def _monuments(self):
        if self._mon is None:
            import monuments
            from shapely import STRtree
            from shapely.geometry import Polygon
            if not monuments.OUT.exists():
                self._mon = dict(parts=[], tree=None, hide=[], hide_tree=None)
            else:
                parts, hide = monuments.load()
                boxes = [box(p["ox"], p["oy"], p["ox"] + p["w"], p["oy"] + p["h"]) for p in parts]
                hp = [Polygon(r) for r in hide]
                self._mon = dict(parts=parts, tree=STRtree(boxes) if boxes else None, hide=hp, hide_tree=STRtree(hp) if hp else None)
        return self._mon

    def _mon_img(self, k, which="rgba"):
        key = (k, which)
        im = self._mon_imgs.get(key)
        if im is None:
            import io
            raw = self._mon["parts"][k][which]
            im = Image.open(io.BytesIO(raw))
            im.load()
            if len(self._mon_imgs) > 900:
                self._mon_imgs.clear()
            self._mon_imgs[key] = im
        return im

    # ------------------------------------------------------------------------------------- line sampling
    def _line_pts(self, i, step):
        key = (i, step)
        if key in self._pts_cache:
            return self._pts_cache[key]
        line = self.scene["road_lines"][0][i]
        L = line.length
        jit = _h(i, "j") % step
        s = np.arange(jit, L, step, dtype=float)
        if len(s) == 0:
            out = (np.zeros((0, 2)), np.zeros((0, 2)), s)
        else:
            p = shapely.line_interpolate_point(line, s)
            q = shapely.line_interpolate_point(line, np.minimum(s + 1.5, L))
            px = np.column_stack([shapely.get_x(p), shapely.get_y(p)])
            dv = np.column_stack([shapely.get_x(q), shapely.get_y(q)]) - px
            nrm = np.hypot(dv[:, 0], dv[:, 1])
            nrm[nrm == 0] = 1
            out = (px, dv / nrm[:, None], s)
        if len(self._pts_cache) > 4000:
            self._pts_cache.clear()
        self._pts_cache[key] = out
        return out

    def _dashes(self, i, period=18, dash=8):
        key = (i, "dash")
        if key in self._pts_cache:
            return self._pts_cache[key]
        line = self.scene["road_lines"][0][i]
        L = line.length
        out = []
        s = 0.0
        while s + dash < L:
            a = shapely.line_interpolate_point(line, s)
            b = shapely.line_interpolate_point(line, s + dash)
            out.append((a.x, a.y, b.x, b.y))
            s += period
        arr = np.array(out, dtype=float).reshape(-1, 4)
        if len(self._pts_cache) > 4000:
            self._pts_cache.clear()
        self._pts_cache[key] = arr
        return arr

    # ------------------------------------------------------------------------------------- the tile
    def render_tile(self, tx, ty, size=TILE, ox=0, oy=0):
        X0, Y0 = tx * TILE + ox, ty * TILE + oy
        S = size + 2 * PAD
        x0, y0 = X0 - PAD, Y0 - PAD
        rect = (x0 - 2, y0 - 2, x0 + S + 2, y0 + S + 2)
        im = Image.new("RGB", (S, S), PAL["ground"])
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

        # ---- land use + cover
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
                if sub == "urban":
                    continue
                fill(g[i], PAL.get(sub, PAL["ground"]))
                if sub == "crop":
                    self._hatch(d, g[i], x0, y0, S, PAL["crop2"])
        smask = self._settled_mask(x0, y0, S)
        if smask is not None:
            im.paste(Image.new("RGB", im.size, PAL["settled"]), (0, 0), smask)
            d = ImageDraw.Draw(im)

        occ = Image.new("L", (S, S), 0)  # where trees must not grow: water, roads, building footprints
        od = ImageDraw.Draw(occ)
        bigw = Image.new("L", (S, S), 0)  # large rivers: get sandbars
        bwd = ImageDraw.Draw(bigw)
        rdm = Image.new("L", (S, S), 0)  # roads and rail (kept clear of sandbars)
        rdd = ImageDraw.Draw(rdm)

        # ---- water: sandy bank, water, foam line
        if "water" in self.scene:
            g, m, idx = self._query("water", rect)
            # one outline for touching/overlapping water polygons, so shared borders leave no pale seam
            uni = shapely.union_all([g[i].buffer(0) for i in idx]) if len(idx) else None
            uni_rings = list(_rings(uni)) if uni is not None and not uni.is_empty else []
            for ext, holes in uni_rings:
                if len(ext) >= 3:
                    pe = P(ext)
                    d.line(pe + [pe[0]], fill=(228, 212, 170), width=6, joint="curve")
                for h in holes:
                    ph = P(h)
                    d.line(ph + [ph[0]], fill=(228, 212, 170), width=6, joint="curve")
            for i in idx:
                for ext, holes in _rings(g[i]):
                    if len(ext) < 3:
                        continue
                    pe = P(ext)
                    d.polygon(pe, fill=PAL["water"])
                    od.polygon(pe, fill=255)
                    if shapely.area(g[i]) > 400000:
                        bwd.polygon(pe, fill=255)
                    for h in holes:
                        ph = P(h)
                        d.polygon(ph, fill=PAL["ground"])
            for ext, holes in uni_rings:
                if len(ext) >= 3:
                    pe = P(ext)
                    d.line(pe + [pe[0]], fill=PAL["water_hi"], width=1)
                    od.line(pe + [pe[0]], fill=255, width=7)
                for h in holes:
                    ph = P(h)
                    d.line(ph + [ph[0]], fill=PAL["water_hi"], width=1)
            self._water_ripples(d, im, x0, y0, S)

        # ---- roads: sidewalk, asphalt, markings; rail
        lines_idx = []
        if "segments" in self.scene:
            g, m, idx = self._query("segments", rect)
            roads = [i for i in idx if m[i][0] == "road"]
            roads.sort(key=lambda i: ROAD_RANK.get(m[i][1], 3))
            for i in roads:
                cls = m[i][1]
                if ROAD_RANK.get(cls, 3) <= 1:
                    continue
                for ext, _ in _rings(g[i]):
                    if len(ext) >= 3:
                        d.polygon(P(ext), fill=CURB, outline=CURB_LINE, width=3)
            for i in roads:
                cls = m[i][1]
                rk = ROAD_RANK.get(cls, 3)
                col = ASPHALT.get(cls, FOOT if rk <= 1 else ASPHALT["unknown"])
                for ext, _ in _rings(g[i]):
                    if len(ext) >= 3:
                        d.polygon(P(ext), fill=col)
                        if rk >= 2:
                            od.polygon(P(ext), fill=255)
                        rdd.polygon(P(ext), fill=255)
            for i in idx:
                if m[i][0] == "rail":
                    for ext, _ in _rings(g[i]):
                        if len(ext) >= 3:
                            d.polygon(P(ext), fill=(150, 140, 126), outline=(112, 104, 98))
                            od.polygon(P(ext), fill=255)
        if "road_lines" in self.scene:
            lg, lm, lidx = self._query("road_lines", rect)
            lines_idx = [int(i) for i in lidx]
            for i in lines_idx:
                kind, cls = lm[i]
                if kind == "rail":
                    # ties and two rails
                    pts, dirs, _ = self._line_pts(i, 6)
                    for (px, py), (dx, dy) in zip(pts, dirs):
                        X, Y = px - x0, py - y0
                        if -4 < X < S + 4 and -4 < Y < S + 4:
                            d.line([(X - dy * 4, Y + dx * 4), (X + dy * 4, Y - dx * 4)], fill=(112, 88, 66))
                    ln = lg[i]
                    for off in (-1.8, 1.8):
                        try:
                            oc = ln.offset_curve(off)
                        except Exception:
                            continue
                        for part in getattr(oc, "geoms", [oc]):
                            if part.geom_type == "LineString" and len(part.coords) > 1:
                                d.line(P(part.coords), fill=(70, 66, 70), width=1)
                elif kind == "road" and cls in ("motorway", "trunk", "primary", "secondary", "tertiary"):
                    arr = self._dashes(i, 18 if cls != "tertiary" else 22, 8)
                    for ax, ay, bx, by in arr:
                        if min(ax, bx) - x0 > S or max(ax, bx) - x0 < 0 or min(ay, by) - y0 > S or max(ay, by) - y0 < 0:
                            continue
                        d.line([(ax - x0, ay - y0), (bx - x0, by - y0)], fill=(236, 232, 214) if cls != "tertiary" else (214, 208, 190))

        # ---- monuments: ground parts, areas where generic clutter is hidden
        mon = self._monuments()
        mparts, hide_u = [], None
        if mon["tree"] is not None:
            mparts = [int(k) for k in mon["tree"].query(box(x0, y0, x0 + S, y0 + S))]
            for k in mparts:
                pt = mon["parts"][k]
                if pt["ground"]:
                    a = self._mon_img(k)
                    im.paste(a, (pt["ox"] - x0, pt["oy"] - y0), a)
            d = ImageDraw.Draw(im)
        if mon["hide_tree"] is not None:
            hh = [mon["hide"][int(k)] for k in mon["hide_tree"].query(box(x0 - 60, y0 - 60, x0 + S + 60, y0 + S + 60))]
            if hh:
                hide_u = shapely.union_all(hh)
                for g in hh:
                    for ext, _ in _rings(g):
                        od.polygon(P(ext), fill=255)

        # ---- building footprints into the occupancy mask
        bg = bm = bidx = None
        if "buildings" in self.scene:
            bg, bm, bidx = self._query("buildings", (rect[0] - 4, rect[1] - 12, rect[2] + 62, rect[3] + MAX_H_PX))
            if hide_u is not None and len(bidx):
                bidx = np.asarray(bidx)[~shapely.contains(hide_u, shapely.centroid(bg[bidx]))]
            for i in bidx:
                ring = bg[i].exterior.coords
                pe = P(ring)
                od.polygon(pe, fill=255)
                od.line(pe, fill=255, width=4)

        occ_a = np.asarray(occ) > 0

        def free(X, Y, r=3):
            for dx, dy in ((0, 0), (r, 0), (-r, 0), (0, r // 2), (0, -r // 2)):
                xx, yy = int(X + dx), int(Y + dy)
                if not (0 <= xx < S and 0 <= yy < S) or occ_a[yy, xx]:
                    return False
            return True

        items = []  # (sort_y, kind, payload)

        # ---- trees in land cover (forest, shrub, grass, wetland)
        self._cover_trees(items, x0, y0, S, free)
        # ---- trees in settled ground: yards and streets
        dens, cell = self.scene["settled"]
        self._settled_trees(items, x0, y0, S, free, dens, cell, lines_idx, lm if "road_lines" in self.scene else None)
        # ---- traffic and pedestrians
        if "road_lines" in self.scene:
            self._traffic(items, x0, y0, S, lines_idx, lg, lm, dens, cell)
        # ---- buildings and landmark sprites
        sprites = []
        for k in mparts:
            pt = mon["parts"][k]
            if not pt["ground"]:
                items.append((pt["y"], "mon", k))
        if bidx is not None and len(bidx):
            ymax = shapely.bounds(bg[bidx])[:, 3]
            for j, i in enumerate(bidx):
                items.append((float(ymax[j]), "bld", int(i)))
                # people and goods in front of shops and houses (anchored to the building hash, so tiles agree)
                hv = _h(int(i))
                cls_i = bm[i][2]
                if cls_i in ("temple", "church", "mosque", "place_of_worship") or bm[i][0] * VK < 6:
                    continue
                if (hv >> 3) % 100 < 42 or hv % 100 < 28:
                    b = bg[i].bounds
                    if (b[2] - b[0]) * (b[3] - b[1]) < 400:
                        continue
                    by_ = float(ymax[j])
                    bx_ = float(bg[i].representative_point().x)
                    rr = np.random.default_rng(hv)
                    for q in range(1 + (hv >> 20) % 3):
                        X = bx_ + float(rr.uniform(-12, 12)) - x0
                        Y = by_ + float(rr.uniform(2, 5)) - y0
                        if (hv >> 22) % 5 == 0 and q == 0:
                            items.append((by_ + 3, "spr", ("stall", X, Y + 2, hv >> 4)))
                        else:
                            items.append((by_ + 3 + q * 0.1, "ped", (X, Y, hv >> (8 + q))))

        if hide_u is not None:
            items = [it for it in items if not (it[1] in ("ped", "veh") and shapely.contains_xy(hide_u, it[2][0] + x0, it[2][1] + y0)) and not (it[1] == "spr" and shapely.contains_xy(hide_u, it[2][1] + x0, it[2][2] + y0))]

        # ---- shadows on the ground
        sh = Image.new("L", (S, S), 0)
        sd = ImageDraw.Draw(sh)
        sx, sy = SHADOW_DIR
        if bidx is not None:
            for i in bidx:
                h = bm[i][0] * VK
                if h < 3:
                    continue
                ring = P(bg[i].exterior.coords)
                dx, dy = sx * h, sy * h
                sd.polygon(ring, fill=255)
                sd.polygon([(x + dx, y + dy) for x, y in ring], fill=255)
                for a in range(len(ring) - 1):
                    (ax, ay), (bx, by) = ring[a], ring[a + 1]
                    sd.polygon([(ax, ay), (bx, by), (bx + dx, by + dy), (ax + dx, ay + dy)], fill=255)
        for _, kind, pl in items:
            if kind == "tree":
                X, Y, seed, tk = pl
                r = 9 if tk not in ("bush", "palm") else 3
                sd.ellipse([X - r * 1.5, Y - 1, X + r * 0.3, Y + r * 0.5], fill=255)
            elif kind == "veh":
                X, Y = pl[0], pl[1]
                sd.ellipse([X - 5, Y - 1, X + 1, Y + 2], fill=255)
            elif kind == "ped":
                X, Y = pl[0], pl[1]
                sd.line([(X, Y), (X - 3, Y + 1)], fill=255)
            elif kind == "spr":
                X, Y = pl[1], pl[2]
                r = {"stall": 5, "cow": 5, "handcart": 5, "parked_scooter": 3, "crowd": 9}.get(pl[0], 3)
                sd.ellipse([X - r * 1.4, Y - 1, X + r * 0.3, Y + r * 0.4], fill=255)
        for k in mparts:
            pt = mon["parts"][k]
            if pt["shadow"] is not None:
                sh.paste(255, (pt["ox"] - x0, pt["oy"] - y0), self._mon_img(k, "shadow"))
        arr = np.asarray(im, dtype=np.float32)
        # fine ground grain, anchored to world pixels
        ix = (np.arange(S) + x0).astype(int) % 256
        iy = (np.arange(S) + y0).astype(int) % 256
        grain = _NOISE[np.ix_(iy, ix)]
        arr *= (1 + 0.022 * grain)[..., None]
        lo = _lo(x0, y0, S)
        arr *= (1 + 0.028 * lo)[..., None]
        # (no noise-driven sandbar blobs in the channel: they read as patches; the sandy bank is the halo drawn with the water)
        m = np.asarray(sh) > 0
        arr[m] *= SHADOW
        im = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(im)

        # ---- painter's algorithm
        items.sort(key=lambda t: t[0])
        for _, kind, pl in items:
            if kind == "bld":
                self._building(d, im, bg[pl], bm[pl], pl, x0, y0)
            elif kind == "tree":
                X, Y, seed, tk = pl
                SP.tree(d, X, Y, seed, tk)
            elif kind == "veh":
                SP.vehicle(d, pl[0], pl[1], pl[2], pl[3], pl[4])
            elif kind == "ped":
                SP.person(d, pl[0], pl[1], pl[2])
            elif kind == "spr":
                getattr(SP, pl[0])(d, pl[1], pl[2], *pl[3:])
            elif kind == "mon":
                a = self._mon_img(pl)
                im.paste(a, (mon["parts"][pl]["ox"] - x0, mon["parts"][pl]["oy"] - y0), a)
        return im.crop((PAD, PAD, PAD + size, PAD + size))

    # ------------------------------------------------------------------------------------- trees
    def _cover_trees(self, items, x0, y0, S, free):
        if "land_cover" not in self.scene:
            return
        g, m, idx = self._query("land_cover", (x0 - 12, y0 - 12, x0 + S + 12, y0 + S + 12))
        polys = [(g[i], m[i]) for i in idx if m[i] in ("forest", "shrub", "grass", "wetland")]
        if not polys:
            return
        cell = 15
        gx0, gy0 = int((x0 - 12) // cell), int((y0 - 12) // cell)
        n = (S + 24) // cell + 2
        pts, hs = [], []
        for gy in range(gy0, gy0 + n):
            for gx in range(gx0, gx0 + n):
                hv = _h(gx, gy, "t")
                pts.append((gx * cell + hv % cell, gy * cell + (hv >> 8) % cell))
                hs.append(hv >> 16)
        arr = np.array(pts, dtype=float)
        rnd = np.array([(k % 1000) / 1000 for k in hs])
        dens = {"forest": 0.9, "shrub": 0.35, "grass": 0.07, "wetland": 0.3}
        ok = np.zeros(len(arr), dtype=bool)
        for geom, sub in polys:
            ok |= shapely.contains_xy(geom, arr[:, 0], arr[:, 1]) & (rnd < dens[sub])
        for j in np.nonzero(ok)[0]:
            X, Y = arr[j][0] - x0, arr[j][1] - y0
            if not free(X, Y, 2):
                continue
            k = hs[j]
            kind = "palm" if k % 9 == 0 else "bush" if k % 5 == 0 else "rain" if k % 7 == 0 else "neem"
            items.append((arr[j][1], "tree", (X, Y - 0, k, kind)))

    def _settled_trees(self, items, x0, y0, S, free, dens, cell, lines_idx, lm):
        def dens_at(wx, wy):
            cx, cy = int(wx // cell), int(wy // cell)
            if 0 <= cy < dens.shape[0] and 0 <= cx < dens.shape[1]:
                return dens[cy, cx]
            return 0.0

        # yard trees on a world grid
        step = 13
        gx0, gy0 = int(x0 // step), int(y0 // step)
        for gy in range(gy0, gy0 + S // step + 2):
            for gx in range(gx0, gx0 + S // step + 2):
                hv = _h(gx, gy, "y")
                wx, wy = gx * step + hv % step, gy * step + (hv >> 6) % step
                dv = dens_at(wx, wy)
                if dv < 0.12:
                    continue
                if ((hv >> 12) % 1000) / 1000 > 0.17 + 0.10 * min(1.0, dv * 3):
                    continue
                X, Y = wx - x0, wy - y0
                if free(X, Y, 3):
                    k = hv >> 14
                    kind = "palm" if k % 8 == 0 else "bush" if k % 4 == 0 else "neem"
                    items.append((wy, "tree", (X, Y, k, kind)))
        # avenue trees along larger roads
        if lm is None:
            return
        for i in lines_idx:
            kind, cls = lm[i]
            if kind != "road" or ROAD_RANK.get(cls, 3) < 4:
                continue
            pts, dirs, s = self._line_pts(i, 24)
            if not len(pts):
                continue
            half = {"primary": 12, "secondary": 10, "trunk": 14, "tertiary": 8}.get(cls, 6) / 2 + 2.6
            for (px, py), (dx, dy), ss in zip(pts, dirs, s):
                X, Y = px - x0, py - y0
                if not (-14 < X < S + 14 and -14 < Y < S + 14):
                    continue
                hv = _h(i, int(ss), "av")
                if hv % 100 > 52 or dens_at(px, py) < 0.15:
                    continue
                am, bm_ = SP.to_m(dx, dy)
                nm = math.hypot(am, bm_) or 1
                am, bm_ = am / nm, bm_ / nm
                side = 1 if (hv >> 8) % 2 else -1
                ox_, oy_ = SP.to_px(-bm_ * half * side, am * half * side)
                TX, TY = X + ox_, Y + oy_
                if 0 <= TX < S and 0 <= TY < S and not free(TX, TY, 2):
                    # allowed on the sidewalk itself, but not on buildings: check a small ring only against buildings
                    pass
                items.append((py + oy_, "tree", (TX, TY, hv >> 12, "rain" if hv % 3 == 0 else "neem")))

    # ------------------------------------------------------------------------------------- traffic
    def _traffic(self, items, x0, y0, S, lines_idx, lg, lm, dens, cell):
        def dens_at(wx, wy):
            cx, cy = int(wx // cell), int(wy // cell)
            if 0 <= cy < dens.shape[0] and 0 <= cx < dens.shape[1]:
                return dens[cy, cx]
            return 0.0

        for i in lines_idx:
            kind, cls = lm[i]
            if kind != "road" or cls not in TRAFFIC:
                if kind == "road" and cls in ("footway", "pedestrian", "path"):
                    pts, dirs, s = self._line_pts(i, 44)
                    for (px, py), ss in zip(pts, s):
                        X, Y = px - x0, py - y0
                        if -6 < X < S + 6 and -6 < Y < S + 6:
                            hv = _h(i, int(ss), "fp")
                            if hv % 100 < 22 and dens_at(px, py) > 0.2:
                                items.append((py, "ped", (X, Y, hv >> 8)))
                continue
            step, p = TRAFFIC[cls]
            wide = {"motorway": 16, "trunk": 14, "primary": 12, "secondary": 10, "tertiary": 8}.get(cls, 6)
            pts, dirs, s = self._line_pts(i, step)
            if len(pts):
                dn = np.array([dens_at(px, py) for px, py in pts])
            for n_, ((px, py), (dx, dy), ss) in enumerate(zip(pts, dirs, s)):
                X, Y = px - x0, py - y0
                if not (-14 < X < S + 14 and -18 < Y < S + 14):
                    continue
                hv = _h(i, int(ss), "v")
                if (hv % 1000) / 1000 > p * (0.35 + min(1.0, dn[n_] * 3.0)):
                    continue
                am, bm_ = SP.to_m(dx, dy)
                theta = math.atan2(bm_, am)
                if (hv >> 10) % 2:   # other lane, other direction (traffic keeps left)
                    theta += math.pi
                nl = (-math.sin(theta), math.cos(theta))
                off = wide / 4.0
                ox_, oy_ = SP.to_px(nl[0] * off, nl[1] * off)
                vk = _lane_kind(hv, cls)
                if BAKE_VEHICLES:
                    items.append((py + oy_, "veh", (X + ox_, Y + oy_, theta, vk, hv >> 4)))
            # pedestrians, stalls, parked scooters, carts and cows along the kerb
            if cls in ("primary", "secondary", "tertiary", "unclassified", "residential"):
                pts, dirs, s = self._line_pts(i, 26)
                for (px, py), (dx, dy), ss in zip(pts, dirs, s):
                    X, Y = px - x0, py - y0
                    if not (-12 < X < S + 12 and -16 < Y < S + 8):
                        continue
                    hv = _h(i, int(ss), "pd")
                    dv = dens_at(px, py)
                    if dv < 0.04:
                        continue
                    am, bm_ = SP.to_m(dx, dy)
                    nm = math.hypot(am, bm_) or 1
                    side = 1 if (hv >> 9) % 2 else -1
                    off = wide / 2 + 0.9
                    ox_, oy_ = SP.to_px(-bm_ / nm * off * side, am / nm * off * side)
                    r100 = hv % 100
                    comm = cls in ("primary", "secondary", "tertiary")
                    if r100 < 40:
                        items.append((py + oy_, "ped", (X + ox_, Y + oy_, hv >> 8)))
                    elif r100 < 48 and comm and dv > 0.2:
                        items.append((py + oy_, "spr", ("crowd", X + ox_, Y + oy_, hv >> 8, 3 + (hv >> 20) % 3, 10)))
                    elif r100 < 56 and comm and dv > 0.15:
                        o2x, o2y = SP.to_px(-bm_ / nm * (off + 1.6) * side, am / nm * (off + 1.6) * side)
                        items.append((py + o2y, "spr", ("stall", X + o2x, Y + o2y, hv >> 8)))
                    elif r100 < 70:
                        items.append((py + oy_, "spr", ("parked_scooter", X + ox_, Y + oy_, hv >> 8)))
                    elif r100 < 74:
                        items.append((py + oy_, "spr", ("handcart", X + ox_, Y + oy_, hv >> 8)))
                    elif r100 < 77 and not comm:
                        items.append((py + oy_, "spr", ("cow", X + ox_, Y + oy_, hv >> 8)))

    # ------------------------------------------------------------------------------------- buildings
    def _building(self, d, im, geom, meta, i, x0, y0):
        h, known, cls, name, roof_shape = meta
        hp = h * VK
        hv = _h(i)
        sacred = cls in ("temple", "church", "mosque", "place_of_worship")
        area_geo = geom.area / (K * K)
        if area_geo > 2000 and not known:
            h = min(h, 14.0)
            if sacred or area_geo > 6000:
                h = min(h, 6.0)
            hp = h * VK
        heritage = cls in HERITAGE and not sacred
        if heritage and not known and area_geo > 300:
            h = max(h, 12.0 if area_geo < 6000 else 10.0)
            hp = h * VK
        self._heritage = heritage
        wall = WALL_SETS[hv % len(WALL_SETS)][0]
        gb = geom.bounds
        agr = (self._agr[0] < (gb[0] + gb[2]) / 2 < self._agr[2] and self._agr[1] < (gb[1] + gb[3]) / 2 < self._agr[3]
               and not sacred and not heritage and area_geo < 320)
        if agr:
            wall = ((236, 214, 160), (244, 232, 204), (232, 176, 124), (240, 222, 178))[hv % 4]
        if heritage:
            wall = (240, 222, 188)
        if sacred:
            wall = (240, 226, 200)
        ring = list(geom.exterior.coords)[:-1]
        n = len(ring)
        if n < 3:
            return
        xs = np.array([p[0] for p in ring])
        ys = np.array([p[1] for p in ring])
        area2 = float(np.sum(xs * np.roll(ys, -1) - np.roll(xs, -1) * ys))
        sgn = 1.0 if area2 > 0 else -1.0
        area_px = abs(area2) / 2
        area_m2 = area_px / (K * K)
        faces = []
        for a in range(n):
            p0, p1 = ring[a], ring[(a + 1) % n]
            dx, dy = p1[0] - p0[0], p1[1] - p0[1]
            nx, ny = dy * sgn, -dx * sgn
            if ny > 1e-6:
                faces.append((p0, p1, nx / (math.hypot(nx, ny) + 1e-9)))

        # pitched roof for small, simple houses
        pitched = None
        if area_m2 < (300 if agr else 130) and h < (9.5 if agr else 8.5) and n <= 8 and not sacred and (hv >> 9) % 100 < (88 if agr else 62):
            rr = shapely.minimum_rotated_rectangle(geom)
            if rr.geom_type == "Polygon" and rr.area > 0 and geom.area / rr.area > 0.86:
                pitched = list(rr.exterior.coords)[:-1]
        outline_c = _shade(wall, 0.55)
        for p0, p1, nxn in faces:
            shade = 0.78 if nxn < 0 else 1.0
            quad = [(p0[0] - x0, p0[1] - y0), (p1[0] - x0, p1[1] - y0), (p1[0] - x0, p1[1] - y0 - hp), (p0[0] - x0, p0[1] - y0 - hp)]
            d.polygon(quad, fill=_shade(wall, shade), outline=_shade(outline_c, shade))
            self._face_detail(d, p0, p1, h, hp, shade, hv, wall, x0, y0, sacred)

        if pitched is not None:
            self._pitched_roof(d, pitched, hp, wall, hv, x0, y0, faces)
            return
        # flat roof, with a parapet and texture
        huge = area_geo > 1500
        base = (214, 194, 152) if (sacred or (huge and not known and h <= 6)) else \
            ROOF_TILE[(hv >> 5) % len(ROOF_TILE)] if (hv >> 5) % 100 < 20 and h < 9 and not huge else \
            ROOF_TIN[(hv >> 5) % len(ROOF_TIN)] if (hv >> 5) % 100 < 35 and h < 7 and not huge else \
            ROOF_FLAT[(hv >> 5) % len(ROOF_FLAT)]
        pts = [(x - x0, y - y0 - hp) for x, y in ring]
        d.polygon(pts, fill=_shade(base, 0.82), outline=_shade(base, 0.55))
        inner = geom.buffer(-1.6, join_style=2)
        if not inner.is_empty and inner.geom_type == "Polygon" and area_px > 60:
            ip = [(x - x0, y - y0 - hp) for x, y in inner.exterior.coords]
            d.polygon(ip, fill=base)
            if area_px > 90:
                self._roof_texture(im, ip, base, hv, base in ROOF_TILE, base in ROOF_TIN, x0, y0)
            if heritage and cls in TOWER_CLS and area_m2 > 900:
                rp = inner.representative_point()
                self._clock_tower(d, rp.x - x0, rp.y - hp - y0, wall, hv)
            else:
                self._roof_props(d, inner, hp, h, hv, x0, y0, area_m2)

    def _clock_tower(self, d, X, Y, wall, hv):
        """Colonial clock tower on the roof of stations, colleges and civic buildings."""
        w, th = 6, 22
        S = [(X - w, Y), (X + w, Y - 3), (X + w, Y - 3 - th), (X - w, Y - th)]
        W = [(X - w, Y), (X - w, Y - th), (X - w - 5, Y - th - 3), (X - w - 5, Y - 3)]
        d.polygon([(X - w, Y + 3), (X + w, Y), (X + w, Y - th), (X - w, Y - th + 3)], fill=_shade(wall, 1.0), outline=_shade(wall, 0.55))
        d.polygon([(X - w, Y + 3), (X - w - 5, Y + 1), (X - w - 5, Y - th - 2), (X - w, Y - th + 3)], fill=_shade(wall, 0.75), outline=_shade(wall, 0.5))
        cx, cy = X, Y - th + 7
        d.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], fill=(250, 246, 232), outline=(80, 60, 52))
        d.line([(cx, cy), (cx, cy - 3)], fill=(40, 36, 40)); d.line([(cx, cy), (cx + 2, cy + 1)], fill=(40, 36, 40))
        d.polygon([(X - w - 1, Y - th + 3), (X + w + 1, Y - th), (X + w + 1, Y - th - 2), (X - w - 1, Y - th + 1)], fill=(196, 84, 62))
        apex = (X - 2, Y - th - 14)
        d.polygon([(X - w - 1, Y - th + 3), (X + w + 1, Y - th), apex], fill=(176, 80, 62), outline=(110, 52, 42))
        d.polygon([(X - w - 1, Y - th + 3), (X - w - 5, Y - th + 1), apex], fill=(138, 64, 50), outline=(110, 52, 42))
        d.line([apex, (apex[0], apex[1] - 4)], fill=(236, 190, 70))

    def _roof_texture(self, im, ip, base, hv, tile, tin, x0, y0):
        xs = [p[0] for p in ip]
        ys = [p[1] for p in ip]
        bx0, by0 = int(max(0, min(xs))), int(max(0, min(ys)))
        bx1, by1 = int(min(im.width, max(xs) + 1)), int(min(im.height, max(ys) + 1))
        w, h = bx1 - bx0, by1 - by0
        if w < 4 or h < 4 or w * h > 120000:
            return
        m = Image.new("L", (w, h), 0)
        ImageDraw.Draw(m).polygon([(x - bx0, y - by0) for x, y in ip], fill=255)
        yy, xx = np.mgrid[0:h, 0:w]
        gx, gy = (xx + bx0 + int(x0)) + (hv % 17), (yy + by0 + int(y0)) + ((hv >> 4) % 13)
        col = np.zeros((h, w, 3), dtype=np.float32) + np.array(base, dtype=np.float32)
        if tile:
            col *= np.where(((2 * gy + gx) % 6) < 1, 0.8, 1.0)[..., None]
        elif tin:
            col *= np.where(((2 * gy - gx) % 9) < 1, 1.12, 1.0)[..., None]
        else:
            col *= (1 + 0.035 * _NOISE[gy % 256, gx % 256])[..., None]
            col *= np.where((((2 * gy + gx) % 40) < 1) | (((2 * gy - gx) % 40) < 1), 0.93, 1.0)[..., None]
            stain = _NOISE[(gy // 5 + 31) % 256, (gx // 5 + 17) % 256] > 1.25
            col[stain] *= 0.9
        tex = Image.fromarray(np.clip(col, 0, 255).astype(np.uint8))
        im.paste(tex, (bx0, by0), m)

    def _roof_props(self, d, inner, hp, h, hv, x0, y0, area_m2):
        """Rooftop life: water tanks, stair-heads and sheds, washing lines, dishes, AC units, plants, solar panels."""
        if h < 5 or area_m2 < 24:
            return
        rng = np.random.default_rng(hv)
        minx, miny, maxx, maxy = inner.bounds
        n = int(min(9, 2 + area_m2 // 55))
        safe = inner.buffer(-3)
        placed = []
        for _ in range(n * 5):
            if len(placed) >= n:
                break
            px, py = float(rng.uniform(minx, maxx)), float(rng.uniform(miny, maxy))
            if not shapely.contains_xy(safe, px, py):
                continue
            if any(abs(px - a) < 10 and abs(py - b) < 8 for a, b, _ in placed):
                continue
            placed.append((px, py, int(rng.integers(0, 1 << 20))))
        order = sorted(placed, key=lambda t: t[1])
        for j, (px, py, k) in enumerate(order):
            X, Y = px - x0, py - hp - y0
            kind = k % 11
            if kind <= 3:           # polyethylene water tank on a plinth (black, blue, white)
                col = [(38, 46, 62), (46, 78, 128), (230, 230, 224), (38, 46, 62), (60, 96, 150)][(k >> 4) % 5]
                d.rectangle([X - 4, Y - 3, X + 3, Y + 1], fill=_shade(col, 0.85), outline=_shade(col, 0.55))
                d.ellipse([X - 4, Y - 7, X + 3, Y - 2], fill=_shade(col, 1.25), outline=_shade(col, 0.65))
                d.line([(X - 3, Y - 4), (X + 1, Y - 4)], fill=_shade(col, 1.6))
                d.line([(X + 2, Y - 3), (X + 2, Y)], fill=_shade(col, 0.55))
            elif kind == 4:         # stair-head
                SP.prism(d, X, Y, 3.6, 2.8, 0, 0, 2.6, (232, 222, 202), (200, 194, 184))
                d.rectangle([X - 1, Y - 1, X, Y + 1], fill=(70, 56, 52))
            elif kind == 5:         # tin shed
                SP.roof_shed(d, X, Y, k >> 5)
            elif kind == 6 and area_m2 > 50:   # washing line
                SP.laundry(d, X - 6, Y + 1, k >> 5, n=5 + (k >> 9) % 3)
            elif kind == 7:
                SP.dish(d, X, Y)
            elif kind == 8:
                SP.ac_unit(d, X, Y)
                SP.ac_unit(d, X + 4, Y - 2)
            elif kind == 9:
                SP.plant_pot(d, X, Y, k >> 5)
                SP.plant_pot(d, X + 4, Y - 2, k >> 6)
            else:                   # second tank of another colour
                col = [(46, 78, 128), (38, 46, 62), (232, 232, 226)][(k >> 4) % 3]
                d.rectangle([X - 2, Y - 2, X + 2, Y + 1], fill=_shade(col, 0.85), outline=_shade(col, 0.55))
                d.ellipse([X - 2, Y - 4, X + 2, Y - 1], fill=_shade(col, 1.25), outline=_shade(col, 0.65))
        if area_m2 > 90 and (hv >> 3) % 4 == 0:   # solar panels
            px, py = float(rng.uniform(minx, maxx)), float(rng.uniform(miny, maxy))
            if shapely.contains_xy(inner.buffer(-4), px, py):
                X, Y = px - x0, py - hp - y0
                d.polygon([(X - 5, Y), (X + 1, Y - 3), (X + 5, Y - 1), (X - 1, Y + 2)], fill=(52, 70, 112), outline=(150, 160, 176))
                d.line([(X - 3, Y), (X + 3, Y - 2)], fill=(120, 140, 180))

    def _pitched_roof(self, d, rect_pts, hp, wall, hv, x0, y0, faces):
        c = rect_pts
        e01 = math.hypot(c[1][0] - c[0][0], c[1][1] - c[0][1])
        e12 = math.hypot(c[2][0] - c[1][0], c[2][1] - c[1][1])
        if e01 > e12:
            c = [c[1], c[2], c[3], c[0]]
            e01, e12 = e12, e01
        ma = ((c[0][0] + c[1][0]) / 2, (c[0][1] + c[1][1]) / 2)
        mb = ((c[2][0] + c[3][0]) / 2, (c[2][1] + c[3][1]) / 2)
        rh = min(0.34 * e01, 4.2 * VK)
        up = lambda p, z: (p[0] - x0, p[1] - y0 - z)
        roof = ROOF_TILE[(hv >> 5) % len(ROOF_TILE)] if (hv >> 11) % 3 else ROOF_TIN[(hv >> 5) % len(ROOF_TIN)]
        halves = [([c[1], c[2], mb, ma], (c[1], c[2])), ([c[3], c[0], ma, mb], (c[3], c[0]))]
        # gables on the short edges (c0-c1 at ma, c2-c3 at mb) when they face the viewer
        for (p0, p1, apex) in ((c[0], c[1], ma), (c[2], c[3], mb)):
            dy = p1[1] - p0[1]
            dx = p1[0] - p0[0]
            # visible when the edge's outward side faces down the screen; test using centre
            cx_ = sum(p[0] for p in c) / 4
            cy_ = sum(p[1] for p in c) / 4
            mx_, my_ = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
            if my_ > cy_ + 0.5:
                d.polygon([up(p0, hp), up(p1, hp), up(apex, hp + rh)], fill=_shade(wall, 0.9), outline=_shade(wall, 0.55))
        for quad, _ in halves:
            ridge = quad[2:]
            cxq = sum(p[0] for p in quad) / 4
            cyq = sum(p[1] for p in quad) / 4
            rx = (ridge[0][0] + ridge[1][0]) / 2
            ry = (ridge[0][1] + ridge[1][1]) / 2
            lit = (cxq - rx) > 0 or ((cxq - rx) == 0 and cyq > ry)
            col = _shade(roof, 1.08 if lit else 0.80)
            poly = [up(quad[0], hp), up(quad[1], hp), up(quad[2], hp + rh), up(quad[3], hp + rh)]
            d.polygon(poly, fill=col, outline=_shade(roof, 0.55))
            # tile courses parallel to the ridge
            for t in (0.25, 0.5, 0.75):
                a = (quad[0][0] + (quad[3][0] - quad[0][0]) * t, quad[0][1] + (quad[3][1] - quad[0][1]) * t)
                b = (quad[1][0] + (quad[2][0] - quad[1][0]) * t, quad[1][1] + (quad[2][1] - quad[1][1]) * t)
                d.line([up(a, hp + rh * t), up(b, hp + rh * t)], fill=_shade(col, 0.82))
        d.line([up(ma, hp + rh), up(mb, hp + rh)], fill=_shade(roof, 1.3))

    def _face_detail(self, d, p0, p1, h, hp, shade, hv, wall, x0, y0, sacred):
        """Facade: plinth, floor slabs, cornice, framed windows with sills, shutters, balconies, AC boxes, shopfronts."""
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(dx, dy)
        if L < 5 or h < 3.0:
            return
        ax, ay = p0[0] - x0, p0[1] - y0
        bx, by = p1[0] - x0, p1[1] - y0
        trim = (208, 134, 100) if getattr(self, "_heritage", False) else WALL_SETS[hv % len(WALL_SETS)][1] if not sacred else (250, 240, 214)

        def band(z0, z1, col, u0=0.0, u1=1.0):
            sx0, sy0, sx1, sy1 = ax + dx * u0, ay + dy * u0, ax + dx * u1, ay + dy * u1
            d.polygon([(sx0, sy0 - z0), (sx1, sy1 - z0), (sx1, sy1 - z1), (sx0, sy0 - z1)], fill=_shade(col, shade))

        plinth = 0.8 * VK
        band(0, plinth, _shade(wall, 0.62))
        d.line([(ax, ay - plinth), (bx, by - plinth)], fill=_shade(wall, 0.5 * shade))
        cornice = 0.7 * VK
        band(hp - cornice, hp, trim)
        d.line([(ax, ay - hp + cornice), (bx, by - hp + cornice)], fill=_shade(wall, 0.55 * shade))
        d.line([(ax, ay - 0.5), (bx, by - 0.5)], fill=_shade(wall, 0.5 * shade))
        if sacred:
            return
        # corner pilaster on the left edge
        d.line([(ax, ay - plinth), (ax, ay - hp + cornice)], fill=_shade(trim, 0.86 * shade))
        floors = max(1, int(h // 3.2))
        fh = (h * VK - plinth - cornice) / floors          # floor height in px
        pitch = 6.2                                         # px along the wall between window centres
        nw = max(1, int((L - 3) // pitch))
        shop = h < 13 and ((hv >> 3) % 100) < 42 and L > 9
        glass = GLASS_SETS[(hv >> 6) % len(GLASS_SETS)]
        shutters = (hv >> 9) % 5 == 0
        ac_every = 3 + (hv >> 11) % 3
        for f in range(floors):
            base = plinth + f * fh
            if f > 0:                                       # slab line between floors
                band(base - 0.5, base + 0.4, trim)
            if f == 0 and shop:
                # shopfront: sign band, open bay or roll-down shutter, striped awning
                u0, u1 = 0.1, 0.9
                top = base + fh * 0.86
                col = SIGN[(hv >> 7) % len(SIGN)]
                band(top - 1.6, top, col, u0, u1)                     # signboard
                mid_x = ax + dx * 0.5
                mid_y = ay + dy * 0.5 - top + 0.8
                d.line([(mid_x - 3, mid_y), (mid_x + 3, mid_y + (-0.2 if dy < 0 else 0.2))], fill=(250, 250, 240))
                if (hv >> 12) % 3 == 0:                               # shutter down
                    band(base + 0.4, top - 1.6, (150, 156, 162), u0, u1)
                    for t in range(1, 5):
                        d.line([(ax + dx * u0, ay + dy * u0 - base - t * 0.9), (ax + dx * u1, ay + dy * u1 - base - t * 0.9)], fill=_shade((120, 126, 132), shade))
                else:
                    band(base + 0.4, top - 1.6, (46, 38, 36), u0, u1)
                    steps = max(2, int(L / 3))
                    acol = SHOP[(hv >> 5) % len(SHOP)]
                    for k in range(steps):
                        ua, ub = u0 + (u1 - u0) * k / steps, u0 + (u1 - u0) * (k + 1) / steps
                        c = acol if k % 2 else (244, 240, 228)
                        band(top - 3.6, top - 1.6, c, ua, ub)
                    for k in range(max(2, nw)):                       # goods on display
                        u = u0 + (u1 - u0) * (k + 0.5) / max(2, nw)
                        gx, gy = ax + dx * u, ay + dy * u - base - 1.2
                        d.point((gx, gy), fill=GOODS_C[(hv + k * 5) % len(GOODS_C)])
                        d.point((gx + 1, gy - 1), fill=GOODS_C[(hv + k * 3) % len(GOODS_C)])
                continue
            for j in range(nw):
                u = (j + 0.5) / nw
                du = 1.35 / L
                wa = (ax + dx * (u - du), ay + dy * (u - du))
                wb = (ax + dx * (u + du), ay + dy * (u + du))
                hh = (hv + f * 7 + j * 13) % 13
                z0, z1 = base + fh * 0.3, base + fh * 0.82
                if hh == 12:                                           # blank wall bay
                    continue
                gc = glass if hh > 2 else (252, 226, 140) if hh == 0 else (214, 150, 80)   # lit window, or curtain
                d.polygon([(wa[0] - 0.6, wa[1] - z0 + 0.6), (wb[0] + 0.6, wb[1] - z0 + 0.6), (wb[0] + 0.6, wb[1] - z1 - 0.6), (wa[0] - 0.6, wa[1] - z1 - 0.6)], fill=_shade(trim, 0.92 * shade))   # surround
                d.polygon([(wa[0], wa[1] - z0), (wb[0], wb[1] - z0), (wb[0], wb[1] - z1), (wa[0], wa[1] - z1)], fill=_shade(gc, shade))
                d.line([(wa[0] - 0.6, wa[1] - z0 + 1), (wb[0] + 0.6, wb[1] - z0 + 1)], fill=_shade(trim, 0.7 * shade))   # sill
                if shutters and hh % 2 == 0:
                    sc = SHUTTER[(hv >> 13) % len(SHUTTER)]
                    d.line([(wa[0] - 1, wa[1] - z0), (wa[0] - 1, wa[1] - z1)], fill=_shade(sc, shade))
                    d.line([(wb[0] + 1, wb[1] - z0), (wb[0] + 1, wb[1] - z1)], fill=_shade(sc, shade))
                if hh == 5:                                            # balcony with a rail
                    d.line([(wa[0] - 1.5, wa[1] - base - 0.4), (wb[0] + 1.5, wb[1] - base - 0.4)], fill=_shade(trim, 0.8 * shade))
                    d.line([(wa[0] - 1.5, wa[1] - base - 1.8), (wb[0] + 1.5, wb[1] - base - 1.8)], fill=_shade((70, 64, 62), shade))
                if j % ac_every == 1 and hh in (3, 4, 7):              # AC unit below the window
                    cx, cy = (wa[0] + wb[0]) / 2, (wa[1] + wb[1]) / 2 - z0 + 1.6
                    d.rectangle([cx - 1, cy, cx + 1, cy + 1], fill=_shade((228, 228, 224), shade), outline=_shade((120, 120, 120), shade))
