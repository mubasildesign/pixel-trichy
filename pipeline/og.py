"""Social preview image: a crop of the base render around Rockfort, upscaled nearest-neighbour."""
import sys; sys.path.insert(0, __file__.rsplit("/", 1)[0])
import config, render, scene

lat, lon = 10.8283, 78.6972
x, y = config.iso(lon, lat)
sc, trees = scene.load()
R = render.Renderer(sc, trees)
W, H = 600, 315
img = R.render_tile(0, 0, size=W, ox=int(x - W / 2), oy=int(y - H / 2 - 60)).crop((0, 0, W, H))
img.resize((W * 2, H * 2), 0).convert("RGB").save("web/assets/og.jpg", quality=88)
print("web/assets/og.jpg")
