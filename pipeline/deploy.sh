#!/usr/bin/env bash
# Build a deployable dist/. Tiles are ~15k files (~1.5 GB); Cloudflare Pages allows 20k files (25 MB each, but a site limit applies) per deploy, so with the AI layer
# serve tiles from R2/S3 + CDN instead and set "base"/"ai" in web/config.json to that origin.
#   pipeline/deploy.sh              -> dist/ with tiles bundled
#   pipeline/deploy.sh --no-tiles   -> dist/ without tiles (upload tiles/ separately, e.g. `rclone sync tiles r2:pixel-trichy/tiles`)
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf dist && mkdir dist
rsync -a --exclude tiles web/ dist/
if [[ "${1:-}" != "--no-tiles" ]]; then
  mkdir dist/tiles && rsync -a tiles/ dist/tiles/
fi
echo "dist: $(find dist -type f | wc -l) files, $(du -sh dist | cut -f1)"
echo "next: npx wrangler pages deploy dist --project-name pixel-trichy   (or: npx netlify deploy --dir dist --prod)"
