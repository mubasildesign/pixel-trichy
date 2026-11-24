# Pixel Trichy

Tiruchirappalli as one explorable isometric map. Original code and art, inspired by the idea of Pixel Chennai; nothing is
copied from that site.

Live pieces: `web/` is a static site (OpenSeadragon + a custom tile source). `pipeline/` builds everything from open data.

## Layout

| Path | What |
| --- | --- |
| `pipeline/config.py` | Projection constants (2:1 dimetric, K=2, VK=2.0), bbox, tile size. Single source of truth; `web/data/places.json` carries a copy under `geo` |
| `pipeline/ingest.py` | Overture Maps (release pinned in file) to `data/raw/*.parquet` via duckdb |
| `pipeline/outline.py` | The real city shape: Overture "Trichy Corporation Limits" plus the outlying temples and Cauvery works, smoothed. Writes `data/outline.pkl` and `web/data/outline.json`. Tiles outside it are not rendered; the rest are RGBA, transparent outside the outline, with a drawn rim |
| `pipeline/landscape.py` | One blurred, darkened low-resolution image of the land beyond the border (fields, water, roads, settlements), `tiles/land.webp`. The viewer draws it under the city tiles so zooming out never shows a grey void |
| `pipeline/scene.py` | Geometry cleanup, building heights, road/rail centre lines. `scene.py clean` drops buildings standing in still water, on rail or on main roads and carves river channels; `scene.raw.pkl` is the uncleaned copy |
| `pipeline/render.py`, `sprites.py` | Painter's-algorithm renderer: cast shadows, asphalt roads with markings, framed windows, balconies and AC boxes, shopfronts with signboards and awnings, pitched tile roofs, rooftop tanks, washing lines and dishes, colonial clock towers on stations and colleges, agraharam houses on Srirangam island, street trees, pedestrians, stalls, scooters and cows. Moving vehicles are not baked in any more |
| `pipeline/art3d.py`, `temples.py`, `monuments.py` | Monument sprites drawn in code: gopurams, vimanams, prakara walls and halls (Srirangam's seven enclosures, Jambukeswarar, Samayapuram, Vayalur, Woraiyur), the lit terraced Rockfort height-field with its temples and cave shrines, Teppakulam with ghat steps and mandapam, Anna Stadium with crowded stands, the twin-spired Lourdes church, bridges generated from every mapped bridge that crosses water (white bowstring arches on the new Kollidam bridge, blue sluice gates on Kallanai and Mukkombu), elevated flyovers with piers, girders, parapets, ramps and lamp posts from every mapped land bridge, Amma Mandapam ghat. Courtyards, ghats and stands are filled with baked crowds, stalls and autos. Bakes `data/monuments.pkl` (parts, hide polygons, and flyover/bridge deck heights for traffic); each monument hides the generic buildings under it |
| `pipeline/civic.py` | Civic and industrial landmarks registered into `monuments.ALL`: bus stands with canopies and rows of buses, the Panjappur integrated bus terminus, Gandhi Market (arcade, tin-roof sheds, produce heaps, clock-tower gate), the Butterfly Park, the Anna Science Centre planetarium, rail-platform canopies, the Golden Rock workshop, BHEL, the airport (real runway, apron and terminal footprints) |
| `pipeline/vehicle_atlas.py`, `traffic_data.py` | Sprite atlases (`web/assets/vehicles.png`, `trains.png`, `atlas.json`) and the road chains for animated traffic (`web/data/traffic.json`). Chains are cut where they would pass through buildings, water or rail, and carry deck heights so vehicles ride up flyovers |
| `pipeline/build_base.py` | `render`, `pyramid`, `cover`: 512 px lossless WebP pyramid (levels 0-17, about 1.5 GB) and coverage mask. `render --region cx cy r` redoes part of the map |
| `pipeline/places.py` | Curated places, thumbnails, search index (streets, temples, areas and about 180 colleges from Overture places) |
| `pipeline/repaint.py` | AI repaint: plan, run, review, approve, build the sparse AI overlay pyramid |
| `pipeline/lora_prep.py` | Turns approved chunks into a training set for a FLUX.2-klein edit LoRA |
| `pipeline/qa.py`, `og.py`, `deploy.sh`, `serve.py` | Static checks, social image, `dist/` builder, local dev server (no-cache, port 8000) |

## Rebuild

```sh
python3 -m venv .venv && .venv/bin/pip install duckdb shapely scipy numpy pillow pyproj
cd pipeline
../.venv/bin/python ingest.py                 # also pulls the city boundary (divisions)
../.venv/bin/python scene.py && ../.venv/bin/python scene.py clean   # clean takes ~10 min
../.venv/bin/python outline.py && ../.venv/bin/python landscape.py
../.venv/bin/python monuments.py && ../.venv/bin/python vehicle_atlas.py && ../.venv/bin/python traffic_data.py
../.venv/bin/python build_base.py render pyramid cover
../.venv/bin/python places.py
cd ..
python3 pipeline/serve.py 8000                # serves web/ (tiles/ is symlinked in)
```

## AI layer

Needs Apple silicon and a second environment: `uv venv .venv-ai && uv pip install --python .venv-ai/bin/python mflux shapely scipy duckdb`.
The model is Qwen-Image-2.1-Turbo via mflux (8 steps, 8-bit, small text encoder). The weights are about 32 GB on disk.

```sh
.venv/bin/python pipeline/repaint.py plan --radius 900            # chunks near each place
.venv-ai/bin/python pipeline/repaint.py run --limit 3
.venv/bin/python pipeline/repaint.py review                         # open ai/review.html
.venv/bin/python pipeline/repaint.py approve-all-above 0.55         # or approve/reject by id
.venv/bin/python pipeline/repaint.py build                          # tiles/ai + tiles/ai_cover.json
```

Chunks are 1024 px with 128 px overlap. Seams are cross-faded with a cosine ramp, and the overlay fades to transparent at its
outer edge, so the plain render shows everywhere that has no approved chunk. The viewer's layer button switches between the two.
`score` is gradient correlation with the source; low scores mean the model moved things and the chunk should be rejected.

A style LoRA: mflux's trainer only supports edit pairs for FLUX.2-klein-base, not Qwen. `pipeline/lora_prep.py` builds the pairs
from approved chunks and writes `ai/lora_train.json`; train with `mflux-train`, then repaint with the klein edit command.

## Deploy

```sh
pipeline/deploy.sh --no-tiles          # dist/ with the app only
# tiles: ~1.5 GB, ~15k files. Upload to R2/S3 behind a CDN and set "base", "ai" in web/config.json
rclone sync tiles r2:pixel-trichy/tiles
npx wrangler pages deploy dist --project-name pixel-trichy
```

Cloudflare Pages allows 20k files, so bundling tiles (`pipeline/deploy.sh`) fits only until the AI layer grows. `web/_headers`
sets immutable caching on `/tiles/*`. The tile host needs `Access-Control-Allow-Origin: *` because tiles are fetched cross-origin.

## Live features (visitors, Memories, Reports)

The "here now / visitors" chip, the Memories pins and the Report tool need a small API under `/api`. The UI hides them when it is
unreachable, so a purely static deploy still works.

- **Local**: `python3 pipeline/serve.py 8000` serves the site and the API (SQLite in `data/live.db`).
  Set `PT_ADMIN=<secret>` to enable the admin endpoints.
- **Cloudflare Pages**: `functions/api/[[route]].js` is the same API on D1.
  ```sh
  npx wrangler d1 create pixel-trichy            # paste the id into wrangler.toml (REPLACE_WITH_D1_ID)
  npx wrangler d1 execute pixel-trichy --remote --file functions/schema.sql
  npx wrangler pages secret put ADMIN --project-name pixel-trichy
  ```
  Not yet run against a real Cloudflare account; test it on a preview deploy first.
- **Moderation**: memories go live at once. Hide one with `DELETE /api/admin/memories/<id>`; read reports with `GET /api/admin/reports`
  and set a status (`seen`, `fixed`, `wontfix`) with `PATCH /api/admin/reports/<id> {"status": "fixed"}`; all with header `x-admin: <secret>`.
  People see the status in Report → My reports.
- Visitors are counted once per browser (random id in localStorage); "here now" is anyone who pinged in the last 75 seconds.

## UI

The interface is styled after [shadcn/ui](https://ui.shadcn.com) (zinc dark tokens, buttons, badges, dialogs, tabs, tooltips, segmented
toggle, lucide icons, Geist font) written as plain CSS in `web/viewer.css`, because the site has no build step. The map's amber is the primary colour.

## Re-rendering and caching

Tiles are served immutable (`web/_headers`), so after any re-render bump `"ver"` in `web/config.json` (and the `?v=` on `viewer.js`,
`viewer.css` in `index.html`). The viewer appends `?v=<ver>` to every tile URL, so CDN and browser caches miss exactly once.
Every effect in the renderer is anchored to world coordinates and tiles are drawn on a padded canvas, so tiles join without seams.

## Data and credit

Map data © OpenStreetMap contributors (ODbL) and Overture Maps Foundation, which includes Microsoft and Google building
footprints. Keep the credit chip in the viewer. If you publish AI-painted tiles, say so on the About panel (it does).

## Known limits

- Building heights are estimated from footprint size; Overture has few real heights here.
- Place blurbs are drafted from public knowledge and flagged `checked: false`; verify each before launch (`qa.py` counts them).
- Overpass was unreachable during the build, so Overture is the only source. OSM-only details (some rail, minor water) may be thin.
