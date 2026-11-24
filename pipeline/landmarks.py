"""Hand-placed landmark sprites drawn in 3D over the open-data render: temple gopurams and rock hills.

Heights are stylised (rounded, compressed) so towers read well at the map's scale; they are not survey data.
Coordinates come from Overture place points checked against the render.
"""
GOPURAMS = [
    # name, lat, lon, base_w_m (E-W), base_d_m (N-S), height_m, tiers, wall colour
    ("Srirangam Raja Gopuram", 10.8575, 78.6897, 46, 30, 73, 13, (232, 190, 140)),
    ("Srirangam inner gopuram N", 10.8658, 78.6899, 34, 22, 36, 9, (226, 184, 150)),
    ("Srirangam inner gopuram E", 10.8624, 78.6935, 22, 34, 34, 9, (232, 196, 160)),
    ("Srirangam inner gopuram W", 10.8624, 78.6862, 22, 34, 34, 9, (226, 184, 150)),
    ("Srirangam inner gopuram S", 10.8594, 78.6899, 34, 22, 36, 9, (232, 190, 140)),
    ("Jambukeswarar gopuram", 10.8514, 78.7056, 39, 28, 42, 9, (236, 200, 160)),
    ("Samayapuram gopuram", 10.9184, 78.7391, 31, 22, 32, 8, (236, 190, 150)),
    ("Woraiyur Vekkaliamman gopuram", 10.8299, 78.6705, 20, 14, 20, 6, (232, 200, 160)),
    ("Erumbeeswarar gopuram", 10.7922, 78.7677, 20, 14, 20, 6, (232, 196, 150)),
    ("Rockfort temple gopuram", 10.8268, 78.6934, 17, 13, 18, 5, (232, 200, 160)),
]
# name, lat, lon, radius_m, height_m, temple on top
ROCKS = [
    ("Rockfort", 10.8283, 78.6972, 95, 83, True),
    ("Golden Rock", 10.7856, 78.7233, 80, 40, False),
    ("Thiruverumbur hill", 10.7927, 78.7674, 70, 36, True),
]
