"""Hand-built monuments for Pixel Trichy, baked once into small sprites (data/monuments.pkl) that the tile renderer pastes
in painter order with everything else.

  .venv/bin/python pipeline/monuments.py            # bake all
  .venv/bin/python pipeline/monuments.py preview srirangam   # /tmp/mon_<name>.png of one monument

Shapes of the Rock, Teppakulam and the stadium follow real Overture polygons. The temple compounds use positions of the
real gopurams and streets (from Overture buildings and roads) and typical proportions. Heights are stylised.
"""
from __future__ import annotations
import sys, io, pickle, math
import numpy as np
import duckdb, shapely
from shapely import wkb
from shapely.geometry import Polygon, Point, box as sbox
from shapely.affinity import translate
from PIL import Image, ImageDraw
from scipy import ndimage

from config import DATA, K, VK, to_metres, iso_from_metres
from art3d import Canvas, shade, mix, fp, frect, flen, fhgt
import temples as T
import sprites as SP
from shapely.ops import unary_union

OUT = DATA / "monuments.pkl"
PARTS: list[dict] = []
HIDE: list[list[tuple[float, float]]] = []   # px rings: generic buildings, trees and vehicles are removed inside
SEG = 44.8                                    # wall pieces are baked in multiples of 6.4 m so the stripes line up


def m(lat, lon):
    return to_metres(lon, lat)


# ------------------------------------------------------------------------------------------------ baking helpers
def part(name, foot, zmax, fn, ground=False, y=None):
    cv = Canvas(foot, zmax)
    fn(cv)
    im, sh = cv.bake()
    bb = im.getchannel("A").getbbox()
    sbb = sh.getbbox()
    boxes = [b for b in (bb, sbb) if b]
    if not boxes:
        return
    x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes); x1 = max(b[2] for b in boxes); y1 = max(b[3] for b in boxes)
    im = im.crop((x0, y0, x1, y1)); sh = sh.crop((x0, y0, x1, y1))

    def png(i):
        b = io.BytesIO(); i.save(b, "PNG", optimize=True); return b.getvalue()
    PARTS.append(dict(name=name, ox=cv.ox + x0, oy=cv.oy + y0, w=x1 - x0, h=y1 - y0, y=-1e9 if ground else (cv.ymax if y is None else y),
                      ground=ground, rgba=png(im), shadow=png(sh) if sbb else None))


def hide_rect(x0, y0, x1, y1):
    HIDE.append([iso_from_metres(x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))])


def hide_poly(poly_m, buf=0.0):
    p = Polygon(poly_m).buffer(buf)
    HIDE.append([iso_from_metres(x, y) for x, y in p.exterior.coords])


def _pieces(a, b, step=SEG):
    out, s = [], a
    while s < b - 1e-6:
        out.append((s, min(b, s + step)))
        s += step
    return out


def wall_parts(name, x0, y0, x1, y1, h, thick, gates, col=T.LIME):
    """Enclosure wall as many small sprites."""
    def segs(a0, a1, gaps):
        out, cur = [], a0
        for c, g in sorted(gaps):
            if c - g > cur:
                out.append((cur, c - g))
            cur = max(cur, c + g)
        if cur < a1:
            out.append((cur, a1))
        return out

    def one(ax0, ay0, ax1, ay1):
        part(name, (ax0, ay0, ax1, ay1), h + 4, lambda cv: T.stripe_wall(cv, ax0, ay0, ax1, ay1, h, col))
    for a, b in segs(x0, x1, gates.get("s", [])):
        for p, q in _pieces(a, b):
            one(p, y0, q, y0 + thick)
    for a, b in segs(x0, x1, gates.get("n", [])):
        for p, q in _pieces(a, b):
            one(p, y1 - thick, q, y1)
    for a, b in segs(y0 + thick, y1 - thick, gates.get("w", [])):
        for p, q in _pieces(a, b):
            one(x0, p, x0 + thick, q)
    for a, b in segs(y0 + thick, y1 - thick, gates.get("e", [])):
        for p, q in _pieces(a, b):
            one(x1 - thick, p, x1, q)


GOPURAM_SCALE = 1.22   # hero-card exaggeration: gateways stand taller and broader than survey proportions


def gopuram_part(name, cx, cy, L, Tt, H, n, axis, pal, seed=0, stub=False):
    L, Tt, H = L * GOPURAM_SCALE, Tt * GOPURAM_SCALE, H * (GOPURAM_SCALE if not stub else 1.0)
    W, D = (L, Tt) if axis == "ns" else (Tt, L)
    foot = (cx - W / 2, cy - D / 2, cx + W / 2, cy + D / 2)
    part(name, foot, H + 14, lambda cv: T.gopuram(cv, cx, cy, L, Tt, H, n, axis, pal, seed, stub=stub))


def compound(name, c, rings, pal, pave=None, hide=None, wall_h=6.0, life=None):
    """Concentric or irregular rectangular enclosures with gopurams on their gates.
    c = (x, y) centre in metres. Each ring: dict(x0,x1,y0,y1 offsets from c, wh, gates={'s'|'n'|'e'|'w': dict(L,T,H,n,stub,off)})."""
    cx, cy = c
    for ri, r in enumerate(rings):
        x0, x1, y0, y1 = cx + r["x0"], cx + r["x1"], cy + r["y0"], cy + r["y1"]
        gaps = {"s": [], "n": [], "e": [], "w": []}
        for side, g in r.get("gates", {}).items():
            L, Tt, H, n = g["L"], g["T"], g["H"], g["n"]
            off = g.get("off", 0.0)
            if side in "sn":
                gx = (x0 + x1) / 2 + off
                gy = y0 + Tt / 2 + 0.5 if side == "s" else y1 - Tt / 2 - 0.5
                gaps[side].append((gx, L / 2 + 0.5))
                gopuram_part(f"{name}-g{ri}{side}", gx, gy, L, Tt, H, n, "ns", g.get("pal", pal), seed=ri * 7 + ord(side), stub=g.get("stub", False))
            else:
                gy = (y0 + y1) / 2 + off
                gx = x0 + Tt / 2 + 0.5 if side == "w" else x1 - Tt / 2 - 0.5
                gaps[side].append((gy, L / 2 + 0.5))
                gopuram_part(f"{name}-g{ri}{side}", gx, gy, L, Tt, H, n, "ew", g.get("pal", pal), seed=ri * 7 + ord(side), stub=g.get("stub", False))
        wall_parts(f"{name}-w{ri}", x0, y0, x1, y1, r.get("wh", wall_h), r.get("thick", 3.5), gaps, r.get("col", T.LIME))
    if pave:
        px0, px1, py0, py1 = pave
        part(f"{name}-pave", (cx + px0, cy + py0, cx + px1, cy + py1), 1,
             lambda cv: cv.ground([(cx + px0, cy + py0), (cx + px1, cy + py0), (cx + px1, cy + py1), (cx + px0, cy + py1)], (224, 198, 146)), ground=True)
    if hide:
        hide_rect(cx + hide[0], cy + hide[2], cx + hide[1], cy + hide[3])
    if life is not None and pave:
        px0, px1, py0, py1 = pave
        avoid = list(life.get("avoid", []))
        for r in rings:
            rr = sbox(cx + r["x0"], cy + r["y0"], cx + r["x1"], cy + r["y1"])
            avoid.append(rr.exterior.buffer(life.get('wall_buf', 4.5)))
            for side, g in r.get("gates", {}).items():
                L = g["L"] * 1.3 + 4; Tt = g["T"] * 1.3 + 8
                if side in "sn":
                    gx = (rr.bounds[0] + rr.bounds[2]) / 2 + g.get("off", 0.0); gy = rr.bounds[1] if side == "s" else rr.bounds[3]
                    avoid.append(sbox(gx - L / 2, gy - Tt / 2, gx + L / 2, gy + Tt / 2))
                else:
                    gy = (rr.bounds[1] + rr.bounds[3]) / 2 + g.get("off", 0.0); gx = rr.bounds[0] if side == "w" else rr.bounds[2]
                    avoid.append(sbox(gx - Tt / 2, gy - L / 2, gx + Tt / 2, gy + L / 2))
        kw = {k: v for k, v in life.items() if k not in ("avoid", "wall_buf")}
        scatter_life(name, sbox(cx + px0, cy + py0, cx + px1, cy + py1), avoid, ord(name[0]) * 31 + len(name), **kw)


# ------------------------------------------------------------------------------------------------ street life
def life(name, rect, seed, people=8, stalls=1, autos=0, cows=0, trees=0, scooters=0, spread=1.0, z=0.0, y=None):
    """A small sprite of a crowd, market stalls and a few vehicles standing on the ground inside rect (metres)."""
    x0, y0, x1, y1 = rect
    rng = np.random.default_rng(seed)

    def draw(cv):
        items = []
        for _ in range(stalls):
            items.append(("stall", float(rng.uniform(x0, x1)), float(rng.uniform(y0, y1)), int(rng.integers(0, 1 << 20))))
        for _ in range(autos):
            items.append(("auto", float(rng.uniform(x0, x1)), float(rng.uniform(y0, y1)), int(rng.integers(0, 1 << 20))))
        for _ in range(cows):
            items.append(("cow", float(rng.uniform(x0, x1)), float(rng.uniform(y0, y1)), int(rng.integers(0, 1 << 20))))
        for _ in range(scooters):
            items.append(("scooter", float(rng.uniform(x0, x1)), float(rng.uniform(y0, y1)), int(rng.integers(0, 1 << 20))))
        for _ in range(trees):
            items.append(("tree", float(rng.uniform(x0, x1)), float(rng.uniform(y0, y1)), int(rng.integers(0, 1 << 20))))
        for k in range(people):
            cxm = float(rng.uniform(x0, x1)); cym = float(rng.uniform(y0, y1))
            items.append(("person", cxm, cym, int(rng.integers(0, 1 << 20))))
        items.sort(key=lambda t: -(t[1] + t[2]))
        d = cv.d
        for kind, x, y, sd in items:
            X, Y = cv.P(x, y, z)
            cv.sd.ellipse([X - 5, Y - 1, X + 1, Y + 3], fill=255)
            if kind == "person":
                SP.person(cv.d, X, Y, sd)
            elif kind == "stall":
                SP.scaled(SP.stall, cv.im, X, Y, 1.8, sd)
            elif kind == "auto":
                SP.scaled(SP.vehicle, cv.im, X, Y, 1.4, float(sd % 628) / 100.0, "auto", sd)
            elif kind == "scooter":
                SP.parked_scooter(d, X, Y, sd)
            elif kind == "cow":
                SP.cow(d, X, Y, sd)
            elif kind == "tree":
                SP.tree(d, X, Y, sd, ("neem", "palm", "rain")[sd % 3])
    part(name, rect, 14 + z, draw, y=y)


def scatter_life(name, area, avoid, seed, cell=17.0, p=0.7, people=(3, 8), stalls_p=0.25, autos_p=0.07, cows_p=0.04, trees_p=0.06, scooters_p=0.1, z=0.0, y=None):
    """Fill a metre-space polygon with life cells, skipping cells that touch the shapes in avoid."""
    rng = np.random.default_rng(seed)
    bad = unary_union([a for a in avoid]) if avoid else None
    x0, y0, x1, y1 = area.bounds
    n = 0
    gx = x0
    while gx < x1:
        gy = y0
        while gy < y1:
            c = sbox(gx, gy, gx + cell, gy + cell)
            gy += cell
            if not area.contains(c.centroid) or (bad is not None and bad.intersects(c)) or rng.random() > p:
                continue
            m_ = c.buffer(-min(2.5, cell * 0.22)).bounds
            lo, hi = people
            life(f"{name}-life{n}", m_, int(rng.integers(0, 1 << 30)), people=int(rng.integers(lo, hi + 1)),
                 stalls=int(rng.random() < stalls_p), autos=int(rng.random() < autos_p), cows=int(rng.random() < cows_p),
                 trees=int(rng.random() < trees_p), scooters=int(rng.random() < scooters_p), z=z, y=y)
            n += 1
        gx += cell
    return n


# ------------------------------------------------------------------------------------------------ real polygons
def _geoms(table, where):
    con = duckdb.connect(); con.execute("INSTALL spatial; LOAD spatial")
    rows = con.execute(f"select ST_AsWKB(geometry), names.primary, subtype, class from '{DATA}/raw/{table}.parquet' where {where}").fetchall()
    out = []
    for w, n, s, c in rows:
        g = wkb.loads(bytes(w))
        gm = shapely.transform(g, lambda a: np.column_stack(to_metres(a[:, 0], a[:, 1])))
        out.append((gm, n, s, c))
    return out


# ------------------------------------------------------------------------------------------------ monuments
def srirangam():
    cx, cy = m(10.8611, 78.6899)
    cy = 3030.0
    cx = -2208.0
    hx = [395, 352, 312, 241, 183, 125, 72]
    hy = [542, 452, 371, 295, 204, 150, 92]
    Ls = [48, 40, 36, 32, 28, 24, 20]
    Hs = [73, 34, 42, 38, 34, 30, 26]
    ns = [11, 7, 9, 8, 7, 6, 5]
    rings = []
    for i in range(7):
        gt = {}
        for side in "snew":
            L, Tt, H, n = Ls[i], Ls[i] * 0.66, Hs[i], ns[i]
            stub = False
            if i == 0 and side != "s":
                H, n, stub = 24, 2, True
            elif side in "ew" and i in (1, 2):
                H = H * 0.85
            g = dict(L=L, T=Tt, H=H, n=n, stub=stub)
            if i == 0 and side == "s":
                g.update(L=50, T=36)
            gt[side] = g
        rings.append(dict(x0=-hx[i], x1=hx[i], y0=-hy[i], y1=hy[i], wh=6 if i < 4 else 7, gates=gt, thick=4 if i < 4 else 3.5))
    compound("srirangam", (cx, cy), rings, T.PAL_CLASSIC, pave=(-186, 186, -208, 208), hide=(-190, 190, -212, 212))
    # the sanctum: golden Pranavakara vimanam and the halls around it
    c0 = (cx, cy)
    foot = (cx - 10, cy - 10, cx + 10, cy + 10)
    part("srirangam-vimanam", (cx - 14, cy - 14, cx + 14, cy + 14), 56, lambda cv: T.vimanam(cv, cx, cy, 26, 40, 5))
    halls = [(-150, 36, -118, 84, 7), (122, -80, 154, -30, 7), (-30, 108, 30, 126, 6), (-30, -140, 30, -120, 6),
             (100, 40, 150, 70, 6), (-160, -150, -130, -110, 5), (120, -170, 160, -146, 5), (-30, -64, 30, -48, 5),
             (-100, -40, -78, 10, 6), (84, 100, 120, 130, 5), (-170, 90, -150, 140, 5)]
    for i, (ax0, ay0, ax1, ay1, hh) in enumerate(halls):
        f = (cx + ax0, cy + ay0, cx + ax1, cy + ay1)
        part(f"srirangam-hall{i}", f, hh + 8, lambda cv, f=f, hh=hh: T.hall(cv, *f, hh))
    # small shrine towers inside the inner court
    for i, (ox, oy) in enumerate([(-45, -30), (45, 40), (-40, 45), (42, -35)]):
        part(f"srirangam-shrine{i}", (cx + ox - 5, cy + oy - 5, cx + ox + 5, cy + oy + 5), 22,
             lambda cv, ox=ox, oy=oy: T.vimanam(cv, cx + ox, cy + oy, 9, 15, 3))
    # crowds, stalls, auto-rickshaws and trees fill the courtyards (hero-card density)
    avoid = [sbox(cx + a - 3, cy + b - 3, cx + c + 3, cy + d_ + 3) for a, b, c, d_, _ in halls]
    avoid.append(sbox(cx - 22, cy - 22, cx + 22, cy + 22))
    for ox, oy in [(-45, -30), (45, 40), (-40, 45), (42, -35)]:
        avoid.append(sbox(cx + ox - 8, cy + oy - 8, cx + ox + 8, cy + oy + 8))
    for i in (4, 5, 6):
        rr = sbox(cx - hx[i], cy - hy[i], cx + hx[i], cy + hy[i])
        avoid.append(rr.exterior.buffer(5))
        for gxm, gym, w, dd in ((0, -hy[i], Ls[i] * 1.3, 26), (0, hy[i], Ls[i] * 1.3, 26), (-hx[i], 0, 26, Ls[i] * 1.3), (hx[i], 0, 26, Ls[i] * 1.3)):
            avoid.append(sbox(cx + gxm - w / 2, cy + gym - dd / 2, cx + gxm + w / 2, cy + gym + dd / 2))
    scatter_life("srirangam", sbox(cx - 183, cy - 204, cx + 183, cy + 204), avoid, 41, cell=16, p=0.8, people=(4, 10), stalls_p=0.35, autos_p=0.1, trees_p=0.08)


def jambukeswarar():
    # real gopurams stand at lon 78.70315, 78.70399, 78.70664, 78.70778 on the axis lat 10.8530: the temple faces west
    cx, cy = m(10.8530, 78.7055)
    ex = m(10.8530, 78.70778)[0] - cx
    wx = m(10.8530, 78.70315)[0] - cx
    w2 = m(10.8530, 78.70399)[0] - cx
    e2 = m(10.8530, 78.70664)[0] - cx
    rings = [
        dict(x0=wx - 4, x1=ex + 4, y0=-125, y1=125, wh=6, thick=4, gates={"w": dict(L=44, T=30, H=44, n=7), "e": dict(L=40, T=26, H=24, n=3, stub=True)}),
        dict(x0=w2 - 3, x1=e2 + 3, y0=-85, y1=85, wh=6, thick=3.5, gates={"w": dict(L=32, T=22, H=34, n=7), "e": dict(L=30, T=20, H=28, n=5)}),
        dict(x0=w2 + 40, x1=e2 - 30, y0=-50, y1=50, wh=6, thick=3, gates={"w": dict(L=22, T=15, H=24, n=5), "e": dict(L=22, T=15, H=22, n=5)}),
    ]
    compound("jambu", (cx, cy), rings, T.PAL_CLASSIC, pave=(w2 + 20, e2 - 10, -70, 70), hide=(w2 + 10, e2 + 10, -80, 80),
             life=dict(avoid=[sbox(cx + 20, cy - 18, cx + 44, cy + 18), sbox(cx + 46, cy - 28, cx + 104, cy + 28)], cell=15, p=0.8, people=(3, 8), stalls_p=0.3, autos_p=0.06, trees_p=0.07))
    part("jambu-vimanam", (cx + 18, cy - 12, cx + 42, cy + 12), 44, lambda cv: T.vimanam(cv, cx + 30, cy, 20, 28, 4))
    f = (cx + 50, cy - 25, cx + 100, cy + 25)
    part("jambu-hall", f, 16, lambda cv: T.hall(cv, *f, 8))


def samayapuram():
    cx, cy = m(10.91845, 78.73905)
    rings = [
        dict(x0=-62, x1=62, y0=-48, y1=48, wh=6, thick=3.5, gates={"e": dict(L=36, T=24, H=44, n=7, pal=T.PAL_BRIGHT), "w": dict(L=22, T=15, H=22, n=5, pal=T.PAL_BRIGHT),
                                                                       "n": dict(L=18, T=12, H=18, n=3, pal=T.PAL_BRIGHT)}),
        dict(x0=-36, x1=34, y0=-28, y1=28, wh=6, thick=3, gates={"e": dict(L=18, T=12, H=20, n=5, pal=T.PAL_BRIGHT), "w": dict(L=16, T=11, H=16, n=3, pal=T.PAL_BRIGHT)}),
    ]
    compound("samay", (cx, cy), rings, T.PAL_BRIGHT, pave=(-60, 60, -46, 46), hide=(-68, 68, -54, 54),
             life=dict(avoid=[sbox(cx - 22, cy - 12, cx, cy + 12), sbox(cx + 4, cy - 16, cx + 32, cy + 16)], cell=9, wall_buf=3, p=0.9, people=(2, 6), stalls_p=0.4, autos_p=0.05, trees_p=0.05))
    part("samay-vimanam", (cx - 14, cy - 8, cx + 2, cy + 8), 34, lambda cv: T.vimanam(cv, cx - 6, cy, 14, 22, 4))
    f = (cx + 6, cy - 14, cx + 30, cy + 14)
    part("samay-hall", f, 12, lambda cv: T.hall(cv, *f, 7))


def vayalur():
    cx, cy = m(10.82891, 78.6231)
    rings = [dict(x0=-44, x1=44, y0=-34, y1=34, wh=5, thick=3, gates={"e": dict(L=24, T=16, H=30, n=5, pal=T.PAL_BRIGHT), "w": dict(L=14, T=10, H=12, n=2, pal=T.PAL_BRIGHT)})]
    compound("vayalur", (cx, cy), rings, T.PAL_BRIGHT, pave=(-42, 42, -32, 32), hide=(-48, 48, -38, 38),
             life=dict(avoid=[sbox(cx - 18, cy - 12, cx + 2, cy + 12), sbox(cx + 4, cy - 12, cx + 30, cy + 12)], cell=9, wall_buf=3, p=0.9, people=(2, 6), stalls_p=0.35, autos_p=0.05, trees_p=0.1))
    part("vayalur-vimanam", (cx - 8, cy - 8, cx + 8, cy + 8), 28, lambda cv: T.vimanam(cv, cx - 6, cy, 12, 17, 3))
    f = (cx + 6, cy - 10, cx + 28, cy + 10)
    part("vayalur-hall", f, 10, lambda cv: T.hall(cv, *f, 6))


def woraiyur():
    cx, cy = m(10.8299, 78.6705)
    rings = [dict(x0=-30, x1=30, y0=-24, y1=24, wh=5, thick=3, gates={"e": dict(L=20, T=14, H=26, n=5, pal=T.PAL_BRIGHT), "w": dict(L=14, T=10, H=12, n=2)})]
    compound("woraiyur", (cx, cy), rings, T.PAL_BRIGHT, pave=(-28, 28, -22, 22), hide=(-34, 34, -28, 28),
             life=dict(avoid=[sbox(cx - 14, cy - 10, cx + 6, cy + 10)], cell=8, wall_buf=3, p=0.9, people=(2, 5), stalls_p=0.3, autos_p=0.04, trees_p=0.1))
    part("woraiyur-vimanam", (cx - 6, cy - 6, cx + 6, cy + 6), 22, lambda cv: T.vimanam(cv, cx - 4, cy, 10, 14, 3))


def lourdes():
    cx, cy = m(10.82695, 78.69254)
    f = (cx - 24, cy - 14, cx + 54, cy + 14)
    # the sprite reaches well above the spire, so the canvas is tall on purpose
    part("lourdes", (cx - 30, cy - 20, cx + 58, cy + 20), 82, lambda cv: T.lourdes_church(cv, cx, cy))
    hide_rect(cx - 32, cy - 22, cx + 58, cy + 22)
    part("lourdes-pave", (cx - 40, cy - 30, cx + 62, cy + 30), 1, lambda cv: cv.ground([(cx - 40, cy - 30), (cx + 62, cy - 30), (cx + 62, cy + 30), (cx - 40, cy + 30)], (206, 196, 176)), ground=True)
    # a low cream compound wall with a gate on the south side, where the road is.
    # each side is its own sprite so the near walls paint in front and the far wall stays behind
    h, t, col = 2.2, 1.1, (236, 232, 222)
    x0, x1, y0, y1, gate = cx - 38, cx + 60, cy - 26, cy + 26, 7
    for i, seg in enumerate(((x0, y1 - t, x1, y1), (x0, y0, x0 + t, y1), (x1 - t, y0, x1, y1),
                             (x0, y0, cx - gate, y0 + t), (cx + gate, y0, x1, y0 + t))):
        def wall(cv, seg=seg):
            cv.box(*seg, 0, h, col, shade(col, 1.05), outline=False)
        part(f"lourdes-wall{i}", seg, 4, wall)
    scatter_life("lourdes", sbox(cx - 40, cy - 30, cx + 62, cy + 30), [sbox(*f), sbox(cx - 22, cy - 12, cx - 2, cy + 12)], 77, cell=10, p=0.45, people=(1, 4), stalls_p=0, autos_p=0, cows_p=0, trees_p=0.18, scooters_p=0.03)


# ------------------------------------------------------------------------------------------------ hills
def heightfield(poly, H, seed, cell=1.6, terrace=1.8, bias=0.62):
    x0, y0, x1, y1 = poly.bounds
    xs = np.arange(x0 - 4, x1 + 4, cell)
    ys = np.arange(y0 - 4, y1 + 4, cell)
    X, Y = np.meshgrid(xs + cell / 2, ys + cell / 2)
    inside = shapely.contains_xy(poly, X, Y)
    dist = ndimage.distance_transform_edt(inside) * cell
    dmax = max(dist.max(), 1.0)
    t = np.clip(dist / dmax, 0, 1)
    rng = np.random.default_rng(seed)
    n1 = ndimage.gaussian_filter(rng.standard_normal(X.shape), 5)
    n1 /= max(1e-6, np.abs(n1).max())
    n2 = ndimage.gaussian_filter(rng.standard_normal(X.shape), 1.6)
    n2 /= max(1e-6, np.abs(n2).max())
    h = H * (t ** bias) * (1.0 + 0.16 * n1) + 1.4 * n2 * t
    h = np.where(inside, np.maximum(h, 1.0), 0.0)
    h = np.round(h / terrace) * terrace
    h[~inside] = 0
    return xs, ys, h.astype(np.float32), inside, n2


def rock_sprite(cv, poly, H, seed, xs, ys, h, inside, n2, cell, base=(138, 112, 90), top=(212, 190, 152), green=(96, 140, 70), terrace=1.2):
    """Granite hill as a lit, terraced heightfield: sandy tops, dark strata on the cliff faces, scrub on the gentle slopes."""
    P = cv.P
    ny, nx = h.shape
    order = [(j, i) for j in range(ny) for i in range(nx) if inside[j, i]]
    order.sort(key=lambda a: -(xs[a[1]] + ys[a[0]]))
    gx, gy = np.gradient(h, cell)
    maxh = float(h.max())
    d = cv.d
    rng = np.random.default_rng(seed + 5)
    cliff = (96, 74, 58)
    for j, i in order:
        x, y = xs[i], ys[j]
        z = float(h[j, i])
        tt = z / maxh
        slope = math.hypot(gx[j, i], gy[j, i])
        lit = 1.0 + 0.55 * gx[j, i] - 0.25 * gy[j, i]
        col = mix(base, top, min(1.0, tt ** 0.75))
        steep = min(1.0, slope / 1.1)
        col = mix(col, cliff, 0.5 * steep)
        veg = (n2[j, i] > 0.05) and slope < 0.8 and 0.04 < tt < 0.75
        if veg:
            col = mix(col, green, 0.65 * (1 - steep))
        grit = 0.94 + 0.12 * float(rng.random())
        col = shade(col, max(0.66, min(1.22, lit)) * (1 + 0.06 * n2[j, i]) * grit)
        x1, y1 = x + cell, y + cell
        zs = float(h[j - 1, i]) if j > 0 else 0.0
        zw = float(h[j, i - 1]) if i > 0 else 0.0
        if zs < z:
            fc = mix(col, cliff, 0.55)
            d.polygon([P(x, y, zs), P(x1, y, zs), P(x1, y, z), P(x, y, z)], fill=shade(fc, 0.92))
            d.line([P(x, y, z), P(x1, y, z)], fill=shade(fc, 1.12))      # lit ledge edge
        if zw < z:
            fc = mix(col, cliff, 0.55)
            d.polygon([P(x, y, zw), P(x, y1, zw), P(x, y1, z), P(x, y, z)], fill=shade(fc, 0.66))
        d.polygon([P(x, y, z), P(x1, y, z), P(x1, y1, z), P(x, y1, z)], fill=col)
        if veg and rng.random() < 0.035 and steep < 0.4:
            bx, by = P(x + cell / 2, y + cell / 2, z)
            SP.tree(d, bx, by, int(rng.integers(0, 1 << 20)), "bush" if rng.random() < 0.6 else "neem")
    # shadow
    from art3d import SHADOW_DIR
    ring = [P(x, y, 0) for x, y in poly.exterior.coords]
    sdx, sdy = SHADOW_DIR[0] * maxh * VK * 0.28, SHADOW_DIR[1] * maxh * VK * 0.28
    for k in range(5):
        cv.sd.polygon([(x + sdx * k / 4, y + sdy * k / 4) for x, y in ring], fill=255)


def rockfort():
    rocks = _geoms("land", "subtype='rock' and names.primary like '%Rock Fort%'")
    poly = max((g for g, *_ in rocks), key=lambda g: g.area)
    if poly.geom_type == "MultiPolygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    poly = poly.buffer(4).simplify(1.5)
    H = 80.0
    cell = 1.0
    xs, ys, h, inside, n2 = heightfield(poly, H, 11, cell, 1.4, 0.55)
    x0, y0, x1, y1 = poly.bounds
    foot = (x0 - 30, y0 - 30, x1 + 30, y1 + 30)
    jj, ii = np.unravel_index(np.argmax(h), h.shape)
    summit = (xs[ii] + cell / 2, ys[jj] + cell / 2)

    def draw(cv):
        rock_sprite(cv, poly, H, 11, xs, ys, h, inside, n2, cell, base=(112, 88, 70), top=(214, 190, 150), terrace=1.4)
        # stair: a zig-zag of pale steps from the southern foot to the summit
        P = cv.P
        south = min(poly.exterior.coords, key=lambda p: p[1] + 0.5 * abs(p[0] - (x0 + x1) / 2))
        a = np.array(south) + np.array([3.0, 6.0]); b = np.array(summit)
        path = []
        N = 70
        for s in range(N + 1):
            t = s / N
            p = a + (b - a) * t
            perp = np.array([-(b - a)[1], (b - a)[0]]) / max(1e-6, np.linalg.norm(b - a))
            p = p + perp * 7 * math.sin(t * 18) * (1 - t * 0.5)
            ii2 = int(np.clip((p[0] - xs[0]) / cell, 0, len(xs) - 1)); jj2 = int(np.clip((p[1] - ys[0]) / cell, 0, len(ys) - 1))
            zz = float(h[jj2, ii2]) + 0.8
            path.append(P(p[0], p[1], zz))
        for k in range(len(path) - 1):
            (ax_, ay_), (bx_, by_) = path[k], path[k + 1]
            tread = (232, 220, 196) if (k // 2) % 2 == 0 else (160, 140, 116)
            cv.d.line([(ax_, ay_ - 1), (bx_, by_ - 1)], fill=tread, width=3)
        cv.d.line([(x, y + 2) for x, y in path], fill=(96, 78, 62), width=1)
    # the rock is one sprite; temples on it are separate parts so they sort against the rock
    part("rockfort-rock", foot, H + 6, draw)
    ry = PARTS[-1]["y"]
    hide_poly(list(poly.exterior.coords), 14)
    sx, sy = summit
    z_s = float(h.max())

    def lifted(z, fn):
        def run(cv):
            cv.dz = z
            fn(cv)
        return run

    # Ucchi Pillayar temple on the summit: a small colourful gopuram on a stone terrace
    sf = (sx - 9, sy - 8, sx + 9, sy + 8)

    def summit_shrine(cv):
        cv.box(sx - 8, sy - 7, sx + 8, sy + 7, 0, 1.6, (176, 160, 140), (200, 184, 160))
        T.gopuram(cv, sx, sy, 12.5, 9.5, 24, 5, "ns", T.PAL_CLASSIC, seed=9)
        T.hall(cv, sx - 14, sy + 5, sx - 5, sy + 11, 4.0)
    part("rockfort-summit", (sx - 15, sy - 9, sx + 9, sy + 12), z_s + 34, lifted(z_s + 0.2, summit_shrine), y=ry + 1)
    # Thayumanavar temple, half-way up on the western slope
    cand = np.argwhere(inside & (np.abs(h - H * 0.48) < 4))
    if len(cand):
        k = int(np.argmin([xs[i] * 0.6 - ys[j] * 0.3 for j, i in cand]))
        j, i = cand[k]
        tx, ty, tz = xs[i] + cell / 2, ys[j] + cell / 2, float(h[j, i])

        def thaya(cv):
            cv.box(tx - 18, ty - 10, tx + 18, ty + 10, 0, 1.8, (180, 164, 142), (204, 188, 164))
            T.hall(cv, tx - 16, ty - 8, tx + 6, ty + 8, 5.0)
            T.gopuram(cv, tx + 10, ty, 15, 11, 26, 5, "ns", T.PAL_CLASSIC, seed=4)
            T.vimanam(cv, tx - 6, ty - 1, 9, 14, 3)
        part("rockfort-thayumanavar", (tx - 18, ty - 10, tx + 18, ty + 10), tz + 38, lifted(tz, thaya), y=ry + 2)
    # rock-cut cave shrines and the entrance gopuram at the southern foot
    sxp, syp = min(poly.exterior.coords, key=lambda p: p[1] + 0.5 * abs(p[0] - (x0 + x1) / 2))
    for q, (ox, oy, w, dd, hh) in enumerate([(-22, 6, 14, 9, 7), (14, 6, 12, 8, 6), (-3, 10, 9, 7, 5)]):
        bx, by = sxp + ox, syp + oy

        def cave(cv, bx=bx, by=by, w=w, dd=dd, hh=hh):
            S, Wq, top = cv.box(bx, by, bx + w, by + dd, 0, hh, (146, 124, 102), (170, 148, 122))
            cv.d.polygon(frect(S, 0.3, 0.7, 0.0, 0.62), fill=(40, 30, 28), outline=(210, 190, 150))
            cv.d.polygon(frect(S, 0.12, 0.2, 0.0, 0.7), fill=(176, 154, 126))
            cv.d.polygon(frect(S, 0.8, 0.88, 0.0, 0.7), fill=(176, 154, 126))
            cv.d.line([fp(S, 0.0, 0.8), fp(S, 1.0, 0.8)], fill=(190, 166, 134))
            cv.d.polygon(frect(S, 0.45, 0.55, 0.4, 0.52), fill=(236, 190, 70))   # lamp glow
        part(f"rockfort-cave{q}", (bx, by, bx + w, by + dd), hh + 4, cave, y=ry + 3 + q)
    gopuram_part("rockfort-entrance", sxp + 2, syp - 16, 18, 12, 20, 5, "ns", T.PAL_CLASSIC, seed=3)
    ring_area = poly.buffer(14).difference(poly.buffer(2))
    avoid = [sbox(sxp - 26, syp - 6, sxp + 28, syp + 22)]
    scatter_life("rockfort", ring_area, avoid, 17, cell=14, p=0.35, people=(1, 4), stalls_p=0.15, autos_p=0.05, cows_p=0.02, trees_p=0.3, scooters_p=0.1)


def hill(name, lat, lon, rx, ry, H, seed, temple=True, rot=0.0):
    cx, cy = m(lat, lon)
    ell = shapely.affinity.rotate(shapely.affinity.scale(Point(cx, cy).buffer(1, quad_segs=20), rx, ry), rot, origin=(cx, cy))
    poly = ell.simplify(1)
    cell = 1.0
    xs, ys, h, inside, n2 = heightfield(poly, H, seed, cell, 1.4, 0.6)
    x0, y0, x1, y1 = poly.bounds
    part(f"{name}-rock", (x0 - 10, y0 - 10, x1 + 10, y1 + 10), H + 4,
         lambda cv: rock_sprite(cv, poly, H, seed, xs, ys, h, inside, n2, cell, base=(126, 100, 80), top=(206, 184, 146)))
    ry_ = PARTS[-1]["y"]
    hide_poly(list(poly.exterior.coords), 6)
    if temple:
        jj, ii = np.unravel_index(np.argmax(h), h.shape)
        sx, sy, sz = xs[ii] + cell / 2, ys[jj] + cell / 2, float(h.max())

        def top(cv):
            cv.dz = sz + 0.2
            cv.box(sx - 8, sy - 7, sx + 8, sy + 7, 0, 1.4, (176, 160, 140), (200, 184, 160))
            T.gopuram(cv, sx, sy, 11, 8.5, 18, 4, "ns", T.PAL_CLASSIC, seed=seed)
            T.hall(cv, sx - 12, sy + 3, sx - 5, sy + 9, 3.5)
        part(f"{name}-temple", (sx - 14, sy - 8, sx + 9, sy + 10), sz + 26, top, y=ry_ + 1)
    ring = poly.buffer(10).difference(poly.buffer(1))
    scatter_life(name, ring, [], seed + 3, cell=12, p=0.3, people=(0, 3), stalls_p=0.1, autos_p=0.04, cows_p=0.03, trees_p=0.4, scooters_p=0.05)
    return cx, cy


# ------------------------------------------------------------------------------------------------ bridges, anicuts, ghats
BRIDGE_W = {"motorway": 16, "trunk": 14, "primary": 12, "secondary": 10, "tertiary": 8, "unclassified": 7, "residential": 6, "service": 5, "track": 5}


def _deck_ring(p, q, hw):
    dx, dy = q[0] - p[0], q[1] - p[1]
    n = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / n * hw, dx / n * hw
    return [(p[0] + nx, p[1] + ny), (q[0] + nx, q[1] + ny), (q[0] - nx, q[1] - ny), (p[0] - nx, p[1] - ny)]


DECK_Z = 1.8


def _bridge_piece(name, pts, hw, stone, seed, anicut=False):
    """One 12-20 m piece of a bridge deck with kerbs, railings, lamp posts and piers. Anicut pieces get blue sluice
    gates on both faces and white spill foam on the water below."""
    xs_ = [p[0] for p in pts]; ys_ = [p[1] for p in pts]
    foot = (min(xs_) - hw - 9, min(ys_) - hw - 9, max(xs_) + hw + 9, max(ys_) + hw + 9)
    deck_col = (176, 162, 140) if stone else (190, 184, 172)
    top_col = (98, 96, 100)
    if anicut:
        a, b = pts[0], pts[-1]

        def foam(cv):
            rng = np.random.default_rng(seed)
            for sgn in (-1, 1):
                e = _deck_ring(a, b, hw + 1.0 + 3.0)
                inner = _deck_ring(a, b, hw + 0.5)
                ring = [inner[0], inner[1], e[1], e[0]] if sgn > 0 else [inner[3], inner[2], e[2], e[3]]
                cv.ground(ring, (226, 238, 240))
                for _ in range(26):
                    u, v = rng.random(), rng.random()
                    x = ring[0][0] + (ring[1][0] - ring[0][0]) * u + (ring[3][0] - ring[0][0]) * v
                    y = ring[0][1] + (ring[1][1] - ring[0][1]) * u + (ring[3][1] - ring[0][1]) * v
                    X, Y = cv.P(x, y)
                    cv.d.line([(X - 2, Y), (X + 2, Y)], fill=(255, 255, 255) if rng.random() < 0.6 else (176, 210, 222))
        part(name + "-foam", foot, 1, foam, ground=True)

    def draw(cv):
        P = cv.P
        a, b = pts[0], pts[-1]
        if anicut:
            # piers and blue vertical-lift gates between them, on both faces
            ring = _deck_ring(a, b, hw)
            cv.extrude(ring, -1.0, DECK_Z - 0.2, (120, 150, 176), (150, 176, 196))
            for (p0, p1) in ((ring[0], ring[1]), (ring[3], ring[2])):
                for k in range(5):
                    u0, u1 = k / 5 + 0.03, (k + 1) / 5 - 0.03
                    g0 = (p0[0] + (p1[0] - p0[0]) * u0, p0[1] + (p1[1] - p0[1]) * u0)
                    g1 = (p0[0] + (p1[0] - p0[0]) * u1, p0[1] + (p1[1] - p0[1]) * u1)
                    q = [P(g0[0], g0[1], -0.6), P(g1[0], g1[1], -0.6), P(g1[0], g1[1], DECK_Z - 0.4), P(g0[0], g0[1], DECK_Z - 0.4)]
                    cv.d.polygon(q, fill=(52, 120, 196), outline=(30, 76, 140))
                    cv.d.line([q[0], q[2]], fill=(84, 150, 216))
        # piers under the deck (stone piers with cutwaters)
        for t in ((0.2, 0.8) if len(pts) > 1 and not anicut else ()):
            c = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            ring = _deck_ring((c[0] - (b[0] - a[0]) * 0.07, c[1] - (b[1] - a[1]) * 0.07), (c[0] + (b[0] - a[0]) * 0.07, c[1] + (b[1] - a[1]) * 0.07), hw * 0.85)
            cv.extrude(ring, -5.0, DECK_Z - 0.6, (132, 120, 104), (150, 138, 120), shadow=False)
        ring = _deck_ring(a, b, hw)
        cv.extrude(ring, DECK_Z - (0.4 if anicut else 2.4), DECK_Z, deck_col, top_col)
        # kerbs and railings along both long edges
        for sgn in (-1, 1):
            e = _deck_ring(a, b, hw)
            p0 = e[0] if sgn > 0 else e[3]; p1 = e[1] if sgn > 0 else e[2]
            q0 = P(p0[0], p0[1], DECK_Z); q1 = P(p1[0], p1[1], DECK_Z)
            r0 = P(p0[0], p0[1], DECK_Z + 1.3); r1 = P(p1[0], p1[1], DECK_Z + 1.3)
            cv.d.line([r0, r1], fill=(238, 232, 220))
            n_ = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 2.2))
            for i in range(n_ + 1):
                u = i / n_
                cv.d.line([(q0[0] + (q1[0] - q0[0]) * u, q0[1] + (q1[1] - q0[1]) * u), (r0[0] + (r1[0] - r0[0]) * u, r0[1] + (r1[1] - r0[1]) * u)], fill=(210, 204, 192))
            cv.d.line([q0, q1], fill=(236, 230, 218))
        # centre line
        c0, c1 = P(a[0], a[1], DECK_Z), P(b[0], b[1], DECK_Z)
        cv.d.line([c0, c1], fill=(232, 226, 210))
        if stone and seed % 3 == 0:     # anicut sluice towers (blue hoist frames on the regulators)
            e = _deck_ring(a, b, hw)
            tw, tr = ((84, 140, 200), (60, 110, 176)) if anicut else ((200, 186, 160), (176, 160, 134))
            for p0 in (e[0], e[3]):
                cv.box(p0[0] - 0.9, p0[1] - 0.9, p0[0] + 0.9, p0[1] + 0.9, DECK_Z, DECK_Z + 4.2, tw, shade(tw, 1.1))
                cv.box(p0[0] - 1.2, p0[1] - 1.2, p0[0] + 1.2, p0[1] + 1.2, DECK_Z + 4.2, DECK_Z + 5.0, tr, shade(tr, 1.1))
        # lamp post
        if seed % 2 == 0:
            e = _deck_ring(a, b, hw)
            lx, ly = (e[0][0] + e[1][0]) / 2, (e[0][1] + e[1][1]) / 2
            base = P(lx, ly, DECK_Z); top = P(lx, ly, DECK_Z + 5.4)
            cv.d.line([base, top], fill=(70, 70, 76))
            cv.d.line([top, (top[0] + 2, top[1])], fill=(70, 70, 76))
            cv.d.point((top[0] + 2, top[1] + 1), fill=(255, 236, 160))
    part(name, foot, DECK_Z + 8, draw)


def amma_mandapam():
    """Ghat on the Kaveri bank at Srirangam: stone steps into the river, a pillared mandapam and bathers."""
    cx, cy = m(10.8469, 78.6899)
    wat = [g for g, n_, s_, c_ in _geoms("water", "subtype in ('river','lake','reservoir','water') and ST_GeometryType(geometry) = 'POLYGON'") if g.area > 40000]
    water = unary_union(wat)
    here = Point(cx, cy)
    near = water.boundary.interpolate(water.boundary.project(here))
    nx, ny = near.x, near.y
    circle = Point(nx, ny).buffer(95)
    bands = [(1.2 + 1.6 * (q + 1), 1.2 + 1.6 * q, (208, 198, 178) if q % 2 == 0 else (166, 154, 134)) for q in range(5)]
    bands.append((20.0, 9.2, (224, 200, 152)))

    def steps(cv):
        for outer_off, inner_off, col in reversed(bands):
            ring = water.buffer(outer_off, join_style=2).difference(water.buffer(inner_off, join_style=2)).intersection(circle)
            for g in (ring.geoms if hasattr(ring, "geoms") else [ring]):
                if g.geom_type == "Polygon" and not g.is_empty:
                    cv.ground(list(g.exterior.coords), col, holes=[list(h.coords) for h in g.interiors], outline=shade(col, 0.82))
    part("amma-steps", (nx - 100, ny - 100, nx + 100, ny + 100), 1, steps, ground=True)
    # the mandapam stands a little inland of the steps, facing the river
    mx, my = nx, ny
    away = np.array([cx - nx, cy - ny]); d_ = np.linalg.norm(away) or 1.0
    mx, my = nx + away[0] / d_ * 15, ny + away[1] / d_ * 15

    def mand(cv):
        cv.box(mx - 11, my - 8, mx + 11, my + 8, 0, 1.2, (196, 184, 162), (212, 200, 178))
        for ix in range(5):
            for iy in range(2):
                px_, py_ = mx - 9 + ix * 4.5, my - 6 + iy * 12
                cv.box(px_ - 0.5, py_ - 0.5, px_ + 0.5, py_ + 0.5, 1.2, 5.5, (236, 218, 176), (236, 218, 176), outline=False, shadow=False)
        cv.box(mx - 10.5, my - 7.5, mx + 10.5, my + 7.5, 5.5, 7.0, (236, 214, 164), T.ROOF_RED)
        cv.frustum(mx, my, 6, 4.5, 7.0, 2.5, 1.8, 12.0, T.OCHRE, shade(T.OCHRE, 1.1))
        T.gopuram(cv, mx + 18, my, 10, 8, 18, 4, "ns", T.PAL_CLASSIC, seed=6)
    part("amma-mandapam", (mx - 12, my - 9, mx + 30, my + 9), 24, mand)
    hide_poly(list(Point(mx, my).buffer(34).exterior.coords), 0)
    ring_area = water.buffer(16).difference(water.buffer(2)).intersection(Point(nx, ny).buffer(80))
    scatter_life("amma", ring_area, [sbox(mx - 14, my - 10, mx + 34, my + 10)], 61, cell=8, p=0.7, people=(2, 6), stalls_p=0.15, autos_p=0.02, cows_p=0.04, trees_p=0.05, scooters_p=0.05)


FLY_HIDE: list[int] = []  # indices into HIDE that only clear the ground under flyovers (traffic may still cross there)
DECKS: list[dict] = []   # centre lines of raised roads (px) with deck height per vertex (m), read by traffic_data.py
KOLLIDAM_NEW = m(10.8656, 78.7043)
ANICUTS = (m(10.8315, 78.8189), m(10.8883, 78.5805))   # Kallanai and Mukkombu: sluice gates and spillway foam


def _deck_record(ln, zfun):
    L = ln.length
    n = max(2, int(L / 4.0) + 1)
    pts, zs = [], []
    for i in range(n):
        s = L * i / (n - 1)
        p = ln.interpolate(s)
        pts.append([round(v, 1) for v in iso_from_metres(p.x, p.y)])
        zs.append(round(float(zfun(s)), 2))
    DECKS.append(dict(px=pts, z=zs))


def _water_union():
    wat = [g.buffer(2) for g, n_, s_, c_ in _geoms("water", "subtype in ('river','lake','reservoir','water','human_made','canal','physical') and ST_GeometryType(geometry) = 'POLYGON'") if g.area > 8000]
    return unary_union(wat)


def _arch_piece(name, a, b, hw, seed):
    """White bowstring arches over one span of the new Kollidam bridge."""
    foot = (min(a[0], b[0]) - hw - 2, min(a[1], b[1]) - hw - 2, max(a[0], b[0]) + hw + 2, max(a[1], b[1]) + hw + 2)

    def draw(cv):
        P = cv.P
        for e0, e1 in ((_deck_ring(a, b, hw)[3], _deck_ring(a, b, hw)[2]), (_deck_ring(a, b, hw)[0], _deck_ring(a, b, hw)[1])):
            pts = []
            for i in range(13):
                u = i / 12
                x, y = e0[0] + (e1[0] - e0[0]) * u, e0[1] + (e1[1] - e0[1]) * u
                z = DECK_Z + 1.0 + 7.0 * math.sin(math.pi * u)
                pts.append((x, y, z))
            for i in range(1, 12):
                x, y, z = pts[i]
                cv.d.line([P(x, y, DECK_Z + 1.0), P(x, y, z)], fill=(214, 214, 210))
            cv.d.line([P(*q) for q in pts], fill=(250, 250, 246), width=2)
            cv.d.line([P(x, y, z + 0.4) for x, y, z in pts], fill=(196, 198, 200))
    part(name, foot, DECK_Z + 12, draw)


def bridges():
    """Raised decks with railings and piers wherever a mapped bridge segment crosses a river, lake or tank."""
    water = _water_union()
    segs = _geoms("segments", "subtype='road' and road_flags is not null and len(road_flags)>0 and list_contains(flatten(list_transform(road_flags, lambda x: x['values'])), 'is_bridge')")
    n = 0
    for g, nm, st, cls in segs:
        if cls in ("footway", "path", "steps", "pedestrian", "cycleway"):
            continue
        parts = g.intersection(water)
        if parts.is_empty:
            continue
        lines = list(parts.geoms) if hasattr(parts, "geoms") else [parts]
        hw = BRIDGE_W.get(cls, 6) / 2.0
        for ln in lines:
            if ln.geom_type != "LineString" or ln.length < 14:
                continue
            ln = ln.segmentize(1.0) if hasattr(ln, "segmentize") else ln
            L = ln.length
            c = ln.centroid
            anicut = any(math.hypot(c.x - ax, c.y - ay) < 1400 for ax, ay in ANICUTS)
            stone = c.x > 9000 or anicut                      # the Grand Anicut and the lower Cauvery are stone-faced
            arches = ln.distance(Point(*KOLLIDAM_NEW)) < 80 and L > 200      # only the NH bridge at the pin, not the bypass beside it
            _deck_record(ln, lambda s: DECK_Z)
            step = 16.0 if not arches else 32.0
            k = int(math.ceil(L / step))
            for i in range(k):
                s0, s1 = i * L / k, (i + 1) * L / k
                if arches:
                    for h_ in range(2):
                        q0, q1 = s0 + (s1 - s0) * h_ / 2, s0 + (s1 - s0) * (h_ + 1) / 2
                        pts = [ln.interpolate(q0 + (q1 - q0) * t / 4.0) for t in range(5)]
                        _bridge_piece(f"bridge{n}", [(p.x, p.y) for p in pts], hw + 0.8, stone, n, anicut=anicut)
                        n += 1
                    a_, b_ = ln.interpolate(s0), ln.interpolate(s1)
                    _arch_piece(f"arch{n}", (a_.x, a_.y), (b_.x, b_.y), hw + 0.8, n)
                else:
                    pts = [ln.interpolate(s0 + (s1 - s0) * t / 4.0) for t in range(5)]
                    _bridge_piece(f"bridge{n}", [(p.x, p.y) for p in pts], hw + 0.8, stone, n, anicut=anicut)
                n += 1
    print("bridge pieces", n, flush=True)


# ------------------------------------------------------------------------------------------------ flyovers on land
FLY_H = {"trunk": 7.5, "primary": 7.0, "secondary": 6.5, "tertiary": 6.0}
FLY_W = {"trunk": 9.5, "primary": 9.5, "secondary": 9.0, "tertiary": 8.0}   # one mapped line is usually one carriageway
CONC = (206, 202, 192)
ASPH = (96, 96, 102)


def _fly_piece(name, a, b, za, zb, hw, pier, lamp):
    """One 8-12 m stretch of a flyover: girder deck at height za..zb (m) with asphalt, lane marks, parapets, a pier, a lamp."""
    ring = _deck_ring(a, b, hw)
    foot = (min(p[0] for p in ring) - 2, min(p[1] for p in ring) - 2, max(p[0] for p in ring) + 2, max(p[1] for p in ring) + 2)
    zt = max(za, zb)

    def draw(cv):
        P = cv.P
        d = cv.d
        zof = lambda p: za if p in (ring[0], ring[3]) else zb
        # shadow: the deck footprint displaced along the light direction by its height
        from art3d import SHADOW_DIR
        for q in (ring,):
            pts = []
            for p in q:
                X, Y = P(p[0], p[1], 0)
                hpx = zof(p) * VK
                pts.append((X + SHADOW_DIR[0] * hpx, Y + SHADOW_DIR[1] * hpx))
            cv.sd.polygon(pts, fill=255)
        ux, uy = (b[0] - a[0]), (b[1] - a[1]); ln_ = math.hypot(ux, uy) or 1; ux, uy = ux / ln_, uy / ln_
        nx_, ny_ = -uy, ux
        # twin pier columns under a cross-beam
        if pier and min(za, zb) > 2.2:
            c = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            zc = (za + zb) / 2
            for sgn in (1, -1):
                pc = (c[0] + nx_ * hw * 0.5 * sgn, c[1] + ny_ * hw * 0.5 * sgn)
                cv.box(pc[0] - 0.6, pc[1] - 0.6, pc[0] + 0.6, pc[1] + 0.6, 0, zc - 1.9, (214, 210, 200), (224, 220, 210), shadow=False)
                Xs, Ys = P(pc[0], pc[1], 0)
                cv.sd.ellipse([Xs - 4, Ys - 1, Xs + 1, Ys + 2], fill=255)
            beam = _deck_ring((c[0] - ux * 0.7, c[1] - uy * 0.7), (c[0] + ux * 0.7, c[1] + uy * 0.7), hw * 0.85)
            cv.extrude(beam, zc - 2.5, zc - 1.6, (196, 192, 182), (206, 202, 192), shadow=False)
        left, right = (ring[0], ring[1]), (ring[3], ring[2])
        sl = sum(p[0] + p[1] for p in left); sr = sum(p[0] + p[1] for p in right)
        e_near, e_far = ([left], [right]) if sl < sr else ([right], [left])
        GD = 1.7   # girder depth
        # girder side facing the viewer, in light concrete with a dark soffit line
        for (p0, p1) in e_near:
            z0_, z1_ = zof(p0), zof(p1)
            q = [P(p0[0], p0[1], max(0, z0_ - GD)), P(p1[0], p1[1], max(0, z1_ - GD)), P(p1[0], p1[1], z1_), P(p0[0], p0[1], z0_)]
            f = 0.98 if abs(ux) > abs(uy) else 0.84
            d.polygon(q, fill=shade(CONC, f))
            d.line([q[0], q[1]], fill=shade(CONC, 0.5))
        # far parapet, asphalt, lane marks, near parapet
        for (p0, p1) in e_far:
            q = [P(p0[0], p0[1], zof(p0)), P(p1[0], p1[1], zof(p1)), P(p1[0], p1[1], zof(p1) + 1.1), P(p0[0], p0[1], zof(p0) + 1.1)]
            d.polygon(q, fill=shade(CONC, 0.9))
            d.line([q[3], q[2]], fill=(246, 244, 236))
        top = [P(p[0], p[1], zof(p)) for p in ring]
        d.polygon(top, fill=ASPH)
        ca, cb = P(a[0], a[1], za + 0.02), P(b[0], b[1], zb + 0.02)
        d.line([ca, ((ca[0] * 2 + cb[0]) / 3, (ca[1] * 2 + cb[1]) / 3)], fill=(240, 236, 220))
        for (p0, p1) in e_near + e_far:
            k0 = P(p0[0] + (a[0] - p0[0]) * 0.14, p0[1] + (a[1] - p0[1]) * 0.14, zof(p0))
            k1 = P(p1[0] + (b[0] - p1[0]) * 0.14, p1[1] + (b[1] - p1[1]) * 0.14, zof(p1))
            d.line([k0, k1], fill=(226, 200, 110))
        for (p0, p1) in e_near:
            z0_, z1_ = zof(p0), zof(p1)
            q = [P(p0[0], p0[1], z0_), P(p1[0], p1[1], z1_), P(p1[0], p1[1], z1_ + 1.1), P(p0[0], p0[1], z0_ + 1.1)]
            d.polygon(q, fill=(236, 232, 222))
            d.line([q[3], q[2]], fill=(252, 250, 244))
            d.line([q[0], q[1]], fill=shade(CONC, 0.7))
        if lamp:
            lx, ly = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            zl = (za + zb) / 2
            b0, t0 = P(lx, ly, zl), P(lx, ly, zl + 6.5)
            d.line([b0, t0], fill=(84, 86, 92))
            d.line([(t0[0] - 3, t0[1] + 1), (t0[0] + 3, t0[1] - 1)], fill=(84, 86, 92))
            d.point((t0[0] - 3, t0[1] + 2), fill=(255, 236, 170)); d.point((t0[0] + 3, t0[1]), fill=(255, 236, 170))
    part(name, foot, zt + 9, draw)


def flyovers():
    """Elevated roads (flyovers, rail over-bridges, the bypass viaducts) from the land parts of mapped bridge segments."""
    from shapely.ops import substring
    con = duckdb.connect(); con.execute("INSTALL spatial; LOAD spatial")
    rows = con.execute(f"select ST_AsWKB(geometry), class, road_flags from '{DATA}/raw/segments.parquet' where subtype='road' and road_flags is not null and len(road_flags)>0 and list_contains(flatten(list_transform(road_flags, lambda x: x['values'])), 'is_bridge')").fetchall()
    wb = _water_union().buffer(5)
    shapely.prepare(wb)
    n = 0
    for w, cls, flags in rows:
        if cls in ("footway", "path", "steps", "pedestrian", "cycleway", "track", "service"):
            continue
        g = shapely.transform(wkb.loads(bytes(w)), lambda a: np.column_stack(to_metres(a[:, 0], a[:, 1])))
        for f in flags:
            if "is_bridge" not in f["values"]:
                continue
            a0, b0 = f["between"] or [0.0, 1.0]
            sub = substring(g, a0, b0, normalized=True)
            land = sub.difference(wb) if wb.intersects(sub) else sub
            for ln in getattr(land, "geoms", [land]):
                if ln.geom_type != "LineString" or ln.length < 45 or wb.distance(ln) < 3:
                    continue
                L = ln.length
                H = FLY_H.get(cls, 5.5)
                if L < 140:
                    H = min(H, max(3.0, L / 16))
                R = min(L * 0.3, 150.0)

                def zf(s, H=H, R=R, L=L):
                    t = max(0.0, min(1.0, min(s, L - s) / R))
                    return 0.4 + (H - 0.4) * (t * t * (3 - 2 * t))
                _deck_record(ln, zf)
                hw = FLY_W.get(cls, 7.0) / 2.0
                k = max(1, int(math.ceil(L / 10.0)))
                for i in range(k):
                    s0, s1 = i * L / k, (i + 1) * L / k
                    pa, pb = ln.interpolate(s0), ln.interpolate(s1)
                    _fly_piece(f"fly{n}", (pa.x, pa.y), (pb.x, pb.y), zf(s0), zf(s1), hw, pier=(i % 2 == 1), lamp=(i % 3 == 0))
                    n += 1
                hide_poly(list(ln.buffer(hw * 0.8, cap_style=2).exterior.coords), 0)
                FLY_HIDE.append(len(HIDE) - 1)
    print("flyover pieces", n, flush=True)


# ------------------------------------------------------------------------------------------------ Teppakulam and the stadium
def teppakulam():
    tanks = _geoms("water", "names.primary = 'Teppakulam'")
    poly = max((g for g, *_ in tanks), key=lambda g: g.area)
    if poly.geom_type == "MultiPolygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    poly = poly.simplify(1.0)
    cx, cy = poly.centroid.x, poly.centroid.y
    # stepped ghats: alternating tread and riser bands, then a sandy promenade
    bands = []
    for q in range(5):
        bands.append((1.2 + 1.5 * (q + 1), 1.2 + 1.5 * q, (206, 196, 176) if q % 2 == 0 else (168, 156, 136)))
    bands.append((17.0, 8.7, (222, 198, 150)))
    x0, y0, x1, y1 = poly.buffer(20).bounds

    def ghat(cv):
        for outer_off, inner_off, col in reversed(bands):
            outer = poly.buffer(outer_off, join_style=2)
            inner = poly.buffer(inner_off, join_style=2)
            cv.ground(list(outer.exterior.coords), col, holes=[list(inner.exterior.coords)], outline=shade(col, 0.82))
    part("tepp-ghat", (x0, y0, x1, y1), 1, ghat, ground=True)
    hide_poly(list(poly.buffer(12).exterior.coords), 0)
    minx, miny, maxx, maxy = poly.bounds
    # central mandapam: stepped plinth with stairs, a pillared pavilion and a colourful five-tier vimana
    def pavilion(cv):
        cv.box(cx - 15, cy - 15, cx + 15, cy + 15, 0, 1.0, (190, 178, 156), (206, 194, 172))
        cv.box(cx - 13, cy - 13, cx + 13, cy + 13, 1.0, 2.0, (200, 188, 166), (216, 204, 182))
        cv.box(cx - 11, cy - 11, cx + 11, cy + 11, 2.0, 3.0, (210, 198, 176), (224, 212, 190))
        # stair flights on the south and west sides
        for q in range(4):
            cv.box(cx - 4, cy - 15 - (4 - q) * 0.9, cx + 4, cy - 14.5, 0, 0.9 * (q + 1), (214, 204, 184), (230, 220, 200), shadow=False)
        S, Wq, top = cv.box(cx - 8.5, cy - 8.5, cx + 8.5, cy + 8.5, 3.0, 8.5, (236, 214, 164), T.ROOF_RED)
        for q, f in ((S, 1.0), (Wq, 0.78)):
            n = 5
            for i in range(n + 1):
                cv.d.line([fp(q, i / n, 0.04), fp(q, i / n, 0.84)], fill=shade((120, 80, 60), f))
            cv.d.line([fp(q, 0, 0.86), fp(q, 1, 0.86)], fill=shade((190, 80, 60), f))
        T.gopuram(cv, cx, cy, 14, 11, 28, 5, "ns", T.PAL_CLASSIC, seed=2, base_col=(236, 214, 164))
    part("tepp-mandapam", (cx - 15, cy - 16, cx + 15, cy + 15), 42, lambda cv: (setattr(cv, "dz", 0.0), pavilion(cv)))
    # little gopurams at the middle of the north and south banks, pavilions at the four corners
    for nm, gx, gy in (("s", cx, miny - 22), ("n", cx, maxy + 22)):
        gopuram_part(f"tepp-g{nm}", gx, gy, 16, 11, 16, 4, "ns", T.PAL_CLASSIC, seed=5)
    for q, (px, py) in enumerate(((minx - 8, miny - 8), (maxx + 8, miny - 8), (minx - 8, maxy + 8), (maxx + 8, maxy + 8))):
        def chhatri(cv, px=px, py=py):
            cv.box(px - 3, py - 3, px + 3, py + 3, 0, 1.2, (200, 188, 166), (214, 202, 180))
            for dx, dy in ((-2, -2), (2, -2), (-2, 2), (2, 2)):
                cv.box(px + dx - 0.4, py + dy - 0.4, px + dx + 0.4, py + dy + 0.4, 1.2, 5.0, (226, 206, 170), (226, 206, 170), outline=False, shadow=False)
            cv.frustum(px, py, 3.4, 3.4, 5.0, 1.2, 1.2, 8.5, T.OCHRE, shade(T.OCHRE, 1.1))
        part(f"tepp-chh{q}", (px - 4, py - 4, px + 4, py + 4), 12, chhatri)
    ring = poly.buffer(17).difference(poly.buffer(7))
    scatter_life("tepp", ring, [sbox(cx - 20, cy - 20, cx + 20, cy + 20)], 31, cell=8, p=0.7, people=(2, 6), stalls_p=0.2, autos_p=0.02, cows_p=0.02, trees_p=0.05, scooters_p=0.05)


def _ring_pts(poly, step=1.6):
    ln = poly.exterior
    L = ln.length
    return [ln.interpolate(L * i / max(1, int(L / step))) for i in range(max(1, int(L / step)))]


SHIRTS = [(236, 236, 228), (214, 64, 56), (56, 104, 196), (240, 190, 50), (60, 150, 90), (232, 120, 160), (40, 40, 46), (250, 160, 60)]


def anna_stadium():
    """Anna Stadium: an 8-lane track round a football pitch, stepped concrete terraces with rows of seated spectators,
    a covered pavilion on the west side, floodlight masts and a scoreboard."""
    items = _geoms("land_use", "names.primary='Anna Stadium' or class in ('track','pitch') and ST_Y(ST_Centroid(geometry)) between 10.778 and 10.783 and ST_X(ST_Centroid(geometry)) between 78.694 and 78.700")
    track = [g for g, n, s, c in items if c == "track"]
    pitch = [g for g, n, s, c in items if c == "pitch"]
    poly = max(track, key=lambda g: g.area) if track else Point(*m(10.78054, 78.69657)).buffer(60)
    if poly.geom_type == "MultiPolygon":
        poly = max(poly.geoms, key=lambda g: g.area)
    field = max(pitch, key=lambda g: g.area) if pitch else poly.buffer(-11)
    if field.geom_type == "MultiPolygon":
        field = max(field.geoms, key=lambda g: g.area)
    poly = Polygon(poly.simplify(0.8).exterior)
    outer = Polygon(poly.buffer(3, join_style=1).exterior)
    x0, y0, x1, y1 = outer.buffer(40).bounds
    ccx, ccy = outer.centroid.x, outer.centroid.y
    rng = np.random.default_rng(18)

    def ground(cv):
        cv.ground(list(outer.buffer(1.5).exterior.coords), (214, 206, 190))
        cv.ground(list(outer.exterior.coords), (184, 84, 62))
        inner = poly.buffer(-9.6)
        cv.ground(list(inner.exterior.coords), (92, 156, 80))
        # lane lines: 8 lanes of 1.2 m
        for k in range(9):
            r = poly.buffer(-0.2 - 1.2 * k)
            if not r.is_empty and r.geom_type == "Polygon":
                cv.d.line([cv.P(x, y) for x, y in r.exterior.coords], fill=(240, 222, 210))
        # mowing stripes and pitch markings, laid out on the field's long axis
        rr = field.minimum_rotated_rectangle
        c = list(rr.exterior.coords)[:4]
        e1 = np.subtract(c[1], c[0]); e2 = np.subtract(c[2], c[1])
        if np.linalg.norm(e1) < np.linalg.norm(e2):
            c = c[1:] + c[:1]; e1, e2 = e2, e1
        L, W = np.linalg.norm(e1), np.linalg.norm(e2)
        u, v = e1 / L, e2 / W
        o = np.array(c[0])
        for k in range(10):
            if k % 2:
                q = [o + u * L * k / 10, o + u * L * (k + 1) / 10, o + u * L * (k + 1) / 10 + v * W, o + u * L * k / 10 + v * W]
                cv.d.polygon([cv.P(*p) for p in q], fill=(104, 170, 90))
        wl = (246, 246, 238)
        P = lambda a, b: cv.P(*(o + u * a + v * b))
        cv.d.polygon([P(0, 0), P(L, 0), P(L, W), P(0, W)], outline=wl)
        cv.d.line([P(L / 2, 0), P(L / 2, W)], fill=wl)
        cv.d.polygon([P(L / 2 + 9.15 * math.cos(t) * 1.0, W / 2 + 9.15 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 28)], outline=wl)
        for end in (0, L):
            sg = 1 if end == 0 else -1
            cv.d.polygon([P(end, W / 2 - 20), P(end + sg * 16.5, W / 2 - 20), P(end + sg * 16.5, W / 2 + 20), P(end, W / 2 + 20)], outline=wl)
            cv.d.polygon([P(end, W / 2 - 9), P(end + sg * 5.5, W / 2 - 9), P(end + sg * 5.5, W / 2 + 9), P(end, W / 2 + 9)], outline=wl)
        # start / finish line across the lanes on the home straight
        sp = poly.exterior.interpolate(poly.exterior.project(Point(ccx - 200, ccy)))
        ip = poly.buffer(-9.6).exterior.interpolate(poly.buffer(-9.6).exterior.project(sp))
        cv.d.line([cv.P(sp.x, sp.y), cv.P(ip.x, ip.y)], fill=(250, 250, 246), width=2)
    part("anna-field", (x0, y0, x1, y1), 1, ground, ground=True)

    # goals, footballers and a few runners
    rr = field.minimum_rotated_rectangle
    c4 = list(rr.exterior.coords)[:4]
    e1 = np.subtract(c4[1], c4[0]); e2 = np.subtract(c4[2], c4[1])
    if np.linalg.norm(e1) < np.linalg.norm(e2):
        c4 = c4[1:] + c4[:1]; e1, e2 = e2, e1
    FL, FW = np.linalg.norm(e1), np.linalg.norm(e2); fu, fv = e1 / FL, e2 / FW; fo = np.array(c4[0])

    def players(cv):
        P = cv.P
        for end in (0.0, FL):
            a = fo + fu * end + fv * (FW / 2 - 3.6); b = fo + fu * end + fv * (FW / 2 + 3.6)
            pa0, pa1, pb0, pb1 = P(*a), P(*a, 2.4), P(*b), P(*b, 2.4)
            cv.d.line([pa0, pa1], fill=(250, 250, 250)); cv.d.line([pb0, pb1], fill=(250, 250, 250)); cv.d.line([pa1, pb1], fill=(250, 250, 250))
        for k in range(18):
            t, w = rng.uniform(0.1, 0.9), rng.uniform(0.1, 0.9)
            p = fo + fu * FL * t + fv * FW * w
            X, Y = P(*p)
            col = (220, 60, 50) if k % 2 else (240, 240, 236)
            cv.sd.point((X - 1, Y), fill=255)
            cv.d.point((X, Y - 1), fill=col); cv.d.point((X, Y - 2), fill=col); cv.d.point((X, Y - 3), fill=(90, 60, 40)); cv.d.point((X, Y), fill=(40, 40, 46))
        for k in range(7):
            q = poly.buffer(-0.8 - 1.2 * (k % 8)).exterior
            pt = q.interpolate(rng.uniform(0, q.length))
            X, Y = P(pt.x, pt.y)
            col = SHIRTS[k % len(SHIRTS)]
            cv.d.point((X, Y - 1), fill=col); cv.d.point((X, Y - 2), fill=col); cv.d.point((X, Y - 3), fill=(90, 60, 40)); cv.d.point((X, Y), fill=(40, 40, 46))
    part("anna-players", (x0 + 30, y0 + 30, x1 - 30, y1 - 30), 4, players)

    # stepped terraces: 8 steps of 2.2 m depth and 0.8 m rise
    NSTEP, DEPTH, RISE = 8, 2.2, 0.8
    rings = [outer.buffer(1.5 + DEPTH * k, join_style=1) for k in range(NSTEP + 1)]
    concrete = [(206, 200, 188), (192, 186, 174)]
    sectors = [(68, 112, 182), (232, 186, 60), (204, 70, 58)]

    def stands(cv):
        for k in range(NSTEP):
            o, i = rings[k + 1], rings[k]
            z1 = RISE * (k + 1)
            cv.extrude(list(o.exterior.coords), 0 if k == NSTEP - 1 else z1 - RISE, z1, concrete[k % 2], concrete[k % 2], holes=[list(i.exterior.coords)], shadow=(k == NSTEP - 1), outline=False)
            # coloured seat strip on each tread, by sector
            mid = o.buffer(-DEPTH * 0.55, join_style=1)
            for pt in _ring_pts(mid, 1.2):
                ang = math.atan2(pt.y - ccy, pt.x - ccx)
                col = sectors[int(((ang + math.pi) / (2 * math.pi)) * 6) % 3]
                X, Y = cv.P(pt.x, pt.y, z1)
                cv.d.point((X, Y), fill=shade(col, 0.85 if k % 2 else 1.0))
        # back wall cap
        cv.d.line([cv.P(x, y, RISE * NSTEP + 0.1) for x, y in rings[-1].exterior.coords], fill=(236, 232, 222))

    part("anna-stands", (x0, y0, x1, y1), RISE * NSTEP + 4, stands)
    stands_y = PARTS[-1]["y"]
    hide_poly(list(rings[-1].buffer(3).exterior.coords), 4)

    # seated spectators: two-pixel figures in rows on the treads that face the viewer (the far side and the ends)
    def crowd(cv):
        for k in range(NSTEP):
            mid = rings[k + 1].buffer(-DEPTH * 0.45, join_style=1)
            z1 = RISE * (k + 1)
            for pt in _ring_pts(mid, 0.9):
                dx, dy = pt.x - ccx, pt.y - ccy
                if dx + dy < -0.25 * math.hypot(dx, dy):     # near side: hidden behind the back wall
                    continue
                west = dx < -(outer.bounds[2] - outer.bounds[0]) * 0.25
                if rng.random() > (0.78 if west else 0.42):
                    continue
                X, Y = cv.P(pt.x, pt.y, z1)
                col = SHIRTS[int(rng.integers(0, len(SHIRTS)))]
                cv.d.point((X, Y - 1), fill=col)
                cv.d.point((X, Y - 2), fill=(70, 46, 34) if rng.random() < 0.8 else (30, 26, 26))
    part("anna-crowd", (x0, y0, x1, y1), RISE * NSTEP + 4, crowd, y=stands_y + 1)

    # covered pavilion over the west stand: slim columns and a white cantilever roof with a blue fascia
    wsec = rings[-1].difference(rings[0]).intersection(sbox(outer.bounds[0] - 30, ccy - 34, ccx - (outer.bounds[2] - outer.bounds[0]) * 0.3, ccy + 34))
    if not wsec.is_empty:
        roof = wsec.buffer(1.2) if wsec.geom_type == "Polygon" else max(wsec.geoms, key=lambda g: g.area).buffer(1.2)
        rb = roof.bounds

        def pav(cv):
            back = roof.exterior
            for i in range(0, int(back.length), 9):
                p = back.interpolate(i)
                if Point(p.x, p.y).distance(rings[-1].exterior) < 3:
                    cv.box(p.x - 0.4, p.y - 0.4, p.x + 0.4, p.y + 0.4, RISE * NSTEP, 13.0, (226, 224, 218), (226, 224, 218), outline=False, shadow=False)
            cv.extrude(list(roof.exterior.coords), 13.0, 13.7, (52, 96, 170), (238, 238, 232))
        part("anna-roof", (rb[0] - 2, rb[1] - 2, rb[2] + 2, rb[3] + 2), 16, pav, y=stands_y + 2)

    # floodlight masts at four corners
    for k, (dx, dy) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1))):
        bx = ccx + dx * (rings[-1].bounds[2] - rings[-1].bounds[0]) / 2 * 0.86
        by = ccy + dy * (rings[-1].bounds[3] - rings[-1].bounds[1]) / 2 * 0.86

        def mast(cv, bx=bx, by=by):
            a, b = cv.P(bx, by, 0), cv.P(bx, by, 30)
            cv.d.line([a, b], fill=(120, 120, 126), width=2)
            cv.d.rectangle([b[0] - 5, b[1] - 4, b[0] + 5, b[1] + 1], fill=(70, 70, 76))
            for i in range(4):
                for j in range(2):
                    cv.d.point((b[0] - 4 + i * 2 + 1, b[1] - 3 + j * 2), fill=(255, 246, 200))
            cv._shadow([a, (a[0] + 1, a[1])], 30 * VK)
        part(f"anna-mast{k}", (bx - 2, by - 2, bx + 2, by + 2), 34, mast)
    sb = (ccx + 6, rings[-1].bounds[3] - 2)

    def scoreboard(cv):
        cv.box(sb[0] - 9, sb[1] - 1, sb[0] + 9, sb[1] + 1, 6, 15, (50, 50, 58), (30, 30, 36))
        S, W_, top = cv.box(sb[0] - 8, sb[1] - 1.2, sb[0] + 8, sb[1] - 1.1, 7.5, 13.5, (30, 40, 70), (30, 40, 70), outline=False, shadow=False)
        for q in range(6):
            cv.d.point(fp(S, 0.1 + 0.15 * q, 0.5), fill=(255, 220, 90))
    part("anna-scoreboard", (sb[0] - 10, sb[1] - 2, sb[0] + 10, sb[1] + 2), 18, scoreboard)
    # entrance plaza on the west with parked two-wheelers and a few people
    plaza = rings[-1].buffer(14).difference(rings[-1].buffer(3)).intersection(sbox(outer.bounds[0] - 60, ccy - 40, ccx, ccy + 40))
    if not plaza.is_empty:
        scatter_life("anna-plaza", plaza, [], 74, cell=10, p=0.5, people=(1, 3), stalls_p=0.15, autos_p=0.05, cows_p=0, trees_p=0.1, scooters_p=0.4)


# ------------------------------------------------------------------------------------------------ build all
ALL = dict(srirangam=srirangam, jambukeswarar=jambukeswarar, samayapuram=samayapuram, vayalur=vayalur, woraiyur=woraiyur,
           lourdes=lourdes, rockfort=rockfort, teppakulam=teppakulam, anna=anna_stadium,
           erumbeeswarar=lambda: hill("erum", 10.7927, 78.7674, 70, 45, 34, 21),
           goldenrock=lambda: hill("golden", 10.7840, 78.7214, 65, 38, 30, 22), bridges=bridges, flyovers=flyovers, amma=amma_mandapam)


def bake(names=None):
    PARTS.clear(); HIDE.clear(); DECKS.clear(); FLY_HIDE.clear()
    for k, fn in ALL.items():
        if names and k not in names:
            continue
        n0 = len(PARTS)
        fn()
        print(f"{k}: {len(PARTS) - n0} parts", flush=True)
    return PARTS, HIDE


def save():
    bake()
    with open(OUT, "wb") as f:
        pickle.dump(dict(parts=PARTS, hide=HIDE, decks=DECKS, fly_hide=FLY_HIDE), f)
    print("saved", len(PARTS), "parts,", len(DECKS), "decks,", OUT.stat().st_size // 1024, "KB")


def load():
    with open(OUT, "rb") as f:
        d = pickle.load(f)
    return d["parts"], d["hide"]


def load_decks():
    with open(OUT, "rb") as f:
        return pickle.load(f).get("decks", [])


def load_fly_hide():
    with open(OUT, "rb") as f:
        return set(pickle.load(f).get("fly_hide", []))


def preview(name):
    """Paste the parts of one monument on a plain ground to eyeball it."""
    bake([name])
    xs0 = min(p["ox"] for p in PARTS); ys0 = min(p["oy"] for p in PARTS)
    xs1 = max(p["ox"] + p["w"] for p in PARTS); ys1 = max(p["oy"] + p["h"] for p in PARTS)
    im = Image.new("RGB", (xs1 - xs0, ys1 - ys0), (150, 170, 110))
    sh = Image.new("L", im.size, 0)
    for p in sorted(PARTS, key=lambda p: p["y"]):
        if p["shadow"]:
            sm = Image.open(io.BytesIO(p["shadow"]))
            sh.paste(255, (p["ox"] - xs0, p["oy"] - ys0), sm)
    arr = np.asarray(im, dtype=np.float32)
    arr[np.asarray(sh) > 0] *= np.array([0.78, 0.81, 0.9], dtype=np.float32)
    im = Image.fromarray(arr.astype(np.uint8))
    for p in sorted(PARTS, key=lambda p: p["y"]):
        a = Image.open(io.BytesIO(p["rgba"]))
        im.paste(a, (p["ox"] - xs0, p["oy"] - ys0), a)
    out = f"/tmp/mon_{name}.png"
    im.save(out)
    print(out, im.size)


if __name__ == "__main__":
    sys.modules.setdefault("monuments", sys.modules["__main__"])
    import civic  # noqa: F401  registers the civic landmarks in ALL
    if sys.argv[1:2] == ["preview"]:
        preview(sys.argv[2])
    else:
        save()
