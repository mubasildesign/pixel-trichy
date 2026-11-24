"""Temple parts drawn with art3d: gopurams, enclosure walls, golden vimanams, pillared halls, a church.

All sizes are metres and are stylised from public descriptions and photographs, not survey drawings.
"""
from __future__ import annotations
import math
import numpy as np

from config import VK
from art3d import shade, mix, fp, frect, flen, fhgt

STONE = (150, 128, 108)
LIME = (238, 230, 212)
OCHRE = (228, 182, 112)
TERRA = (206, 122, 90)
SKY = (176, 200, 208)
ROSE = (226, 150, 140)
GOLD = (236, 190, 70)
ROOF_RED = (186, 98, 72)

PAL_CLASSIC = [(206, 86, 66), (66, 124, 176), (236, 162, 62), (58, 150, 146), (234, 214, 168), (178, 82, 120), (226, 128, 60)]
PAL_BRIGHT = [(246, 206, 96), (226, 96, 100), (98, 164, 214), (244, 234, 206), (84, 178, 130), (238, 140, 64)]
PAL_WHITE = [(244, 240, 228), (236, 220, 190), (244, 240, 228), (226, 200, 170)]


def _niches(cv, q, seed, pal, dense=1.0, big_centre=False):
    """Rows of little niches and figurines on a tier face."""
    L, Hh = flen(q), fhgt(q)
    if L < 9 or Hh < 5:
        return
    n = max(2, int(L / (6.5 / dense)))
    d = cv.d
    wall_dark = (92, 62, 52)
    for j in range(n):
        u = (j + 0.5) / n
        w = 0.28 / n
        if big_centre and abs(u - 0.5) < 0.5 / n:
            r = frect(q, u - 0.45 / n, u + 0.45 / n, 0.12, 0.78)
            d.polygon(r, fill=(70, 46, 40), outline=(200, 150, 70))
            continue
        r = frect(q, u - w, u + w, 0.18, 0.66)
        d.polygon(r, fill=wall_dark)
        x, y = fp(q, u, 0.84)
        d.point((x, y), fill=pal[(j + seed) % len(pal)])
        if Hh > 9:
            x, y = fp(q, u, 0.74)
            d.point((x, y), fill=pal[(j + seed + 2) % len(pal)])


def _pilasters(cv, q, wall, n=2):
    d = cv.d
    for u in [0.0, 1.0] + ([0.5] if n > 2 else []):
        d.line([fp(q, u, 0.0), fp(q, u, 1.0)], fill=shade(wall, 0.6))


def gopuram(cv, cx, cy, L, T, H, n, axis="ns", pal=PAL_CLASSIC, seed=0, base_col=STONE, gold_top=True, stub=False):
    """South Indian temple gateway tower. L = long side, T = short side (the passage runs through T).
    axis 'ns': gate in the north/south walls, long side along east-west. axis 'ew': the other way round."""
    W, D = (L, T) if axis == "ns" else (T, L)
    hb = H * (0.30 if stub else 0.24)
    foot = (cx - W / 2, cy - D / 2, cx + W / 2, cy + D / 2)

    # stone base with the gateway
    def base():
        S, Wq, top = cv.box(foot[0], foot[1], foot[2], foot[3], 0, hb, base_col, shade(base_col, 1.1))
        front = S if axis == "ns" else Wq
        # dark gateway with a lighter frame
        d = cv.d
        d.polygon(frect(front, 0.36, 0.64, 0.0, 0.66), fill=(54, 40, 36), outline=shade(base_col, 0.5))
        d.line([fp(front, 0.36, 0.7), fp(front, 0.5, 0.82), fp(front, 0.64, 0.7)], fill=shade(base_col, 0.55))
        for q in (S, Wq):
            _pilasters(cv, q, base_col, 3)
            for v in (0.33, 0.66):
                d.line([fp(q, 0.0, v), fp(q, 1.0, v)], fill=shade(base_col, 0.78))
    cv.add(foot, 0, base)
    n = max(2, n)

    hcrown = H * 0.11
    hz = H - hb - hcrown
    wts = np.array([1.12 - 0.5 * (k / max(1, n - 1)) for k in range(n)])
    hs = hz * wts / wts.sum()

    def prof_w(t):
        return 0.36 + 0.56 * (1 - t) ** 2.3

    def prof_d(t):
        return 0.44 + 0.48 * (1 - t) ** 1.9

    z = hb
    for k in range(n):
        t0, t1 = k / n, (k + 1) / n
        w0, w1, d0, d1 = prof_w(t0) * 0.97, prof_w(t1), prof_d(t0) * 0.97, prof_d(t1)
        col = pal[k % len(pal)]
        hk = hs[k]
        zb, zm, zt = z, z + hk * 0.84, z + hk
        zz = z
        z += hk
        body_foot = (cx - W * w0 / 2, cy - D * d0 / 2, cx + W * w0 / 2, cy + D * d0 / 2)

        def body(zb=zb, zm=zm, w0=w0, w1=w1, d0=d0, d1=d1, col=col, k=k):
            S, Wq, top = cv.frustum(cx, cy, W * w0 / 2, D * d0 / 2, zb, W * w1 / 2, D * d1 / 2, zm, col, shade(col, 1.05))
            # niches on both visible faces, a taller central niche on the front
            _niches(cv, S, seed + k, PAL_BRIGHT, 1.7, big_centre=(axis == "ns"))
            _niches(cv, Wq, seed + k + 3, PAL_BRIGHT, 1.7, big_centre=(axis == "ew"))
            for q, f in ((S, 1.0), (Wq, 0.8)):
                cv.d.line([fp(q, 0, 0.07), fp(q, 1, 0.07)], fill=shade(col, 0.5 * f))
                cv.d.line([fp(q, 0, 0.93), fp(q, 1, 0.93)], fill=shade(mix(col, (255, 244, 214), 0.6), f))
            _pilasters(cv, S, col, 2)
            _pilasters(cv, Wq, col, 2)
        cv.add(body_foot, zb, body)

        def cornice(zm=zm, zt=zt, w1=w1, d1=d1, col=col):
            cv.box(cx - W * w1 * 0.53, cy - D * d1 * 0.53, cx + W * w1 * 0.53, cy + D * d1 * 0.53, zm, zt, shade(col, 1.1), shade(col, 1.2))
        cv.add((cx - W * w1 * 0.53, cy - D * d1 * 0.53, cx + W * w1 * 0.53, cy + D * d1 * 0.53), zm, cornice)

    # barrel-vault crown ("shalai") and golden finials
    wc, dc = prof_w(1.0), prof_d(1.0)
    cf = (cx - W * wc / 2, cy - D * dc / 2, cx + W * wc / 2, cy + D * dc / 2)

    def crown():
        hb0 = hcrown * 0.5
        S, Wq, top = cv.box(cf[0], cf[1], cf[2], cf[3], z, z + hb0, shade(ROOF_RED, 1.05), ROOF_RED)
        d = cv.d
        # the vault: an arched cap over the box, drawn on the long visible face and the end face
        long_q, end_q = (S, Wq) if axis == "ns" else (Wq, S)
        for q, f in ((end_q, 0.8), (long_q, 1.0)):
            pts = []
            for i in range(9):
                u = i / 8
                pts.append(fp(q, u, 1.0 + 0.9 * math.sin(math.pi * u)))
            base = [fp(q, 1, 1.0), fp(q, 0, 1.0)]
            d.polygon(pts + base, fill=shade(ROOF_RED, 1.08 * f), outline=shade(ROOF_RED, 0.62))
            # ribs
            nribs = max(2, int(flen(q) / 4))
            for i in range(1, nribs):
                u = i / nribs
                d.line([fp(q, u, 1.0), fp(q, u, 1.0 + 0.9 * math.sin(math.pi * u))], fill=shade(ROOF_RED, 0.78 * f))
        zt = z + hb0 + hcrown * 0.5
        if axis == "ns":
            a, b = cv.P(cx - W * wc / 2 * 0.86, cy, zt), cv.P(cx + W * wc / 2 * 0.86, cy, zt)
        else:
            a, b = cv.P(cx, cy - D * dc / 2 * 0.86, zt), cv.P(cx, cy + D * dc / 2 * 0.86, zt)
        nfin = 7 if H > 50 else 5 if H > 30 else 3
        for i in range(nfin):
            t = (i + 0.5) / nfin
            p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            hh = (4.0 if i != nfin // 2 else 6.0) * (1.0 if H > 40 else 0.8)
            d.line([(p[0], p[1]), (p[0], p[1] - hh)], fill=shade(GOLD, 0.6))
            d.ellipse([p[0] - 1.4, p[1] - hh - 3, p[0] + 1.4, p[1] - hh + 0.4], fill=GOLD, outline=shade(GOLD, 0.6))
    cv.add(cf, z, crown)
    return foot


def vimanam(cv, cx, cy, B, H, tiers=4, col=GOLD):
    """Golden stepped sanctum tower with a dome and finial."""
    foot = (cx - B / 2, cy - B / 2, cx + B / 2, cy + B / 2)
    hb = H * 0.22

    def base():
        S, Wq, top = cv.box(foot[0], foot[1], foot[2], foot[3], 0, hb, LIME, shade(LIME, 1.05))
        cv.d.polygon(frect(S, 0.4, 0.6, 0.0, 0.6), fill=(70, 50, 44))
    cv.add(foot, 0, base)
    z = hb
    hk = (H * 0.62 - hb * 0) / tiers
    for k in range(tiers):
        f0, f1 = 0.86 - 0.5 * k / tiers, 0.86 - 0.5 * (k + 1) / tiers
        zb = z
        ft = (cx - B * f0 / 2, cy - B * f0 / 2, cx + B * f0 / 2, cy + B * f0 / 2)

        def tier(zb=zb, f0=f0, f1=f1, k=k):
            S, Wq, top = cv.frustum(cx, cy, B * f0 / 2, B * f0 / 2, zb, B * f1 / 2, B * f1 / 2, zb + hk, mix(col, (255, 230, 140), 0.12 * (k % 2)), shade(col, 1.15))
            for q in (S, Wq):
                if flen(q) > 7:
                    cv.d.line([fp(q, 0.5, 0.15), fp(q, 0.5, 0.85)], fill=shade(col, 0.62))
        cv.add(ft, zb, tier)
        z += hk

    def dome():
        x, y = cv.P(cx, cy, z)
        r = B * 0.16 * 2.0
        cv.d.ellipse([x - r, y - r * 1.15, x + r, y + r * 0.45], fill=col, outline=shade(col, 0.6))
        cv.d.ellipse([x - r * 0.1, y - r * 1.05, x + r * 0.95, y - r * 0.1], fill=shade(col, 1.15))
        top = y - r * 1.15
        cv.d.line([(x, top), (x, top - 7)], fill=shade(col, 0.6))
        cv.d.ellipse([x - 1.4, top - 10, x + 1.4, top - 6.5], fill=col, outline=shade(col, 0.6))
    cv.add((cx - B * 0.2, cy - B * 0.2, cx + B * 0.2, cy + B * 0.2), z, dome)
    return foot


def hall(cv, x0, y0, x1, y1, h, col=LIME, roof=ROOF_RED, cols=True, pitched=True):
    """Pillared mandapam: walls with a row of dark columns under a pitched terracotta roof."""
    foot = (x0, y0, x1, y1)

    def draw():
        S, Wq, top = cv.box(x0, y0, x1, y1, 0, h, col, roof)
        if cols:
            for q in (S, Wq):
                n = max(2, int(flen(q) / 4))
                for i in range(n + 1):
                    u = i / n
                    cv.d.line([fp(q, u, 0.05), fp(q, u, 0.82)], fill=shade(col, 0.5))
                cv.d.line([fp(q, 0, 0.85), fp(q, 1, 0.85)], fill=shade(col, 0.7))
        P = cv.P
        if not pitched:
            return
        rh = min(x1 - x0, y1 - y0) * 0.28
        xm, ym = (x0 + x1) / 2, (y0 + y1) / 2
        e = 0.6   # eaves overhang
        if x1 - x0 >= y1 - y0:   # ridge along x
            cv.d.polygon([P(x0 - e, y0 - e, h), P(x1 + e, y0 - e, h), P(x1 + e, ym, h + rh), P(x0 - e, ym, h + rh)], fill=shade(roof, 1.08), outline=shade(roof, 0.62))
            cv.d.polygon([P(x0 - e, ym, h + rh), P(x1 + e, ym, h + rh), P(x1 + e, y1 + e, h), P(x0 - e, y1 + e, h)], fill=shade(roof, 0.86), outline=shade(roof, 0.58))
        else:                    # ridge along y
            cv.d.polygon([P(x0 - e, y0 - e, h), P(xm, y0 - e, h + rh), P(xm, y1 + e, h + rh), P(x0 - e, y1 + e, h)], fill=shade(roof, 0.82), outline=shade(roof, 0.58))
            cv.d.polygon([P(xm, y0 - e, h + rh), P(x1 + e, y0 - e, h), P(x1 + e, y1 + e, h), P(xm, y1 + e, h + rh)], fill=shade(roof, 1.1), outline=shade(roof, 0.62))
    cv.add(foot, 0, draw)
    return foot


def stripe_wall(cv, x0, y0, x1, y1, h, col=LIME, stripe=(188, 74, 52), top=None):
    """A wall segment with the red-and-white vertical stripes of Tamil temple enclosure walls."""
    foot = (x0, y0, x1, y1)

    def draw():
        S, Wq, tp = cv.box(x0, y0, x1, y1, 0, h, col, top or shade(col, 1.05), outline=False)
        for q in (S, Wq):
            L = flen(q)
            n = max(2, int(L / 3.2))
            for i in range(0, n, 2):
                cv.d.polygon(frect(q, i / n, (i + 1) / n, 0.0, 0.78), fill=shade(stripe, 1.0 if q is S else 0.78))
            cv.d.line([fp(q, 0, 0.8), fp(q, 1, 0.8)], fill=shade(col, 0.85))
            cv.d.polygon(frect(q, 0, 1, 0.8, 1.0), fill=shade(col, 1.0 if q is S else 0.78))
        # row of small figurines along the parapet
        L = max(abs(x1 - x0), abs(y1 - y0))
        nn = int(L / 7)
        for i in range(nn):
            t = (i + 0.5) / nn
            if x1 - x0 > y1 - y0:
                p = cv.P(x0 + (x1 - x0) * t, (y0 + y1) / 2, h + 0.3)
            else:
                p = cv.P((x0 + x1) / 2, y0 + (y1 - y0) * t, h + 0.3)
            cv.d.rectangle([p[0] - 1, p[1] - 2, p[0], p[1]], fill=(236, 226, 206), outline=(150, 130, 110))
    cv.add(foot, 0, draw)
    return foot


def wall_ring(cv, x0, y0, x1, y1, h, thick, gates, col=LIME, plain=False):
    """Rectangular enclosure. gates = {'s': [(centre_x, half_gap)], 'n': [...], 'w': [(centre_y, half_gap)], 'e': [...]}."""
    def segs(a0, a1, gaps):
        out, cur = [], a0
        for c, g in sorted(gaps):
            if c - g > cur:
                out.append((cur, c - g))
            cur = max(cur, c + g)
        if cur < a1:
            out.append((cur, a1))
        return out
    wall = (lambda *a: stripe_wall(cv, *a, h=h, col=col)) if not plain else (lambda *a: stripe_wall(cv, *a, h=h, col=col, stripe=shade(col, 0.88)))
    t = thick
    for a, b in segs(x0, x1, gates.get("s", [])):
        wall(a, y0, b, y0 + t)
    for a, b in segs(x0, x1, gates.get("n", [])):
        wall(a, y1 - t, b, y1)
    for a, b in segs(y0 + t, y1 - t, gates.get("w", [])):
        wall(x0, a, x0 + t, b)
    for a, b in segs(y0 + t, y1 - t, gates.get("e", [])):
        wall(x1 - t, a, x1, b)


def church(cv, cx, cy, Ln, Wn, Hn, Ht, col=(244, 242, 236)):
    """Neo-Gothic church: nave running east-west with a spired tower at the west end."""
    x0, x1 = cx - Ln / 2, cx + Ln / 2
    foot = (x0 + Wn * 0.62, cy - Wn / 2, x1, cy + Wn / 2)

    def nave():
        S, Wq, top = cv.box(foot[0], foot[1], foot[2], foot[3], 0, Hn, col, (176, 100, 84))
        # lancet windows and buttresses
        for q in (S, Wq):
            n = max(3, int(flen(q) / 6))
            for i in range(n):
                u = (i + 0.5) / n
                cv.d.polygon(frect(q, u - 0.12 / n * 2, u + 0.12 / n * 2, 0.3, 0.8), fill=(96, 120, 150))
                cv.d.line([fp(q, i / n, 0.0), fp(q, i / n, 1.0)], fill=shade(col, 0.82))
        a = cv.P(x0 + Wn * 0.62 + 3, cy, Hn + 0.2)
        b = cv.P(x1 - 3, cy, Hn + 0.2)
        cv.d.line([a, b], fill=(140, 76, 60))
    cv.add(foot, 0, nave)
    tx0, tx1 = x0 - 0.0, x0 + Wn * 0.8
    tfoot = (tx0 - Wn * 0.1, cy - Wn * 0.4, tx0 + Wn * 0.62, cy + Wn * 0.4)

    def tower():
        S, Wq, top = cv.box(tfoot[0], tfoot[1], tfoot[2], tfoot[3], 0, Ht * 0.62, col, col)
        cv.d.polygon(frect(S, 0.35, 0.65, 0.05, 0.4), fill=(70, 54, 50))
        for q in (S, Wq):
            cv.d.polygon(frect(q, 0.4, 0.6, 0.62, 0.9), fill=(96, 120, 150))
        mx, my = (tfoot[0] + tfoot[2]) / 2, (tfoot[1] + tfoot[3]) / 2
        apex = cv.P(mx, my, Ht)
        zb = Ht * 0.62
        p = [cv.P(tfoot[0], tfoot[1], zb), cv.P(tfoot[2], tfoot[1], zb), cv.P(tfoot[2], tfoot[3], zb), cv.P(tfoot[0], tfoot[3], zb)]
        cv.d.polygon([p[0], p[1], apex], fill=(120, 130, 146), outline=(80, 88, 104))
        cv.d.polygon([p[0], p[3], apex], fill=(96, 106, 124), outline=(70, 78, 92))
        cv.d.line([apex, (apex[0], apex[1] - 6)], fill=(60, 60, 64))
        cv.d.line([(apex[0] - 2, apex[1] - 4), (apex[0] + 2, apex[1] - 4)], fill=(60, 60, 64))
    cv.add(tfoot, 0, tower)
    return foot


# ------------------------------------------------------------------------------------------------ neo-Gothic cathedral
SLATE = (118, 128, 148)
WINDOW = (82, 110, 150)


def spire(cv, cx, cy, hw, z0, z1, col=SLATE, cross=True):
    P = cv.P
    apex = P(cx, cy, z1)
    b = [P(cx - hw, cy - hw, z0), P(cx + hw, cy - hw, z0), P(cx + hw, cy + hw, z0), P(cx - hw, cy + hw, z0)]
    cv.d.polygon([b[0], b[1], apex], fill=shade(col, 1.08), outline=shade(col, 0.6))
    cv.d.polygon([b[0], b[3], apex], fill=shade(col, 0.82), outline=shade(col, 0.55))
    cv.d.line([b[0], apex], fill=shade(col, 1.25))
    if cross:
        cv.d.line([apex, (apex[0], apex[1] - 7)], fill=(236, 226, 190))
        cv.d.line([(apex[0] - 2, apex[1] - 5), (apex[0] + 2, apex[1] - 5)], fill=(236, 226, 190))


def _lancets(cv, q, n, v0=0.28, v1=0.82, w=0.3, col=WINDOW):
    for i in range(n):
        u = (i + 0.5) / n
        r = frect(q, u - w / n / 2, u + w / n / 2, v0, v1)
        cv.d.polygon(r, fill=col)
        x, y = fp(q, u, v1 + 0.06)
        cv.d.point((x, y), fill=col)
        cv.d.line([fp(q, i / n, 0.0), fp(q, i / n, 1.0)], fill=shade(LIME, 0.8))      # buttress


BLUE = (62, 176, 218)          # the bright metal roof in the aerial photographs
ROSE_GLASS = (74, 102, 148)
DOOR = (58, 44, 40)
CREAM = (244, 240, 230)


def _pointed(cv, q, u0, u1, v0, v1, col, frame=CREAM):
    """A lancet: a shaft with a pointed head, and a light stone frame."""
    d = cv.d
    head = v0 + (v1 - v0) * 0.72
    d.polygon(frect(q, u0, u1, v0, head), fill=col, outline=frame)
    d.polygon([fp(q, u0, head), fp(q, u1, head), fp(q, (u0 + u1) / 2, v1)], fill=col, outline=frame)


def _rose(cv, q, u, v, r, col=ROSE_GLASS):
    """Circular rose window with a stone cross and ring, as on the west front."""
    c = fp(q, u, v)
    d = cv.d
    d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], fill=col, outline=CREAM)
    d.ellipse([c[0] - r * 0.45, c[1] - r * 0.45, c[0] + r * 0.45, c[1] + r * 0.45], outline=CREAM)
    d.line([(c[0] - r + 1, c[1]), (c[0] + r - 1, c[1])], fill=CREAM)
    d.line([(c[0], c[1] - r + 1), (c[0], c[1] + r - 1)], fill=CREAM)


def lourdes_church(cv, cx, cy):
    """Our Lady of Lourdes, Trichy, from photographs: one very tall Gothic spire on the west
    front (rose window, pinnacles, a cross), and a long nave under a bright blue pitched roof.
    Sizes are stylised, not a survey."""
    d = cv.d
    P = cv.P
    wall = CREAM
    # nave running east from just behind the tower
    nx0, nx1, ny0, ny1 = cx - 4, cx + 50, cy - 8, cy + 8
    He, rise = 11.0, 4.6

    def draw_nave():
        S, Wq, top = cv.box(nx0, ny0, nx1, ny1, 0, He, wall, wall, shadow=True)
        d.polygon(frect(S, 0, 1, 0.0, 0.16), fill=shade(wall, 0.86))          # stone plinth
        _pointed_row = 9
        for i in range(_pointed_row):
            u = (i + 0.5) / _pointed_row
            w = 0.30 / _pointed_row
            _pointed(cv, S, u - w, u + w, 0.30, 0.84, WINDOW)
        for i in range(_pointed_row + 1):
            d.line([fp(S, i / _pointed_row, 0.16), fp(S, i / _pointed_row, 1.0)], fill=shade(wall, 0.72))
        d.line([fp(S, 0, 0.22), fp(S, 1, 0.22)], fill=shade(wall, 0.78))
        # bright blue gabled roof, the thing the church is recognised by from above
        e = 1.1
        ridge = He + rise
        south = shade(BLUE, 1.14)
        north = shade(BLUE, 0.74)
        d.polygon([P(nx0 - e, ny1 + e, He), P(nx1 + e, ny1 + e, He), P(nx1 + e, cy, ridge), P(nx0 - e, cy, ridge)], fill=north, outline=shade(BLUE, 0.55))
        d.polygon([P(nx0 - e, ny0 - e, He), P(nx1 + e, ny0 - e, He), P(nx1 + e, cy, ridge), P(nx0 - e, cy, ridge)], fill=south, outline=shade(BLUE, 0.6))
        rib = shade(BLUE, 0.62)
        for i in range(1, 8):
            x = nx0 + (nx1 - nx0) * i / 8
            d.line([P(x, ny0 - e, He), P(x, cy, ridge)], fill=rib)
            d.line([P(x, cy, ridge), P(x, ny1 + e, He)], fill=shade(BLUE, 0.5))
        d.line([P(nx0 - e, cy, ridge), P(nx1 + e, cy, ridge)], fill=(214, 236, 246))
    cv.add((nx0, ny0, nx1, ny1), 0, draw_nave)

    # the west tower: square, cream stone, taller than the nave, with the rose window facing west
    tx0, tx1, ty0, ty1 = cx - 20, cx - 2, cy - 9, cy + 9
    Ht, Hs = 24.0, 70.0

    def draw_tower():
        S, Wq, top = cv.box(tx0, ty0, tx1, ty1, 0, Ht, wall, wall, shadow=False)
        cv._shadow([P(tx0, ty0, 0), P(tx1, ty0, 0), P(tx1, ty1, 0), P(tx0, ty1, 0)], Hs * VK)
        for q in (S, Wq):
            d.polygon(frect(q, 0, 1, 0.0, 0.10), fill=shade(wall, 0.84))
            for v in (0.34, 0.62, 0.90):
                d.line([fp(q, 0, v), fp(q, 1, v)], fill=shade(wall, 0.75))
            d.line([fp(q, 0.08, 0.1), fp(q, 0.08, 1.0)], fill=shade(wall, 0.7))
            d.line([fp(q, 0.92, 0.1), fp(q, 0.92, 1.0)], fill=shade(wall, 0.7))
        # west front: pointed door, a tall window, the rose, then the belfry
        _pointed(cv, Wq, 0.30, 0.70, 0.0, 0.30, DOOR, (214, 196, 160))
        _pointed(cv, Wq, 0.38, 0.62, 0.36, 0.56, WINDOW)
        _rose(cv, Wq, 0.5, 0.55, max(4, int(flen(Wq) * 0.16)))
        _pointed(cv, Wq, 0.20, 0.42, 0.68, 0.90, (64, 68, 86))
        _pointed(cv, Wq, 0.58, 0.80, 0.68, 0.90, (64, 68, 86))
        # south face of the tower, the other side the map shows
        _pointed(cv, S, 0.34, 0.66, 0.16, 0.46, WINDOW)
        _rose(cv, S, 0.5, 0.60, max(3, int(flen(S) * 0.13)))
        _pointed(cv, S, 0.22, 0.44, 0.70, 0.90, (64, 68, 86))
        _pointed(cv, S, 0.56, 0.78, 0.70, 0.90, (64, 68, 86))
        # parapet and the four corner pinnacles, then the spire and its cross
        cv.box(tx0 - 0.6, ty0 - 0.6, tx1 + 0.6, ty1 + 0.6, Ht - 1.4, Ht + 0.5, shade(wall, 0.94), shade(wall, 1.06), outline=False, shadow=False)
        mx, my = (tx0 + tx1) / 2, (ty0 + ty1) / 2
        pin = (206, 200, 186)
        for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            spire(cv, mx + dx * 7.4, my + dy * 7.6, 1.25, Ht - 0.4, Ht + 9, pin, cross=False)
        spire(cv, mx, my, 5.6, Ht + 0.5, Hs, (214, 210, 198), cross=False)
        # little gabled openings on the two faces of the spire the map can see
        apex = P(mx, my, Hs)
        base_s = (P(mx - 5.6, my - 5.6, Ht + 0.5), P(mx + 5.6, my - 5.6, Ht + 0.5))
        base_w = (P(mx - 5.6, my - 5.6, Ht + 0.5), P(mx - 5.6, my + 5.6, Ht + 0.5))

        def lucarne(b0, b1, t=0.30, w=0.15):
            def at(u, tt):
                bx = b0[0] + (b1[0] - b0[0]) * u
                by = b0[1] + (b1[1] - b0[1]) * u
                return (bx + (apex[0] - bx) * tt, by + (apex[1] - by) * tt)
            d.polygon([at(0.5 - w, t), at(0.5 + w, t), at(0.5, t + 0.10)], fill=(58, 66, 90), outline=CREAM)
        lucarne(*base_s)
        lucarne(*base_w, 0.46)
        d.line([apex, (apex[0], apex[1] - 16)], fill=(46, 44, 48), width=2)
        d.line([(apex[0] - 6, apex[1] - 10), (apex[0] + 6, apex[1] - 10)], fill=(46, 44, 48), width=2)
    cv.add((tx0, ty0, tx1, ty1), 0, draw_tower)


def cathedral(cv, cx, cy, L=52.0, W=14.0, Hn=14.0, Ht=28.0, Hs=50.0, wall=(246, 244, 238)):
    """Twin-towered Gothic basilica: nave running east-west, transepts, crossing spire; the facade faces west."""
    x0, x1 = cx - L / 2, cx + L / 2
    nave = (x0 + 8, cy - W / 2, x1, cy + W / 2)

    def draw_nave():
        S, Wq, top = cv.box(*nave, 0, Hn, wall, (178, 98, 78))
        _lancets(cv, S, max(4, int(flen(S) / 6)))
        d = cv.d
        a, b = cv.P(nave[0], cy, Hn + 0.2), cv.P(nave[2], cy, Hn + 0.2)
        d.line([a, b], fill=(140, 76, 60))
    cv.add(nave, 0, draw_nave)

    tx = cx + L * 0.12
    trans = (tx - 6, cy - 17, tx + 6, cy + 17)

    def draw_trans():
        S, Wq, top = cv.box(*trans, 0, Hn - 0.5, wall, (178, 98, 78))
        _lancets(cv, S, 3, 0.3, 0.8, 0.5)
        _lancets(cv, Wq, 5, 0.3, 0.8, 0.5)
        cv.d.ellipse([fp(Wq, 0.5, 0.52)[0] - 3, fp(Wq, 0.5, 0.52)[1] - 3, fp(Wq, 0.5, 0.52)[0] + 3, fp(Wq, 0.5, 0.52)[1] + 3], fill=(92, 120, 160), outline=(60, 80, 110))
    cv.add(trans, 0, draw_trans)

    cr = (tx - 4.5, cy - 4.5, tx + 4.5, cy + 4.5)

    def draw_cross():
        S, Wq, top = cv.box(*cr, Hn, Hn + 9, wall, wall)
        _lancets(cv, S, 2, 0.2, 0.8, 0.5)
        _lancets(cv, Wq, 2, 0.2, 0.8, 0.5)
        spire(cv, tx, cy, 4.8, Hn + 9, Hn + 30, SLATE)
    cv.add(cr, Hn, draw_cross)

    for k, (ya, yb) in enumerate(((cy - 8.5, cy - 0.5), (cy + 0.5, cy + 8.5))):
        tf = (x0, ya, x0 + 10, yb)

        def draw_tower(tf=tf, ya=ya, yb=yb):
            S, Wq, top = cv.box(*tf, 0, Ht, wall, wall)
            d = cv.d
            d.polygon(frect(Wq, 0.28, 0.72, 0.0, 0.30), fill=(70, 54, 50), outline=(210, 200, 180))      # west door
            d.polygon(frect(Wq, 0.3, 0.7, 0.36, 0.62), fill=WINDOW, outline=(200, 196, 188))
            d.polygon(frect(Wq, 0.36, 0.64, 0.7, 0.92), fill=(70, 70, 90))                              # belfry louvres
            d.polygon(frect(S, 0.3, 0.7, 0.7, 0.92), fill=(70, 70, 90))
            for q in (S, Wq):
                d.line([fp(q, 0, 0.65), fp(q, 1, 0.65)], fill=shade(wall, 0.75))
                d.line([fp(q, 0, 0.0), fp(q, 0, 1.0)], fill=shade(wall, 0.7))
            spire(cv, (tf[0] + tf[2]) / 2, (tf[1] + tf[3]) / 2, 5.2, Ht, Hs, SLATE)
        cv.add(tf, 0, draw_tower)
    # central gable between the towers with a rose window
    gf = (x0 + 8, cy - 8.5, x0 + 10, cy + 8.5)
    return nave
