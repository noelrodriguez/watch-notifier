/**
 * Self-check for the mobile deals-layout selection + mobile sort parsing.
 * Run with: node webapp/flask/static/layout.test.mjs
 * Exits non-zero on failure.
 */

import assert from 'node:assert/strict';

/* Mirrors pickLayout(isMobile, layout) in app.js. Cards only on a phone AND when
   configured for cards; desktop or any unknown value falls back to the table. */
function pickLayout(isMobile, layout) {
  return isMobile && layout === 'cards' ? 'cards' : 'table';
}

/* Mirrors parseMobileSort(v) in app.js. */
const MOBILE_SORT_COLS = ['price', 'date_seen', 'brand'];
function parseMobileSort(v) {
  const [column, dir] = String(v).split(':');
  if (MOBILE_SORT_COLS.includes(column) && (dir === 'asc' || dir === 'desc')) {
    return { column, dir };
  }
  return { column: 'date_seen', dir: 'desc' };
}

// 1. Cards only when on a phone AND configured for cards
assert.equal(pickLayout(true, 'cards'), 'cards');
assert.equal(pickLayout(true, 'table'), 'table');
// 2. Desktop always uses the table, whatever the config says
assert.equal(pickLayout(false, 'cards'), 'table');
assert.equal(pickLayout(false, 'table'), 'table');
// 3. Unknown/garbage config value falls back to the table (never a broken UI)
assert.equal(pickLayout(true, 'bogus'), 'table');
assert.equal(pickLayout(true, undefined), 'table');

// 4. Mobile sort round-trips the supported options
assert.deepEqual(parseMobileSort('price:asc'), { column: 'price', dir: 'asc' });
assert.deepEqual(parseMobileSort('date_seen:desc'), { column: 'date_seen', dir: 'desc' });
assert.deepEqual(parseMobileSort('brand:asc'), { column: 'brand', dir: 'asc' });
// 5. Unexpected values default to newest-first
assert.deepEqual(parseMobileSort('model:asc'), { column: 'date_seen', dir: 'desc' });
assert.deepEqual(parseMobileSort('price:sideways'), { column: 'date_seen', dir: 'desc' });
assert.deepEqual(parseMobileSort(''), { column: 'date_seen', dir: 'desc' });

console.log('layout.test.mjs: all assertions passed');
