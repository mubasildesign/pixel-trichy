// Pixel Trichy viewer: an OpenSeadragon deep-zoom map of Tiruchirappalli with places (pins, a carousel and a card),
// road labels, search, English | Tamil, share links (?lat=&lng=&zoom= or #place), focus mode, a minimap, an optional AI-art
// layer and an optional rail ride. Data: places.json, search.json (lazy), tiles/cover.json, optional ai_cover.json, transit.json.
(() => {
  const $ = (s, el = document) => el.querySelector(s);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const store = { get: k => { try { return localStorage.getItem(k); } catch { return null; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch {} } };

  // ------------------------------------------------------------------ language
  const TEXT = {
    en: {
      search: 'Search', places: 'Places', in: 'Zoom in', out: 'Zoom out', full: 'Full screen', layer: 'AI art', labels: 'Labels', share: 'Share',
      about: 'About', rail: 'Rail ride', lang: 'தமிழ்', langTip: 'Language: English. Switch to Tamil',
      tipSearch: 'Search (/)', tipPlaces: 'Places on this map (P)', tipFull: 'Full screen (F)', tipAbout: 'About this map',
      tipShare: 'Copy a link to this view', tipLabels: 'Show or hide road names (N)', tipRail: 'Show or hide moving traffic and trains. Click a train to ride it (M)',
      tipAi: 'Showing AI-painted areas. Switch to the plain drawing (L)', tipPlain: 'Showing the plain drawing. Switch to AI-painted areas (L)',
      searchPh: 'A place, a street or lat, long', searchLabel: 'Search the map', goCoords: 'Go to this spot', outside: 'Outside this map',
      covers: 'This map covers 10.72 to 10.95 N and 78.58 to 78.84 E', noMatch: 'No match. Try a place, a street or a position like 10.8283, 78.6972.',
      copied: 'Link copied', copyFailed: 'Could not copy. Press and hold the address bar to copy.', focusHint: 'Map only. Press H to bring the controls back.',
      hint: 'Drag to explore, scroll or pinch to zoom, and tap a pin to read about a place.',
      keysH: 'Keyboard', keys: [['/', 'Search'], ['P', 'Show or hide places'], ['[  ]', 'Previous or next place'], ['N', 'Road names'], ['M', 'Trains'], ['L', 'AI art'], ['H', 'Hide or show the controls'], ['F', 'Full screen']],
      close: 'Close', unchecked: 'Details not yet fact-checked.', mapLabel: 'Map of Tiruchirappalli. Drag to move, scroll or pinch to zoom.',
      Street: 'Street', Temple: 'Temple', Waterworks: 'Waterworks', Landmark: 'Landmark', Neighbourhood: 'Neighbourhood', Spot: 'Position', College: 'College',
      ridePick: 'Rail ride: click a train or a station', rideOn: 'Riding', rideStop: 'Stop', rideNone: 'Click a train to ride it.',
      credit: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="https://overturemaps.org/">Overture Maps</a>',
      aboutH: 'About this map',
      aboutIntro: 'Tiruchirappalli as one pixel-art map you can zoom right into, from Mukkombu in the west to Kallanai in the east, and from Samayapuram in the north to the airport and NIT in the south.',
      madeH: "How it's made",
      made1: 'Every building, road, river and tree starts from open data: Overture Maps (which includes OpenStreetMap and building footprints from Google and Microsoft) and its land-cover layer. A program draws that data as an isometric map. Building heights are mostly estimated from footprint size, because height data is thin for this city.',
      made2: 'The temple gopurams and the Rock are hand-placed, stylised models. Their heights are rounded and not survey data.',
      made3: 'Some areas also have an AI-painted layer, made with a local image model that repaints the plain drawing. The model invents small details such as signs and rooftop clutter, so those areas are labelled as AI art. Switch off AI art in the tools to see the plain drawing underneath.',
      thanks: 'Map data © OpenStreetMap contributors and Overture Maps Foundation.',
      submitted: 'Submitted to the Isometric Cities site.',
      cats: 'Places',
      memories: 'Memories', report: 'Report', tipMemories: 'Pin a memory on the map', tipReport: 'Report something wrong on the map', tipLang: 'Language',
      liveNow: '{n} here now', visitors: '{n} visitors', visitor1: '1 visitor', cancel: 'Cancel',
      madeA: 'Made with', madeB: 'for Trichy',
      memMode: 'Click a spot to pin a memory of it · Esc closes', memTitle: 'Pin a memory', memDesc: 'Share a short memory of this place. Everyone who opens the map can read it.',
      memText: 'Your memory', memPh: 'I used to buy sweets here after school…', memName: 'Your name (optional)', memNamePh: 'Name or initials', memSubmit: 'Pin it', memThanks: 'Memory pinned', memOutside: 'That spot is outside the map.', memHide: 'Hide memories',
      repTitle: 'Report a problem', repDesc: 'Found something wrong or missing on the map? Tell us where and what.', tabNew: 'New report', tabMine: 'My reports',
      repKind: 'What is it about?', kinds: { map: 'Wrong on the map', missing: 'Missing place', traffic: 'Traffic', seam: 'Seam or glitch', other: 'Other' },
      repWhere: 'Where', repHere: 'Map centre', repSpot: 'Spot you picked', repPick: 'Choose on map', repPickMsg: 'Click the spot with the problem · Esc cancels',
      repNote: 'What did you notice?', repNotePh: 'The road here is missing, a building looks wrong…', repSend: 'Send report', repSending: 'Sending…', repSent: 'Thanks, report sent', repShort: 'Write a few words first.', repFail: 'Could not send. Please try again.',
      mineDesc: 'What became of the faults you flagged. Only this browser sees this list.', mineEmpty: 'You have not sent any reports yet.', showOnMap: 'Show on map',
      status: { new: 'Still waiting: the map has not looked yet', seen: 'Seen: we are looking into it', fixed: 'Fixed: thanks for flagging it', wontfix: 'Reviewed: no change planned' },
    },
    ta: {
      search: 'தேடல்', places: 'இடங்கள்', in: 'பெரிதாக்கு', out: 'சிறிதாக்கு', full: 'முழுத்திரை', layer: 'AI ஓவியம்', labels: 'பெயர்கள்', share: 'பகிர்',
      about: 'பற்றி', rail: 'ரயில் பயணம்', lang: 'English', langTip: 'மொழி: தமிழ். ஆங்கிலத்துக்கு மாற',
      tipSearch: 'தேடல் (/)', tipPlaces: 'இந்த வரைபடத்தின் இடங்கள் (P)', tipFull: 'முழுத்திரை (F)', tipAbout: 'இந்த வரைபடம் பற்றி',
      tipShare: 'இந்தக் காட்சியின் இணைப்பைப் பகிர்', tipLabels: 'சாலைப் பெயர்களைக் காட்ட / மறைக்க (N)', tipRail: 'உண்மையான தண்டவாளங்களில் ரயில்கள் (M)',
      tipAi: 'AI ஓவியப் பகுதிகள் காட்டப்படுகின்றன. அடிப்படை வரைபடத்துக்கு மாற (L)', tipPlain: 'அடிப்படை வரைபடம் காட்டப்படுகிறது. AI ஓவியத்துக்கு மாற (L)',
      searchPh: 'இடம், தெரு, அட்ச-தீர்க்கம்', searchLabel: 'வரைபடத்தில் தேடு', goCoords: 'இந்த இடத்துக்குச் செல்', outside: 'இந்த வரைபடத்துக்கு வெளியே',
      covers: 'இது 10.72 முதல் 10.95° வ, 78.58 முதல் 78.84° கி வரை உள்ளடக்கும்', noMatch: 'பொருத்தம் இல்லை. ஓர் இடம், தெரு அல்லது 10.8283, 78.6972 போன்ற அட்ச தீர்க்க ரேகையை முயலவும்.',
      copied: 'இணைப்பு நகலெடுக்கப்பட்டது', copyFailed: 'நகலெடுக்க முடியவில்லை. முகவரிப் பட்டியை அழுத்திப் பிடித்து நகலெடுக்கவும்.', focusHint: 'வரைபடம் மட்டும். கட்டுப்பாடுகளைத் திரும்பப் பெற H அழுத்தவும்.',
      hint: 'நகர்த்த இழுக்கவும்; பெரிதாக்க உருட்டவும் அல்லது கிள்ளவும்; ஓர் இடத்தைப் பற்றி அறிய குறியைத் தொடவும்.',
      keysH: 'விசைப்பலகை', keys: [['/', 'தேடல்'], ['P', 'இடங்களைக் காட்ட / மறைக்க'], ['[  ]', 'முந்தைய / அடுத்த இடம்'], ['N', 'சாலைப் பெயர்கள்'], ['M', 'ரயில்கள்'], ['L', 'AI ஓவியம்'], ['H', 'கட்டுப்பாடுகளை மறைக்க / காட்ட'], ['F', 'முழுத்திரை']],
      close: 'மூடு', unchecked: 'விவரங்கள் இன்னும் சரிபார்க்கப்படவில்லை.', mapLabel: 'திருச்சிராப்பள்ளி வரைபடம். நகர்த்த இழுக்கவும், பெரிதாக்க உருட்டவும் அல்லது கிள்ளவும்.',
      Street: 'தெரு', Temple: 'கோயில்', Waterworks: 'நீர்ப்பணி', Landmark: 'அடையாளம்', Neighbourhood: 'பகுதி', Spot: 'இடம்', College: 'கல்லூரி',
      ridePick: 'ரயில் பயணம்: ஒரு ரயிலையோ நிலையத்தையோ தொடவும்', rideOn: 'பயணம்', rideStop: 'நிறுத்து', rideNone: 'பயணிக்க வரைபடத்தில் ஒரு ரயிலைத் தொடவும்.',
      credit: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> பங்களிப்பாளர்கள், <a href="https://overturemaps.org/">Overture Maps</a>',
      aboutH: 'இந்த வரைபடம் பற்றி',
      aboutIntro: 'திருச்சிராப்பள்ளி முழுவதும் ஒரே பிக்சல் ஓவிய வரைபடமாக. மேற்கே முக்கொம்பு முதல் கிழக்கே கல்லணை வரை, வடக்கே சமயபுரம் முதல் தெற்கே விமான நிலையம், என்ஐடி வரை பெரிதாக்கிப் பார்க்கலாம்.',
      madeH: 'எப்படி உருவானது',
      made1: 'ஒவ்வொரு கட்டடமும் சாலையும் ஆறும் மரமும் திறந்த தரவிலிருந்து தொடங்குகிறது: Overture Maps (இதில் OpenStreetMap மற்றும் Google, Microsoft கட்டட அடித்தடங்கள் அடங்கும்) மற்றும் நிலப்போர்வை அடுக்கு. ஒரு நிரல் அந்தத் தரவை ஐசோமெட்ரிக் வரைபடமாக வரைகிறது. இந்த நகருக்கு உயரத் தரவு குறைவு என்பதால், கட்டட உயரங்கள் பெரும்பாலும் அடித்தட அளவிலிருந்து மதிப்பிடப்பட்டவை.',
      made2: 'கோயில் கோபுரங்களும் மலைக்கோட்டையும் கையால் வைக்கப்பட்ட, பாணியாக்கப்பட்ட மாதிரிகள். அவற்றின் உயரங்கள் தோராயமானவை; அளவீட்டுத் தரவு அல்ல.',
      made3: 'சில பகுதிகளுக்கு AI ஓவிய அடுக்கும் உண்டு. அடிப்படை வரைபடத்தை மீண்டும் வரையும் உள்ளூர் பட மாதிரியால் உருவானது. பலகைகள், மொட்டைமாடிப் பொருட்கள் போன்ற சிறு விவரங்களை மாதிரி கற்பனை செய்வதால் அவை AI ஓவியம் என்று குறிக்கப்படுகின்றன. அடியில் உள்ள எளிய வரைபடத்தைப் பார்க்க, கருவிகளில் AI ஓவியத்தை அணைக்கவும்.',
      thanks: 'வரைபடத் தரவு © OpenStreetMap பங்களிப்பாளர்கள் மற்றும் Overture Maps Foundation.',
      submitted: 'Isometric Cities தளத்துக்குச் சமர்ப்பிக்கப்பட்டது.',
      cats: 'இடங்கள்',
      memories: 'நினைவுகள்', report: 'புகார்', tipMemories: 'வரைபடத்தில் ஒரு நினைவைப் பதியுங்கள்', tipReport: 'வரைபடத்தில் உள்ள பிழையைத் தெரிவியுங்கள்', tipLang: 'மொழி',
      liveNow: '{n} பேர் இப்போது இங்கே', visitors: '{n} பார்வையாளர்கள்', visitor1: '1 பார்வையாளர்', cancel: 'ரத்து',
      madeA: 'அன்புடன்', madeB: 'திருச்சிக்காக',
      memMode: 'நினைவைப் பதிய ஓர் இடத்தைத் தொடவும் · மூட Esc', memTitle: 'ஒரு நினைவைப் பதியுங்கள்', memDesc: 'இந்த இடத்தைப் பற்றிய சிறு நினைவைப் பகிருங்கள். வரைபடத்தைத் திறக்கும் அனைவரும் இதைப் படிக்கலாம்.',
      memText: 'உங்கள் நினைவு', memPh: 'பள்ளி முடிந்ததும் இங்கே இனிப்பு வாங்குவேன்…', memName: 'உங்கள் பெயர் (விருப்பம்)', memNamePh: 'பெயர் அல்லது முதலெழுத்துகள்', memSubmit: 'பதி', memThanks: 'நினைவு பதியப்பட்டது', memOutside: 'அந்த இடம் வரைபடத்துக்கு வெளியே உள்ளது.', memHide: 'நினைவுகளை மறை',
      repTitle: 'ஒரு சிக்கலைத் தெரிவியுங்கள்', repDesc: 'வரைபடத்தில் ஏதேனும் தவறு அல்லது விடுபாடு இருக்கிறதா? எங்கே, என்ன என்று சொல்லுங்கள்.', tabNew: 'புதிய புகார்', tabMine: 'என் புகார்கள்',
      repKind: 'எதைப் பற்றியது?', kinds: { map: 'வரைபடத்தில் தவறு', missing: 'விடுபட்ட இடம்', traffic: 'போக்குவரத்து', seam: 'இணைப்புக் கோடு / குறைபாடு', other: 'மற்றவை' },
      repWhere: 'எங்கே', repHere: 'வரைபட மையம்', repSpot: 'நீங்கள் தேர்ந்த இடம்', repPick: 'வரைபடத்தில் தேர்வு', repPickMsg: 'சிக்கல் உள்ள இடத்தைத் தொடவும் · ரத்து செய்ய Esc',
      repNote: 'என்ன கவனித்தீர்கள்?', repNotePh: 'இங்கே சாலை இல்லை, ஒரு கட்டடம் தவறாகத் தெரிகிறது…', repSend: 'புகாரை அனுப்பு', repSending: 'அனுப்புகிறது…', repSent: 'நன்றி, புகார் அனுப்பப்பட்டது', repShort: 'முதலில் சில சொற்கள் எழுதுங்கள்.', repFail: 'அனுப்ப முடியவில்லை. மீண்டும் முயலுங்கள்.',
      mineDesc: 'நீங்கள் தெரிவித்த குறைகளுக்கு என்ன ஆனது. இந்தப் பட்டியலை இந்த உலாவி மட்டுமே காணும்.', mineEmpty: 'நீங்கள் இன்னும் புகார் எதுவும் அனுப்பவில்லை.', showOnMap: 'வரைபடத்தில் காட்டு',
      status: { new: 'இன்னும் காத்திருக்கிறது: வரைபடம் இன்னும் பார்க்கவில்லை', seen: 'பார்க்கப்பட்டது: ஆராய்கிறோம்', fixed: 'சரிசெய்யப்பட்டது: தெரிவித்ததற்கு நன்றி', wontfix: 'பரிசீலிக்கப்பட்டது: மாற்றம் இல்லை' },
    },
  };
  const qs = new URLSearchParams(location.search);
  let lang = qs.get('lang') || store.get('pt-lang') || ((navigator.language || '').startsWith('ta') ? 'ta' : 'en');
  if (!TEXT[lang]) lang = 'en';
  const t = k => (TEXT[lang][k] ?? TEXT.en[k] ?? k);

  // ------------------------------------------------------------------ boot
  const cfgUrl = document.currentScript.dataset.config || 'config.json';
  const getJson = u => fetch(u).then(r => { if (!r.ok) throw new Error(u + ' ' + r.status); return r.json(); });
  const maybeJson = u => fetch(u).then(r => (r.ok ? r.json() : null)).catch(() => null);

  getJson(cfgUrl).then(async CFG => {
    const vq = CFG.ver ? '?v=' + CFG.ver : '';
    const [D, cover, aiCover] = await Promise.all([getJson(CFG.data + vq), getJson(CFG.cover + vq), CFG.aiCover ? maybeJson(CFG.aiCover + vq) : null]);
    start(CFG, D, cover, aiCover);
  }).catch(err => { console.error(err); document.body.insertAdjacentHTML('beforeend', '<div class="toast on">Could not load the map data.</div>'); });

  function start(CFG, D, cover, aiCover) {
    const G = D.geo;
    const places = D.places;
    const nm = p => (lang === 'ta' && p.ta ? p.ta : p.name);

    // lat/lon <-> deepest-level pixels (same maths as pipeline/config.py)
    const isoOf = (lon, lat) => { const x = (lon - G.lon0) * G.mLon, y = (lat - G.lat0) * G.mLat; return [(x - y) * G.k - G.x0, -(x + y) * G.k / 2 - G.y0]; };
    const lonLatOf = (px, py) => { const d = (px + G.x0) / G.k, s = -2 * (py + G.y0) / G.k; return [G.lon0 + ((s + d) / 2) / G.mLon, G.lat0 + ((s - d) / 2) / G.mLat]; };
    const inBox = (lat, lon) => lat >= G.bbox.south && lat <= G.bbox.north && lon >= G.bbox.west && lon <= G.bbox.east;

    // ---------------------------------------------------------------- viewer and tile sources
    const ver = CFG.ver ? '?v=' + CFG.ver : ''; // bump in config.json whenever tiles are re-rendered, so CDN and browser caches miss
    function tileSource(url, cv) {
      const max = cv.level, rows = cv.rows;
      const exact = cv.tiles ? Object.fromEntries(Object.entries(cv.tiles).map(([l, a]) => [l, new Set(a)])) : null; // sparse layers list every tile
      return new OpenSeadragon.TileSource({
        width: cv.width, height: cv.height, tileSize: cv.px, tileOverlap: 0, minLevel: 0, maxLevel: max,
        getTileUrl: (l, x, y) => `${url}${l}/${x}_${y}.webp${ver}`,
        tileExists: (l, x, y) => {
          if (exact) return !!(exact[l] && exact[l].has(x + '_' + y));
          const sc = 2 ** (max - l), c0 = x * sc, c1 = c0 + sc - 1;
          for (let r = y * sc; r < (y + 1) * sc && r < rows.length; r++) {
            const row = rows[r]; // [first, last, first, last, ...] runs of rendered columns
            for (let i = 0; i < row.length; i += 2) if (row[i] <= c1 && row[i + 1] >= c0) return true;
          }
          return false;
        },
      });
    }
    const v = OpenSeadragon({
      element: $('#map'), showNavigationControl: false, prefixUrl: '', animationTime: 1.1, springStiffness: 7, blendTime: 0.15,
      maxZoomPixelRatio: 3, minZoomImageRatio: 1, visibilityRatio: 1, constrainDuringPan: true, imageLoaderLimit: 6,
      gestureSettingsMouse: { clickToZoom: false, dblClickToZoom: true }, gestureSettingsTouch: { pinchRotate: false },
      crossOriginPolicy: 'Anonymous', homeFillsViewer: false, preserveImageSizeOnResize: true, background: '#201e1c',
    });
    const W = cover.width;
    let aiItem = null, aiOn = store.get('pt-ai') !== 'off', baseItem = null;
    // blurred countryside under the city (tiles are transparent outside the outline), same extent as the base image
    if (CFG.land) v.addTiledImage({ tileSource: { type: 'image', url: CFG.land + ver, buildPyramid: false }, x: 0, y: 0, width: 1, index: 0 });
    v.addTiledImage({ tileSource: tileSource(CFG.base, cover), x: 0, y: 0, width: 1, success: e => { baseItem = e.item; onReady(); } });
    if (aiCover && aiCover.rows && aiCover.rows.some(r => r.length)) {
      v.addTiledImage({ tileSource: tileSource(CFG.ai, aiCover), x: 0, y: 0, width: 1, opacity: aiOn ? 1 : 0, success: e => { aiItem = e.item; syncLayerTool(); } });
    }

    const base = () => baseItem;
    const px2vp = (x, y) => base().imageToViewportCoordinates(x, y);
    const imgZoom = () => base().viewportToImageZoom(v.viewport.getZoom(true));
    const centerPx = () => { const c = v.viewport.getCenter(true); const p = base().viewportToImageCoordinates(c); return [p.x, p.y]; };

    // ---------------------------------------------------------------- toast + helpers
    const toastEl = $('.toast');
    let toastT;
    function toast(msg) { toastEl.textContent = msg; toastEl.classList.add('on'); clearTimeout(toastT); toastT = setTimeout(() => toastEl.classList.remove('on'), 2600); }

    // ---------------------------------------------------------------- tools (lucide icons, shadcn-style buttons)
    const ICON = {
      places: '<path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/>',
      in: '<path d="M5 12h14"/><path d="M12 5v14"/>', out: '<path d="M5 12h14"/>',
      layer: '<path d="M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83z"/><path d="M2 12a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 12"/><path d="M2 17a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 17"/>',
      labels: '<path d="M12.586 2.586A2 2 0 0 0 11.172 2H4a2 2 0 0 0-2 2v7.172a2 2 0 0 0 .586 1.414l8.704 8.704a2.426 2.426 0 0 0 3.42 0l6.58-6.58a2.426 2.426 0 0 0 0-3.42z"/><circle cx="7.5" cy="7.5" r=".5" fill="currentColor"/>',
      rail: '<path d="m21 8-2 2-1.5-3.7A2 2 0 0 0 15.646 5H8.4a2 2 0 0 0-1.903 1.257L5 10 3 8"/><path d="M7 14h.01"/><path d="M17 14h.01"/><rect width="18" height="8" x="3" y="10" rx="2"/><path d="M5 18v2"/><path d="M19 18v2"/>',
      share: '<circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" x2="15.42" y1="13.51" y2="17.49"/><line x1="15.41" x2="8.59" y1="6.51" y2="10.49"/>',
      full: '<path d="M8 3H5a2 2 0 0 0-2 2v3"/><path d="M21 8V5a2 2 0 0 0-2-2h-3"/><path d="M3 16v3a2 2 0 0 0 2 2h3"/><path d="M16 21h3a2 2 0 0 0 2-2v-3"/>',
      about: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
      memories: '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>',
      report: '<path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z"/><line x1="4" x2="4" y1="22" y2="15"/>',
      x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
      crosshair: '<circle cx="12" cy="12" r="10"/><line x1="22" x2="18" y1="12" y2="12"/><line x1="6" x2="2" y1="12" y2="12"/><line x1="12" x2="12" y1="6" y2="2"/><line x1="12" x2="12" y1="22" y2="18"/>',
      left: '<path d="m15 18-6-6 6-6"/>', right: '<path d="m9 18 6-6-6-6"/>',
    };
    const svg = (id, cls = '') => `<svg class="i ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICON[id]}</svg>`;
    const railL = $('.rail-left'), railR = $('.rail-right'), util = $('.util');
    const tools = {};
    const addTool = (id, onClick, opts = {}) => {
      const b = document.createElement('button');
      b.type = 'button'; b.dataset.tool = id; if (opts.pressed !== undefined) b.setAttribute('aria-pressed', opts.pressed);
      b.className = 'btn btn-ghost ' + (opts.txt ? 'txt' : 'btn-icon');
      b.innerHTML = svg(id) + (opts.txt ? '<span class="lbl"></span>' : '');
      b.addEventListener('click', onClick); (opts.to || railR).appendChild(b); tools[id] = b; if (opts.hidden) b.hidden = true; return b;
    };
    const sep = (to = railR) => { const s = document.createElement('span'); s.className = 'sep'; to.appendChild(s); };
    // left rail: the things you do on the map
    addTool('places', () => togglePlaces(), { pressed: false, txt: true, to: railL });
    addTool('memories', () => toggleMemories(), { pressed: false, txt: true, hidden: true, to: railL });
    addTool('report', () => openReport(), { txt: true, hidden: true, to: railL });
    // right rail: how you look at the map
    addTool('in', () => v.viewport.zoomBy(1.8).applyConstraints());
    addTool('out', () => v.viewport.zoomBy(1 / 1.8).applyConstraints());
    addTool('full', () => toggleFull());
    sep();
    addTool('layer', () => setAi(!aiOn), { pressed: aiOn, hidden: true });
    addTool('labels', () => setLabels(!labelsOn), { pressed: true });
    addTool('rail', () => traffic().then(r => r.toggle()).catch(e => { trafficJs = null; console.warn(e); }), { pressed: true, hidden: true });
    sep();
    addTool('share', () => share());
    // top right: language and about
    const langSeg = document.createElement('div');
    langSeg.className = 'seg'; langSeg.setAttribute('role', 'group');
    langSeg.innerHTML = '<button type="button" data-lang="en">EN</button><button type="button" data-lang="ta" lang="ta">தமிழ்</button>';
    langSeg.addEventListener('click', e => { const b = e.target.closest('button'); if (b && b.dataset.lang !== lang) setLang(b.dataset.lang); });
    util.appendChild(langSeg);
    addTool('about', () => openAbout(), { to: util });
    function syncTitles() {
      const tip = { places: 'tipPlaces', memories: 'tipMemories', report: 'tipReport', labels: 'tipLabels', rail: 'tipRail', full: 'tipFull', share: 'tipShare', about: 'tipAbout', in: 'in', out: 'out', layer: aiOn ? 'tipAi' : 'tipPlain' };
      for (const [id, k] of Object.entries(tip)) { tools[id].dataset.tip = t(k).replace(/ \(.\)$/, ''); tools[id].setAttribute('aria-label', t(k)); }
      for (const id of ['places', 'memories', 'report']) $('.lbl', tools[id]).textContent = t(id);
      langSeg.dataset.tip = t('tipLang'); langSeg.setAttribute('aria-label', t('tipLang'));
      $$('button', langSeg).forEach(b => b.setAttribute('aria-pressed', b.dataset.lang === lang));
    }
    function syncLayerTool() { tools.layer.hidden = !aiItem; tools.layer.setAttribute('aria-pressed', aiOn); syncTitles(); }
    function setAi(on) { aiOn = on; store.set('pt-ai', on ? 'on' : 'off'); if (aiItem) aiItem.setOpacity(on ? 1 : 0); syncLayerTool(); }
    function toggleFull() {
      const el = document.documentElement;
      if (document.fullscreenElement) document.exitFullscreen(); else if (el.requestFullscreen) el.requestFullscreen().catch(() => {});
    }

    // ---------------------------------------------------------------- places: pins, strip, dock
    const pins = new Map();
    for (const p of places) {
      const el = document.createElement('div');
      el.className = 'pin'; el.dataset.cat = p.cat; el.setAttribute('role', 'button'); el.tabIndex = 0;
      el.innerHTML = `<b>${p.n}</b><span class="tag"></span>`;
      el.addEventListener('click', e => { e.stopPropagation(); openPlace(p, true); });
      el.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openPlace(p, true); } });
      pins.set(p.slug, el);
    }
    function addPinOverlays() {
      for (const p of places) {
        v.addOverlay({ element: pins.get(p.slug), location: px2vp(p.x, p.y), placement: OpenSeadragon.Placement.BOTTOM, checkResize: false });
      }
    }
    const strip = $('.strip'), stripWrap = $('.stripwrap'), dock = $('.dock');
    $('.sarrow.l', stripWrap).addEventListener('click', () => strip.scrollBy({ left: -Math.max(260, strip.clientWidth * 0.7), behavior: 'smooth' }));
    $('.sarrow.r', stripWrap).addEventListener('click', () => strip.scrollBy({ left: Math.max(260, strip.clientWidth * 0.7), behavior: 'smooth' }));
    const step = d => { const i = cur ? places.findIndex(q => q.slug === cur.slug) : -1; openPlace(places[(i + d + places.length) % places.length], true); };
    let cur = null;
    function renderStrip() {
      const cats = D.cats;
      let html = '';
      let last = '';
      for (const p of places) {
        if (p.cat !== last) { last = p.cat; html += `<span class="cats" data-cat="${p.cat}">${esc(cats[p.cat][lang === 'ta' ? 1 : 0])}</span>`; }
        html += `<button class="card${cur && cur.slug === p.slug ? ' on' : ''}" data-slug="${p.slug}" data-cat="${p.cat}"><img src="${p.img}${ver}" alt="" loading="lazy"><i class="n">${p.n}</i><span class="t">${esc(nm(p))}</span><span class="t2" lang="${lang === 'ta' ? 'en' : 'ta'}">${esc(lang === 'ta' ? p.name : p.ta)}</span></button>`;
      }
      strip.innerHTML = html;
      pins.forEach((el, slug) => { const p = places.find(q => q.slug === slug); $('.tag', el).textContent = nm(p); el.title = nm(p); el.setAttribute('aria-label', nm(p)); el.classList.toggle('on', !!cur && cur.slug === slug); });
    }
    strip.addEventListener('click', e => { const c = e.target.closest('.card'); if (c) openPlace(places.find(p => p.slug === c.dataset.slug), true); });
    const syncStack = () => document.documentElement.style.setProperty('--stack', stripWrap.hidden ? '0px' : (stripWrap.offsetHeight + 8) + 'px');
    if (window.ResizeObserver) new ResizeObserver(syncStack).observe(stripWrap);
    function togglePlaces(force) {
      const on = force ?? stripWrap.hidden;
      stripWrap.hidden = !on; syncStack(); document.body.classList.toggle('strip-on', on); tools.places.setAttribute('aria-pressed', on);
      if (on) { renderStrip(); const c = $('.card.on', strip); if (c) c.scrollIntoView({ inline: 'center', block: 'nearest' }); }
    }
    function renderDock() {
      if (!cur) { dock.hidden = true; return; }
      const p = cur;
      const i = places.findIndex(q => q.slug === p.slug), prev = places[(i - 1 + places.length) % places.length], next = places[(i + 1) % places.length];
      dock.dataset.cat = p.cat;
      dock.innerHTML = `<button class="x btn btn-icon-sm" aria-label="${t('close')}">${svg('x')}</button><img src="${p.img}${ver}" alt="">
        <div class="body"><div class="meta"><span class="num">${p.n}</span><span class="area">${esc(D.cats[p.cat][lang === 'ta' ? 1 : 0])} · ${esc(p.area)}</span></div>
        <h2>${esc(nm(p))}</h2><div class="ta" lang="${lang === 'ta' ? 'en' : 'ta'}">${esc(lang === 'ta' ? p.name : p.ta)}</div><p>${esc(p.blurb)}</p>
        ${p.checked ? '' : `<div class="unchecked">${t('unchecked')}</div>`}
        <div class="step"><button class="prev btn btn-ghost btn-sm" aria-label="${esc(nm(prev))}">${svg('left')}<span>${esc(nm(prev))}</span></button><button class="next btn btn-ghost btn-sm" aria-label="${esc(nm(next))}"><span>${esc(nm(next))}</span>${svg('right')}</button></div></div>`;
      dock.hidden = false;
      $('.x', dock).addEventListener('click', closeDock);
      $('.prev', dock).addEventListener('click', () => step(-1)); $('.next', dock).addEventListener('click', () => step(1));
    }
    function closeDock() { cur = null; dock.hidden = true; pins.forEach(el => el.classList.remove('on')); $$('.card', strip).forEach(c => c.classList.remove('on')); history.replaceState(null, '', location.pathname + location.search); clearSpot(); }
    function $$(s, el = document) { return [...el.querySelectorAll(s)]; }
    function openPlace(p, fly) {
      cur = p; if (stripWrap.hidden) togglePlaces(true); renderDock(); renderStrip();
      if (!stripWrap.hidden) { const c = $(`.card[data-slug="${p.slug}"]`, strip); if (c) c.scrollIntoView({ inline: 'center', block: 'nearest', behavior: 'smooth' }); }
      history.replaceState(null, '', '#' + p.slug);
      if (fly) flyTo(p.x, p.y, 0.8); else jumpTo(p.x, p.y, 0.8);
    }
    function flyTo(x, y, ratio, immediately) {
      const z = base().imageToViewportZoom(ratio);
      v.viewport.zoomTo(z, null, immediately); v.viewport.panTo(px2vp(x, y), immediately);
    }
    const jumpTo = (x, y, r) => flyTo(x, y, r, true);

    // ---------------------------------------------------------------- spot marker (search by position)
    let spotEl = null;
    function setSpot(x, y) {
      clearSpot(); spotEl = document.createElement('div'); spotEl.className = 'spot';
      v.addOverlay({ element: spotEl, location: px2vp(x, y), placement: OpenSeadragon.Placement.CENTER, checkResize: false });
    }
    function clearSpot() { if (spotEl) { v.removeOverlay(spotEl); spotEl = null; } }

    // ---------------------------------------------------------------- road labels
    let labelsOn = store.get('pt-labels') !== 'off';
    function addLabels() {
      for (const r of D.roads) {
        const el = document.createElement('div');
        el.innerHTML = `<span class="road-label r${r.r}" style="display:inline-block;transform:rotate(${r.a}deg)">${esc(r.name)}</span>`;
        v.addOverlay({ element: el, location: px2vp(r.x, r.y), placement: OpenSeadragon.Placement.CENTER, checkResize: false });
      }
    }
    function setLabels(on) { labelsOn = on; store.set('pt-labels', on ? 'on' : 'off'); document.body.classList.toggle('no-labels', !on); tools.labels.setAttribute('aria-pressed', on); }
    const style = document.createElement('style');
    // road names only once you are zoomed into streets; the overview stays clean
    style.textContent = 'body:not(.zoom-far) .road-label, body:not(.zoom-mid) .road-label.r2, body:not(.zoom-mid) .road-label.r3, body:not(.zoom-near) .road-label.r3 { display: none !important; }';
    document.head.appendChild(style);
    function zoomClasses() {
      const z = imgZoom(), b = document.body.classList;
      b.toggle('zoom-far', z > 0.32); b.toggle('zoom-mid', z > 0.5); b.toggle('zoom-near', z > 0.8);
      b.toggle('zoom-overview', z < 0.09);
    }

    // ---------------------------------------------------------------- city border and name (vector, crisp at every zoom)
    const NS = 'http://www.w3.org/2000/svg';
    const borderSvg = document.createElementNS(NS, 'svg');
    borderSvg.setAttribute('class', 'border-svg'); borderSvg.setAttribute('aria-hidden', 'true');
    const borderG = document.createElementNS(NS, 'g');
    borderSvg.appendChild(borderG);
    let borderReady = false;
    function addBorder(poly) {
      const d = 'M' + poly.map(p => p[0] + ' ' + p[1]).join('L') + 'Z';
      for (const cls of ['glow', 'edge']) { const p = document.createElementNS(NS, 'path'); p.setAttribute('d', d); p.setAttribute('class', 'b-' + cls); borderG.appendChild(p); }
      v.canvas.insertBefore(borderSvg, v.canvas.children[1] || null); borderReady = true; drawBorder();
    }
    function drawBorder() {
      if (!borderReady || !base()) return;
      const f = (x, y) => base().imageToViewerElementCoordinates(new OpenSeadragon.Point(x, y));
      const p0 = f(0, 0), p1 = f(10000, 0), s = (p1.x - p0.x) / 10000;
      borderG.setAttribute('transform', `translate(${p0.x} ${p0.y}) scale(${s})`);
    }
    const cityName = document.createElement('div');
    cityName.className = 'city-name';
    function placeCityName() {
      const ol = D.outline;
      if (!ol) return;
      cityName.innerHTML = `<span class="cn-en">TIRUCHIRAPPALLI</span><span class="cn-ta" lang="ta">திருச்சிராப்பள்ளி</span>`;
      v.addOverlay({ element: cityName, location: px2vp(ol.label[0], ol.label[1]), placement: OpenSeadragon.Placement.CENTER, checkResize: false });
    }

    // ---------------------------------------------------------------- search
    const form = $('.search'), input = $('#q'), results = $('#results');
    let rows = null, sel = -1, shown = [];
    const loadRows = () => rows ? Promise.resolve(rows) : getJson(CFG.search + (CFG.ver ? '?v=' + CFG.ver : '')).then(r => (rows = r)).catch(() => (rows = []));
    const norm = s => String(s).toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '');
    function search(q) {
      q = q.trim();
      if (!q) return [];
      const m = q.match(/^(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)$/);
      if (m) { const lat = +m[1], lon = +m[2]; return [{ coord: true, lat, lon, ok: inBox(lat, lon) }]; }
      const n = norm(q), out = [];
      for (const r of rows || []) {
        const name = norm(r[0]), ta = r[6] || '';
        let s = -1;
        if (name === n) s = 0; else if (name.startsWith(n)) s = 1; else if (name.split(/\s+/).some(w => w.startsWith(n))) s = 2; else if (name.includes(n)) s = 3; else if (ta && ta.includes(q)) s = 2;
        else if (n.length >= 4 && norm(r[3]).startsWith(n.replace(/s$/, ''))) s = 4;   // "college", "colleges", "temple" list that kind
        if (s >= 0) out.push([s + (r[7] ? 0 : 0.5), r]);
      }
      out.sort((a, b) => a[0] - b[0] || a[1][0].length - b[1][0].length);
      return out.slice(0, 10).map(o => o[1]);
    }
    function renderResults(list, q) {
      shown = list; sel = list.length ? 0 : -1;
      if (!q.trim()) { results.hidden = true; return; }
      let html = '';
      for (let i = 0; i < list.length; i++) {
        const r = list[i];
        if (r.coord) { html += r.ok ? `<button class="row${i === sel ? ' on' : ''}" data-i="${i}" role="option"><span>${r.lat.toFixed(4)}, ${r.lon.toFixed(4)}</span><small>${t('goCoords')}</small></button>` : `<div class="none">${t('outside')}. ${t('covers')}</div>`; continue; }
        const label = lang === 'ta' && r[6] ? r[6] : r[0];
        html += `<button class="row${i === sel ? ' on' : ''}" data-i="${i}" role="option"><span>${esc(label)}</span><small>${esc(t(r[3]))}</small></button>`;
      }
      results.innerHTML = html || `<div class="none">${t('noMatch')}</div>`;
      results.hidden = false;
    }
    function pick(i) {
      const r = shown[i]; if (!r) return;
      closeSearch(true);
      if (r.coord) { if (!r.ok) return; const [x, y] = isoOf(r.lon, r.lat); setSpot(x, y); flyTo(x, y, 1.0); return; }
      const p = r[7] && places.find(q => q.slug === r[7]);
      if (p) { openPlace(p, true); return; }
      closeDock(); setSpot(r[1], r[2]); flyTo(r[1], r[2], 0.7);
    }
    function closeSearch(clear) { results.hidden = true; if (clear) input.value = ''; input.blur(); }
    input.addEventListener('focus', () => loadRows());
    input.addEventListener('input', () => loadRows().then(() => renderResults(search(input.value), input.value)));
    form.addEventListener('submit', e => { e.preventDefault(); if (shown.length) pick(Math.max(sel, 0)); });
    results.addEventListener('mousedown', e => { const b = e.target.closest('.row'); if (b) { e.preventDefault(); pick(+b.dataset.i); } });
    input.addEventListener('keydown', e => {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault(); if (!shown.length) return; sel = (sel + (e.key === 'ArrowDown' ? 1 : -1) + shown.length) % shown.length;
        $$('.row', results).forEach((r, i) => r.classList.toggle('on', i === sel));
      } else if (e.key === 'Escape') closeSearch(true);
    });
    input.addEventListener('blur', () => setTimeout(() => (results.hidden = true), 120));

    // ---------------------------------------------------------------- share
    function viewUrl() {
      const u = location.origin + location.pathname;
      if (cur) return u + '#' + cur.slug;
      const [x, y] = centerPx(); const [lon, lat] = lonLatOf(x, y);
      return `${u}?lat=${lat.toFixed(5)}&lng=${lon.toFixed(5)}&zoom=${imgZoom().toFixed(2)}${lang === 'ta' ? '&lang=ta' : ''}`;
    }
    function share() {
      const url = viewUrl();
      if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(url).then(() => toast(t('copied')), () => toast(t('copyFailed')));
      else { const ta = document.createElement('textarea'); ta.value = url; document.body.appendChild(ta); ta.select(); let ok = false; try { ok = document.execCommand('copy'); } catch {} ta.remove(); toast(ok ? t('copied') : t('copyFailed')); }
    }

    // ---------------------------------------------------------------- dialogs (shadcn Dialog), mode bar
    let dlgOv = null, dlgClose = null, dlgReopen = null;
    function dialog(html, opts = {}) {
      closeDialog(true);
      const ov = document.createElement('div');
      ov.className = 'dlg-ov';
      ov.innerHTML = `<div class="dlg${opts.wide ? ' wide' : ''}" role="dialog" aria-modal="true">${html}<button type="button" class="dlg-x btn btn-ghost btn-icon-sm" aria-label="${t('close')}">${svg('x')}</button></div>`;
      ov.addEventListener('mousedown', e => { if (e.target === ov) closeDialog(); });
      $('.dlg-x', ov).addEventListener('click', () => closeDialog());
      $$('[data-close]', ov).forEach(b => b.addEventListener('click', () => closeDialog()));
      document.body.appendChild(ov); dlgOv = ov; dlgClose = opts.onClose || null; dlgReopen = opts.reopen || null;
      const f = $(opts.focus || 'textarea, input, .btn-primary', ov); if (f) setTimeout(() => f.focus(), 30);
      return ov;
    }
    function closeDialog(silent) {
      if (!dlgOv) return;
      dlgOv.remove(); dlgOv = null; const c = dlgClose; dlgClose = null; dlgReopen = null;
      if (c && !silent) c();
    }

    const modebar = $('.modebar');
    let mode = null;       // 'memory' | 'pick'
    function setMode(m, msg, onPick) {
      mode = m ? { m, onPick } : null;
      document.body.classList.toggle('adding', !!m); modebar.hidden = !m;
      if (m) { $('.modebar-msg', modebar).textContent = msg; }
      if (!m) { tools.memories.setAttribute('aria-pressed', memOn); }
    }
    $('.btn', modebar).addEventListener('click', () => exitMode());
    function exitMode() {
      if (!mode) return;
      if (mode.m === 'memory') { toggleMemories(false); return; }
      setMode(null); if (pickReturn) { const r = pickReturn; pickReturn = null; r(); }
    }
    let pickReturn = null;
    const here = e => { // click position -> lat/lon
      const p = base().viewportToImageCoordinates(v.viewport.pointFromPixel(e.position));
      const [lon, lat] = lonLatOf(p.x, p.y);
      return { x: p.x, y: p.y, lat, lon };
    };

    // ---------------------------------------------------------------- about
    function openAbout() {
      const render = () => `<h2>${t('aboutH')}</h2><p class="desc">${t('aboutIntro')}</p><h3>${t('madeH')}</h3><p>${t('made1')}</p><p>${t('made2')}</p><p>${t('made3')}</p><p>${t('thanks')}</p><p>${t('submitted')}</p><h3>${t('keysH')}</h3><div class="keys">${t('keys').map(k => `<kbd>${k[0]}</kbd><span>${esc(k[1])}</span>`).join('')}</div><div class="foot-btns"><button class="btn btn-primary" data-close>${t('close')}</button></div>`;
      dialog(render(), { wide: true, focus: '.btn-primary', reopen: openAbout });
    }

    // ---------------------------------------------------------------- live API: visitors, memories, reports
    const API = (CFG.api || '/api').replace(/\/$/, '');
    const api = (path, opts) => fetch(API + path, opts).then(async r => {
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw Object.assign(new Error(j.error || r.status), { status: r.status, msg: j.error });
      return j;
    });
    const post = (path, body) => api(path, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
    const uid = store.get('pt-uid') || (() => { const id = [...crypto.getRandomValues(new Uint8Array(10))].map(x => x.toString(16).padStart(2, '0')).join(''); store.set('pt-uid', id); return id; })();
    const fmtN = n => Number(n).toLocaleString('en-IN');
    const fmtDate = ts => new Date(ts * 1000).toLocaleString(lang === 'ta' ? 'ta-IN' : 'en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' });

    const liveEl = $('.live');
    let liveStats = null, apiOk = false;
    function renderLive() {
      if (!liveStats) return;
      $('.live-now', liveEl).innerHTML = t('liveNow').replace('{n}', `<b>${fmtN(liveStats.live)}</b>`);
      $('.live-total', liveEl).innerHTML = liveStats.visitors === 1 ? t('visitor1').replace('1', '<b>1</b>') : t('visitors').replace('{n}', `<b>${fmtN(liveStats.visitors)}</b>`);
    }
    function setApi(ok) {
      if (ok === apiOk) return;
      apiOk = ok; liveEl.hidden = !ok; tools.memories.hidden = !ok; tools.report.hidden = !ok;
      if (!ok && memOn) toggleMemories(false);
    }
    async function ping() {
      try { liveStats = await post('/ping', { id: uid }); renderLive(); setApi(true); } catch (e) { if (e.status !== 429) setApi(false); }
    }
    function startLive() {
      ping(); setInterval(() => { if (!document.hidden) ping(); }, 30000);
      document.addEventListener('visibilitychange', () => { if (!document.hidden) ping(); });
    }

    // ---- memories: pins people leave on the map
    let memOn = false, memLoaded = false, memCardEl = null;
    const memDraft = { text: '', name: store.get('pt-name') || '' };
    function memPin(m) {
      const el = document.createElement('div');
      el.className = 'mem-pin'; el.setAttribute('role', 'button'); el.tabIndex = 0; el.innerHTML = svg('memories'); el.title = m.text.slice(0, 60);
      el.addEventListener('click', e => { e.stopPropagation(); openMemCard(m, el); });
      el.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openMemCard(m, el); } });
      const [x, y] = isoOf(m.lon, m.lat);
      v.addOverlay({ element: el, location: px2vp(x, y), placement: OpenSeadragon.Placement.BOTTOM, checkResize: false });
      return el;
    }
    async function loadMemories() {
      if (memLoaded) return;
      try { (await api('/memories')).reverse().forEach(memPin); memLoaded = true; } catch {}
    }
    function toggleMemories(force) {
      memOn = force ?? !memOn;
      document.body.classList.toggle('mem-on', memOn); tools.memories.setAttribute('aria-pressed', memOn);
      closeMemCard();
      if (memOn) { loadMemories(); setMode('memory', t('memMode'), openMemory); }
      else if (mode && mode.m === 'memory') setMode(null);
    }
    function closeMemCard() {
      if (!memCardEl) return;
      v.removeOverlay(memCardEl.el); memCardEl.pin.classList.remove('on'); memCardEl = null;
    }
    function openMemCard(m, pin) {
      closeMemCard();
      const el = document.createElement('div');
      el.className = 'mem-card';
      el.innerHTML = `<p>${esc(m.text)}</p><div class="by"><span>${m.name ? '— ' + esc(m.name) + ' · ' : ''}${fmtDate(m.ts)}</span><button type="button" class="btn btn-ghost btn-icon-sm" aria-label="${t('close')}">${svg('x')}</button></div>`;
      $('button', el).addEventListener('click', closeMemCard);
      el.addEventListener('click', e => e.stopPropagation());
      const [x, y] = isoOf(m.lon, m.lat);
      v.addOverlay({ element: el, location: px2vp(x, y), placement: OpenSeadragon.Placement.BOTTOM, offset: new OpenSeadragon.Point(0, -36), checkResize: false });
      pin.classList.add('on'); memCardEl = { el, pin };
    }
    function openMemory(pt) {
      setSpot(pt.x, pt.y);
      const ov = dialog(`<h2>${t('memTitle')}</h2><p class="desc">${t('memDesc')}</p>
        <div class="field"><label class="label" for="mt">${t('memText')}</label><textarea class="textarea" id="mt" maxlength="280" placeholder="${esc(t('memPh'))}"></textarea><div class="hint"><span></span><span class="cnt">0/280</span></div></div>
        <div class="field"><label class="label" for="mn">${t('memName')}</label><input class="input" id="mn" maxlength="40" placeholder="${esc(t('memNamePh'))}"></div>
        <div class="error" hidden></div>
        <div class="foot-btns"><button type="button" class="btn btn-ghost" data-close>${t('cancel')}</button><button type="button" class="btn btn-primary send">${t('memSubmit')}</button></div>`,
        { onClose: clearSpot, reopen: () => openMemory(pt) });
      const ta = $('#mt', ov), nm_ = $('#mn', ov), err = $('.error', ov), cnt = $('.cnt', ov), send = $('.send', ov);
      ta.value = memDraft.text; nm_.value = memDraft.name; cnt.textContent = ta.value.length + '/280';
      ta.addEventListener('input', () => { memDraft.text = ta.value; cnt.textContent = ta.value.length + '/280'; });
      nm_.addEventListener('input', () => { memDraft.name = nm_.value; });
      send.addEventListener('click', async () => {
        err.hidden = true;
        if (ta.value.trim().length < 3) { err.textContent = t('repShort'); err.hidden = false; return; }
        send.disabled = true; send.textContent = t('repSending');
        try {
          const m = await post('/memories', { lat: pt.lat, lon: pt.lon, text: ta.value.trim(), name: nm_.value.trim() });
          store.set('pt-name', nm_.value.trim()); memDraft.text = '';
          const pin = memPin(m); closeDialog(true); clearSpot(); setMode(null); toast(t('memThanks'));
          setTimeout(() => openMemCard(m, pin), 150);
        } catch (e) { send.disabled = false; send.textContent = t('memSubmit'); err.textContent = e.msg || t('repFail'); err.hidden = false; }
      });
    }

    // ---- reports: flag a fault, and see what became of it
    const reportDraft = { kind: 'map', note: '', lat: null, lon: null, picked: false, tab: 'new' };
    const myReports = () => { try { return JSON.parse(store.get('pt-reports') || '[]'); } catch { return []; } };
    const saveReports = l => store.set('pt-reports', JSON.stringify(l.slice(0, 60)));
    async function refreshStatuses() {
      const l = myReports(); if (!l.length) return l;
      try {
        const st = await api('/reports?ids=' + l.map(r => r.id).join(','));
        const by = Object.fromEntries(st.map(r => [r.id, r.status]));
        l.forEach(r => { if (by[r.id]) r.status = by[r.id]; }); saveReports(l);
      } catch {}
      return l;
    }
    function pickSpot() {
      pickReturn = () => openReport();
      closeDialog(true);
      setMode('pick', t('repPickMsg'), pt => {
        reportDraft.lat = pt.lat; reportDraft.lon = pt.lon; reportDraft.picked = true; setSpot(pt.x, pt.y);
        pickReturn = null; setMode(null); openReport();
      });
    }
    function openReport(tab) {
      if (tab) reportDraft.tab = tab;
      const d = reportDraft;
      if (d.lat == null) { const [x, y] = centerPx(); const [lon, lat] = lonLatOf(x, y); d.lat = lat; d.lon = lon; d.picked = false; }
      const kinds = Object.entries(t('kinds')).map(([k, l]) => `<button type="button" class="chipbtn" data-kind="${k}" aria-pressed="${d.kind === k}">${esc(l)}</button>`).join('');
      const nMine = myReports().length;
      const ov = dialog(`<h2>${t('repTitle')}</h2><p class="desc">${t('repDesc')}</p>
        <div class="tabs" role="tablist"><button type="button" role="tab" data-tab="new" aria-selected="${d.tab === 'new'}">${t('tabNew')}</button><button type="button" role="tab" data-tab="mine" aria-selected="${d.tab === 'mine'}">${t('tabMine')}${nMine ? ` <span class="badge">${nMine}</span>` : ''}</button></div>
        <div class="pane" data-pane="new"${d.tab === 'new' ? '' : ' hidden'}>
          <div class="field"><span class="label">${t('repKind')}</span><div class="chipgroup">${kinds}</div></div>
          <div class="field"><span class="label">${t('repWhere')}</span><div class="where"><span>${svg('places')}<em class="coords"></em></span><button type="button" class="btn btn-outline btn-sm pick">${svg('crosshair')}${t('repPick')}</button></div></div>
          <div class="field"><label class="label" for="rn">${t('repNote')}</label><textarea class="textarea" id="rn" maxlength="600" placeholder="${esc(t('repNotePh'))}"></textarea><div class="hint"><span></span><span class="cnt"></span></div></div>
          <div class="error" hidden></div>
          <div class="foot-btns"><button type="button" class="btn btn-ghost" data-close>${t('cancel')}</button><button type="button" class="btn btn-primary send">${t('repSend')}</button></div>
        </div>
        <div class="pane" data-pane="mine"${d.tab === 'mine' ? '' : ' hidden'}><p class="desc" style="margin-top:12px">${t('mineDesc')}</p><div class="replist"></div></div>`,
        { wide: true, focus: d.tab === 'new' ? '#rn' : '.dlg-x', reopen: () => openReport(), onClose: () => { clearSpot(); d.lat = null; d.picked = false; } });
      const ta = $('#rn', ov), err = $('.error', ov), cnt = $('.cnt', ov), send = $('.send', ov), list = $('.replist', ov);
      const coords = () => { $('.coords', ov).textContent = `${d.picked ? t('repSpot') : t('repHere')} · ${d.lat.toFixed(5)}, ${d.lon.toFixed(5)}`; };
      coords(); ta.value = d.note; cnt.textContent = ta.value.length + '/600';
      ta.addEventListener('input', () => { d.note = ta.value; cnt.textContent = ta.value.length + '/600'; });
      $$('.chipbtn', ov).forEach(b => b.addEventListener('click', () => { d.kind = b.dataset.kind; $$('.chipbtn', ov).forEach(x => x.setAttribute('aria-pressed', x === b)); }));
      $('.pick', ov).addEventListener('click', pickSpot);
      const renderMine = l => {
        list.innerHTML = l.length ? l.map(r => `<div class="rep" data-s="${r.status}"><div class="st"><i></i>${esc(t('status')[r.status] || t('status').new)}</div><div class="m">${esc(t('kinds')[r.kind] || '')} · ${fmtDate(r.ts)}</div><div class="note">${esc(r.note)}</div><button type="button" class="btn btn-outline btn-sm" data-go="${r.id}">${svg('crosshair')}${t('showOnMap')}</button></div>`).join('') : `<div class="empty">${t('mineEmpty')}</div>`;
        $$('[data-go]', list).forEach(b => b.addEventListener('click', () => {
          const r = l.find(z => String(z.id) === b.dataset.go); closeDialog();
          const [x, y] = isoOf(r.lon, r.lat); setSpot(x, y); flyTo(x, y, 0.9);
        }));
      };
      const showTab = name => {
        d.tab = name;
        $$('[data-tab]', ov).forEach(b => b.setAttribute('aria-selected', b.dataset.tab === name));
        $$('.pane', ov).forEach(p => (p.hidden = p.dataset.pane !== name));
        if (name === 'mine') { renderMine(myReports()); refreshStatuses().then(l => { if (dlgOv === ov) renderMine(l); }); }
      };
      $$('[data-tab]', ov).forEach(b => b.addEventListener('click', () => showTab(b.dataset.tab)));
      if (d.tab === 'mine') showTab('mine');
      send.addEventListener('click', async () => {
        err.hidden = true;
        if (ta.value.trim().length < 3) { err.textContent = t('repShort'); err.hidden = false; return; }
        send.disabled = true; send.textContent = t('repSending');
        try {
          const r = await post('/reports', { id: uid, kind: d.kind, note: ta.value.trim(), lat: d.lat, lon: d.lon });
          const l = myReports(); l.unshift({ id: r.id, kind: d.kind, note: ta.value.trim(), lat: d.lat, lon: d.lon, ts: Math.floor(Date.now() / 1000), status: 'new' }); saveReports(l);
          d.note = ''; toast(t('repSent')); d.tab = 'mine'; clearSpot(); d.picked = false; d.lat = null; openReport('mine');
        } catch (e) { send.disabled = false; send.textContent = t('repSend'); err.textContent = e.msg || t('repFail'); err.hidden = false; }
      });
    }

    // ---------------------------------------------------------------- keep the view inside the Trichy area (no empty margins)
    const OB = D.outline && D.outline.bounds;
    let applyingBounds = false;
    function applyBounds() {
      if (!OB || !base() || applyingBounds) return;
      const vw = v.container.clientWidth, vh = v.container.clientHeight;
      if (!vw || !vh) return;
      const IW = cover.width, IH = cover.height, asp = vw / vh;
      let w = (OB[2] - OB[0]) * 1.07, h = (OB[3] - OB[1]) * 1.07;
      const cx = (OB[0] + OB[2]) / 2, cy = (OB[1] + OB[3]) / 2;
      if (w / h > asp) h = w / asp; else w = h * asp;          // grow the short side with real map, never with blank space
      w = Math.min(w, IW); h = Math.min(h, IH);
      const x0 = Math.max(0, Math.min(IW - w, cx - w / 2)), y0 = Math.max(0, Math.min(IH - h, cy - h / 2));
      applyingBounds = true;
      v.viewport._setContentBounds(new OpenSeadragon.Rect(x0 / IW, y0 / IW, w / IW, h / IW), v.world.getContentFactor());
      applyingBounds = false;
      v.viewport.applyConstraints(true);
    }
    v.world.addHandler('metrics-change', applyBounds);
    window.addEventListener('resize', () => setTimeout(applyBounds, 60));

    // ---------------------------------------------------------------- minimap
    const mini = $('.mini'), mc = $('canvas', mini), mx = mc.getContext('2d');
    const miniImg = new Image();
    miniImg.src = `${CFG.base}${Math.max(0, cover.level - 9)}/0_0.webp${ver}`;
    miniImg.onload = drawMini;
    function drawMini() {
      mx.imageSmoothingEnabled = false; mx.clearRect(0, 0, mc.width, mc.height);
      if (miniImg.complete && miniImg.naturalWidth) mx.drawImage(miniImg, 0, 0, mc.width, mc.height);
      if (!base()) return;
      const b = v.viewport.getBounds(true), r = base().viewportToImageRectangle(b);
      const sx = mc.width / cover.width, sy = mc.height / cover.height;
      mx.strokeStyle = '#f0a23c'; mx.fillStyle = 'rgba(240,162,60,.18)'; mx.lineWidth = 2;
      const x = r.x * sx, y = r.y * sy, w = Math.max(3, r.width * sx), h = Math.max(3, r.height * sy);
      mx.fillRect(x, y, w, h); mx.strokeRect(x, y, w, h);
    }
    mc.addEventListener('click', e => {
      const b = mc.getBoundingClientRect(); const px = (e.clientX - b.left) / b.width * cover.width, py = (e.clientY - b.top) / b.height * cover.height;
      v.viewport.panTo(px2vp(px, py));
    });

    // ---------------------------------------------------------------- moving traffic and trains (traffic.js)
    let trafficJs = null;
    const traffic = () => trafficJs || (trafficJs = new Promise((ok, no) => {
      const s = Object.assign(document.createElement('script'), {
        src: 'traffic.js' + ver, onerror: no,
        onload: () => ok(window.pixelTraffic.init({ v, px2vp, base, t, toast, flyTo, lang: () => lang, urls: Object.fromEntries(Object.entries(CFG.traffic).map(([k, u]) => [k, u + ver])) })),
      });
      document.head.appendChild(s);
    }));
    function startTraffic() { if (CFG.traffic) traffic().then(() => { tools.rail.hidden = false; syncTitles(); }).catch(e => { trafficJs = null; console.warn(e); }); }

    // ---------------------------------------------------------------- language
    function setLang(l) {
      lang = l; store.set('pt-lang', l); document.documentElement.lang = l;
      $('#q').placeholder = t('searchPh'); $('#q').setAttribute('aria-label', t('searchLabel')); $('#map').setAttribute('aria-label', t('mapLabel')); $('.credit').innerHTML = t('credit');
      $('.made-txt').textContent = t('madeA'); $('.made-txt2').textContent = t('madeB');
      mini.setAttribute('aria-label', t('mapLabel'));
      syncTitles(); renderStrip(); renderDock(); renderLive(); if (!results.hidden) renderResults(search(input.value), input.value);
      if (mode) $('.modebar-msg', modebar).textContent = mode.m === 'pick' ? t('repPickMsg') : t('memMode');
      if (dlgReopen) dlgReopen();
      if (window.pixelTraffic && window.pixelTraffic.refresh) window.pixelTraffic.refresh();
    }

    // ---------------------------------------------------------------- events
    // pixel art stays crisp when zoomed in; smooth only when shrinking, to avoid shimmer
    const crisp = () => { try { v.drawer.setImageSmoothingEnabled(imgZoom() < 0.95); } catch (e) {} };
    v.addHandler('animation', () => { drawMini(); zoomClasses(); crisp(); drawBorder(); });
    v.addHandler('animation-finish', () => { drawMini(); zoomClasses(); crisp(); drawBorder(); });
    v.addHandler('update-viewport', drawBorder);
    window.addEventListener('resize', () => setTimeout(drawBorder, 50));
    v.addHandler('canvas-click', e => {
      if (!e.quick) return;
      if (dlgOv) return;
      if (mode) {
        const pt = here(e);
        if (!inBox(pt.lat, pt.lon)) { toast(t('memOutside')); return; }
        mode.onPick(pt); return;
      }
      if (memCardEl) { closeMemCard(); return; }
      if (window.pixelTraffic && window.pixelTraffic.click && window.pixelTraffic.click(e.position)) return;
      if (cur || spotEl) closeDock();
    });
    document.addEventListener('keydown', e => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === 'Escape' && dlgOv) { closeDialog(); return; }
      if (dlgOv) return;
      const typing = /^(input|textarea)$/i.test(e.target.tagName);
      if (e.key === '/' && !typing) { e.preventDefault(); document.body.classList.remove('focus'); input.focus(); }
      else if (typing) return;
      else if (e.key === 'p' || e.key === 'P') togglePlaces();
      else if (e.key === 'h' || e.key === 'H') { document.body.classList.toggle('focus'); if (document.body.classList.contains('focus')) toast(t('focusHint')); }
      else if (e.key === ']') step(1);
      else if (e.key === '[') step(-1);
      else if (e.key === 'f' || e.key === 'F') toggleFull();
      else if (e.key === 'l' || e.key === 'L') { if (aiItem) setAi(!aiOn); }
      else if (e.key === 'n' || e.key === 'N') setLabels(!labelsOn);
      else if ((e.key === 'm' || e.key === 'M') && !tools.rail.hidden) tools.rail.click();
      else if (e.key === 'Escape') { if (window.pixelTraffic && window.pixelTraffic.stop()) return; if (mode) exitMode(); else if (memCardEl) closeMemCard(); else if (memOn) toggleMemories(false); else if (cur || spotEl) closeDock(); else if (!stripWrap.hidden && !cur) togglePlaces(false); document.body.classList.remove('focus'); }
    });

    // ---------------------------------------------------------------- ready: overlays, deep links
    function onReady() {
      applyBounds(); v.viewport.goHome(true); addPinOverlays(); addLabels(); setLabels(labelsOn); placeCityName(); startLive();
      if (CFG.traffic && CFG.traffic.outline) getJson(CFG.traffic.outline + ver).then(o => addBorder(o.poly)).catch(() => {}); setLang(lang); mini.hidden = false; zoomClasses(); drawMini(); startTraffic();
      const ld = $('.loading'); if (ld) { ld.classList.add('done'); setTimeout(() => ld.remove(), 700); }
      if (!store.get('pt-hint')) { store.set('pt-hint', '1'); setTimeout(() => toast(t('hint')), 1200); }
      const h = decodeURIComponent(location.hash.slice(1));
      const p = h && places.find(q => q.slug === h);
      const lat = parseFloat(qs.get('lat')), lng = parseFloat(qs.get('lng') ?? qs.get('lon')), zoom = parseFloat(qs.get('zoom'));
      if (p) openPlace(p, false);
      else if (!isNaN(lat) && !isNaN(lng) && inBox(lat, lng)) { const [x, y] = isoOf(lng, lat); jumpTo(x, y, isNaN(zoom) ? 0.8 : Math.min(3, Math.max(0.02, zoom))); }
      else { const first = places.find(q => q.slug === 'rockfort'); if (first) jumpTo(first.x, first.y, 0.12); }
      window.addEventListener('hashchange', () => { const s = decodeURIComponent(location.hash.slice(1)); const q = places.find(z => z.slug === s); if (q && (!cur || cur.slug !== s)) openPlace(q, true); });
    }
    // debug handle for tests
    window.__pt = { v, isoOf, lonLatOf, openPlace: s => openPlace(places.find(p => p.slug === s), false), places };
  }
})();
