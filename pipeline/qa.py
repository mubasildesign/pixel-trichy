"""Static QA: projection roundtrip, landmark positions vs known coordinates, places inside coverage, asset sizes."""
import sys, json, math; sys.path.insert(0, __file__.rsplit("/", 1)[0])
from pathlib import Path
import config

ok = True
def check(name, cond, info=""):
    global ok; ok &= bool(cond); print(("PASS " if cond else "FAIL ") + name, info)

# 1. projection roundtrip < 0.5 m
worst = 0
for lon, lat in [(78.62, 10.75), (78.69, 10.83), (78.75, 10.9), (78.5, 10.7)]:
    x, y = config.iso(lon, lat); lo, la = config.lonlat_from_iso(x, y)
    worst = max(worst, math.hypot((lo - lon) * 109500, (la - lat) * 110700))
check("projection roundtrip", worst < 0.5, f"worst {worst:.3f} m")

# 2. places in bbox + have thumbnails
places = json.loads(Path("web/data/places.json").read_text())
items = places["places"] if isinstance(places, dict) else places
B = config.BBOX; w, s, e, n = B["west"], B["south"], B["east"], B["north"]
bad = [p["slug"] for p in items if not (w <= p["lon"] <= e and s <= p["lat"] <= n)]
check("places inside bbox", not bad, str(bad))
miss = [p["slug"] for p in items if not (Path("web") / p["img"]).exists()]
check("place thumbnails", not miss, str(miss))

# 3. places on covered tiles
cov = json.loads(Path("tiles/cover.json").read_text())
def covered(x, y):
    r = int(y) // cov["px"]; c = int(x) // cov["px"]
    row = cov["rows"][r] if 0 <= r < len(cov["rows"]) else []
    return any(row[i] <= c <= row[i + 1] for i in range(0, len(row), 2))
nc = [p["slug"] for p in items if not covered(p["x"], p["y"])]
check("places on rendered tiles", not nc, str(nc))
# places x,y agree with projection
off = [p["slug"] for p in items if math.hypot(*[a - b for a, b in zip(config.iso(p["lon"], p["lat"]), (p["x"], p["y"]))]) > 2]
check("place pixel coords match lat/lon", not off, str(off))
unchecked = [p["slug"] for p in items if not p.get("checked")]
print("NOTE blurbs not yet fact-checked by a human:", len(unchecked))

# 4. external libs / sizes
check("openseadragon vendored", Path("web/vendor/openseadragon.min.js").stat().st_size > 1e5)
check("og image", Path("web/assets/og.jpg").exists())
sz = sum(f.stat().st_size for f in Path("web").glob("*.*")) + sum(f.stat().st_size for f in Path("web/data").glob("*.json"))
check("app payload < 3 MB (excl. tiles/thumbs)", sz < 3e6, f"{sz/1e6:.2f} MB")
sys.exit(0 if ok else 1)
