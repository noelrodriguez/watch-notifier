# Watch Deals Web App — Design Spec

**Date:** 2026-06-19
**Status:** Approved

## Goal

Build a local web app that displays the database of watch deals collected by the hourly GitHub Actions monitor. After pulling the latest code, a single script starts the app and opens it in the default browser. Filtering by price, brand, model, dial color, strap type, source, and date is required. Visual aesthetic: Dark Luxury Data Dense.

Two tech stacks are built in parallel (Flask + Streamlit) so the user can compare and permanently drop one later. Each stack is fully self-contained in its own folder.

---

## File Layout

```
watch-notifier/
├── data/
│   ├── watches.json          ← watch registry (manually curated)
│   ├── deals.json            ← auto-created by monitor; committed by GH Actions
│   └── monitor_state.json    ← existing dedup IDs (moved from repo root)
├── watch_monitor.py          ← modified: reads registry, writes deals.json
├── requirements.txt          ← updated: + flask, streamlit
├── .github/workflows/
│   └── monitor.yml           ← updated: commits data/deals.json alongside state
└── webapp/
    ├── start.sh              ← one-click launcher: both stacks + 2 browser tabs
    ├── flask/                ← DELETE to remove Flask stack entirely
    │   ├── app.py
    │   ├── templates/
    │   │   └── index.html
    │   └── static/
    │       ├── style.css
    │       └── app.js
    └── streamlit/            ← DELETE to remove Streamlit stack entirely
        └── app.py
```

Removing a stack is `rm -rf webapp/flask/` or `rm -rf webapp/streamlit/`. `requirements.txt` has comments marking which deps belong to which stack.

---

## Data Model

### `data/watches.json` — watch registry (manually curated)

One entry per watch being tracked. All filter metadata lives here.

```json
[
  {
    "brand": "Longines",
    "model": "Master Collection Chrono Moonphase",
    "size_mm": 40,
    "refs": [
      { "ref": "L2.673.4.78.6", "dial": "silver",     "strap": "bracelet" },
      { "ref": "L2.673.4.78.3", "dial": "silver",     "strap": "leather"  },
      { "ref": "L2.673.4.61.6", "dial": "anthracite", "strap": "bracelet" },
      { "ref": "L2.673.4.71.2", "dial": "ivory",      "strap": "leather"  },
      { "ref": "L2.673.4.92.0", "dial": "blue",       "strap": "bracelet" }
    ],
    "search_terms": [
      "longines master moonphase",
      "longines master chronograph moonphase"
    ],
    "price_ceiling": 2000,
    "notes": "40mm only — 42mm is L2.773 family, not the target"
  }
]
```

### `data/deals.json` — deal database (auto-managed by monitor)

Array of deal objects, one per unique listing ever seen. Appended on each monitor run; never overwritten.

```json
[
  {
    "id": "reddit:1abc23",
    "title": "Longines Master Moonphase 40mm L2.673.4.78.6, box & papers",
    "price": 1750,
    "url": "https://reddit.com/r/Watchexchange/...",
    "source": "r/watchexchange",
    "date_seen": "2026-06-20T14:32:00Z",
    "brand": "Longines",
    "model": "Master Collection Chrono Moonphase",
    "size_mm": 40,
    "ref_matches": ["L2.673.4.78.6"],
    "dial": "silver",
    "strap": "bracelet",
    "preferred_signals": ["40mm", "l2.673"],
    "is_hot": true
  }
]
```

**Tagging logic (at ingest):**
1. Match the listing's `title` against each registry entry's `search_terms` (substring match) to assign `brand`, `model`, `size_mm`. First registry entry whose search_terms match wins.
2. Search the listing title for every ref string in the matched watch's `refs` array. Collect all hits into `ref_matches`. Use the first hit to set `dial` and `strap`. If no ref found: `ref_matches = []`, `dial = null`, `strap = null`.
3. Set `is_hot = price != null and price <= price_ceiling`.

**First-run behavior:** `data/deals.json` is created empty on first run. The silent-baseline behavior (no notifications) is unchanged. The web app shows an empty state: "No deals yet — check back after the next monitor run."

**Backfill:** Deals that triggered notifications before this feature was deployed are not retroactively added. Only deals discovered after deployment appear in `deals.json`.

---

## Monitor Changes (`watch_monitor.py`)

- `STATE_FILE` path updated: `Path(__file__).parent / "data" / "monitor_state.json"`
- New `DEALS_FILE`: `Path(__file__).parent / "data" / "deals.json"`
- New `REGISTRY_FILE`: `Path(__file__).parent / "data" / "watches.json"`
- New `load_registry()` — reads `watches.json`; returns empty list if file missing (safe fallback).
- New `tag_deal(item, registry)` — returns the item dict enriched with `brand`, `model`, `size_mm`, `ref_matches`, `dial`, `strap`, `is_hot`, `date_seen`.
- New `save_deals(new_items)` — loads existing `deals.json` (or `[]`), appends new tagged items, writes back.
- `main()` calls `tag_deal` + `save_deals` for every newly-pushed item.

---

## GitHub Actions (`monitor.yml`)

The existing commit step is extended to include `data/deals.json`:

```yaml
git add data/monitor_state.json data/deals.json
git commit -m "chore: update monitor state [skip ci]"
git push
```

No other workflow changes.

---

## Web App — Flask Stack (`:5000`)

**Aesthetic:** Dark Luxury Data Dense — near-black background (`#07070d`), gold accents (`#c9a84c`), compact table rows, sidebar filters.

**Routes:**
- `GET /` — serves `index.html` shell
- `GET /api/deals` — returns `data/deals.json` as JSON
- `GET /api/watches` — returns `data/watches.json` as JSON (used to populate filter dropdowns)

Filtering is done client-side in JavaScript. The dataset is small (weeks of hourly runs = hundreds of entries at most), so no server-side query logic is needed.

**Table columns (left to right):**

| Column | Field | Notes |
|--------|-------|-------|
| (hot) | `is_hot` | 🔥 emoji, green left border on row |
| Price | `price` | Sortable; green if hot, muted if not; `—` if null |
| Title | `title` | Truncated, full title on hover; row click opens `url` |
| Brand | `brand` | Gold text |
| Model | `model` | Muted, truncated |
| Ref | `ref_matches[0]` | Monospace, `—` if empty |
| Dial / Strap | `dial` + `strap` | e.g. "Silver · Bracelet"; `—` if unknown |
| Source | `source` | Colored badge (purple=Reddit, blue=eBay, amber=Chrono24) |
| Seen | `date_seen` | Relative ("2h ago"); sortable; default sort |

**Sidebar filters:**

| Filter | UI | Field |
|--------|----|-------|
| Hot deals only | Toggle | `is_hot` |
| Price range | Min/max inputs | `price` |
| Brand | Dropdown | `brand` |
| Model | Dropdown (scoped to brand) | `model` |
| Size | Dropdown | `size_mm` |
| Dial color | Dropdown | `dial` |
| Strap | Dropdown | `strap` |
| Source | Checkboxes | `source` |
| Date seen | Dropdown (presets + all time) | `date_seen` |
| — | Clear filters button | resets all |

**Toolbar:** result count ("47 listings · 3 hot deals") + sort dropdown (newest first / price low-high / price high-low).

---

## Web App — Streamlit Stack (`:8501`)

- Reads `data/deals.json` directly (no server layer needed).
- Uses Streamlit's built-in dark theme.
- `st.sidebar` contains the same filter dimensions as Flask.
- `st.dataframe` renders the filtered result set with the same columns.
- Approximately 80 lines of Python; no custom CSS or JS.
- Aesthetic is Streamlit-default dark — less polished than Flask but zero frontend code.

---

## One-Click Launcher (`webapp/start.sh`)

```
1. pip install flask streamlit  (no-op if already installed)
2. Kill any existing process on :5000 or :8501
3. Start Flask in background   → logs to webapp/flask/flask.log
4. Start Streamlit in background → logs to webapp/streamlit/streamlit.log
5. Sleep 2s
6. open http://localhost:5000 && open http://localhost:8501
```

Usage after `git pull`:
```bash
bash webapp/start.sh
```

---

## Deletion Guide

To permanently drop a stack after choosing one:

**Drop Flask:**
```bash
rm -rf webapp/flask
# Remove flask from requirements.txt
```

**Drop Streamlit:**
```bash
rm -rf webapp/streamlit
# Remove streamlit from requirements.txt
```

Update `webapp/start.sh` to remove the dropped stack's start command and browser tab.
