/* NYC award-recognised restaurants — roster
 *
 * Vanilla JS, no build step, no framework. Renders docs/data/venues.json.
 *
 * The dashboard next door (app.js) ranks 636 restaurants by what their prix
 * fixe is worth. This page ranks 1,400 by what juries have said about them,
 * which is a different question with different data behind it: most of these
 * restaurants have no menu here, no price, and — until someone spends a Places
 * lookup on them — no confirmed address. So every row has to stay legible when
 * most of its fields are absent, and absent must never render as zero.
 *
 * Two traps carried over from app.js, because the data is the same shape:
 *   1. One slug is "53". Plain objects coerce integer-like keys and reorder
 *      them ahead of string keys, so slug lookups here use a Map.
 *   2. Names carry diacritics ("Café Boulud", "Mắm"). Search folds them on both
 *      sides so "mam" finds "Mắm".
 */
'use strict';

const DATA_URL = 'data/venues.json';
const FETCH_TIMEOUT_MS = 15000;
const PAGE = 120;
/* Values listed per filter group before the group says how many it is hiding. */
const FACET_LIMIT = 14;

const $ = (sel) => document.querySelector(sel);
/* Chrome lookups go through this, not `$`.
 *
 * index.html and venues.js are two files a browser caches independently, so a
 * returning visitor can hold yesterday's HTML against today's JS. Every
 * `$('#thing').textContent = ...` against an element that only exists in the
 * newer HTML throws at boot — and because boot is one call chain, the throw
 * takes the whole roster with it and the visitor gets a blank page until they
 * hard-reload. The `?v=` on the script tag stops the reverse pairing (new HTML,
 * old JS) and cannot help with this one.
 *
 * The dashboard has had this guard for as long as it has had chrome to miss;
 * the roster never got it. A detached span absorbs the write, that one piece
 * of furniture is silently missing, and the 1,420 rows still render. */
const $opt = (sel) => document.querySelector(sel) || el('span');
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
};
/** Fold diacritics + case so "Café" and "cafe" compare equal. */
const fold = (s) =>
  (s == null ? '' : String(s))
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')          // combining diacritics
    .replace(/[‘’ʼ′]/g, "'")  // curly apostrophes -> '
    .replace(/[–—‒−]/g, '-')  // en/em dash, minus -> -
    .replace(/[“”]/g, '"')
    .toLowerCase();

/* Every URL on this page comes from outside it: an award record's source_url
   from the crawled award files, and `rw.reserve` from the Restaurant Week
   listing API — which is re-pulled weekly and reaches the payload without a
   human reading it. A `javascript:` or `data:` value arriving in either would
   become a live link on a Book button. The dashboard checks this in eight
   places and this file checked it in none, on the same data.

   No base is passed to URL() on purpose, and this file used to pass
   location.href. With a base, a bare "www.joesbar.com" resolves RELATIVE to
   this page: it comes back with an http: protocol, passes the very check meant
   to stop it, and renders a Book button that navigates to
   docs/www.joesbar.com — a 404 on our own origin, under a link that says it
   goes to the restaurant. Without a base a relative string throws, which is
   the answer we want. The dashboard's copy of this function has always been
   the no-base one; this is the same implementation, for the same data. */
const isHttpURL = (u) => {
  if (!u) return false;
  try { return /^https?:$/.test(new URL(u).protocol); } catch { return false; }
};

/* Debug-only: ?today=YYYY-MM-DD freezes "today", as on the dashboard — the
   roster now has date-dependent copy of its own, and it must be checkable at
   any date without waiting for one. */
const TODAY_OVERRIDE = (/[?&]today=(\d{4}-\d{2}-\d{2})\b/.exec(location.search) || [])[1] || null;
const todayISO = () => {
  if (TODAY_OVERRIDE) return TODAY_OVERRIDE;
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

/** Format an ISO date as "Sep 6, 2026". The roster outlives its seasons, so
    unlike the dashboard's same-year copy this one keeps the year. */
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const fmtDate = (iso) => {
  if (!iso) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  return m ? `${MONTHS[+m[2] - 1]} ${+m[3]}, ${m[1]}` : iso;
};

/* Round-trip, not just a shape match: Date.parse accepts "2026-02-30" and
   quietly rolls it to March 2, so the regex alone would pass a day that does
   not exist. The same implementation app.js carries, over the same field. */
const isISODate = (s) => {
  if (typeof s !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(s)) return false;
  const d = new Date(`${s}T12:00:00Z`);
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === s;
};

/* What is the Restaurant Week season the payload describes doing today?
 *
 * The roster is the year-round product and the season is one nullable column
 * on it, so this page had no notion of a season ending at all: on 17 September
 * 2026 it still read "636 of them in Summer 2026 Restaurant Week", present
 * tense, eleven days after the programme closed. `program_end` was already in
 * venues.json and simply unused.
 *
 * Three answers, because there are three. The first fix for the above returned
 * a BOOLEAN, and a boolean has to put "we do not know when it ends" somewhere:
 * it put it on `false`, which is the present tense, which is the claim that
 * the prices on this page are ones you can still get. Reproduced on 19
 * September 2026, thirteen days after the programme closed, by serving a
 * payload with `program_end` deleted: the page went back to "636 of them in
 * Summer 2026 Restaurant Week". Deleted, null and "2026-13-40" all did it —
 * the junk date because "2026-09-19" > "2026-13-40" is false as a string
 * comparison, so an unparseable date read as a season still running.
 *
 * That is the dashboard's archiveNote defect, in the same repo, on the same
 * kind of missing date: unknown fell through to the strongest claim. The rule
 * this repo works to is that null means unknown, so unknown gets its own
 * answer and the copy that reads it says so out loud. */
const seasonState = () => {
  const end = STATE.data && STATE.data.program_end;
  if (!isISODate(end)) return 'unknown';
  /* `>` not `>=`: the end date is inclusive everywhere else in this codebase
     (hasEnded, isUrgent, the planner, the countdown), and on the last day of
     the season the programme is still running. */
  return todayISO() > end ? 'ended' : 'running';
};

/* The season's name, or nothing. A payload without `season_label` used to
   render the literal string "undefined Restaurant Week" — the same absence
   the rest of this file is careful to leave blank. */
const seasonLabel = () => {
  const s = STATE.data && STATE.data.season_label;
  return typeof s === 'string' && s.trim() ? s.trim() : null;
};

const STATE = {
  data: null,
  rows: [],
  bySlug: new Map(),
  q: '',
  sort: 'prestige',
  filters: new Map(),   // facet -> Set(values)
  shown: PAGE,
  view: 'list',         // 'list' | 'map'
  pinned: null,         // slug of the venue whose card sits under the map
};

/* ---------- scoring helpers -------------------------------------------- */

/* A 4.9 from 30 people is not better than a 4.5 from 3,000, so the rating sort
   shrinks each score toward the roster mean by how thin its sample is. Same
   treatment the exporter gives the dashboard's ratings, and for the same
   reason: an unweighted star sort puts the least-known rooms on top.

   Both numbers come from the payload rather than being spelled out here. This
   page used to hard-code a prior of three hundred and a 4.4 fallback, while
   every payload in the project shrinks with m = 150 — so the roster ordered
   452 of its 629 rated rows differently from the dashboard, under a comment
   saying the treatment was the same. src/config.py:GOOGLE_PRIOR is the one
   home for it now, and export_venues publishes it beside the mean it was
   shrunk toward. */
let PRIOR = 150;
let RATING_MEAN = 4.4;

function weightedRating(v) {
  if (v.rating == null) return null;
  const n = v.ratings_total || 0;
  return (v.rating * n + RATING_MEAN * PRIOR) / (n + PRIOR);
}

/* ---------- facets ------------------------------------------------------ */

/* Every honour a venue holds, in the payload's own English.
   `top_honor_label` is the single HIGHEST one, which is a different question:
   Daniel holds a Michelin star, but its highest honour is a Beard win, because
   a Beard win scores 88 and one star scores 84 (config/awards.json). Filtering
   on the highest honour therefore hid 7 of the 69 starred restaurants, 12 of
   the 80 Bib Gourmands, 8 of the 194 Beard winners, and 24 of the NYT's own
   Top 100 — a control named "NYT Top 100" that returned 76 rows.
   app.js made this call correctly for the dashboard already ("By TIER, not by
   source"); this is the roster catching up. */
function honoursHeld(v) {
  if (v._honours) return v._honours;
  const out = [];
  for (const a of v.recognition) {
    const h = STATE.data.honors[`${a.source}:${a.level}`];
    if (h && h.label && !out.includes(h.label)) out.push(h.label);
  }
  v._honours = out;
  return out;
}

const FACETS = [
  { key: 'top_honor_label', label: 'Highest honour',
    get: (v) => (v.top_honor_label ? [v.top_honor_label] : []) },
  /* Not a duplicate of the group above: this one answers "has it ever been
     given X", the other "what is the best it holds". A venue appears once in
     the first and once per honour here. */
  { key: 'honour_held', label: 'Honours held (any)', get: honoursHeld },
  { key: 'award_source', label: 'Named by',
    get: (v) => v.award_sources.map((s) => STATE.data.source_labels[s] || s) },
  { key: 'borough', label: 'Borough', get: (v) => (v.borough ? [v.borough] : []) },
  { key: 'status', label: 'Still trading',
    get: (v) => [{ open: 'Open', closed: 'Closed', unknown: 'Unverified' }[v.status]] },
  { key: 'rw', label: 'Restaurant Week',
    get: (v) => [v.rw ? 'In this season' : 'Not participating'] },
  { key: 'cuisine', label: 'Cuisine (Restaurant Week rows only)',
    get: (v) => (v.rw ? v.rw.cuisines : []) },
  /* The only thing on the roster that answers "what does this place actually
     cook". Parsed from Restaurant Week menus, so it exists for those rows and
     not for the 778 that were never in the programme. */
  { key: 'dish', label: 'On the menu (Restaurant Week rows only)',
    get: (v) => v.dishes || [] },
];

/* Every preset here names an honour ("Michelin starred", "NYT Top 100"), so
   every one of them filters on honours HELD. None of them means "and nothing
   better" — which is what filtering on `top_honor_label` quietly meant. */
const PRESETS = [
  { label: 'Michelin starred', apply: () => setFilter('honour_held',
      ['One Michelin star', 'Two Michelin stars', 'Three Michelin stars']) },
  { label: 'Bib Gourmand', apply: () => setFilter('honour_held', ['Bib Gourmand']) },
  { label: 'NYT Top 100', apply: () => setFilter('honour_held', ['NYT Top 100']) },
  { label: 'Beard winners', apply: () => setFilter('honour_held', ['James Beard winner']) },
  { label: 'All three juries agree', apply: () => { clearFilters(); STATE.threeWay = true; } },
  { label: 'In Restaurant Week', apply: () => setFilter('rw', ['In this season']) },
  { label: 'Open', apply: () => setFilter('status', ['Open']) },
  { label: 'Game, offal & odd cuts',
    apply: () => setFilter('dish', ['game meats', 'foie gras', 'bone marrow',
                                    'sweetbreads', 'snails', 'steak tartare']) },
];

function setFilter(key, values) {
  clearFilters();
  STATE.filters.set(key, new Set(values));
}
function clearFilters() {
  STATE.filters.clear();
  STATE.threeWay = false;
}

/* ---------- the URL is the state ---------------------------------------- *

   Everything above lived in memory and nowhere else, so the roster had no way
   to be returned to. The walk that found it: filter to the Michelin-starred
   rooms, search "brooklyn", get 21 of 1,420 — then open one of them on the
   value dashboard, which is what the Restaurant Week pill is for and which
   navigates in this same tab — then press Back. The roster boots from scratch:
   120 of 1,420, no chips, the search box empty. Thirteen clicks of work, and
   the one gesture every browser promises will undo a navigation is what throws
   it away. The same goes for a reload, and for sending someone "look at this".

   The dashboard next door has had this since it had filters, in exactly this
   shape — URLSearchParams inside the hash, `~` between multiple values,
   replaceState so the URL tracks the page without filling the Back button with
   one entry per keystroke. This is the roster catching up, and the two files
   are deliberately readable side by side.

   Read back defensively: a hash is user-editable text — a forwarded link, a
   truncated paste, last season's URL — so a token that cannot be read is
   ignored rather than coerced. The dashboard learned each of these the hard
   way and the comments there name the damage; the two that matter here are an
   unknown facet value (it adds a chip that can match nothing, and the page
   then reads "0 of 1,420", blaming a filter for a value that does not exist)
   and `sort=constructor`, which is inherited from Object.prototype, passes a
   truthy check, and is then called as a comparator. */

function writeHash() {
  const p = new URLSearchParams();
  for (const [key, set] of STATE.filters) if (set.size) p.set(key, [...set].join('~'));
  if (STATE.threeWay) p.set('juries', '3');
  if (STATE.q) p.set('q', $('#q') ? $('#q').value.trim() : STATE.q);
  if (STATE.sort !== 'prestige') p.set('sort', STATE.sort);
  if (STATE.view !== 'list') p.set('view', STATE.view);
  // How far down the list you had read is part of where you were: without it,
  // Back from row 600 lands you at row 120 with no way to tell what happened.
  if (STATE.shown > PAGE) p.set('n', String(STATE.shown));
  const s = p.toString();
  history.replaceState(null, '', s ? `#${s}` : location.pathname + location.search);
}

/** Every value a facet can legitimately produce from the loaded roster. */
function knownFacetValues(f) {
  const out = new Set();
  for (const v of STATE.rows) for (const val of f.get(v)) if (val) out.add(val);
  return out;
}

function readHash() {
  const raw = location.hash.replace(/^#/, '');
  if (!raw) return;
  const p = new URLSearchParams(raw);
  for (const f of FACETS) {
    const v = p.get(f.key);
    if (!v) continue;
    const known = knownFacetValues(f);
    const set = new Set(v.split('~').filter((x) => known.has(x)));
    if (set.size) STATE.filters.set(f.key, set);
  }
  if (p.get('juries') === '3') STATE.threeWay = true;
  const q = p.get('q');
  if (q) {
    STATE.q = fold(q.trim());
    if ($('#q')) $('#q').value = q;
  }
  // Object.hasOwn, not truthiness — see above.
  const s = p.get('sort');
  if (s && Object.hasOwn(SORTS, s)) {
    STATE.sort = s;
    if ($('#sort')) $('#sort').value = s;
  }
  if (p.get('view') === 'map') STATE.view = 'map';
  // A count that is not a count leaves the page at its first page of rows,
  // which is the same place a visitor with no hash at all starts from.
  const n = Number(p.get('n'));
  if (Number.isInteger(n) && n > PAGE) STATE.shown = Math.min(n, STATE.rows.length);
}

/* ---------- filtering + sorting ----------------------------------------- */

function haystack(v) {
  if (v._hay) return v._hay;
  const parts = [v.name, v.borough, v.neighborhood, v.address, v.top_honor_label];
  for (const a of v.recognition) parts.push(a.award, a.person, a.level);
  if (v.rw) parts.push(...v.rw.cuisines);
  if (v.dishes) parts.push(...v.dishes);
  if (v.dishes_maybe) parts.push(...v.dishes_maybe);
  v._hay = fold(parts.filter(Boolean).join(' '));
  return v._hay;
}

/* `exceptKey` leaves one facet out of the test, which is what lets that facet
   count itself honestly. Counting against the FULLY filtered set would zero
   every unselected value in the facet you just used, so a second choice in the
   same group becomes unreachable — you could never say "Brooklyn OR Queens".
   Same rule the dashboard uses, and for the same reason. */
function matches(v, exceptKey) {
  if (STATE.q && !haystack(v).includes(STATE.q)) return false;
  if (STATE.threeWay && v.award_sources.length < 3) return false;
  for (const [key, chosen] of STATE.filters) {
    if (key === exceptKey) continue;
    const facet = FACETS.find((f) => f.key === key);
    const mine = facet.get(v);
    if (!mine.some((m) => chosen.has(m))) return false;
  }
  return true;
}

const SORTS = {
  prestige: (a, b) => b.prestige - a.prestige || b.award_count - a.award_count
                      || a.name.localeCompare(b.name),
  recent: (a, b) => (b.last_award_year || 0) - (a.last_award_year || 0)
                    || b.prestige - a.prestige,
  awards: (a, b) => b.award_count - a.award_count || b.prestige - a.prestige,
  /* Nulls sort last in every direction: a restaurant nobody has rated is not
     the worst-rated one. */
  rating: (a, b) => {
    const x = weightedRating(a), y = weightedRating(b);
    if (x == null && y == null) return b.prestige - a.prestige;
    if (x == null) return 1;
    if (y == null) return -1;
    return y - x;
  },
  name: (a, b) => a.name.localeCompare(b.name),
  oldest: (a, b) => {
    const x = a.first_award_year, y = b.first_award_year;
    if (x == null && y == null) return b.prestige - a.prestige;
    if (x == null) return 1;
    if (y == null) return -1;
    return x - y;
  },
};

/* ---------- rendering --------------------------------------------------- */

const HONOR_CLASS = (key) =>
  !key ? 'none' : key.startsWith('michelin') ? 'michelin'
    : key.startsWith('nyt') ? 'nyt' : 'beard';

/* `status` has three values and the sources have more. A restaurant Google
   reports as CLOSED_TEMPORARILY is `closed` here — you cannot eat there — but
   it has not shut for good, and striking it through as "Closed" says something
   the source did not. status_source carries the verbatim answer, so read it
   for the label rather than flattening the two. */
const TEMPORARY = /CLOSED_TEMPORARILY/i;

function statusPill(v) {
  const temporary = v.status === 'closed' && TEMPORARY.test(v.status_source || '');
  const label = temporary ? 'Temporarily closed'
    : { open: 'Open', closed: 'Closed', unknown: 'Unverified' }[v.status];
  const pill = el('span', `pill status-${v.status}${temporary ? ' temporary' : ''}`,
                  label);
  pill.title = temporary
    ? `${v.status_source} — not shut for good; check before you travel`
    : v.status_source
      ? `Status from ${v.status_source}`
      : 'Nothing has confirmed whether this restaurant is still trading. '
        + 'That is a gap in our data, not a claim that it closed.';
  return pill;
}

function awardLine(a) {
  const li = el('li', 'awardRow');
  li.append(el('span', 'awardYear', a.year == null ? '—' : String(a.year)));
  /* Michelin and the Times store the honour in `level` as a machine value
     ("3 stars", "nyt_100_best"); config/awards.json is where those get their
     English, and the payload carries that map so this file never spells an
     honour itself. The Beard rows already read as prose, so they keep theirs. */
  const honour = STATE.data.honors[`${a.source}:${a.level}`];
  const what = a.award
    ? `${a.award} · ${a.level}`
    : (honour ? honour.label : a.level) || 'recognised';
  const label = a.rank ? `${what} (no. ${a.rank})` : what;
  if (isHttpURL(a.url)) {
    const link = el('a', 'awardWhat', label);
    link.href = a.url;
    link.rel = 'noreferrer noopener';
    link.target = '_blank';
    li.append(link);
  } else {
    li.append(el('span', 'awardWhat', label));
  }
  /* The Beard awards are frequently to a chef rather than to a room, and
     hiding that makes the roster claim the restaurant won things it did not. */
  if (a.person) li.append(el('span', 'awardWho', a.person));
  return li;
}

function renderRow(v) {
  const row = el('article', 'venue');

  const head = el('div', 'venueHead');
  const title = el('h2', 'venueName', v.name);
  head.append(title);
  if (v.top_honor_label) {
    /* The year, when the honour is not from that source's most recent
       selection. "James Beard winner" with nothing after it reads as news, and
       387 of the 782 badges here are for an award given as long ago as 1993 --
       several to restaurants that have since closed.

       The year says WHEN, never that the honour was lost: a Michelin star is a
       standing selection and does lapse, a Beard win is an event and does not.
       Both are answered honestly by naming the year and claiming nothing else.

       Kept out of top_honor_label itself on purpose -- that string is a facet
       value in the "Highest honour" filter, and folding the year into it would
       turn one option into several hundred. */
    const label = v.top_honor_label
      + (v.top_honor_year && !v.top_honor_is_latest ? ` · ${v.top_honor_year}` : '');
    head.append(el('span', `pill honor ${HONOR_CLASS(v.top_honor)}`, label));
  }
  head.append(statusPill(v));
  if (v.rw) {
    /* The row is where somebody actually decides, and it was the one part of
       this page that never mentioned the season at all. On 19 September 2026,
       thirteen days after Summer 2026 closed, every one of the 636 rows still
       read "Restaurant Week $60" in the dashboard's value green — the same
       pill, the same colour, the same tense it had in July. Driven against a
       payload whose season was still running, and against one with no end date
       at all, it rendered identically in all three.

       The coverage banner did say the programme had ended, but it says it once,
       at the top of a page that runs to 1,420 rows, and it is the ROW that
       carries a price. A price with no tense on it is read as a price.

       The pill keeps the money — what the prix fixe was is a true fact and it
       is why the row is interesting — and stops implying you can pay it. */
    const state = seasonState();
    const tiers = v.rw.price_tiers.join(' / ') || 'Restaurant Week';
    const suffix = state === 'ended' ? ' · ended'
      : state === 'unknown' ? ' · dates unconfirmed' : '';
    const rw = el('a', `pill rw${state === 'running' ? '' : ` ${state}`}`,
                  `Restaurant Week ${tiers}${suffix}`);
    /* Straight to this restaurant on the dashboard, not to the top of it. The
       dashboard reads `#r=<slug>` and openRestaurant() clears whatever was
       filtered so the link wins -- landing someone on a 636-row list and
       leaving them to find the name again is not a link, it is a hint. */
    rw.href = `restaurant-week.html#r=${encodeURIComponent(v.rw.slug)}`;
    const programme = seasonLabel() ? `${seasonLabel()} Restaurant Week` : 'Restaurant Week';
    rw.title = state === 'ended'
      ? `${programme} ended ${fmtDate(STATE.data.program_end)}. This was its prix fixe. `
        + 'Open the archived listing on the value dashboard — menu, gap against '
        + 'à la carte and subway walk.'
      : state === 'unknown'
        ? `This was ${v.name}'s ${programme} prix fixe. Whether that programme is `
          + 'still running is unknown — the payload carries no usable end date. '
          + 'Open its listing on the value dashboard.'
        : 'Open this restaurant on the value dashboard — its prix fixe, '
          + 'menu, gap against à la carte and subway walk.';
    head.append(rw);
  }
  row.append(head);

  const meta = el('p', 'venueMeta');
  const place = [v.neighborhood, v.borough].filter(Boolean).join(', ')
             || v.address || 'location not established';
  meta.append(el('span', 'where', place));
  if (v.rating != null) {
    meta.append(el('span', 'rating',
      `${v.rating.toFixed(1)}★ (${(v.ratings_total || 0).toLocaleString()})`));
  }
  const span = v.first_award_year == null ? null
    : v.first_award_year === v.last_award_year ? String(v.first_award_year)
    : `${v.first_award_year}–${v.last_award_year}`;
  if (span) meta.append(el('span', 'era', `recognised ${span}`));
  if (v.award_sources.length > 1) {
    meta.append(el('span', 'juries', `${v.award_sources.length} juries`));
  }
  /* The one thing a person actually wants to DO with a row. Only the 636
     Restaurant Week rows carry a link -- the award files have no websites in
     them -- so this renders for those and is simply absent for the rest,
     rather than a dead control that looks the same for everyone. */
  if (v.dishes && v.dishes.length) {
    /* Six is where the line wraps on a phone; the row says how many it kept
       back rather than trailing off. */
    const head = v.dishes.slice(0, 6);
    const rest = v.dishes.length - head.length;
    const d = el('span', 'dishes', head.join(' · ') + (rest ? ` +${rest}` : ''));
    d.title = "Matched on this restaurant's Restaurant Week menu: "
            + v.dishes.join(', ');
    meta.append(d);
  }
  /* The weaker claim, marked rather than blended in — the same grammar the
     dashboard uses for an estimated price. The word is on the menu, but the
     dish may not be about it: most of these are truffle honey or truffle mayo
     rather than a truffle dish. Filters ignore these; search still finds them. */
  if (v.dishes_maybe && v.dishes_maybe.length) {
    const m = el('span', 'dishesMaybe', v.dishes_maybe.slice(0, 4).join(' · ') + '?');
    m.title = 'Mentioned on the menu, but as a garnish or in passing rather '
            + 'than as the dish: ' + v.dishes_maybe.join(', ')
            + '. The filters deliberately do not count these.';
    meta.append(m);
  }
  if (v.rw && isHttpURL(v.rw.reserve)) {
    const book = el('a', 'reserve', 'Book');
    book.href = v.rw.reserve;
    book.rel = 'noreferrer noopener';
    book.target = '_blank';
    /* The word stays "Book": this link is the restaurant's own reservations
       page or website, it works year-round, and calling it something vaguer
       once the season is over would cost a reader a working control without
       making anything truer. What it must not do is let the pill above it be
       read as the thing being booked — so out of season the name says which
       prices you are about to be offered. The pill carries the same fact
       visibly, for the phone, where nothing has a tooltip. */
    const state = seasonState();
    book.title = state === 'running'
      ? `Reservations or website for ${v.name}`
      : `Reservations or website for ${v.name}, at its normal prices — `
        + (state === 'ended'
          ? `the Restaurant Week menu ended ${fmtDate(STATE.data.program_end)}.`
          : 'the Restaurant Week menu may no longer be offered.');
    meta.append(book);
  }
  row.append(meta);

  if (v.recognition.length) {
    const det = el('details', 'awards');
    det.append(el('summary', null,
      `${v.award_count} award record${v.award_count === 1 ? '' : 's'}`));
    const list = el('ul', 'awardList');
    for (const a of v.recognition) list.append(awardLine(a));
    det.append(list);
    row.append(det);
  }
  return row;
}

function renderFacets() {
  const box = $('#facets');
  box.textContent = '';
  for (const f of FACETS) {
    /* Counted against what is actually on screen, not against the whole
       roster. Filtered to the 62 Michelin-starred venues, this group used to
       still say "Manhattan 1104" — a count is a promise about what clicking
       will give you, and that one could promise 55 rows and deliver none. */
    const counts = new Map();
    for (const v of STATE.rows) {
      if (!matches(v, f.key)) continue;
      for (const val of f.get(v)) {
        if (val) counts.set(val, (counts.get(val) || 0) + 1);
      }
    }
    // A ticked value stays on screen at zero, or there is no way to untick it.
    for (const val of (STATE.filters.get(f.key) || [])) {
      if (!counts.has(val)) counts.set(val, 0);
    }
    if (counts.size < 2 && !STATE.filters.has(f.key)) continue;
    const group = el('div', 'facet');
    group.append(el('h3', null, f.label));
    const chosen = STATE.filters.get(f.key);
    const sorted = [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
    /* Cuisine has far more values than fit, so the list is cut -- but a cut
       list that does not say it was cut reads as "those are all of them", and
       someone looking for Georgian would conclude the roster has none. Any
       chosen value is kept regardless of where it sorts, or ticking it and
       then searching would make the tick vanish. */
    const shown = sorted.slice(0, FACET_LIMIT);
    const shownVals = new Set(shown.map(([v]) => v));
    for (const [val, n] of sorted) {
      if (chosen && chosen.has(val) && !shownVals.has(val)) shown.push([val, n]);
    }
    const hidden = sorted.length - shown.length;
    for (const [val, n] of shown) {
      const id = `f-${f.key}-${fold(val).replace(/\W+/g, '-')}`;
      const label = el('label', 'facetOpt');
      const cb = el('input');
      cb.type = 'checkbox';
      cb.id = id;
      cb.checked = Boolean(chosen && chosen.has(val));
      cb.addEventListener('change', () => {
        const set = STATE.filters.get(f.key) || new Set();
        if (cb.checked) set.add(val); else set.delete(val);
        if (set.size) STATE.filters.set(f.key, set); else STATE.filters.delete(f.key);
        STATE.shown = PAGE;
        apply();
      });
      label.append(cb, el('span', 'facetName', val), el('span', 'facetN', String(n)));
      group.append(label);
    }
    if (hidden > 0) {
      const note = el('p', 'facetMore',
        `+${hidden} more — use the search box`);
      note.title = `${sorted.length} values in total; the ${shown.length} `
                 + `commonest are listed. Search matches all of them.`;
      group.append(note);
    }
    box.append(group);
  }
}

function renderPresets() {
  const box = $('#presets');
  box.textContent = '';
  for (const p of PRESETS) {
    const b = el('button', 'preset', p.label);
    b.type = 'button';
    b.addEventListener('click', () => { p.apply(); STATE.shown = PAGE; apply(); });
    box.append(b);
  }
}

function renderActive() {
  const box = $('#activeFilters');
  box.textContent = '';
  const chips = [];
  if (STATE.threeWay) chips.push(['Named by all three juries', () => { STATE.threeWay = false; }]);
  for (const [key, set] of STATE.filters) {
    for (const val of set) {
      chips.push([val, () => {
        set.delete(val);
        if (!set.size) STATE.filters.delete(key);
      }]);
    }
  }
  box.hidden = chips.length === 0;
  for (const [label, undo] of chips) {
    const chip = el('button', 'chip', `${label} ✕`);
    chip.type = 'button';
    chip.addEventListener('click', () => { undo(); STATE.shown = PAGE; apply(); });
    box.append(chip);
  }
  const n = chips.length;
  $('#filterCount').textContent = String(n);
  $('#filterCount').hidden = n === 0;
  $('#clearBtn').hidden = n === 0;
}

/* Say which thing found nothing.

   This page shipped the static "Nothing matches those filters." from
   index.html and never touched it, so every empty result blamed filters —
   including a typo in the search box, which is the commonest way to reach zero
   rows and the one case where the Clear filters button beside it cannot help.

   The dashboard had the same bug and the same fix; what decides the wording is
   whether the term matches anything IGNORING the filters, because "are filters
   set" answers a different question. Here it is doubly useless: the roster's
   Restaurant Week and Still-trading facets start empty, so filters usually are
   not set and the sentence was simply wrong. */
function emptyMessage() {
  const msg = $('#emptyMsg');
  if (!msg) return;
  if (!STATE.rows.length) {
    msg.textContent = 'The roster loaded, but it lists no restaurants. '
      + 'That is a problem with the data, not with anything you set.';
    return;
  }
  const term = $('#q') && $('#q').value.trim();
  if (!STATE.q) {
    msg.textContent = STATE.threeWay
      ? 'No restaurant is named by all three juries with those filters.'
      : 'Nothing matches those filters.';
    return;
  }
  const loose = STATE.rows.filter((v) => haystack(v).includes(STATE.q)).length;
  msg.textContent = loose
    ? `\u201c${term}\u201d matches ${loose} restaurant${loose === 1 ? '' : 's'}, `
      + 'but the filters remove them all.'
    : `Nothing matches \u201c${term}\u201d. Check the spelling, or search a chef, `
      + 'a neighbourhood or an award.';
}

function apply() {
  const hits = STATE.rows.filter(matches);
  hits.sort(SORTS[STATE.sort] || SORTS.prestige);

  const box = $('#rows');
  box.textContent = '';
  if (STATE.view === 'list') {
    for (const v of hits.slice(0, STATE.shown)) box.append(renderRow(v));
  } else {
    renderMap(hits);
  }

  $('#shown').textContent = String(Math.min(STATE.shown, hits.length));
  $('#total').textContent = String(hits.length);
  $('#empty').hidden = hits.length !== 0;
  if (!hits.length) emptyMessage();
  const more = $('#showMore');
  more.hidden = STATE.view !== 'list' || hits.length <= STATE.shown;
  more.textContent = `Show ${Math.min(PAGE, hits.length - STATE.shown)} more`;
  renderActive();
  /* Always, now that the counts depend on the filters. Re-rendering steals
     focus from the checkbox you just used, so it is handed straight back. */
  const focused = document.activeElement && document.activeElement.id;
  renderFacets();
  if (focused) {
    const again = document.getElementById(focused);
    if (again) again.focus();
  }
  // Last, and on every path: apply() is the one funnel every control goes
  // through, so recording the state here is what makes "every control" true.
  writeHash();
}

/* ---------- map ---------------------------------------------------------

   The roster page allows no third-party origin at all -- no tile server, no
   CDN -- which rules out Leaflet and the dashboard's CARTO tiles. What a dot
   map of one city actually needs from a basemap is a single recognisable
   shape, so the base layer is the five boroughs' shoreline from
   docs/data/boroughs.json (NYC Planning geometry, simplified by
   src/fetch_borough_outlines.py), drawn as plain SVG paths. Everything on
   the map is also in the list -- the map is the picture, the list is the
   record, and keyboard and screen-reader users lose nothing to it. */

const BOROUGHS_URL = 'data/boroughs.json';
const svgEl = (tag, attrs) => {
  const n = document.createElementNS('http://www.w3.org/2000/svg', tag);
  for (const [k, val] of Object.entries(attrs || {})) n.setAttribute(k, val);
  return n;
};

let MAP = null;           // { svg, dots, project } once the geometry is in
let MAP_LOADING = false;

async function timedFetch(url) {
  /* Same deadline treatment as the payload fetch below, for the same reason:
     a request that is accepted and never answered would otherwise hang the
     map forever with no error to catch. */
  const ctl = new AbortController();
  const timer = setTimeout(() => ctl.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(url, { cache: 'no-cache', signal: ctl.signal });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

function buildMap(geo) {
  const pts = geo.boroughs.flatMap((b) => b.rings.flat());
  const lngs = pts.map((p) => p[0]);
  const lats = pts.map((p) => p[1]);
  const lng0 = Math.min(...lngs); const lng1 = Math.max(...lngs);
  const lat0 = Math.min(...lats); const lat1 = Math.max(...lats);
  /* Equirectangular with the east-west axis shrunk by cos(mid-latitude), so
     a mile north and a mile east are the same length on screen. */
  const K = Math.cos(((lat0 + lat1) / 2) * Math.PI / 180);
  const W = 700;
  const scale = W / ((lng1 - lng0) * K);
  const H = Math.round((lat1 - lat0) * scale);
  const PAD = 8;
  const project = (lat, lng) => [
    PAD + (lng - lng0) * K * scale,
    PAD + (lat1 - lat) * scale,
  ];
  const svg = svgEl('svg', {
    viewBox: `0 0 ${W + 2 * PAD} ${H + 2 * PAD}`,
    role: 'img',
    'aria-label': 'Dot map of the current selection across the five boroughs. '
      + 'The list view carries the same restaurants with full details.',
  });
  const land = svgEl('g', { class: 'mapLand' });
  for (const b of geo.boroughs) {
    for (const ring of b.rings) {
      land.append(svgEl('path', {
        d: 'M' + ring.map(([x, y]) => project(y, x).map((n) => n.toFixed(1)).join(' ')).join('L') + 'Z',
      }));
    }
  }
  svg.append(land);
  const dots = svgEl('g', { class: 'mapDots' });
  svg.append(dots);
  return { svg, dots, project };
}

function renderMap(hits) {
  if (!MAP) return;
  MAP.dots.textContent = '';
  let placed = 0;
  /* Painted in reverse sort order so the top of the CURRENT sort -- highest
     prestige, best rating, whatever is chosen -- is painted last and sits on
     top of the pile-ups in midtown. */
  for (const v of [...hits].reverse()) {
    if (v.lat == null || v.lng == null) continue;
    placed += 1;
    const [x, y] = MAP.project(v.lat, v.lng);
    const dot = svgEl('circle', {
      cx: x.toFixed(1), cy: y.toFixed(1), r: 2.6,
      class: `dot ${v.status}`, 'data-slug': v.slug,
    });
    const label = svgEl('title');
    label.textContent = v.top_honor_label
      ? `${v.name} — ${v.top_honor_label}` : v.name;
    dot.append(label);
    MAP.dots.append(dot);
  }
  /* The detail card under the map is inside a region the markup labels "Map of
     the current selection", and it outlived the selection. Tap a dot, then
     search for something that matches nothing: the map empties to zero dots,
     the page says nothing matches, and the card goes on showing the restaurant
     you tapped — with its Book link — as though it were the one thing left.
     Reproduced on a phone, which is where a stray tap is easiest.
     A pinned venue the current filters exclude is no longer part of this
     selection, so it stops being displayed as part of it. */
  if (STATE.pinned && !hits.some((v) => v.slug === STATE.pinned)) {
    STATE.pinned = null;
    $opt('#mapDetail').textContent = '';
  }
  const off = hits.length - placed;
  $('#mapGaps').textContent = off
    ? `${placed.toLocaleString()} of the ${hits.length.toLocaleString()} shown are on the map; `
      + `${off.toLocaleString()} have no confirmed location yet and appear only in the list.`
    : `All ${placed.toLocaleString()} shown are on the map.`;
}

function setView(view) {
  STATE.view = view;
  $('#viewList').setAttribute('aria-pressed', String(view === 'list'));
  $('#viewMap').setAttribute('aria-pressed', String(view === 'map'));
  const list = view === 'list';
  $('#rows').hidden = !list;
  $('#mapView').hidden = list;
  if (list || MAP) { apply(); return; }
  if (MAP_LOADING) return;
  MAP_LOADING = true;
  $('#mapGaps').textContent = 'Loading the map…';
  timedFetch(BOROUGHS_URL).then((geo) => {
    MAP = buildMap(geo);
    $('#mapWrap').append(MAP.svg);
    apply();
  }).catch((err) => {
    const why = err.name === 'AbortError'
      ? 'it did not answer within fifteen seconds' : err.message;
    $('#mapGaps').textContent =
      `Could not load the map outlines (${why}). The list view has everything.`;
  }).finally(() => { MAP_LOADING = false; });
}

function wireMapDetail() {
  /* One listener on the dot layer; a dot click swaps the detail card under
     the map for the same row the list would render. */
  $('#mapWrap').addEventListener('click', (e) => {
    const hit = e.target.closest ? e.target.closest('.dot') : null;
    const slug = hit && hit.getAttribute('data-slug');
    if (!slug) return;
    const v = STATE.bySlug.get(slug);
    if (!v) return;
    STATE.pinned = slug;
    const box = $('#mapDetail');
    box.textContent = '';
    box.append(renderRow(v));
  });
}

function renderCoverage() {
  const c = STATE.data.counts;
  const box = $opt('#coverage');
  box.hidden = false;
  const p = el('p');
  p.append(el('strong', null, `${c.with_recognition.toLocaleString()} recognised restaurants`));
  // Past tense once the programme has closed. The count is a historical fact
  // about who took part, and the present tense made it read as a list of
  // places you could still book under the Restaurant Week price.
  const state = seasonState();
  const label = seasonLabel();
  const programme = label ? `${label} Restaurant Week` : 'Restaurant Week';
  p.append(document.createTextNode(state === 'running'
    ? `, ${c.in_restaurant_week} of them in ${programme} `
      + `(${c.both} are both). `
    : `, ${c.in_restaurant_week} of which took part in ${programme} `
      + `(${c.both} are both). `));
  if (state === 'ended') {
    p.append(document.createTextNode(
      `That programme ended ${fmtDate(STATE.data.program_end)}; its prices and menus are over. `
      + `Everything else on this page is year-round. `));
  }
  // Unknown is not "still running", and it is not an ending either. It is the
  // one case where the page cannot tell a reader whether these prices are
  // buyable, so it says exactly that instead of picking the flattering half.
  if (state === 'unknown') {
    p.append(document.createTextNode(
      `Whether that programme is still running is unknown: the payload carries no `
      + `usable end date for it, so treat its prices and menus as a record of what `
      + `was offered rather than as something you can book. `
      + `Everything else on this page is year-round. `));
  }
  if (c.unverified) {
    p.append(document.createTextNode(
      `${c.unverified.toLocaleString()} have no confirmed open/closed status yet — `
      + `they are shown as Unverified rather than assumed open.`));
  }
  box.append(p);
}

/* ---------- boot -------------------------------------------------------- */

function wire() {
  const q = $('#q');
  q.addEventListener('input', () => {
    STATE.q = fold(q.value.trim());
    STATE.shown = PAGE;
    apply();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === '/' && document.activeElement !== q) {
      e.preventDefault();
      q.focus();
    }
  });
  $('#sort').addEventListener('change', (e) => { STATE.sort = e.target.value; apply(); });
  $('#filterBtn').addEventListener('click', () => {
    const panel = $('#panel');
    panel.hidden = !panel.hidden;
    $('#filterBtn').setAttribute('aria-expanded', String(!panel.hidden));
  });
  $('#showMore').addEventListener('click', () => { STATE.shown += PAGE; apply(); });
  $('#viewList').addEventListener('click', () => setView('list'));
  $('#viewMap').addEventListener('click', () => setView('map'));
  wireMapDetail();
  for (const id of ['#clearBtn', '#clearBtn2']) {
    $(id).addEventListener('click', () => {
      clearFilters();
      STATE.q = '';
      $('#q').value = '';
      STATE.shown = PAGE;
      apply();
    });
  }
  /* Changing only the hash is a same-document navigation, so boot() does not
     re-run: without this, pasting or editing a filter URL in the bar of an
     already-open roster silently does nothing, and the page goes on showing
     the selection it had while its own URL describes a different one. The
     dashboard has carried this since it had filters and its comment says the
     same thing — the roster's URL is new, so it inherits the lesson rather
     than rediscovering it. Found the same way, by pasting one.

     replaceState does not fire hashchange, so the writeHash() at the end of
     apply() cannot re-enter this. */
  addEventListener('hashchange', () => {
    clearFilters();
    STATE.q = '';
    $('#q').value = '';
    STATE.sort = 'prestige';
    $('#sort').value = 'prestige';
    STATE.shown = PAGE;
    STATE.view = 'list';
    readHash();
    setView(STATE.view);
  });

  const toTop = $('#toTop');
  toTop.addEventListener('click', () => window.scrollTo({ top: 0 }));
  window.addEventListener('scroll', () => { toTop.hidden = window.scrollY < 800; },
                          { passive: true });

  /* Same key the dashboard uses, so a viewer's choice survives the hop. */
  let saved = null;
  try { saved = localStorage.getItem('rw-theme'); } catch { /* private mode */ }
  if (saved) document.documentElement.dataset.theme = saved;
  $('#themeToggle').addEventListener('click', () => {
    const cur = document.documentElement.dataset.theme
      || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    const next = cur === 'dark' ? 'light' : 'dark';
    document.documentElement.dataset.theme = next;
    try { localStorage.setItem('rw-theme', next); } catch { /* private mode */ }
  });
}

async function boot() {
  let payload;
  /* 1.2 MB of roster comes down before there is a row to draw, and until it
     lands the page is a masthead over nothing — which reads as broken rather
     than as busy. The dashboard next door says this already; the roster said
     nothing at all, so a slow connection and a dead one looked identical.
     render() clears this by emptying #rows; the failure path clears it too. */
  $('#rows').append(el('p', 'empty', 'Loading the roster…'));
  try {
    /* A fetch that is accepted and never answered hangs forever: `res.ok` and
       a thrown network error both need a response, and neither arrives. The
       catch below is good and could not be reached that way — the page simply
       stayed blank, with not even the loading line, indefinitely. */
    const ctl = new AbortController();
    const timer = setTimeout(() => ctl.abort(), FETCH_TIMEOUT_MS);
    try {
      const res = await fetch(DATA_URL, { cache: 'no-cache', signal: ctl.signal });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      payload = await res.json();
    } finally {
      clearTimeout(timer);
    }
  } catch (err) {
    const why = err.name === 'AbortError'
      ? 'it did not answer within fifteen seconds' : err.message;
    $('#rows').textContent = '';
    $('#rows').append(el('p', 'empty',
      `Could not load the roster (${why}). The data file is docs/data/venues.json.`));
    return;
  }
  STATE.data = payload;
  STATE.rows = payload.venues;
  for (const v of STATE.rows) STATE.bySlug.set(v.slug, v);

  /* Published values win over the fallbacks above, so the roster and the
     dashboard shrink by the same weight of doubt toward the same mean. Derived
     here only if the payload predates those keys. */
  if (payload.google_prior) PRIOR = payload.google_prior;
  if (payload.google_mean != null) {
    RATING_MEAN = payload.google_mean;
  } else {
    const rated = STATE.rows.filter((v) => v.rating != null);
    if (rated.length) {
      RATING_MEAN = rated.reduce((s, v) => s + v.rating, 0) / rated.length;
    }
  }

  // Chrome, not content: $opt so a cached index.html without one of these
  // costs that line rather than the whole roster. #rows stays on $ — if the
  // row host is missing there is no page to degrade into, and a thrown error
  // is more honest than a silent blank.
  $opt('#rosterCount').textContent = `${payload.counts.venues.toLocaleString()} restaurants`;
  $opt('#footProvenance').textContent =
    `Built ${payload.generated_at.slice(0, 10)} from the Michelin 2025 NYC selection, `
    + `James Beard Foundation awards 1991–2026, and the New York Times Top 100. `
    + `${payload.counts.mappable.toLocaleString()} of ${payload.counts.venues.toLocaleString()} `
    + `venues have confirmed coordinates.`;

  renderCoverage();
  renderPresets();
  wire();
  // After the rows are in STATE (readHash validates values against them) and
  // after the controls exist (it writes the search box and the sort select),
  // but before the first render, so a restored page draws once.
  readHash();
  if (STATE.view === 'map') setView('map'); else apply();
}

boot();
