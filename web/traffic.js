// Moving traffic for Pixel Trichy: vehicles that drive along the real road network and trains that run on the real rail lines.
// Everything is drawn with sprite atlases on one canvas above the map, in the same projection as the tiles (image pixels at the
// deepest level). Motion is decorative, it is not live traffic or timetable data. Click a train to ride it, click a station to fly there.
(() => {
  const K = 2, VK = 2, TIME = 1.4;                 // projection constants (pipeline/config.py), fast-forward factor for the animation
  const SPACING = [110, 110, 105, 130, 170, 260, 400]; // metres between vehicles in one lane, by road class index (motorway ... residential)
  const LANE = [3.6, 3.6, 3, 2.5, 2, 1.5, 1.2];   // metres from the centre line to the lane we drive in (traffic keeps left)
  const SPEED = { scooter: 8.5, cycle: 3.4, auto: 6.2, car: 8.2, bus: 6.8, truck: 5.8 };
  const LOD = [[0.28, 2], [0.5, 3], [0.9, 4], [Infinity, 5]]; // [below this image zoom, highest road class index drawn]
  const DWELL = 6;                                // seconds a train stands in a station
  const TRAIN_SPEED = 21, FREIGHT_SPEED = 13;     // metres per second
  const GAP = 1.2;

  let OCC_STEP = 6;                               // px between road occlusion samples (set from traffic.json)
  let ctx = null, canvas = null, g = null, raf = 0, last = 0, T = 0, shown = true;
  let roads = null, trains = [], lines = [], atlas = null, vImg = null, tImg = null, clip = null, follow = null, bar = null;

  // ------------------------------------------------------------------ helpers
  const mlen = (dx, dy) => { const a = (dx / K - 2 * dy / K) / 2, b = (-dx / K - 2 * dy / K) / 2; return Math.hypot(a, b); };
  const toM = (dx, dy) => [(dx / K - 2 * dy / K) / 2, (-dx / K - 2 * dy / K) / 2];
  const toPx = (a, b) => [a * K - b * K, -a * K / 2 - b * K / 2];
  function rng(seed) { let s = seed >>> 0; return () => { s = (s + 0x6D2B79F5) >>> 0; let t = s; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  const img = src => new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = no; i.src = src; });
  const getJson = u => fetch(u).then(r => { if (!r.ok) throw new Error(u); return r.json(); });

  // a polyline with cumulative length in metres
  function prep(flat) {
    const n = flat.length / 2, xs = new Float32Array(n), ys = new Float32Array(n), cum = new Float32Array(n), pc = new Float32Array(n);
    let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
    for (let i = 0; i < n; i++) {
      xs[i] = flat[2 * i]; ys[i] = flat[2 * i + 1];
      if (i) { cum[i] = cum[i - 1] + mlen(xs[i] - xs[i - 1], ys[i] - ys[i - 1]); pc[i] = pc[i - 1] + Math.hypot(xs[i] - xs[i - 1], ys[i] - ys[i - 1]); }
      x0 = Math.min(x0, xs[i]); x1 = Math.max(x1, xs[i]); y0 = Math.min(y0, ys[i]); y1 = Math.max(y1, ys[i]);
    }
    return { xs, ys, cum, pc, len: cum[n - 1], box: [x0 - 40, y0 - 40, x1 + 40, y1 + 40] };
  }
  const out = [0, 0, 0, 0, 0, 0];
  // position and travel direction (px, in the metre frame as a unit vector a,b) at distance d metres
  function at(p, d) {
    const c = p.cum; let lo = 0, hi = c.length - 1;
    if (d <= 0) d = 0; else if (d >= p.len) d = p.len - 1e-3;
    while (hi - lo > 1) { const m = (lo + hi) >> 1; if (c[m] <= d) lo = m; else hi = m; }
    const f = (d - c[lo]) / ((c[hi] - c[lo]) || 1);
    const dx = p.xs[hi] - p.xs[lo], dy = p.ys[hi] - p.ys[lo], m = toM(dx, dy), nm = Math.hypot(m[0], m[1]) || 1;
    out[0] = p.xs[lo] + dx * f; out[1] = p.ys[lo] + dy * f; out[2] = m[0] / nm; out[3] = m[1] / nm;
    out[4] = p.pc[lo] + (p.pc[hi] - p.pc[lo]) * f; out[5] = lo;   // out[4]: px along the chain, out[5]: vertex index
    return out;
  }
  const bucket = (a, b, n) => (((Math.round(Math.atan2(b, a) / (2 * Math.PI) * n)) % n) + n) % n;

  // ------------------------------------------------------------------ road traffic
  function fill(ch, idx) {
    if (ch.v) return ch.v;
    const r = rng(idx * 7919 + 13), cls = ch.c, L = ch.p.len, per = Math.max(1, Math.round(L / SPACING[cls]));
    const big = cls <= 3, list = [];
    for (let lane = 0; lane < 2; lane++) {
      for (let k = 0; k < per; k++) {
        const q = r();
        let kind = q < 0.34 ? 'scooter' : q < 0.55 ? 'auto' : q < 0.78 ? 'car' : q < 0.84 ? 'cycle' : (big && q < 0.92) ? 'bus' : (big && q < 0.97) ? 'truck' : 'scooter';
        if (cls >= 5 && (kind === 'bus' || kind === 'truck')) kind = 'scooter';
        const nv = atlas.vehicles.rows[kind][1];
        list.push({ s0: ((k + r() * 0.7) / per) * L, v: SPEED[kind] * (0.82 + r() * 0.36) * (big ? 1.12 : cls >= 5 ? 0.78 : 1), dir: lane ? -1 : 1, kind, var: (r() * nv) | 0 });
      }
    }
    return (ch.v = list);
  }

  function drawRoads(P, w, h, maxCls) {
    const vx0 = -P.x / P.s - 60, vy0 = -P.y / P.s - 80, vx1 = (w - P.x) / P.s + 60, vy1 = (h - P.y) / P.s + 60;
    const A = atlas.vehicles, cw = A.cell[0], chh = A.cell[1], ox = A.origin[0], oy = A.origin[1], N = A.headings;
    const q = [];
    for (let i = 0; i < roads.length; i++) {
      const ch = roads[i];
      if (ch.c > maxCls) continue;
      const b = ch.p.box;
      if (b[2] < vx0 || b[0] > vx1 || b[3] < vy0 || b[1] > vy1) continue;
      const L = ch.p.len;
      for (const v of fill(ch, i)) {
        let s = v.dir > 0 ? (v.s0 + v.v * T) % L : ((v.s0 - v.v * T) % L + L) % L;
        const p = at(ch.p, s);
        // per-sample flag from traffic_data.py: '1' something in front hides it, 'A'.. on a bridge or flyover deck (lift = (code-65)/2 m)
        const f = ch.occ.charCodeAt(Math.floor(p[4] / OCC_STEP));
        if (f === 49) continue;
        const lift = f >= 65 ? (f - 65) * 0.5 * VK : 0;
        let a = p[2] * v.dir, bb = p[3] * v.dir;
        // lane: offset to the left of the direction of travel
        const off = toPx(-bb * LANE[ch.c], a * LANE[ch.c]);
        const X = p[0] + off[0], Y = p[1] + off[1] - lift;
        if (X < vx0 || X > vx1 || Y < vy0 || Y > vy1) continue;
        q.push(Y + lift, X, bucket(a, bb, N), v, lift);
      }
    }
    // painter order: far (smaller y) first
    const n = q.length / 5, ord = new Array(n);
    for (let i = 0; i < n; i++) ord[i] = i;
    ord.sort((i, j) => q[5 * i] - q[5 * j]);
    const row = A.rows;
    for (const i of ord) {
      const Y = q[5 * i] - q[5 * i + 4], X = q[5 * i + 1], hd = q[5 * i + 2], v = q[5 * i + 3];
      const r = row[v.kind][0] + v.var;
      g.drawImage(vImg, hd * cw, r * chh, cw, chh, P.x + (X - ox) * P.s, P.y + (Y - oy) * P.s, cw * P.s, chh * P.s);
    }
  }

  // ------------------------------------------------------------------ trains
  function buildTrains(data) {
    lines = data.lines.map(l => {
      const flat = []; for (const p of l.pts) flat.push(p[0], p[1]);
      const p = prep(flat);
      // station positions: px along the line -> metres along the line
      const pc = [0]; for (let i = 1; i < l.pts.length; i++) pc.push(pc[i - 1] + Math.hypot(l.pts[i][0] - l.pts[i - 1][0], l.pts[i][1] - l.pts[i - 1][1]));
      const toMetres = d => { let k = 1; while (k < pc.length - 1 && pc[k] < d) k++; const f = (d - pc[k - 1]) / ((pc[k] - pc[k - 1]) || 1); return p.cum[k - 1] + (p.cum[k] - p.cum[k - 1]) * Math.max(0, Math.min(1, f)); };
      return { name: l.name, path: p, occ: l.occ || '', stations: l.stations.map(s => ({ ...s, m: toMetres(s.at) })) };
    });
    const A = atlas.trains;
    trains = [];
    let id = 0;
    lines.forEach((l, li) => {
      const count = li === 0 ? 5 : 4;
      for (let i = 0; i < count; i++) {
        const freight = i === 2 || (li === 1 && i === 3);
        const r = rng(li * 101 + i * 17 + 3), cars = [];
        const lv = (r() * A.rows.loco[1]) | 0;
        cars.push({ kind: 'loco', var: lv, len: A.len.loco });
        const nc = freight ? 11 + ((r() * 5) | 0) : 7 + ((r() * 4) | 0), cv = (r() * A.rows.coach[1]) | 0, wv = (r() * A.rows.wagon[1]) | 0;
        for (let k = 0; k < nc; k++) cars.push(freight ? { kind: 'wagon', var: (k % 5 === 0 ? 1 - wv : wv), len: A.len.wagon } : { kind: 'coach', var: cv, len: A.len.coach });
        const total = cars.reduce((s, c) => s + c.len + GAP, 0);
        trains.push({ id: ++id, line: l, cars, total, freight, speed: freight ? FREIGHT_SPEED : TRAIN_SPEED, d: l.path.len * ((i + 0.37) / count), dir: i % 2 ? -1 : 1, wait: 0, lastStop: -1, x: 0, y: 0, sx: 0, sy: 0 });
      }
    });
  }
  function stepTrain(t, dt) {
    const l = t.line, len = l.path.len;
    if (t.wait > 0) { t.wait -= dt; return; }
    const nd = t.d + t.dir * t.speed * dt;
    if (!t.freight) {
      for (let i = 0; i < l.stations.length; i++) {
        const s = l.stations[i];
        if ((t.d - s.m) * (nd - s.m) <= 0 && t.lastStop !== i) { t.wait = DWELL; t.lastStop = i; t.d = s.m; return; }
        if (Math.abs(nd - s.m) > 200 && t.lastStop === i) t.lastStop = -1;
      }
    }
    t.d = nd;
    // the whole train has to clear the end before it turns round
    if (t.dir > 0 && t.d >= len - 5) { t.d = len - 5; t.dir = -1; t.lastStop = -1; t.wait = DWELL; }
    if (t.dir < 0 && t.d <= 5) { t.d = 5; t.dir = 1; t.lastStop = -1; t.wait = DWELL; }
  }
  function drawTrains(P) {
    const A = atlas.trains, cw = A.cell[0], chh = A.cell[1], ox = A.origin[0], oy = A.origin[1], N = A.headings;
    const q = [];
    for (const t of trains) {
      const p = t.line.path;
      let off = 0;
      for (let i = 0; i < t.cars.length; i++) {
        const c = t.cars[i];
        // cars trail behind the loco, which leads in the direction of travel
        const dist = t.d - t.dir * (off + c.len / 2);
        off += c.len + GAP;
        if (dist < 0 || dist > p.len) continue;
        const r = at(p, dist);
        const a = r[2] * t.dir, b = r[3] * t.dir;
        const hidden = t.line.occ.charCodeAt(r[5]) === 49;
        q.push(r[1], r[0], bucket(a, b, N), c, t, hidden);
      }
    }
    const n = q.length / 6, ord = []; for (let i = 0; i < n; i++) ord.push(i);
    ord.sort((i, j) => q[6 * i] - q[6 * j]);
    for (const i of ord) {
      const Y = q[6 * i], X = q[6 * i + 1], hd = q[6 * i + 2], c = q[6 * i + 3], t = q[6 * i + 4], hidden = q[6 * i + 5];
      if (c.kind === 'loco') { t.x = X; t.y = Y; t.sx = P.x + X * P.s; t.sy = P.y + Y * P.s; }
      if (hidden) continue;
      const row = A.rows[c.kind][0] + c.var;
      g.drawImage(tImg, hd * cw, row * chh, cw, chh, P.x + (X - ox) * P.s, P.y + (Y - oy) * P.s, cw * P.s, chh * P.s);
    }
    if (follow) { g.beginPath(); g.arc(follow.sx, follow.sy - 10 * P.s, Math.max(16, 22 * P.s), 0, 6.283); g.lineWidth = 2; g.strokeStyle = '#f0a23c'; g.stroke(); }
  }
  function drawStations(P, w, h) {
    if (P.s < 0.38) return;
    g.font = '600 12px ui-sans-serif, system-ui, "Noto Sans Tamil", sans-serif'; g.textBaseline = 'middle';
    const seen = new Set();
    for (const l of data.lines) for (const s of l.stations) {
      if (seen.has(s.name)) continue; seen.add(s.name);
      const sx = P.x + s.x * P.s, sy = P.y + s.y * P.s;
      if (sx < -60 || sy < -40 || sx > w + 60 || sy > h + 40) continue;
      const label = nameOf(s), tw = g.measureText(label).width;
      g.fillStyle = 'rgba(32,30,28,.88)'; g.fillRect(sx - tw / 2 - 7, sy - 40 * Math.min(1, P.s) - 10, tw + 14, 20);
      g.fillStyle = '#f4ead8'; g.textAlign = 'center'; g.fillText(label, sx, sy - 40 * Math.min(1, P.s)); g.textAlign = 'left';
      g.beginPath(); g.arc(sx, sy, 4, 0, 6.283); g.fillStyle = '#f0a23c'; g.fill(); g.lineWidth = 2; g.strokeStyle = '#2a1a05'; g.stroke();
    }
  }
  let data = null;
  const nameOf = s => (ctx.lang() === 'ta' && s.ta ? s.ta : s.name);

  // ------------------------------------------------------------------ frame
  function projector() {
    const b = ctx.base(), f = (x, y) => b.imageToViewerElementCoordinates(new OpenSeadragon.Point(x, y));
    const p0 = f(0, 0), p1 = f(1000, 0);
    return { s: (p1.x - p0.x) / 1000, x: p0.x, y: p0.y };
  }
  function fit() {
    const r = ctx.v.element.getBoundingClientRect(), dpr = window.devicePixelRatio || 1;
    const W = Math.round(r.width * dpr), H = Math.round(r.height * dpr);
    if (canvas.width !== W || canvas.height !== H) { canvas.width = W; canvas.height = H; }
    return dpr;
  }
  function frame(ts) {
    raf = requestAnimationFrame(frame);
    const dt = Math.min(0.1, (ts - (last || ts)) / 1000) * TIME; last = ts;
    T += dt;
    for (const t of trains) stepTrain(t, dt);
    if (follow) { ctx.v.viewport.panTo(ctx.px2vp(follow.x, follow.y - 10), true); updateBar(); }
    draw();
  }
  function draw() {
    const dpr = fit(), P = projector(), w = canvas.width / dpr, h = canvas.height / dpr;
    g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, w, h);
    if (!shown) return;
    g.imageSmoothingEnabled = false;
    // keep everything inside the city outline
    g.save();
    g.beginPath();
    for (let i = 0; i < clip.length; i++) { const x = P.x + clip[i][0] * P.s, y = P.y + clip[i][1] * P.s; if (i) g.lineTo(x, y); else g.moveTo(x, y); }
    g.closePath(); g.clip();
    let maxCls = -1; for (const [z, c] of LOD) if (P.s < z) { maxCls = c; break; }
    if (P.s >= 0.16) drawRoads(P, w, h, maxCls);
    drawTrains(P);
    g.restore();
    drawStations(P, w, h);
  }

  // ------------------------------------------------------------------ ride
  function nextStop(t) {
    const l = t.line, ahead = l.stations.filter(s => (t.dir > 0 ? s.m > t.d + 1 : s.m < t.d - 1));
    if (!ahead.length) return l.stations[t.dir > 0 ? l.stations.length - 1 : 0];
    return t.dir > 0 ? ahead[0] : ahead[ahead.length - 1];
  }
  function updateBar() {
    if (!follow) return;
    const s = nextStop(follow);
    // never rebuild the button: replacing it every frame swallows the click (mousedown and mouseup land on different nodes)
    const a = `${ctx.t('rideOn')}: ${follow.line.name}${follow.freight ? ' · freight' : ''}`, b = `→ ${nameOf(s)}${follow.wait > 0 ? ' •' : ''}`, c = ctx.t('rideStop');
    if (bar._a !== a) { bar._a = a; bar.$a.textContent = a; }
    if (bar._b !== b) { bar._b = b; bar.$b.textContent = b; }
    if (bar._c !== c) { bar._c = c; bar.$c.textContent = c; }
  }
  function startRide(t) { follow = t; bar.hidden = false; updateBar(); ctx.v.viewport.zoomTo(ctx.base().imageToViewportZoom(0.9)); }
  function stopRide() { follow = null; bar.hidden = true; }
  function click(pos) {
    if (!shown) return false;
    let best = null, bd = 30;
    for (const t of trains) { const d = Math.hypot(t.sx - pos.x, t.sy - pos.y); if (d < bd) { bd = d; best = t; } }
    if (best) { startRide(best); return true; }
    const P = projector();
    for (const l of data.lines) for (const s of l.stations) if (Math.hypot(P.x + s.x * P.s - pos.x, P.y + s.y * P.s - pos.y) < 18) { stopRide(); ctx.flyTo(s.x, s.y, 0.9); return true; }
    return false;
  }
  function set(on) {
    shown = on;
    const b = document.querySelector('[data-tool=rail]'); if (b) b.setAttribute('aria-pressed', on);
    if (!on) stopRide();
  }

  // ------------------------------------------------------------------ boot
  function init(c) {
    ctx = c;
    return Promise.all([getJson(c.urls.traffic), getJson(c.urls.transit), getJson(c.urls.atlas), getJson(c.urls.outline), img(c.urls.vehicles), img(c.urls.trains)]).then(([tr, tran, at_, ol, vi, ti]) => {
      atlas = at_; vImg = vi; tImg = ti; clip = ol.poly; data = tran; OCC_STEP = tr.step || 6;
      roads = tr.chains.map(ch => ({ c: ch.c, p: prep(ch.p), occ: ch.occ || '' }));
      buildTrains(tran);
      canvas = document.createElement('canvas');
      canvas.style.cssText = 'position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none;z-index:3;image-rendering:pixelated';
      document.getElementById('map').appendChild(canvas);
      g = canvas.getContext('2d');
      bar = document.createElement('div'); bar.className = 'ride-bar surface'; bar.hidden = true;
      bar.innerHTML = '<span class="r-a"></span><span class="r-b"></span><button type="button" class="btn btn-outline btn-sm r-stop"></button>';
      bar.$a = bar.querySelector('.r-a'); bar.$b = bar.querySelector('.r-b'); bar.$c = bar.querySelector('.r-stop');
      document.body.appendChild(bar);
      ['pointerdown', 'mousedown', 'dblclick', 'wheel'].forEach(ev => bar.addEventListener(ev, e => e.stopPropagation()));
      bar.$c.addEventListener('click', e => { e.stopPropagation(); stopRide(); });
      ctx.v.addHandler('canvas-drag', () => { if (follow) stopRide(); });
      document.addEventListener('visibilitychange', () => { last = 0; });
      raf = requestAnimationFrame(frame);
      return api;
    });
  }
  const api = { toggle: () => set(!shown), isOn: () => shown, debug: () => trains.map(t => ({ x: Math.round(t.x), y: Math.round(t.y), sx: t.sx, sy: t.sy, d: Math.round(t.d), dir: t.dir, kind: t.kind })), click, stop: () => { const was = !!follow; stopRide(); return was; }, refresh: () => { if (follow) updateBar(); } };
  window.pixelTraffic = { stop: () => (api.stop ? api.stop() : false), init, debug: () => (api.debug ? api.debug() : []), click: p => (api.click ? api.click(p) : false), refresh: () => api.refresh() };
})();
