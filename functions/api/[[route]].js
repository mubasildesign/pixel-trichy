// Cloudflare Pages Function: the same live API as pipeline/serve.py (see its docstring), on D1.
const LIVE_WINDOW = 75;
const KINDS = ['map', 'missing', 'traffic', 'seam', 'other'];
const STATUSES = ['new', 'seen', 'fixed', 'wontfix'];
const BBOX = [10.60, 10.99, 78.45, 78.95];
const LIMITS = { memory: [6, 3600], report: [12, 3600], ping: [400, 3600] };

const json = (o, status = 200) => new Response(JSON.stringify(o), { status, headers: { 'content-type': 'application/json', 'cache-control': 'no-store' } });
const clean = (s, n) => String(s ?? '').replace(/[\x00-\x08\x0b-\x1f]/g, '').trim().slice(0, n);
const inBox = (lat, lon) => lat >= BBOX[0] && lat <= BBOX[1] && lon >= BBOX[2] && lon <= BBOX[3];

async function limited(db, ip, kind) {
  const [n, win] = LIMITS[kind], now = Math.floor(Date.now() / 1000);
  const { c } = await db.prepare('select count(*) c from hits where ip=? and kind=? and ts>?').bind(ip, kind, now - win).first();
  if (c >= n) return true;
  await db.batch([db.prepare('insert into hits values (?,?,?)').bind(ip, kind, now), db.prepare('delete from hits where ts<?').bind(now - 7200)]);
  return false;
}

export async function onRequest({ request, env }) {
  const db = env.DB, url = new URL(request.url), path = url.pathname.replace(/\/$/, ''), method = request.method;
  const ip = request.headers.get('cf-connecting-ip') || 'x', now = Math.floor(Date.now() / 1000);
  const body = async () => { try { return await request.json(); } catch { return {}; } };
  try {
    if (method === 'POST' && path === '/api/ping') {
      if (await limited(db, ip, 'ping')) return json({ error: 'slow down' }, 429);
      const id = clean((await body()).id, 40);
      if (!/^[A-Za-z0-9_-]{8,40}$/.test(id)) return json({ error: 'bad id' }, 400);
      await db.batch([
        db.prepare('insert or ignore into visitors values (?,?)').bind(id, now),
        db.prepare('insert or replace into presence values (?,?)').bind(id, now),
        db.prepare('delete from presence where ts<?').bind(now - 3600),
      ]);
      const live = (await db.prepare('select count(*) c from presence where ts>?').bind(now - LIVE_WINDOW).first()).c;
      const visitors = (await db.prepare('select count(*) c from visitors').first()).c;
      return json({ live, visitors });
    }
    if (method === 'GET' && path === '/api/memories') {
      const { results } = await db.prepare('select id, lat, lon, text, name, ts from memories where hidden=0 order by id desc limit 800').all();
      return json(results);
    }
    if (method === 'POST' && path === '/api/memories') {
      if (await limited(db, ip, 'memory')) return json({ error: 'You have pinned a few memories already. Try again in a while.' }, 429);
      const b = await body(), lat = +b.lat, lon = +b.lon, text = clean(b.text, 280), name = clean(b.name, 40);
      if (!inBox(lat, lon) || text.length < 3) return json({ error: 'bad memory' }, 400);
      const r = await db.prepare('insert into memories (lat, lon, text, name, ts) values (?,?,?,?,?)').bind(lat, lon, text, name, now).run();
      return json({ id: r.meta.last_row_id, lat, lon, text, name, ts: now }, 201);
    }
    if (method === 'POST' && path === '/api/reports') {
      if (await limited(db, ip, 'report')) return json({ error: 'Too many reports from here. Try again in a while.' }, 429);
      const b = await body(), kind = KINDS.includes(b.kind) ? b.kind : 'other', note = clean(b.note, 600), lat = +b.lat, lon = +b.lon;
      if (note.length < 3 || !inBox(lat, lon)) return json({ error: 'bad report' }, 400);
      const r = await db.prepare('insert into reports (uid, kind, note, lat, lon, ts) values (?,?,?,?,?,?)').bind(clean(b.id, 40), kind, note, lat, lon, now).run();
      return json({ id: r.meta.last_row_id }, 201);
    }
    if (method === 'GET' && path === '/api/reports') {
      const ids = (url.searchParams.get('ids') || '').match(/\d+/g)?.slice(0, 100).map(Number) || [];
      if (!ids.length) return json([]);
      const { results } = await db.prepare(`select id, status from reports where id in (${ids.map(() => '?').join(',')})`).bind(...ids).all();
      return json(results);
    }
    if (path.startsWith('/api/admin/')) {
      if (!env.ADMIN || request.headers.get('x-admin') !== env.ADMIN) return json({ error: 'forbidden' }, 403);
      if (method === 'GET' && path === '/api/admin/reports') return json((await db.prepare('select * from reports order by id desc limit 500').all()).results);
      let m = path.match(/^\/api\/admin\/reports\/(\d+)$/);
      if (method === 'PATCH' && m) {
        const st = (await body()).status;
        if (!STATUSES.includes(st)) return json({ error: 'bad status' }, 400);
        await db.prepare('update reports set status=? where id=?').bind(st, +m[1]).run();
        return json({ ok: true });
      }
      m = path.match(/^\/api\/admin\/memories\/(\d+)$/);
      if (method === 'DELETE' && m) { await db.prepare('update memories set hidden=1 where id=?').bind(+m[1]).run(); return json({ ok: true }); }
    }
    return json({ error: 'not found' }, 404);
  } catch (e) {
    return json({ error: 'server error' }, 500);
  }
}
