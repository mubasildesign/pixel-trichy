"""Render the base tile pyramid (DZI layout, WebP) from data/scene.pkl.

  .venv/bin/python pipeline/build_base.py render [--limit N] [--region cx cy r]   # deepest level
  .venv/bin/python pipeline/build_base.py pyramid                                 # all lower levels
  .venv/bin/python pipeline/build_base.py cover                                   # coverage json for the viewer
Resumable: existing tiles are skipped.
"""
from __future__ import annotations
import sys, json, math, time, os
from multiprocessing import Pool
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
from shapely.geometry import Polygon, box

import config as C
from config import TILE, WIDTH, HEIGHT, MAX_LEVEL, TILES, BBOX, iso_from_metres, to_metres

OUT = TILES / "base"
BG = (32, 30, 28)
import outline
QUADP = outline.load()                       # the real city outline (see outline.py)
QUAD = list(QUADP.exterior.coords)
RIM = (150, 112, 70)
NCOLS, NROWS = math.ceil(WIDTH / TILE), math.ceil(HEIGHT / TILE)
QUAD_WEBP = dict(format="WEBP", lossless=True, method=4)   # lossless keeps pixel edges crisp (lossy 4:2:0 smears colour)

_R = None


def _init():
    global _R
    import scene, render
    sc, trees = scene.load()
    _R = render.Renderer(sc, trees)


def tile_wanted(c, r):
    return QUADP.intersects(box(c * TILE, r * TILE, (c + 1) * TILE, (r + 1) * TILE))


def mask_outside(im, x0, y0):
    """Make everything outside the city outline transparent (the viewer shows the blurred countryside, landscape.py,
    underneath), with a thin warm rim along the edge."""
    pts = [(x - x0, y - y0) for x, y in QUAD]
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    im = im.convert("RGBA")
    ImageDraw.Draw(im).line(pts + pts[:1], fill=RIM, width=3, joint="curve")
    im.putalpha(m.filter(ImageFilter.MaxFilter(3)))
    return im


def level_dims(level):
    s = 2 ** (MAX_LEVEL - level)
    return math.ceil(WIDTH / s), math.ceil(HEIGHT / s)


def _render_one(args):
    c, r = args
    out = OUT / str(MAX_LEVEL) / f"{c}_{r}.webp"
    if out.exists():
        return 0
    im = _R.render_tile(c, r)
    im = mask_outside(im, c * TILE, r * TILE)
    w = min(TILE, WIDTH - c * TILE); h = min(TILE, HEIGHT - r * TILE)
    if (w, h) != (TILE, TILE):
        im = im.crop((0, 0, w, h))
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out, **QUAD_WEBP)
    return 1


def cmd_render(argv):
    jobs = [(c, r) for r in range(NROWS) for c in range(NCOLS) if tile_wanted(c, r)]
    if "--region" in argv:
        i = argv.index("--region"); cx, cy, rad = (int(v) for v in argv[i + 1:i + 4])
        jobs = [(c, r) for c, r in jobs if abs(c * TILE + 256 - cx) <= rad and abs(r * TILE + 256 - cy) <= rad]
    if "--limit" in argv:
        jobs = jobs[: int(argv[argv.index("--limit") + 1])]
    print(f"{len(jobs)} tiles at level {MAX_LEVEL}", flush=True)
    t = time.time(); done = 0
    with Pool(max(1, os.cpu_count() - 1), initializer=_init) as p:
        for n in p.imap_unordered(_render_one, jobs, chunksize=4):
            done += 1
            if done % 200 == 0:
                rate = done / (time.time() - t)
                print(f"{done}/{len(jobs)}  {rate:.1f} tiles/s  eta {(len(jobs)-done)/rate/60:.1f} min", flush=True)
    print("render done", time.time() - t)


def cmd_pyramid(argv):
    for level in range(MAX_LEVEL - 1, -1, -1):
        w, h = level_dims(level)
        cols, rows = math.ceil(w / TILE), math.ceil(h / TILE)
        cw, ch = level_dims(level + 1)
        n = 0
        for r in range(rows):
            for c in range(cols):
                out = OUT / str(level) / f"{c}_{r}.webp"
                if out.exists():
                    continue
                kids = {}
                for dy in (0, 1):
                    for dx in (0, 1):
                        p = OUT / str(level + 1) / f"{2*c+dx}_{2*r+dy}.webp"
                        if p.exists():
                            kids[(dx, dy)] = Image.open(p).convert("RGBA")
                if not kids:
                    continue
                canvas = Image.new("RGBA", (2 * TILE, 2 * TILE), (0, 0, 0, 0))
                for (dx, dy), im in kids.items():
                    canvas.paste(im, (dx * TILE, dy * TILE))
                tw, th = min(TILE, w - c * TILE), min(TILE, h - r * TILE)
                canvas = canvas.crop((0, 0, min(2 * TILE, 2 * tw), min(2 * TILE, 2 * th)))
                im = canvas.resize((tw, th), Image.BOX)
                out.parent.mkdir(parents=True, exist_ok=True)
                im.save(out, **QUAD_WEBP)
                n += 1
        print(f"level {level}: {n} tiles ({w}x{h})", flush=True)


def cmd_cover(argv):
    rows = []
    for r in range(NROWS):
        cs = [c for c in range(NCOLS) if (OUT / str(MAX_LEVEL) / f"{c}_{r}.webp").exists()]
        runs = []
        for c in cs:
            if runs and c == runs[-1] + 1:
                runs[-1] = c
            else:
                runs += [c, c]
        rows.append(runs)
    (TILES / "cover.json").write_text(json.dumps(dict(px=TILE, w=NCOLS, h=NROWS, rows=rows, level=MAX_LEVEL, width=WIDTH, height=HEIGHT)))
    (TILES / "base.dzi").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?>\n<Image xmlns="http://schemas.microsoft.com/deepzoom/2008" Format="webp" Overlap="0" TileSize="{TILE}"><Size Width="{WIDTH}" Height="{HEIGHT}"/></Image>')
    print("wrote cover.json and base.dzi")


if __name__ == "__main__":
    CMDS = {"render": cmd_render, "pyramid": cmd_pyramid, "cover": cmd_cover}
    names = [a for a in sys.argv[1:] if a in CMDS]
    flags = [a for a in sys.argv[1:] if a not in CMDS]
    for n in names:
        CMDS[n](flags)
