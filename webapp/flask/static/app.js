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
      (s) => `
    <label class="checkbox-row">
      <span class="checkbox-box checked">
        <input type="checkbox" class="source-checkbox" value="${s}" checked>
      </span>
      <span class="checkbox-text">${s}</span>
    </label>`
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
    if (f.sources.length && !f.sources.includes(d.source)) return false;
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
      const safeUrl  = encodeURI(d.url || '#');
      const safeTitle = (d.title || '').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
      return `<tr${rowCls} onclick="window.open('${safeUrl}','_blank')">
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
  fetchData();
});
