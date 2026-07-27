# Dashboard config — `data/dashboard_config.json`

Live runtime config for the Flask dashboard (`webapp/flask/`). It is served by
`GET /api/config` and **read fresh on every page load** — edit the file on the VM and
the change shows on the next reload, **no restart needed**. If the file is missing or
malformed, the app falls back to built-in defaults (in both `webapp/flask/app.py`'s
`_CONFIG_DEFAULTS` and the JS defaults in `static/app.js`), so a bad edit never takes the
dashboard down.

Editing on the box:

```bash
sudo -u watch nano /opt/watch-notifier/data/dashboard_config.json
# then just reload the page — no service restart
```

## Keys

| Key | Type | Default | What it does |
|---|---|---|---|
| `trend_ranges` | array of `{label, months}` | 1M/2M/3M/6M/All | The time-range buttons on the deal-detail price-history chart. `months: null` = all history. |
| `default_range` | string (a `label`) | `"3M"` | Which `trend_ranges` button is selected when the detail view opens. |
| `mobile_deals_layout` | `"cards"` \| `"table"` | `"cards"` | Which UI the **Deals view uses on a phone** (≤768px). See below. |

## `mobile_deals_layout` — phone Deals UI

Two mobile treatments for the deals list, swappable live:

- **`"cards"` (default)** — each deal is a self-contained tile you scroll *down*
  through (price hero + 🔥 + source on top, brand/model, then muted ref · dial/strap and
  date). Column-header sorting and the Columns menu don't apply, so a sort `<select>`
  (Newest, Oldest, Price ↑/↓, Brand A–Z) appears in the toolbar instead.
- **`"table"`** — the dense table with auto-hidden columns (the pre-cards mobile
  treatment): essential columns visible by default (hot · price · brand/model), the rest
  reachable via the Columns menu, `hiddenColsMobile` remembering your choices.

To switch: set the value, save, reload the phone.

```json
{ "mobile_deals_layout": "table" }
```

Notes:
- **Desktop (≥769px) is unaffected** — it always renders the table regardless of this
  value. Cards are a deliberate mobile-only exception to the "table is the product"
  north star in `PRODUCT.md` / `DESIGN.md`.
- Any unknown value falls back to `"cards"` (the JS treats only `"table"` as the opt-out).
- The card-layout design rationale and the tradeoffs vs. the table live in
  `docs/mobile-card-layout-future-option.md` (the original deferral doc).
