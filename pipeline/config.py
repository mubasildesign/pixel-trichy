"""Shared camera and area constants for Pixel Trichy.

Every stage (ingest, render, repaint, viewer, transit) must import projection from here.
Changing a constant here invalidates all tiles, so pick once.

Camera: 2:1 dimetric "game isometric", ground plane rotated 45 degrees.
  east  -> screen right and up
  north -> screen left and up
  So the north-east corner of the area is at the top of the image, south-west at the bottom.
Heights move a point straight up the screen.
"""
from __future__ import annotations
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TILES = ROOT / "tiles"

# Area of interest (WGS84). Covers Mukkombu to Kallanai, Samayapuram to the airport/NIT.
BBOX = dict(south=10.72, north=10.95, west=78.58, east=78.84)

# Local metre frame centred on the bbox centre (equirectangular, fine over 30 km).
LAT0 = (BBOX["south"] + BBOX["north"]) / 2
LON0 = (BBOX["west"] + BBOX["east"]) / 2
M_PER_DEG_LAT = 110_574.0
M_PER_DEG_LON = 111_320.0 * math.cos(math.radians(LAT0))

# Pixels per ground metre along each screen-diagonal axis at the deepest zoom level.
K = 2.0
# Vertical pixels per metre of building height.
VK = 2.0

TILE = 512


def to_metres(lon: float, lat: float) -> tuple[float, float]:
    return (lon - LON0) * M_PER_DEG_LON, (lat - LAT0) * M_PER_DEG_LAT


def from_metres(x: float, y: float) -> tuple[float, float]:
    return LON0 + x / M_PER_DEG_LON, LAT0 + y / M_PER_DEG_LAT


def iso_from_metres(x, y, h=0.0):
    """Metres east/north (+height) -> pixel at the deepest level, origin top-left of the image."""
    sx = (x - y) * K
    sy = -(x + y) * K / 2 - h * VK
    return sx - _X0, sy - _Y0


def iso(lon, lat, h=0.0):
    x, y = to_metres(lon, lat)
    return iso_from_metres(x, y, h)


def lonlat_from_iso(px, py):
    """Inverse for ground level (h=0)."""
    sx, sy = px + _X0, py + _Y0
    # sx = (x-y)K ; sy = -(x+y)K/2  ->  x-y = sx/K ; x+y = -2 sy/K
    d, s = sx / K, -2 * sy / K
    return from_metres((s + d) / 2, (s - d) / 2)


# --- image extent ------------------------------------------------------------------------
_corners = [to_metres(BBOX[ew], BBOX[ns]) for ew in ("west", "east") for ns in ("south", "north")]
_sx = [(x - y) * K for x, y in _corners]
_sy = [-(x + y) * K / 2 for x, y in _corners]
HEADROOM = 144  # px of room above the northern-most ground for tall buildings. Fixed (not VK-derived) so changing VK never shifts stored pixel coordinates
_X0 = min(_sx)
_Y0 = min(_sy) - HEADROOM
WIDTH = int(math.ceil(max(_sx) - _X0))
HEIGHT = int(math.ceil(max(_sy) - _Y0))
MAX_LEVEL = int(math.ceil(math.log2(max(WIDTH, HEIGHT))))


def geo_block() -> dict:
    """Everything the viewer needs to turn lat/lon into pixels (and back)."""
    return dict(lat0=LAT0, lon0=LON0, mLat=M_PER_DEG_LAT, mLon=M_PER_DEG_LON, k=K, vk=VK,
                x0=_X0, y0=_Y0, width=WIDTH, height=HEIGHT, bbox=BBOX)


if __name__ == "__main__":
    print("size", WIDTH, HEIGHT, "max level", MAX_LEVEL, "tiles", math.ceil(WIDTH / TILE), "x", math.ceil(HEIGHT / TILE))
    for name, (lat, lon) in dict(rockfort=(10.8284, 78.6963), junction=(10.8059, 78.6853), srirangam=(10.8625, 78.6893)).items():
        px, py = iso(lon, lat)
        print(name, round(px), round(py), [round(v, 5) for v in lonlat_from_iso(px, py)])
