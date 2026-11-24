"""Rail lines and stations for the ride layer -> web/data/transit.json (iso pixel coordinates, deepest level).

Trichy has no metro, so the ride runs on the real Southern Railway lines through the junction. Train positions on the map
are decorative: trains shuttle along each line; they are not live timetable data.
"""
import json, math
import numpy as np
import shapely
from shapely.geometry import Polygon, Point
from shapely.ops import linemerge, unary_union
import duckdb

from config import ROOT, BBOX, iso_from_metres, to_metres, K, LON0, LAT0, M_PER_DEG_LON, M_PER_DEG_LAT
import scene as S

STATIONS = {  # raw Overture name -> (clean name, Tamil)
    "Tiruchchirappalli Junction": ("Tiruchirappalli Junction", "திருச்சி சந்திப்பு"),
    "Tiruchirappalli Palakkarai railway station": ("Palakkarai", "பாலக்கரை"),
    "Tiruchirappalli Town railway station": ("Trichy Fort", "திருச்சி கோட்டை"),
    "Trichy Town Station": ("Trichy Town", "திருச்சி டவுன்"),
    "Srirangam Railway Station": ("Srirangam", "ஸ்ரீரங்கம்"),
    "Ponmalai Golden Rock": ("Golden Rock", "பொன்மலை"),
    "Thiruverumbur Railway Station": ("Thiruverumbur", "திருவெறும்பூர்"),
    "Lalgudi railway station": ("Lalgudi", "லால்குடி"),
    "Pichchanclarkovil Railway Station": ("Pichandarkoil", "பிச்சாண்டார்கோவில்"),
    "Jeeyapuram Railway Station": ("Jeeyapuram", "ஜீயபுரம்"),
    "Thondamanpatti Railway Station": ("Thondamanpatti", "தொண்டமான்பட்டி"),
}


def main():
    con = duckdb.connect(); con.execute("INSTALL spatial; LOAD spatial")
    rows = con.execute("select ST_AsWKB(geometry) from '../data/raw/segments.parquet' where subtype='rail'").fetchall()
    geoms = shapely.from_wkb([bytes(r[0]) for r in rows])
    g = S._project(geoms)
    b = BBOX
    quad = Polygon([iso_from_metres(*to_metres(b[e], b[n])) for e, n in (("west", "south"), ("east", "south"), ("east", "north"), ("west", "north"))])
    g = shapely.intersection(g, quad)
    # graph over all rail vertices (snapped to a 3 px grid) so routes follow the real track between stations
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra
    idx, pts, ei, ej, ew = {}, [], [], [], []
    def node(x, y):
        k = (round(x / 3), round(y / 3))
        if k not in idx:
            idx[k] = len(pts); pts.append((x, y))
        return idx[k]
    for geom in g:
        if geom.is_empty:
            continue
        for part in (geom.geoms if hasattr(geom, "geoms") else [geom]):
            c = list(part.coords)
            for (x0, y0), (x1, y1) in zip(c, c[1:]):
                a_, b_ = node(x0, y0), node(x1, y1)
                if a_ != b_:
                    w = math.hypot(x1 - x0, y1 - y0)
                    ei += [a_, b_]; ej += [b_, a_]; ew += [w, w]
    n = len(pts)
    A = coo_matrix((ew, (ei, ej)), shape=(n, n)).tocsr()
    P = np.array(pts)
    st_rows = con.execute("select names.primary, ST_Y(geometry), ST_X(geometry) from '../data/raw/places.parquet' "
                          "where taxonomy.primary='train_station'").fetchall()
    stations = {}
    for name, lat, lon in st_rows:
        if name in STATIONS:
            x, y = iso_from_metres((lon - LON0) * M_PER_DEG_LON, (lat - LAT0) * M_PER_DEG_LAT)
            d = np.hypot(P[:, 0] - x, P[:, 1] - y)
            j = int(d.argmin())
            stations[STATIONS[name][0]] = (STATIONS[name][1], j, float(d[j]))
    print({k: round(v[2]) for k, v in stations.items()})
    hub = stations["Tiruchirappalli Junction"][1]
    dist, pred = dijkstra(A, indices=hub, return_predecessors=True)
    print({k: (round(dist[v[1]]) if np.isfinite(dist[v[1]]) else None) for k, v in stations.items()})
    ROUTES = [  # terminal stations; every other station within 250 px of the path is added as a stop
        ("Tiruchirappalli Junction", "Lalgudi"),
        ("Tiruchirappalli Junction", "Thondamanpatti"),
        ("Tiruchirappalli Junction", "Jeeyapuram"),
    ]
    lines = []
    for a_name, b_name in ROUTES:
        if b_name not in stations or not np.isfinite(dist[stations[b_name][1]]):
            continue
        path, cur = [], stations[b_name][1]
        while cur != hub and cur >= 0:
            path.append(cur); cur = pred[cur]
        path.append(hub); path.reverse()
        coords = [tuple(P[i]) for i in path]
        line = shapely.LineString(coords)
        sts = []
        for nm, (ta, j, off) in stations.items():
            q = shapely.Point(P[j])
            if line.distance(q) < 250:
                at = line.project(q); pt = line.interpolate(at)
                sts.append(dict(name=nm, ta=ta, at=round(at), x=round(pt.x), y=round(pt.y)))
        sts.sort(key=lambda s: s["at"])
        simp = line.simplify(1.5)
        lines.append(dict(id=f"line{len(lines) + 1}", name=f"{sts[0]['name']} to {sts[-1]['name']}", length=round(line.length),
                          pts=[[round(x, 1), round(y, 1)] for x, y in simp.coords], stations=sts,
                          trains=max(1, min(3, round(line.length / 25000)))))
    out = ROOT / "web" / "data" / "transit.json"
    out.write_text(json.dumps(dict(lines=lines), ensure_ascii=False, separators=(",", ":")))
    for l in lines:
        print(l["id"], l["name"], l["length"], len(l["pts"]), [s["name"] for s in l["stations"]], l["trains"])


if __name__ == "__main__":
    main()
