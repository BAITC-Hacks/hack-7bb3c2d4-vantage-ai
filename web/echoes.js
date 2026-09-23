// echoes.js — "Amount echoes" section for the review screen.
// ES module, no dependencies. Exports mountEchoes(container, D, api) and echoFacts(D).
//
// An echo is a hypothesis for an analyst to check: an exact amount arriving at an
// account and leaving again (relay), leaving split into parts (split), or one account
// sending the identical amount to several receivers on one day (fan_split).

// ---------- i18n ----------
// api.lang is "en" | "ru" | "kk" (default "en"). Every user-facing string lives here;
// the `evidence` field that arrives in the payload is pipeline English and is shown as is.
const T = {
  en: {
    locale: "en-GB",
    // count nouns: [one, other]; pluralForm() picks the form
    count_relay: ["relay", "relays"],
    count_split: ["split", "splits"],
    count_fan_split: ["same-amount fan-out", "same-amount fan-outs"],
    // filter chips
    chip_relay: "relays",
    chip_split: "splits",
    chip_fan_split: "same-amount fan-outs",
    sort: "sort",
    sort_score: "score",
    sort_amount: "amount",
    sort_date: "date",
    kind_relay: "Same amount in and out",
    kind_split: "One amount in, split on the way out",
    kind_fan_split: "Same amount to {n} receivers",
    badge_exact: "exact",
    badge_within: "within 2%",
    same_day: "same day",
    next_day: "next day",
    date_unknown: "date unknown",
    in: "in",
    out: "out",
    score: "score",
    open_account: "Open account",
    empty: "No exact-amount echoes were found within the 2% tolerance: nothing in this window arrived and left again as the same amount, or went out identically to several receivers, <b>which is itself a finding</b>.",
    empty_filtered: "No echoes of the selected kinds. Turn a kind back on to see them.",
    mock: "mock data",
    mock_title: "D.echoes is missing from the run payload; showing placeholder echoes built from edges",
    diagram_label: "Amount echo diagram",
    role_unknown: "role unknown",
    side_in: "in",
    side_out: "out",
    one_day: "one day",
    ev_fan_split: "{out} KZT went out to {n} receivers in matching amounts on {date}; consistent with a single instruction, worth checking.",
    ev_split: "{in} KZT arrived and {out} KZT left as {n} parts within {d} day(s); worth checking whether the parts were pre-arranged.",
    ev_relay: "{in} KZT arrived and {out} KZT left again within {d} day(s); consistent with a pass-through, worth checking.",
  },
  ru: {
    locale: "ru-RU",
    // count nouns: [1, 2–4, 5+]
    count_relay: ["транзит", "транзита", "транзитов"],
    count_split: ["дробление", "дробления", "дроблений"],
    count_fan_split: ["веерный платёж", "веерных платежа", "веерных платежей"],
    chip_relay: "транзиты",
    chip_split: "дробления",
    chip_fan_split: "веерные платежи",
    sort: "сортировка",
    sort_score: "оценка",
    sort_amount: "сумма",
    sort_date: "дата",
    kind_relay: "Та же сумма вошла и вышла",
    kind_split: "Одна сумма вошла, вышла частями",
    kind_fan_split: "Одна и та же сумма {n} получателям",
    badge_exact: "точно",
    badge_within: "в пределах 2%",
    same_day: "в тот же день",
    next_day: "на следующий день",
    date_unknown: "дата неизвестна",
    in: "вход",
    out: "выход",
    score: "оценка",
    open_account: "Открыть счёт",
    empty: "Точных повторов суммы в пределах допуска 2% не найдено: в этом окне ни одна сумма не пришла и не ушла в том же размере и не разошлась одинаковыми частями нескольким получателям, <b>что само по себе является наблюдением</b>.",
    empty_filtered: "Нет повторов выбранных типов. Включите тип снова, чтобы их увидеть.",
    mock: "тестовые данные",
    mock_title: "В данных прогона нет D.echoes; показаны заглушки, построенные по рёбрам графа",
    diagram_label: "Схема повтора суммы",
    role_unknown: "роль неизвестна",
    side_in: "вход",
    side_out: "выход",
    one_day: "в один день",
    ev_fan_split: "{out} KZT ушли {n} получателям одинаковыми суммами {date}; похоже на единое поручение, стоит проверить.",
    ev_split: "{in} KZT поступили и {out} KZT ушли {n} частями в течение {d} дн.; стоит проверить, было ли дробление согласовано заранее.",
    ev_relay: "{in} KZT поступили и {out} KZT ушли в течение {d} дн.; похоже на транзит, стоит проверить.",
  },
  kk: {
    locale: "kk-KZ",
    // Kazakh nouns stay singular after a numeral: one form
    count_relay: ["транзит"],
    count_split: ["бөлшектеу"],
    count_fan_split: ["бірдей сомамен тарату"],
    chip_relay: "транзиттер",
    chip_split: "бөлшектеулер",
    chip_fan_split: "бірдей сомамен таратулар",
    sort: "сұрыптау",
    sort_score: "балл",
    sort_amount: "сома",
    sort_date: "күні",
    kind_relay: "Сол сома кірді және шықты",
    kind_split: "Бір сома кірді, бөліктерге бөлініп шықты",
    kind_fan_split: "Бірдей сома {n} алушыға",
    badge_exact: "дәл",
    badge_within: "2% шегінде",
    same_day: "сол күні",
    next_day: "келесі күні",
    date_unknown: "күні белгісіз",
    in: "кіріс",
    out: "шығыс",
    score: "балл",
    open_account: "Шотты ашу",
    empty: "2% шегінде дәл қайталанған сома табылмады: бұл кезеңде бірде-бір сома сол мөлшерде кіріп қайта шықпаған және бірнеше алушыға бірдей мөлшерде жіберілмеген, <b>бұл өзі де маңызды қорытынды</b>.",
    empty_filtered: "Таңдалған түрлердегі қайталанулар жоқ. Көру үшін түрін қайта қосыңыз.",
    mock: "тестілік деректер",
    mock_title: "Іске қосу деректерінде D.echoes жоқ; графтың қырлары бойынша құрылған уақытша үлгілер көрсетілген",
    diagram_label: "Сома қайталануының сызбасы",
    role_unknown: "рөлі белгісіз",
    side_in: "кіріс",
    side_out: "шығыс",
    one_day: "бір күнде",
    ev_fan_split: "{out} KZT {date} {n} алушыға бірдей сомалармен жіберілген; бір нұсқауға ұқсайды, тексерген жөн.",
    ev_split: "{in} KZT кірді және {out} KZT {n} бөлікпен {d} күн ішінде шықты; бөліктердің алдын ала келісілгенін тексерген жөн.",
    ev_relay: "{in} KZT кірді және {out} KZT {d} күн ішінде қайта шықты; транзитке ұқсайды, тексерген жөн.",
  },
};
const t = (k, lang) => (T[lang] || T.en)[k] ?? T.en[k] ?? k;
// "{name}" placeholders → values
const fill = (s, vars) => String(s).replace(/\{(\w+)\}/g, (_, k) => (vars[k] ?? `{${k}}`));
// Pick the noun form for n. en: [one, other]; ru: [1, 2–4, 5+] (11–14 → 5+); kk: single form.
function pluralForm(lang, n, forms) {
  n = Math.abs(Math.round(n));
  if (lang === "ru" && forms.length >= 3) {
    const m10 = n % 10, m100 = n % 100;
    if (m10 === 1 && m100 !== 11) return forms[0];
    if (m10 >= 2 && m10 <= 4 && (m100 < 12 || m100 > 14)) return forms[1];
    return forms[2];
  }
  if (lang === "kk") return forms[0];
  return n === 1 ? forms[0] : forms[forms.length - 1];
}

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
// "5 July" / "5 июля" / "5 шілде". Dates are UTC-constructed, so format in UTC too.
function dayMonth(d, locale) {
  try { return d.toLocaleDateString(locale, { day: "numeric", month: "long", timeZone: "UTC" }); }
  catch (_) { return d.toLocaleDateString("en-GB", { day: "numeric", month: "long", timeZone: "UTC" }); }
}
function whenText(e, tr, locale) {
  const d0 = parseDate(e.date);
  if (!d0) return e.date ? String(e.date) : tr("date_unknown");
  const lag = Math.max(0, Math.round(num(e.lag_days, 0)));
  if (lag === 0) return `${dayMonth(d0, locale)}, ${tr("same_day")}`;
  if (lag === 1) return `${dayMonth(d0, locale)}, ${tr("next_day")}`;
  const d1 = new Date(d0.getTime() + lag * 86400000);
  // same month: "5–8 July" — the day of d0 in front of the formatted d1
  if (d1.getUTCMonth() === d0.getUTCMonth()) return `${d0.getUTCDate()}–${dayMonth(d1, locale)}`;
  return `${dayMonth(d0, locale)} – ${dayMonth(d1, locale)}`;
}
// "135 relays" / "135 транзитов" / "135 транзит"
function countLabel(kind, n, tr, lang) { return `${n} ${pluralForm(lang, n, tr("count_" + kind))}`; }

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
function diagram(e, D, api, nodeRole, tr) {
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
  e.ins.forEach((s, i) => parts.push(dot(xL, yIn(i), 5, safeColour(api, nodeRole(s.id)), s.id, tr("side_in"))));
  e.outs.forEach((o, i) => parts.push(dot(xR, yOut(i), 5, safeColour(api, nodeRole(o.id)), o.id, tr("side_out"))));
  // centre
  parts.push(`<g class="ech-dot" data-gid="${esc(e.gid)}" tabindex="0" role="button"><title>${esc(e.gid)} — ${esc(role || tr("role_unknown"))}</title>` +
    `<circle cx="${xC}" cy="${cy}" r="9" fill="${colour}" stroke="var(--bg)" stroke-width="2"/>` +
    `<text x="${xC}" y="${cy + 22}" text-anchor="middle" font-family="var(--mono)" font-size="11" fill="var(--fg)">…${esc(tail(e.gid))}</text></g>`);
  return `<svg viewBox="0 0 ${W} ${H}" width="${W}" height="${H}" xmlns="http://www.w3.org/2000/svg" aria-label="${esc(tr("diagram_label"))}">${parts.join("")}</svg>`;
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
  const lang = T[api.lang] ? api.lang : "en";
  const tr = k => t(k, lang);
  const locale = tr("locale");
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
  countsEl.innerHTML = `${esc(countLabel("relay", counts.relay, tr, lang))} · ${esc(countLabel("split", counts.split, tr, lang))} · ${esc(countLabel("fan_split", counts.fan_split, tr, lang))}` +
    (mock ? `<span class="ech-mock" title="${esc(tr("mock_title"))}">${esc(tr("mock"))}</span>` : "");
  head.appendChild(countsEl);

  const tools = document.createElement("div");
  tools.className = "ech-tools";
  const chips = {};
  for (const kind of ["relay", "split", "fan_split"]) {
    const b = document.createElement("button");
    b.type = "button"; b.className = "ech-chip"; b.setAttribute("aria-pressed", "true");
    b.innerHTML = `${esc(tr("chip_" + kind))}<span class="ech-n">${counts[kind]}</span>`;
    b.addEventListener("click", () => { state.on[kind] = !state.on[kind]; b.setAttribute("aria-pressed", String(state.on[kind])); renderList(); });
    chips[kind] = b; tools.appendChild(b);
  }
  const sortWrap = document.createElement("label");
  sortWrap.className = "ech-sort";
  sortWrap.innerHTML = `<span>${esc(tr("sort"))}</span><select><option value="score">${esc(tr("sort_score"))}</option><option value="amount">${esc(tr("sort_amount"))}</option><option value="date">${esc(tr("sort_date"))}</option></select>`;
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
    listEl.innerHTML = tr("empty"); // contains the <b> emphasis, intentionally not escaped
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
      listEl.innerHTML = `<div class="ech-empty">${esc(tr("empty_filtered"))}</div>`;
      return;
    }
    listEl.innerHTML = v.map(e => card(e)).join("");
  }

  function card(e) {
    const phrase = e.kind === "fan_split" ? fill(tr("kind_fan_split"), { n: e.outs.length || e.n_targets }) : tr("kind_" + e.kind);
    const badge = e.match === "exact" ? `<span class="ech-badge exact">${esc(tr("badge_exact"))}</span>` : `<span class="ech-badge">${esc(tr("badge_within"))}</span>`;
    const ev = e.evidence || defaultEvidence(e, api, tr);
    return `<article class="ech-card" data-id="${esc(e.echo_id)}">
      <div class="ech-fig">${diagram(e, D, api, nodeRole, tr)}<div>${badge}</div></div>
      <div class="ech-body">
        <div class="ech-kind">${esc(phrase)}</div>
        <div class="ech-when"><b>${esc(whenText(e, tr, locale))}</b>${e.in_kzt > 0 ? ` · ${esc(tr("in"))} ${esc(api.fmt(Math.round(e.in_kzt)))}` : ""} · ${esc(tr("out"))} ${esc(api.fmt(Math.round(e.out_kzt)))} KZT · ${esc(tr("score"))} ${e.score.toFixed(2)}</div>
        <p class="ech-ev">${esc(ev)}</p>
        <div class="ech-foot"><button type="button" class="ech-open" data-gid="${esc(e.gid)}">${esc(tr("open_account"))}</button><span class="ech-id">${esc(e.echo_id)} · ${esc(e.gid)}</span></div>
      </div>
    </article>`;
  }

  renderList();
}

// Fallback sentence when the payload carries no evidence string.
function defaultEvidence(e, api, tr) {
  const f = n => api.fmt(Math.round(n));
  const vars = { in: f(e.in_kzt), out: f(e.out_kzt), n: e.outs.length, d: e.lag_days, date: e.date || tr("one_day") };
  if (e.kind === "fan_split") return fill(tr("ev_fan_split"), vars);
  if (e.kind === "split") return fill(tr("ev_split"), vars);
  return fill(tr("ev_relay"), vars);
}
