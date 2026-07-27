/**
 * Self-check for the price-history derivation used by the deals trend view.
 * Run with: node webapp/flask/static/price-history.test.mjs
 * Exits non-zero on failure.
 *
 * Mirrors priceHistory() / modelKey() / median() in app.js. Kept in sync by copy,
 * same convention as columns.test.mjs — the app.js versions are browser globals, not
 * ES modules, so the pure logic is duplicated here for a dependency-free check.
 */

import assert from 'node:assert/strict';

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

function filterByMonths(series, months) {
  if (months == null) return series;
  const cutoff = new Date();
  cutoff.setMonth(cutoff.getMonth() - months);
  return series.filter((p) => new Date(p.date) >= cutoff);
}

function priceHistory(deals) {
  const groups = {};
  for (const d of deals) {
    if (d.price == null || d.price <= 0) continue;
    const key = modelKey(d);
    if (!key) continue;
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

// ── median ──
assert.equal(median([1]), 1);
assert.equal(median([3, 1, 2]), 2);            // odd → middle after sort
assert.equal(median([4, 1, 2, 3]), 2.5);       // even → mean of the two middle

// ── grouping by model ──
const deals = [
  { brand: 'Longines', model: 'Master', price: 2000, date_seen: '2026-01-03T00:00:00Z' },
  { brand: 'Longines', model: 'Master', price: 1500, date_seen: '2026-01-01T00:00:00Z' },
  { brand: 'Longines', model: 'Master', price: 1800, date_seen: '2026-01-02T00:00:00Z' },
  { brand: 'Omega',    model: 'Speedy', price: 4000, date_seen: '2026-01-01T00:00:00Z' },
];
const h = priceHistory(deals);
assert.deepEqual(Object.keys(h).sort(), ['Longines · Master', 'Omega · Speedy']);
const master = h['Longines · Master'];
assert.equal(master.count, 3);
assert.equal(master.median, 1800);
assert.equal(master.min, 1500);
assert.equal(master.max, 2000);

// ── series is sorted by date ascending (regardless of input order) ──
assert.deepEqual(master.series.map((p) => p.price), [1500, 1800, 2000]);
assert.equal(master.latest, 2000);             // latest = most recent by date

// ── excludes null and the -1 "gave up" sentinel ──
const withGaps = [
  { brand: 'A', model: 'X', price: 100, date_seen: '2026-01-01T00:00:00Z' },
  { brand: 'A', model: 'X', price: null, date_seen: '2026-01-02T00:00:00Z' },
  { brand: 'A', model: 'X', price: -1, date_seen: '2026-01-03T00:00:00Z' },
  { brand: 'A', model: 'X', price: 300, date_seen: '2026-01-04T00:00:00Z' },
];
const gx = priceHistory(withGaps)['A · X'];
assert.equal(gx.count, 2);                      // only the two real prices
assert.deepEqual(gx.series.map((p) => p.price), [100, 300]);

// ── deals with no brand/model are skipped (can't group) ──
const noKey = priceHistory([{ brand: '', model: '', price: 500, date_seen: '2026-01-01T00:00:00Z' }]);
assert.deepEqual(Object.keys(noKey), []);

// ── brand-only (empty model) still forms a key ──
const brandOnly = priceHistory([{ brand: 'Rolex', model: '', price: 9000, date_seen: '2026-01-01' }]);
assert.deepEqual(Object.keys(brandOnly), ['Rolex · ']);

// ── sparse group (below the 3-point trend floor) still returns its points ──
const sparse = priceHistory([
  { brand: 'B', model: 'Y', price: 100, date_seen: '2026-01-01T00:00:00Z' },
  { brand: 'B', model: 'Y', price: 200, date_seen: '2026-01-02T00:00:00Z' },
]);
assert.equal(sparse['B · Y'].count, 2);         // caller decides <3 → sparse state

// ── filterByMonths: windows the series by date, relative to now ──
const now = Date.now();
const daysAgo = (n) => new Date(now - n * 864e5).toISOString();
const windowed = [
  { date: daysAgo(3), price: 1 },     // within 1 month
  { date: daysAgo(50), price: 2 },    // within 3 months, not 1
  { date: daysAgo(200), price: 3 },   // only "all"
];
assert.equal(filterByMonths(windowed, null).length, 3);  // null → keep all
assert.equal(filterByMonths(windowed, 1).length, 1);      // only the 3-day-old point
assert.equal(filterByMonths(windowed, 3).length, 2);      // 3- and 50-day-old points
assert.deepEqual(filterByMonths(windowed, 1).map((p) => p.price), [1]);
assert.deepEqual(filterByMonths([], 3), []);              // empty in → empty out

console.log('price-history.test.mjs: all checks passed');
