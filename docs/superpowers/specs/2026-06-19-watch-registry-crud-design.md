# Watch Registry CRUD + Config-Driven Monitor — Design Spec

**Date:** 2026-06-19
**Status:** Approved

## Goal

Make the monitor fully config-driven and let the user manage *what is tracked*
through the local Flask web app instead of editing code. Each watch in
`data/watches.json` becomes self-contained — carrying its own search terms and
relevance rules — so the monitor can track any watch, not just the hardcoded
Longines. Preferred-match signals are reduced to sizes only (derived
automatically). The web app gains full CRUD over the registry, with an explicit
"push to activate" step that bridges the local edit to the GitHub Actions
monitor.

---

## Section 1 — Data Model & Monitor Refactor

### New `data/watches.json` schema (per entry, self-contained)

```json
{
  "id": "longines-master-chrono-moonphase",
  "brand": "Longines",
  "model": "Master Collection Chrono Moonphase",
  "size_mm": 40,
  "search_terms": [
    "longines master moonphase",
    "longines master chronograph moonphase"
  ],
  "relevance_required_all": [["longines", "master", "moon"]],
  "refs": [
    { "ref": "L2.673.4.78.6", "dial": "silver",     "strap": "bracelet" },
    { "ref": "L2.673.4.78.3", "dial": "silver",     "strap": "leather"  },
    { "ref": "L2.673.4.61.6", "dial": "anthracite", "strap": "bracelet" },
    { "ref": "L2.673.4.71.2", "dial": "ivory",      "strap": "leather"  },
    { "ref": "L2.673.4.92.0", "dial": "blue",       "strap": "bracelet" }
  ],
  "price_ceiling": 2000,
  "notes": "40mm only — 42mm is L2.773 family, not the target"
}
```

### Changes from today's schema

- **`id`** — new stable slug auto-generated from brand+model. CRUD edit/delete
  operations target a specific entry by this id.
- **`relevance_required_all`** — new per-entry field. Was a global constant
  (`RELEVANCE_REQUIRED_ALL`) in `watch_monitor.py`. A listing must contain ALL
  tokens of at least one group to count as relevant for that watch.
- **Preferred signals** — the `PREFERRED_SIGNALS` global constant is **removed
  entirely**. The monitor derives size signals automatically from `size_mm`
  (e.g. `40` → `["40mm", "40 mm"]`). This satisfies the "only sizes in preferred
  signals" requirement with no field to maintain.

### `watch_monitor.py` refactor

- Delete the global constants `SEARCH_TERMS`, `RELEVANCE_REQUIRED_ALL`,
  `PREFERRED_SIGNALS`, and `PRICE_ALERT_CEILING`.
- Load `data/watches.json` and **loop over every entry**. For each entry:
  - run *its* `search_terms` against each source,
  - filter results by *its* `relevance_required_all`,
  - derive preferred size signals from *its* `size_mm`,
  - use *its* `price_ceiling` for the 🔥 hot flag.
- A listing is tagged to the first registry entry whose relevance group matches.
  The existing tag logic (`tag_deal`) is now driven by per-entry rules instead of
  globals.
- `is_hot = price != null and price <= matched_entry.price_ceiling`.

### Backward compatibility

The existing single Longines entry is migrated in place to the new schema (add
`id`, add `relevance_required_all`). Post-migration tagging behavior is identical
to today's, verified by a migration test (Section 4).

---

## Section 2 — Flask CRUD API

Extend `webapp/flask/app.py` with write routes for the registry.

| Method   | Route                  | Purpose                                   |
|----------|------------------------|-------------------------------------------|
| `GET`    | `/api/watches`         | List all (exists today)                   |
| `POST`   | `/api/watches`         | Create — validate, generate `id`, append  |
| `PUT`    | `/api/watches/<id>`    | Update an entry by id                      |
| `DELETE` | `/api/watches/<id>`    | Remove an entry by id                      |
| `GET`    | `/api/status`          | Git sync state for the banner             |
| `POST`   | `/api/push`            | Commit + push `watches.json` to GitHub     |

### Write safety

- All writes go through one `save_watches(list)` helper that writes atomically
  (temp file + `os.replace`) so a crash cannot corrupt `watches.json`.
- **Validation** — each failure returns JSON `{ "error": "..." }` with a status:
  - `400` if `brand`, `model`, or `size_mm` is missing.
  - `400` if no `ref` with non-empty `dial` and `strap` is provided.
  - `409` if a create's generated `id` collides with an existing entry.
- `id` is generated server-side as a slug (e.g.
  `longines-master-chrono-moonphase`); clients never set it.
- `relevance_required_all` defaults server-side to one group of the lowercased
  brand + model words if the client omits it (auto-derive).

### Errors

JSON body `{ "error": "size_mm is required" }` with the appropriate HTTP status.
The frontend surfaces these inline on the form.

---

## Section 3 — Web UI

The Flask app gains a second view for managing watches, with a nav toggle
between **Deals** and **Watches**, keeping the existing single-page app and
dark-luxury aesthetic.

### Watches view

- **Header row:** "Tracked Watches (N)" + a **＋ Add Watch** button.
- **Push-to-activate banner:** hidden when in sync. When `watches.json` has
  uncommitted/unpushed changes, a gold banner appears:
  *"⚠ 3 unsaved changes — not yet monitoring. [Push to activate]"*. The button
  calls `POST /api/push`, which runs
  `git add data/watches.json && git commit && git push`, re-checks status, and
  clears the banner on success (git error shown inline on failure). Banner state
  comes from `GET /api/status` (working-tree dirty / ahead-count).
- **Watch list:** compact rows — brand · model · size, ref count, price ceiling
  — each with **Edit** and **Delete** (delete asks for confirmation).

### Add / Edit form (modal or inline panel)

- **Main fields:** Brand, Model, Size (mm), Price ceiling, Notes.
- **Refs section (required, ≥1 row):** each row = Ref / Dial / Strap, with
  **＋ Add ref** to add rows.
- **Advanced (collapsed):** Search terms (editable list, pre-filled from
  brand+model) and Relevance groups (editable, pre-filled with one group of the
  brand + model words).
- Save → `POST`/`PUT` → on success, refresh list and show the unsaved-changes
  banner. Validation errors render inline.

### Streamlit stack

Left read-only for now (it was always the "compare and maybe drop" candidate).
CRUD lands in Flask only.

---

## Section 4 — Testing

- **Monitor tests** (`tests/test_tagging.py`): multi-watch registry loads; each
  entry's `relevance_required_all` filters independently; size signals derive
  from `size_mm`; per-entry `price_ceiling` drives the hot flag; a non-matching
  listing is dropped.
- **Flask CRUD tests** (`webapp/flask/tests/test_app.py`): create valid → 201
  with generated id; create missing required field → 400; create with no refs →
  400; duplicate id → 409; update by id; delete by id; atomic write does not
  corrupt on bad input.
- **Status / push:** `GET /api/status` reports dirty vs clean; `POST /api/push`
  is mocked (no real network) — verify it shells the correct git commands and
  surfaces failures.
- **Migration check:** the existing Longines entry, run through the new loader,
  produces identical tagging to today.
