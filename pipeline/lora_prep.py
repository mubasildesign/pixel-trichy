"""Build a style-LoRA training set from approved repaint chunks, for mflux-train (FLUX.2 klein edit adapter).

mflux's trainer supports edit-style pairs only for FLUX.2-klein-base models (not Qwen-Image), so the style LoRA is trained on
klein: it learns "plain isometric render -> our painted look" from chunks you approved. Then repaint with
`mflux-generate-flux2-edit --model flux2-klein-9b|4b --lora ai/lora/<name>.safetensors`.

  .venv/bin/python pipeline/lora_prep.py [--min-score 0.6] [--size 768]
  .venv-ai/bin/mflux-train --config ai/lora_train.json
"""
import json, argparse
from pathlib import Path
from PIL import Image
from repaint import AI, QUEUE, SRC, OUT, PROMPT

ap = argparse.ArgumentParser()
ap.add_argument("--min-score", type=float, default=0.0)
ap.add_argument("--size", type=int, default=768)
ap.add_argument("--model", default="flux2-klein-base-4b")
a = ap.parse_args()

q = json.loads(QUEUE.read_text())
data = AI / "lora_data"
data.mkdir(exist_ok=True)
n = 0
STYLE = "Pixel Trichy isometric pixel-art city style: " + PROMPT.split(". ", 1)[1]
for c in q["chunks"]:
    if c["status"] != "done" or c["review"] != "approved" or (c["score"] or 0) < a.min_score:
        continue
    # four 768 crops per 1024 chunk would overlap; use the centre and the four quadrant-aligned crops
    s = c["size"]
    for k, (ox, oy) in enumerate([(0, 0), (s - a.size, 0), (0, s - a.size), (s - a.size, s - a.size), ((s - a.size) // 2, (s - a.size) // 2)]):
        base = f"{c['id']}_{k}"
        Image.open(SRC / f"{c['id']}.png").crop((ox, oy, ox + a.size, oy + a.size)).save(data / f"{base}_in.png")
        Image.open(OUT / f"{c['id']}.png").crop((ox, oy, ox + a.size, oy + a.size)).save(data / f"{base}_out.png")
        (data / f"{base}_in.txt").write_text(STYLE)
        n += 1
cfg = {
    "model": a.model, "data": str(data), "seed": 7, "steps": 4, "guidance": 1.0, "quantize": 8, "low_ram": True,
    "max_resolution": a.size,
    "training_loop": {"num_epochs": 40, "batch_size": 1, "timestep_low": 0, "timestep_high": 4},
    "optimizer": {"name": "AdamW", "learning_rate": 1e-4},
    "checkpoint": {"save_frequency": 10, "output_path": str(AI / "lora")},
    "monitoring": {"preview_width": 768, "preview_height": 768, "plot_frequency": 10, "generate_image_frequency": 10},
    "lora_layers": {"targets": []},
}
(AI / "lora_train.json").write_text(json.dumps(cfg, indent=1))
print(f"{n} pairs in {data}; wrote ai/lora_train.json (fill lora_layers.targets from mflux docs for {a.model} before training)")
