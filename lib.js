// Everything the dashboard shows is computed from rounds.json by the functions in this file.
// To update the dashboard, change rounds.json only. Nothing else holds data.

export const CAT_ORDER = ['Enterprise', 'Climate', 'Health', 'Fintech', 'Industry', 'Deep Tech', 'AI Infra', 'Defence & Space', 'Consumer', 'Cyber'];
export const COLORS = ['#3B4BC8', '#3E9B4F', '#D93F7A', '#E3A21A', '#8A6F4E', '#7A3FD1', '#D7352B', '#2B3A4A', '#F26B2A', '#12A5C9'];
export const TXT = ['#FFFFFF', '#FFFFFF', '#FFFFFF', '#0E1620', '#FFFFFF', '#FFFFFF', '#FFFFFF', '#FFFFFF', '#0E1620', '#0E1620'];
const EXTRA_COLORS = ['#6B7783', '#9A5B2E', '#2E7D6B', '#8B3A62'];
export const SUB_ORDER = {
  'Enterprise': ['Agents', 'Sales', 'HR', 'Legal', 'Productivity'],
  'Climate': ['Energy', 'Grid', 'Mobility', 'Materials', 'Agrifood'],
  'Health': ['Biotech', 'Medtech', 'Digital', 'Drug Discovery'],
  'Fintech': ['Payments', 'Lending', 'Insurance', 'Wealth', 'Back-office'],
  'Industry': ['Construction', 'Industrial', 'Retail', 'Property', 'Public'],
  'Deep Tech': ['Quantum', 'Chips', 'Robotics', 'Hardware'],
  'AI Infra': ['Models', 'Compute', 'Dev Tools', 'Data'],
  'Defence & Space': ['Defence', 'Drones', 'Launch', 'Satellites', 'Earth Data'],
  'Consumer': ['Apps', 'Media', 'Games', 'Education', 'Brands'],
  'Cyber': ['Threat', 'AI Security', 'Identity', 'Privacy'],
};
export const STAGES = ['Pre-Seed', 'Seed', 'Series A', 'Series B', 'Series C', 'Series D+', 'Debt', 'Grant', 'Other'];
export const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
export const FIVE = ['United Kingdom', 'Germany', 'Netherlands', 'France', 'Sweden'];
export const AMT_STEPS = [0.5, 1, 2, 5, 10, 25, 50, 100, 250, 500, 1000];
export const BANDS = [[0, 1, '< £1m'], [1, 5, '£1–5m'], [5, 10, '£5–10m'], [10, 25, '£10–25m'], [25, 50, '£25–50m'], [50, 100, '£50–100m'], [100, 250, '£100–250m'], [250, 1e9, '£250m+']];

// ---------- formatting ----------
export const sum = (a) => a.reduce((s, v) => s + v, 0);
export const fmt = (m) => (m < 0 ? 'Undisclosed' : m >= 1000 ? '£' + (m / 1000).toFixed(m >= 10000 ? 0 : 2) + 'bn' : m >= 1 ? '£' + (m >= 100 ? Math.round(m) : m.toFixed(1).replace(/\.0$/, '')) + 'm' : '£' + Math.round(m * 1000) + 'k');
export const fmtStep = (m) => (m >= 1000 ? '£' + m / 1000 + 'bn' : m >= 1 ? '£' + m + 'm' : '£' + m * 1000 + 'k');
export const fmtAxis = (m) => (m >= 1000 ? '£' + (m / 1000).toFixed(m % 1000 ? 1 : 0).replace(/\.0$/, '') + 'bn' : '£' + Math.round(m) + 'm');
export const median = (a) => { if (!a.length) return -1; const s = a.slice().sort((x, y) => x - y), h = Math.floor(s.length / 2); return s.length % 2 ? s[h] : (s[h - 1] + s[h]) / 2; };
const esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// ---------- turning rows into the compact shape the page uses ----------
export function stageOf(rt) {
  rt = rt || '';
  if (rt === 'Pre-Seed') return 0;
  if (rt.startsWith('Seed')) return 1;
  if (rt.startsWith('Series A')) return 2;
  if (rt.startsWith('Series B')) return 3;
  if (rt.startsWith('Series C')) return 4;
  if (rt.startsWith('Series')) return 5;
  if (rt === 'Debt Financing' || rt === 'Convertible Loan') return 6;
  if (rt === 'Grant') return 7;
  return 8;
}
export function primaryCountry(c) {
  for (const p of (c || '').split(',')) { const q = p.trim(); if (q && q !== 'United States' && q !== 'Europe (unspecified)') return q; }
  return 'Not specified';
}
export const yearsIn = (rows) => [...new Set(rows.map((r) => (r.month || '').slice(0, 4)).filter(Boolean))].sort().reverse();

export function prepare(rows, year) {
  const use = rows.filter((r) => r.name && r.month && r.month.startsWith(year));
  const cats = CAT_ORDER.slice(); use.forEach((r) => { const c = r.category || 'Unclassified'; if (cats.indexOf(c) < 0) cats.push(c); });
  const subsG = []; cats.forEach((c, ci) => (SUB_ORDER[c] || []).forEach((s) => subsG.push([ci, s])));
  const subIdx = (ci, s) => { let k = subsG.findIndex((x) => x[0] === ci && x[1] === s); if (k < 0) { subsG.push([ci, s || 'Other']); k = subsG.length - 1; } return k; };
  const cc = {}; use.forEach((r) => { const p = primaryCountry(r.country); cc[p] = (cc[p] || 0) + 1; });
  const countries = Object.keys(cc).filter((k) => k !== 'Not specified').sort((a, b) => cc[b] - cc[a]).concat(['Not specified']);
  const months = [...new Set(use.map((r) => r.month))].sort();
  const colors = cats.map((c, i) => (i < COLORS.length ? COLORS[i] : EXTRA_COLORS[(i - COLORS.length) % EXTRA_COLORS.length]));
  const txt = cats.map((c, i) => (i < TXT.length ? TXT[i] : '#FFFFFF'));
  const R = use.map((r) => {
    const ci = cats.indexOf(r.category || 'Unclassified');
    const c = countries.indexOf(primaryCountry(r.country));
    // rows of the same company share a key; `company_key` (set by the update pipeline) separates two different companies that share a name
    return { name: r.name, c, cat: ci, sub: subIdx(ci, r.sub), st: stageOf(r.round), amt: r.amount ? Math.round(r.amount / 1e4) / 100 : -1,
      m: months.indexOf(r.month), blurb: (r.blurb || r.desc || '').slice(0, 90), investors: r.investors || '', url: r.url || '',
      key: r.company_key || (r.name === 'Birdsview' ? r.name + '|' + c : r.name) };
  });
  const keyOf = (r) => r.key;
  const O = {}; R.forEach((r) => { (O[keyOf(r)] = O[keyOf(r)] || []).push([r.st, r.amt, r.m]); });
  Object.keys(O).forEach((k) => { if (O[k].length < 2) delete O[k]; });
  return { year, R, cats, subsG, countries, months, colors, txt, O, keyOf };
}

export const monName = (D, j) => MON[parseInt(D.months[j].slice(5), 10) - 1];

export function othersText(D, i) {
  const r = D.R[i], list = D.O[D.keyOf(r)];
  if (!list) return '';
  const rest = list.slice(); const at = rest.findIndex((o) => o[0] === r.st && o[2] === r.m && Math.abs(o[1] - r.amt) < 0.01);
  if (at >= 0) rest.splice(at, 1);
  if (!rest.length) return '';
  rest.sort((a, b) => a[2] - b[2]);
  const parts = rest.slice(0, 3).map((o) => fmt(o[1]) + (STAGES[o[0]] === 'Other' ? '' : ' ' + STAGES[o[0]]) + ' (' + monName(D, o[2]) + ')');
  return 'Also raised: ' + parts.join(', ') + (rest.length > 3 ? ' and ' + (rest.length - 3) + ' more' : '');
}

// ---------- search: plain words become filters ----------
const C_ALIAS = { uk: 'United Kingdom', 'u.k.': 'United Kingdom', britain: 'United Kingdom', british: 'United Kingdom', german: 'Germany', french: 'France', dutch: 'Netherlands', swedish: 'Sweden', swiss: 'Switzerland', spanish: 'Spain', italian: 'Italy', finnish: 'Finland', belgian: 'Belgium', danish: 'Denmark', irish: 'Ireland', austrian: 'Austria', polish: 'Poland', norwegian: 'Norway', estonian: 'Estonia', ukrainian: 'Ukraine', lithuanian: 'Lithuania', portuguese: 'Portugal', czech: 'Czechia', hungarian: 'Hungary', bulgarian: 'Bulgaria', icelandic: 'Iceland', greek: 'Greece', romanian: 'Romania', turkish: 'Turkey', croatian: 'Croatia' };
const CAT_ALIAS = { 'ai infrastructure': 'AI Infra', 'ai infra': 'AI Infra', infrastructure: 'AI Infra', infra: 'AI Infra', enterprise: 'Enterprise', saas: 'Enterprise', 'climate tech': 'Climate', climate: 'Climate', cleantech: 'Climate', healthtech: 'Health', healthcare: 'Health', health: 'Health', fintech: 'Fintech', finance: 'Fintech', industrial: 'Industry', industry: 'Industry', 'deep tech': 'Deep Tech', deeptech: 'Deep Tech', 'defence & space': 'Defence & Space', defence: 'Defence & Space', defense: 'Defence & Space', spacetech: 'Defence & Space', space: 'Defence & Space', consumer: 'Consumer', cybersecurity: 'Cyber', cyber: 'Cyber', security: 'Cyber' };
const STAGE_ALIAS = [['pre-seed', 0], ['pre seed', 0], ['preseed', 0], ['seed', 1], ['series a', 2], ['series b', 3], ['series c', 4], ['series d', 5], ['series e', 5], ['debt', 6], ['grant', 7]];
const MW = { january: 0, jan: 0, february: 1, feb: 1, march: 2, mar: 2, april: 3, apr: 3, may: 4, june: 5, jun: 5, july: 6, jul: 6, august: 7, aug: 7, september: 8, sept: 8, sep: 8, october: 9, oct: 9, november: 10, nov: 10, december: 11, dec: 11 };
const STOP = new Set(['the', 'a', 'an', 'of', 'for', 'and', 'from', 'in', 'with', 'based', 'startup', 'startups', 'company', 'companies', 'round', 'rounds', 'raised', 'raising', 'raise', 'funding', 'investment', 'that', 'which', 'are', 'is', 'to', 'by', 'on', 'at', 'show', 'me', 'all', 'biggest', 'largest']);

export function parseQuery(D, q) {
  const o = { countries: new Set(), cats: new Set(), subs: new Set(), stages: new Set(), min: 0, max: Infinity, m0: 0, m1: 99, chips: [], tokens: [] };
  if (!q.trim()) return o;
  let s = ' ' + q.toLowerCase().replace(/[£,]/g, '').replace(/\bmillion\b/g, 'm').replace(/\bbillion\b/g, 'bn').replace(/\bthousand\b/g, 'k') + ' ';
  s = s.replace(/between\s+(\d+(?:\.\d+)?)\s*(k|m|bn)?\s+and\s+(\d+(?:\.\d+)?)\s*(k|m|bn)?/g, ' $1$2-$3$4 ');
  const unit = (u) => (u === 'bn' ? 1000 : u === 'k' ? 0.001 : 1);
  let m = /(\d+(?:\.\d+)?)\s*(k|m|bn)?\s*(?:-|–|to)\s*(\d+(?:\.\d+)?)\s*(k|m|bn)?/.exec(s);
  if (m) {
    const u2 = m[4] || m[2] || 'm', u1 = m[2] || u2;
    o.min = parseFloat(m[1]) * unit(u1); o.max = parseFloat(m[3]) * unit(u2);
    if (o.min > o.max) { const t = o.min; o.min = o.max; o.max = t; }
    s = s.replace(m[0], ' ');
  } else {
    m = /(?:>|over|above|more than|at least|minimum|min)\s*(\d+(?:\.\d+)?)\s*(k|m|bn)?/.exec(s);
    if (m) { o.min = parseFloat(m[1]) * unit(m[2] || 'm'); s = s.replace(m[0], ' '); }
    m = /(?:<|under|below|less than|up to|maximum|max)\s*(\d+(?:\.\d+)?)\s*(k|m|bn)?/.exec(s);
    if (m) { o.max = parseFloat(m[1]) * unit(m[2] || 'm'); s = s.replace(m[0], ' '); }
  }
  if (o.min > 0 || o.max < Infinity) o.chips.push((o.min > 0 ? fmtStep(o.min) : 'any') + ' – ' + (o.max < Infinity ? fmtStep(o.max) : 'any size'));
  const qm = /\bq([1-4])\b/.exec(s);
  if (qm) { const n = parseInt(qm[1], 10); o.m0 = (n - 1) * 3; o.m1 = n * 3 - 1; o.chips.push('Q' + n); s = s.replace(qm[0], ' '); }
  const mre = new RegExp('\\b(' + Object.keys(MW).join('|') + ')\\b', 'g'); let mm; const ms = [];
  while ((mm = mre.exec(s))) ms.push(MW[mm[1]]);
  if (ms.length) { o.m0 = Math.min(...ms); o.m1 = Math.max(...ms); o.chips.push(MON[o.m0] + (o.m1 !== o.m0 ? '–' + MON[o.m1] : '')); s = s.replace(mre, ' '); }
  STAGE_ALIAS.forEach((a) => { const re = new RegExp('(^|[^a-z-])' + esc(a[0]) + '(?![a-z-])'); if (re.test(s)) { o.stages.add(a[1]); s = s.replace(re, ' '); } });
  o.stages.forEach((i) => o.chips.push(STAGES[i]));
  const cal = Object.keys(C_ALIAS).map((k) => [k, C_ALIAS[k]]).concat(D.countries.map((c) => [c.toLowerCase(), c]));
  cal.sort((a, b) => b[0].length - a[0].length).forEach((a) => {
    const ci = D.countries.indexOf(a[1]); if (ci < 0) return;
    const re = new RegExp('(^|[^a-z])' + esc(a[0]) + '(?![a-z])');
    if (re.test(s)) { if (!o.countries.has(ci)) o.chips.push(a[1]); o.countries.add(ci); s = s.replace(re, ' '); }
  });
  Object.keys(CAT_ALIAS).sort((a, b) => b.length - a.length).forEach((k) => {
    const re = new RegExp('(^|[^a-z])' + esc(k) + '(?![a-z])'); const ci = D.cats.indexOf(CAT_ALIAS[k]); if (ci < 0) return;
    if (re.test(s)) { if (!o.cats.has(ci)) o.chips.push(D.cats[ci]); o.cats.add(ci); s = s.replace(re, ' '); }
  });
  D.subsG.forEach((sg, i) => {
    const re = new RegExp('(^|[^a-z])' + esc(sg[1].toLowerCase()) + '(?![a-z])');
    if (re.test(s)) { o.subs.add(i); o.chips.push(D.cats[sg[0]] + ' › ' + sg[1]); s = s.replace(re, ' '); }
  });
  o.tokens = s.split(/[^a-z0-9.+-]+/).filter((t) => t.length > 1 && !STOP.has(t));
  o.tokens.forEach((t) => o.chips.push('“' + t + '”'));
  return o;
}

export const emptyFilters = (D) => ({ countries: [], cats: [], subs: [], stages: [], min: 0, max: -1, m0: 0, m1: Math.max(0, D.months.length - 1) });

export function makeFilter(f, par) {
  const A = { countries: new Set(f.countries), cats: new Set(f.cats), subs: new Set(f.subs), stages: new Set(f.stages), min: f.min, max: f.max < 0 ? Infinity : f.max, m0: f.m0, m1: f.m1 };
  const B = par, lo = Math.max(A.min, B.min), hi = Math.min(A.max, B.max), m0 = Math.max(A.m0, B.m0), m1 = Math.min(A.m1, B.m1);
  const inS = (a, b, v) => (a.size === 0 || a.has(v)) && (b.size === 0 || b.has(v));
  return (r, skip) => {
    if (skip !== 'country' && !inS(A.countries, B.countries, r.c)) return false;
    if (skip !== 'cat' && !inS(A.cats, B.cats, r.cat)) return false;
    if (skip !== 'sub' && !inS(A.subs, B.subs, r.sub)) return false;
    if (skip !== 'stage' && !inS(A.stages, B.stages, r.st)) return false;
    if (skip !== 'amt' && (lo > 0 || hi < Infinity)) { if (r.amt < 0 || r.amt < lo || r.amt > hi) return false; }
    if (skip !== 'month' && (r.m < m0 || r.m > m1)) return false;
    if (B.tokens.length) { const hay = (r.name + ' ' + r.blurb).toLowerCase(); for (let i = 0; i < B.tokens.length; i++) if (hay.indexOf(B.tokens[i]) < 0) return false; }
    return true;
  };
}

// ---------- chart maths ----------
export function axisFor(maxV, steps) {
  for (let k = 0; k < steps.length; k++) if (Math.ceil(maxV / steps[k]) <= 8) return { step: steps[k], top: Math.max(1, Math.ceil(maxV / steps[k])) * steps[k] };
  const s = steps[steps.length - 1]; return { step: s, top: Math.ceil(maxV / s) * s };
}

export function squarify(items, x, y, w, h) {
  const total = sum(items.map((i) => i.v)); if (total <= 0 || w <= 0 || h <= 0) return [];
  const nodes = items.map((i) => ({ ...i, a: (i.v / total) * w * h })), out = [];
  const worst = (row, side) => { const s = sum(row.map((n) => n.a)), mx = Math.max(...row.map((n) => n.a)), mn = Math.min(...row.map((n) => n.a)); return Math.max((side * side * mx) / (s * s), (s * s) / (side * side * mn)); };
  let rx = x, ry = y, rw = w, rh = h;
  while (nodes.length) {
    const side = Math.min(rw, rh), row = [nodes.shift()];
    while (nodes.length && worst(row.concat([nodes[0]]), side) <= worst(row, side)) row.push(nodes.shift());
    const area = sum(row.map((n) => n.a));
    if (rw >= rh) { const cw = area / rh; let cy = ry; row.forEach((n) => { const nh = n.a / cw; out.push({ ...n, x: rx, y: cy, w: cw, h: nh }); cy += nh; }); rx += cw; rw -= cw; }
    else { const rhh = area / rw; let cx = rx; row.forEach((n) => { const nw = n.a / rhh; out.push({ ...n, x: cx, y: ry, w: nw, h: rhh }); cx += nw; }); ry += rhh; rh -= rhh; }
  }
  return out;
}

export function arcPath(cx, cy, r0, r1, a0, a1) {
  if (a1 - a0 >= 359.99) a1 = a0 + 359.99;
  const p = (r, a) => { const t = ((a - 90) * Math.PI) / 180; return [(cx + r * Math.cos(t)).toFixed(2), (cy + r * Math.sin(t)).toFixed(2)]; };
  const s0 = p(r1, a0), e0 = p(r1, a1), s1 = p(r0, a1), e1 = p(r0, a0), big = a1 - a0 > 180 ? 1 : 0;
  return 'M' + s0[0] + ' ' + s0[1] + 'A' + r1 + ' ' + r1 + ' 0 ' + big + ' 1 ' + e0[0] + ' ' + e0[1] + 'L' + s1[0] + ' ' + s1[1] + 'A' + r0 + ' ' + r0 + ' 0 ' + big + ' 0 ' + e1[0] + ' ' + e1[1] + 'Z';
}

// treemap of sectors (header band on top) with every sub-sector labelled; tiny ones are grouped as "Other (n)"
export function buildTreemap(D, catV, subV, fmtV, aCat) {
  const TW = 1100, TH = 600, totV = sum(catV), pc = (v, t) => (v / t) * 100 + '%';
  const sq = squarify(D.cats.map((c, i) => ({ i, v: catV[i] })).filter((c) => c.v > 0).sort((a, b) => b.v - a.v), 0, 0, TW, TH);
  const tiles = [], subTiles = [];
  sq.forEach((t) => {
    const name = D.cats[t.i], dim = aCat >= 0 && aCat !== t.i, withSubs = t.w >= 120 && t.h >= 120, light = D.txt[t.i] === '#FFFFFF';
    const fs = Math.max(11, Math.min(19, (t.w - 24) / (name.length * 0.72))), hh = withSubs ? Math.round(fs * 1.2 + 40) : t.h;
    tiles.push({ i: t.i, l: pc(t.x, TW), t: pc(t.y, TH), w: pc(t.w, TW), h: pc(t.h, TH), bg: D.colors[t.i], op: dim ? 0.3 : 1, fg: D.txt[t.i], hbg: light ? 'rgba(14,22,32,0.24)' : 'rgba(255,255,255,0.34)', name, fs: fs.toFixed(1),
      val: t.h > 44 || withSubs ? fmtV(t.v) + ' · ' + Math.round((t.v / totV) * 100) + '%' : '', title: name + ' · ' + fmtV(t.v) + ' · ' + Math.round((t.v / totV) * 100) + '% · click to highlight' });
    if (!withSubs) return;
    const bx = t.x + 5, by = t.y + hh, bw = t.w - 10, bh = t.h - hh - 5, area = bw * bh;
    const items = D.subsG.map((sg, k) => ({ k, c: sg[0], v: subV[k] })).filter((x) => x.c === t.i && x.v > 0).sort((a, b) => b.v - a.v);
    const tot = sum(items.map((x) => x.v)), keep = items.filter((x) => (x.v / tot) * area >= 4800), small = items.filter((x) => (x.v / tot) * area < 4800);
    const list = keep.map((x) => ({ k: x.k, v: x.v, label: D.subsG[x.k][1] }));
    if (small.length === 1) list.push({ k: small[0].k, v: small[0].v, label: D.subsG[small[0].k][1] });
    else if (small.length > 1) list.push({ k: -1, v: sum(small.map((x) => x.v)), label: 'Other (' + small.length + ')', tip: small.map((x) => D.subsG[x.k][1]).join(', ') });
    list.sort((a, b) => b.v - a.v);
    squarify(list, bx, by, bw, bh).forEach((u) => subTiles.push({ l: pc(u.x, TW), t: pc(u.y, TH), w: pc(u.w, TW), h: pc(u.h, TH), label: u.label, val: u.h > 46 && u.w > 70 ? fmtV(u.v) : '', fg: D.txt[t.i], fill: light ? 'rgba(255,255,255,0.20)' : 'rgba(14,22,32,0.14)', line: light ? 'rgba(255,255,255,0.55)' : 'rgba(14,22,32,0.4)', op: dim ? 0.3 : 1, title: (u.tip || u.label) + ' · ' + fmtV(u.v) }));
  });
  return { tiles, subTiles };
}
