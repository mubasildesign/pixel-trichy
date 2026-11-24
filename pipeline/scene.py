"""Turn the raw Overture parquet files into one projected, queryable scene (data/scene.pkl).

All geometry is converted to deepest-level iso pixel coordinates (ground plane, height handled by the renderer).
"""
from __future__ import annotations
import pickle, hashlib
import numpy as np
import duckdb
import shapely
from shapely import STRtree
from shapely.geometry import Polygon, box

from config import DATA, BBOX, K, WIDTH, HEIGHT, LON0, LAT0, M_PER_DEG_LON, M_PER_DEG_LAT, iso_from_metres, to_metres

RAW = DATA / "raw"
SCENE = DATA / "scene.pkl"
_CORE = iso_from_metres(*to_metres(78.6935, 10.8260))  # Chathiram / old city, roughly


def _project(geoms):
    """Vectorised lon/lat -> iso pixel for a shapely array."""
    def f(c):
        x = (c[:, 0] - LON0) * M_PER_DEG_LON
        y = (c[:, 1] - LAT0) * M_PER_DEG_LAT
        px, py = iso_from_metres(x, y)
        return np.column_stack([px, py])
    return shapely.transform(geoms, f)


def _metres(geoms):
    def f(c):
        return np.column_stack([(c[:, 0] - LON0) * M_PER_DEG_LON, (c[:, 1] - LAT0) * M_PER_DEG_LAT])
    return shapely.transform(geoms, f)


def _iso_from_metre_geoms(geoms):
    def f(c):
        px, py = iso_from_metres(c[:, 0], c[:, 1])
        return np.column_stack([px, py])
    return shapely.transform(geoms, f)


ROAD_W = {  # metres, full carriageway width as drawn
    "motorway": 16, "trunk": 14, "primary": 12, "secondary": 10, "tertiary": 8, "unclassified": 6,
    "residential": 6, "living_street": 5, "pedestrian": 4, "service": 4, "track": 3.5,
    "footway": 1.6, "path": 1.4, "steps": 1.4, "cycleway": 1.6, "bridleway": 1.4, "unknown": 4,
}
RIVER_W = {"kaveri": 520, "cauvery": 520, "kollidam": 420, "coleroon": 420, "uyyakondan": 60, "kudamurutti": 60}


def _read(name, cols):
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial")
    path = RAW / f"{name}.parquet"
    if not path.exists():
        return [], {}
    q = f"select ST_AsWKB(geometry) as g, {', '.join(cols)} from '{path}'" if cols else f"select ST_AsWKB(geometry) as g from '{path}'"
    rows = con.execute(q).fetchall()
    geoms = shapely.from_wkb([bytes(r[0]) for r in rows])
    attrs = {c.split(' as ')[-1].strip(): [r[i + 1] for r in rows] for i, c in enumerate(cols)}
    return geoms, attrs


def _hash01(s: str) -> float:
    return int(hashlib.md5(s.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF


def build():
    b = BBOX
    clip = Polygon([iso_from_metres(*to_metres(b[e], b[n])) for e, n in (('west','south'),('east','south'),('east','north'),('west','north'))]).buffer(30)
    scene = {}

    # --- land cover (forest / crop / grass ...) ---------------------------------------------------
    geoms, a = _read("land_cover", ["subtype"])
    if len(geoms):
        g = _project(geoms)
        g = shapely.intersection(shapely.make_valid(g), clip)
        keep = [i for i, x in enumerate(g) if not x.is_empty]
        scene["land_cover"] = (np.array([g[i] for i in keep], dtype=object), [a["subtype"][i] for i in keep])

    # --- land use (residential, park, farmland ...) -----------------------------------------------
    geoms, a = _read("land_use", ["subtype", "class"])
    if len(geoms):
        g = shapely.intersection(shapely.make_valid(_project(geoms)), clip)
        keep = [i for i, x in enumerate(g) if not x.is_empty]
        scene["land_use"] = (np.array([g[i] for i in keep], dtype=object), [(a["subtype"][i], a["class"][i]) for i in keep])

    # --- water: polygons as-is, linear waterways buffered in metres ---------------------------------
    geoms, a = _read("water", ["subtype", "class", "names.primary as name"])
    gm = _metres(geoms)
    out, meta = [], []
    for i, g in enumerate(gm):
        sub, cls, name = a["subtype"][i], a["class"][i], (a["name"][i] or "")
        if g.geom_type in ("LineString", "MultiLineString"):
            w = {"river": 40, "stream": 8, "canal": 10}.get(sub, 6)
            if cls == "ditch" or cls == "drain":
                w = 4
            for key, rw in RIVER_W.items():
                if key in name.lower():
                    w = rw
            g = g.buffer(w / 2, cap_style="round", quad_segs=3)
        out.append(g)
        meta.append((sub, cls))
    pg = shapely.intersection(shapely.make_valid(_iso_from_metre_geoms(np.array(out, dtype=object))), clip)
    keep = [i for i, x in enumerate(pg) if not x.is_empty]
    scene["water"] = (np.array([pg[i] for i in keep], dtype=object), [meta[i] for i in keep])

    # --- roads and rail: buffered in metres so widths are right on the ground, then projected -------
    geoms, a = _read("segments", ["subtype", "class", "names.primary as name"])
    gm = _metres(geoms)
    polys, meta = [], []
    for i, g in enumerate(gm):
        sub, cls = a["subtype"][i], a["class"][i]
        if sub == "rail":
            w = 3.0
        elif sub == "road":
            w = ROAD_W.get(cls, 4)
        else:
            continue
        polys.append(g.buffer(w / 2, cap_style="flat", join_style="round", quad_segs=2))
        meta.append((sub, cls, a["name"][i]))
    pg = shapely.intersection(shapely.make_valid(_iso_from_metre_geoms(np.array(polys, dtype=object))), clip)
    keep = [i for i, x in enumerate(pg) if not x.is_empty]
    scene["segments"] = (np.array([pg[i] for i in keep], dtype=object), [meta[i] for i in keep])
    # centre lines of named roads, used for labels and search
    lines = _iso_from_metre_geoms(gm)
    named = [(lines[i], (a["subtype"][i], a["class"][i], a["name"][i])) for i in range(len(lines))
             if a["subtype"][i] == "road" and a["name"][i]]
    scene["road_names"] = (np.array([n[0] for n in named], dtype=object), [n[1] for n in named])

    # --- infrastructure (bridges, piers, runways ...) ----------------------------------------------
    geoms, a = _read("infrastructure", ["subtype", "class"])
    if len(geoms):
        g = shapely.intersection(shapely.make_valid(_project(geoms)), clip)
        keep = [i for i, x in enumerate(g) if not x.is_empty]
        scene["infrastructure"] = (np.array([g[i] for i in keep], dtype=object), [(a["subtype"][i], a["class"][i]) for i in keep])

    # --- buildings ---------------------------------------------------------------------------------
    geoms, a = _read("buildings", ["height", "num_floors", "class", "subtype", "id", "roof_shape", "names.primary as name"])
    if len(geoms):
        g = _project(geoms)
        polys, meta = [], []
        for i, geom in enumerate(g):
            if geom is None or geom.is_empty:
                continue
            parts = [geom] if geom.geom_type == "Polygon" else list(getattr(geom, "geoms", []))
            for p in parts:
                if p.geom_type != "Polygon" or p.area < 6:
                    continue
                h = a["height"][i]
                if h is None and a["num_floors"][i]:
                    h = a["num_floors"][i] * 3.3
                known = h is not None
                if h is None:
                    # No usable height data (Open Buildings 2.5D needs Earth Engine). Infer from footprint size,
                    # distance to the old city, and a stable per-building random factor. This is an estimate.
                    r = _hash01(a["id"][i])
                    area_m2 = p.area / (K * K)
                    if area_m2 < 40:
                        h = 3.2 + 1.5 * r
                    elif area_m2 < 150:
                        h = 5.5 + 4.5 * r
                    elif area_m2 < 600:
                        h = 8 + 7 * r
                    else:
                        h = 11 + 12 * min(1.0, area_m2 / 3000) * (0.5 + r)
                    cx, cy = p.centroid.x, p.centroid.y
                    d = np.hypot(cx - _CORE[0], cy - _CORE[1]) / K  # metres from the old city core
                    h *= 1.0 + 0.5 * max(0.0, 1 - d / 3500)
                    h = min(h, 40.0)
                polys.append(p)
                meta.append((float(h), known, a["class"][i], a["name"][i], a["roof_shape"][i]))
        scene["buildings"] = (np.array(polys, dtype=object), meta)

    # --- settled-ground density (built-up areas get dusty ground instead of field green) ---------------
    from scipy.ndimage import gaussian_filter
    cell = 16
    polys = scene["buildings"][0]
    cen = shapely.centroid(polys)
    cx, cy = shapely.get_x(cen), shapely.get_y(cen)
    area = shapely.area(polys) / (K * K)
    H, _, _ = np.histogram2d(cy, cx, bins=[int(HEIGHT // cell) + 2, int(WIDTH // cell) + 2],
                             range=[[0, (int(HEIGHT // cell) + 2) * cell], [0, (int(WIDTH // cell) + 2) * cell]], weights=np.minimum(area, 400))
    dens = gaussian_filter(H / (cell * cell / (K * K)), 2.2)  # roughly: fraction of ground covered, smoothed
    scene["settled"] = (dens.astype(np.float32), cell)

    for key, val in scene.items():
        if key == "settled":
            continue
        scene[key] = (val[0], val[1])
        print(key, len(val[0]))
    with open(SCENE, "wb") as f:
        pickle.dump(scene, f, protocol=pickle.HIGHEST_PROTOCOL)
    return scene


def add_lines():
    """Add road/rail centre lines (px space) to an existing scene.pkl, used for traffic, markings and street trees."""
    with open(SCENE, "rb") as f:
        scene = pickle.load(f)
    geoms, a = _read("segments", ["subtype", "class"])
    lines = _iso_from_metre_geoms(_metres(geoms))
    keep = [i for i, g in enumerate(lines) if g.geom_type == "LineString" and a["subtype"][i] in ("road", "rail") and g.length > 6]
    scene["road_lines"] = (np.array([lines[i] for i in keep], dtype=object),
                           [(a["subtype"][i], a["class"][i] if a["subtype"][i] == "road" else "rail") for i in keep])
    with open(SCENE, "wb") as f:
        pickle.dump(scene, f, protocol=pickle.HIGHEST_PROTOCOL)
    print("road_lines", len(keep))


def clean():
    """Fix footprints that landed in water, on railway track or on top of carriageways.

    Overture water for the big rivers is only a centre line, so we buffer it by a guessed width. That guess floods banks
    that have houses on them. We therefore carve land back out of linear water wherever a building stands, and drop
    buildings that really sit in ponds or tanks, on the rail corridor, or mostly on a main road.
    Reads scene.raw.pkl (made on first run) so it can be re-run safely.
    """
    import shutil
    raw = DATA / "scene.raw.pkl"
    if not raw.exists():
        shutil.copy(SCENE, raw)
    with open(raw, "rb") as f:
        sc = pickle.load(f)
    bg, bm = sc["buildings"]
    area = shapely.area(bg)
    n0 = len(bg)
    keep = np.ones(n0, bool)
    why = {"pond": 0, "rail": 0, "road": 0}
    named = np.array([bool(m[3]) or (m[2] in ("religious", "transportation", "education", "civic", "medical", "entertainment")) for m in bm])

    # ponds / tanks / lakes: a building mostly inside is a bad footprint
    wg, wm = sc["water"]
    still = [i for i, m in enumerate(wm) if m[0] in ("pond", "lake", "reservoir", "water", "spring", "human_made")]
    if still:
        su = shapely.union_all(wg[still])
        fr = shapely.area(shapely.intersection(bg, su)) / area
        bad = (fr > 0.35) & ~named
        why["pond"] = int(bad.sum()); keep &= ~bad

    # rail corridor: 3 m wide track plus ballast
    sg, sm = sc["segments"]
    rail = [i for i, m in enumerate(sm) if m[0] == "rail"]
    ru = shapely.union_all(sg[rail]).buffer(2.0 * K)
    fr = shapely.area(shapely.intersection(bg, ru)) / area
    bad = (fr > 0.12) & ~named
    why["rail"] = int(bad.sum()); keep &= ~bad

    # main roads: footprint mostly on tarmac is a misregistered building
    main = [i for i, m in enumerate(sm) if m[0] == "road" and m[1] in ("motorway", "trunk", "primary", "secondary", "tertiary")]
    mu = shapely.union_all(sg[main])
    fr = shapely.area(shapely.intersection(bg, mu)) / area
    bad = (fr > 0.45) & ~named
    why["road"] = int(bad.sum()); keep &= ~bad
    print("dropped", why, "of", n0)

    kept_idx = np.nonzero(keep)[0]
    sc["buildings"] = (bg[kept_idx], [bm[i] for i in kept_idx])

    # carve land out of linear water wherever buildings stand
    bt = STRtree(sc["buildings"][0])
    bgk = sc["buildings"][0]
    out = []
    for g, m in zip(wg, wm):
        if m[0] in ("river", "canal", "stream"):
            hit = bt.query(g, predicate="intersects")
            if len(hit):
                land = shapely.union_all(shapely.buffer(bgk[hit], 4.0 * K if m[0] == "river" else 1.2 * K))
                g = shapely.make_valid(g.difference(land))
        out.append(g)
    ok = [i for i, g in enumerate(out) if not g.is_empty]
    sc["water"] = (np.array([out[i] for i in ok], dtype=object), [wm[i] for i in ok])
    with open(SCENE, "wb") as f:
        pickle.dump(sc, f, protocol=pickle.HIGHEST_PROTOCOL)
    print("buildings", len(sc["buildings"][0]), "water polys", len(ok))


def load():
    with open(SCENE, "rb") as f:
        scene = pickle.load(f)
    trees = {}
    for key, (geoms, meta) in scene.items():
        if key == "settled":
            continue
        trees[key] = STRtree(geoms)
    return scene, trees


if __name__ == "__main__":
    import sys
    {"lines": add_lines, "clean": clean}.get(sys.argv[1] if sys.argv[1:] else "", build)()
