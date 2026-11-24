"""Sprite atlases for the animated traffic: web/assets/vehicles.png (+ .json) and web/assets/trains.png.

Each row is one kind/colour variant, 16 headings across (heading 0 = east on the ground, counter-clockwise, same as the metre frame).
Drawn with the same prism toolkit and light as the map tiles, so they sit in the same world.
"""
import json, math
from PIL import Image, ImageDraw

from config import ROOT
import sprites as SP
from sprites import prism, shade

OUT = ROOT / "web" / "assets"
NH = 16
VCELL = (48, 44)
VORG = (24, 32)
TCELL = (80, 64)
TORG = (40, 44)
GLASS = (70, 92, 116)

ROAD = [("scooter", 7), ("cycle", 3), ("auto", 1), ("car", 7), ("bus", 4), ("truck", 2)]


def road_seed(kind, v):
    return {"scooter": (v << 2) | ((v * 3 + 1) << 5), "cycle": v << 5, "auto": 0, "car": v, "bus": v << 3, "truck": v}[kind]


def shadow(d, X, Y, L, theta):
    # soft contact shadow: two translucent ellipses under the vehicle, pushed away from the sun
    for k, a in ((1.0, 40), (0.6, 40)):
        r = L * 0.9 * k
        d.ellipse([X - r * 0.9 - 1, Y - r * 0.28 + 1, X + r * 0.5, Y + r * 0.26 + 2], fill=(20, 24, 40, a))


def road_atlas():
    rows = []
    for kind, n in ROAD:
        for v in range(n):
            rows.append((kind, v))
    W, H = VCELL[0] * NH, VCELL[1] * len(rows)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for r, (kind, v) in enumerate(rows):
        for h in range(NH):
            cell = Image.new("RGBA", VCELL, (0, 0, 0, 0))
            d = ImageDraw.Draw(cell, "RGBA")
            theta = h * 2 * math.pi / NH
            L = {"bus": 9.5, "truck": 8, "car": 4, "auto": 2.6, "scooter": 1.8, "cycle": 1.7}[kind]
            shadow(d, VORG[0], VORG[1], L / 2 * 1.4, theta)
            SP.vehicle(d, VORG[0], VORG[1], theta, kind, road_seed(kind, v))
            im.paste(cell, (h * VCELL[0], r * VCELL[1]))
    rowmap, i = {}, 0
    for kind, n in ROAD:
        rowmap[kind] = [i, n]; i += n
    return im, dict(cell=list(VCELL), origin=list(VORG), headings=NH, rows=rowmap)


def coach(d, X, Y, th, body, stripe=None):
    prism(d, X, Y, 21, 3.1, th, 0.55, 1.6, body, shade(body, 1.05))
    if stripe:
        prism(d, X, Y, 21.05, 3.15, th, 1.0, 1.4, stripe, stripe, outline=False)
    prism(d, X, Y, 21, 3.1, th, 1.6, 2.7, GLASS, GLASS)
    prism(d, X, Y, 21, 3.1, th, 2.7, 3.6, body, shade(body, 1.22))


def loco(d, X, Y, th, body, accent):
    prism(d, X, Y, 19, 3.0, th, 0.6, 3.5, body, shade(body, 1.2))
    prism(d, X, Y, 6, 3.02, th, 0.9, 2.2, accent, accent, outline=False)
    prism(d, X, Y, 19, 2.2, th, 3.5, 3.9, shade(body, 0.8), shade(body, 1.0))


def wagon(d, X, Y, th, col):
    prism(d, X, Y, 13.5, 2.9, th, 0.6, 3.1, col, shade(col, 1.14))


TRAIN = [("loco", [((52, 92, 168), (240, 200, 60)), ((186, 62, 52), (240, 232, 200))]),
         ("coach", [((52, 92, 168), (240, 232, 200)), ((176, 58, 52), (240, 220, 140)), ((60, 120, 92), (230, 230, 220))]),
         ("wagon", [((128, 92, 72),), ((112, 120, 130),)])]


def train_atlas():
    rows = [(k, v) for k, vs in TRAIN for v in vs]
    W, H = TCELL[0] * NH, TCELL[1] * len(rows)
    im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rowmap, i = {}, 0
    for kind, vs in TRAIN:
        rowmap[kind] = [i, len(vs)]; i += len(vs)
    for r, (kind, v) in enumerate(rows):
        for h in range(NH):
            cell = Image.new("RGBA", TCELL, (0, 0, 0, 0))
            d = ImageDraw.Draw(cell, "RGBA")
            th = h * 2 * math.pi / NH
            X, Y = TORG
            shadow(d, X, Y, 10, th)
            if kind == "loco":
                loco(d, X, Y, th, *v)
            elif kind == "coach":
                coach(d, X, Y, th, *v)
            else:
                wagon(d, X, Y, th, *v)
            im.paste(cell, (h * TCELL[0], r * TCELL[1]))
    return im, dict(cell=list(TCELL), origin=list(TORG), headings=NH, rows=rowmap, len=dict(loco=19, coach=21, wagon=13.5))


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    a, ma = road_atlas()
    a.save(OUT / "vehicles.png", optimize=True)
    b, mb = train_atlas()
    b.save(OUT / "trains.png", optimize=True)
    (OUT / "atlas.json").write_text(json.dumps(dict(vehicles=ma, trains=mb)))
    print("vehicles", a.size, "trains", b.size)
