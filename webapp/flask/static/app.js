/* app.js — Watch Deals frontend */

let allDeals = [];

/* Dashboard config (trend-chart time ranges), fetched fresh on load from /api/config
   so editing data/dashboard_config.json on the box changes the range buttons with no
   code change. These are the fallbacks if the fetch fails. */
const DEFAULT_TREND_CONFIG = {
  trend_ranges: [
    { label: '1M', months: 1 },
    { label: '2M', months: 2 },
    { label: '3M', months: 3 },
    { label: '6M', months: 6 },
    { label: 'All', months: null },
  ],
  default_range: '3M',
};
let trendConfig = DEFAULT_TREND_CONFIG;

async function fetchConfig() {
  try {
    const res = await fetch('/api/config');
    if (!res.ok) return;
    const cfg = await res.json();
    if (cfg && Array.isArray(cfg.trend_ranges) && cfg.trend_ranges.length) {
      trendConfig = {
        trend_ranges: cfg.trend_ranges,
        default_range: cfg.default_range
          || cfg.trend_ranges[cfg.trend_ranges.length - 1].label,
      };
    }
  } catch { /* keep the built-in defaults */ }
}

/* Active column sort. Default = newest first (date_seen, descending). */
let sortState = { column: 'date_seen', dir: 'desc' };

/* ── Column visibility ── */
const COL_KEYS = ['price', 'title', 'brand', 'model', 'ref', 'dial', 'source', 'date_seen', 'trend'];
const LS_COL_KEY = 'deals-hidden-cols';
/* Mobile keeps its own column prefs so shrinking the phone view doesn't clobber the
   desktop choice. With nothing stored, mobile defaults to the essential set
   (hot/price/brand/model visible), hiding the rest — still reachable via Columns.
   Source is hidden by default while r/watchexchange is the only source (the badge is
   the same on every row); revisit if a second source is added. */
const LS_COL_KEY_MOBILE = 'deals-hidden-cols-mobile';
const MOBILE_DEFAULT_HIDDEN = ['title', 'ref', 'dial', 'source', 'date_seen', 'trend'];
const mobileMQ = (typeof matchMedia !== 'undefined')
  ? matchMedia('(max-width: 768px)')
  : { matches: false, addEventListener() {} };

function activeColKey() { return mobileMQ.matches ? LS_COL_KEY_MOBILE : LS_COL_KEY; }

/* Pure: turn a stored string (or null = nothing stored) into the hidden-column Set.
   null on the mobile key seeds the essential-only default; null on desktop = show all. */
function loadHiddenCols(raw, key) {
  if (raw == null) {
    return key === LS_COL_KEY_MOBILE ? new Set(MOBILE_DEFAULT_HIDDEN) : new Set();
  }
  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.filter((k) => COL_KEYS.includes(k)));
  } catch { return new Set(); }
}

function readHiddenCols() {
  const key = activeColKey();
  try {
    const raw = (typeof localStorage !== 'undefined') ? localStorage.getItem(key) : null;
    return loadHiddenCols(raw, key);
  } catch { return loadHiddenCols(null, key); }
}

function saveHiddenCols(hidden) {
  try {
    (typeof localStorage !== 'undefined') &&
      localStorage.setItem(activeColKey(), JSON.stringify([...hidden]));
  } catch { /* storage unavailable */ }
}

let hiddenCols = readHiddenCols();

function applyColVisibility() {
  hiddenCols.forEach((key) => {
    document.querySelectorAll(`.col-${key}`).forEach((el) => { el.style.display = 'none'; });
  });
  COL_KEYS.filter((k) => !hiddenCols.has(k)).forEach((key) => {
    document.querySelectorAll(`.col-${key}`).forEach((el) => { el.style.display = ''; });
  });
}

/* ── Data fetch ── */
async function fetchData() {
  try {
    const [dealsRes, watchesRes] = await Promise.all([
      fetch('/api/deals'),
      fetch('/api/watches'),
    ]);
    allDeals = await dealsRes.json();
    await watchesRes.json(); // reserved for future use
  } catch (e) {
    document.getElementById('result-count').textContent = 'Failed to load deals.';
    return;
  }
  buildSourceCheckboxes();
  populateDropdowns();
  updateLastSync();
  render();
}

/* ── Populate dropdowns from deal data ── */
function populateDropdowns() {
  const unique = (key) =>
    [...new Set(allDeals.map((d) => d[key]).filter(Boolean))].sort();

  populateSelect('brand-select', unique('brand'), 'All brands');
  populateSelect('dial-select', unique('dial').map(capitalize), 'All dials', unique('dial'));
  populateSelect('strap-select', unique('strap').map(capitalize), 'All straps', unique('strap'));

  const sizes = [...new Set(allDeals.map((d) => d.size_mm).filter(Boolean))].sort((a, b) => a - b);
  populateSelect('size-select', sizes.map((s) => `${s}mm`), 'All sizes', sizes.map(String));

  updateModelDropdown();
}

function populateSelect(id, labels, placeholder, values = null) {
  const sel = document.getElementById(id);
  const current = sel.value;
  sel.innerHTML = `<option value="">${placeholder}</option>`;
  labels.forEach((label, i) => {
    const opt = document.createElement('option');
    opt.value = values ? values[i] : label;
    opt.textContent = label;
    sel.appendChild(opt);
  });
  if (current) sel.value = current;
}

function updateModelDropdown() {
  const brand = document.getElementById('brand-select').value;
  const subset = brand ? allDeals.filter((d) => d.brand === brand) : allDeals;
  const models = [...new Set(subset.map((d) => d.model).filter(Boolean))].sort();
  const current = document.getElementById('model-select').value;
  populateSelect('model-select', models, 'All models');
  if (current && models.includes(current)) document.getElementById('model-select').value = current;
}

/* ── Source checkboxes (built after data loads) ── */
function buildSourceCheckboxes() {
  const sources = [...new Set(allDeals.map((d) => d.source).filter(Boolean))].sort();
  const group = document.getElementById('source-group');
  group.innerHTML = sources
    .map(
      (s) => {
        const safe = escapeHtml(s);
        return `
    <label class="checkbox-row">
      <span class="checkbox-box checked">
        <input type="checkbox" class="source-checkbox" value="${safe}" checked>
      </span>
      <span class="checkbox-text">${safe}</span>
    </label>`;
      }
    )
    .join('');

  group.querySelectorAll('.checkbox-row').forEach((row) => {
    row.addEventListener('click', (e) => {
      if (e.target.tagName === 'INPUT') return;
      const cb = row.querySelector('input');
      cb.checked = !cb.checked;
      row.querySelector('.checkbox-box').classList.toggle('checked', cb.checked);
      render();
    });
    row.querySelector('input').addEventListener('change', (e) => {
      row.querySelector('.checkbox-box').classList.toggle('checked', e.target.checked);
      render();
    });
  });
}

/* ── Last sync time ── */
function updateLastSync() {
  if (!allDeals.length) return;
  const latest = allDeals.reduce((a, b) =>
    (a.date_seen || '') > (b.date_seen || '') ? a : b
  );
  document.getElementById('last-sync').textContent = relativeTime(latest.date_seen);
}

/* ── Filters ── */
function getFilters() {
  const checkedSources = [...document.querySelectorAll('.source-checkbox:checked')].map(
    (cb) => cb.value
  );
  return {
    hotOnly: document.getElementById('hot-toggle').getAttribute('aria-pressed') === 'true',
    priceMin: parseFloat(document.getElementById('price-min').value) || null,
    priceMax: parseFloat(document.getElementById('price-max').value) || null,
    brand:  document.getElementById('brand-select').value,
    model:  document.getElementById('model-select').value,
    size:   document.getElementById('size-select').value,
    dial:   document.getElementById('dial-select').value,
    strap:  document.getElementById('strap-select').value,
    dateRange: document.getElementById('date-select').value,
    sources: checkedSources,
  };
}

function applyFilters(deals, f) {
  return deals.filter((d) => {
    if (f.hotOnly && !d.is_hot) return false;
    if (f.priceMin !== null && (d.price == null || d.price < f.priceMin)) return false;
    if (f.priceMax !== null && (d.price == null || d.price > f.priceMax)) return false;
    if (f.brand && d.brand !== f.brand) return false;
    if (f.model && d.model !== f.model) return false;
    if (f.size  && String(d.size_mm) !== f.size)  return false;
    if (f.dial  && d.dial  !== f.dial)  return false;
    if (f.strap && d.strap !== f.strap) return false;
    if (!f.sources.includes(d.source)) return false;
    if (f.dateRange) {
      const cutoff = dateCutoff(f.dateRange);
      if (cutoff && (!d.date_seen || new Date(d.date_seen) < cutoff)) return false;
    }
    return true;
  });
}

/* Value a column sorts on (handles the cells that aren't plain fields). */
function sortValue(deal, column) {
  if (column === 'price')   return deal.price ?? null;            // numeric, null = unpriced
  if (column === 'ref')     return (deal.ref_matches && deal.ref_matches[0]) || '';
  if (column === 'dial')    return deal.dial || '';
  return deal[column] || '';                                      // title/brand/model/source/date_seen
}

function sortDeals(deals) {
  const { column, dir } = sortState;
  const mul = dir === 'asc' ? 1 : -1;
  const s = [...deals];
  s.sort((a, b) => {
    const av = sortValue(a, column);
    const bv = sortValue(b, column);
    // Empty/unknown values always sort last, regardless of direction.
    const aEmpty = av === null || av === '';
    const bEmpty = bv === null || bv === '';
    if (aEmpty && bEmpty) return 0;
    if (aEmpty) return 1;
    if (bEmpty) return -1;
    if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * mul;
    return String(av).localeCompare(String(bv)) * mul;
  });
  return s;
}

/* Clicking a header sorts by it (asc); clicking the active one flips direction. */
function setupSortHeaders() {
  document.querySelectorAll('th.sortable').forEach((th) => {
    th.addEventListener('click', () => {
      const col = th.dataset.sort;
      if (sortState.column === col) {
        sortState.dir = sortState.dir === 'asc' ? 'desc' : 'asc';
      } else {
        sortState = { column: col, dir: 'asc' };
      }
      updateSortIndicators();
      render();
    });
  });
  updateSortIndicators();
}

function updateSortIndicators() {
  document.querySelectorAll('th.sortable').forEach((th) => {
    const active = th.dataset.sort === sortState.column;
    th.classList.toggle('sorted', active);
    th.setAttribute('data-dir', active ? sortState.dir : '');
  });
}

function dateCutoff(range) {
  const now = Date.now();
  if (range === '24h') return new Date(now - 864e5);
  if (range === '7d')  return new Date(now - 6048e5);
  if (range === '30d') return new Date(now - 2592e6);
  return null;
}

/* ── Price history (derived from the deals already in memory) ── */
/* Group priced deals by watch model → a time-ordered series + summary stats. Deals with
   no usable price (null, or the -1 "gave up" sentinel) are dropped so a stuck listing
   can't skew a trend. Grouped by model (not ref) on purpose: refs are too sparse in this
   dataset to trend, per the price-history PRD. */
function priceHistory(deals) {
  const groups = {};
  for (const d of deals) {
    if (d.price == null || d.price <= 0) continue;   // drops null AND the -1 sentinel
    const key = modelKey(d);
    if (!key) continue;                              // no brand/model → can't group
    (groups[key] = groups[key] || []).push({ date: d.date_seen, price: d.price });
  }
  const out = {};
  for (const key of Object.keys(groups)) {
    const pts = groups[key].sort((a, b) => new Date(a.date) - new Date(b.date));
    const prices = pts.map((p) => p.price);
    out[key] = {
      series: pts,
      count: pts.length,
      median: median(prices),
      min: Math.min(...prices),
      max: Math.max(...prices),
      latest: prices[prices.length - 1],
    };
  }
  return out;
}

function modelKey(d) {
  const b = (d.brand || '').trim();
  const m = (d.model || '').trim();
  return (b || m) ? `${b} · ${m}` : '';
}

function median(nums) {
  const s = [...nums].sort((a, b) => a - b);
  const mid = Math.floor(s.length / 2);
  return s.length % 2 ? s[mid] : (s[mid - 1] + s[mid]) / 2;
}

/* Fewer than this many priced points isn't a trend — callers show a sparse state. */
const TREND_MIN_POINTS = 3;

/* Filter a time-ordered series to the last `months` (null = keep all). Used by the
   detail chart's range selector; a pure function so the self-check can cover it. */
function filterByMonths(series, months) {
  if (months == null) return series;
  const cutoff = new Date();
  cutoff.setMonth(cutoff.getMonth() - months);
  return series.filter((p) => new Date(p.date) >= cutoff);
}

/* Shared coordinate mapping for both the row sparkline and the detail chart: min–max
   normalized, x spread evenly across the width (a single point sits centered). */
function sparkCoords(series, w, h, pad) {
  const prices = series.map((p) => p.price);
  const lo = Math.min(...prices), hi = Math.max(...prices);
  const span = hi - lo || 1;
  const n = series.length;
  const xf = (i) => pad + (n === 1 ? (w - 2 * pad) / 2 : (i * (w - 2 * pad)) / (n - 1));
  const yf = (v) => h - pad - ((v - lo) / span) * (h - 2 * pad);
  return { prices, xf, yf, n };
}

/* Small static row sparkline: one gold polyline, `mark` highlights this row's price
   (green if under ceiling, else gold). No axes/labels — inside DESIGN.md's No-Display rule. */
function sparkline(series, opts = {}) {
  const w = opts.w || 60, h = opts.h || 18, pad = opts.pad || 2;
  const { prices, xf, yf } = sparkCoords(series, w, h, pad);
  const pts = series.map((p, i) => `${xf(i).toFixed(1)},${yf(p.price).toFixed(1)}`).join(' ');
  let dot = '';
  if (opts.mark != null) {
    const i = prices.lastIndexOf(opts.mark);
    if (i >= 0) {
      const col = opts.markHot ? '#5db85d' : '#c9a84c';
      dot = `<circle cx="${xf(i).toFixed(1)}" cy="${yf(opts.mark).toFixed(1)}" r="2" fill="${col}"/>`;
    }
  }
  return `<svg class="sparkline" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" `
    + `aria-hidden="true"><polyline points="${pts}" fill="none" stroke="#c9a84c" `
    + `stroke-width="1" opacity="0.85"/>${dot}</svg>`;
}

/* Larger interactive chart for the detail modal: area fill + dust median guide + gold
   line, plus hidden crosshair/hover-dot the hover handler drives. Returns the SVG markup
   and the per-point pixel coords so wireTrendHover can map the mouse to the nearest point. */
function buildTrendChart(series, opts) {
  const { w, h, pad } = opts;
  const { prices, xf, yf } = sparkCoords(series, w, h, pad);
  const points = series.map((p, i) => ({ x: xf(i), y: yf(p.price), price: p.price, date: p.date }));
  const line = points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
  const area = `<polygon points="${xf(0).toFixed(1)},${(h - pad).toFixed(1)} ${line} `
    + `${xf(series.length - 1).toFixed(1)},${(h - pad).toFixed(1)}" fill="#c9a84c" opacity="0.08"/>`;
  const medY = yf(opts.median).toFixed(1);
  const medLine = `<line x1="${pad}" y1="${medY}" x2="${w - pad}" y2="${medY}" stroke="#9a9282" `
    + `stroke-width="0.5" stroke-dasharray="2 2" opacity="0.5"/>`;
  let mark = '';
  if (opts.mark != null) {
    const i = prices.lastIndexOf(opts.mark);
    if (i >= 0) {
      const col = opts.markHot ? '#5db85d' : '#c9a84c';
      mark = `<circle cx="${points[i].x.toFixed(1)}" cy="${points[i].y.toFixed(1)}" r="2.5" fill="${col}"/>`;
    }
  }
  const svg = `<svg class="trend-svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" `
    + `preserveAspectRatio="xMidYMid meet">${area}${medLine}`
    + `<polyline points="${line}" fill="none" stroke="#c9a84c" stroke-width="1.5" opacity="0.85"/>`
    + `${mark}`
    + `<line class="trend-cross" x1="0" y1="${pad}" x2="0" y2="${h - pad}" stroke="#c9a84c" `
    + `stroke-width="0.5" opacity="0"/>`
    + `<circle class="trend-hoverdot" r="3" fill="#c9a84c" opacity="0"/></svg>`;
  return { svg, points, dims: { w, h } };
}

/* ── Render ── */
function render() {
  const f = getFilters();
  const filtered = applyFilters(allDeals, f);
  const sorted   = sortDeals(filtered);

  const tbody   = document.getElementById('deals-tbody');
  const empty   = document.getElementById('empty-state');
  const countEl = document.getElementById('result-count');

  const hotCount = sorted.filter((d) => d.is_hot).length;
  countEl.innerHTML =
    `<span>${sorted.length}</span> listing${sorted.length !== 1 ? 's' : ''}` +
    (hotCount ? ` · <span>${hotCount}</span> hot deal${hotCount !== 1 ? 's' : ''}` : '');

  if (!sorted.length) {
    tbody.innerHTML = '';
    empty.style.display = 'block';
    return;
  }
  empty.style.display = 'none';

  const hist = priceHistory(allDeals);

  tbody.innerHTML = sorted
    .map((d) => {
      const rowCls   = d.is_hot ? ' class="hot"' : '';
      const gaveUp   = d.price === -1;  // monitor flag: price never recovered after retries
      const price    = gaveUp ? '⚠ no price' : d.price != null ? `$${d.price.toLocaleString()}` : '—';
      const priceCls = gaveUp ? 'price-missing'
        : d.is_hot ? 'price-hot' : d.price != null ? 'price-ok' : 'price-none';
      const ref      = d.ref_matches && d.ref_matches.length ? d.ref_matches[0] : '—';
      const dialStr  = d.dial
        ? `${capitalize(d.dial)} · ${capitalize(d.strap || '')}`
        : '—';
      const safeTitle = escapeHtml(d.title || '');
      const safeId = escapeHtml(encodeURIComponent(d.id || ''));
      const h = hist[modelKey(d)];
      const trendCell = (h && h.count >= TREND_MIN_POINTS)
        ? sparkline(h.series, { mark: d.price > 0 ? d.price : null, markHot: d.is_hot })
        : '<span class="trend-sparse" title="Not enough history yet">–</span>';
      return `<tr${rowCls} data-deal-id="${safeId}">
        <td>${d.is_hot ? '<span class="hot-badge">🔥</span>' : ''}</td>
        <td class="price-cell ${priceCls} col-price">${price}</td>
        <td class="title-cell col-title" title="${safeTitle}">${escapeHtml(d.title || '—')}</td>
        <td class="brand-cell col-brand">${escapeHtml(d.brand || '—')}</td>
        <td class="model-cell col-model">${escapeHtml(d.model || '—')}</td>
        <td class="ref-cell col-ref">${escapeHtml(ref)}</td>
        <td class="dial-cell col-dial">${escapeHtml(dialStr)}</td>
        <td class="col-source">${sourceBadge(d.source)}</td>
        <td class="age-cell col-date_seen">${relativeTime(d.date_seen)}</td>
        <td class="trend-cell col-trend">${trendCell}</td>
        <td><button class="deal-del-btn" data-id="${safeId}" title="Delete deal">✕</button></td>
      </tr>`;
    })
    .join('');

  applyColVisibility();
}

/* ── Helpers ── */
function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function relativeTime(iso) {
  if (!iso) return '—';
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 60)  return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24)  return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function sourceBadge(source) {
  if (!source) return '—';
  const safe = escapeHtml(source);
  if (source === 'r/watchexchange') return `<span class="source-badge source-reddit">r/WEX</span>`;
  if (source === 'eBay')            return `<span class="source-badge source-ebay">eBay</span>`;
  if (source === 'Chrono24')        return `<span class="source-badge source-chrono">Chrono24</span>`;
  return `<span class="source-badge">${safe}</span>`;
}

function capitalize(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : '';
}

/* ── Deal detail modal ── */
/* Holds the open deal + its full (all-time) model series + the selected range, so the
   range buttons can re-filter and re-render without recomputing the grouping. */
let trendState = null;

function openDealDetail(id) {
  const d = allDeals.find((x) => String(x.id) === String(id));
  if (!d) return;
  const key = modelKey(d);
  const h = priceHistory(allDeals)[key];
  const fullSeries = h ? h.series : [];
  const gaveUp = d.price === -1;
  const priceStr = gaveUp ? '⚠ no price'
    : d.price != null ? `$${d.price.toLocaleString()}` : '—';
  const priceCls = gaveUp ? 'price-missing' : d.is_hot ? 'price-hot' : 'price-ok';
  const ref = d.ref_matches && d.ref_matches.length ? d.ref_matches[0] : '—';
  const dialStr = d.dial ? `${capitalize(d.dial)} · ${capitalize(d.strap || '')}` : '—';
  const rows = [
    ['Reference', ref],
    ['Dial / Strap', dialStr],
    ['Size', d.size_mm ? `${d.size_mm}mm` : '—'],
    ['Source', d.source || '—'],
    ['Seen', d.date_seen ? new Date(d.date_seen).toLocaleDateString() : '—'],
  ];

  // Range buttons come from the config; initial selection = the config default.
  const def = trendConfig.trend_ranges.find((r) => r.label === trendConfig.default_range)
    || trendConfig.trend_ranges[trendConfig.trend_ranges.length - 1];
  trendState = { deal: d, series: fullSeries, months: def ? def.months : null };
  const rangesHtml = trendConfig.trend_ranges.map((r) => {
    const m = r.months == null ? '' : r.months;
    const active = (r.months == null ? null : r.months) === trendState.months ? ' active' : '';
    return `<button class="trend-range-btn${active}" data-months="${m}">${escapeHtml(r.label)}</button>`;
  }).join('');

  document.getElementById('deal-detail-title').textContent =
    d.title || key || 'Listing';
  document.getElementById('deal-detail-body').innerHTML = `
    <div class="detail-price ${priceCls}">${priceStr}`
      + `${d.is_hot ? ' <span class="hot-badge">🔥</span>' : ''}</div>
    <div class="detail-model">${escapeHtml(key || '—')}</div>
    <dl class="detail-grid">
      ${rows.map(([k, v]) => `<dt>${k}</dt><dd>${escapeHtml(String(v))}</dd>`).join('')}
    </dl>
    <div class="detail-trend">
      <div class="label">Median asking over time</div>
      ${fullSeries.length ? `<div class="trend-ranges">${rangesHtml}</div>` : ''}
      <div class="trend-panel" id="trend-panel"></div>
    </div>
    ${d.url ? `<a class="detail-link" href="${escapeHtml(d.url)}" target="_blank" `
      + `rel="noopener">Open listing ↗</a>` : ''}`;

  document.querySelectorAll('#deal-detail-body .trend-range-btn').forEach((b) => {
    b.addEventListener('click', () => {
      trendState.months = b.dataset.months === '' ? null : Number(b.dataset.months);
      document.querySelectorAll('#deal-detail-body .trend-range-btn')
        .forEach((x) => x.classList.toggle('active', x === b));
      renderTrendPanel();
    });
  });

  renderTrendPanel();
  document.getElementById('deal-modal').style.display = 'flex';
}

/* Render the chart for the current trendState (deal + series + selected range). */
function renderTrendPanel() {
  const panel = document.getElementById('trend-panel');
  if (!panel || !trendState) return;
  const { deal, series, months } = trendState;
  const pts = filterByMonths(series, months);
  if (!pts.length) {
    panel.innerHTML = series.length
      ? '<div class="trend-sparse-msg">No listings in this range.</div>'
      : `<div class="trend-sparse-msg">No price history yet for this model.</div>`;
    return;
  }
  const prices = pts.map((p) => p.price);
  const med = median(prices), min = Math.min(...prices), max = Math.max(...prices);
  const chart = buildTrendChart(pts, { w: 320, h: 90, pad: 6, median: med,
    mark: deal.price > 0 ? deal.price : null, markHot: deal.is_hot });
  panel.innerHTML =
    `<div class="trend-chart-wrap">${chart.svg}<div class="trend-tooltip" style="display:none"></div></div>`
    + `<div class="trend-stats">${pts.length} listing${pts.length !== 1 ? 's' : ''} · `
    + `median $${Math.round(med).toLocaleString()} · $${min.toLocaleString()}–$${max.toLocaleString()}</div>`;
  wireTrendHover(panel, chart);
}

/* Snap a crosshair + dot + tooltip to the nearest point as the mouse moves over the chart. */
function wireTrendHover(panel, chart) {
  const svg = panel.querySelector('.trend-svg');
  const wrap = panel.querySelector('.trend-chart-wrap');
  const tip = panel.querySelector('.trend-tooltip');
  const cross = svg.querySelector('.trend-cross');
  const dot = svg.querySelector('.trend-hoverdot');
  const vbw = chart.dims.w;

  svg.addEventListener('mousemove', (e) => {
    const rect = svg.getBoundingClientRect();
    const scale = rect.width / vbw;               // CSS px per viewBox unit (uniform)
    const vbX = (e.clientX - rect.left) / scale;
    let best = chart.points[0];
    for (const p of chart.points) {
      if (Math.abs(p.x - vbX) < Math.abs(best.x - vbX)) best = p;
    }
    cross.setAttribute('x1', best.x); cross.setAttribute('x2', best.x);
    cross.setAttribute('opacity', '0.4');
    dot.setAttribute('cx', best.x); dot.setAttribute('cy', best.y);
    dot.setAttribute('opacity', '1');
    tip.innerHTML = `<span class="tt-price">$${best.price.toLocaleString()}</span>`
      + `<span class="tt-date">${new Date(best.date).toLocaleDateString()}</span>`;
    tip.style.display = 'block';
    tip.style.left = `${best.x * scale}px`;
    tip.style.top = `${best.y * scale}px`;
  });
  svg.addEventListener('mouseleave', () => {
    cross.setAttribute('opacity', '0');
    dot.setAttribute('opacity', '0');
    tip.style.display = 'none';
  });
}

function setupDealModal() {
  const modal = document.getElementById('deal-modal');
  const close = () => { modal.style.display = 'none'; };
  document.getElementById('deal-detail-close').addEventListener('click', close);
  modal.addEventListener('click', (e) => { if (e.target === modal) close(); });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && modal.style.display !== 'none') close();
  });
}

/* ── Event listeners ── */
function setupListeners() {
  const hotToggle = document.getElementById('hot-toggle');
  hotToggle.addEventListener('click', () => {
    const pressed = hotToggle.getAttribute('aria-pressed') === 'true';
    hotToggle.setAttribute('aria-pressed', String(!pressed));
    hotToggle.classList.toggle('active', !pressed);
    render();
  });

  ['price-min', 'price-max'].forEach((id) =>
    document.getElementById(id).addEventListener('input', render)
  );

  ['brand-select', 'model-select', 'size-select', 'dial-select',
   'strap-select', 'date-select'].forEach((id) => {
    document.getElementById(id).addEventListener('change', () => {
      if (id === 'brand-select') updateModelDropdown();
      render();
    });
  });

  document.getElementById('deals-tbody').addEventListener('click', (e) => {
    const delBtn = e.target.closest('.deal-del-btn');
    if (delBtn) { deleteDeal(delBtn.dataset.id); return; }
    const row = e.target.closest('tr[data-deal-id]');
    if (!row) return;
    openDealDetail(decodeURIComponent(row.dataset.dealId));
  });

  document.getElementById('clear-btn').addEventListener('click', () => {
    hotToggle.setAttribute('aria-pressed', 'false');
    hotToggle.classList.remove('active');
    document.getElementById('price-min').value = '';
    document.getElementById('price-max').value = '';
    ['brand-select', 'model-select', 'size-select', 'dial-select',
     'strap-select', 'date-select'].forEach((id) => {
      document.getElementById(id).value = '';
    });
    document.querySelectorAll('.source-checkbox').forEach((cb) => {
      cb.checked = true;
      cb.closest('.checkbox-row').querySelector('.checkbox-box').classList.add('checked');
    });
    sortState = { column: 'date_seen', dir: 'desc' };  // back to default (newest first)
    updateSortIndicators();
    document.body.classList.remove('filter-open');  // close the mobile drawer
    render();
  });
}

/* Sync the popover checkboxes to the current hiddenCols set. */
function syncColPopover() {
  document.querySelectorAll('#col-popover [data-col]').forEach((box) => {
    const key = box.dataset.col;
    const cb  = box.querySelector('input');
    const vis = !hiddenCols.has(key);
    cb.checked = vis;
    box.classList.toggle('checked', vis);
  });
}

/* ── Column toggle popover ── */
function setupColToggle() {
  const btn = document.getElementById('col-toggle-btn');
  const popover = document.getElementById('col-popover');

  syncColPopover();

  // Crossing the mobile breakpoint swaps which stored column prefs are live.
  mobileMQ.addEventListener('change', () => {
    hiddenCols = readHiddenCols();
    syncColPopover();
    applyColVisibility();
    document.body.classList.remove('filter-open');  // drawer is mobile-only
  });

  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    const open = popover.style.display !== 'none';
    popover.style.display = open ? 'none' : 'block';
    btn.setAttribute('aria-expanded', String(!open));
  });

  document.addEventListener('click', (e) => {
    if (!popover.contains(e.target) && e.target !== btn) {
      popover.style.display = 'none';
      btn.setAttribute('aria-expanded', 'false');
    }
  });

  popover.querySelectorAll('.checkbox-row').forEach((row) => {
    row.addEventListener('click', (e) => {
      if (e.target.tagName === 'INPUT') return;
      const cb = row.querySelector('input');
      cb.checked = !cb.checked;
      cb.dispatchEvent(new Event('change'));
    });
    row.querySelector('input').addEventListener('change', (e) => {
      const box = row.querySelector('[data-col]');
      const key = box.dataset.col;
      box.classList.toggle('checked', e.target.checked);
      if (e.target.checked) hiddenCols.delete(key);
      else hiddenCols.add(key);
      saveHiddenCols(hiddenCols);
      applyColVisibility();
    });
  });
}

/* ── Mobile filter drawer ── */
function setupFilterDrawer() {
  const shut = () => document.body.classList.remove('filter-open');
  document.getElementById('filter-toggle')
    .addEventListener('click', () => document.body.classList.add('filter-open'));
  document.getElementById('filter-close').addEventListener('click', shut);
  document.getElementById('filter-scrim').addEventListener('click', shut);
}

/* ── Boot ── */
document.addEventListener('DOMContentLoaded', () => {
  setupListeners();
  setupSortHeaders();
  setupColToggle();
  setupFilterDrawer();
  setupDealModal();
  setupWatchesListeners();
  fetchConfig();
  fetchData();
});

/* ── Watches view ── */
let allWatches = [];

async function fetchWatches() {
  try {
    const res = await fetch('/api/watches');
    allWatches = await res.json();
  } catch (e) {
    document.getElementById('watches-list').innerHTML =
      '<p class="subtitle">Failed to load watches.</p>';
    return;
  }
  renderWatches();
}

function renderWatches() {
  document.getElementById('watch-count').textContent = allWatches.length;
  document.getElementById('watches-list').innerHTML = allWatches.map((w) => `
    <div class="watch-row">
      <div class="watch-meta">
        <span class="watch-name">${escapeHtml(w.brand)} · ${escapeHtml(w.model)}</span>
        <span class="watch-sub">${w.size_mm ? escapeHtml(String(w.size_mm)) + 'mm' : '—'} ·
          ${(w.refs || []).length} ref(s) ·
          ${w.price_ceiling ? '$' + escapeHtml(String(w.price_ceiling)) : 'no ceiling'}</span>
      </div>
      <div class="watch-actions">
        <button data-edit="${escapeHtml(w.id)}">Edit</button>
        <button data-del="${escapeHtml(w.id)}">Delete</button>
      </div>
    </div>`).join('') || '<p class="subtitle">No watches yet.</p>';

  document.querySelectorAll('[data-edit]').forEach((b) =>
    b.addEventListener('click', () => openWatchForm(b.dataset.edit)));
  document.querySelectorAll('[data-del]').forEach((b) =>
    b.addEventListener('click', () => deleteWatch(b.dataset.del)));
}

function refRowHtml(ref = {}) {
  return `<div class="ref-row">
    <input class="ref-ref" placeholder="Ref" value="${escapeHtml(ref.ref || '')}">
    <input class="ref-dial" placeholder="Dial" value="${escapeHtml(ref.dial || '')}">
    <input class="ref-strap" placeholder="Strap" value="${escapeHtml(ref.strap || '')}">
  </div>`;
}

function openWatchForm(id) {
  const w = allWatches.find((x) => String(x.id) === id);
  document.getElementById('watch-modal-title').textContent = w ? 'Edit Watch' : 'Add Watch';
  document.getElementById('form-error').style.display = 'none';
  document.getElementById('f-id').value = w ? w.id : '';
  document.getElementById('f-brand').value = w ? w.brand : '';
  document.getElementById('f-model').value = w ? w.model : '';
  document.getElementById('f-size').value = w ? (w.size_mm || '') : '';
  document.getElementById('f-ceiling').value = w ? (w.price_ceiling || '') : '';
  document.getElementById('f-notes').value = w ? (w.notes || '') : '';
  document.getElementById('f-search-terms').value =
    w && w.search_terms ? w.search_terms.join('\n') : '';
  document.getElementById('f-relevance').value =
    w && w.relevance_required_all
      ? w.relevance_required_all.map((g) => g.join(', ')).join('\n') : '';
  const rows = (w && w.refs && w.refs.length) ? w.refs : [{}];
  document.getElementById('refs-rows').innerHTML = rows.map(refRowHtml).join('');
  document.getElementById('watch-modal').style.display = 'flex';
}

function collectForm() {
  const refs = [...document.querySelectorAll('.ref-row')].map((r) => ({
    ref: r.querySelector('.ref-ref').value.trim(),
    dial: r.querySelector('.ref-dial').value.trim(),
    strap: r.querySelector('.ref-strap').value.trim(),
  })).filter((r) => r.ref || r.dial || r.strap);
  const terms = document.getElementById('f-search-terms').value
    .split('\n').map((s) => s.trim()).filter(Boolean);
  const rel = document.getElementById('f-relevance').value
    .split('\n').map((line) => line.split(',').map((s) => s.trim().toLowerCase())
      .filter(Boolean)).filter((g) => g.length);
  const size = parseInt(document.getElementById('f-size').value, 10);
  const ceiling = parseInt(document.getElementById('f-ceiling').value, 10);
  return {
    brand: document.getElementById('f-brand').value.trim(),
    model: document.getElementById('f-model').value.trim(),
    size_mm: Number.isNaN(size) ? null : size,
    price_ceiling: Number.isNaN(ceiling) ? null : ceiling,
    notes: document.getElementById('f-notes').value.trim(),
    refs,
    search_terms: terms,
    relevance_required_all: rel,
  };
}

async function saveWatch() {
  const id = document.getElementById('f-id').value;
  const payload = collectForm();
  const res = await fetch(id ? `/api/watches/${id}` : '/api/watches', {
    method: id ? 'PUT' : 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json();
    const el = document.getElementById('form-error');
    el.textContent = err.error || 'Save failed';
    el.style.display = 'block';
    return;
  }
  document.getElementById('watch-modal').style.display = 'none';
  fetchWatches();
}

async function deleteWatch(id) {
  if (!confirm('Delete this watch?')) return;
  const res = await fetch(`/api/watches/${id}`, { method: 'DELETE' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    alert('Delete failed: ' + (err.error || res.status));
    return;
  }
  fetchWatches();
}

async function deleteDeal(encodedId) {
  if (!confirm('Delete this deal?')) return;
  const res = await fetch(`/api/deals/${encodedId}`, { method: 'DELETE' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    alert('Delete failed: ' + (err.error || res.status));
    return;
  }
  allDeals = allDeals.filter((d) => encodeURIComponent(d.id || '') !== encodedId);
  render();
}

function setupWatchesListeners() {
  document.querySelectorAll('.nav-btn').forEach((b) =>
    b.addEventListener('click', () => {
      document.querySelectorAll('.nav-btn').forEach((x) => x.classList.remove('active'));
      b.classList.add('active');
      document.getElementById('deals-view').style.display =
        b.dataset.view === 'deals-view' ? 'block' : 'none';
      document.getElementById('watches-view').style.display =
        b.dataset.view === 'watches-view' ? 'block' : 'none';
      if (b.dataset.view === 'watches-view') fetchWatches();
    }));
  document.getElementById('add-watch-btn').addEventListener('click', () => openWatchForm(null));
  document.getElementById('add-ref-btn').addEventListener('click', () => {
    document.getElementById('refs-rows').insertAdjacentHTML('beforeend', refRowHtml());
  });
  document.getElementById('watch-cancel').addEventListener('click', () => {
    document.getElementById('watch-modal').style.display = 'none';
  });
  document.getElementById('watch-save').addEventListener('click', saveWatch);
}
