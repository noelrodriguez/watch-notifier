# Future option — mobile card / stacked layout for the Deals view

**Status:** Not implemented. Deliberately deferred in favour of *auto-hide columns*
(see the 2026-07-26 mobile spec). This doc captures the card-layout design so it can
be picked up later without re-deriving it.

**When to revisit:** if sideways-scanning a reduced table on the phone starts to feel
cramped, or if mobile becomes a primary surface (today it's desktop-first — one user
at a desk, per `PRODUCT.md`). Card layout is the more "native phone" answer; it costs a
second rendering path.

---

## The idea

On desktop each deal is one horizontal `<table>` row (hot · price · brand · model ·
ref · size · source · date · status across columns). On a ~402pt phone that row can't
fit, so each deal becomes a **self-contained card** and you scroll **down** through a
stack — never sideways.

```
┌──────────────────────────────┐
│ 🔥 $1,750           [reddit]  │  price (large) · hot glyph · source badge
│ Longines Master Collection   │  brand + model (primary text)
│ Chrono Moonphase             │
│ L2.673.4.78.6 · 40mm         │  ref (mono) + size — muted
│ Seen Jul 24 · New            │  date + status — muted
└──────────────────────────────┘
```

Tap a card → opens the deal (same action as clicking a row today).

### Card content hierarchy (maps to the design system)

- **Price** is the hero of each card — the one number you scan for. Gold if at/under
  the watch's ceiling (Signal Green per `DESIGN.md`), otherwise Ivory. Large by card
  standards but still bound by the No-Display Rule unless a deliberate exception is made.
- **Hot glyph (🔥)** stays a bare emoji, top-left or beside the price — loudest, smallest
  element, same as today.
- **Source badge** keeps its existing pill treatment (Reddit `#9c7fc0`, etc.), top-right.
- **Brand + model** = primary Ivory body text, the card's "title line".
- **Ref (mono) · size · date · status** = the muted supporting row(s) — Dust/Fog, small.
- A `.hot` card gets the 2px left gold/green border that the `.hot` row has today —
  the one sanctioned side-stripe.

## What it costs — the honest part

Card layout is **a second rendering path**, and that's the whole reason it was deferred:

1. **`renderDeals()` branches.** Today it builds `<tr>`s. It would need to build cards
   below the mobile breakpoint and rows above it — two DOM shapes from the same data.
   Cleanest is a shared `dealFields(deal)` helper both renderers call, so sort/filter
   logic stays single-source and only the final markup differs.
2. **Sorting loses its home.** "Click a column header to sort" has no columns on cards.
   Mobile needs a separate control — a small sort `<select>` (Price ↑/↓, Date ↑/↓,
   Brand A–Z) that writes the same sort state the header clicks write, so desktop is
   untouched.
3. **The Columns show/hide feature becomes meaningless** on cards — there are no columns
   to toggle. Hide that control below the breakpoint.
4. **Two layouts to keep in sync forever.** Every future column/field change touches both
   the row renderer and the card renderer.

Rough cost: ~2–3× the JS/CSS of the auto-hide-columns approach.

## Design-system tension

`DESIGN.md` and `PRODUCT.md` treat the **dense table as the product** ("Density is a
feature: the table is the product"). Cards trade density for legibility — a legitimate
mobile choice, but a real departure from the stated north star. If cards ship, note it
as a deliberate mobile-only exception, not a drift; desktop keeps the table.

## Implementation sketch (when picked up)

- **Breakpoint:** reuse whatever the mobile spec settles on (single source, e.g. a
  `--mobile` max-width around 640–768px).
- **Toggle mechanism:** CSS-first. Render *both* a `<table>` and a `.deal-cards`
  container from the same data; show one and hide the other by media query. Simpler to
  reason about than JS user-agent branching, at the cost of building both DOMs. If that's
  too heavy for the row count, switch to a JS branch on a `matchMedia` listener.
- **Shared data prep:** extract `dealFields(deal)` → `{priceHtml, isHot, sourceBadge,
  brand, model, ref, size, date, status}` and feed both renderers.
- **Sort control:** a `.mobile-sort` `<select>` in the toolbar, visible only on mobile,
  bound to the existing sort state so a change re-runs the same sort + re-render.
- **Tap target:** whole card is clickable (min 44pt height) → existing row-click handler.
- **Tests:** the existing `columns.test.mjs` covers column logic; add one that asserts
  `dealFields()` returns the right shape so both renderers stay in sync.

## Definition of done (future)

- Below the breakpoint: cards stack vertically, no horizontal scroll, price/hot/source
  scannable at a glance, whole card tappable.
- Above the breakpoint: the table renders exactly as it does today — zero regression.
- Sort works on both surfaces from one shared state.
- Columns menu hidden on mobile; visible on desktop.
