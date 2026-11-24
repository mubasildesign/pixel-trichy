"""Local dev server for web/: static files (tiles are versioned by ?v= in config.json) plus the small live API that the
production Cloudflare Worker (worker/index.js) also implements, backed here by SQLite in data/live.db.

  .venv/bin/python pipeline/serve.py [port]
  PT_ADMIN=secret .venv/bin/python pipeline/serve.py      # enables the admin endpoints below

API (JSON, same paths in worker/index.js):
  POST   /api/ping            {id}                        -> {live, visitors}     heartbeat; first sight of an id counts a visitor
  GET    /api/memories                                    -> [{id, lat, lon, text, name, ts}]
  POST   /api/memories        {lat, lon, text, name}      -> the stored memory
  POST   /api/reports         {id, kind, note, lat, lon}  -> {id}
  GET    /api/reports?ids=1,2,3                           -> [{id, status}]       status: new | seen | fixed | wontfix
  admin (header x-admin: $PT_ADMIN):
  GET    /api/admin/reports                               -> every report
  PATCH  /api/admin/reports/<id>   {status}
  DELETE /api/admin/memories/<id>
"""
import sys, os, json, time, sqlite3, threading, http.server, functools, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "web"
DB = ROOT / "data" / "live.db"
ADMIN = os.environ.get("PT_ADMIN", "")
LIVE_WINDOW = 75            # seconds without a heartbeat before a visitor stops counting as "here now"
KINDS = {"map", "missing", "traffic", "seam", "other"}
STATUSES = {"new", "seen", "fixed", "wontfix"}
BBOX = (10.60, 10.99, 78.45, 78.95)   # south, north, west, east: generous, just to reject junk coordinates

_lock = threading.Lock()
_hits = {}                  # (ip, kind) -> [timestamps], a small flood guard
LIMITS = {"memory": (6, 3600), "report": (12, 3600), "ping": (400, 3600)}


def db():
    con = sqlite3.connect(DB, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    DB.parent.mkdir(exist_ok=True)
    with db() as c:
        c.executescript("""
        create table if not exists visitors (id text primary key, first_ts integer);
        create table if not exists presence (id text primary key, ts integer);
        create table if not exists memories (id integer primary key autoincrement, lat real, lon real, text text, name text, ts integer, hidden integer default 0);
        create table if not exists reports (id integer primary key autoincrement, uid text, kind text, note text, lat real, lon real, status text default 'new', ts integer);
        """)


def clean(s, n):
    s = re.sub(r"[\x00-\x08\x0b-\x1f]", "", str(s or "")).strip()
    return re.sub(r"\s+\n", "\n", s)[:n]


def in_box(lat, lon):
    return BBOX[0] <= lat <= BBOX[1] and BBOX[2] <= lon <= BBOX[3]


def too_many(ip, kind):
    n, win = LIMITS[kind]
    now = time.time()
    with _lock:
        h = [t for t in _hits.get((ip, kind), []) if now - t < win]
        if len(h) >= n:
            _hits[(ip, kind)] = h
            return True
        h.append(now)
        _hits[(ip, kind)] = h
    return False


class H(http.server.SimpleHTTPRequestHandler):
    def send_response(self, code, message=None):
        self._code = code
        super().send_response(code, message)

    def end_headers(self):
        # only successful tiles are cached for good; a 404 must never be remembered
        if "/tiles/" in self.path and "?v=" in self.path and getattr(self, "_code", 200) == 200:
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        else:
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def log_message(self, *a):
        pass

    # ------------------------------------------------------------------ API
    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _body(self):
        try:
            n = int(self.headers.get("Content-Length") or 0)
            return json.loads(self.rfile.read(min(n, 20000)) or b"{}")
        except Exception:
            return {}

    def _admin(self):
        return bool(ADMIN) and self.headers.get("x-admin") == ADMIN

    def api(self, method):
        path = self.path.split("?")[0]
        qs = self.path.split("?")[1] if "?" in self.path else ""
        ip = self.client_address[0]
        try:
            if method == "POST" and path == "/api/ping":
                if too_many(ip, "ping"):
                    return self._json({"error": "slow down"}, 429)
                uid = clean(self._body().get("id"), 40)
                if not re.fullmatch(r"[A-Za-z0-9_-]{8,40}", uid):
                    return self._json({"error": "bad id"}, 400)
                now = int(time.time())
                with db() as c:
                    c.execute("insert or ignore into visitors values (?,?)", (uid, now))
                    c.execute("insert or replace into presence values (?,?)", (uid, now))
                    c.execute("delete from presence where ts < ?", (now - 3600,))
                    live = c.execute("select count(*) from presence where ts > ?", (now - LIVE_WINDOW,)).fetchone()[0]
                    visitors = c.execute("select count(*) from visitors").fetchone()[0]
                return self._json({"live": live, "visitors": visitors})

            if method == "GET" and path == "/api/memories":
                with db() as c:
                    rows = c.execute("select id, lat, lon, text, name, ts from memories where hidden=0 order by id desc limit 800").fetchall()
                return self._json([dict(r) for r in rows])

            if method == "POST" and path == "/api/memories":
                if too_many(ip, "memory"):
                    return self._json({"error": "You have pinned a few memories already. Try again in a while."}, 429)
                b = self._body()
                lat, lon = float(b.get("lat", 0)), float(b.get("lon", 0))
                text, name = clean(b.get("text"), 280), clean(b.get("name"), 40)
                if not in_box(lat, lon) or len(text) < 3:
                    return self._json({"error": "bad memory"}, 400)
                with db() as c:
                    cur = c.execute("insert into memories (lat, lon, text, name, ts) values (?,?,?,?,?)", (lat, lon, text, name, int(time.time())))
                return self._json({"id": cur.lastrowid, "lat": lat, "lon": lon, "text": text, "name": name, "ts": int(time.time())}, 201)

            if method == "POST" and path == "/api/reports":
                if too_many(ip, "report"):
                    return self._json({"error": "Too many reports from here. Try again in a while."}, 429)
                b = self._body()
                kind = b.get("kind") if b.get("kind") in KINDS else "other"
                note = clean(b.get("note"), 600)
                lat, lon = float(b.get("lat", 0)), float(b.get("lon", 0))
                if len(note) < 3 or not in_box(lat, lon):
                    return self._json({"error": "bad report"}, 400)
                with db() as c:
                    cur = c.execute("insert into reports (uid, kind, note, lat, lon, ts) values (?,?,?,?,?,?)", (clean(b.get("id"), 40), kind, note, lat, lon, int(time.time())))
                return self._json({"id": cur.lastrowid}, 201)

            if method == "GET" and path == "/api/reports":
                ids = [int(i) for i in re.findall(r"\d+", dict(p.split("=", 1) for p in qs.split("&") if "=" in p).get("ids", ""))][:100]
                with db() as c:
                    rows = c.execute(f"select id, status from reports where id in ({','.join('?' * len(ids))})", ids).fetchall() if ids else []
                return self._json([dict(r) for r in rows])

            if path.startswith("/api/admin/"):
                if not self._admin():
                    return self._json({"error": "forbidden"}, 403)
                if method == "GET" and path == "/api/admin/reports":
                    with db() as c:
                        return self._json([dict(r) for r in c.execute("select * from reports order by id desc limit 500").fetchall()])
                m = re.fullmatch(r"/api/admin/reports/(\d+)", path)
                if method == "PATCH" and m:
                    st = self._body().get("status")
                    if st not in STATUSES:
                        return self._json({"error": "bad status"}, 400)
                    with db() as c:
                        c.execute("update reports set status=? where id=?", (st, int(m.group(1))))
                    return self._json({"ok": True})
                m = re.fullmatch(r"/api/admin/memories/(\d+)", path)
                if method == "DELETE" and m:
                    with db() as c:
                        c.execute("update memories set hidden=1 where id=?", (int(m.group(1)),))
                    return self._json({"ok": True})
            return self._json({"error": "not found"}, 404)
        except (ValueError, TypeError):
            return self._json({"error": "bad request"}, 400)

    def do_GET(self):
        if self.path.startswith("/api/"):
            return self.api("GET")
        return super().do_GET()

    def do_POST(self):
        return self.api("POST") if self.path.startswith("/api/") else self.send_error(404)

    def do_PATCH(self):
        return self.api("PATCH") if self.path.startswith("/api/") else self.send_error(404)

    def do_DELETE(self):
        return self.api("DELETE") if self.path.startswith("/api/") else self.send_error(404)


if __name__ == "__main__":
    init_db()
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(H, directory=str(WEB)))
    print(f"http://localhost:{port}   live API on /api/*  ({'admin on' if ADMIN else 'admin off: set PT_ADMIN'})", flush=True)
    srv.serve_forever()
