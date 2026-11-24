"""AI repaint pipeline: plan chunks, repaint them with a local image-edit model, review, and build the AI tile pyramid.

The AI layer is a sparse overlay: only approved chunks become tiles, and their edges fade to transparent so the plain
render shows through everywhere else. Run with the AI environment for `run` (needs mflux), the main one for the rest:

  .venv/bin/python pipeline/repaint.py plan [--radius 900] [--places slug,slug] [--chunk 1024 --overlap 128]
  .venv-ai/bin/python pipeline/repaint.py run [--limit N] [--model qwen-image-2.1-turbo] [--lora path scale] [--quantize 8]
  .venv/bin/python pipeline/repaint.py review            # writes ai/review.html, prints a status table
  .venv/bin/python pipeline/repaint.py approve ID [ID ...]   |   reject ID [ID ...]   |   approve-all-above 0.55
  .venv/bin/python pipeline/repaint.py build             # AI pyramid + ai_cover.json

Every chunk keeps: id, pixel box, status (planned/done/failed), review (pending/approved/rejected), score (edge agreement
with the source render; low means the model moved things), seed, model, seconds.
"""
from __future__ import annotations
import sys, json, time, math, argparse
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
from config import ROOT, TILES, TILE, WIDTH, HEIGHT, MAX_LEVEL, BBOX, iso_from_metres, to_metres  # noqa: E402

AI = ROOT / "ai"
QUEUE = AI / "queue.json"
SRC, OUT = AI / "src", AI / "out"
OUT_TILES = TILES / "ai"
WEBP = dict(format="WEBP", quality=92, method=4)

PROMPT = ("Redraw this isometric city map as detailed pixel art in the style of a classic isometric city-builder game. "
          "Keep every building, road, pond, rock and tree in exactly the same position, size and shape; do not add or remove "
          "buildings. Add small details: clay-tile and concrete roofs, rooftop water tanks, small shop signboards, coconut "
          "palms and neem trees, people, scooters and autorickshaws on the roads. Warm sunlit palette, crisp 1-pixel outlines, no blur.")


def load_queue():
    return json.loads(QUEUE.read_text()) if QUEUE.exists() else dict(prompt=PROMPT, chunks=[])


def save_queue(q):
    AI.mkdir(exist_ok=True)
    QUEUE.write_text(json.dumps(q, indent=1))


# --------------------------------------------------------------------------------------------- plan
def cmd_plan(a):
    places = json.loads((ROOT / "web/data/places.json").read_text())["places"]
    if a.places:
        keep = set(a.places.split(","))
        places = [p for p in places if p["slug"] in keep]
    stride = a.chunk - a.overlap
    q = load_queue()
    have = {c["id"] for c in q["chunks"]}
    new = 0
    cols, rows = math.ceil(WIDTH / stride), math.ceil(HEIGHT / stride)
    for p in places:
        for r in range(rows):
            for c in range(cols):
                x0, y0 = c * stride, r * stride
                cx, cy = x0 + a.chunk / 2, y0 + a.chunk / 2
                if abs(cx - p["x"]) > a.radius or abs(cy - p["y"]) > a.radius:
                    continue
                cid = f"c{c}_{r}"
                if cid in have:
                    continue
                have.add(cid)
                q["chunks"].append(dict(id=cid, x=x0, y=y0, size=a.chunk, overlap=a.overlap, near=p["slug"], status="planned",
                                        review="pending", score=None, seed=1000 + c * 131 + r, model=None, seconds=None))
                new += 1
    save_queue(q)
    print(f"{new} new chunks, {len(q['chunks'])} total")


# --------------------------------------------------------------------------------------------- run
def edge_score(src: Image.Image, out: Image.Image) -> float:
    """Correlation of gradient magnitude after blurring both to ~8 px: high means the layout survived."""
    def g(im):
        a = np.asarray(im.convert("L").resize((128, 128), Image.BOX), dtype=np.float32)
        gy, gx = np.gradient(a)
        return np.hypot(gx, gy).ravel()
    s, o = g(src), g(out)
    s, o = s - s.mean(), o - o.mean()
    d = math.sqrt((s * s).sum() * (o * o).sum()) or 1.0
    return float((s * o).sum() / d)


def cmd_run(a):
    import render, scene
    from mflux.models.common.compute_precision import ComputePrecision  # noqa: F401
    from mflux.models.common.config.model_config import ModelConfig
    from mflux.models.qwen21.variants.edit.qwen_image_21_edit import QwenImage21Edit
    from mflux.models.common.resolution.config_resolution import ConfigResolution

    q = load_queue()
    todo = [c for c in q["chunks"] if c["status"] in ("planned", "failed") or (a.redo and c["id"] in a.redo)]
    if a.ids:
        todo = [c for c in q["chunks"] if c["id"] in a.ids]
    todo = todo[: a.limit] if a.limit else todo
    if not todo:
        print("nothing to do"); return
    SRC.mkdir(parents=True, exist_ok=True); OUT.mkdir(parents=True, exist_ok=True)
    sc, trees = scene.load()
    R = render.Renderer(sc, trees)
    cfg = ConfigResolution.resolve_restricted(a.model, "qwen-image-2.1", model_path=None,
                                              extra_keys=("qwen-image-2.1-turbo",), base_model=None)
    kw = {}
    if a.lora:
        kw = dict(lora_paths=[a.lora[0]], lora_scales=[float(a.lora[1]) if len(a.lora) > 1 else 1.0], bake_lora=True)
    model = QwenImage21Edit(quantize=a.quantize, model_path=None, model_config=cfg, small_text_encoder=a.small_text_encoder, **kw)
    for c in todo:
        t = time.time()
        src_path, out_path = SRC / f"{c['id']}.png", OUT / f"{c['id']}.png"
        R.render_tile(0, 0, size=c["size"], ox=c["x"], oy=c["y"]).save(src_path)
        try:
            img = model.generate_image(seed=c["seed"], prompt=q["prompt"], num_inference_steps=a.steps, guidance=1.0,
                                       image_paths=[str(src_path)], output_resolution=c["size"],
                                       width=c["size"], height=c["size"])
            out = img.image if hasattr(img, "image") else img
            out = out.convert("RGB")
            if out.size != (c["size"], c["size"]):
                out = out.resize((c["size"], c["size"]), Image.LANCZOS)
            out.save(out_path)
            c.update(status="done", score=round(edge_score(Image.open(src_path), out), 3), model=a.model, seconds=round(time.time() - t, 1))
        except Exception as e:  # keep going; the chunk is retried on the next run
            c.update(status="failed", error=str(e)[:200])
        save_queue(q)
        print(c["id"], c["status"], c.get("score"), c.get("seconds"), flush=True)


# --------------------------------------------------------------------------------------------- review
def cmd_review(a):
    q = load_queue()
    rows = []
    for c in q["chunks"]:
        if c["status"] != "done":
            continue
        rows.append(f'<tr><td>{c["id"]}<br>{c["near"]}<br>score {c["score"]}<br><b>{c["review"]}</b></td>'
                    f'<td><img src="src/{c["id"]}.png" width="480"></td><td><img src="out/{c["id"]}.png" width="480"></td></tr>')
    (AI / "review.html").write_text('<meta charset="utf-8"><body style="background:#222;color:#eee;font:14px sans-serif"><table>' + "".join(rows) + "</table>")
    by = {}
    for c in q["chunks"]:
        by[(c["status"], c["review"])] = by.get((c["status"], c["review"]), 0) + 1
    print(by, "\nopen ai/review.html, then approve/reject by id")


def _set(ids, val):
    q = load_queue()
    for c in q["chunks"]:
        if c["id"] in ids:
            c["review"] = val
    save_queue(q)


def cmd_approve_above(a):
    q = load_queue()
    for c in q["chunks"]:
        if c["status"] == "done" and c["score"] is not None and c["score"] >= a.threshold and c["review"] == "pending":
            c["review"] = "approved"
    save_queue(q)


# --------------------------------------------------------------------------------------------- build
def feather(size, overlap, edge):
    """Weight 1 inside, ramping to ~0 over `overlap` px at every side (so neighbouring chunks cross-fade)."""
    r = np.minimum(np.arange(size), np.arange(size)[::-1]).astype(np.float32)
    ramp = np.clip((r + 1) / max(1, overlap), 0, 1)
    ramp = 0.5 - 0.5 * np.cos(np.pi * ramp)
    return np.outer(ramp, ramp)


def cmd_build(a):
    q = load_queue()
    ok = [c for c in q["chunks"] if c["status"] == "done" and c["review"] == "approved"]
    if not ok:
        print("no approved chunks"); return
    # accumulate premultiplied colour + weight on the deepest-level tile grid
    acc = {}
    for c in ok:
        img = np.asarray(Image.open(OUT / f"{c['id']}.png").convert("RGB"), dtype=np.float32)
        w = feather(c["size"], c["overlap"], True)
        x0, y0, s = c["x"], c["y"], c["size"]
        for ty in range(max(0, y0 // TILE), min(math.ceil(HEIGHT / TILE), (y0 + s - 1) // TILE + 1)):
            for tx in range(max(0, x0 // TILE), min(math.ceil(WIDTH / TILE), (x0 + s - 1) // TILE + 1)):
                tx0, ty0 = tx * TILE, ty * TILE
                ix0, iy0 = max(x0, tx0), max(y0, ty0)
                ix1, iy1 = min(x0 + s, tx0 + TILE), min(y0 + s, ty0 + TILE)
                if ix1 <= ix0 or iy1 <= iy0:
                    continue
                t = acc.setdefault((tx, ty), [np.zeros((TILE, TILE, 3), np.float32), np.zeros((TILE, TILE), np.float32)])
                sub = img[iy0 - y0:iy1 - y0, ix0 - x0:ix1 - x0]
                sw = w[iy0 - y0:iy1 - y0, ix0 - x0:ix1 - x0]
                t[0][iy0 - ty0:iy1 - ty0, ix0 - tx0:ix1 - tx0] += sub * sw[..., None]
                t[1][iy0 - ty0:iy1 - ty0, ix0 - tx0:ix1 - tx0] += sw
    import shutil
    shutil.rmtree(OUT_TILES, ignore_errors=True)  # only approved chunks may remain
    d17 = OUT_TILES / str(MAX_LEVEL)
    d17.mkdir(parents=True, exist_ok=True)
    rgba = {}
    for (tx, ty), (col, wt) in acc.items():
        alpha = np.clip(wt, 0, 1)
        rgb = col / np.maximum(wt, 1e-6)[..., None]
        arr = np.dstack([np.clip(rgb, 0, 255), alpha * 255]).astype(np.uint8)
        w_ = min(TILE, WIDTH - tx * TILE); h_ = min(TILE, HEIGHT - ty * TILE)
        im = Image.fromarray(arr, "RGBA").crop((0, 0, w_, h_))
        im.save(d17 / f"{tx}_{ty}.webp", **WEBP)
        rgba[(tx, ty)] = im
    # lower levels: average premultiplied RGBA of the 2x2 children
    level_tiles = rgba
    for level in range(MAX_LEVEL - 1, -1, -1):
        s = 2 ** (MAX_LEVEL - level)
        lw, lh = math.ceil(WIDTH / s), math.ceil(HEIGHT / s)
        parents = {}
        for (cx, cy), im in level_tiles.items():
            parents.setdefault((cx // 2, cy // 2), []).append(((cx % 2, cy % 2), im))
        nxt = {}
        d = OUT_TILES / str(level)
        d.mkdir(parents=True, exist_ok=True)
        for (px, py), kids in parents.items():
            canvas = np.zeros((2 * TILE, 2 * TILE, 4), np.float32)
            for (dx, dy), im in kids:
                arr = np.asarray(im, dtype=np.float32)
                arr[..., :3] *= arr[..., 3:4] / 255.0
                canvas[dy * TILE:dy * TILE + arr.shape[0], dx * TILE:dx * TILE + arr.shape[1]] = arr
            small = canvas.reshape(TILE, 2, TILE, 2, 4).mean(axis=(1, 3))
            al = small[..., 3:4]
            rgb = np.where(al > 0.5, small[..., :3] / np.maximum(al / 255.0, 1e-6), 0)
            out = np.dstack([np.clip(rgb, 0, 255), al]).astype(np.uint8)
            tw, th = min(TILE, lw - px * TILE), min(TILE, lh - py * TILE)
            im = Image.fromarray(out, "RGBA").crop((0, 0, tw, th))
            im.save(d / f"{px}_{py}.webp", **WEBP)
            nxt[(px, py)] = im
        level_tiles = nxt
    rows = [[] for _ in range(math.ceil(HEIGHT / TILE))]
    for (tx, ty) in rgba:
        r = rows[ty]
        rows[ty] = [min(r[0], tx), max(r[1], tx)] if r else [tx, tx]
    tiles = {str(l): sorted(p.stem for p in (OUT_TILES / str(l)).glob("*.webp")) for l in range(MAX_LEVEL + 1) if (OUT_TILES / str(l)).exists()}
    (TILES / "ai_cover.json").write_text(json.dumps(dict(px=TILE, w=math.ceil(WIDTH / TILE), h=len(rows), rows=rows, tiles=tiles, level=MAX_LEVEL, width=WIDTH, height=HEIGHT)))
    print(f"built AI pyramid from {len(ok)} approved chunks, {len(rgba)} tiles at level {MAX_LEVEL}")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("plan"); p.add_argument("--radius", type=int, default=900); p.add_argument("--places"); p.add_argument("--chunk", type=int, default=1024); p.add_argument("--overlap", type=int, default=128); p.set_defaults(f=cmd_plan)
    p = sp.add_parser("run"); p.add_argument("--limit", type=int); p.add_argument("--ids", nargs="*"); p.add_argument("--redo", nargs="*"); p.add_argument("--model", default="qwen-image-2.1-turbo"); p.add_argument("--steps", type=int, default=8)
    p.add_argument("--quantize", type=int, default=8); p.add_argument("--small-text-encoder", action="store_true", default=True); p.add_argument("--lora", nargs="+"); p.set_defaults(f=cmd_run)
    p = sp.add_parser("review"); p.set_defaults(f=cmd_review)
    p = sp.add_parser("approve"); p.add_argument("ids", nargs="+"); p.set_defaults(f=lambda a: _set(a.ids, "approved"))
    p = sp.add_parser("reject"); p.add_argument("ids", nargs="+"); p.set_defaults(f=lambda a: _set(a.ids, "rejected"))
    p = sp.add_parser("approve-all-above"); p.add_argument("threshold", type=float); p.set_defaults(f=cmd_approve_above)
    p = sp.add_parser("build"); p.set_defaults(f=cmd_build)
    a = ap.parse_args()
    a.f(a)


if __name__ == "__main__":
    main()
