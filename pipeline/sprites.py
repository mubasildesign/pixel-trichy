"""Small pixel-art sprites for the isometric renderer: trees, palms, people and vehicles.

Everything is drawn in screen pixels relative to a tile origin. Ground metres map to screen with the same axes as config.py:
one metre east is (K, -K/2) px, one metre north is (-K, -K/2) px, one metre up is (0, -VK) px. Light comes from the east, so
faces that point right are lit and faces that point left are in shade.
"""
from __future__ import annotations
import math
import numpy as np
from config import K, VK

EX = (K, -K / 2)
EY = (-K, -K / 2)


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c)


def mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def to_px(a, b):
    """Metre offset (east a, north b) -> pixel offset."""
    return (a * EX[0] + b * EY[0], a * EX[1] + b * EY[1])


def to_m(dx, dy):
    """Pixel offset -> metre offset on the ground plane."""
    return ((dx / K - 2 * dy / K) / 2, (-dx / K - 2 * dy / K) / 2)


# ------------------------------------------------------------------------------------------------ prisms
def prism(d, cx, cy, L, W, theta, z0, z1, wall, roof, outline=True, wall_alpha=1.0):
    """Oriented box centred on ground pixel (cx, cy). L along heading theta (radians, metre frame), W across.
    Returns the roof polygon (pixel coords) so callers can decorate it."""
    f = (math.cos(theta), math.sin(theta))
    u = (-f[1], f[0])
    corners = []
    for s, t in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        a = f[0] * s * L / 2 + u[0] * t * W / 2
        b = f[1] * s * L / 2 + u[1] * t * W / 2
        dx, dy = to_px(a, b)
        corners.append((cx + dx, cy + dy))
    h0, h1 = z0 * VK, z1 * VK
    n = 4
    # corners are in counter-clockwise order in the metre frame -> outward normal of edge p0->p1 is (dy, -dx) in metre frame,
    # but we test visibility in pixel space where "down the screen" is toward the viewer.
    xs = [p[0] for p in corners]
    ys = [p[1] for p in corners]
    area2 = sum(xs[i] * ys[(i + 1) % n] - xs[(i + 1) % n] * ys[i] for i in range(n))
    sgn = 1.0 if area2 > 0 else -1.0
    for i in range(n):
        p0, p1 = corners[i], corners[(i + 1) % n]
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        nx, ny = dy * sgn, -dx * sgn
        if ny > 1e-6:
            sh = 0.78 if nx < 0 else 1.0
            quad = [(p0[0], p0[1] - h0), (p1[0], p1[1] - h0), (p1[0], p1[1] - h1), (p0[0], p0[1] - h1)]
            d.polygon(quad, fill=shade(wall, sh), outline=shade(wall, 0.55 * sh) if outline else None)
    top = [(x, y - h1) for x, y in corners]
    d.polygon(top, fill=roof, outline=shade(roof, 0.65) if outline else None)
    return top


# ------------------------------------------------------------------------------------------------ trees
LEAF = [(74, 128, 62), (88, 142, 66), (66, 118, 70), (96, 148, 72), (80, 134, 84), (104, 140, 60)]


def tree(d, X, Y, seed, kind="neem"):
    """Base of the trunk at (X, Y). Canopies are built from several lobes so they read as foliage, not discs."""
    rng = np.random.default_rng(seed)
    if kind == "palm":
        H = 15 + int(rng.integers(0, 6))
        lean = float(rng.uniform(-2.5, 2.5))
        pts = [(X + lean * (t / H) ** 2, Y - t) for t in range(0, H + 1, 2)]
        d.line(pts, fill=(124, 96, 68), width=2)
        for i, (px, py) in enumerate(pts[1:-1]):
            if i % 2 == 0:
                d.point((px + 1, py), fill=(92, 68, 48))
        tx, ty = pts[-1]
        for ang in np.linspace(0, 2 * np.pi, 9, endpoint=False) + rng.uniform(0, 1):
            ex = tx + math.cos(ang) * 8
            ey = ty + math.sin(ang) * 3.6 + (3.2 if math.sin(ang) > -0.3 else 0)
            col = (74, 138, 70) if math.cos(ang) > 0 else (48, 104, 58)
            mx, my = (tx + ex) / 2, (ty + ey) / 2 - 2
            d.line([(tx, ty), (mx, my), (ex, ey)], fill=col, width=1)
            d.line([(mx, my + 1), (ex, ey + 1)], fill=shade(col, 0.8), width=1)
        d.ellipse([tx - 1, ty, tx + 1, ty + 2], fill=(116, 84, 44))
        return
    if kind == "bush":
        r = 3 + int(rng.integers(0, 2))
        c = LEAF[int(rng.integers(0, len(LEAF)))]
        d.ellipse([X - r, Y - r - 1, X + r, Y + 1], fill=c, outline=shade(c, 0.6))
        d.ellipse([X - r + 1, Y - r, X - 1, Y - 1], fill=shade(c, 0.8))
        d.ellipse([X, Y - r - 1, X + r - 1, Y - 1], fill=shade(c, 1.22))
        if r > 3 and int(rng.integers(0, 4)) == 0:
            d.point((X + 1, Y - 3), fill=(236, 90, 120))
        return
    big = kind in ("rain", "banyan")
    r = 7.4 + float(rng.uniform(0, 4.0)) + (2.5 if kind == "rain" else 4.5 if kind == "banyan" else 0)
    c = LEAF[int(rng.integers(0, len(LEAF)))]
    trunk_h = 4 + int(rng.integers(0, 3))
    d.line([(X, Y), (X, Y - trunk_h)], fill=(100, 74, 54), width=2 if not big else 3)
    d.point((X + 1, Y - 1), fill=(130, 100, 74))
    cy = Y - trunk_h - r * 0.62
    lobes = [(0.0, 0.0, 1.0)]
    for _ in range(3 + int(rng.integers(0, 2))):
        lobes.append((float(rng.uniform(-0.75, 0.75)), float(rng.uniform(-0.55, 0.35)), float(rng.uniform(0.55, 0.78))))
    lobes.sort(key=lambda t: t[1])
    for lx, ly, lr in lobes:
        w, h = r * 1.1 * lr, r * 0.85 * lr
        cx, cyy = X + lx * r * 0.9, cy + ly * r * 0.7
        cc = shade(c, 0.92 + 0.16 * float(rng.uniform(0, 1)))
        d.ellipse([cx - w, cyy - h, cx + w, cyy + h], fill=cc, outline=shade(cc, 0.46))
        d.ellipse([cx - w + 1, cyy - 1, cx + w * 0.4, cyy + h - 1], fill=shade(cc, 0.68))    # shaded underside, left
        d.ellipse([cx - w * 0.2, cyy - h + 1, cx + w - 1, cyy + h * 0.15], fill=shade(cc, 1.22))  # sunlit top, right
        for _ in range(int(lr * 4)):
            px = cx + float(rng.uniform(-w * 0.8, w * 0.8))
            py = cyy + float(rng.uniform(-h * 0.8, h * 0.6))
            d.point((px, py), fill=shade(cc, 1.4) if px > cx else shade(cc, 0.6))


# ------------------------------------------------------------------------------------------------ people
SHIRTS = [(206, 70, 60), (60, 110, 190), (244, 204, 70), (244, 244, 236), (60, 156, 104), (160, 70, 156), (244, 132, 60), (52, 52, 64),
          (224, 96, 140), (70, 170, 190)]
PANTS = [(54, 62, 96), (74, 70, 66), (150, 130, 96), (40, 40, 48), (92, 100, 130)]
SKIN = [(216, 164, 126), (180, 126, 92), (142, 96, 68), (120, 80, 56)]
HAIR = (34, 26, 26)


def person(d, X, Y, seed, walking=True):
    """About 8 px tall (props are drawn larger than life, as in the reference art). (X, Y) is the point between the feet."""
    s = int(seed)
    x, y = int(round(X)), int(round(Y))
    kind = s % 8
    shirt = SHIRTS[(s >> 1) % len(SHIRTS)]
    skin = SKIN[(s >> 4) % len(SKIN)]
    lo = shade(shirt, 0.74)
    # head and hair
    d.point((x, y - 8), fill=HAIR)
    d.point((x + 1, y - 8), fill=HAIR if kind != 5 else (240, 240, 236))
    d.point((x, y - 7), fill=skin)
    d.point((x + 1, y - 7), fill=shade(skin, 1.06))
    # torso (left column in shade, right column lit)
    for r in (-6, -5, -4, -3):
        d.point((x - 1, y + r), fill=lo)
        d.point((x, y + r), fill=shirt)
        d.point((x + 1, y + r), fill=shade(shirt, 1.12))
    if kind in (0, 1):                           # sari / long skirt: colour runs to the ground
        sari = shade(SHIRTS[(s >> 5) % len(SHIRTS)], 0.95)
        for r in (-2, -1):
            d.point((x - 1, y + r), fill=shade(sari, 0.78))
            d.point((x, y + r), fill=sari)
            d.point((x + 1, y + r), fill=shade(sari, 1.1))
        d.point((x, y), fill=(60, 50, 50))
        d.point((x + 1, y), fill=(60, 50, 50))
    elif kind in (2, 3):                         # white dhoti / lungi
        for r in (-2, -1):
            d.point((x - 1, y + r), fill=(214, 212, 204))
            d.point((x, y + r), fill=(244, 244, 238))
            d.point((x + 1, y + r), fill=(250, 250, 246))
        d.point((x, y), fill=skin)
        d.point((x + 1, y), fill=skin)
    else:                                         # trousers
        pc = PANTS[(s >> 6) % len(PANTS)]
        d.point((x - 1 if walking and (s & 1) else x, y - 2), fill=pc)
        d.point((x + 1, y - 2), fill=shade(pc, 1.1))
        d.point((x - 1 if walking and (s & 1) else x, y - 1), fill=pc)
        d.point((x + 1, y - 1), fill=shade(pc, 1.1))
        d.point((x, y), fill=(40, 36, 40))
        d.point((x + 1, y), fill=(40, 36, 40))


def crowd(d, X, Y, seed, n=6, spread=14):
    rng = np.random.default_rng(int(seed))
    pts = sorted(((float(rng.uniform(-spread, spread)), float(rng.uniform(-spread * 0.45, spread * 0.45))) for _ in range(n)), key=lambda p: p[1])
    for k, (dx, dy) in enumerate(pts):
        person(d, X + dx, Y + dy, int(rng.integers(0, 1 << 20)), walking=bool(k % 2))


AWN = [(210, 64, 52), (52, 108, 188), (236, 176, 50), (60, 150, 100), (186, 70, 150), (240, 120, 50)]
GOODS = [(236, 120, 60), (210, 50, 50), (110, 170, 70), (244, 210, 80), (170, 90, 150), (250, 250, 240)]


def stall(d, X, Y, seed):
    """Market stall with a striped awning, crates of goods and a seller."""
    s = int(seed)
    x, y = int(round(X)), int(round(Y))
    c = AWN[s % len(AWN)]
    c2 = (244, 240, 228)
    d.rectangle([x - 5, y - 3, x + 4, y], fill=(126, 92, 62), outline=(84, 60, 44))
    for i in range(-4, 4):
        d.point((x + i, y - 4), fill=GOODS[(s + i) % len(GOODS)])
        if i % 2 == 0:
            d.point((x + i, y - 5), fill=GOODS[(s + i + 2) % len(GOODS)])
    d.line([(x - 5, y - 9), (x - 5, y - 3)], fill=(90, 66, 48))
    d.line([(x + 4, y - 9), (x + 4, y - 3)], fill=(90, 66, 48))
    for k in range(5):
        d.rectangle([x - 5 + 2 * k, y - 11 + (k % 2 == 0) * 0, x - 4 + 2 * k, y - 8], fill=c if k % 2 else c2)
    d.line([(x - 5, y - 8), (x + 4, y - 8)], fill=shade(c, 0.7))
    person(d, x + 1, y - 2, s >> 3)


def cow(d, X, Y, seed):
    s = int(seed)
    x, y = int(round(X)), int(round(Y))
    body = [(244, 240, 228), (170, 120, 80), (90, 70, 60)][s % 3]
    d.rectangle([x - 4, y - 5, x + 2, y - 2], fill=body, outline=shade(body, 0.6))
    d.rectangle([x + 3, y - 6, x + 5, y - 4], fill=shade(body, 0.92), outline=shade(body, 0.6))
    d.point((x + 6, y - 6), fill=(236, 230, 210))
    for lx in (x - 3, x - 1, x + 1):
        d.line([(lx, y - 2), (lx, y)], fill=shade(body, 0.55))
    d.line([(x - 5, y - 5), (x - 6, y - 2)], fill=shade(body, 0.6))


def parked_scooter(d, X, Y, seed):
    s = int(seed)
    x, y = int(round(X)), int(round(Y))
    c = CAR[s % len(CAR)]
    d.rectangle([x - 2, y - 3, x + 2, y - 1], fill=c, outline=shade(c, 0.6))
    d.rectangle([x - 1, y - 4, x + 1, y - 3], fill=(40, 40, 46))
    d.point((x + 2, y - 5), fill=(70, 70, 76))
    d.point((x - 2, y), fill=(30, 30, 34))
    d.point((x + 2, y), fill=(30, 30, 34))


def handcart(d, X, Y, seed):
    s = int(seed)
    x, y = int(round(X)), int(round(Y))
    d.rectangle([x - 4, y - 4, x + 3, y - 2], fill=(150, 108, 70), outline=(96, 68, 46))
    for i in range(-3, 3):
        d.point((x + i, y - 5), fill=GOODS[(s + i) % len(GOODS)])
    d.point((x - 3, y - 1), fill=(30, 30, 34)); d.point((x + 2, y - 1), fill=(30, 30, 34))
    d.line([(x + 3, y - 3), (x + 6, y - 1)], fill=(96, 68, 46))


# rooftop and wall details -------------------------------------------------------------------------------
CLOTHES = [(214, 60, 60), (60, 110, 200), (244, 214, 70), (250, 250, 244), (70, 170, 110), (196, 80, 170), (244, 140, 60), (90, 200, 210)]


def laundry(d, X, Y, seed, n=6):
    """Washing line along the east-west diagonal, clothes hanging below it."""
    s = int(seed)
    x1, y1 = X + n * 2, Y - n
    d.line([(X, Y), (x1, y1)], fill=(110, 100, 96))
    d.line([(X, Y), (X, Y + 3)], fill=(110, 100, 96))
    d.line([(x1, y1), (x1, y1 + 3)], fill=(110, 100, 96))
    for k in range(n):
        cx, cy = X + 1 + k * 2 - (k % 2), Y - k * 0.5 - (k % 2) * 0
        cl = CLOTHES[(s + k * 3) % len(CLOTHES)]
        h = 2 + (s + k) % 3
        d.rectangle([cx, cy, cx + 1, cy + h], fill=cl)


def ac_unit(d, X, Y):
    x, y = int(X), int(Y)
    d.rectangle([x, y, x + 2, y + 1], fill=(226, 226, 222), outline=(120, 120, 120))
    d.point((x + 1, y), fill=(60, 60, 70))


def dish(d, X, Y):
    x, y = int(X), int(Y)
    d.line([(x, y), (x, y - 2)], fill=(90, 90, 96))
    d.ellipse([x - 2, y - 5, x + 1, y - 2], fill=(236, 236, 232), outline=(120, 120, 126))
    d.point((x, y - 4), fill=(60, 60, 66))


def roof_shed(d, X, Y, seed):
    """Small tin-roofed shed or stair-head on a flat roof."""
    s = int(seed)
    tin = [(150, 168, 190), (190, 120, 90), (176, 176, 170)][s % 3]
    prism(d, X, Y, 4.0, 2.6, 0.0, 0, 2.2, (232, 222, 200), tin)


def plant_pot(d, X, Y, seed):
    x, y = int(X), int(Y)
    d.rectangle([x, y - 1, x + 1, y], fill=(176, 96, 64))
    d.ellipse([x - 1, y - 4, x + 2, y - 1], fill=(70, 140, 70), outline=(44, 100, 52))


# ------------------------------------------------------------------------------------------------ vehicles
CAR = [(236, 236, 232), (200, 204, 208), (200, 60, 54), (60, 100, 170), (60, 62, 68), (210, 190, 140), (70, 130, 96)]
BUS = [(180, 56, 50), (50, 100, 170), (60, 130, 90), (230, 170, 50)]
GLASS = (70, 92, 116)


def vehicle(d, X, Y, theta, kind, seed):
    s = int(seed)
    if kind == "scooter":
        c = CAR[(s >> 2) % len(CAR)]
        prism(d, X, Y, 1.8, 0.55, theta, 0.2, 0.8, c, shade(c, 1.1))
        person(d, X + 0.5, Y - 1.3, s >> 5, walking=False)
    elif kind == "cycle":
        prism(d, X, Y, 1.7, 0.3, theta, 0.3, 0.6, (60, 60, 66), (80, 80, 86))
        person(d, X + 0.5, Y - 1.1, s >> 5, walking=False)
    elif kind == "auto":
        prism(d, X, Y, 2.6, 1.35, theta, 0.25, 1.0, (36, 36, 40), (50, 50, 54))
        prism(d, X - 0.2, Y - 0.2, 2.3, 1.3, theta, 1.0, 1.75, GLASS, (236, 190, 40))
    elif kind == "bus":
        c = BUS[(s >> 3) % len(BUS)]
        prism(d, X, Y, 9.5, 2.5, theta, 0.4, 2.0, c, c)
        prism(d, X, Y, 9.5, 2.5, theta, 2.0, 3.2, GLASS, shade(c, 1.15))
    elif kind == "truck":
        c = (200, 120, 50) if s % 2 else (60, 100, 150)
        prism(d, X + 1.8, Y, 2.0, 2.2, theta, 0.5, 2.4, shade(c, 0.9), shade(c, 1.1))
        prism(d, X - 1.5, Y, 5.0, 2.3, theta, 0.7, 3.0, (210, 204, 190), (226, 220, 206))
    else:  # car
        c = CAR[s % len(CAR)]
        prism(d, X, Y, 4.0, 1.75, theta, 0.3, 0.95, c, shade(c, 1.1))
        prism(d, X - 0.1, Y, 2.1, 1.6, theta, 0.95, 1.5, GLASS, shade(c, 1.12))


def scaled(fn, im, X, Y, factor, *args):
    """Draw sprite fn on a scratch layer and paste it back enlarged (nearest neighbour), feet anchored at (X, Y)."""
    from PIL import Image, ImageDraw
    S = 64
    tmp = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    fn(ImageDraw.Draw(tmp), S / 2, S - 6, *args)
    big = tmp.resize((int(S * factor), int(S * factor)), Image.NEAREST)
    im.paste(big, (int(round(X - S / 2 * factor)), int(round(Y - (S - 6) * factor))), big)
