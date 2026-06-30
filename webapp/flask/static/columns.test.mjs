/**
 * Self-check for column visibility persistence logic.
 * Run with: node webapp/flask/static/columns.test.mjs
 * Exits non-zero on failure.
 */

import assert from 'node:assert/strict';

const COL_KEYS = ['price', 'title', 'brand', 'model', 'ref', 'dial', 'source', 'date_seen'];

function loadHiddenCols(raw) {
  try {
    if (!raw) return new Set();
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return new Set();
    return new Set(parsed.filter((k) => COL_KEYS.includes(k)));
  } catch { return new Set(); }
}

function saveHiddenCols(hidden) {
  return JSON.stringify([...hidden]);
}

// 1. Empty storage → all columns visible
assert.deepEqual(loadHiddenCols(null), new Set());
assert.deepEqual(loadHiddenCols(''), new Set());

// 2. Round-trip: save then load
const hidden = new Set(['price', 'dial']);
const serialized = saveHiddenCols(hidden);
assert.deepEqual(loadHiddenCols(serialized), hidden);

// 3. Unknown keys are filtered out
const withUnknown = JSON.stringify(['price', 'notacolumn']);
assert.deepEqual(loadHiddenCols(withUnknown), new Set(['price']));

// 4. Malformed JSON → empty set (no crash)
assert.deepEqual(loadHiddenCols('not-json'), new Set());

// 5. Non-array JSON → empty set
assert.deepEqual(loadHiddenCols('{"a":1}'), new Set());

// 6. All valid keys survive round-trip
const allHidden = new Set(COL_KEYS);
assert.deepEqual(loadHiddenCols(saveHiddenCols(allHidden)), allHidden);

console.log('columns.test.mjs: all checks passed');
