// echoes.js — "Amount echoes" section for the review screen.
// ES module, no dependencies. Exports mountEchoes(container, D, api) and echoFacts(D).
//
// An echo is a hypothesis for an analyst to check: an exact amount arriving at an
// account and leaving again (relay), leaving split into parts (split), or one account
// sending the identical amount to several receivers on one day (fan_split).

const KIND_PHRASE = {
  relay: "Same amount in and out",
  split: "One amount in, split on the way out",
  fan_split: "Same amount to N receivers",
};
const KIND_NOUN = {
  relay: ["relay", "relays"],
  split: ["split", "splits"],
  fan_split: ["same-amount fan-out", "same-amount fan-outs"],
};
const MONTHS = ["January","February","March","April","May","June","July","August","September","October","November","December"];

const CSS = `
.echoes{font-family:var(--body);color:var(--fg);font-variant-numeric:tabular-nums;width:100%}
.echoes *{box-sizing:border-box}
.echoes .ech-head{display:flex;flex-wrap:wrap;align-items:center;gap:10px 16px;margin:0 0 12px}
.echoes .ech-counts{font-family:var(--display);font-size:14px;font-weight:600;letter-spacing:.01em}
.echoes .ech-counts .ech-mock{margin-left:8px;font-family:var(--mono);font-size:10px;font-weight:400;color:var(--amber);border:1px solid var(--amber);border-radius:4px;padding:1px 5px;vertical-align:middle}
.echoes .ech-tools{display:flex;flex-wrap:wrap;align-items:center;gap:6px;margin-left:auto}
.echoes .ech-chip{font:inherit;font-size:12px;line-height:1;padding:6px 10px;border-radius:999px;border:1px solid var(--line);background:var(--sunk);color:var(--muted);cursor:pointer}
.echoes .ech-chip[aria-pressed="true"]{border-color:var(--primary);color:var(--fg);background:var(--panel)}
.echoes .ech-chip .ech-n{font-family:var(--mono);margin-left:5px;color:var(--muted)}
.echoes .ech-sort{display:flex;align-items:center;gap:6px;margin-left:8px;font-size:12px;color:var(--muted)}
.echoes .ech-sort select{font:inherit;font-size:12px;color:var(--fg);background:var(--sunk);border:1px solid var(--line);border-radius:6px;padding:5px 8px}
.echoes .ech-list{display:flex;flex-direction:column;gap:10px;max-height:70vh;overflow:auto;padding-right:2px}
.echoes .ech-card{display:grid;grid-template-columns:340px minmax(0,1fr);gap:0 18px;background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.echoes .ech-fig{display:flex;flex-direction:column;gap:6px;align-items:flex-start}
.echoes .ech-fig svg{display:block;width:100%;height:auto;overflow:visible}
.echoes .ech-dot{cursor:pointer}
.echoes .ech-dot:hover circle{stroke:var(--fg)}
.echoes .ech-badge{font-family:var(--mono);font-size:10px;letter-spacing:.04em;text-transform:uppercase;padding:2px 7px;border-radius:4px;border:1px solid var(--line);color:var(--muted)}
.echoes .ech-badge.exact{color:var(--amber);border-color:var(--amber)}
.echoes .ech-body{display:flex;flex-direction:column;gap:6px;min-width:0}
.echoes .ech-kind{font-family:var(--display);font-size:15px;font-weight:600;line-height:1.3}
.echoes .ech-when{font-size:12px;color:var(--muted);font-family:var(--mono)}
.echoes .ech-when b{color:var(--fg);font-weight:500}
.echoes .ech-ev{font-size:13px;line-height:1.5;color:var(--fg);margin:2px 0 4px}
.echoes .ech-foot{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-top:auto}
.echoes .ech-open{font:inherit;font-size:12px;padding:6px 12px;border-radius:6px;border:1px solid var(--primary);background:transparent;color:var(--primary);cursor:pointer}
.echoes .ech-open:hover{background:var(--sunk)}
.echoes .ech-id{font-family:var(--mono);font-size:11px;color:var(--muted)}
.echoes .ech-empty{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:18px 16px;font-size:13px;line-height:1.5;color:var(--muted)}
.echoes .ech-empty b{color:var(--fg);font-weight:500}
@media (max-width:900px){
  .echoes .ech-card{grid-template-columns:1fr;gap:12px}
  .echoes .ech-fig svg{max-width:360px}
  .echoes .ech-tools{margin-left:0}
}
`;

let styleInjected = false;
function injectStyle() {
  if (styleInjected || document.getElementById("echoes-style")) { styleInjected = true; return; }
  const s = document.createElement("style");
  s.id = "echoes-style";
  s.textContent = CSS;
  document.head.appendChild(s);
  styleInjected = true;
}

// ---------- helpers ----------
function asList(v) {
  if (Array.isArray(v)) return v.map(String).filter(Boolean);
  if (typeof v === "string") return v.split(/[\s,]+/).filter(Boolean);
  return [];
}
function num(v, d = 0) { const n = Number(v); return Number.isFinite(n) ? n : d; }
function esc(s) { return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }
function tail(gid) { const s = String(gid); return s.length > 7 ? s.slice(-7) : s; }
function parseDate(s) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(s || ""));
  if (!m) return null;
  return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
}
function dayMonth(d) { return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`; }
function whenText(e) {
  const d0 = parseDate(e.date);
  if (!d0) return e.date ? String(e.date) : "date unknown";
  const lag = Math.max(0, Math.round(num(e.lag_days, 0)));
  if (lag === 0) return `${dayMonth(d0)}, same day`;
  const d1 = new Date(d0.getTime() + lag * 86400000);
  if (d1.getUTCMonth() === d0.getUTCMonth()) return `${d0.getUTCDate()}–${d1.getUTCDate()} ${MONTHS[d0.getUTCMonth()]}`;
  return `${dayMonth(d0)} – ${dayMonth(d1)}`;
}
function plural(kind, n) { const p = KIND_NOUN[kind] || [kind, kind + "s"]; return `${n} ${n === 1 ? p[0] : p[1]}`; }

// Normalise one raw echo record into a predictable shape.
function normalise(raw, i) {
  const gid = String(raw.gid ?? raw.account ?? "");
  const kind = ["relay", "split", "fan_split"].includes(raw.kind) ? raw.kind : "relay";
  const sources = asList(raw.sources);
  const targets = asList(raw.targets);
  const in_kzt = num(raw.in_kzt);
  const out_kzt = num(raw.out_kzt);
  let legs = Array.isArray(raw.legs) ? raw.legs.filter(l => l && l.s != null && l.t != null).map(l => ({ s: String(l.s), t: String(l.t), kzt: num(l.kzt), date: l.date })) : [];
  if (!legs.length) {
    const inEach = sources.length ? in_kzt / sources.length : 0;
    const outEach = targets.length ? out_kzt / targets.length : 0;
    legs = [
      ...sources.map(s => ({ s, t: gid, kzt: inEach, date: raw.date })),
      ...targets.map(t => ({ s: gid, t, kzt: outEach, date: raw.date })),
    ];
  }
  // Per-counterparty amounts, aggregated from legs.
  const inMap = new Map(), outMap = new Map();
  for (const l of legs) {
    if (l.t === gid && l.s !== gid) inMap.set(l.s, (inMap.get(l.s) || 0) + l.kzt);
    else if (l.s === gid && l.t !== gid) outMap.set(l.t, (outMap.get(l.t) || 0) + l.kzt);
  }
  for (const s of sources) if (!inMap.has(s)) inMap.set(s, sources.length ? in_kzt / sources.length : in_kzt);
  for (const t of targets) if (!outMap.has(t)) outMap.set(t, targets.length ? out_kzt / targets.length : out_kzt);
  const match = raw.match === "within_2pct" ? "within_2pct" : "exact";
  return {
    echo_id: String(raw.echo_id ?? `ECH-${String(i + 1).padStart(3, "0")}`),
    kind, gid, date: raw.date ?? "", lag_days: num(raw.lag_days, 0),
    in_kzt, out_kzt,
    n_sources: num(raw.n_sources, inMap.size), n_targets: num(raw.n_targets, outMap.size),
    ins: [...inMap.entries()].map(([id, kzt]) => ({ id, kzt })),
    outs: [...outMap.entries()].map(([id, kzt]) => ({ id, kzt })),
    match, score: Math.max(0, Math.min(1, num(raw.score, 0))),
    evidence: String(raw.evidence ?? ""),
    amount: Math.max(in_kzt, out_kzt),
  };
}

// ---------- dev-only mock (used ONLY when D.echoes is missing) ----------
export function _mockEchoes(D) {
  const edges = Array.isArray(D?.edges) ? D.edges : [];
  const inBy = new Map(), outBy = new Map();
  for (const e of edges) {
    if (!e || e.s == null || e.t == null) continue;
    const s = String(e.s), t = String(e.t), kzt = num(e.kzt);
    if (!outBy.has(s)) outBy.set(s, []); outBy.get(s).push({ id: t, kzt });
    if (!inBy.has(t)) inBy.set(t, []); inBy.get(t).push({ id: s, kzt });
  }
  const out = [];
  let n = 0;
  const mk = (kind, gid, ins, outs, lag, i) => ({
    echo_id: `ECH-${String(i).padStart(3, "0")}`, kind, gid,
    date: `2026-07-${String(1 + (i % 9)).padStart(2, "0")}`,
    in_kzt: ins.reduce((a, x) => a + x.kzt, 0), out_kzt: outs.reduce((a, x) => a + x.kzt, 0),
    lag_days: lag, n_sources: ins.length, n_targets: outs.length,
    sources: ins.map(x => x.id).join(" "), targets: outs.map(x => x.id).join(" "),
    match: i % 3 === 0 ? "within_2pct" : "exact", score: Math.round((0.95 - i * 0.05) * 100) / 100,
    evidence: "",
    legs: [...ins.map(x => ({ s: x.id, t: gid, kzt: x.kzt })), ...outs.map(x => ({ s: gid, t: x.id, kzt: x.kzt }))],
  });
  for (const [gid, ins] of inBy) {
    const outs = outBy.get(gid);
    if (!outs || !outs.length) continue;
    const a = ins[0].kzt;
    if (a <= 0) continue;
    if (n % 3 === 0) {           // relay
      const e = mk("relay", gid, [ins[0]], [{ id: outs[0].id, kzt: a }], n % 2, out.length + 1);
      e.evidence = `${fmtPlain(a)} KZT arrived from one account and ${fmtPlain(a)} KZT left to one receiver within ${n % 2} day(s); amounts are identical.`;
      out.push(e);
    } else if (n % 3 === 1 && outs.length >= 2) {  // split
      const k = Math.min(3, outs.length), parts = [];
      let rem = a;
      for (let j = 0; j < k; j++) { const p = j === k - 1 ? rem : Math.round(a / k); parts.push({ id: outs[j].id, kzt: p }); rem -= p; }
      const e = mk("split", gid, [ins[0]], parts, 0, out.length + 1);
      e.evidence = `${fmtPlain(a)} KZT arrived and left the same day as ${k} parts totalling ${fmtPlain(a)} KZT; the split sums exactly to the inflow.`;
      out.push(e);
    } else if (outs.length >= 3) {  // fan_split
      const k = Math.min(4, outs.length);
      const each = Math.round(outs[0].kzt);
      const e = mk("fan_split", gid, [], outs.slice(0, k).map(x => ({ id: x.id, kzt: each })), 0, out.length + 1);
      e.in_kzt = each * k;
      e.evidence = `${fmtPlain(each)} KZT was sent to each of ${k} receivers on the same day, ${fmtPlain(each * k)} KZT in total.`;
      out.push(e);
    }
    n++;
    if (out.length >= 9) break;
  }
  out.forEach(e => { e._mock = true; });
  return out;
}
function fmtPlain(n) { return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ","); }

function resolveEchoes(D) {
  if (Array.isArray(D?.echoes)) return { list: D.echoes, mock: false };
  return { list: _mockEchoes(D), mock: true };
}

// ---------- public: facts for the shell ----------
export function echoFacts(D) {
  const { list, mock } = resolveEchoes(D);
  const byKind = { relay: 0, split: 0, fan_split: 0 };
  let largestKzt = 0, largestId = null;
  list.forEach((raw, i) => {
    const e = normalise(raw, i);
    byKind[e.kind] = (byKind[e.kind] || 0) + 1;
    if (e.amount > largestKzt) { largestKzt = e.amount; largestId = e.echo_id; }
  });
  return { total: list.length, byKind, largestKzt, largestId, mock };
}

// ---------- SVG diagram ----------
function diagram(e, D, api, nodeRole) {
  const W = 340, ROW = 26, PAD = 18;
  const rows = Math.max(1, e.ins.length, e.outs.length);
  const H = Math.max(96, rows * ROW + PAD * 2 + 6);
  const cy = H / 2 - 4;
  const xL = 26, xC = W / 2, xR = W - 26;
  const role = nodeRole(e.gid);
  const colour = safeColour(api, role);
  const fmt = n => `${api.fmt(Math.round(n))} KZT`;
  const ys = k => { const h = (k - 1) * ROW; return i => cy - h / 2 + i * ROW; };
  const yIn = ys(e.ins.length), yOut = ys(e.outs.length);
  const parts = [];
  parts.push(`<defs><marker id="ech-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0,0 L8,4 L0,8 z" fill="var(--muted)"/></marker></defs>`);
  // in-lines
  e.ins.forEach((s, i) => {
    const y = yIn(i);
    const x1 = xL + 7, x2 = xC - 12;
    parts.push(`<line x1="${x1}" y1="${y}" x2="${x2}" y2="${cy}" stroke="var(--line)" stroke-width="1.2" marker-end="url(#ech-arrow)"/>`);
    const fx = x1 + 12, fy = y + (cy - y) * ((fx - x1) / (x2 - x1));
    parts.push(label(fx, fy - 6, fmt(s.kzt), "start"));
  });
  e.outs.forEach((t, i) => {
    const y = yOut(i);
    const x1 = xC + 12, x2 = xR - 7;
    parts.push(`<line x1="${x1}" y1="${cy}" x2="${x2}" y2="${y}" stroke="var(--line)" stroke-width="1.2" marker-end="url(#ech-arrow)"/>`);
    const fx = x2 - 12, fy = cy + (y - cy) * ((fx - x1) / (x2 - x1));
    parts.push(label(fx, fy - 6, fmt(t.kzt), "end"));
  });
  // side dots
  e.ins.forEach((s, i) => parts.push(dot(xL, yIn(i), 5, safeColour(api, nodeRole(s.id)), s.id, "in")));
  e.outs.forEach((t, i) => parts.push(dot(xR, yOut(i), 5, safeColour(api, nodeRole(t.id)), t.id, "out")));
  // centre
  parts.push(`<g class="ech-dot" data-gid="${esc(e.gid)}" tabindex="0" role="button"><title>${esc(e.gid)} — ${esc(role || "role unknown")}</title>` +
    `<circle cx="${xC}" cy="${cy}" r="9" fill="${colour}" stroke="var(--bg)" stroke-width="2"/>` +
    `<text x="${xC}" y="${cy + 22}" text-anchor="middle" font-family="var(--mono)" font-size="11" fill="var(--fg)">…${esc(tail(e.gid))}</text></g>`);
  return `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg" aria-label="Amount echo diagram">${parts.join("")}</svg>`;
}
function label(x, y, text, anchor = "middle") {
  return `<text x="${x}" y="${y}" text-anchor="${anchor}" font-family="var(--mono)" font-size="10" fill="var(--muted)">${esc(text)}</text>`;
}
function dot(x, y, r, colour, gid, side) {
  return `<g class="ech-dot" data-gid="${esc(gid)}" tabindex="0" role="button"><title>${esc(gid)} (${side})</title>` +
    `<circle cx="${x}" cy="${y}" r="${r}" fill="${colour}" stroke="var(--bg)" stroke-width="1.5"/></g>`;
}
function safeColour(api, role) {
  try { const c = api.roleColor?.(role); if (c) return c; } catch (_) { /* ignore */ }
  return "var(--muted)";
}

// ---------- public: mount ----------
export function mountEchoes(container, D, api) {
  injectStyle();
  api = Object.assign({ selectNode: () => {}, roleColor: () => "", fmt: n => fmtPlain(n) }, api || {});
  container.classList.add("echoes");
  container.innerHTML = "";

  const roleOf = new Map();
  for (const n of (Array.isArray(D?.nodes) ? D.nodes : [])) roleOf.set(String(n.id), n.role);
  const nodeRole = gid => roleOf.get(String(gid)) || "";

  const { list, mock } = resolveEchoes(D);
  const echoes = list.map(normalise);
  const counts = { relay: 0, split: 0, fan_split: 0 };
  echoes.forEach(e => { counts[e.kind]++; });

  const state = { on: { relay: true, split: true, fan_split: true }, sort: "score" };

  // ----- header -----
  const head = document.createElement("div");
  head.className = "ech-head";
  const countsEl = document.createElement("div");
  countsEl.className = "ech-counts";
  countsEl.innerHTML = `${plural("relay", counts.relay)} · ${plural("split", counts.split)} · ${plural("fan_split", counts.fan_split)}` +
    (mock ? `<span class="ech-mock" title="D.echoes is missing from the run payload; showing placeholder echoes built from edges">mock data</span>` : "");
  head.appendChild(countsEl);

  const tools = document.createElement("div");
  tools.className = "ech-tools";
  const chips = {};
  for (const kind of ["relay", "split", "fan_split"]) {
    const b = document.createElement("button");
    b.type = "button"; b.className = "ech-chip"; b.setAttribute("aria-pressed", "true");
    b.innerHTML = `${esc(KIND_NOUN[kind][1])}<span class="ech-n">${counts[kind]}</span>`;
    b.addEventListener("click", () => { state.on[kind] = !state.on[kind]; b.setAttribute("aria-pressed", String(state.on[kind])); renderList(); });
    chips[kind] = b; tools.appendChild(b);
  }
  const sortWrap = document.createElement("label");
  sortWrap.className = "ech-sort";
  sortWrap.innerHTML = `<span>sort</span><select><option value="score">score</option><option value="amount">amount</option><option value="date">date</option></select>`;
  sortWrap.querySelector("select").addEventListener("change", ev => { state.sort = ev.target.value; renderList(); });
  tools.appendChild(sortWrap);
  head.appendChild(tools);
  container.appendChild(head);

  // ----- list -----
  const listEl = document.createElement("div");
  listEl.className = "ech-list";
  container.appendChild(listEl);

  if (!echoes.length) {
    head.querySelector(".ech-tools").remove();
    listEl.className = "ech-empty";
    listEl.innerHTML = `No exact-amount echoes were found within the 2% tolerance: nothing in this window arrived and left again as the same amount, or went out identically to several receivers, <b>which is itself a finding</b>.`;
    return;
  }

  listEl.addEventListener("click", ev => {
    const open = ev.target.closest(".ech-open");
    if (open) { api.selectNode(open.dataset.gid); return; }
    const d = ev.target.closest(".ech-dot");
    if (d) api.selectNode(d.dataset.gid);
  });
  listEl.addEventListener("keydown", ev => {
    if (ev.key !== "Enter" && ev.key !== " ") return;
    const d = ev.target.closest?.(".ech-dot");
    if (d) { ev.preventDefault(); api.selectNode(d.dataset.gid); }
  });

  function sorted() {
    const v = echoes.filter(e => state.on[e.kind]);
    const by = {
      score: (a, b) => b.score - a.score || b.amount - a.amount,
      amount: (a, b) => b.amount - a.amount || b.score - a.score,
      date: (a, b) => String(b.date).localeCompare(String(a.date)) || b.score - a.score,
    }[state.sort] || (() => 0);
    return v.sort(by);
  }

  function renderList() {
    const v = sorted();
    if (!v.length) {
      listEl.innerHTML = `<div class="ech-empty">No echoes of the selected kinds. Turn a kind back on to see them.</div>`;
      return;
    }
    listEl.innerHTML = v.map(e => card(e)).join("");
  }

  function card(e) {
    const phrase = e.kind === "fan_split" ? `Same amount to ${e.outs.length || e.n_targets} receivers` : KIND_PHRASE[e.kind];
    const badge = e.match === "exact" ? `<span class="ech-badge exact">exact</span>` : `<span class="ech-badge">within 2%</span>`;
    const ev = e.evidence || defaultEvidence(e, api);
    return `<article class="ech-card" data-id="${esc(e.echo_id)}">
      <div class="ech-fig">${diagram(e, D, api, nodeRole)}<div>${badge}</div></div>
      <div class="ech-body">
        <div class="ech-kind">${esc(phrase)}</div>
        <div class="ech-when"><b>${esc(whenText(e))}</b>${e.in_kzt > 0 ? ` · in ${esc(api.fmt(Math.round(e.in_kzt)))}` : ""} · out ${esc(api.fmt(Math.round(e.out_kzt)))} KZT · score ${e.score.toFixed(2)}</div>
        <p class="ech-ev">${esc(ev)}</p>
        <div class="ech-foot"><button type="button" class="ech-open" data-gid="${esc(e.gid)}">Open account</button><span class="ech-id">${esc(e.echo_id)} · ${esc(e.gid)}</span></div>
      </div>
    </article>`;
  }

  renderList();
}

function defaultEvidence(e, api) {
  const f = n => api.fmt(Math.round(n));
  if (e.kind === "fan_split") return `${f(e.out_kzt)} KZT went out to ${e.outs.length} receivers in matching amounts on ${e.date || "one day"}; consistent with a single instruction, worth checking.`;
  if (e.kind === "split") return `${f(e.in_kzt)} KZT arrived and ${f(e.out_kzt)} KZT left as ${e.outs.length} parts within ${e.lag_days} day(s); worth checking whether the parts were pre-arranged.`;
  return `${f(e.in_kzt)} KZT arrived and ${f(e.out_kzt)} KZT left again within ${e.lag_days} day(s); consistent with a pass-through, worth checking.`;
}
