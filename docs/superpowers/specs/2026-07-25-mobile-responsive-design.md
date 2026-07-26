# Spec — Mobile responsive pass (iPhone 17 Pro)

**Date:** 2026-07-25
**Scope:** Whole app (Deals view, Watches list, Add/Edit modal)
**Status:** Approved, ready for implementation plan.

## Goal

Make the Flask dashboard (`webapp/flask/`) usable on a portrait iPhone (iPhone 17
Pro, ~402pt CSS width). Today the app is fixed-desktop: a 220px flex sidebar + a dense
flex table, no media queries. The primary complaint: the left filter bar steals
horizontal room from the table on a phone.

Non-goal: changing anything about the desktop experience. Every rule in this spec lives
inside one mobile media query; desktop CSS is untouched.

## Decisions (locked)

- **Filter bar → slide-in drawer** on mobile (not a top panel, not removed).
- **Dense table → auto-hide columns** on mobile (not horizontal-scroll-only, not cards).
  Card/stacked layout was considered and deferred — see
  `docs/mobile-card-layout-future-option.md`.
- **Scope = whole app**, including the Watches list and the Add/Edit modal.
- **Delivery** via branch → PR (CLAUDE.md), using `/deliver-feature`.

## Breakpoint

One knob: `@media (max-width: 768px)` == "mobile treatment."

- Portrait iPhone 17 Pro (~402pt) → mobile.
- Landscape phone (~852pt) and desktop → current layout, unchanged.
- The `<meta name="viewport" content="width=device-width, initial-scale=1.0">` tag is
  already present in `templates/index.html` — no change needed for media queries to fire.

## Components

### 1. Header (`templates/index.html`, `static/style.css`)

- Add a **Filters** toggle button to the header, styled as a gold-ghost button
  consistent with the existing `.nav-btn` treatment. Visible only ≤768px (hidden on
  desktop via the media query).
- On mobile the header compresses: keep the "Watch Deals" title and the Deals/Watches
  nav; hide the "Last synced" `.app-meta` (reclaims width). Desktop keeps it.
- The Filters button only appears on the Deals view (there is no filter drawer on the
  Watches view). When the Watches tab is active, the button is hidden.

### 2. Sidebar → drawer (`static/style.css`, `static/app.js`, `templates/index.html`)

- ≤768px: `.sidebar` becomes a fixed-position overlay drawer, off-screen by default
  (`transform: translateX(-100%)`), sliding in from the left when open. A scrim (reuse
  the modal scrim `rgba(0,0,0,0.7)`) sits behind it over the table.
- A `.drawer-open` class (on `body` or `.layout`) drives the open state via CSS
  transform + scrim visibility. One small JS toggle wires it up.
- Opens: the header **Filters** button. Closes: tapping the scrim, a close (✕)
  affordance inside the drawer header, and after the existing "Clear filters" action.
- The 8 filter sections inside `.sidebar` are unchanged — no filter logic touched.
- Above 768px: `.sidebar` is the normal static 220px column; the drawer/scrim/toggle
  CSS does not apply. No desktop regression.
- Touch targets (Filters button, close ✕) ≥ 44pt.

### 3. Table → auto-hide columns (`static/app.js`, `static/style.css`)

- Reuse the existing column show/hide machinery (the Columns popover + persisted
  visibility). Do **not** overwrite the user's desktop column choices.
- Add a **separate mobile preference key** in `localStorage`, `hiddenColsMobile`,
  independent of the existing desktop key. `matchMedia('(max-width: 768px)')` decides
  which key is live for read/write.
- On first mobile load (no `hiddenColsMobile` yet), seed it with the essential visible
  set: **hot · price · brand/model**. All other columns start hidden on mobile but remain
  reachable via the existing Columns menu (toggles persist to the mobile key). Source is
  hidden by default too while r/watchexchange is the only source (the badge is identical
  on every row); revisit if a second source is added.
- `.table-wrap` keeps `overflow-x: auto` as a safety net if the essential set still runs
  slightly wide; reduce `.table-wrap` horizontal padding on mobile to give the table
  more room.
- The Columns popover itself must be usable on mobile (fits within viewport width; the
  floating popover's fixed/min width may need a mobile cap).

### 4. Watches view + modal (`static/style.css`)

- `.watches-header`: `＋ Add Watch` button stays reachable; allow the header to wrap if
  the title + button don't fit.
- `.watch-row` already flexes (name/sub left, edit/delete actions right); on mobile,
  let the actions wrap under the name/sub if space is tight so nothing is clipped.
- **Modal is the real fix.** `.modal-card` is a hard `width: 460px` today, which
  overflows a 402pt screen. On mobile: `width: 100%` minus small side margins (e.g.
  `calc(100vw - 24px)` with a `max-width`), keep the existing `max-height: 86vh;
  overflow-y: auto`. `.ref-row` inputs (`ref`/`dial`/`strap`) wrap instead of forcing a
  single overflowing row. `.modal-actions` stay reachable.

## Out of scope

- Card / stacked deal layout (deferred — see the future-option doc).
- Any change to desktop styling, sort behavior, or filter logic.
- New dependencies (this is CSS + a drawer toggle + one localStorage key).
- Real-device push/auto-refresh changes (unrelated).

## Testing / verification

- Existing `static/columns.test.mjs` must stay green. If the column-key logic changes
  (mobile pref key), extend it to cover mobile-key read/write/seed.
- Manual/browser verification at 402pt portrait, dark mode, via the preview browser:
  - Filters button opens/closes the drawer; scrim-tap and ✕ close it.
  - Table shows only the essential columns by default; Columns menu reveals more.
  - Modal fits the screen; refs wrap; save/cancel reachable.
  - Desktop (≥769px) renders exactly as before (no regression) — spot-check.
- Screenshot the portrait Deals view as delivery proof.

## Definition of done

- On ≤768px: filters live in a slide-in drawer, table shows the essential columns with
  no meaningful sideways scroll, Watches list and modal are fully usable.
- On ≥769px: pixel-identical to current `main`.
- Tests green; PR opened for review (not merged).
