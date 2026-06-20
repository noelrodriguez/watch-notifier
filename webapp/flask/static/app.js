/* app.js — Watch Deals frontend */

let allDeals = [];

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
    sort: document.getElementById('sort-select').value,
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

function sortDeals(deals, sort) {
  const s = [...deals];
  if (sort === 'price-asc')  s.sort((a, b) => (a.price ?? Infinity)  - (b.price ?? Infinity));
  if (sort === 'price-desc') s.sort((a, b) => (b.price ?? -Infinity) - (a.price ?? -Infinity));
  if (sort === 'newest')     s.sort((a, b) => (b.date_seen || '').localeCompare(a.date_seen || ''));
  return s;
}

function dateCutoff(range) {
  const now = Date.now();
  if (range === '24h') return new Date(now - 864e5);
  if (range === '7d')  return new Date(now - 6048e5);
  if (range === '30d') return new Date(now - 2592e6);
  return null;
}

/* ── Render ── */
function render() {
  const f = getFilters();
  const filtered = applyFilters(allDeals, f);
  const sorted   = sortDeals(filtered, f.sort);

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

  tbody.innerHTML = sorted
    .map((d) => {
      const rowCls   = d.is_hot ? ' class="hot"' : '';
      const price    = d.price != null ? `$${d.price.toLocaleString()}` : '—';
      const priceCls = d.is_hot ? 'price-hot' : d.price != null ? 'price-ok' : 'price-none';
      const ref      = d.ref_matches && d.ref_matches.length ? d.ref_matches[0] : '—';
      const dialStr  = d.dial
        ? `${capitalize(d.dial)} · ${capitalize(d.strap || '')}`
        : '—';
      const safeUrl  = escapeHtml(d.url || '');
      const safeTitle = escapeHtml(d.title || '');
      return `<tr${rowCls} data-url="${safeUrl}">
        <td>${d.is_hot ? '<span class="hot-badge">🔥</span>' : ''}</td>
        <td class="price-cell ${priceCls}">${price}</td>
        <td class="title-cell" title="${safeTitle}">${escapeHtml(d.title || '—')}</td>
        <td class="brand-cell">${escapeHtml(d.brand || '—')}</td>
        <td class="model-cell">${escapeHtml(d.model || '—')}</td>
        <td class="ref-cell">${escapeHtml(ref)}</td>
        <td class="dial-cell">${escapeHtml(dialStr)}</td>
        <td>${sourceBadge(d.source)}</td>
        <td class="age-cell">${relativeTime(d.date_seen)}</td>
      </tr>`;
    })
    .join('');
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
   'strap-select', 'date-select', 'sort-select'].forEach((id) => {
    document.getElementById(id).addEventListener('change', () => {
      if (id === 'brand-select') updateModelDropdown();
      render();
    });
  });

  document.getElementById('deals-tbody').addEventListener('click', (e) => {
    const row = e.target.closest('tr[data-url]');
    if (!row) return;
    const url = row.dataset.url;
    if (url && /^https?:\/\//i.test(url)) window.open(url, '_blank');
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
    render();
  });
}

/* ── Boot ── */
document.addEventListener('DOMContentLoaded', () => {
  setupListeners();
  setupWatchesListeners();
  fetchData();
});

/* ── Watches view ── */
let allWatches = [];

async function fetchWatches() {
  const res = await fetch('/api/watches');
  allWatches = await res.json();
  renderWatches();
  refreshStatus();
}

function renderWatches() {
  document.getElementById('watch-count').textContent = allWatches.length;
  document.getElementById('watches-list').innerHTML = allWatches.map((w) => `
    <div class="watch-row">
      <div class="watch-meta">
        <span class="watch-name">${escapeHtml(w.brand)} · ${escapeHtml(w.model)}</span>
        <span class="watch-sub">${w.size_mm ? w.size_mm + 'mm' : '—'} ·
          ${(w.refs || []).length} ref(s) ·
          ${w.price_ceiling ? '$' + w.price_ceiling : 'no ceiling'}</span>
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
  const w = allWatches.find((x) => x.id === id);
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
  await fetch(`/api/watches/${id}`, { method: 'DELETE' });
  fetchWatches();
}

/* ── Push banner ── */
async function refreshStatus() {
  let s;
  try { s = await (await fetch('/api/status')).json(); } catch { return; }
  const banner = document.getElementById('push-banner');
  if (s.needs_push) {
    document.getElementById('push-banner-text').textContent =
      '⚠ Unsaved changes — not yet monitoring.';
    banner.style.display = 'flex';
  } else {
    banner.style.display = 'none';
  }
}

async function pushChanges() {
  const btn = document.getElementById('push-btn');
  btn.disabled = true;
  const res = await fetch('/api/push', { method: 'POST' });
  const body = await res.json();
  btn.disabled = false;
  if (body.ok) {
    refreshStatus();
  } else {
    document.getElementById('push-banner-text').textContent =
      'Push failed: ' + (body.error || 'unknown error');
  }
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
  document.getElementById('push-btn').addEventListener('click', pushChanges);
}
