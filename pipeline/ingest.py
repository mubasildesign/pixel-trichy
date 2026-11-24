"""Download the Trichy bbox from Overture Maps (public S3, no key) into data/raw/*.parquet.

Overture bundles OSM-derived roads/water/land plus Microsoft/Google/OSM building footprints.
Run:  .venv/bin/python pipeline/ingest.py [theme ...]
"""
import sys, time
import duckdb
from config import BBOX, DATA

RELEASE = "2026-11-18.0"
BASE = f"s3://overturemaps-us-west-2/release/{RELEASE}"
PAD = 0.01  # degrees, so features crossing the edge are kept

JOBS = {
    "buildings": ("buildings", "building"),
    "segments": ("transportation", "segment"),
    "water": ("base", "water"),
    "land": ("base", "land"),
    "land_use": ("base", "land_use"),
    "land_cover": ("base", "land_cover"),
    "infrastructure": ("base", "infrastructure"),
    "places": ("places", "place"),
}


def main(names):
    raw = DATA / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; INSTALL spatial; LOAD spatial; SET s3_region='us-west-2'; SET threads=8;")
    b = BBOX
    where = (f"bbox.xmin <= {b['east']+PAD} AND bbox.xmax >= {b['west']-PAD} "
             f"AND bbox.ymin <= {b['north']+PAD} AND bbox.ymax >= {b['south']-PAD}")
    for name in names or JOBS:
        theme, typ = JOBS[name]
        out = raw / f"{name}.parquet"
        t = time.time()
        con.execute(f"""COPY (SELECT * FROM read_parquet('{BASE}/theme={theme}/type={typ}/*', hive_partitioning=1)
                         WHERE {where}) TO '{out}' (FORMAT parquet)""")
        n = con.execute(f"SELECT count(*) FROM '{out}'").fetchone()[0]
        print(f"{name}: {n} rows in {time.time()-t:.0f}s -> {out}", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
