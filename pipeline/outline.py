"""The mapped area: Tiruchirappalli's real city outline instead of a plain rectangle.

Shape = the Trichy City Municipal Corporation boundary (Overture divisions, from OpenStreetMap)
        + a margin of surrounding ground
        + a disc around each landmark that lies outside the corporation (Samayapuram, Mukkombu, Kallanai, Vayalur, NIT/BHEL)
        + a narrow strip joining each disc to the city, so the map stays one piece.
Everything is computed in metres, then projected to level-17 iso pixels.

  .venv/bin/python pipeline/outline.py        -> data/outline.pkl, web/data/outline.json, /tmp/outline.png
"""
from __future__ import annotations
import pickle, json, math
import duckdb, shapely
from shapely import wkb
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import nearest_points, transform

from config import DATA, ROOT, BBOX, to_metres, iso_from_metres, WIDTH, HEIGHT

MARGIN = 1300         # metres of ground around the corporation boundary
EDGE_SMOOTH = 2400    # closing radius, rounds off sharp notches and blends the landmark discs into the city

# lon, lat, radius in metres
EXCLAVES = {
    "samayapuram": (78.7391, 10.9184, 1800),
    "mukkombu": (78.5880, 10.8870, 1800),
    "kallanai": (78.8185, 10.8325, 2000),
    "vayalur": (78.6231, 10.8289, 1500),
    "nit": (78.8160, 10.7620, 2200),
    "panjappur": (78.6526, 10.7483, 1500),
    "butterfly-park": (78.6373, 10.8778, 1100),
    "kk-nagar": (78.6890, 10.7560, 1400),
}
STRIP = 1100          # width of connecting strips, metres
OUT = DATA / "outline.pkl"


def corporation_m():
    con = duckdb.connect(); con.execute("INSTALL spatial; LOAD spatial")
    g = con.execute(f"select ST_AsWKB(geometry) from '{DATA}/raw/divisions.parquet' where name='Trichy Corporation Limits'").fetchone()[0]
    g = wkb.loads(bytes(g))
    return transform(lambda x, y, z=None: tuple(zip(*[to_metres(a, b) for a, b in zip(x, y)])), g)


def build():
    corp = corporation_m()
    shape = corp.buffer(MARGIN)
    for name, (lon, lat, r) in EXCLAVES.items():
        c = Point(*to_metres(lon, lat))
        disc = c.buffer(r, quad_segs=24)
        a, b = nearest_points(shape, c)
        if a.distance(c) > r * 0.8:
            shape = shape.union(LineString([a, c]).buffer(STRIP / 2))
        shape = shape.union(disc)
    shape = shape.buffer(EDGE_SMOOTH, quad_segs=10).buffer(-EDGE_SMOOTH, quad_segs=10)
    shape = shape.buffer(-120, quad_segs=6).buffer(120, quad_segs=6)
    if shape.geom_type == "MultiPolygon":
        shape = max(shape.geoms, key=lambda g: g.area)
    shape = Polygon(shape.exterior)  # no holes
    shape = shape.simplify(8)
    # keep inside the render bbox
    bx = Polygon([to_metres(BBOX[e], BBOX[n]) for e, n in (("west", "south"), ("east", "south"), ("east", "north"), ("west", "north"))])
    shape = shape.intersection(bx)
    if shape.geom_type == "MultiPolygon":
        shape = max(shape.geoms, key=lambda g: g.area)
    px = transform(lambda x, y, z=None: tuple(zip(*[iso_from_metres(a, b) for a, b in zip(x, y)])), shape)
    with open(OUT, "wb") as f:
        pickle.dump(dict(metres=shape, px=px), f)
    coords = [[round(x), round(y)] for x, y in px.exterior.coords]
    (ROOT / "web" / "data").mkdir(parents=True, exist_ok=True)
    (ROOT / "web" / "data" / "outline.json").write_text(json.dumps(dict(poly=coords, width=WIDTH, height=HEIGHT)))
    print("outline: %.0f km2 (bbox %.0f km2), %d vertices" % (shape.area / 1e6, bx.area / 1e6, len(coords)))
    return px


def load():
    with open(OUT, "rb") as f:
        return pickle.load(f)["px"]


if __name__ == "__main__":
    build()
