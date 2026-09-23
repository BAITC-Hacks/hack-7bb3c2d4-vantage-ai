/* replay.js — "Replay the month": day-by-day playback of July on the hop layout.
   ES module, no dependencies. Exports mountReplay(container, D, api) and replayFacts(D). */

const STEP_MS = 700;
const TRAIL_DAYS = 3;
const MONTHS = ["January", "February", "March", "April", "May", "June", "July",
  "August", "September", "October", "November", "December"];

/* UI strings. api.lang is "en" | "ru" | "kk"; anything else falls back to English. */
const T = {
  en: {
    play: "Play",
    pause: "Pause",
    trail: "Show previous days",
    kztMoved: "KZT transferred",
    transfers: "transfers",
    activeAccounts: "active accounts",
    knownClients: "listed accounts",
    hop: "hop {n}",
    hintSelect: "click a node to select",
    hintMock: "placeholder days (D.days missing)",
    dayOfMonth: "Day of month",
    barTitle: "{date} — {kzt} KZT, {n} transfers",
    locale: "en-GB",
  },
  ru: {
    play: "Воспроизвести",
    pause: "Пауза",
    trail: "Показать предыдущие дни",
    kztMoved: "переведено, KZT",
    transfers: "переводов",
    activeAccounts: "активных счетов",
    knownClients: "счета из списка",
    hop: "шаг {n}",
    hintSelect: "нажмите на узел, чтобы выбрать",
    hintMock: "дни-заглушки (D.days отсутствует)",
    dayOfMonth: "День месяца",
    barTitle: "{date} — {kzt} KZT, переводов: {n}",
    locale: "ru-RU",
  },
  kk: {
    play: "Ойнату",
    pause: "Кідірту",
    trail: "Алдыңғы күндерді көрсету",
    kztMoved: "аударылды, KZT",
    transfers: "аударым",
    activeAccounts: "белсенді шоттар",
    knownClients: "тізімдегі шоттар",
    hop: "{n}-қадам",
    hintSelect: "таңдау үшін түйінді басыңыз",
    hintMock: "уақытша күндер (D.days жоқ)",
    dayOfMonth: "Айдың күні",
    barTitle: "{date} — {kzt} KZT, аударым: {n}",
    locale: "kk-KZ",
  },
};
const t = (k, lang) => (T[lang] || T.en)[k] ?? T.en[k] ?? k;
const _fill = (s, vars) => String(s).replace(/\{(\w+)\}/g, (_, v) => (vars[v] ?? ""));

const CSS = `
.replay{display:flex;flex-direction:column;gap:10px;min-height:560px;font:.8125rem/1.4 var(--body);color:var(--text);
  font-variant-numeric:tabular-nums;box-sizing:border-box}
.replay *{box-sizing:border-box}
.replay .rp-row{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.replay .rp-btn{height:2rem;padding:0 .8rem;border:1px solid var(--line);border-radius:var(--r-md,8px);background:var(--sunk);color:var(--text);
  font:500 .8125rem/1 var(--body);cursor:pointer;min-width:64px;font-variant-numeric:tabular-nums}
.replay .rp-btn:hover{background:var(--strong)}
.replay .rp-play{height:3.4rem;padding:0 2rem;font-size:1.1rem;font-weight:800;letter-spacing:-.01em;background:var(--amber);color:#0B0C0D;border-color:var(--amber);border-radius:var(--r-pill,14px)}
.replay .rp-play:hover{filter:brightness(1.08);background:var(--amber)}
.replay .rp-play[aria-pressed=true]{background:var(--amber);color:#0B0C0D;box-shadow:none}
.replay .rp-btn[aria-pressed=true]{background:var(--panel);color:var(--fg);box-shadow:inset 0 0 0 1px var(--line)}
.replay .rp-range{flex:1 1 160px;min-width:120px;height:22px;margin:0;appearance:none;-webkit-appearance:none;background:transparent;cursor:pointer;accent-color:var(--amber)}
.replay .rp-range::-webkit-slider-runnable-track{height:2px;background:var(--line);border-radius:1px}
.replay .rp-range::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;width:14px;height:14px;margin-top:-6px;border-radius:50%;
  background:var(--amber);border:1px solid var(--bg)}
.replay .rp-range::-moz-range-track{height:2px;background:var(--line);border-radius:1px}
.replay .rp-range::-moz-range-thumb{width:14px;height:14px;border-radius:50%;background:var(--amber);border:1px solid var(--bg)}
.replay .rp-date{font:600 1.5rem/1 var(--display);letter-spacing:-.02em;color:var(--fg);min-width:118px;white-space:nowrap}
.replay .rp-figs{display:flex;gap:18px;margin-left:auto}
.replay .rp-fig b{display:block;font:600 1.0625rem/1.15 var(--display);letter-spacing:-.02em;color:var(--fg);white-space:nowrap}
.replay .rp-fig span{font-size:.72rem;color:var(--muted);white-space:nowrap;text-transform:uppercase;letter-spacing:.06em}
.replay .rp-spark{display:flex;align-items:flex-end;gap:2px;height:40px;padding:4px 6px;border:1px solid var(--line);border-radius:var(--r-md,8px);
  background:var(--sunk)}
.replay .rp-bar{flex:1 1 0;min-height:2px;background:var(--steel);opacity:.6;border-radius:1px 1px 0 0;cursor:pointer;border:0;padding:0}
.replay .rp-bar:hover{background:var(--text);opacity:1}
.replay .rp-bar.cur{background:var(--amber);opacity:1}
.replay .rp-stage{position:relative;flex:1 1 auto;min-height:420px;padding:8px;border:1px solid var(--line);border-radius:var(--r-xl,16px);overflow:hidden;
  background:linear-gradient(var(--grid) 1px,transparent 1px) content-box,linear-gradient(90deg,var(--grid) 1px,transparent 1px) content-box,
  linear-gradient(var(--bg),var(--bg)) content-box,var(--sunk);background-size:32px 32px,32px 32px,auto,auto}
.replay .rp-stage canvas{display:block;width:calc(100% + 16px);height:calc(100% + 16px);margin:-8px}
.replay .rp-hint{position:absolute;right:12px;bottom:8px;font:.72rem/1 var(--body);color:var(--steel);pointer-events:none}
/* phone: controls wrap onto rows (play · date · trail / slider / figures); bars keep a tall hit area */
@media (max-width:640px){
  .replay{min-height:0;gap:8px}
  .replay .rp-row{gap:8px 10px}
  .replay .rp-btn{height:auto;min-height:36px;padding:0 12px}
  .replay .rp-date{font-size:1.25rem;min-width:0;flex:1 1 auto}
  .replay .rp-range{order:5;flex:1 1 100%;min-width:0;height:36px}
  .replay .rp-range::-webkit-slider-runnable-track{margin-top:0}
  .replay .rp-range::-webkit-slider-thumb{width:22px;height:22px;margin-top:-10px}
  .replay .rp-range::-moz-range-thumb{width:22px;height:22px}
  .replay .rp-figs{order:6;flex:1 1 100%;margin-left:0;justify-content:space-between;gap:8px}
  .replay .rp-fig{min-width:0}
  .replay .rp-fig b{font-size:.9375rem}
  .replay .rp-fig span{font-size:.66rem;white-space:normal}
  .replay .rp-spark{height:48px;gap:1px;padding:4px 4px 0;align-items:flex-end}
  .replay .rp-bar{position:relative;min-width:0}
  .replay .rp-bar::after{content:"";position:absolute;left:-1px;right:0;top:-44px;bottom:0}
  .replay .rp-stage{min-height:300px}
}
`;

/* ------------------------------ helpers ------------------------------ */

function _hash(s) { // small deterministic integer from an id
  let h = 0; s = String(s);
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return h;
}

/* Dev-only mock: spread D.edges across 31 July dates deterministically. Used ONLY when D.days is missing. */
export function _mockDays(D) {
  const buckets = Array.from({ length: 31 }, () => new Map());
  // a few "burst" days so the replay has shape
  const weight = d => (d === 6 || d === 14 || d === 22 || d === 28) ? 3 : 1;
  const wsum = Array.from({ length: 31 }, (_, d) => weight(d)).reduce((a, b) => a + b, 0);
  const pick = h => { // weighted day pick
    let r = h % wsum;
    for (let d = 0; d < 31; d++) { r -= weight(d); if (r < 0) return d; }
    return 30;
  };
  for (const e of D.edges || []) {
    const h = _hash(e.s + ":" + e.t);
    const parts = Math.max(1, Math.min(e.n || 1, 3));
    for (let p = 0; p < parts; p++) {
      const d = pick((h + p * 7919) >>> 0);
      const key = e.s + ">" + e.t;
      const cur = buckets[d].get(key) || { s: e.s, t: e.t, kzt: 0, n: 0 };
      cur.kzt += (e.kzt || 0) / parts;
      cur.n += Math.max(1, Math.round((e.n || 1) / parts));
      buckets[d].set(key, cur);
    }
  }
  return buckets.map((m, d) => {
    const transfers = [...m.values()];
    const acc = new Set();
    let kzt = 0, n_tx = 0;
    for (const t of transfers) { kzt += t.kzt; n_tx += t.n; acc.add(t.s); acc.add(t.t); }
    return { date: `2026-07-${String(d + 1).padStart(2, "0")}`, kzt: Math.round(kzt), n_tx, active: acc.size, transfers };
  });
}

function _days(D) { return Array.isArray(D.days) && D.days.length ? D.days : _mockDays(D); }

export function replayFacts(D) {
  const days = _days(D);
  let busiest = days[0];
  for (const d of days) if ((d.kzt || 0) > (busiest.kzt || 0)) busiest = d;
  const sorted = days.map(d => d.kzt || 0).sort((a, b) => a - b);
  const mid = sorted.length >> 1;
  const medianKzt = sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
  const quietDays = days.filter(d => (d.kzt || 0) < medianKzt / 2).length; // days below half the median
  return { busiestDay: { date: busiest.date, kzt: busiest.kzt, n_tx: busiest.n_tx }, quietDays, medianKzt };
}

function _prettyDate(iso, locale) {
  const dt = new Date(String(iso) + "T00:00:00");
  if (!Number.isNaN(dt.getTime())) {
    try { return dt.toLocaleDateString(locale || "en-GB", { day: "numeric", month: "long" }); } catch (_) { /* fall through */ }
  }
  const [, m, d] = String(iso).split("-").map(Number);
  return `${d} ${MONTHS[(m || 7) - 1]}`;
}

function _rgb(cssVal) { // "#00C8FF" | "rgb(0,200,255)" -> [r,g,b]
  const v = (cssVal || "").trim();
  if (v[0] === "#") {
    const h = v.length === 4 ? v.slice(1).split("").map(c => c + c).join("") : v.slice(1, 7);
    return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
  }
  const m = v.match(/(\d+)[,\s]+(\d+)[,\s]+(\d+)/);
  return m ? [+m[1], +m[2], +m[3]] : [0, 200, 255];
}
const _rgba = (c, a) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;

/* ------------------------------ mount ------------------------------ */

export function mountReplay(container, D, api) {
  if (!document.getElementById("replay-style")) {
    const st = document.createElement("style");
    st.id = "replay-style"; st.textContent = CSS;
    document.head.appendChild(st);
  }
  container.classList.add("replay");
  container.innerHTML = "";

  const days = _days(D);
  const N = days.length;
  const usingMock = !(Array.isArray(D.days) && D.days.length);
  const lang = T[api.lang] ? api.lang : "en";
  const s = k => t(k, lang);
  const locale = s("locale");
  const fmt = api.fmt || (n => Number(n).toLocaleString(locale, { maximumFractionDigits: 0 }));

  /* controls */
  const row = document.createElement("div"); row.className = "rp-row";
  const play = document.createElement("button"); play.className = "rp-btn rp-play"; play.type = "button"; play.textContent = "\u25B6 " + s("play");
  const range = document.createElement("input"); range.className = "rp-range"; range.type = "range";
  range.min = "1"; range.max = String(N); range.step = "1"; range.value = "1"; range.setAttribute("aria-label", s("dayOfMonth"));
  const dateEl = document.createElement("div"); dateEl.className = "rp-date";
  const figs = document.createElement("div"); figs.className = "rp-figs";
  const mkFig = label => { const f = document.createElement("div"); f.className = "rp-fig"; const b = document.createElement("b"); const s = document.createElement("span"); s.textContent = label; f.append(b, s); figs.appendChild(f); return b; };
  const fKzt = mkFig(s("kztMoved")), fTx = mkFig(s("transfers")), fAct = mkFig(s("activeAccounts"));
  const trail = document.createElement("button"); trail.className = "rp-btn"; trail.type = "button"; trail.textContent = s("trail");
  trail.setAttribute("aria-pressed", "true");
  row.append(play, range, dateEl, trail, figs);

  const spark = document.createElement("div"); spark.className = "rp-spark";
  const maxKzt = Math.max(1, ...days.map(d => d.kzt || 0));
  const bars = days.map((d, i) => {
    const b = document.createElement("button"); b.className = "rp-bar"; b.type = "button";
    b.style.height = `${Math.max(2, Math.round(((d.kzt || 0) / maxKzt) * 32))}px`;
    b.title = _fill(s("barTitle"), { date: _prettyDate(d.date, locale), kzt: fmt(d.kzt || 0), n: fmt(d.n_tx || 0) });
    b.addEventListener("click", () => { setDay(i); });
    spark.appendChild(b); return b;
  });

  const stage = document.createElement("div"); stage.className = "rp-stage";
  const cv = document.createElement("canvas"); stage.appendChild(cv);
  const hint = document.createElement("div"); hint.className = "rp-hint";
  hint.textContent = usingMock ? s("hintMock") : s("hintSelect");
  stage.appendChild(hint);
  container.append(row, spark, stage);

  const ctx = cv.getContext("2d");

  /* colours */
  const cs = getComputedStyle(container);
  const PRIMARY = _rgb(cs.getPropertyValue("--primary") || "#00C8FF");
  const FG = _rgb(cs.getPropertyValue("--fg") || "#EEF3FB");
  const MUTED = cs.getPropertyValue("--muted").trim() || "#8FA3BF";
  const MONO = cs.getPropertyValue("--mono").trim() || "ui-monospace,monospace";

  /* layout state */
  let W = 0, H = 0, dpr = 1;
  const pos = new Map();            // id -> {x,y,r,seed,color}
  const nodeById = new Map();
  for (const n of D.nodes) nodeById.set(String(n.id), n);
  const maxHop = Math.max(1, ...D.nodes.map(n => n.hop || 0));
  let dayArcs = [];                 // per day: Float32Array-ish list of arcs {x1,y1,cx,cy,x2,y2,w}
  let dayActive = days.map(d => { const s = new Set(); for (const t of d.transfers || []) { s.add(String(t.s)); s.add(String(t.t)); } return s; });

  function layout() {
    pos.clear();
    const padL = W < 480 ? 40 : 88, padR = W < 480 ? 36 : 80, top = 34, bottom = H - 24;
    const band = Math.min(62, (W - padL - padR) / (maxHop + 1) * .55);
    for (const n of D.nodes) {
      const id = String(n.id);
      const jig = ((+id.slice(-4) % 997) / 997 - .5);
      pos.set(id, {
        x: padL + (W - padL - padR) * ((n.hop || 0) / maxHop) + jig * band,
        y: top + (bottom - top) * (n.y ?? .5),
        r: n.seed ? 3 : 2.2, seed: !!n.seed, color: api.roleColor(n.role) || MUTED,
      });
    }
    // precompute positioned arcs per day
    dayArcs = days.map(d => {
      const out = [];
      for (const t of d.transfers || []) {
        const a = pos.get(String(t.s)), b = pos.get(String(t.t));
        if (!a || !b) continue;
        const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1;
        const sign = (_hash(t.s + t.t) & 1) ? 1 : -1;
        const bend = Math.min(60, len * .18) * sign;
        const cx = (a.x + b.x) / 2 - dy / len * bend, cy = (a.y + b.y) / 2 + dx / len * bend;
        const w = Math.max(.8, Math.min(5, .8 + Math.log10(Math.max(1, t.kzt || 1)) * .7 - 2));
        out.push({ x1: a.x, y1: a.y, cx, cy, x2: b.x, y2: b.y, w });
      }
      return out;
    });
  }

  /* drawing */
  let day = 0, trailOn = true;

  function drawArcs(arcs, alpha) {
    ctx.strokeStyle = _rgba(PRIMARY, alpha);
    ctx.fillStyle = _rgba(PRIMARY, alpha);
    for (const a of arcs) {
      ctx.lineWidth = a.w;
      ctx.beginPath(); ctx.moveTo(a.x1, a.y1); ctx.quadraticCurveTo(a.cx, a.cy, a.x2, a.y2); ctx.stroke();
      // arrowhead at t, along the end tangent (control -> end)
      const tx = a.x2 - a.cx, ty = a.y2 - a.cy, tl = Math.hypot(tx, ty) || 1;
      const ux = tx / tl, uy = ty / tl, s = 3.5 + a.w;
      const bx = a.x2 - ux * 3, by = a.y2 - uy * 3;
      ctx.beginPath();
      ctx.moveTo(bx, by);
      ctx.lineTo(bx - ux * s - uy * s * .5, by - uy * s + ux * s * .5);
      ctx.lineTo(bx - ux * s + uy * s * .5, by - uy * s - ux * s * .5);
      ctx.closePath(); ctx.fill();
    }
  }

  function draw() {
    if (!W || !H) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);

    // column labels
    ctx.font = `11px ${MONO}`; ctx.fillStyle = MUTED; ctx.textAlign = "center"; ctx.textBaseline = "top";
    const narrow = W < 480, padL = narrow ? 40 : 88, padR = narrow ? 36 : 80;
    for (let h = 0; h <= maxHop; h++) {
      const x = padL + (W - padL - padR) * (h / maxHop);
      const label = narrow ? String(h) : (h === 0 ? s("knownClients") : _fill(s("hop"), { n: h }));
      ctx.fillText(label, x, narrow ? (h % 2 ? 22 : 8) : 10);
    }

    // inactive nodes, dim
    const active = dayActive[day];
    for (const [id, p] of pos) {
      if (active.has(id)) continue;
      ctx.globalAlpha = .38;
      ctx.fillStyle = p.color;
      ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2); ctx.fill();
      if (p.seed) { ctx.strokeStyle = _rgba(FG, .6); ctx.lineWidth = 1; ctx.beginPath(); ctx.arc(p.x, p.y, p.r + 2, 0, Math.PI * 2); ctx.stroke(); }
    }
    ctx.globalAlpha = 1;

    // trail arcs (older first, fainter)
    ctx.lineCap = "round"; ctx.lineJoin = "round";
    if (trailOn) {
      for (let k = TRAIL_DAYS; k >= 1; k--) {
        const di = day - k; if (di < 0) continue;
        drawArcs(dayArcs[di], .32 * (1 - (k - 1) / TRAIL_DAYS));
      }
    }
    drawArcs(dayArcs[day], .95);

    // active nodes, bright & larger
    for (const id of active) {
      const p = pos.get(id); if (!p) continue;
      ctx.fillStyle = p.color;
      ctx.beginPath(); ctx.arc(p.x, p.y, p.r + 1.4, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = _rgba(FG, p.seed ? .95 : .5); ctx.lineWidth = 1;
      ctx.beginPath(); ctx.arc(p.x, p.y, p.r + (p.seed ? 3.4 : 2.4), 0, Math.PI * 2); ctx.stroke();
    }
  }

  function setDay(i, fromRange) {
    day = Math.max(0, Math.min(N - 1, i));
    const d = days[day];
    if (!fromRange) range.value = String(day + 1);
    dateEl.textContent = _prettyDate(d.date, locale);
    fKzt.textContent = fmt(d.kzt || 0);
    fTx.textContent = fmt(d.n_tx || 0);
    fAct.textContent = fmt(d.active ?? dayActive[day].size);
    bars.forEach((b, j) => b.classList.toggle("cur", j === day));
    draw();
  }

  /* playback */
  let playing = false, raf = 0, last = 0, acc = 0;
  function tick(ts) {
    if (!playing) return;
    if (last) acc += ts - last;
    last = ts;
    if (acc >= STEP_MS) { acc -= STEP_MS; setDay((day + 1) % N); }
    raf = requestAnimationFrame(tick);
  }
  function setPlaying(v) {
    playing = v; play.textContent = v ? s("pause") : s("play"); play.setAttribute("aria-pressed", v ? "true" : "false");
    cancelAnimationFrame(raf); last = 0; acc = 0;
    if (v) raf = requestAnimationFrame(tick);
  }
  play.addEventListener("click", () => setPlaying(!playing));
  range.addEventListener("input", () => { setDay(+range.value - 1, true); });
  trail.addEventListener("click", () => { trailOn = !trailOn; trail.setAttribute("aria-pressed", trailOn ? "true" : "false"); draw(); });

  /* hit testing */
  function nearest(ev) {
    const r = cv.getBoundingClientRect();
    const mx = ev.clientX - r.left, my = ev.clientY - r.top;
    let best = null, bd = 64; // 8px radius
    const active = dayActive[day];
    for (const [id, p] of pos) {
      const d2 = (p.x - mx) ** 2 + (p.y - my) ** 2;
      const dd = active.has(id) ? d2 * .5 : d2; // prefer active nodes
      if (dd < bd) { bd = dd; best = id; }
    }
    return best;
  }
  cv.addEventListener("mousemove", ev => { cv.style.cursor = nearest(ev) ? "pointer" : "default"; });
  cv.addEventListener("click", ev => { const id = nearest(ev); if (id && api.selectNode) api.selectNode(id); });

  /* sizing */
  function resize() {
    const r = stage.getBoundingClientRect();
    const w = Math.max(200, Math.floor(r.width)), h = Math.max(200, Math.floor(r.height));
    dpr = Math.min(2, window.devicePixelRatio || 1);
    if (w === W && h === H && cv.width === Math.round(w * dpr)) return;
    W = w; H = h;
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    layout(); draw();
  }
  const ro = new ResizeObserver(resize);
  ro.observe(stage);
  resize();
  setDay(0);

  return {
    setDay: i => setDay(i), play: () => setPlaying(true), pause: () => setPlaying(false),
    destroy: () => { setPlaying(false); ro.disconnect(); container.innerHTML = ""; container.classList.remove("replay"); },
  };
}
