"""Curated places -> web/data/places.json (+ thumbnails) and the lazy search index web/data/search.json.

Coordinates were checked against Overture place points. Blurbs are short, written for this project, and marked
"checked": False until a person has verified them against a second source.
"""
from __future__ import annotations
import json, math, shutil
import numpy as np
import shapely
from collections import defaultdict
from config import iso, geo_block, WIDTH, HEIGHT, ROOT, lonlat_from_iso

WEB = ROOT / "web"

CATS = {
    "heritage": ["Temples & heritage", "கோயில்களும் மரபும்"],
    "rivers": ["Cauvery & waterworks", "காவிரியும் நீர்ப்பணிகளும்"],
    "landmarks": ["Landmarks", "அடையாளங்கள்"],
    "areas": ["Neighbourhoods", "பகுதிகள்"],
}

# slug, English, Tamil, area, cat, lat, lon, blurb
P = [
    ("rockfort", "Rockfort", "மலைக்கோட்டை", "Rockfort", "heritage", 10.8283, 78.6972,
     "A rock about 83 metres high rises from the middle of the old city. A steep stair climbs to the Ucchi Pillayar temple on top, and Pallava-era cave temples sit at its foot. The Madurai Nayaks fortified it, and it was fought over in the Carnatic Wars."),
    ("srirangam-temple", "Sri Ranganathaswamy Temple", "ஸ்ரீரங்கநாதசுவாமி கோயில்", "Srirangam", "heritage", 10.8624, 78.6899,
     "One of the largest functioning Hindu temples in the world, enclosed by seven concentric walls across roughly 156 acres. The Raja Gopuram at the south gate, completed in 1987, rises about 73 metres."),
    ("jambukeswarar", "Jambukeswarar Temple", "ஜம்புகேஸ்வரர் கோயில்", "Thiruvanaikaval", "heritage", 10.8533, 78.7056,
     "The Shiva shrine of the element water, where the sanctum floor is kept damp by a spring. It lies on Srirangam island about a kilometre from the Ranganathaswamy temple."),
    ("teppakulam", "Teppakulam", "தெப்பக்குளம்", "Rockfort", "heritage", 10.8271, 78.6932,
     "The big temple tank at the foot of the Rock, with a small mandapam in the middle. The bazaar streets around it are among the busiest in the city."),
    ("samayapuram", "Samayapuram Mariamman Temple", "சமயபுரம் மாரியம்மன் கோயில்", "Samayapuram", "heritage", 10.9184, 78.7391,
     "A Mariamman shrine on the Chennai highway north of the city, and one of the busiest pilgrimage temples in Tamil Nadu."),
    ("vayalur", "Vayalur Murugan Temple", "வயலூர் முருகன் கோயில்", "Vayalur", "heritage", 10.8289, 78.6231,
     "A Murugan temple west of the city, praised in the Thiruppugazh hymns of Arunagirinathar. A tall gopuram marks the entrance to its walled courtyard."),
    ("woraiyur", "Woraiyur Vekkaliamman Temple", "உறையூர் வெக்காளியம்மன் கோயில்", "Woraiyur", "heritage", 10.8299, 78.6705,
     "Woraiyur is the old Uraiyur, an early Chola capital named in Sangam poetry. The Vekkaliamman temple is its best known shrine."),
    ("lourdes-church", "Our Lady of Lourdes Church", "லூர்து அன்னை ஆலயம்", "Rockfort", "heritage", 10.8270, 78.6928,
     "A Catholic church beside St. Joseph's College, said to be modelled on the basilica at Lourdes in France. Its spire is a landmark in the old city."),
    ("erumbeeswarar", "Erumbeeswarar Temple", "எறும்பீசுவரர் கோயில்", "Thiruverumbur", "heritage", 10.7927, 78.7674,
     "A Shiva temple on a low rocky hill in Thiruverumbur, in the industrial east of the city."),
    ("amma-mandapam", "Amma Mandapam Ghat", "அம்மா மண்டபம்", "Srirangam", "heritage", 10.8469, 78.6899,
     "The bathing ghat on the Cauvery at Srirangam. Pilgrims bathe here, and crowds gather during the Aadi Perukku river festival."),
    ("kallanai", "Kallanai (Grand Anicut)", "கல்லணை", "Kallanai", "rivers", 10.8315, 78.8189,
     "Built by the Chola king Karikalan around the 2nd century CE, it is among the oldest water-regulation structures still in use. It sends Cauvery water into the delta. The British engineer Arthur Cotton restored it in the 19th century."),
    ("mukkombu", "Mukkombu (Upper Anicut)", "முக்கொம்பு", "Mukkombu", "rivers", 10.8883, 78.5805,
     "Where the Cauvery divides, sending the Kollidam off to the north. The Upper Anicut regulator controls the flow, and the riverside park is a popular day out."),
    ("kaveri-bridge", "Kaveri Bridge", "காவிரி பாலம்", "Cauvery", "rivers", 10.8394, 78.6973,
     "The long bridge that joins the city to Srirangam island across the Cauvery."),
    ("kollidam-bridge", "New Kollidam Bridge", "புதிய கொள்ளிடம் பாலம்", "Kollidam", "rivers", 10.8656, 78.7043,
     "Carries the road across the broad, sandy bed of the Kollidam on the north side of Srirangam island."),
    ("trichy-junction", "Tiruchirappalli Junction", "திருச்சி சந்திப்பு", "Junction", "landmarks", 10.7941, 78.6854,
     "Southern Railway's busy junction and the seat of the Tiruchirappalli division, with lines to Chennai, Madurai, Thanjavur and Karur."),
    ("central-bus-stand", "Central Bus Stand", "மத்திய பேருந்து நிலையம்", "Junction", "landmarks", 10.7986, 78.6808,
     "The main bus terminus, close to the railway junction, with services across Tamil Nadu."),
    ("chatram", "Chatram Bus Stand", "சத்திரம் பேருந்து நிலையம்", "Rockfort", "landmarks", 10.83169, 78.69361,
     "The bus stand near Rockfort. Its name recalls the old pilgrim rest-houses, called chatrams."),
    ("anna-stadium", "Anna Stadium", "அண்ணா விளையாட்டரங்கம்", "Anna Nagar", "landmarks", 10.78054, 78.69657,
     "The city's main sports ground, with a football pitch, a running track and tiered stands that host district meets and local matches."),
    ("gandhi-market", "Gandhi Market", "காந்தி சந்தை", "Gandhi Market", "landmarks", 10.81575, 78.69792,
     "The city's wholesale market for vegetables, fruit and flowers, busy from before dawn."),
    ("st-josephs", "St. Joseph's College", "புனித வளனார் கல்லூரி", "Rockfort", "landmarks", 10.8278, 78.6929,
     "A Jesuit college founded in 1844 that has been in Tiruchirappalli since 1883, with a long campus below the Rock."),
    ("golden-rock", "Golden Rock Railway Workshop", "பொன்மலை ரயில்வே பணிமனை", "Ponmalai", "landmarks", 10.7898, 78.7222,
     "A large Southern Railway workshop. The neighbourhood is called Ponmalai, 'golden hill', after a small rocky hill nearby."),
    ("airport", "Tiruchirappalli International Airport", "திருச்சி பன்னாட்டு விமான நிலையம்", "Airport", "landmarks", 10.7600, 78.7125,
     "The city's airport, known for direct flights to Singapore, Malaysia, the Gulf and Sri Lanka."),
    ("nit", "NIT Tiruchirappalli", "தேசிய தொழில்நுட்பக் கழகம்", "NIT", "landmarks", 10.7588, 78.8160,
     "Founded in 1964 as the Regional Engineering College and now one of India's National Institutes of Technology."),
    ("bhel", "BHEL Township", "பெல் நகரியம்", "Thiruverumbur", "landmarks", 10.7791, 78.7975,
     "BHEL's boiler plant, set up in the 1960s, anchors the township and the industrial belt of Thiruverumbur."),
    ("panjappur-terminus", "Panjappur Integrated Bus Terminus", "பஞ்சப்பூர் ஒருங்கிணைந்த பேருந்து முனையம்", "Panjappur", "landmarks", 10.75438, 78.65584,
     "The city's new integrated bus terminus at Panjappur on the Madurai highway, with long canopied bus bays, a terminal hall and large car parks."),
    ("butterfly-park", "Tropical Butterfly Conservatory", "பட்டாம்பூச்சி பூங்கா", "Melur, Srirangam", "landmarks", 10.87765, 78.63605,
     "A large butterfly park at Melur on the western end of Srirangam island, with landscaped gardens, lily ponds and glass conservatory domes."),
    ("planetarium", "Anna Science Centre Planetarium", "அண்ணா அறிவியல் மையக் கோளரங்கம்", "Pudukkottai Road", "landmarks", 10.76819, 78.70372,
     "A science centre and planetarium on the Pudukkottai road near the airport, with a domed sky theatre and science galleries."),
    ("srirangam", "Srirangam", "ஸ்ரீரங்கம்", "Srirangam", "areas", 10.8570, 78.6970,
     "The island between the Cauvery and the Kollidam. Its streets run in concentric squares around the great temple."),
    ("thillai-nagar", "Thillai Nagar", "தில்லை நகர்", "Thillai Nagar", "areas", 10.8225, 78.6836,
     "A leafy residential and shopping neighbourhood west of the Rock, known for its cafes and showrooms."),
    ("woraiyur-area", "Woraiyur", "உறையூர்", "Woraiyur", "areas", 10.8239, 78.6768,
     "A close-grained old quarter west of the city centre, once a Chola capital."),
    ("thiruverumbur", "Thiruverumbur", "திருவெறும்பூர்", "Thiruverumbur", "areas", 10.7942, 78.7617,
     "A town in the east of the city that grew around its hill temple and the BHEL works."),
    ("ponmalai", "Ponmalai", "பொன்மலை", "Ponmalai", "areas", 10.7856, 78.7233,
     "The railway workshop quarter around the Golden Rock hill, south-east of the junction."),
    ("beema-nagar", "Beema Nagar", "பீமா நகர்", "Beema Nagar", "areas", 10.8087, 78.6920,
     "A busy neighbourhood between the Junction and the old city, next to Palakkarai."),
    ("palakkarai", "Palakkarai", "பாலக்கரை", "Palakkarai", "areas", 10.8115, 78.6955,
     "An old commercial quarter east of the railway, with its own small station and crowded bazaar streets."),
    ("kk-nagar", "KK Nagar", "கே.கே. நகர்", "KK Nagar", "areas", 10.7570, 78.6895,
     "A large planned residential area in the south of the city, off the Madurai road."),
    ("kattur", "Kattur", "காட்டூர்", "Kattur", "areas", 10.7940, 78.7500,
     "A growing residential and shopping area on the Thanjavur road, between the city centre and Thiruverumbur."),
]


def build_places():
    places = []
    for n, (slug, en, ta, area, cat, lat, lon, blurb) in enumerate(P, 1):
        x, y = iso(lon, lat)
        places.append(dict(name=en, ta=ta, area=area, cat=cat, blurb=blurb, x=round(x), y=round(y),
                           lat=lat, lon=lon, slug=slug, n=n, img=f"assets/places/{slug}.webp", checked=False))
    return places


def build_roads():
    """Named road centre lines merged by name; keep the longest piece of each name for labels, all for search."""
    import scene
    sc, _ = scene.load()
    geoms, meta = sc["road_names"]
    by = defaultdict(list)
    for g, (sub, cls, name) in zip(geoms, meta):
        by[name].append((g, cls))
    rank = {"trunk": 0, "primary": 1, "secondary": 2, "tertiary": 3}
    labels, search = [], []
    for name, parts in by.items():
        longest = max(parts, key=lambda p: p[0].length)
        g, cls = longest
        total = sum(p[0].length for p in parts)
        pts = shapely.get_coordinates(shapely.segmentize(g, 200))
        mid = pts[len(pts) // 2]
        i = len(pts) // 2
        a, b = pts[max(0, i - 1)], pts[min(len(pts) - 1, i + 1)]
        ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        if ang > 90: ang -= 180
        if ang < -90: ang += 180
        lat_lon = lonlat_from_iso(mid[0], mid[1])
        search.append([name, round(mid[0]), round(mid[1]), "Street", round(lat_lon[0], 5), round(lat_lon[1], 5)])  # lon, lat
        if cls in rank and total > 900 * 2:  # main roads at least ~900 m
            labels.append(dict(name=name, x=round(mid[0]), y=round(mid[1]), a=round(ang, 1), r=rank[cls], len=round(total)))
    labels.sort(key=lambda l: (l["r"], -l["len"]))
    return labels[:260], search


THUMB_SCALE = {"srirangam-temple": 3.2, "rockfort": 2.2, "teppakulam": 2.0, "anna-stadium": 2.0, "samayapuram": 1.6,
               "vayalur": 1.6, "jambukeswarar": 2.2, "woraiyur": 1.5, "lourdes-church": 1.0, "erumbeeswarar": 1.8,
               "airport": 3.0, "gandhi-market": 1.6, "central-bus-stand": 1.6, "chatram": 1.6, "golden-rock": 2.4, "bhel": 2.0,
               "amma-mandapam": 1.5, "kallanai": 1.4, "trichy-junction": 1.6, "st-josephs": 1.2,
               "panjappur-terminus": 3.2, "butterfly-park": 2.6, "planetarium": 1.2, "kollidam-bridge": 1.6, "mukkombu": 1.6}


# AI-illustrated hero scenes (GenerateImage, from the base render + Chennai style references). They are illustrations,
# not survey drawings. Their card crops are saved to web/assets/heroes/<slug>-card.webp and copied to the place thumbnail.
HEROES = set()   # place cards are real renders of the map now; the AI hero images stay in web/assets/heroes as design targets


def thumbs(places):
    from PIL import Image
    import scene, render
    from config import TILE
    sc, trees = scene.load()
    R = render.Renderer(sc, trees)
    for p in places:
        if p["slug"] in HEROES:
            shutil.copyfile(WEB / "assets" / "heroes" / f'{p["slug"]}-card.webp', WEB / p["img"])
            continue
        k = THUMB_SCALE.get(p["slug"], 1.0)  # big monuments are shown from further out
        im = R.render_tile(0, 0, size=int(720 * k), ox=p["x"] - int(360 * k), oy=p["y"] - int(400 * k))
        im = im.crop((int(120 * k), int(250 * k), int(600 * k), int(530 * k)))  # place point at the middle
        if k != 1.0:
            im = im.resize((480, 280), Image.LANCZOS)
        im.save(WEB / p["img"], format="WEBP", quality=90)


def colleges():
    """Colleges, universities and institutes from Overture places, for search."""
    import duckdb
    from config import BBOX, DATA
    con = duckdb.connect(); con.execute("INSTALL spatial; LOAD spatial")
    b = BBOX
    rows = con.execute(f"""select names.primary, ST_X(geometry), ST_Y(geometry), confidence from '{DATA}/raw/places.parquet'
        where (basic_category in ('college_university') or names.primary ilike '%college%' or names.primary ilike '%university%'
               or names.primary ilike '%institute of%' or names.primary ilike '%polytechnic%')
          and ST_Y(geometry) between {b['south']} and {b['north']} and ST_X(geometry) between {b['west']} and {b['east']}
        order by confidence desc""").fetchall()
    out, seen = [], set()
    bad = ("coaching", "academy", "tuition", "xerox", "bus stop", "hostel", "canteen", "atm", "store", "shop", "stationery")
    for name, lon, lat, conf in rows:
        if not name:
            continue
        key = " ".join(name.lower().replace(",", " ").split())
        if key in seen or any(w in key for w in bad):
            continue
        if not any(w in key for w in ("college", "university", "institute", "polytechnic", "nit ", "iiit", "iim")):
            continue
        seen.add(key)
        x, y = iso(lon, lat)
        out.append([name.strip(), round(x), round(y), "College", round(lon, 5), round(lat, 5)])
    print(len(out), "colleges for search")
    return out


def main():
    places = build_places()
    thumbs(places)
    labels, search = build_roads()
    import outline
    ol = outline.load()
    bx = ol.bounds
    # the city name sits in the countryside just below the outline's lowest point
    low = max(ol.exterior.coords, key=lambda p: p[1])
    data = dict(cats=CATS, places=places, geo=geo_block(), roads=labels, width=WIDTH, height=HEIGHT,
                outline=dict(label=[round(low[0]), round(min(HEIGHT - 600, low[1] + 1500))], bounds=[round(v) for v in bx]))
    (WEB / "data" / "places.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    for p in places:
        search.append([p["name"], p["x"], p["y"], {"heritage": "Temple", "rivers": "Waterworks", "landmarks": "Landmark", "areas": "Neighbourhood"}[p["cat"]],
                       p["lon"], p["lat"], p["ta"], p["slug"]])
    search += colleges()
    (WEB / "data" / "search.json").write_text(json.dumps(search, ensure_ascii=False, separators=(",", ":")))
    print(len(places), "places,", len(labels), "road labels,", len(search), "search rows")


if __name__ == "__main__":
    main()
