/**
 * Self-check for column visibility persistence logic.
 * Run with: node webapp/flask/static/columns.test.mjs
 * Exits non-zero on failure.
 */

import assert from 'node:assert/strict';

const COL_KEYS = ['price', 'title', 'brand', 'model', 'ref', 'dial', 'source', 'date_seen', 'trend'];
const LS_COL_KEY = 'deals-hidden-cols';
const LS_COL_KEY_MOBILE = 'deals-hidden-cols-mobile';
const MOBILE_DEFAULT_HIDDEN = ['title', 'ref', 'dial', 'source', 'date_seen', 'trend'];

/* Mirrors loadHiddenCols(raw, key) in app.js. raw == null means nothing stored:
   mobile seeds the essential-only default, desktop shows everything. */
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

function saveHiddenCols(hidden) {
  return JSON.stringify([...hidden]);
}

// 1. Nothing stored on desktop → all columns visible
assert.deepEqual(loadHiddenCols(null, LS_COL_KEY), new Set());
assert.deepEqual(loadHiddenCols('', LS_COL_KEY), new Set());

// 2. Round-trip: save then load
const hidden = new Set(['price', 'dial']);
const serialized = saveHiddenCols(hidden);
assert.deepEqual(loadHiddenCols(serialized, LS_COL_KEY), hidden);

// 3. Unknown keys are filtered out
const withUnknown = JSON.stringify(['price', 'notacolumn']);
assert.deepEqual(loadHiddenCols(withUnknown, LS_COL_KEY), new Set(['price']));

// 4. Malformed JSON → empty set (no crash)
assert.deepEqual(loadHiddenCols('not-json', LS_COL_KEY), new Set());

// 5. Non-array JSON → empty set
assert.deepEqual(loadHiddenCols('{"a":1}', LS_COL_KEY), new Set());

// 6. All valid keys survive round-trip
const allHidden = new Set(COL_KEYS);
assert.deepEqual(loadHiddenCols(saveHiddenCols(allHidden), LS_COL_KEY), allHidden);

// 7. Nothing stored on mobile → essential-only default (non-essentials hidden)
assert.deepEqual(loadHiddenCols(null, LS_COL_KEY_MOBILE), new Set(MOBILE_DEFAULT_HIDDEN));

// 8. Mobile default leaves the essential set visible, and hides source
//    (single-source: the badge is identical on every row)
const mobileHidden = loadHiddenCols(null, LS_COL_KEY_MOBILE);
['price', 'brand', 'model'].forEach((k) =>
  assert.ok(!mobileHidden.has(k), `${k} should be visible on mobile by default`));
assert.ok(mobileHidden.has('source'), 'source should be hidden on mobile by default');

// 9. Once mobile has a stored value, it wins over the default (even "hide nothing")
assert.deepEqual(loadHiddenCols('[]', LS_COL_KEY_MOBILE), new Set());
assert.deepEqual(loadHiddenCols(saveHiddenCols(new Set(['price'])), LS_COL_KEY_MOBILE),
  new Set(['price']));

console.log('columns.test.mjs: all checks passed');
