"""Road chains for the animated traffic -> web/data/traffic.json.

Road segments are joined into long continuous polylines (straight-through at junctions) so vehicles can run for blocks
instead of disappearing every 80 m. Coordinates are deepest-level iso pixels, clipped to the city outline.
"""
import json, math, pickle
import numpy as np
import shapely
import shapely.affinity
from shapely.geometry import LineString, MultiPolygon
from shapely.strtree import STRtree

from config import DATA, ROOT, K, VK
import outline

STEP = 6.0  # px of road between occlusion samples (the browser reads the flag at the vehicle's arc length)
RAIL_STEP = 5.0  # rail lines are densified so their station distances still hold

CLASSES = ["motorway", "trunk", "primary", "secondary", "tertiary", "unclassified", "residential"]
MOVING = CLASSES[:6]          # no animated traffic on residential lanes
MIN_LEN = {"motorway": 80, "trunk": 80, "primary": 80, "secondary": 80, "tertiary": 90, "unclassified": 140, "residential": 220}
BAD_GAP = 14.0                # px of blocked road (a level crossing, a kerb clipped by a footprint) that is still driven through


def chains_from(lines, max_turn_deg=38):
    n = len(lines)
    coords = [np.asarray(l.coords) for l in lines]
    ends = {}
    for i, c in enumerate(coords):
        for e, p in ((0, c[0]), (1, c[-1])):
            ends.setdefault((round(p[0] / 3), round(p[1] / 3)), []).append((i, e))
    link = {}
    for key, lst in ends.items():
        if len(lst) < 2:
            continue
        vecs = []
        for i, e in lst:
            c = coords[i]
            v = (c[min(2, len(c) - 1)] - c[0]) if e == 0 else (c[max(-3, -len(c))] - c[-1])
            nv = np.hypot(*v) or 1
            vecs.append(v / nv)
        cand = []
        for a in range(len(lst)):
            for b in range(a + 1, len(lst)):
                if lst[a][0] == lst[b][0]:
                    continue
                cosang = float(np.dot(vecs[a], vecs[b]))     # -1 = perfectly straight through
                if cosang < -math.cos(math.radians(max_turn_deg)):
                    cand.append((cosang, a, b))
        cand.sort()
        used = set()
        for _, a, b in cand:
            if a in used or b in used:
                continue
            used.add(a); used.add(b)
            link[lst[a]] = lst[b]; link[lst[b]] = lst[a]
    seen = [False] * n
    out = []

    def walk(i, e_start):
        # start at segment i entering via end e_start, follow links
        pts = []
        cur, enter = i, e_start
        while cur is not None and not seen[cur]:
            seen[cur] = True
            c = coords[cur]
            pts.append(c if enter == 0 else c[::-1])
            nxt = link.get((cur, 1 - enter))
            if nxt is None:
                break
            cur, enter = nxt
        return np.vstack([p if k == 0 else p[1:] for k, p in enumerate(pts)])
    for i in range(n):
        if seen[i]:
            continue
        # find the start of this chain: go backwards while linked
        cur, e = i, 0
        guard = 0
        while (cur, e) in link and guard < 100000:
            nxt = link[(cur, e)]
            if nxt[0] == i:
                break
            cur, e = nxt[0], 1 - nxt[1]
            guard += 1
        out.append(walk(cur, e))
    return out


def building_silhouettes(sc):
    """Screen-space silhouette and sort key of every building, the same way render.py draws them.

    A vehicle on the ground is hidden when a silhouette covers it and that building is drawn after it (its footprint
    reaches lower on the screen). This runs once at build time, so the browser only reads flags.
    """
    bg, bm = sc["buildings"]
    sil, key = [], []
    for g, m in zip(bg, bm):
        h, known, cls = m[0], m[1], m[2]
        if not known:
            h *= 0.74                      # HEIGHT_TRIM in render.py
        area_geo = g.area / (K * K)
        if area_geo > 2000 and not known:
            h = min(h, 14.0)
            if cls in ("temple", "church", "mosque", "place_of_worship") or area_geo > 6000:
                h = min(h, 6.0)
        roof = shapely.affinity.translate(g, 0, -h * VK)
        sil.append(shapely.convex_hull(MultiPolygon([g, roof]) if g.geom_type == "Polygon" else shapely.union(g, roof)))
        key.append(g.bounds[3])            # render sorts by the footprint's largest screen y
    return np.array(sil, dtype=object), np.array(key)


def occlusion(points_xy, sil, key):
    """1 where some building in front covers the point."""
    occ = np.zeros(len(points_xy), dtype=np.uint8)
    if len(points_xy) == 0:
        return occ
    tree = STRtree(sil)
    pts = shapely.points(points_xy)
    hit_p, hit_b = tree.query(pts, predicate="intersects")
    front = key[hit_b] > points_xy[hit_p, 1]
    occ[np.unique(hit_p[front])] = 1
    return occ


def deck_heights(points_xy, decks, dirs):
    """Deck height (m) at each sample that runs along a bridge or flyover centre line, else 0."""
    z = np.zeros(len(points_xy), np.float32)
    if not decks or not len(points_xy):
        return z
    segs, zs = [], []
    for dk in decks:
        p = np.asarray(dk["px"], float); h = np.asarray(dk["z"], float)
        for i in range(len(p) - 1):
            segs.append(LineString([p[i], p[i + 1]])); zs.append((h[i], h[i + 1], p[i], p[i + 1]))
    tree = STRtree(segs)
    pts = shapely.points(points_xy)
    hit_p, hit_s = tree.query(pts, predicate="dwithin", distance=5.0)
    for pi, si in zip(hit_p, hit_s):
        h0, h1, a, b = zs[si]
        ab = b - a; L = float(np.hypot(*ab)) or 1.0
        if abs(float(np.dot(ab / L, dirs[pi]))) < 0.85:     # crossing under the deck, not running along it
            continue
        t = float(np.clip(np.dot(points_xy[pi] - a, ab) / (L * L), 0, 1))
        z[pi] = max(z[pi], h0 + (h1 - h0) * t)
    return z


def blocked(points_xy, sc, hide):
    """Samples a car cannot be on: inside a building footprint, in water, on the rail corridor or inside a monument compound."""
    bad = np.zeros(len(points_xy), bool)
    pts = shapely.points(points_xy)
    bg = sc["buildings"][0]
    inner = shapely.buffer(bg, -1.5)
    t = STRtree(inner)
    hp, _ = t.query(pts, predicate="within")
    bad[hp] = True
    wg = sc["water"][0]
    t = STRtree(wg)
    hp, _ = t.query(pts, predicate="within")
    bad[hp] = True
    sg, sm = sc["segments"]
    rail = [sg[i] for i, m in enumerate(sm) if m[0] == "rail"]
    t = STRtree(rail)
    hp, _ = t.query(pts, predicate="within")
    bad[hp] = True
    if hide:
        t = STRtree(hide)
        hp, _ = t.query(pts, predicate="within")
        bad[hp] = True
    return bad


def monument_occlusion(points_xy, parts):
    """1 where a baked monument sprite (bridge deck, gopuram, stadium stand ...) is drawn over the point after it."""
    import io
    from PIL import Image
    occ = np.zeros(len(points_xy), np.uint8)
    boxes = [shapely.box(p["ox"], p["oy"], p["ox"] + p["w"], p["oy"] + p["h"]) for p in parts]
    tree = STRtree(boxes)
    hit_p, hit_b = tree.query(shapely.points(points_xy), predicate="intersects")
    cache = {}
    for pi, bi in zip(hit_p, hit_b):
        p = parts[bi]
        if p["ground"] or occ[pi] or p["y"] <= points_xy[pi, 1]:
            continue
        a = cache.get(bi)
        if a is None:
            a = np.asarray(Image.open(io.BytesIO(p["rgba"])).getchannel("A"))
            cache[bi] = a
        x, y = int(points_xy[pi, 0] - p["ox"]), int(points_xy[pi, 1] - p["oy"]) - 3   # test the vehicle body, not its wheels
        if 0 <= y < a.shape[0] and 0 <= x < a.shape[1] and a[y, x] > 0:
            occ[pi] = 1
    return occ


def split_runs(n, bad, step):
    """Index ranges [i0, i1) of drivable runs, bridging blocked gaps shorter than BAD_GAP."""
    gap = int(BAD_GAP // step)
    b = bad.copy()
    i = 0
    while i < n:
        if b[i]:
            j = i
            while j < n and b[j]:
                j += 1
            if j - i <= gap and i > 0 and j < n:
                b[i:j] = False
            i = j
        else:
            i += 1
    runs, i = [], 0
    while i < n:
        if b[i]:
            i += 1
            continue
        j = i
        while j < n and not b[j]:
            j += 1
        runs.append((i, j))
        i = j
    return runs


def densify(coords, step=RAIL_STEP):
    ln = shapely.segmentize(LineString(coords), step)
    return np.asarray(ln.coords)


def uniform_samples(ln, step=STEP):
    """Points every `step` px of arc length along a line, including the start."""
    d = np.arange(0.0, ln.length + step * 0.5, step)
    return shapely.get_coordinates(shapely.line_interpolate_point(ln, d))


def main():
    with open(DATA / "scene.pkl", "rb") as f:
        sc = pickle.load(f)
    lg, lm = sc["road_lines"]
    poly = outline.load().buffer(40)
    print("silhouettes ...", flush=True)
    sil, key = building_silhouettes(sc)
    import monuments
    from shapely.geometry import Polygon
    parts, hide_rings = monuments.load()
    decks = monuments.load_decks()
    fly = monuments.load_fly_hide()
    hide = [Polygon(r) for k, r in enumerate(hide_rings) if len(r) >= 3 and k not in fly]
    cand = []
    for ci, cls in enumerate(CLASSES):
        if cls not in MOVING:
            continue
        idx = [i for i, m in enumerate(lm) if m[0] == "road" and m[1] == cls]
        segs = []
        for i in idx:
            g = shapely.intersection(lg[i], poly)
            for part in getattr(g, "geoms", [g]):
                if part.geom_type == "LineString" and part.length > 4:
                    segs.append(part)
        for ch in chains_from(segs):
            ln = LineString(ch).simplify(1.3)
            if ln.length >= MIN_LEN[cls]:
                cand.append((ci, ln))
        print(cls, len(idx), "segments", flush=True)
    # sample every chain, find deck heights and blocked stretches, and cut chains where they leave the road
    samples = [uniform_samples(ln) for _, ln in cand]
    allp = np.vstack(samples)
    dirs = []
    for sm in samples:
        dv = np.gradient(sm, axis=0) if len(sm) > 1 else np.array([[1.0, 0.0]])
        nv = np.hypot(dv[:, 0], dv[:, 1])[:, None]; nv[nv == 0] = 1
        dirs.append(dv / nv)
    dirs = np.vstack(dirs)
    z = deck_heights(allp, decks, dirs)
    bad = blocked(allp, sc, hide) & (z < 0.5)
    print("deck samples", int((z > 0.5).sum()), "blocked", int(bad.sum()), "of", len(allp), flush=True)
    result, pieces, total = [], [], 0
    o = 0
    for (ci, ln), sm in zip(cand, samples):
        n = len(sm)
        for i0, i1 in split_runs(n, bad[o:o + n], STEP):
            sub = sm[i0:i1]
            if len(sub) < 2 or (i1 - i0) * STEP < MIN_LEN[CLASSES[ci]]:
                continue
            sl = LineString(sub).simplify(1.3)
            pieces.append((ci, sl, o + i0, o + i1))
        o += n
    # resample each kept piece and flag occlusion (buildings and monuments in front) or deck height
    samp2 = [uniform_samples(sl) for _, sl, _, _ in pieces]
    allq = np.vstack(samp2)
    dirs2 = []
    for sm in samp2:
        dv = np.gradient(sm, axis=0) if len(sm) > 1 else np.array([[1.0, 0.0]])
        nv = np.hypot(dv[:, 0], dv[:, 1])[:, None]; nv[nv == 0] = 1
        dirs2.append(dv / nv)
    z2 = deck_heights(allq, decks, np.vstack(dirs2))
    occ = occlusion(allq, sil, key) | monument_occlusion(allq, parts)
    o = 0
    for (ci, sl, _, _), sm in zip(pieces, samp2):
        n = len(sm)
        flags = []
        for k in range(n):
            zz = z2[o + k]
            flags.append(chr(65 + min(40, int(round(zz * 2)))) if zz > 0.5 else ("1" if occ[o + k] else "0"))
        result.append(dict(c=ci, p=np.round(np.asarray(sl.coords)).astype(int).reshape(-1).tolist(), occ="".join(flags)))
        total += sl.length
        o += n
    print("road samples", len(allq), "occluded", round(float(occ.mean()) * 100, 1), "%, on decks", int((z2 > 0.5).sum()), flush=True)
    out = ROOT / "web" / "data" / "traffic.json"
    out.write_text(json.dumps(dict(classes=CLASSES, step=STEP, chains=result), separators=(",", ":")))
    print(len(result), "chains,", round(total / 2), "road metres,", out.stat().st_size // 1024, "KB", flush=True)

    # rail lines: densify the same way so station distances (metres along the line) still hold
    tp = ROOT / "web" / "data" / "transit.json"
    tr = json.loads(tp.read_text())
    lines = []
    for l in tr["lines"]:
        dense = densify([tuple(p) for p in l["pts"]])
        lines.append((l, dense))
    rail = occlusion(np.vstack([d for _, d in lines]), sil, key)
    o = 0
    for l, d in lines:
        n = len(d)
        l["pts"] = [[round(float(x), 1), round(float(y), 1)] for x, y in d]
        l["occ"] = "".join("1" if f else "0" for f in rail[o:o + n])
        o += n
    tp.write_text(json.dumps(tr, separators=(",", ":")))
    print("rail samples", len(rail), "occluded", round(float(rail.mean()) * 100, 1), "%", flush=True)


if __name__ == "__main__":
    main()
