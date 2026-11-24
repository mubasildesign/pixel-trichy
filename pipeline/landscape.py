"""The countryside around the city outline, as one small blurred image under the tiles -> tiles/land.webp.

The tiles are transparent outside the city outline. The viewer lays this image underneath, stretched to the same extent,
so the map fades out into soft, darker fields, rivers and villages instead of a hard black edge.

  .venv/bin/python pipeline/landscape.py
"""
from __future__ import annotations
import json
import numpy as np
import shapely
from PIL import Image, ImageDraw, ImageFilter
from scipy import ndimage

from config import WIDTH, HEIGHT, TILES
from render_v1 import PAL, _rings
import outline

F = 16                                  # level-17 pixels per landscape pixel
OUT = TILES / "land.webp"
BG = np.array([32, 30, 28], np.float32)  # page background (viewer.css)
FIELD = (176, 186, 112)                  # beyond the mapped data


def main():
    import scene
    sc, _ = scene.load()
    w, h = int(round(WIDTH / F)), int(round(HEIGHT / F))
    im = Image.new("RGB", (w, h), FIELD)
    d = ImageDraw.Draw(im)

    def poly(g, col):
        g = shapely.transform(g, lambda c: c / F)
        for ext, holes in _rings(g):
            if len(ext) >= 3:
                d.polygon(ext, fill=col)
            for hh in holes:
                if len(hh) >= 3:
                    d.polygon(hh, fill=PAL["ground"])

    rng = np.random.default_rng(3)
    lg, lm = sc["land_cover"]
    for g, sub in sorted(zip(lg, lm), key=lambda t: {"barren": 0, "urban": 0, "grass": 1, "crop": 2, "shrub": 3, "wetland": 3, "forest": 4}.get(t[1], 0)):
        if sub != "urban":
            poly(g, PAL.get(sub, PAL["ground"]))
    ug, um = sc["land_use"]
    for g, (sub, cls) in zip(ug, um):
        if sub == "residential":
            poly(g, PAL["residential"])
        elif sub in ("park", "recreation") or cls in ("park", "garden"):
            poly(g, PAL["park"])
    dens, cell = sc["settled"]
    sm = Image.fromarray((np.clip(dens * 3.0, 0, 1) * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR)
    im.paste(Image.new("RGB", im.size, PAL["settled"]), (0, 0), sm)
    d = ImageDraw.Draw(im)
    wg, _ = sc["water"]
    for g in wg:
        poly(g, PAL["water"])
    sg, smeta = sc["segments"]
    for g, m in zip(sg, smeta):
        if m[0] == "road" and m[1] in ("motorway", "trunk", "primary", "secondary", "tertiary"):
            poly(g, (236, 222, 186))
        elif m[0] == "rail":
            poly(g, (130, 120, 112))
    bg, bm = sc["buildings"]
    roofs = [(214, 206, 196), (200, 120, 96), (226, 220, 208), (188, 178, 166)]
    for k, g in enumerate(bg):
        poly(g, roofs[k % 4])
    # scattered tree clumps in the fields so the countryside has texture after the blur
    a = np.asarray(im).copy()
    for _ in range(int(w * h / 90)):
        x, y = int(rng.integers(0, w)), int(rng.integers(0, h))
        if tuple(a[y, x]) in (FIELD, PAL["crop"], PAL["grass"], PAL["shrub"]):
            a[max(0, y - 1):y + 1, max(0, x - 1):x + 2] = (110, 150, 80)
    im = Image.fromarray(a)

    # blur, then darken and desaturate with distance from the outline; never fully black
    im = im.filter(ImageFilter.GaussianBlur(2.2))
    arr = np.asarray(im, np.float32)
    ol = outline.load()
    mk = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mk).polygon([(x / F, y / F) for x, y in ol.exterior.coords], fill=255)
    inside = np.asarray(mk) > 0
    dist = ndimage.distance_transform_edt(~inside)                     # landscape px from the outline
    t = np.clip(dist / 560.0, 0, 1) ** 0.9
    grey = arr.mean(axis=2, keepdims=True)
    arr = arr * 0.66 + grey * 0.34                                     # desaturate
    arr *= (0.72 - 0.26 * t)[..., None]                                # darker further out
    arr = arr * (1 - 0.4 * t[..., None]) + BG * (0.4 * t[..., None])
    # soft vignette towards the image border
    yy, xx = np.mgrid[0:h, 0:w]
    edge = np.minimum.reduce([xx, w - 1 - xx, yy * 2.0, (h - 1 - yy) * 2.0]) / (w * 0.08)
    e = np.clip(edge, 0, 1)[..., None]
    arr = arr * e + BG * 0.6 * (1 - e) + arr * 0.4 * (1 - e)
    # inside the outline the tiles cover it; keep it lightly blurred so it reads as a preview while tiles load
    base = np.asarray(im, np.float32)
    arr[inside] = base[inside] * 0.92
    Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(OUT, format="WEBP", quality=74, method=6)
    (TILES / "land.json").write_text(json.dumps(dict(w=w, h=h, f=F, width=WIDTH, height=HEIGHT)))
    print("landscape", w, h, OUT.stat().st_size // 1024, "KB")


if __name__ == "__main__":
    main()
