import React, { useState, useMemo } from 'react';
import ROUNDS from './rounds.json';
import GEO from './europe-map.json';
import STATUS from './status.json';
import {
  STAGES, MON, FIVE, AMT_STEPS, BANDS, sum, fmt, fmtStep, fmtAxis, median, yearsIn, prepare, monName, othersText, parseQuery, emptyFilters, makeFilter,
  axisFor, arcPath, buildTreemap,
} from './lib.js';

const INK = '#0E1620', BG = '#E4E9EE', CARD = '#F3F6F8', MUTED = '#46525E', LINE = '#A9B3BD', ACCENT = '#E4572E';
const disp = (size, weight = 800, ls = '-0.02em') => ({ fontFamily: "'Montserrat', sans-serif", fontWeight: weight, fontSize: size, letterSpacing: ls, lineHeight: 1.1 });
const mono = (size = 12, extra = {}) => ({ fontFamily: "'DM Mono', monospace", fontSize: size, ...extra });
const eyebrow = { ...mono(13), fontWeight: 500, letterSpacing: '0.14em', textTransform: 'uppercase', color: MUTED };
const label = { ...mono(12), fontWeight: 500, letterSpacing: '0.14em', textTransform: 'uppercase', color: MUTED };
const wrap = { maxWidth: 1320, margin: '0 auto', padding: '0 40px', boxSizing: 'border-box' };
const selectStyle = { flex: 1, minWidth: 0, minHeight: 42, border: `1.5px solid ${INK}`, background: CARD, fontSize: 14, padding: '0 8px', color: INK };
const CARDS = [['01', 'The state of'], ['02', 'Analytics'], ['03', 'Funding map']];
const fmtDay = (iso) => new Date(iso + 'T00:00:00Z').toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });

const Pill = ({ on, onClick, children, size = 36, extra }) => (
  <button type="button" onClick={onClick} aria-pressed={on} style={{ display: 'inline-flex', alignItems: 'center', gap: 8, minHeight: size, padding: '0 12px', border: `1.5px solid ${INK}`, background: on ? INK : CARD, color: on ? BG : INK, fontSize: 13, fontWeight: 500, cursor: 'pointer', borderRadius: 99, ...extra }}>{children}</button>
);
const Cnt = ({ children }) => <span style={{ ...mono(11), opacity: 0.75 }}>{children}</span>;
const Swatch = ({ color, size = 9, ring }) => <span style={{ width: size, height: size, borderRadius: '50%', background: color, flex: 'none', boxShadow: ring ? `0 0 0 1.5px ${ring}` : 'none' }} />;
const H2 = ({ children, size = 'clamp(30px,4.6vw,62px)' }) => <h2 style={{ margin: '14px 0 0', fontFamily: "'Montserrat', sans-serif", fontWeight: 800, fontSize: size, lineHeight: 1, letterSpacing: '-0.03em' }}>{children}</h2>;
const H3 = ({ children, size = 22, style }) => <h3 style={{ margin: 0, ...disp(size), ...style }}>{children}</h3>;
const Btn = ({ onClick, children, solid = true }) => (
  <button type="button" onClick={onClick} style={{ minHeight: 52, padding: '0 28px', border: `2px solid ${INK}`, background: solid ? INK : 'transparent', color: solid ? BG : INK, fontFamily: "'Montserrat', sans-serif", fontWeight: 800, fontSize: 14, cursor: 'pointer' }}>{children}</button>
);

export default function FundingDashboard() {
  const years = useMemo(() => yearsIn(ROUNDS), []);
  const [year, setYear] = useState(years[0]);
  const D = useMemo(() => prepare(ROUNDS, year), [year]);
  return <Dashboard key={year} D={D} years={years} year={year} setYear={setYear} />;
}

function Dashboard({ D, years, year, setYear }) {
  const [card, setCard] = useState(0);
  const [q, setQ] = useState('');
  const [f, setF] = useState(() => emptyFilters(D));
  const [show, setShow] = useState(6);
  const [sel, setSel] = useState(-1);
  const [tab, setTab] = useState('capital');
  const [metric, setMetric] = useState('capital');
  const [profC, setProfC] = useState('United Kingdom');
  const [aCat, setACat] = useState(-1);
  const [seg, setSeg] = useState(null);
  const [hoverC, setHoverC] = useState(-1);
  const [mapSel, setMapSel] = useState(-1);
  // Hero animation. Full by default. If the device asks for reduced motion we show a calm version (slow glow and dim, nothing flying or drifting)
  // instead of a frozen picture. The visitor can pause it, or switch to the full version, with the button.
  const reduced = useMemo(() => typeof window !== 'undefined' && !!window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches, []);
  const [mode, setMode] = useState(() => { try { const m = window.localStorage.getItem('fd-motion'); if (m === 'full' || m === 'calm' || m === 'off') return m; } catch (e) { /* ignore */ } return reduced ? 'calm' : 'full'; });
  const full = mode === 'full', calm = mode === 'calm';
  const onMotionClick = () => { const nm = full ? 'off' : 'full'; setMode(nm); try { window.localStorage.setItem('fd-motion', nm); } catch (e) { /* ignore */ } };

  const { R, cats, subsG, countries, months, colors, txt } = D;
  const N = R.length, nm = months.length;
  const go = (i) => { setCard(i); try { const el = document.getElementById('deck-top'); if (el && el.scrollIntoView) el.scrollIntoView({ behavior: 'smooth', block: 'start' }); } catch (e) { /* ignore */ } };

  // ================= CARD 1: THE STATE OF THE YEAR (the only part the filters touch) =================
  const par = useMemo(() => parseQuery(D, q), [D, q]);
  const pass = useMemo(() => makeFilter(f, par), [f, par]);
  const match = useMemo(() => { const out = []; for (let i = 0; i < N; i++) if (pass(R[i], '')) out.push(i); return out; }, [pass, R, N]);
  const facet = (skip, get, size) => { const c = new Array(size).fill(0); for (let i = 0; i < N; i++) if (pass(R[i], skip)) c[get(R[i])]++; return c; };
  const cCnt = facet('country', (r) => r.c, countries.length), catCnt = facet('cat', (r) => r.cat, cats.length), subCnt = facet('sub', (r) => r.sub, subsG.length), stCnt = facet('stage', (r) => r.st, STAGES.length);
  const known = match.filter((i) => R[i].amt >= 0), raised = sum(known.map((i) => R[i].amt));
  let big = -1; match.forEach((i) => { if (big < 0 || R[i].amt > R[big].amt) big = i; });
  const inM = new Set(match);

  const lay = useMemo(() => {
    const colW = 1040 / nm, step = 8.6, per = Math.max(4, Math.floor((colW - 14) / step)), off = (colW - (per - 1) * step) / 2, byM = months.map(() => []);
    R.forEach((r, i) => byM[r.m].push(i));
    const maxRows = Math.max(1, ...byM.map((l) => Math.ceil(l.length / per))), baseY = maxRows * step + 22, pos = new Array(N);
    byM.forEach((list, j) => { list.sort((a, b) => R[a].cat - R[b].cat || R[b].amt - R[a].amt || a - b); list.forEach((idx, n) => { pos[idx] = [j * colW + off + (n % per) * step, baseY - Math.floor(n / per) * step]; }); });
    return { pos, baseY, H: baseY + 16 };
  }, [R, months, nm, N]);

  const mcount = months.map(() => 0); match.forEach((i) => mcount[R[i].m]++);
  const order = match.slice().sort((a, b) => R[b].amt - R[a].amt);
  const topC = countries.map((c, i) => i).filter((i) => countries[i] !== 'Not specified').slice(0, 11);
  f.countries.forEach((i) => { if (topC.indexOf(i) < 0) topC.push(i); });
  const toggle = (key, v) => {
    const cur = f[key].slice(), at = cur.indexOf(v); if (at >= 0) cur.splice(at, 1); else cur.push(v);
    const nf = { ...f, [key]: cur }; if (key === 'cats') nf.subs = nf.subs.filter((s) => cur.indexOf(subsG[s][0]) >= 0);
    setF(nf); setShow(6);
  };
  const setAmt = (lo, hi) => { setF({ ...f, min: lo, max: hi }); setShow(6); };
  const PRE = [['Under £1m', 0, 1], ['£1–10m', 1, 10], ['£10–100m', 10, 100], ['£100m–1bn', 100, 1000], ['£1bn+', 1000, -1]];
  const EXAMPLES = ['UK infrastructure startups raising £10–100m', 'German defence seed rounds', 'Fintech series A under £20m', 'Biggest climate rounds in Q3'];
  const selR = sel >= 0 ? R[sel] : null, selOthers = selR ? othersText(D, sel) : '';

  // ================= CARD 2: ANALYTICS (independent: always every round) =================
  const ALL = useMemo(() => R.map((r, i) => i), [R]);
  const val = (r) => (metric === 'capital' ? Math.max(r.amt, 0) : 1);
  const allKnown = ALL.filter((i) => R[i].amt >= 0), allRaised = sum(allKnown.map((i) => R[i].amt));
  const stack = cats.map(() => months.map(() => 0)); R.forEach((r) => { stack[r.cat][r.m] += val(r); });
  const colTot = months.map((m, j) => sum(cats.map((c, ci) => stack[ci][j])));
  const ax = metric === 'capital' ? axisFor(Math.max(14000, ...colTot), [2000, 5000]) : axisFor(Math.max(1, ...colTot), [5, 10, 20, 50, 100]);
  const topV = ax.top, nTicks = Math.round(topV / ax.step), ticks = []; for (let k = 0; k <= nTicks; k++) ticks.push({ pct: (k / nTicks) * 100 + '%', t: metric === 'capital' ? (k === 0 ? '£0' : fmtAxis(k * ax.step)) : String(k * ax.step) });
  const fmtV = (v) => (metric === 'capital' ? fmt(v) : v + ' rounds');
  const shareTxt = (v, t) => Math.round((v / Math.max(t, 1)) * 100) + '%';
  let readout = null;
  if (seg) { const v = stack[seg.c][seg.m]; readout = { name: cats[seg.c], color: colors[seg.c], line: monName(D, seg.m) + ' · ' + fmtV(v) + ' · ' + shareTxt(v, colTot[seg.m]) + ' of that month' }; }
  else if (aCat >= 0) { const tv = sum(stack[aCat]); readout = { name: cats[aCat], color: colors[aCat], line: 'All months · ' + fmtV(tv) + ' · ' + shareTxt(tv, sum(colTot)) + ' of the total' }; }
  const bandCount = BANDS.map(() => 0), bandCap = BANDS.map(() => 0);
  allKnown.forEach((i) => { const a = R[i].amt; for (let b = 0; b < BANDS.length; b++) if (a >= BANDS[b][0] && a < BANDS[b][1]) { bandCount[b]++; bandCap[b] += a; break; } });
  const amts = allKnown.map((i) => R[i].amt).sort((a, b) => b - a), top10 = sum(amts.slice(0, 10)), top1 = Math.max(1, Math.ceil(amts.length * 0.01)), topP = sum(amts.slice(0, top1));
  const concentration = [
    { big: Math.round((top10 / allRaised) * 100) + '%', label: 'of capital sits in the 10 largest rounds', color: ACCENT },
    { big: Math.round((topP / allRaised) * 100) + '%', label: 'of capital sits in the top 1% of rounds (' + top1 + ' rounds)', color: ACCENT },
    { big: fmt(median(amts)), label: 'is the median round size', color: INK },
    { big: Math.round((amts.filter((a) => a < 5).length / amts.length) * 100) + '%', label: 'of rounds are under £5m', color: INK },
  ];
  const catV = cats.map(() => 0), catN = cats.map(() => 0), subV = subsG.map(() => 0), catCap = cats.map(() => 0);
  R.forEach((r) => { catV[r.cat] += val(r); catN[r.cat]++; subV[r.sub] += val(r); catCap[r.cat] += Math.max(r.amt, 0); });
  const totV = sum(catV);
  const { tiles, subTiles } = useMemo(() => buildTreemap(D, catV, subV, fmtV, aCat), [D, metric, aCat]); // eslint-disable-line
  const leagueSort = cats.map((c, i) => i).sort((a, b) => catV[b] - catV[a]), leagueMax = Math.max(1, ...catV);
  const maxOf = (arr) => Math.max(1, ...arr);

  // countries
  const allCap = countries.map(() => 0); R.forEach((r) => { if (r.amt > 0) allCap[r.c] += r.amt; });
  const totalAll = sum(allCap);
  const profileOf = (name) => {
    const pc = countries.indexOf(name), ids = []; R.forEach((r, i) => { if (r.c === pc) ids.push(i); });
    const cv = cats.map(() => 0), sv = subsG.map(() => 0), mv = months.map(() => 0), stn = STAGES.map(() => 0), am = [];
    ids.forEach((i) => { const r = R[i], a = Math.max(r.amt, 0); cv[r.cat] += a; sv[r.sub] += a; mv[r.m] += a; stn[r.st]++; if (r.amt > 0) am.push(r.amt); });
    const cap = sum(cv), rank = countries.map((c, k) => k).filter((k) => allCap[k] > allCap[pc]).length + 1;
    return { pc, ids, cv, sv, mv, stn, am, cap, rank, lead: cv.indexOf(Math.max(...cv)) };
  };
  const P = profileOf(profC);
  const arcs = []; let ang = 0;
  cats.map((c, i) => i).sort((a, b) => P.cv[b] - P.cv[a]).forEach((i) => { if (P.cv[i] <= 0) return; const sweep = (P.cv[i] / P.cap) * 360; arcs.push({ d: arcPath(100, 100, 62, 96, ang, ang + sweep), color: colors[i], title: cats[i] + ' · ' + fmt(P.cv[i]) }); ang += sweep; });
  const mixSorted = cats.map((c, i) => i).filter((i) => P.cv[i] > 0).sort((a, b) => P.cv[b] - P.cv[a]);
  const stColors = ['#BCC5CE', '#8A97A5', '#5C6B7B', '#34475C', INK, ACCENT, '#E3A21A', '#12A5C9', '#7A3FD1'];
  const topIds = P.ids.slice().sort((a, b) => R[b].amt - R[a].amt).slice(0, 5);
  const subIds = subsG.map((sg, k) => k).filter((k) => P.sv[k] > 0).sort((a, b) => P.sv[b] - P.sv[a]).slice(0, 5), subMax = maxOf(subIds.map((k) => P.sv[k]));

  // ================= CARD 3: FUNDING MAP (independent: every round; click pins a country) =================
  const capCat = countries.map(() => cats.map(() => 0)), capBy = countries.map(() => 0);
  R.forEach((r) => { const a = Math.max(r.amt, 0) + 0.001; capCat[r.c][r.cat] += a; capBy[r.c] += a; });
  const maxCap = maxOf(capBy), shownC = hoverC >= 0 ? hoverC : mapSel;
  let hover = null;
  if (shownC >= 0) {
    const list = []; R.forEach((r, i) => { if (r.c === shownC) list.push(i); }); list.sort((a, b) => R[b].amt - R[a].amt);
    hover = { name: countries[shownC], line: list.length + ' rounds · ' + fmt(Math.max(capBy[shownC] - 0.001 * list.length, 0)) + ' raised', top: list.slice(0, 5) };
  }

  // ================= HERO DOTS =================
  const heroGroups = useMemo(() => {
    const groups = GEO.hero.map((g, gi) => ({ dur: (3.6 + gi * 0.9).toFixed(1) + 's', shimmerBegin: '-' + (gi * 1.1).toFixed(1) + 's', drift: gi % 2 ? '7 -5' : '-6 6', driftDur: (9 + gi * 1.6).toFixed(1) + 's', filter: 'none', r: 2.2, to: '0.5', vals: '1;0.12;1',
      dots: g.map((d) => ({ x: d[0], y: d[1], from: d[2] + ' ' + d[3], begin: d[4] + 's', tw: (((d[0] * 7 + d[1] * 13) | 0) % 3) === 0, twDur: (2 + ((d[0] + d[1]) % 30) / 10).toFixed(1) + 's', twBegin: (d[4] + 2.7).toFixed(1) + 's' })) }));
    const glow = GEO.hero[2].filter((d, k) => k % 3 === 0).concat(GEO.hero[5].filter((d, k) => k % 4 === 0)).map((d) => ({ x: d[0], y: d[1], from: d[2] + ' ' + d[3], begin: (d[4] + 0.3).toFixed(2) + 's', tw: false }));
    groups.push({ dur: '2.8s', shimmerBegin: '-0.6s', drift: '0 0', driftDur: '10s', filter: 'drop-shadow(0 0 5px rgba(255,255,255,0.95))', r: 3.4, to: '1', vals: '0.05;1;0.05', dots: glow });
    return groups;
  }, []);

  const cardStyle = (i) => {
    const on = i === card, before = i < card;
    return { position: on ? 'relative' : 'absolute', left: 0, right: 0, top: 0, zIndex: on ? 2 : before ? 1 : 3, visibility: on ? 'visible' : 'hidden', pointerEvents: on ? 'auto' : 'none', opacity: on ? 1 : 0,
      transform: on ? 'translateY(0px) scale(1)' : before ? 'translateY(-60px) scale(0.93)' : 'translateY(140px) scale(1)', transformOrigin: '50% 0',
      transition: 'transform 0.95s cubic-bezier(0.22,0.9,0.24,1), opacity 0.75s ease, visibility 0s linear ' + (on ? '0s' : '0.95s'),
      background: BG, borderRadius: '30px 30px 0 0', boxShadow: '0 -16px 50px rgba(14,22,32,0.25)', overflow: 'hidden', boxSizing: 'border-box' };
  };
  const nearest = Math.floor(N / 100) * 100;

  return (
    <div style={{ background: BG, color: INK, fontFamily: "'Instrument Sans', system-ui, sans-serif", width: '100%' }}>
      {/* ---------------- TITLE BAND ---------------- */}
      <header style={{ position: 'relative', overflow: 'hidden', background: '#9B1B22', color: '#F4F6F8' }}>
        <svg key={mode} viewBox="0 0 760 720" preserveAspectRatio="xMidYMid slice" aria-hidden="true" style={{ position: 'absolute', left: 0, top: 0, width: '100%', height: '100%' }}>
          {heroGroups.map((g, gi) => (
            <g key={gi} style={{ filter: g.filter }}>
              {(full || calm) && <animate attributeName="opacity" values={full ? g.vals : (g.to === '1' ? '1;0.5;1' : '1;0.55;1')} dur={full ? g.dur : (parseFloat(g.dur) * 2.2).toFixed(1) + 's'} begin={g.shimmerBegin} repeatCount="indefinite" />}
              {full && <animateTransform attributeName="transform" type="translate" values={'0 0;' + g.drift + ';0 0'} dur={g.driftDur} begin={g.shimmerBegin} repeatCount="indefinite" />}
              {g.dots.map((d, k) => (
                <circle key={k} cx={d.x} cy={d.y} r={g.r} fill="#F4F6F8" opacity={full ? 0 : g.to === '1' ? 0.7 : 0.5}>
                  {full && <animateTransform attributeName="transform" type="translate" from={d.from} to="0 0" dur="2.4s" begin={d.begin} fill="freeze" calcMode="spline" keyTimes="0;1" keySplines="0.16 1 0.3 1" />}
                  {full && <animate attributeName="opacity" from="0" to={g.to} dur="1.4s" begin={d.begin} fill="freeze" />}
                  {full && d.tw && <animate attributeName="opacity" values="0.08;1;0.08" dur={d.twDur} begin={d.twBegin} repeatCount="indefinite" />}
                </circle>
              ))}
            </g>
          ))}
        </svg>
        <div style={{ position: 'absolute', right: 40, bottom: 66, zIndex: 3, display: 'flex', alignItems: 'center', gap: 12 }}>
          {reduced && calm && <span style={{ fontSize: 12, opacity: 0.85, maxWidth: 210, textAlign: 'right', lineHeight: 1.3 }}>Showing a calmer version because your device asks for reduced motion.</span>}
          <button type="button" onClick={onMotionClick} aria-pressed={full} style={{ minHeight: 40, padding: '0 16px', border: '1.5px solid #F4F6F8', background: 'transparent', color: '#F4F6F8', fontSize: 13, fontWeight: 600, cursor: 'pointer', borderRadius: 99 }}>{full ? 'Pause animation' : calm ? 'Play full animation' : 'Play animation'}</button>
        </div>
        <nav style={{ position: 'relative', zIndex: 2, display: 'flex', flexWrap: 'wrap', gap: 16, alignItems: 'center', justifyContent: 'space-between', ...wrap, padding: '18px 40px 0' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 22, fontSize: 15, fontWeight: 600 }}>
            {CARDS.map((c, i) => <button key={c[1]} type="button" onClick={() => go(i)} style={{ minHeight: 44, padding: 0, border: 0, background: 'transparent', color: 'inherit', font: 'inherit', cursor: 'pointer' }}>{i === 0 ? c[1] + ' ' + year : c[1]}</button>)}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 18 }}>
            {years.length > 1 && <div style={{ display: 'flex', gap: 6 }}>{years.map((y) => <button key={y} type="button" onClick={() => setYear(y)} aria-pressed={y === year} style={{ minHeight: 36, padding: '0 12px', border: '1.5px solid #F4F6F8', background: y === year ? '#F4F6F8' : 'transparent', color: y === year ? '#9B1B22' : '#F4F6F8', fontWeight: 700, fontSize: 13, cursor: 'pointer', borderRadius: 99 }}>{y}</button>)}</div>}
            <div style={disp(15)}>The Funding Dashboard</div>
          </div>
        </nav>
        <div id="top" style={{ position: 'relative', zIndex: 2, ...wrap, padding: '74px 40px 110px' }}>
          <h1 style={{ margin: 0, fontFamily: "'Montserrat', sans-serif", fontWeight: 800, fontSize: 'clamp(38px,7.6vw,108px)', lineHeight: 1, letterSpacing: '-0.035em' }}>The Funding<br />Dashboard</h1>
          <p style={{ margin: '28px 0 0', maxWidth: 620, fontSize: 21, lineHeight: 1.45, fontWeight: 500 }}>{nearest.toLocaleString('en-GB')}+ biggest funding rounds tracked across Europe in {year}</p>
          {STATUS && STATUS.updated && <p style={{ margin: '14px 0 0', ...mono(13), letterSpacing: '0.08em', textTransform: 'uppercase', opacity: 0.85 }}>Last updated {fmtDay(STATUS.updated)}</p>}
        </div>
      </header>

      {/* ---------------- CARD TABS ---------------- */}
      <div id="deck-top" style={{ position: 'relative', zIndex: 4, ...wrap, margin: '-44px auto 0' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
          {CARDS.map((c, i) => (
            <button key={c[0]} type="button" onClick={() => go(i)} aria-pressed={card === i} style={{ flex: '1 1 240px', minHeight: 78, display: 'flex', alignItems: 'center', gap: 16, padding: '0 22px', border: `2px solid ${INK}`, background: card === i ? INK : CARD, color: card === i ? BG : INK, cursor: 'pointer', textAlign: 'left', boxShadow: '0 12px 32px rgba(14,22,32,0.18)', transition: 'background .35s, color .35s' }}>
              <span style={{ ...mono(13), fontWeight: 500, letterSpacing: '0.1em', opacity: 0.7 }}>{c[0]}</span>
              <span style={disp(17, 800, '-0.01em')}>{i === 0 ? c[1] + ' ' + year : c[1]}</span>
            </button>
          ))}
        </div>
      </div>

      {/* ---------------- DECK ---------------- */}
      <div id="deck" style={{ position: 'relative', marginTop: 28, background: '#C3CCD5', padding: '30px 16px 0', boxSizing: 'border-box', overflow: 'hidden' }}>
        <div style={{ position: 'relative' }}>

          {/* ===== CARD 1 ===== */}
          <div style={cardStyle(0)}>
            <section style={{ ...wrap, padding: '44px 40px 0' }}>
              <div style={{ maxWidth: 900 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 14, background: CARD, border: `2px solid ${INK}`, padding: '0 18px', minHeight: 68, boxSizing: 'border-box' }}>
                  <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true" style={{ flex: 'none' }}><circle cx="10.5" cy="10.5" r="6.5" fill="none" stroke={INK} strokeWidth="2" /><path d="M15.5 15.5L21 21" stroke={INK} strokeWidth="2" strokeLinecap="round" /></svg>
                  <label htmlFor="q" style={{ position: 'absolute', left: -9999 }}>Search funding rounds</label>
                  <input id="q" type="text" value={q} onChange={(e) => { setQ(e.target.value); setShow(6); }} placeholder="Try: UK infrastructure startups raising £10–100m" autoComplete="off" style={{ flex: 1, minWidth: 0, height: 64, border: 0, background: 'transparent', fontSize: 19, fontWeight: 500, color: INK, outline: 'none' }} />
                  {q.trim() && <button type="button" onClick={() => setQ('')} aria-label="Clear search" style={{ minWidth: 44, minHeight: 44, border: 0, background: 'transparent', cursor: 'pointer', fontSize: 24, color: INK }}>&times;</button>}
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 14, alignItems: 'center', fontSize: 14, color: MUTED }}>
                  {q.trim() ? (<>
                    <span style={{ ...mono(12), fontWeight: 500, letterSpacing: '0.12em', textTransform: 'uppercase' }}>Understood as</span>
                    {par.chips.map((t, i) => <span key={i} style={{ padding: '6px 12px', border: `1.5px solid ${INK}`, borderRadius: 99, background: CARD, color: INK, fontSize: 13, fontWeight: 500 }}>{t}</span>)}
                    {par.chips.length === 0 && <span>Searching names and descriptions only</span>}
                  </>) : (<>
                    <span style={{ ...mono(12), fontWeight: 500, letterSpacing: '0.12em', textTransform: 'uppercase' }}>Try</span>
                    {EXAMPLES.map((t) => <button key={t} type="button" onClick={() => { setQ(t); setShow(6); }} style={{ minHeight: 36, padding: '0 14px', border: `1.5px solid ${INK}`, borderRadius: 99, background: 'transparent', color: INK, fontSize: 13, fontWeight: 500, cursor: 'pointer' }}>{t}</button>)}
                  </>)}
                </div>
                <div style={{ marginTop: 12, ...mono(12), color: MUTED }}>Search and filters apply to this section only.</div>
              </div>
            </section>

            <section id="state" style={{ ...wrap, padding: '40px 40px 20px' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 44, alignItems: 'flex-start' }}>
                {/* main column */}
                <div style={{ flex: '1 1 640px', minWidth: 0, order: 2 }}>
                  <div style={eyebrow}>Every funding round, one dot</div>
                  <H2>The state of {year}</H2>
                  <div style={{ display: 'flex', flexWrap: 'wrap', marginTop: 30, borderTop: `2px solid ${INK}`, borderBottom: `2px solid ${INK}` }}>
                    {[{ big: match.length.toLocaleString('en-GB'), label: match.length === N ? 'funding rounds' : 'of ' + N.toLocaleString('en-GB') + ' rounds' }, { big: fmt(raised), label: 'raised' }, { big: big >= 0 && R[big].amt >= 0 ? fmt(R[big].amt) : '–', label: big >= 0 ? 'largest: ' + R[big].name : 'largest round' }].map((k) => (
                      <div key={k.label} style={{ flex: '1 1 180px', padding: '18px 20px 16px 0' }}>
                        <div style={disp(30, 800, '-0.02em')}>{k.big}</div>
                        <div style={{ marginTop: 8, ...mono(12), letterSpacing: '0.08em', textTransform: 'uppercase', color: MUTED }}>{k.label}</div>
                      </div>
                    ))}
                  </div>
                  <div style={{ marginTop: 18, overflowX: 'auto' }}>
                    <div style={{ minWidth: 720 }}>
                      <svg viewBox={'0 0 1040 ' + lay.H} role="img" aria-label="Dot chart: each dot is one funding round, grouped by month and coloured by sector. Rounds outside the current filters are greyed out." style={{ display: 'block', width: '100%', height: 'auto' }}>
                        {R.map((r, i) => { const on = inM.has(i), isSel = sel === i, p = lay.pos[i];
                          return <circle key={i} cx={p[0].toFixed(1)} cy={p[1].toFixed(1)} r={isSel ? 5.8 : 3.4} fill={on ? colors[r.cat] : '#BCC5CE'} fillOpacity={on ? 1 : 0.5} stroke={isSel ? INK : 'none'} strokeWidth="1.8" onClick={() => setSel(i)} style={{ cursor: 'pointer' }}><title>{r.name + ' · ' + countries[r.c] + ' · ' + STAGES[r.st] + ' · ' + fmt(r.amt)}</title></circle>; })}
                        <path d={'M0 ' + (lay.baseY + 12) + 'H1040'} stroke={INK} strokeWidth="2" fill="none" />
                      </svg>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(' + nm + ',minmax(0,1fr))', marginTop: 10 }}>
                        {months.map((m, j) => <div key={m} style={{ textAlign: 'center' }}><div style={disp(13, 600, '0')}>{monName(D, j)}</div><div style={{ marginTop: 3, ...mono(11), color: MUTED }}>{mcount[j] + (match.length === N ? '' : ' shown')}</div></div>)}
                      </div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 20px', marginTop: 22, fontSize: 13, color: MUTED }}>
                    {cats.map((c, i) => <span key={c} style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}><Swatch color={colors[i]} size={10} />{c}</span>)}
                  </div>

                  {selR && (
                    <div style={{ marginTop: 22, border: `2px solid ${INK}`, padding: 6, background: CARD }}>
                      <div style={{ border: `1px solid ${INK}`, padding: '20px 22px', display: 'flex', flexWrap: 'wrap', gap: '18px 40px', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                        <div style={{ flex: '1 1 300px', minWidth: 0 }}>
                          <div style={{ ...mono(12), fontWeight: 500, letterSpacing: '0.14em', textTransform: 'uppercase', color: colors[selR.cat] }}>{cats[selR.cat]} › {subsG[selR.sub][1]}</div>
                          <div style={{ marginTop: 10, ...disp(28) }}>{selR.name}</div>
                          <div style={{ marginTop: 8, fontSize: 16, color: MUTED }}>{selR.blurb}</div>
                          {selOthers && <div style={{ marginTop: 10, fontSize: 14, fontWeight: 500 }}>{selOthers}</div>}
                          {selR.investors && <div style={{ marginTop: 8, fontSize: 14, color: MUTED }}>Investors: {selR.investors}</div>}
                          {selR.url && <a href={selR.url} target="_blank" rel="noopener noreferrer" style={{ display: 'inline-block', marginTop: 10, fontSize: 14, fontWeight: 600, textDecoration: 'underline' }}>Source</a>}
                        </div>
                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '18px 34px' }}>
                          <div><div style={disp(24)}>{fmt(selR.amt)}</div><div style={{ marginTop: 6, ...mono(11), letterSpacing: '0.08em', textTransform: 'uppercase', color: MUTED }}>{STAGES[selR.st]}</div></div>
                          <div><div style={disp(24)}>{countries[selR.c]}</div><div style={{ marginTop: 6, ...mono(11), letterSpacing: '0.08em', textTransform: 'uppercase', color: MUTED }}>{monName(D, selR.m) + ' ' + year}</div></div>
                        </div>
                        <button type="button" onClick={() => setSel(-1)} aria-label="Close details" style={{ minWidth: 44, minHeight: 44, border: `1.5px solid ${INK}`, background: 'transparent', cursor: 'pointer', fontSize: 20 }}>&times;</button>
                      </div>
                    </div>
                  )}

                  <div id="explore" style={{ marginTop: 64, display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'baseline', gap: 8 }}>
                    <H3 size={26}>Matching rounds</H3>
                    <div style={{ ...mono(13), color: MUTED }} aria-live="polite">{match.length.toLocaleString('en-GB')} of {N.toLocaleString('en-GB')} rounds · {fmt(raised)} raised</div>
                  </div>
                  <div style={{ marginTop: 16, borderTop: `2px solid ${INK}` }}>
                    {order.slice(0, show).map((i) => { const r = R[i], o = othersText(D, i);
                      return (
                        <button key={i} type="button" onClick={() => setSel(i)} style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 24px', width: '100%', textAlign: 'left', padding: '18px 6px', border: 0, borderBottom: `1px solid ${LINE}`, background: sel === i ? '#D3DAE2' : 'transparent', color: INK, cursor: 'pointer', alignItems: 'flex-start', boxSizing: 'border-box' }}>
                          <span style={{ flex: '1 1 280px', minWidth: 0 }}>
                            <span style={{ display: 'flex', alignItems: 'center', gap: 10 }}><Swatch color={colors[r.cat]} size={11} /><span style={disp(19, 800, '-0.01em')}>{r.name}</span></span>
                            <span style={{ display: 'block', margin: '6px 0 0 21px', fontSize: 14, color: MUTED }}>{r.blurb}</span>
                            {o && <span style={{ display: 'block', margin: '8px 0 0 21px', fontSize: 13, fontWeight: 500 }}>{o}</span>}
                          </span>
                          <span style={{ flex: '0 1 220px', fontSize: 13, color: MUTED, paddingTop: 3 }}>{countries[r.c] + ' · ' + cats[r.cat] + ' › ' + subsG[r.sub][1] + ' · ' + STAGES[r.st]}</span>
                          <span style={{ flex: '0 0 120px', textAlign: 'right', ...disp(18) }}>{fmt(r.amt)}</span>
                        </button>
                      ); })}
                  </div>
                  {match.length > show && <button type="button" onClick={() => setShow(show + 12)} style={{ marginTop: 18, minHeight: 48, padding: '0 26px', border: `2px solid ${INK}`, background: 'transparent', fontSize: 15, fontWeight: 600, cursor: 'pointer' }}>Show more rounds</button>}
                  {match.length === 0 && <p style={{ margin: '24px 0 0', fontSize: 17, color: MUTED }}>No rounds match. Loosen a filter, or reset them all.</p>}
                </div>

                {/* filter rail */}
                <aside style={{ flex: '0 1 310px', minWidth: 280, width: '100%', boxSizing: 'border-box', order: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', borderBottom: `2px solid ${INK}`, paddingBottom: 10 }}>
                    <div style={disp(24)}>Filters</div>
                    <button type="button" onClick={() => { setQ(''); setShow(6); setF(emptyFilters(D)); }} style={{ minHeight: 44, padding: '0 4px', border: 0, background: 'transparent', fontSize: 14, fontWeight: 500, textDecoration: 'underline', cursor: 'pointer', color: INK }}>Reset all</button>
                  </div>
                  <div style={{ marginTop: 20, ...label }}>Country</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
                    {topC.map((i) => <Pill key={i} on={f.countries.indexOf(i) >= 0} onClick={() => toggle('countries', i)}>{countries[i]} <Cnt>{cCnt[i]}</Cnt></Pill>)}
                  </div>
                  <label htmlFor="more-countries" style={{ position: 'absolute', left: -9999 }}>Add another country</label>
                  <select id="more-countries" value="" onChange={(e) => { const v = parseInt(e.target.value, 10); if (!isNaN(v)) toggle('countries', v); }} style={{ marginTop: 10, minHeight: 40, width: '100%', border: `1.5px solid ${INK}`, background: CARD, fontSize: 14, padding: '0 10px', color: INK }}>
                    <option value="">More countries…</option>
                    {countries.map((c, i) => topC.indexOf(i) < 0 && <option key={c} value={i}>{c + ' (' + cCnt[i] + ')'}</option>)}
                  </select>

                  <div style={{ marginTop: 26, ...label }}>Sector</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
                    {cats.map((c, i) => <Pill key={c} on={f.cats.indexOf(i) >= 0} onClick={() => toggle('cats', i)}><Swatch color={colors[i]} ring={f.cats.indexOf(i) >= 0 ? BG : INK} />{c} <Cnt>{catCnt[i]}</Cnt></Pill>)}
                  </div>
                  {f.cats.length > 0 && (<>
                    <div style={{ marginTop: 18, ...label }}>Sub-sector</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
                      {subsG.map((sg, i) => f.cats.indexOf(sg[0]) >= 0 && <Pill key={i} size={34} on={f.subs.indexOf(i) >= 0} onClick={() => toggle('subs', i)}><Swatch color={colors[sg[0]]} size={8} />{sg[1]} <Cnt>{subCnt[i]}</Cnt></Pill>)}
                    </div>
                  </>)}

                  <div style={{ marginTop: 26, ...label }}>Round size (£)</div>
                  <div style={{ display: 'flex', gap: 10, marginTop: 10, alignItems: 'center' }}>
                    <label htmlFor="amt-min" style={{ position: 'absolute', left: -9999 }}>Minimum round size</label>
                    <select id="amt-min" value={f.min} onChange={(e) => setAmt(parseFloat(e.target.value), f.max)} style={selectStyle}><option value={0}>No minimum</option>{AMT_STEPS.map((a) => <option key={a} value={a}>{fmtStep(a)}</option>)}</select>
                    <span style={{ color: MUTED }}>to</span>
                    <label htmlFor="amt-max" style={{ position: 'absolute', left: -9999 }}>Maximum round size</label>
                    <select id="amt-max" value={f.max} onChange={(e) => setAmt(f.min, parseFloat(e.target.value))} style={selectStyle}><option value={-1}>No maximum</option>{AMT_STEPS.map((a) => <option key={a} value={a}>{fmtStep(a)}</option>)}</select>
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
                    {PRE.map((p) => <Pill key={p[0]} size={34} on={f.min === p[1] && f.max === p[2]} onClick={() => setAmt(p[1], p[2])}>{p[0]}</Pill>)}
                  </div>
                  <div style={{ marginTop: 8, fontSize: 12, color: MUTED }}>Rounds with undisclosed amounts are hidden when a size is set.</div>

                  <div style={{ marginTop: 26, ...label }}>Stage</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 10 }}>
                    {STAGES.map((c, i) => <Pill key={c} size={34} on={f.stages.indexOf(i) >= 0} onClick={() => toggle('stages', i)}>{c} <Cnt>{stCnt[i]}</Cnt></Pill>)}
                  </div>

                  <div style={{ marginTop: 26, ...label }}>Months</div>
                  <div style={{ display: 'flex', gap: 10, marginTop: 10, alignItems: 'center' }}>
                    <label htmlFor="m-from" style={{ position: 'absolute', left: -9999 }}>From month</label>
                    <select id="m-from" value={f.m0} onChange={(e) => { const v = parseInt(e.target.value, 10); setF({ ...f, m0: v, m1: Math.max(v, f.m1) }); setShow(6); }} style={selectStyle}>{months.map((m, j) => <option key={m} value={j}>{monName(D, j)}</option>)}</select>
                    <span style={{ color: MUTED }}>to</span>
                    <label htmlFor="m-to" style={{ position: 'absolute', left: -9999 }}>To month</label>
                    <select id="m-to" value={f.m1} onChange={(e) => { const v = parseInt(e.target.value, 10); setF({ ...f, m1: v, m0: Math.min(v, f.m0) }); setShow(6); }} style={selectStyle}>{months.map((m, j) => <option key={m} value={j}>{monName(D, j)}</option>)}</select>
                  </div>
                </aside>
              </div>
            </section>
            <div style={{ ...wrap, padding: '30px 40px 70px', display: 'flex', flexWrap: 'wrap', gap: 12, justifyContent: 'space-between' }}><span /><Btn onClick={() => go(1)}>Next: Analytics &rarr;</Btn></div>
          </div>

          {/* ===== CARD 2 ===== */}
          <div style={cardStyle(1)}>
            <section id="analytics" style={{ ...wrap, padding: '56px 40px 20px' }}>
              <div style={eyebrow}>Capital · Sectors · Countries</div>
              <H2>Analytics</H2>
              <p style={{ margin: '18px 0 0', maxWidth: 660, fontSize: 17, lineHeight: 1.55, color: MUTED }}>Covers all {N.toLocaleString('en-GB')} rounds, independent of the filters in The state of {year}.</p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10, marginTop: 30, alignItems: 'center', borderBottom: `2px solid ${INK}`, paddingBottom: 16 }}>
                {[['capital', 'Capital'], ['sectors', 'Sectors'], ['countries', 'Countries']].map((t) => <button key={t[0]} type="button" onClick={() => setTab(t[0])} aria-pressed={tab === t[0]} style={{ minHeight: 46, padding: '0 22px', border: `2px solid ${INK}`, background: tab === t[0] ? INK : CARD, color: tab === t[0] ? BG : INK, ...disp(13, 600, '0'), cursor: 'pointer', borderRadius: 99 }}>{t[1]}</button>)}
                {tab !== 'countries' && (
                  <span style={{ marginLeft: 'auto', display: 'flex', gap: 6, alignItems: 'center', fontSize: 13, color: MUTED }}>Measure
                    {[['capital', 'Capital'], ['rounds', 'Rounds']].map((t) => <button key={t[0]} type="button" onClick={() => setMetric(t[0])} aria-pressed={metric === t[0]} style={{ minHeight: 40, padding: '0 16px', border: `1.5px solid ${INK}`, background: metric === t[0] ? INK : 'transparent', color: metric === t[0] ? BG : INK, fontSize: 13, fontWeight: 600, cursor: 'pointer', borderRadius: 99 }}>{t[1]}</button>)}
                  </span>
                )}
              </div>

              {tab === 'capital' && (<>
                <div style={{ marginTop: 44 }}>
                  <H3>{metric === 'capital' ? 'Capital raised by month' : 'Rounds by month'}</H3>
                  <p style={{ margin: '8px 0 0', fontSize: 14, color: MUTED }}>Each column is a month, split by sector. Click any coloured block, or a sector below, to see what it is.</p>
                  <div style={{ marginTop: 16, minHeight: 62, display: 'flex', alignItems: 'center', gap: 14, border: `2px solid ${INK}`, background: CARD, padding: '10px 16px', boxSizing: 'border-box' }}>
                    {readout ? (<>
                      <span style={{ width: 22, height: 22, borderRadius: '50%', background: readout.color, flex: 'none' }} />
                      <div style={{ minWidth: 0 }}><div style={disp(20, 800, '-0.01em')}>{readout.name}</div><div style={{ marginTop: 3, ...mono(13), color: MUTED }}>{readout.line}</div></div>
                    </>) : <span style={{ fontSize: 15, color: MUTED }}>Click a coloured block to see which sector it is and how much it holds.</span>}
                  </div>
                  <div style={{ position: 'relative', margin: '26px 0 0 64px', height: 340 }}>
                    {ticks.map((t, k) => (
                      <React.Fragment key={k}>
                        <div style={{ position: 'absolute', left: 0, right: 0, bottom: t.pct, borderTop: '1px solid #C3CBD3' }} />
                        <div style={{ position: 'absolute', left: -64, width: 54, bottom: t.pct, marginBottom: -8, textAlign: 'right', ...mono(12), color: MUTED }}>{t.t}</div>
                      </React.Fragment>
                    ))}
                    <div style={{ position: 'absolute', left: 0, right: 0, top: 0, bottom: 0, display: 'flex', alignItems: 'flex-end', gap: 14, padding: '0 6px', boxSizing: 'border-box' }}>
                      {months.map((m, j) => (
                        <div key={m} style={{ flex: 1, minWidth: 0, height: '100%', display: 'flex', alignItems: 'flex-end', justifyContent: 'center' }}>
                          <div style={{ position: 'relative', width: '78%', height: (colTot[j] / topV) * 100 + '%', display: 'flex', flexDirection: 'column-reverse' }}>
                            <div style={{ position: 'absolute', left: -20, right: -20, top: -24, textAlign: 'center', ...mono(12), fontWeight: 500 }}>{metric === 'capital' ? fmt(colTot[j]) : colTot[j]}</div>
                            {cats.map((c, ci) => stack[ci][j] > 0 && (
                              <div key={ci} title={monName(D, j) + ' · ' + c + ' · ' + fmtV(stack[ci][j])} onClick={() => { const same = seg && seg.c === ci && seg.m === j; if (same) { setACat(-1); setSeg(null); } else { setACat(ci); setSeg({ c: ci, m: j }); } }}
                                style={{ flex: stack[ci][j] + ' 1 0', background: colors[ci], opacity: aCat < 0 || aCat === ci ? 1 : 0.18, borderTop: `1px solid ${BG}`, minHeight: 0, cursor: 'pointer', transition: 'opacity .4s' }} />
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 14, margin: '10px 0 0 64px', padding: '0 6px', boxSizing: 'border-box' }}>
                    {months.map((m, j) => <div key={m} style={{ flex: 1, minWidth: 0, textAlign: 'center', ...disp(13, 600, '0') }}>{monName(D, j)}</div>)}
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, margin: '26px 0 0 64px' }}>
                    {cats.map((c, i) => <button key={c} type="button" onClick={() => { if (aCat === i) { setACat(-1); setSeg(null); } else { setACat(i); setSeg(null); } }} aria-pressed={aCat === i} style={{ display: 'inline-flex', alignItems: 'center', gap: 8, minHeight: 38, padding: '0 14px', border: `1.5px solid ${INK}`, background: aCat === i ? INK : 'transparent', color: aCat === i ? BG : INK, fontSize: 13, fontWeight: 600, cursor: 'pointer', borderRadius: 99 }}><Swatch color={colors[i]} size={10} />{c}</button>)}
                  </div>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 48, marginTop: 70 }}>
                  <div style={{ flex: '1 1 440px', minWidth: 0 }}>
                    <H3>Round sizes</H3>
                    <p style={{ margin: '8px 0 0', fontSize: 14, color: MUTED }}>Most rounds are small. Most capital sits in a few very large ones.</p>
                    <div style={{ marginTop: 24, display: 'flex', flexDirection: 'column', gap: 10 }}>
                      {BANDS.map((b, k) => (
                        <div key={b[2]} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                          <div style={{ width: 92, flex: 'none', ...mono(13), fontWeight: 500 }}>{b[2]}</div>
                          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 4 }}>
                            <div style={{ height: 12, background: '#D5DCE3' }}><div style={{ height: 12, width: (bandCount[k] / Math.max(allKnown.length, 1)) * 100 + '%', background: INK }} /></div>
                            <div style={{ height: 12, background: '#D5DCE3' }}><div style={{ height: 12, width: (bandCap[k] / Math.max(allRaised, 1)) * 100 + '%', background: ACCENT }} /></div>
                          </div>
                          <div style={{ width: 96, flex: 'none', textAlign: 'right', fontSize: 12, color: MUTED }}><div>{bandCount[k]} rounds</div><div>{Math.round((bandCap[k] / Math.max(allRaised, 1)) * 100)}% of capital</div></div>
                        </div>
                      ))}
                    </div>
                    <div style={{ display: 'flex', gap: 20, marginTop: 16, fontSize: 13, color: MUTED }}><span style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}><span style={{ width: 12, height: 12, background: INK }} />Share of rounds</span><span style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}><span style={{ width: 12, height: 12, background: ACCENT }} />Share of capital</span></div>
                  </div>
                  <div style={{ flex: '1 1 360px', minWidth: 0 }}>
                    <H3>Concentration</H3>
                    <div style={{ marginTop: 24, display: 'grid', gridTemplateColumns: 'repeat(2,minmax(0,1fr))', gap: '26px 20px' }}>
                      {concentration.map((c) => <div key={c.label}><div style={{ ...disp(34), lineHeight: 1.05, color: c.color }}>{c.big}</div><div style={{ marginTop: 8, fontSize: 14, lineHeight: 1.4, color: MUTED }}>{c.label}</div></div>)}
                    </div>
                  </div>
                </div>
              </>)}

              {tab === 'sectors' && (<>
                <div style={{ marginTop: 44 }}>
                  <H3>{metric === 'capital' ? 'Capital by sector' : 'Rounds by sector'}</H3>
                  <p style={{ margin: '8px 0 0', fontSize: 14, color: MUTED }}>Tile area is {metric === 'capital' ? 'proportional to capital raised' : 'proportional to the number of rounds'}. Smaller tiles inside are sub-sectors. Click a sector to highlight it in every chart here.</p>
                  <div style={{ position: 'relative', marginTop: 24, width: '100%', height: 600, background: BG }}>
                    {tiles.map((t) => (
                      <button key={t.i} type="button" onClick={() => setACat(aCat === t.i ? -1 : t.i)} title={t.title} style={{ position: 'absolute', left: t.l, top: t.t, width: t.w, height: t.h, display: 'flex', flexDirection: 'column', alignItems: 'stretch', justifyContent: 'flex-start', padding: 0, margin: 0, border: `3px solid ${BG}`, background: t.bg, opacity: t.op, cursor: 'pointer', overflow: 'hidden', textAlign: 'left', boxSizing: 'border-box', transition: 'opacity .4s' }}>
                        <span style={{ display: 'block', flex: 'none', padding: '10px 12px 2px', background: t.hbg, color: t.fg, fontFamily: "'Montserrat', sans-serif", fontWeight: 800, fontSize: t.fs + 'px', lineHeight: 1.15, letterSpacing: '-0.01em', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{t.name}</span>
                        <span style={{ display: 'block', flex: 'none', padding: '0 12px 8px', background: t.hbg, color: t.fg, ...mono(12), fontWeight: 500, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', minHeight: 20 }}>{t.val}</span>
                      </button>
                    ))}
                    {subTiles.map((s, k) => (
                      <div key={k} title={s.title} style={{ position: 'absolute', left: s.l, top: s.t, width: s.w, height: s.h, background: s.fill, border: `1px solid ${s.line}`, opacity: s.op, boxSizing: 'border-box', overflow: 'hidden', pointerEvents: 'none', padding: '6px 8px', color: s.fg, transition: 'opacity .4s' }}>
                        <div style={{ fontFamily: "'Montserrat', sans-serif", fontWeight: 700, fontSize: 12, lineHeight: 1.15, wordBreak: 'break-word' }}>{s.label}</div>
                        <div style={{ marginTop: 3, ...mono(11), fontWeight: 500, opacity: 0.85 }}>{s.val}</div>
                      </div>
                    ))}
                  </div>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 56, marginTop: 70 }}>
                  <div style={{ flex: '1 1 520px', minWidth: 0 }}>
                    <H3>Sector league table</H3>
                    <div style={{ marginTop: 20, borderTop: `2px solid ${INK}` }}>
                      {leagueSort.map((i) => { const subs = subsG.map((sg, k) => ({ k, c: sg[0], v: subV[k] })).filter((x) => x.c === i && x.v > 0).sort((a, b) => b.v - a.v).slice(0, 3);
                        return (
                          <div key={i} onClick={() => setACat(aCat === i ? -1 : i)} style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '8px 16px', padding: '14px 8px', borderBottom: `1px solid ${LINE}`, background: aCat === i ? '#D3DAE2' : 'transparent', cursor: 'pointer' }}>
                            <div style={{ flex: '1 1 170px', display: 'flex', alignItems: 'center', gap: 10 }}><Swatch color={colors[i]} size={12} /><span style={disp(14, 600, '0')}>{cats[i]}</span></div>
                            <div style={{ flex: '2 1 160px', height: 12, background: '#D5DCE3' }}><div style={{ height: 12, width: (catV[i] / leagueMax) * 100 + '%', background: colors[i] }} /></div>
                            <div style={{ flex: '0 0 76px', textAlign: 'right', ...mono(13), fontWeight: 500 }}>{Math.round((catV[i] / totV) * 100) + '%'}</div>
                            <div style={{ flex: '0 0 96px', textAlign: 'right', ...disp(14) }}>{fmt(catCap[i])}</div>
                            <div style={{ flex: '1 1 100%', fontSize: 12, color: MUTED, paddingLeft: 22 }}>{catN[i] + ' rounds · top: ' + (subs.map((x) => subsG[x.k][1]).join(', ') || '–')}</div>
                          </div>
                        ); })}
                    </div>
                  </div>
                  <div style={{ flex: '1 1 440px', minWidth: 0 }}>
                    <H3>Momentum by sector</H3>
                    <p style={{ margin: '8px 0 0', fontSize: 14, color: MUTED }}>Monthly {metric === 'capital' ? 'capital raised' : 'rounds'}, across the year.</p>
                    <div style={{ marginTop: 20, display: 'grid', gridTemplateColumns: 'repeat(2,minmax(0,1fr))', gap: '18px 22px' }}>
                      {cats.map((c, ci) => { const pk = Math.max(1, ...stack[ci]);
                        return (
                          <div key={c} style={{ opacity: aCat < 0 || aCat === ci ? 1 : 0.25, transition: 'opacity .4s' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', fontSize: 13, fontWeight: 600 }}><span>{c}</span><span style={{ ...mono(11), color: MUTED, fontWeight: 400 }}>peak {metric === 'capital' ? fmt(pk) : pk}</span></div>
                            <div style={{ display: 'flex', alignItems: 'flex-end', gap: 3, height: 54, marginTop: 6, borderBottom: `1px solid ${INK}` }}>
                              {months.map((m, j) => <div key={m} title={monName(D, j) + ' · ' + fmtV(stack[ci][j])} style={{ flex: 1, height: (stack[ci][j] / pk) * 100 + '%', background: colors[ci], minHeight: 1 }} />)}
                            </div>
                          </div>
                        ); })}
                    </div>
                  </div>
                </div>
              </>)}

              {tab === 'countries' && (<>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 40 }}>
                  {FIVE.filter((n) => countries.indexOf(n) >= 0).map((n) => <button key={n} type="button" onClick={() => setProfC(n)} aria-pressed={profC === n} style={{ minHeight: 44, padding: '0 20px', border: `1.5px solid ${INK}`, background: profC === n ? INK : CARD, color: profC === n ? BG : INK, fontSize: 14, fontWeight: 600, cursor: 'pointer', borderRadius: 99 }}>{n}</button>)}
                </div>
                <p style={{ margin: '14px 0 0', fontSize: 13, color: MUTED }}>Country profiles always show every round in that country.</p>
                <div style={{ marginTop: 34, display: 'flex', flexWrap: 'wrap', gap: '26px 60px', alignItems: 'flex-end', justifyContent: 'space-between', borderBottom: `2px solid ${INK}`, paddingBottom: 26 }}>
                  <div style={{ ...disp('clamp(34px,5.4vw,76px)', 800, '-0.03em'), lineHeight: 1 }}>{profC}</div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '20px 44px' }}>
                    {[{ big: fmt(P.cap), label: 'raised' }, { big: String(P.ids.length), label: 'rounds' }, { big: Math.round((P.cap / totalAll) * 100) + '%', label: 'of all capital, #' + P.rank }, { big: P.am.length ? fmt(median(P.am)) : '–', label: 'median round' }].map((k) => (
                      <div key={k.label}><div style={disp(26)}>{k.big}</div><div style={{ marginTop: 6, ...mono(11), letterSpacing: '0.08em', textTransform: 'uppercase', color: MUTED }}>{k.label}</div></div>
                    ))}
                  </div>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 50, marginTop: 40 }}>
                  <div style={{ flex: '1 1 380px', minWidth: 0 }}>
                    <H3 size={20}>Sector mix by capital</H3>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 24, alignItems: 'center', marginTop: 20 }}>
                      <div style={{ position: 'relative', width: 200, height: 200, flex: 'none' }}>
                        <svg viewBox="0 0 200 200" role="img" aria-label="Donut chart of the country's capital by sector" style={{ display: 'block', width: 200, height: 200 }}>{arcs.map((a, k) => <path key={k} d={a.d} fill={a.color} stroke={BG} strokeWidth="2"><title>{a.title}</title></path>)}</svg>
                        <div style={{ position: 'absolute', left: 0, top: 0, width: 200, height: 200, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center' }}><div style={disp(20)}>{fmt(P.cap)}</div><div style={{ ...mono(11), color: MUTED, marginTop: 4 }}>raised</div></div>
                      </div>
                      <div style={{ flex: '1 1 180px', display: 'flex', flexDirection: 'column', gap: 8 }}>
                        {mixSorted.map((i) => <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 9, fontSize: 13 }}><Swatch color={colors[i]} size={10} /><span style={{ flex: 1, fontWeight: 500 }}>{cats[i]}</span><span style={mono(13)}>{Math.round((P.cv[i] / P.cap) * 100) + '%'}</span></div>)}
                      </div>
                    </div>
                  </div>
                  <div style={{ flex: '1 1 380px', minWidth: 0 }}>
                    <H3 size={20}>Capital by month</H3>
                    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 7, height: 170, marginTop: 20, borderBottom: `2px solid ${INK}` }}>
                      {months.map((m, j) => <div key={m} title={monName(D, j) + ' · ' + fmt(P.mv[j])} style={{ flex: 1, height: (P.mv[j] / maxOf(P.mv)) * 100 + '%', background: ACCENT, minHeight: 2 }} />)}
                    </div>
                    <div style={{ display: 'flex', gap: 7, marginTop: 8 }}>{months.map((m, j) => <div key={m} style={{ flex: 1, textAlign: 'center', ...mono(11), fontWeight: 500, color: MUTED }}>{monName(D, j).slice(0, 1)}</div>)}</div>
                    <H3 size={20} style={{ marginTop: 34 }}>Rounds by stage</H3>
                    <div style={{ display: 'flex', height: 22, marginTop: 16, background: '#D5DCE3' }}>
                      {STAGES.map((n, k) => P.stn[k] > 0 && <div key={n} title={n + ' · ' + P.stn[k] + ' rounds'} style={{ width: (P.stn[k] / Math.max(P.ids.length, 1)) * 100 + '%', background: stColors[k] }} />)}
                    </div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 16px', marginTop: 10, fontSize: 12, color: MUTED }}>
                      {STAGES.map((n, k) => P.stn[k] > 0 && <span key={n} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><span style={{ width: 9, height: 9, background: stColors[k] }} />{n} {P.stn[k]}</span>)}
                    </div>
                  </div>
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 50, marginTop: 50 }}>
                  <div style={{ flex: '1 1 380px', minWidth: 0 }}>
                    <H3 size={20}>Five biggest rounds</H3>
                    <div style={{ marginTop: 14, borderTop: `2px solid ${INK}` }}>
                      {topIds.map((i) => <div key={i} style={{ display: 'flex', justifyContent: 'space-between', gap: 14, padding: '13px 0', borderBottom: `1px solid ${LINE}` }}><div style={{ minWidth: 0 }}><div style={disp(15, 600, '0')}>{R[i].name}</div><div style={{ marginTop: 3, fontSize: 12, color: MUTED }}>{R[i].blurb.slice(0, 60)}</div></div><div style={{ textAlign: 'right', flex: 'none' }}><div style={disp(15)}>{fmt(R[i].amt)}</div><div style={{ marginTop: 3, ...mono(11), color: MUTED }}>{STAGES[R[i].st]}</div></div></div>)}
                    </div>
                  </div>
                  <div style={{ flex: '1 1 380px', minWidth: 0 }}>
                    <H3 size={20}>Leading sub-sectors</H3>
                    <div style={{ marginTop: 18, display: 'flex', flexDirection: 'column', gap: 10 }}>
                      {subIds.map((k) => <div key={k} style={{ display: 'flex', alignItems: 'center', gap: 12, fontSize: 13 }}><div style={{ width: 128, flex: 'none', fontWeight: 500 }}>{subsG[k][1]}</div><div style={{ flex: 1, height: 14, background: '#D5DCE3' }}><div style={{ height: 14, width: (P.sv[k] / subMax) * 100 + '%', background: colors[subsG[k][0]] }} /></div><div style={{ width: 66, flex: 'none', textAlign: 'right', ...mono(13) }}>{fmt(P.sv[k])}</div></div>)}
                    </div>
                  </div>
                </div>
                <H3 size={20} style={{ marginTop: 64 }}>The five side by side</H3>
                <div style={{ marginTop: 16, borderTop: `2px solid ${INK}`, overflowX: 'auto' }}>
                  <div style={{ minWidth: 640 }}>
                    <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr 0.8fr 1fr 1.4fr', gap: 12, padding: '12px 0', borderBottom: `1px solid ${INK}`, ...mono(11), fontWeight: 500, letterSpacing: '0.1em', textTransform: 'uppercase', color: MUTED }}><div>Country</div><div>Capital</div><div>Rounds</div><div>Median round</div><div>Leading sector</div></div>
                    {FIVE.filter((n) => countries.indexOf(n) >= 0).map((n) => { const p = profileOf(n);
                      return (
                        <div key={n} style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr 0.8fr 1fr 1.4fr', gap: 12, padding: '15px 0', borderBottom: `1px solid ${LINE}`, alignItems: 'center', fontSize: 14 }}>
                          <div style={disp(14)}>{n}</div><div style={{ fontWeight: 600 }}>{fmt(p.cap)}</div><div>{p.ids.length}</div><div>{p.am.length ? fmt(median(p.am)) : '–'}</div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}><Swatch color={colors[p.lead]} size={10} />{cats[p.lead]}</div>
                        </div>
                      ); })}
                  </div>
                </div>
              </>)}
            </section>
            <div style={{ ...wrap, padding: '30px 40px 70px', display: 'flex', flexWrap: 'wrap', gap: 12, justifyContent: 'space-between' }}><Btn solid={false} onClick={() => go(0)}>&larr; The state of {year}</Btn><Btn onClick={() => go(2)}>Next: Funding map &rarr;</Btn></div>
          </div>

          {/* ===== CARD 3 ===== */}
          <div style={cardStyle(2)}>
            <section id="map" style={{ ...wrap, padding: '56px 40px 20px' }}>
              <div style={eyebrow}>Hover a country</div>
              <H2>Funding map</H2>
              <p style={{ margin: '18px 0 0', maxWidth: 660, fontSize: 17, lineHeight: 1.55, color: MUTED }}>Each country is coloured by its leading sector for capital raised. Hover for its biggest rounds; click a country to pin it.</p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px 18px', marginTop: 20, fontSize: 13, color: MUTED }}>
                {cats.map((c, i) => <span key={c} style={{ display: 'inline-flex', alignItems: 'center', gap: 7 }}><Swatch color={colors[i]} size={11} />{c}</span>)}
              </div>
              <div style={{ position: 'relative', marginTop: 24, border: `2px solid ${INK}`, padding: 8, background: '#D5DCE3', boxSizing: 'border-box' }}>
                <div style={{ border: `1px solid ${INK}`, position: 'relative', overflow: 'hidden' }}>
                  <svg viewBox="0 0 760 720" role="img" aria-label="Dot map of Europe, each country coloured by its leading sector. Hover or click a country to see its biggest funding rounds." style={{ display: 'block', width: '100%', height: 'auto', maxHeight: 780 }}>
                    <path d={GEO.grat} fill="none" stroke={INK} strokeOpacity="0.12" strokeWidth="0.7" />
                    {Object.keys(GEO.countries).map((name) => {
                      const ci = countries.indexOf(name), has = ci >= 0 && capBy[ci] > 0.01;
                      const lead = has ? capCat[ci].indexOf(Math.max(...capCat[ci])) : -1, pinned = mapSel === ci && ci >= 0, hov = hoverC === ci && ci >= 0;
                      const op = hov || pinned ? 1 : shownC >= 0 ? (has ? 0.35 : 0.14) : has ? 0.62 + 0.38 * Math.sqrt(capBy[ci] / maxCap) : 0.2;
                      return (
                        <g key={name}>
                          <path d={GEO.countries[name]} stroke={has ? colors[lead] : '#8A97A5'} strokeOpacity={op} strokeWidth={hov || pinned ? 6.8 : has ? 5 : 3} strokeLinecap="round" fill="none" />
                          {ci >= 0 && <path d={GEO.countries[name]} stroke="#000" strokeOpacity="0" strokeWidth="14" strokeLinecap="round" fill="none" onMouseEnter={() => setHoverC(ci)} onMouseLeave={() => setHoverC(-1)} onClick={() => setMapSel(pinned ? -1 : ci)} style={{ cursor: 'pointer' }} />}
                        </g>
                      ); })}
                  </svg>
                  <div style={{ position: 'absolute', right: 16, top: 16, width: 'min(340px,calc(100% - 32px))', background: CARD, border: `2px solid ${INK}`, padding: 6, boxSizing: 'border-box' }}>
                    <div style={{ border: `1px solid ${INK}`, padding: '16px 16px 12px' }}>
                      {hover ? (<>
                        <div style={disp(20)}>{hover.name}</div>
                        <div style={{ marginTop: 7, ...mono(12), color: MUTED }}>{hover.line}</div>
                        <div style={{ marginTop: 12, borderTop: `2px solid ${INK}` }}>
                          {hover.top.map((i) => <div key={i} style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: '9px 0', borderBottom: `1px solid ${LINE}` }}><div style={{ minWidth: 0 }}><div style={{ ...disp(13, 600, '0'), lineHeight: 1.2 }}>{R[i].name}</div><div style={{ fontSize: 12, color: MUTED, marginTop: 3 }}>{R[i].blurb.slice(0, 44)}</div></div><div style={{ textAlign: 'right', flex: 'none' }}><div style={disp(13)}>{fmt(R[i].amt)}</div><div style={{ ...mono(10), color: MUTED, marginTop: 3 }}>{STAGES[R[i].st]}</div></div></div>)}
                        </div>
                      </>) : (<>
                        <div style={{ ...disp(18), lineHeight: 1.15 }}>Hover a country</div>
                        <div style={{ marginTop: 8, fontSize: 14, color: MUTED }}>to see its five biggest rounds.</div>
                      </>)}
                    </div>
                  </div>
                </div>
              </div>
            </section>
            <div style={{ ...wrap, padding: '30px 40px 70px', display: 'flex', flexWrap: 'wrap', gap: 12, justifyContent: 'space-between' }}><Btn solid={false} onClick={() => go(1)}>&larr; Analytics</Btn><Btn onClick={() => go(0)}>Back to The state of {year}</Btn></div>
          </div>
        </div>
      </div>

      {/* ---------------- FOOTER ---------------- */}
      <footer id="method" style={{ marginTop: 90, background: INK, color: BG }}>
        <div style={{ ...wrap, padding: '56px 40px 64px', display: 'flex', flexWrap: 'wrap', gap: 36, justifyContent: 'space-between' }}>
          <div style={{ flex: '1 1 420px', maxWidth: 700 }}>
            <div style={disp(20)}>The Funding Dashboard</div>
            <p style={{ margin: '14px 0 0', fontSize: 14, lineHeight: 1.7, color: '#B9C2CB' }}>
              Data compiled from public funding announcements, January {year} onwards. Amounts converted to GBP at monthly average exchange rates. Amounts typed in search or filters are in pounds. Sources:{' '}
              <a href="https://scaling-europe.beehiiv.com" target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'underline' }}>Scaling Europe</a>,{' '}
              <a href="https://sifted.eu" target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'underline' }}>Sifted</a>,{' '}
              <a href="https://tech.eu" target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'underline' }}>Tech.eu</a>
            </p>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12, fontSize: 15 }}>
            <div style={{ ...mono(12), fontWeight: 500, letterSpacing: '0.14em', textTransform: 'uppercase', color: '#B9C2CB' }}>Contact</div>
            <a href="https://www.linkedin.com/in/dhruv-banerjee-514983287/" target="_blank" rel="noopener noreferrer" style={{ textDecoration: 'underline' }}>LinkedIn</a>
            <a href="mailto:dhruvb363@gmail.com" style={{ textDecoration: 'underline' }}>dhruvb363@gmail.com</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
