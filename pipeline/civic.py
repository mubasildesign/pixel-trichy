"""Civic and industrial landmarks for Pixel Trichy: bus stands, Gandhi Market, rail platforms, the Golden Rock workshop,
the airport, BHEL and NIT. Built from the real Overture polygons where they exist and registered in monuments.ALL.
"""
from __future__ import annotations
import math
import numpy as np
from shapely.geometry import Point, Polygon, LineString, box as sbox
from shapely.ops import unary_union
from shapely import affinity

import sprites as SP
import temples as T
from art3d import shade, mix, fp, frect
import monuments as M
from monuments import part, hide_poly, _geoms, m, scatter_life, life


def _axes(poly):
    """Long and short axis unit vectors (metre frame) of a polygon's oriented bounding box, with its extents."""
    rr = poly.minimum_rotated_rectangle
    c = list(rr.exterior.coords)[:4]
    e1 = np.array([c[1][0] - c[0][0], c[1][1] - c[0][1]]); e2 = np.array([c[2][0] - c[1][0], c[2][1] - c[1][1]])
    if np.linalg.norm(e1) < np.linalg.norm(e2):
        e1, e2 = e2, e1
    L1, L2 = np.linalg.norm(e1), np.linalg.norm(e2)
    u, v = e1 / L1, e2 / L2
    return rr.centroid.x, rr.centroid.y, u, v, L1, L2


def _sprite_part(name, rect, items, zmax=14):
    """Bake a list of (kind, x, y, seed, extra) ground sprites into one sprite, farthest first."""
    def draw(cv):
        order = sorted(items, key=lambda t: -(t[1] + t[2]))
        for kind, x, y, sd, extra in order:
            X, Y = cv.P(x, y, 0)
            cv.sd.ellipse([X - 6, Y - 1, X + 2, Y + 3], fill=255)
            if kind == "person":
                SP.person(cv.d, X, Y, sd)
            elif kind == "stall":
                SP.scaled(SP.stall, cv.im, X, Y, 1.8, sd)
            elif kind in ("bus", "auto", "car", "truck", "scooter"):
                SP.scaled(SP.vehicle, cv.im, X, Y, 1.5 if kind != "bus" else 1.6, extra, kind, sd)
            elif kind == "cow":
                SP.scaled(SP.cow, cv.im, X, Y, 1.5, sd)
            elif kind == "handcart":
                SP.handcart(cv.d, X, Y, sd)
            elif kind == "tree":
                SP.tree(cv.d, X, Y, sd, ("neem", "palm", "rain")[sd % 3])
    part(name, rect, zmax, draw)


BUS_COLS = [(58, 140, 84), (232, 190, 52), (212, 72, 60), (238, 238, 232), (60, 110, 190)]


def _rect_ring(p, th, L, W):
    c, s = math.cos(th), math.sin(th)
    return [(p[0] + a * c - b * s, p[1] + a * s + b * c) for a, b in ((-L / 2, -W / 2), (L / 2, -W / 2), (L / 2, W / 2), (-L / 2, W / 2))]


def bus3d(name, p, th, col):
    ring = _rect_ring(p, th, 11.5, 2.6)
    bb = Polygon(ring).bounds

    def draw(cv):
        cv.extrude(ring, 0.5, 1.7, col, shade(col, 1.1))
        cv.extrude(_rect_ring(p, th, 11.3, 2.5), 1.7, 3.0, (70, 90, 120), shade(col, 1.0))
        cv.extrude(_rect_ring(p, th, 10.6, 2.0), 3.0, 3.3, shade(col, 1.12), shade(col, 1.2), shadow=False)
    part(name, (bb[0] - 0.5, bb[1] - 0.5, bb[2] + 0.5, bb[3] + 0.5), 5, draw)


# ------------------------------------------------------------------------------------------------ bus stands
PARTS_B = []


def bus_station(name, poly, seed, hide=True, rows_axis_long=True):
    """Asphalt yard with bay lines, rows of buses, a pillared waiting platform under a long canopy, kiosks and crowds."""
    rng = np.random.default_rng(seed)
    cx, cy, u, v, L1, L2 = _axes(poly)
    x0, y0, x1, y1 = poly.buffer(6).bounds

    def ground(cv):
        cv.ground(list(poly.buffer(1).exterior.coords), (112, 110, 114), outline=(200, 196, 184))
        # bay lines every 3.6 m along the long axis in two rows
        for sgn in (-1, 1):
            for k in range(int(L1 / 3.6) + 1):
                t = -L1 / 2 + 3.6 * k
                a = np.array([cx, cy]) + u * t + v * sgn * L2 * 0.1
                b = a + v * sgn * min(14.0, L2 * 0.32)
                if poly.contains(Point(*a)) and poly.contains(Point(*b)):
                    cv.d.line([cv.P(*a), cv.P(*b)], fill=(236, 232, 220))
    part(f"{name}-yard", (x0, y0, x1, y1), 1, ground, ground=True)
    if hide:
        hide_poly(list(poly.buffer(2).exterior.coords), 0)
    # canopied platform down the middle
    plat = LineString([np.array([cx, cy]) - u * L1 * 0.44, np.array([cx, cy]) + u * L1 * 0.44]).buffer(3.4, cap_style=2)
    pe = [tuple(p) for p in plat.exterior.coords]

    def canopy(cv):
        cv.extrude(pe, 0, 0.5, (196, 190, 176), (208, 202, 188), shadow=False)
        n = int(L1 * 0.88 / 7)
        for k in range(n + 1):
            for sgn in (-1, 1):
                p = np.array([cx, cy]) - u * L1 * 0.44 + u * (L1 * 0.88) * k / max(1, n) + v * sgn * 2.6
                cv.box(p[0] - 0.3, p[1] - 0.3, p[0] + 0.3, p[1] + 0.3, 0.5, 4.6, (210, 206, 196), (210, 206, 196), outline=False, shadow=False)
        roof = plat.buffer(1.0, cap_style=2)
        cv.extrude([tuple(p) for p in roof.exterior.coords], 4.6, 5.3, (60, 120, 170), (74, 140, 196))
    # split into short pieces so the painter order works along the platform
    k = max(1, int(L1 * 0.88 / 18))
    for q in range(k):
        a = np.array([cx, cy]) - u * L1 * 0.44 + u * (L1 * 0.88) * q / k
        b = np.array([cx, cy]) - u * L1 * 0.44 + u * (L1 * 0.88) * (q + 1) / k
        seg = LineString([a, b]).buffer(4.6, cap_style=2)
        pe_ = [tuple(p) for p in LineString([a, b]).buffer(3.4, cap_style=2).exterior.coords]
        roof_ = [tuple(p) for p in LineString([a, b]).buffer(4.4, cap_style=2).exterior.coords]

        def seg_canopy(cv, a=a, b=b, pe_=pe_, roof_=roof_):
            cv.extrude(pe_, 0, 0.5, (196, 190, 176), (208, 202, 188), shadow=False)
            ln = np.linalg.norm(b - a)
            n = max(1, int(ln / 6))
            for kk in range(n + 1):
                for sgn in (-1, 1):
                    p = a + (b - a) * kk / n + v * sgn * 2.6
                    cv.box(p[0] - 0.3, p[1] - 0.3, p[0] + 0.3, p[1] + 0.3, 0.5, 4.6, (210, 206, 196), (210, 206, 196), outline=False, shadow=False)
            cv.extrude(roof_, 4.6, 5.3, (58, 118, 168), (78, 144, 200))
        bb = seg.bounds
        part(f"{name}-canopy{q}", (bb[0], bb[1], bb[2], bb[3]), 8, seg_canopy)
    # buses in two rows facing the platform, autos and scooters, people on the platform
    items = []
    th = math.atan2(v[1], v[0])
    for sgn in (-1, 1):
        for kk in range(int(L1 / 5.0)):
            t = -L1 / 2 + 2.5 + 5.0 * kk
            for dist in (11.0, 31.0, 51.0):
                p = np.array([cx, cy]) + u * t + v * sgn * dist
                if poly.buffer(-2).contains(Point(*p)) and rng.random() < 0.55:
                    bus3d(f"{name}-b{len(PARTS_B)}", p, th, BUS_COLS[int(rng.integers(0, len(BUS_COLS)))])
                    PARTS_B.append(1)
    for _ in range(int(L1 / 6)):
        p = np.array([cx, cy]) + u * rng.uniform(-L1 * 0.45, L1 * 0.45) + v * rng.uniform(-3.0, 3.0)
        items.append(("person", p[0], p[1], int(rng.integers(0, 1 << 20)), 0))
        items.append(("person", p[0] + 0.8, p[1] + 0.5, int(rng.integers(0, 1 << 20)), 0))
    for _ in range(int(L1 / 18)):
        p = np.array([cx, cy]) + u * rng.uniform(-L1 * 0.45, L1 * 0.45) + v * rng.choice([-1, 1]) * rng.uniform(21, L2 / 2 - 2)
        if poly.buffer(-2).contains(Point(*p)):
            items.append(("auto", p[0], p[1], int(rng.integers(0, 1 << 20)), float(rng.uniform(0, 6.28))))
            items.append(("stall", p[0] + 4, p[1], int(rng.integers(0, 1 << 20)), 0))
    # chunk the sprite list along the long axis so each sprite part is local
    chunks = {}
    for it in items:
        key = int(((it[1] - cx) * u[0] + (it[2] - cy) * u[1]) // 40)
        chunks.setdefault(key, []).append(it)
    for key, lst in chunks.items():
        xs_ = [i[1] for i in lst]; ys_ = [i[2] for i in lst]
        _sprite_part(f"{name}-bus{key}", (min(xs_) - 3, min(ys_) - 3, max(xs_) + 3, max(ys_) + 3), lst, 9)


# ------------------------------------------------------------------------------------------------ Gandhi Market
PRODUCE = [((214, 50, 40), (240, 90, 70)), ((196, 120, 150), (220, 150, 176)), ((236, 200, 60), (250, 226, 110)),
           ((60, 130, 50), (96, 170, 70)), ((240, 140, 40), (255, 180, 70)), ((240, 240, 230), (255, 255, 250)), ((130, 84, 50), (160, 110, 70))]


def _heap(d, X, Y, col):
    """A 5 px heap of produce in a basket."""
    c, hi = col
    d.polygon([(X - 3, Y), (X + 3, Y), (X + 2, Y + 1), (X - 2, Y + 1)], fill=(150, 104, 58))
    d.ellipse([X - 3, Y - 3, X + 3, Y + 1], fill=c)
    d.point((X - 1, Y - 2), fill=hi); d.point((X + 1, Y - 1), fill=hi)


def market(name, poly, seed):
    """Gandhi Market: an arcade of two-storey shops round the edge with an arched gateway and clock tower, long sheds with
    pitched tin roofs inside, produce heaps along the aisles, porters, shoppers and lorries unloading at the gate."""
    rng = np.random.default_rng(seed)
    cx, cy, u, v, L1, L2 = _axes(poly)
    poly = poly.simplify(1.0)
    x0, y0, x1, y1 = poly.buffer(14).bounds

    def ground(cv):
        cv.ground(list(poly.exterior.coords), (178, 166, 146), outline=(140, 128, 110))
    part(f"{name}-ground", (x0, y0, x1, y1), 1, ground, ground=True)
    hide_poly(list(poly.buffer(2).exterior.coords), 0)
    # perimeter arcade: pieces of a 2-storey block along the edge, with gaps for gates on the long sides
    ring_out = poly.buffer(-0.5, join_style=2)
    ring_in = poly.buffer(-8.5, join_style=2)
    arcade = ring_out.difference(ring_in)
    gates = [np.array([cx, cy]) - v * L2 / 2, np.array([cx, cy]) + v * L2 / 2, np.array([cx, cy]) - u * L1 / 2]
    for g in gates:
        arcade = arcade.difference(Point(*g).buffer(7))
    pieces = list(arcade.geoms) if hasattr(arcade, "geoms") else [arcade]
    k = 0
    for pg in pieces:
        if pg.is_empty or pg.area < 30:
            continue
        # cut long arcade pieces into ~24 m blocks so the painter order works along the edge
        bx0, by0, bx1, by1 = pg.bounds
        step = 24.0
        for gx in np.arange(bx0, bx1, step):
            for gy in np.arange(by0, by1, step):
                cell = pg.intersection(sbox(gx, gy, gx + step, gy + step))
                for cp in (cell.geoms if hasattr(cell, "geoms") else [cell]):
                    if cp.geom_type != "Polygon" or cp.area < 20:
                        continue
                    ring = list(cp.exterior.coords)
                    bb = cp.bounds

                    def blk(cv, ring=ring, cp=cp):
                        cv.extrude(ring, 0, 7.5, (236, 216, 170), (196, 96, 70))
                        # arches on the street faces and the inner faces
                        pts = list(cp.exterior.coords)
                        for i in range(len(pts) - 1):
                            a_, b_ = np.array(pts[i]), np.array(pts[i + 1])
                            ln = np.linalg.norm(b_ - a_)
                            if ln < 4:
                                continue
                            n_ = int(ln // 3.2)
                            for j in range(n_):
                                p = a_ + (b_ - a_) * (j + 0.5) / n_
                                q0, q1 = cv.P(p[0], p[1], 0.3), cv.P(p[0], p[1], 2.6)
                                cv.d.line([q0, q1], fill=(120, 70, 50), width=2)
                                w0 = cv.P(p[0], p[1], 4.4); w1 = cv.P(p[0], p[1], 5.8)
                                cv.d.line([w0, w1], fill=(70, 96, 120))
                        cv.d.line([cv.P(x, y, 3.6) for x, y in pts], fill=(250, 236, 200))
                    part(f"{name}-arc{k}", (bb[0] - 1, bb[1] - 1, bb[2] + 1, bb[3] + 1), 10, blk)
                    k += 1
    # main gateway on the south long side: an arch between two piers, with a clock tower beside it
    gs = gates[0]
    th = math.atan2(u[1], u[0])

    def gate(cv):
        for sg in (-1, 1):
            p = gs + u * 5.5 * sg
            cv.box(p[0] - 1.4, p[1] - 1.4, p[0] + 1.4, p[1] + 1.4, 0, 10.5, (240, 222, 176), (200, 100, 72))
        a_ = gs - u * 5.5; b_ = gs + u * 5.5
        pts = [cv.P(*(a_ + (b_ - a_) * t), 8.0 + 2.4 * math.sin(math.pi * t)) for t in np.linspace(0, 1, 12)]
        cv.d.line(pts, fill=(240, 222, 176), width=3)
        top = [cv.P(*a_, 10.5), cv.P(*b_, 10.5)]
        cv.d.line(top, fill=(200, 100, 72), width=2)
        c = gs + u * 9.5
        cv.box(c[0] - 1.8, c[1] - 1.8, c[0] + 1.8, c[1] + 1.8, 0, 16, (240, 224, 186), (240, 224, 186))
        S, W_, _ = cv.box(c[0] - 2.2, c[1] - 2.2, c[0] + 2.2, c[1] + 2.2, 16, 19, (236, 216, 170), (236, 216, 170))
        for q in (S, W_):
            mx, my = fp(q, 0.5, 0.5)
            cv.d.ellipse([mx - 2, my - 2, mx + 2, my + 2], fill=(252, 250, 240), outline=(60, 50, 40))
            cv.d.line([(mx, my), (mx, my - 1)], fill=(30, 30, 30)); cv.d.line([(mx, my), (mx + 1, my)], fill=(30, 30, 30))
        cv.frustum(c[0], c[1], 2.4, 2.4, 19, 0.3, 0.3, 23, (200, 100, 72), (200, 100, 72))
    gb = Point(*gs).buffer(14).bounds
    part(f"{name}-gate", gb, 26, gate)
    # inner sheds: long pitched tin roofs on posts, in rows along the long axis
    inner = poly.buffer(-12, join_style=2)
    tins = [(176, 180, 184), (150, 96, 76), (190, 192, 190), (164, 110, 86)]
    items = []
    rows = int((L2 - 24) // 13)
    for r in range(rows):
        vv = -L2 / 2 + 12 + 6.5 + 13 * r
        n = int((L1 - 24) // 20)
        for c in range(n):
            tt = -L1 / 2 + 12 + 10 + 20 * c
            a_ = np.array([cx, cy]) + u * (tt - 8.5) + v * vv
            b_ = np.array([cx, cy]) + u * (tt + 8.5) + v * vv
            sh = LineString([a_, b_]).buffer(3.6, cap_style=2)
            if not inner.contains(sh):
                continue
            col = tins[(r + c) % len(tins)]
            bb = sh.bounds

            def shed(cv, a_=a_, b_=b_, col=col):
                P = cv.P
                for t in np.linspace(0, 1, 4):
                    for sg in (-1, 1):
                        p = a_ + (b_ - a_) * t + v * 3.0 * sg
                        cv.d.line([P(*p, 0), P(*p, 3.4)], fill=(96, 84, 74))
                # two roof planes meeting at the ridge, the near one lit
                e0, e1 = a_ - v * 3.8, b_ - v * 3.8
                f0, f1 = a_ + v * 3.8, b_ + v * 3.8
                r0, r1 = a_, b_
                far = [P(*f0, 3.4), P(*f1, 3.4), P(*r1, 5.2), P(*r0, 5.2)]
                near = [P(*e0, 3.4), P(*e1, 3.4), P(*r1, 5.2), P(*r0, 5.2)]
                fsum = sum(f0) + sum(f1); esum = sum(e0) + sum(e1)
                back, front = (far, near) if fsum > esum else (near, far)
                cv.d.polygon(back, fill=shade(col, 0.82), outline=shade(col, 0.6))
                cv.d.polygon(front, fill=col, outline=shade(col, 0.66))
                for t in np.linspace(0.1, 0.9, 7):
                    q0 = (front[0][0] + (front[1][0] - front[0][0]) * t, front[0][1] + (front[1][1] - front[0][1]) * t)
                    q1 = (front[3][0] + (front[2][0] - front[3][0]) * t, front[3][1] + (front[2][1] - front[3][1]) * t)
                    cv.d.line([q0, q1], fill=shade(col, 0.88))
                cv.d.line([P(*r0, 5.2), P(*r1, 5.2)], fill=shade(col, 1.15))
                # produce heaps under the eaves on both sides
                for sg in (-1, 1):
                    for j in range(7):
                        p = a_ + (b_ - a_) * (j + 0.5) / 7 + v * 2.2 * sg
                        X, Y = P(*p, 0)
                        _heap(cv.d, X, Y, PRODUCE[(j * 3 + int(sum(a_)) + (sg > 0)) % len(PRODUCE)])
                cv.sd.polygon([P(*e0, 0), P(*e1, 0), P(*f1, 0), P(*f0, 0)], fill=255)
            part(f"{name}-shed{r}-{c}", (bb[0] - 1, bb[1] - 1, bb[2] + 1, bb[3] + 1), 8, shed)
            # shoppers walking the aisle in front of the shed (in lines, not a blob), porters with head loads
            for j in range(int(rng.integers(3, 6))):
                p = a_ + (b_ - a_) * rng.random() - v * rng.uniform(5.0, 7.5)
                items.append(("person", p[0], p[1], int(rng.integers(0, 1 << 20)), 0))
            if rng.random() < 0.18:
                p = a_ + (b_ - a_) * rng.random() - v * 6.2
                items.append(("handcart", p[0], p[1], int(rng.integers(0, 1 << 20)), 0))
    # lorries unloading at the side gate
    for k in range(3):
        p = gates[2] + u * (6 + k * 1.0) + v * (k - 1) * 4.5
        items.append(("truck", p[0], p[1], int(rng.integers(0, 1 << 20)), th))
    for k in range(6):
        p = gates[0] - v * rng.uniform(3, 10) + u * rng.uniform(-8, 8)
        items.append(("person", p[0], p[1], int(rng.integers(0, 1 << 20)), 0))
    chunks = {}
    for it in items:
        key = (int(((it[1] - cx) * u[0] + (it[2] - cy) * u[1]) // 40), int(((it[1] - cx) * v[0] + (it[2] - cy) * v[1]) // 40))
        chunks.setdefault(key, []).append(it)
    for key, lst in chunks.items():
        xs_ = [i[1] for i in lst]; ys_ = [i[2] for i in lst]
        _sprite_part(f"{name}-life{key[0]}_{key[1]}", (min(xs_) - 3, min(ys_) - 3, max(xs_) + 3, max(ys_) + 3), lst, 8)


# ------------------------------------------------------------------------------------------------ rail platforms
def platforms(name, polys, seed):
    """Canopies and crowds over the station platform polygons."""
    rng = np.random.default_rng(seed)
    items = []
    for q, pl in enumerate(polys):
        if pl.area < 300:
            continue
        cx, cy, u, v, L1, L2 = _axes(pl)
        if L2 > 14:
            continue
        pieces = max(1, int(L1 // 20))
        for k in range(pieces):
            a = np.array([cx, cy]) + u * (-L1 / 2 + L1 * k / pieces)
            b = np.array([cx, cy]) + u * (-L1 / 2 + L1 * (k + 1) / pieces)
            seg = LineString([a, b]).buffer(max(2.0, L2 / 2 - 0.2), cap_style=2)
            roof = LineString([a, b]).buffer(max(2.5, L2 / 2 + 0.8), cap_style=2)
            pe_ = [tuple(p) for p in seg.exterior.coords]
            re_ = [tuple(p) for p in roof.exterior.coords]
            bb = roof.bounds

            def can(cv, a=a, b=b, pe_=pe_, re_=re_, hw=max(2.0, L2 / 2 - 0.5)):
                cv.extrude(pe_, 0, 0.6, (200, 194, 182), (212, 206, 194), shadow=False)
                nn = max(1, int(np.linalg.norm(b - a) / 6))
                for kk in range(nn + 1):
                    for sgn in (-1, 1):
                        p = a + (b - a) * kk / nn + v * sgn * hw * 0.8
                        cv.box(p[0] - 0.25, p[1] - 0.25, p[0] + 0.25, p[1] + 0.25, 0.6, 4.6, (214, 210, 200), (214, 210, 200), outline=False, shadow=False)
                cv.extrude(re_, 4.6, 5.2, (176, 70, 56), (200, 90, 72))
            part(f"{name}-can{q}-{k}", (bb[0], bb[1], bb[2], bb[3]), 8, can)
        for _ in range(int(L1 / 5)):
            p = np.array([cx, cy]) + u * rng.uniform(-L1 / 2, L1 / 2) + v * rng.uniform(-L2 / 3, L2 / 3)
            items.append(("person", p[0], p[1], int(rng.integers(0, 1 << 20)), 0))
    chunks = {}
    for it in items:
        key = (int(it[1] // 60), int(it[2] // 60))
        chunks.setdefault(key, []).append(it)
    for key, lst in chunks.items():
        xs_ = [i[1] for i in lst]; ys_ = [i[2] for i in lst]
        _sprite_part(f"{name}-crowd{key[0]}_{key[1]}", (min(xs_) - 3, min(ys_) - 3, max(xs_) + 3, max(ys_) + 3), lst, 8)


# ------------------------------------------------------------------------------------------------ factories
def shed_row(name, cx, cy, u, v, n, w=34, d=44, gap=6, saw=True, col=(226, 220, 204), seed=1):
    """Row of sawtooth-roofed factory bays."""
    rng = np.random.default_rng(seed)
    for k in range(n):
        c = np.array([cx, cy]) + u * (k - (n - 1) / 2) * (w + gap)
        a = c - u * w / 2 - v * d / 2; b = c + u * w / 2 + v * d / 2
        ring = [tuple(a), tuple(a + u * w), tuple(a + u * w + v * d), tuple(a + v * d)]
        bb = unary_union([Polygon(ring)]).bounds

        def draw(cv, ring=ring, c=c):
            cv.extrude(ring, 0, 8.5, col, (176, 80, 62))
            # sawtooth ridges and skylights
            P = cv.P
            nteeth = 5
            for t in range(nteeth):
                p0 = np.array(ring[0]) + v * (d * t / nteeth)
                p1 = p0 + u * w
                q0 = p0 + v * d / nteeth * 0.5
                q1 = q0 + u * w
                cv.d.polygon([P(*p0, 8.5), P(*p1, 8.5), P(*q1, 11.5), P(*q0, 11.5)], fill=(190, 92, 70), outline=(120, 56, 44))
                cv.d.polygon([P(*q0, 11.5), P(*q1, 11.5), P(*(q1 + v * d / nteeth * 0.5), 8.5), P(*(q0 + v * d / nteeth * 0.5), 8.5)], fill=(150, 190, 214), outline=(100, 128, 150))
        part(f"{name}-bay{k}", (bb[0] - 1, bb[1] - 1, bb[2] + 1, bb[3] + 1), 14, draw)


def chimney(name, x, y, H=46.0, r=2.2):
    def draw(cv):
        cv.frustum(x, y, r * 1.5, r * 1.5, 0, r * 0.8, r * 0.8, H, (176, 72, 56), (110, 60, 50))
        cv.frustum(x, y, r * 0.8, r * 0.8, H, r * 0.85, r * 0.85, H + 1.2, (46, 40, 40), (30, 28, 30), shadow=False)
    part(name, (x - 5, y - 5, x + 5, y + 5), H + 4, draw)


def water_tower(name, x, y, H=24.0):
    def draw(cv):
        for dx, dy in ((-2, -2), (2, -2), (2, 2), (-2, 2)):
            cv.box(x + dx - 0.4, y + dy - 0.4, x + dx + 0.4, y + dy + 0.4, 0, H, (190, 190, 186), (190, 190, 186), outline=False, shadow=False)
        cv.frustum(x, y, 5, 5, H, 6, 6, H + 7, (214, 214, 208), (200, 200, 194))
        cv.frustum(x, y, 6, 6, H + 7, 2.5, 2.5, H + 10, (60, 120, 170), (80, 140, 190))
    part(name, (x - 7, y - 7, x + 7, y + 7), H + 14, draw)


def loco_yard(name, cx, cy, u, v, n=4, seed=2):
    """A few diesel locomotives and wagons on short sidings (pure sprites)."""
    rng = np.random.default_rng(seed)
    cols = [(46, 96, 168), (176, 60, 52), (52, 54, 60), (214, 168, 46)]
    for k in range(n):
        base = np.array([cx, cy]) + v * (k - (n - 1) / 2) * 11
        L = 36
        a = base - u * L / 2; b = base + u * L / 2
        ring = [tuple(a - v * 1.6), tuple(b - v * 1.6), tuple(b + v * 1.6), tuple(a + v * 1.6)]
        col = cols[k % len(cols)]
        bb = Polygon(ring).bounds

        def draw(cv, ring=ring, col=col, a=a, b=b):
            cv.extrude(ring, 0.6, 4.2, col, shade(col, 1.15))
            for j in range(1, 5):
                p = a + (b - a) * j / 5
                q = [cv.P(p[0] - v[0] * 1.6, p[1] - v[1] * 1.6, 2.4), cv.P(p[0] - v[0] * 1.6, p[1] - v[1] * 1.6, 3.6)]
                cv.d.line(q, fill=(240, 236, 226))
        part(f"{name}-wagon{k}", (bb[0] - 1, bb[1] - 1, bb[2] + 1, bb[3] + 1), 8, draw)


# ------------------------------------------------------------------------------------------------ the places
def junction():
    pl = [g for g, n, s, c in _geoms("infrastructure", "class='platform' and ST_X(ST_Centroid(geometry)) between 78.678 and 78.692 and ST_Y(ST_Centroid(geometry)) between 10.788 and 10.800")]
    platforms("tpj", pl, 5)
    # forecourt: taxis, autos, crowds in front of the station
    cx, cy = m(10.7941, 78.6854)
    scatter_life("tpj-fore", sbox(cx - 90, cy - 70, cx + 90, cy + 70), [], 9, cell=14, p=0.18, people=(2, 6), stalls_p=0.2, autos_p=0.2, cows_p=0.02, trees_p=0.08, scooters_p=0.15)


def central_bus():
    bs = [g for g, n, s, c in _geoms("infrastructure", "class='bus_station' and names.primary='Trichy Central Bus Stand'")]
    for k, g in enumerate(bs):
        if g.geom_type == "MultiPolygon":
            g = max(g.geoms, key=lambda a: a.area)
        bus_station("cbs", g, 11)


def chatram():
    bs = [g for g, n, s, c in _geoms("infrastructure", "class='bus_station' and names.primary='Chatram bus stand'")]
    for g in bs:
        if g.geom_type == "MultiPolygon":
            g = max(g.geoms, key=lambda a: a.area)
        bus_station("chatram", g, 12)


def gandhi_market():
    ms = [g for g, n, s, c in _geoms("land_use", "names.primary='Gandhi Market'")]
    for g in ms:
        if g.geom_type == "MultiPolygon":
            g = max(g.geoms, key=lambda a: a.area)
        market("gandhi", g, 13)


def golden_rock_works():
    cx, cy = m(10.7898, 78.7222)
    u = np.array([0.8, -0.6]); v = np.array([0.6, 0.8])
    c0 = np.array([cx, cy])
    hide_poly(list(Point(cx, cy).buffer(170).exterior.coords), 0)
    part("gr-yard", (cx - 190, cy - 190, cx + 190, cy + 190), 1,
         lambda cv: cv.ground(list(Point(cx, cy).buffer(168).exterior.coords), (178, 156, 124), outline=(150, 128, 100)), ground=True)
    for r, off in enumerate((-70, 0, 70)):
        c = c0 + v * off
        shed_row(f"gr-row{r}", c[0], c[1], u, v, 4, w=36, d=44, gap=6, seed=r + 3)
    for k, (du, dv) in enumerate(((-110, -90), (110, 100), (-120, 80), (120, -60))):
        p = c0 + u * du + v * dv
        chimney(f"gr-chim{k}", p[0], p[1], 40 + 6 * k)
    water_tower("gr-wt", *(c0 + u * 20 - v * 110))
    loco_yard("gr-loco", *(c0 - u * 20 + v * 130), u, v, n=4)
    scatter_life("gr", Point(cx, cy).buffer(160), [Point(cx, cy).buffer(0.1)], 21, cell=18, p=0.12, people=(1, 4), stalls_p=0.02, autos_p=0.08, cows_p=0.01, trees_p=0.15, scooters_p=0.1)


def bhel():
    cx, cy = m(10.7791, 78.7975)
    u = np.array([1.0, 0.0]); v = np.array([0.0, 1.0])
    c0 = np.array([cx, cy])
    hide_poly(list(Point(cx, cy).buffer(120).exterior.coords), 0)
    part("bhel-yard", (cx - 140, cy - 140, cx + 140, cy + 140), 1,
         lambda cv: cv.ground(list(Point(cx, cy).buffer(118).exterior.coords), (186, 170, 142), outline=(150, 134, 108)), ground=True)
    shed_row("bhel-row0", cx, cy - 40, u, v, 3, w=40, d=52, gap=8, seed=7)
    shed_row("bhel-row1", cx, cy + 40, u, v, 3, w=40, d=52, gap=8, seed=8)
    chimney("bhel-c0", cx - 90, cy, 60, 3.0); chimney("bhel-c1", cx + 92, cy + 20, 52, 2.6)
    water_tower("bhel-wt", cx, cy + 100, 28)
    scatter_life("bhel", Point(cx, cy).buffer(110), [], 22, cell=16, p=0.1, people=(1, 4), stalls_p=0.03, autos_p=0.08, cows_p=0.01, trees_p=0.2, scooters_p=0.1)


def airport():
    cx, cy = m(10.7653, 78.7097)
    # runway, taxiways and aprons from the mapped airport features
    rows = _geoms("infrastructure", "subtype='airport' and class in ('runway','taxiway','taxilane','apron')")
    near = [(g, c) for g, n, s, c in rows if Point(cx, cy).distance(g.centroid) < 3500]
    x0, y0, x1, y1 = cx - 3600, cy - 3600, cx + 3600, cy + 3600
    layers = []
    for g, c in near:
        if c == "apron":
            layers.append((g, (150, 148, 150), (124, 122, 124)))
        elif c == "runway":
            layers.append((g.buffer(23, cap_style=2), (86, 86, 92), (60, 60, 66)))
        else:
            layers.append((g.buffer(8 if c == "taxiway" else 5, cap_style=2), (112, 110, 114), (96, 94, 98)))
    for q, (g, col, edge) in enumerate(layers):
        polys = list(g.geoms) if hasattr(g, "geoms") else [g]
        for pi, pg in enumerate(polys):
            if pg.geom_type != "Polygon" or pg.is_empty:
                continue
            bb = pg.bounds
            part(f"airport-g{q}-{pi}", (bb[0] - 4, bb[1] - 4, bb[2] + 4, bb[3] + 4), 1,
                 lambda cv, pg=pg, col=col, edge=edge: cv.ground(list(pg.exterior.coords), col, holes=[list(h.coords) for h in pg.interiors], outline=edge), ground=True)
    # centre line and thresholds on the runway
    for g, c in near:
        if c == "runway":
            parts_ = list(g.geoms) if hasattr(g, "geoms") else [g]
            for ln in parts_:
                if ln.geom_type != "LineString":
                    continue
                L = ln.length
                bb = ln.buffer(3).bounds

                def mark(cv, ln=ln, L=L):
                    for k in range(int(L // 60)):
                        a = ln.interpolate(k * 60 + 8); b = ln.interpolate(k * 60 + 38)
                        cv.d.line([cv.P(a.x, a.y), cv.P(b.x, b.y)], fill=(244, 244, 238), width=2)
                part("airport-runway-marks", (bb[0], bb[1], bb[2], bb[3]), 1, mark, ground=True)
    # the real terminal footprints (new terminal, integrated terminal, cargo terminal) as glass-and-steel blocks
    terms = [g for g, n, s, cl in _geoms("buildings", "names.primary like 'Tiruchirapalli%Terminal' or names.primary like 'Tiruchirappalli%Terminal'")]
    tcx = tcy = None
    for q, g in enumerate(terms):
        polys = list(g.geoms) if hasattr(g, "geoms") else [g]
        for pi, pg in enumerate(polys):
            ring = list(pg.simplify(1.0).exterior.coords)
            bb = pg.bounds
            if pg.area > 20000:
                tcx, tcy = pg.centroid.x, pg.centroid.y
            hide_poly(ring, 4)

            def draw(cv, ring=ring, pg=pg):
                cv.extrude(ring, 0, 8.5, (232, 234, 230), (212, 210, 204))
                inner = pg.buffer(-3.0)
                if not inner.is_empty and inner.geom_type == "Polygon":
                    cv.extrude(list(inner.exterior.coords), 8.5, 9.4, (196, 198, 200), (226, 224, 218))
                cv.extrude(list(pg.buffer(5, join_style=2).exterior.coords), 6.2, 7.0, (214, 218, 222), (226, 230, 232), shadow=False, holes=[list(pg.exterior.coords)])
            part(f"airport-term{q}-{pi}", (bb[0] - 6, bb[1] - 6, bb[2] + 6, bb[3] + 6), 14, draw)
    if tcx is None:
        tcx, tcy = cx, cy
    # control tower beside the terminal
    tx_, ty_ = tcx + 140, tcy - 40

    def tower(cv):
        x, y = tx_, ty_
        cv.box(x - 3, y - 3, x + 3, y + 3, 0, 26, (232, 230, 222), (232, 230, 222))
        cv.frustum(x, y, 5.5, 5.5, 26, 7.5, 7.5, 32, (96, 140, 184), (120, 164, 206))
        cv.box(x - 8, y - 8, x + 8, y + 8, 32, 33, (222, 222, 216), (222, 222, 216))
    part("airport-tower", (tx_ - 10, ty_ - 10, tx_ + 10, ty_ + 10), 38, tower)

    def plane(px, py, ang, col, nm):
        def draw(cv):
            c_, s_ = math.cos(ang), math.sin(ang)
            f = lambda a, b: (px + a * c_ - b * s_, py + a * s_ + b * c_)
            body = [f(-19, -2.4), f(19, -2.4), f(19, 2.4), f(-19, 2.4)]
            cv.extrude(body, 2.4, 7.4, (240, 240, 236), (252, 252, 248))
            cv.d.polygon([cv.P(*f(-4, -2.4), 3.2), cv.P(*f(-4, -24), 3.2), cv.P(*f(2, -24), 3.2), cv.P(*f(6, -2.4), 3.2)], fill=(214, 218, 224), outline=(150, 150, 156))
            cv.d.polygon([cv.P(*f(-4, 2.4), 3.2), cv.P(*f(-4, 24), 3.2), cv.P(*f(2, 24), 3.2), cv.P(*f(6, 2.4), 3.2)], fill=(214, 218, 224), outline=(150, 150, 156))
            cv.d.polygon([cv.P(*f(-19, 0), 7.4), cv.P(*f(-19, 0), 15), cv.P(*f(-12, 0), 7.4)], fill=col)
            cv.d.line([cv.P(*f(-16, -2.5), 5), cv.P(*f(14, -2.5), 5)], fill=col)
        part(nm, (px - 26, py - 26, px + 26, py + 26), 18, draw)
    apr = [g for g, c_ in near if c_ == "apron" and g.area > 40000]
    cols = [(200, 60, 50), (40, 90, 170), (230, 160, 40), (60, 140, 90)]
    k = 0
    for g in apr:
        minx, miny, maxx, maxy = g.bounds
        for _ in range(6):
            px, py = np.random.default_rng(k).uniform(minx, maxx), np.random.default_rng(k + 100).uniform(miny, maxy)
            k += 1
            if g.buffer(-30).contains(Point(px, py)) and all(Point(px, py).distance(Point(a, b)) > 60 for a, b in [(p.x, p.y) for p in []]):
                plane(px, py, 1.57 + (k % 3) * 0.1, cols[k % len(cols)], f"airport-plane{k}")
    scatter_life("airport", Point(tcx, tcy).buffer(130), [t.buffer(8) for t in terms], 23, cell=14, p=0.12, people=(1, 4), stalls_p=0.0, autos_p=0.2, cows_p=0, trees_p=0.1, scooters_p=0.05)


# ------------------------------------------------------------------------------------------------ domes and vaults
def dome(cv, cx, cy, R, z0, col, rings=9, sides=24):
    """Hemisphere as stacked rings (lit from the east), standing on z0."""
    prev_r = R
    for k in range(rings):
        phi0, phi1 = (math.pi / 2) * k / rings, (math.pi / 2) * (k + 1) / rings
        r1 = R * math.cos(phi1)
        za, zb = z0 + R * math.sin(phi0), z0 + R * math.sin(phi1)
        c = shade(col, 0.82 + 0.22 * k / rings)
        ring = list(Point(cx, cy).buffer(max(0.3, prev_r), quad_segs=sides // 4).exterior.coords)
        cv.extrude(ring, za, zb, c, shade(col, 1.08), outline=False, shadow=(k == 0))
        prev_r = r1
    X, Y = cv.P(cx - R * 0.25, cy - R * 0.25, z0 + R * 0.8)
    cv.d.point((X, Y), fill=(255, 255, 255))


def vault(cv, a, b, w, z0, rise, col, n=8):
    """Barrel-vault canopy over the strip a-b (metres), w wide, springing at z0."""
    a = np.asarray(a, float); b = np.asarray(b, float)
    ab = b - a; L = np.linalg.norm(ab) or 1.0
    u = ab / L; v = np.array([-u[1], u[0]])
    strips = []
    for i in range(n):
        t0, t1 = math.pi * i / n, math.pi * (i + 1) / n
        o0, o1 = math.cos(t0) * w / 2, math.cos(t1) * w / 2
        h0, h1 = z0 + rise * math.sin(t0), z0 + rise * math.sin(t1)
        q = [cv.P(*(a + v * o0), h0), cv.P(*(b + v * o0), h0), cv.P(*(b + v * o1), h1), cv.P(*(a + v * o1), h1)]
        nrm = v * math.cos((t0 + t1) / 2)                         # horizontal part of the strip normal
        lit = 0.86 + 0.14 * max(-1.0, min(1.0, -(nrm[0] + nrm[1]) / 1.0)) + 0.06 * math.sin((t0 + t1) / 2)
        strips.append((sum(p[1] for p in q), q, lit))
    for _, q, lit in sorted(strips, key=lambda s: s[0]):
        cv.d.polygon(q, fill=shade(col, lit))
    cv.d.line([cv.P(*(a + v * w / 2), z0), cv.P(*(b + v * w / 2), z0)], fill=shade(col, 0.7))
    cv.d.line([cv.P(*(a - v * w / 2), z0), cv.P(*(b - v * w / 2), z0)], fill=shade(col, 0.7))


# ------------------------------------------------------------------------------------------------ Panjappur terminus
def panjappur():
    """Panjappur Integrated Bus Terminus on the Madurai highway: long platforms under white barrel-vault canopies with
    rows of buses, a glass terminal hall with a dome, lawns, trees and big car parks with lamp posts."""
    rows = _geoms("infrastructure", "class='bus_station' and names.primary='Panjappur Integrated Bus Terminus'")
    g = max((r[0] for r in rows), key=lambda a: a.area)
    if g.geom_type == "MultiPolygon":
        g = max(g.geoms, key=lambda a: a.area)
    g = g.simplify(2.0)
    rng = np.random.default_rng(91)
    cx, cy, u, v, L1, L2 = _axes(g)
    # the terminal faces the highway: put it on the side of the short axis nearest the south-west (towards the viewer)
    if (v[0] + v[1]) > 0:
        v = -v
    c0 = np.array([cx, cy])
    x0, y0, x1, y1 = g.buffer(10).bounds
    yard = g.buffer(-16)
    NP = 6
    span = L2 - 140

    def ground(cv):
        cv.ground(list(g.exterior.coords), (126, 168, 92))
        cv.ground(list(yard.exterior.coords), (108, 108, 114), outline=(200, 196, 184))
        # car park bays in the front band
        for k in range(int(L1 * 0.8 / 3.0)):
            t = -L1 * 0.4 + 3.0 * k
            for vv in (L2 / 2 - 30, L2 / 2 - 52):
                a = c0 + u * t + v * vv; b = a + v * 5
                if yard.contains(Point(*a)) and yard.contains(Point(*b)):
                    cv.d.line([cv.P(*a), cv.P(*b)], fill=(230, 228, 216))
        # kerbed lawn medians half way between platforms
        for pi in range(NP + 1):
            vv = L2 / 2 - 120 - span * pi / NP
            a = c0 + v * vv - u * L1 * 0.38; b = c0 + v * vv + u * L1 * 0.38
            med = LineString([a, b]).buffer(3.0, cap_style=2).intersection(yard.buffer(-4))
            if not med.is_empty and med.geom_type == "Polygon":
                cv.ground(list(med.exterior.coords), (118, 168, 86), outline=(214, 210, 198))
    part("panj-ground", (x0, y0, x1, y1), 1, ground, ground=True)
    hide_poly(list(g.buffer(4).exterior.coords), 0)
    # terminal hall on the front band, middle
    tc = c0 + v * (L2 / 2 - 80)
    TL, TW = min(150.0, L1 * 0.36), 34.0
    tring = [tuple(tc - u * TL / 2 - v * TW / 2), tuple(tc + u * TL / 2 - v * TW / 2), tuple(tc + u * TL / 2 + v * TW / 2), tuple(tc - u * TL / 2 + v * TW / 2)]

    def hall(cv):
        cv.extrude(tring, 0, 13.0, (226, 214, 186), (214, 210, 200))
        # glass curtain wall with mullions on the faces that face the viewer, a jaali panel and the name band
        for i in range(4):
            p0, p1 = np.array(tring[i]), np.array(tring[(i + 1) % 4])
            nrm = np.array([p1[1] - p0[1], -(p1[0] - p0[0])])
            if -(nrm[0] + nrm[1]) <= 0:
                continue
            ln = np.linalg.norm(p1 - p0)
            q = [cv.P(*p0, 1.0), cv.P(*p1, 1.0), cv.P(*p1, 10.5), cv.P(*p0, 10.5)]
            cv.d.polygon(q, fill=(84, 128, 160))
            for j in range(int(ln // 3)):
                t = j / max(1, int(ln // 3))
                pp = p0 + (p1 - p0) * t
                cv.d.line([cv.P(*pp, 1.0), cv.P(*pp, 10.5)], fill=(150, 186, 206))
            cv.d.line([cv.P(*p0, 5.6), cv.P(*p1, 5.6)], fill=(150, 186, 206))
            jp0 = p0 + (p1 - p0) * 0.62; jp1 = p0 + (p1 - p0) * 0.92
            jq = [cv.P(*jp0, 1.0), cv.P(*jp1, 1.0), cv.P(*jp1, 12.0), cv.P(*jp0, 12.0)]
            cv.d.polygon(jq, fill=(232, 224, 206))
            for yy in range(int(min(p[1] for p in jq)), int(max(p[1] for p in jq)), 2):
                cv.d.line([(min(p[0] for p in jq) + 1, yy), (max(p[0] for p in jq) - 1, yy)], fill=(206, 196, 176))
            np0 = p0 + (p1 - p0) * 0.66; np1 = p0 + (p1 - p0) * 0.88
            cv.d.line([cv.P(*np0, 11.4), cv.P(*np1, 11.4)], fill=(255, 214, 120), width=2)
        # canopy along the front drop-off
        fr = [tuple(tc - u * TL / 2 - v * (TW / 2 + 9)), tuple(tc + u * TL / 2 - v * (TW / 2 + 9)), tuple(tc + u * TL / 2 - v * (TW / 2 - 1)), tuple(tc - u * TL / 2 - v * (TW / 2 - 1))]
        for j in range(9):
            pp = tc - u * TL / 2 + u * TL * j / 8 - v * (TW / 2 + 8)
            cv.d.line([cv.P(*pp, 0), cv.P(*pp, 6.8)], fill=(200, 200, 196))
        cv.extrude(fr, 6.8, 7.3, (236, 236, 232), (246, 246, 242), shadow=False)
        dome(cv, *(tc + u * TL * 0.22), 7.5, 13.0, (210, 226, 236))
    hb = Polygon(tring).buffer(12).bounds
    part("panj-hall", hb, 28, hall)
    # platforms with vault canopies behind the hall, in pieces for the painter
    for pi in range(NP):
        vv = L2 / 2 - 120 - span * (pi + 0.5) / NP
        PL = L1 * 0.78 - abs(pi - (NP - 1) / 2) * 18
        n = max(1, int(PL // 30))
        for k in range(n):
            a = c0 + v * vv + u * (-PL / 2 + PL * k / n)
            b = c0 + v * vv + u * (-PL / 2 + PL * (k + 1) / n)
            if not yard.contains(Point(*a)) or not yard.contains(Point(*b)):
                continue
            ring = [tuple(a - v * 5), tuple(b - v * 5), tuple(b + v * 5), tuple(a + v * 5)]
            bb = Polygon(ring).buffer(2).bounds

            def plat(cv, a=a, b=b, ring=ring):
                cv.extrude(ring, 0, 0.5, (196, 190, 178), (214, 208, 196), shadow=False)
                for j in range(4):
                    for sg in (-1, 1):
                        pp = a + (b - a) * j / 3 + v * 3.6 * sg
                        cv.d.line([cv.P(*pp, 0.5), cv.P(*pp, 6.0)], fill=(206, 206, 202))
                vault(cv, a, b, 13.0, 6.0, 2.6, (246, 246, 242))
                Xs = [cv.P(*p, 0) for p in (a - v * 6.5, b - v * 6.5, b + v * 6.5, a + v * 6.5)]
                from art3d import SHADOW_DIR
                cv.sd.polygon([(x + SHADOW_DIR[0] * 16, y + SHADOW_DIR[1] * 16) for x, y in Xs], fill=255)
            part(f"panj-plat{pi}-{k}", bb, 11, plat)
            # buses nose-in along both sides of the platform
            th = math.atan2(v[1], v[0])
            for j in range(int(np.linalg.norm(b - a) // 4.2)):
                for sg in (-1, 1):
                    if rng.random() < 0.38:
                        p = a + u * (2.1 + 4.2 * j) + v * (12.5 * sg)
                        if yard.contains(Point(*p)):
                            bus3d(f"panj-b{len(PARTS_B)}", p, th, BUS_COLS[int(rng.integers(0, len(BUS_COLS)))])
                            PARTS_B.append(1)
    # cars in the front car park, lamp posts, trees round the edge, people at the hall
    items = []
    for k in range(int(L1 * 0.8 / 3.0)):
        t = -L1 * 0.4 + 1.5 + 3.0 * k
        for vv in (L2 / 2 - 27.5, L2 / 2 - 49.5):
            if rng.random() < 0.62:
                p = c0 + u * t + v * vv
                if yard.contains(Point(*p)):
                    items.append(("car", p[0], p[1], int(rng.integers(0, 1 << 20)), math.atan2(v[1], v[0])))
    for pi in range(NP + 1):
        vv = L2 / 2 - 120 - span * pi / NP
        for k in range(int(L1 * 0.76 / 12)):
            p = c0 + v * vv + u * (-L1 * 0.38 + 6 + 12 * k)
            if yard.buffer(-6).contains(Point(*p)):
                items.append(("tree", p[0], p[1], int(rng.integers(0, 1 << 20)), 0))
    edge = g.buffer(-10).exterior
    for k in range(int(edge.length // 16)):
        p = edge.interpolate(k * 16 + rng.uniform(-3, 3))
        items.append(("tree", p.x, p.y, int(rng.integers(0, 1 << 20)), 0))
    for k in range(40):
        p = tc - v * (TW / 2 + rng.uniform(2, 14)) + u * rng.uniform(-TL / 2, TL / 2)
        items.append(("person", p[0], p[1], int(rng.integers(0, 1 << 20)), 0))
    for k in range(10):
        p = tc - v * (TW / 2 + rng.uniform(12, 20)) + u * rng.uniform(-TL / 2, TL / 2)
        items.append(("auto", p[0], p[1], int(rng.integers(0, 1 << 20)), float(math.atan2(u[1], u[0]))))
    chunks = {}
    for it in items:
        key = (int(it[1] // 60), int(it[2] // 60))
        chunks.setdefault(key, []).append(it)
    for key, lst in chunks.items():
        xs_ = [i[1] for i in lst]; ys_ = [i[2] for i in lst]
        _sprite_part(f"panj-life{key[0]}_{key[1]}", (min(xs_) - 3, min(ys_) - 3, max(xs_) + 3, max(ys_) + 3), lst, 14)
    for k in range(int(L1 * 0.8 / 24)):
        p = c0 + u * (-L1 * 0.4 + 24 * k) + v * (L2 / 2 - 39)

        def lamp(cv, p=p):
            a_, b_ = cv.P(*p, 0), cv.P(*p, 9)
            cv.d.line([a_, b_], fill=(90, 92, 98))
            cv.d.line([(b_[0] - 3, b_[1] + 1), (b_[0] + 3, b_[1] - 1)], fill=(90, 92, 98))
            cv.d.point((b_[0] - 3, b_[1] + 2), fill=(255, 240, 180)); cv.d.point((b_[0] + 3, b_[1]), fill=(255, 240, 180))
        part(f"panj-lamp{k}", (p[0] - 2, p[1] - 2, p[0] + 2, p[1] + 2), 12, lamp)


# ------------------------------------------------------------------------------------------------ Butterfly park
def butterfly_park():
    """Tropical Butterfly Conservatory at Melur: lawns, winding red paths, lily ponds, round flower gardens, glass domes."""
    rows = _geoms("land_use", "subtype='park' and ST_DWithin(geometry, ST_Point(78.63605, 10.87765), 0.002)")
    g = max((r[0] for r in rows), key=lambda a: a.area)
    if g.geom_type == "MultiPolygon":
        g = max(g.geoms, key=lambda a: a.area)
    g = g.simplify(2.0)
    rng = np.random.default_rng(77)
    cx, cy, u, v, L1, L2 = _axes(g)
    c0 = np.array([cx, cy])
    x0, y0, x1, y1 = g.buffer(10).bounds
    ponds = []
    for k in range(5):
        p = c0 + u * (L1 * (k - 2) * 0.14) + v * (L2 * 0.12 * (1 if k % 2 else -1))
        pg = affinity.scale(Point(*p).buffer(13 + 5 * rng.random(), quad_segs=6), 1.5, 0.9, origin=tuple(p))
        pg = affinity.rotate(pg, rng.uniform(0, 180), origin=tuple(p))
        if g.buffer(-12).contains(pg):
            ponds.append(pg)
    gardens = []
    for k in range(4):
        p = c0 + u * (L1 * (k - 1.5) * 0.2) - v * (L2 * 0.26) * (1 if k % 2 else 0.4)
        if g.buffer(-14).contains(Point(*p)) and all(pg.distance(Point(*p)) > 16 for pg in ponds):
            gardens.append(p)
    path = LineString([tuple(c0 + u * L1 * (t - 0.5) * 0.9 + v * L2 * 0.18 * math.sin(t * 9)) for t in np.linspace(0, 1, 40)])
    path = path.intersection(g.buffer(-4))

    def ground(cv):
        cv.ground(list(g.exterior.coords), (118, 172, 86))
        cv.ground(list(g.buffer(-3).exterior.coords), (126, 182, 92))
        for pl in (path.geoms if hasattr(path, "geoms") else [path]):
            if pl.geom_type == "LineString" and pl.length > 5:
                cv.ground(list(pl.buffer(2.4).exterior.coords), (204, 112, 96))
                cv.d.line([cv.P(x, y) for x, y in pl.coords], fill=(226, 150, 130))
        for pg in ponds:
            cv.ground(list(pg.buffer(2.0).exterior.coords), (40, 70, 110))
            cv.ground(list(pg.exterior.coords), (80, 150, 186))
            for _ in range(10):
                q = pg.buffer(-2).representative_point()
                xx, yy = q.x + rng.uniform(-6, 6), q.y + rng.uniform(-4, 4)
                if pg.contains(Point(xx, yy)):
                    X, Y = cv.P(xx, yy)
                    cv.d.ellipse([X - 1, Y - 1, X + 1, Y], fill=(70, 140, 70))
                    cv.d.point((X, Y - 1), fill=(240, 150, 190))
        for p in gardens:
            for r, col in ((11, (204, 112, 96)), (9.5, (232, 70, 80)), (7.5, (250, 200, 60)), (5.5, (236, 120, 190)), (3.5, (110, 176, 80)), (1.5, (250, 250, 240))):
                cv.ground(list(Point(*p).buffer(r, quad_segs=8).exterior.coords), col)
    part("bfly-ground", (x0, y0, x1, y1), 1, ground, ground=True)
    hide_poly(list(g.buffer(2).exterior.coords), 0)
    # glass conservatory domes
    dc = [c0 + u * L1 * 0.28 + v * L2 * 0.2, c0 + u * L1 * 0.34 + v * L2 * 0.05]
    for k, p in enumerate(dc):
        R = 10.0 - 3 * k

        def dm(cv, p=p, R=R):
            cv.extrude(list(Point(*p).buffer(R + 0.6, quad_segs=6).exterior.coords), 0, 1.0, (200, 196, 186), (210, 206, 196))
            dome(cv, p[0], p[1], R, 1.0, (200, 226, 238))
        part(f"bfly-dome{k}", (p[0] - R - 2, p[1] - R - 2, p[0] + R + 2, p[1] + R + 2), R + 4, dm)
    # trees everywhere except ponds, paths and gardens, plus visitors on the paths
    items = []
    avoid = unary_union(ponds + [Point(*p).buffer(13) for p in gardens] + [Point(*p).buffer(14) for p in dc] + [path.buffer(4)])
    for k in range(int(g.area / 150)):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        if g.buffer(-3).contains(Point(x, y)) and not avoid.contains(Point(x, y)):
            items.append(("tree", x, y, int(rng.integers(0, 1 << 20)), 0))
    for pl in (path.geoms if hasattr(path, "geoms") else [path]):
        if pl.geom_type != "LineString":
            continue
        for k in range(int(pl.length // 14)):
            p = pl.interpolate(rng.uniform(0, pl.length))
            items.append(("person", p.x + rng.uniform(-1, 1), p.y + rng.uniform(-1, 1), int(rng.integers(0, 1 << 20)), 0))
    chunks = {}
    for it in items:
        key = (int(it[1] // 50), int(it[2] // 50))
        chunks.setdefault(key, []).append(it)
    for key, lst in chunks.items():
        xs_ = [i[1] for i in lst]; ys_ = [i[2] for i in lst]
        _sprite_part(f"bfly-life{key[0]}_{key[1]}", (min(xs_) - 3, min(ys_) - 3, max(xs_) + 3, max(ys_) + 3), lst, 16)


# ------------------------------------------------------------------------------------------------ Planetarium
def planetarium():
    """Anna Science Centre Planetarium: a white sky-theatre dome on a drum, a gallery block and a garden forecourt."""
    rows = _geoms("buildings", "ST_DWithin(geometry, ST_Point(78.70372, 10.76819), 0.0004)")
    g = max((r[0] for r in rows), key=lambda a: a.area)
    if g.geom_type == "MultiPolygon":
        g = max(g.geoms, key=lambda a: a.area)
    c = g.centroid
    R = max(10.0, min(18.0, math.sqrt(g.area / math.pi) * 0.75))
    site = g.buffer(28)
    hide_poly(list(site.exterior.coords), 0)

    def ground(cv):
        cv.ground(list(site.exterior.coords), (122, 170, 90))
        cv.ground(list(Point(c.x, c.y).buffer(R + 10).exterior.coords), (214, 204, 184))
        for r, col in ((5, (232, 70, 80)), (3, (250, 200, 60))):
            p = (c.x - R - 18, c.y - 6)
            cv.ground(list(Point(*p).buffer(r).exterior.coords), col)
    bb = site.buffer(4).bounds
    part("planet-ground", bb, 1, ground, ground=True)

    def build(cv):
        cv.extrude(list(Point(c.x + R + 9, c.y + 4).buffer(1).buffer(9, join_style=2).exterior.coords), 0, 8, (226, 214, 190), (196, 100, 76))
        cv.extrude(list(Point(c.x, c.y).buffer(R + 1.5, quad_segs=8).exterior.coords), 0, 6.5, (222, 212, 192), (210, 204, 192))
        S = list(Point(c.x, c.y).buffer(R + 1.5, quad_segs=8).exterior.coords)
        cv.d.line([cv.P(x, y, 4.4) for x, y in S], fill=(170, 110, 80))
        dome(cv, c.x, c.y, R, 6.5, (244, 244, 240), rings=11)
    part("planet-dome", (c.x - R - 20, c.y - R - 12, c.x + R + 20, c.y + R + 14), R + 10, build)
    scatter_life("planet", Point(c.x, c.y).buffer(R + 9).difference(Point(c.x, c.y).buffer(R + 3)), [], 93, cell=7, p=0.35, people=(1, 3), stalls_p=0.05, autos_p=0.05, cows_p=0, trees_p=0.15, scooters_p=0.15)


M.ALL.update(junction=junction, centralbus=central_bus, chatram=chatram, gandhi=gandhi_market, goldenrockworks=golden_rock_works,
             bhel=bhel, airport=airport, panjappur=panjappur, butterfly=butterfly_park, planetarium=planetarium)
