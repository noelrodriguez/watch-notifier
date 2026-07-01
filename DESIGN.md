---
name: Watch Deals
description: A dark, gold-accented instrument panel for triaging secondary-market watch listings.
colors:
  void-black: "#07070d"
  panel-black: "#09090f"
  raised-black: "#0d0d16"
  field-black: "#111120"
  hairline: "#1e1e2e"
  hairline-soft: "#141420"
  border-strong: "#333333"
  warm-gold: "#c9a84c"
  warm-gold-bright: "#e0c060"
  signal-green: "#5db85d"
  signal-coral: "#d08770"
  danger-red: "#aa3333"
  danger-red-text: "#f1b0b0"
  ivory: "#e0d9cc"
  clay: "#c0b89a"
  dust: "#9a9282"
  fog: "#777777"
  graphite: "#444444"
  source-reddit: "#9c7fc0"
  source-ebay: "#7c9fc0"
  source-chrono: "#c09a50"
typography:
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.2
    letterSpacing: "4px"
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "9px"
    fontWeight: 500
    lineHeight: 1.2
    letterSpacing: "2px"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif"
    fontSize: "13px"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "normal"
  mono:
    fontFamily: "Menlo, 'Courier New', monospace"
    fontSize: "10px"
    fontWeight: 400
    lineHeight: 1.2
    letterSpacing: "normal"
rounded:
  sm: "4px"
  md: "6px"
  lg: "8px"
  pill: "10px"
spacing:
  xs: "6px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "20px"
  xxl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.warm-gold}"
    textColor: "{colors.void-black}"
    rounded: "{rounded.sm}"
    padding: "8px 16px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.fog}"
    rounded: "{rounded.sm}"
    padding: "6px 14px"
  button-ghost-hover:
    backgroundColor: "transparent"
    textColor: "{colors.warm-gold}"
  input-field:
    backgroundColor: "{colors.field-black}"
    textColor: "{colors.clay}"
    rounded: "{rounded.sm}"
    padding: "7px 10px"
  card-modal:
    backgroundColor: "{colors.raised-black}"
    textColor: "{colors.ivory}"
    rounded: "{rounded.lg}"
    padding: "22px"
---

# Design System: Watch Deals

## 1. Overview

**Creative North Star: "The Midnight Desk"**

A single desk lamp over a dark workspace, late at night, everything unnecessary switched
off. The surface is near-black, layered in three or four almost-identical dark tones so
structure reads from depth, not from borders. One warm gold accent — the lamplight — marks
the things that matter: brand identity, the active nav item, a call to action, the price
you should actually look at. A muted green stands in for "this is a genuinely good find,"
used sparingly enough that it still means something when it appears.

This is a solo-operator tool, not a showroom. It rejects literal watch-dealer catalog
styling — no faux leather, no filigree, no ornamental flourish borrowed from the product
category. The luxury reference is a tone carried by one color, not a costume worn by the
whole interface. Density is a feature: the table is the product, and everything else exists
to filter, sort, or annotate it.

**Key Characteristics:**
- Near-black, tonally-layered surfaces (no pure black, no gradients)
- One deliberate accent (warm gold) plus one signal color (green, for hot deals)
- Flat by default — depth comes from tone-shift, not shadow
- Small, tightly-tracked uppercase labels throughout (9–12px, 2–4px letter-spacing)
- Dense data table as the primary surface; everything else is filter chrome around it

## 2. Colors

Four near-black layers carry structure; one warm gold accent carries emphasis; a small
signal palette (green / coral / red) reports status.

### Primary
- **Warm Gold** (`#c9a84c`): the single brand accent. Used for the wordmark, section labels,
  active/hover states, primary buttons, and anything that means "look here." Its hover state,
  **Warm Gold Bright** (`#e0c060`), only appears on sortable-column hover — a lift, not a
  restyle.

### Secondary
- **Signal Green** (`#5db85d`): the "this is a genuinely good deal" color — the hot-price
  toggle, the hot-deal row border, and prices at or under the ceiling. Never decorative;
  it only appears when a listing has actually cleared the bar.

### Tertiary
- **Signal Coral** (`#d08770`): reserved for "missing/incomplete data" (a price that never
  recovered after retries) — a warm warning, distinct from true errors.
- **Danger Red** (`#aa3333` border / `#f1b0b0` text): form validation errors only.

### Neutral
- **Void Black** (`#07070d`): the base page background.
- **Panel Black** (`#09090f`): header, sidebar, and toolbar surfaces — one step up from void.
- **Raised Black** (`#0d0d16`): modal cards — the most "elevated" surface in the system.
- **Field Black** (`#111120`): input, select, and checkbox interiors — reads as recessed.
- **Hairline** (`#1e1e2e`) / **Hairline Soft** (`#141420`): 1px dividers between layered
  surfaces. Soft is used for lighter internal separators (table rows, toolbar edge).
- **Border Strong** (`#333333`): borders that need to read as a control, not a divider
  (buttons, modal card edge).
- **Ivory** (`#e0d9cc`): primary body text.
- **Clay** (`#c0b89a`): secondary text — input values, watch-row labels.
- **Dust** (`#9a9282`): tertiary text — model names, less-important cells.
- **Fog** (`#777777`): muted text — subtitles, secondary labels.
- **Graphite** (`#444444`): quiet text — counts, placeholders, empty-state copy.

### Categorical (source badges)
- **Source Reddit** (`#9c7fc0`), **Source eBay** (`#7c9fc0`), **Source Chrono24** (`#c09a50`):
  a small tagging palette used only inside `.source-badge` pills, each paired with its own
  low-opacity tint background and matching border. Not brand colors — purely categorical.

### Named Rules
**The One Lamp Rule.** Warm gold is the only warm, saturated color allowed outside status
signals. If a new element wants an accent color, it's gold, or it's not an accent.

## 3. Typography

**Body Font:** `-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif` (system stack —
no webfont currently loaded)
**Label/Mono Font:** `Menlo, 'Courier New', monospace` (reference numbers only)

**Character:** Small, quiet, and tightly tracked. There is no display or headline scale in
this system — the interface has no hero moment, only a wordmark-sized title and a lot of
12–13px working text. Emphasis comes from letter-spacing and uppercase treatment on labels,
not from size jumps.

### Hierarchy
- **Title** (400 weight, 12px, 4px letter-spacing, uppercase): the "Watch Deals" wordmark in
  the header only. One use, never repeated at body scale.
- **Label** (500 weight, 9px, 2px letter-spacing, uppercase): filter-section labels, table
  column headers. The workhorse of the system — most of the interface's "voice" lives here.
- **Body** (400 weight, 13px base / 12px in dense contexts like the table): everything else —
  values, watch names, modal copy.
- **Mono** (400 weight, 10px, monospace): reference numbers only (`.ref-cell`), so they stay
  visually distinct from prose and align in columns.

### Named Rules
**The No-Display Rule.** Nothing in this system exceeds 13px except the tracked-uppercase
title. If a redesign wants a bigger typographic moment, it needs a deliberate decision, not a
drift — this system is built to stay quiet.

## 4. Elevation

Flat by tonal layering, not shadow. Depth is conveyed almost entirely by stepping between
the four near-black surface tones (Void → Panel → Raised → Field) plus 1px hairline borders.
The system uses exactly one real shadow, reserved for a true floating element.

### Shadow Vocabulary
- **Floating popover** (`box-shadow: 0 4px 16px rgba(0,0,0,0.5)`): the only elevation shadow
  in the system, used solely on the column-visibility popover, which floats above the
  toolbar. Nothing else casts a shadow.
- **Modal backdrop** (`background: rgba(0,0,0,0.7)`): dims the page behind the watch-edit
  modal; not a card shadow, a scrim.

### Named Rules
**The Flat-By-Default Rule.** Surfaces are flat at rest; the only elevation is the one
floating popover and the modal scrim. Don't add card shadows to the table, sidebar, or
toolbar — tone-stepping already does that job.

## 5. Components

Quiet and restrained: components recede by default, and only price, status, and the gold
accent are allowed to pull the eye. Nothing in this system should compete with the table.

### Buttons
- **Shape:** 4px radius across every button variant — no exceptions.
- **Primary** (`#c9a84c` background, `#07070d` text, 600 weight): reserved for the single
  most important action per view — Add Watch, Save, Push to activate.
- **Ghost** (transparent background, `#555`/`#aaa` text, 1px `#252535`/`#333` border): the
  default for secondary actions (Clear filters, Cancel, nav tabs). Hover shifts text and
  border toward warm gold (`#c9a84c` / `#c9a84c44`) rather than filling the background.
- **Dashed ghost** (`+ Add ref`): a 1px dashed `#555` border signals "this adds a new row,"
  distinct from the solid-border ghost buttons used for navigation/dismissal.

### Chips / Badges
- **Source badges:** pill-shaped (10px radius), 10px text, low-opacity tinted background +
  matching-hue border, one per source (`#9c7fc0` Reddit, `#7c9fc0` eBay, `#c09a50` Chrono24).
- **Hot badge:** a bare emoji glyph, not a pill — deliberately the loudest, smallest element
  on the page, reserved for genuinely-hot rows.

### Cards / Containers
- **Corner Style:** 8px radius (modal card), 6px (popover) — the only two rounded containers
  in the system.
- **Background:** Raised Black (`#0d0d16`) for the modal, Panel Black (`#09090f`) for the
  floating popover.
- **Shadow Strategy:** see Elevation — popover gets the one real shadow; the modal relies on
  the backdrop scrim instead of its own shadow.
- **Border:** 1px `#222` (modal), 1px `#252535` (popover).
- **Internal Padding:** 22px (modal), 10–12px (popover).

### Inputs / Fields
- **Style:** Field Black (`#111120`) background, 1px `#252535` border, 4px radius, Clay
  (`#c0b89a`) text, Graphite-toned (`#333`) placeholder.
- **Focus:** border shifts to `#c9a84c44` (27% warm gold) — a glow, not a fill change.
- **Custom checkbox:** a 16px square, not a native checkbox; checked state fills
  `#c9a84c22` with a `#c9a84c88` border and a gold ✓ glyph.
- **Custom toggle:** a 34×20px pill; off is graphite (`#1a1a28`), on shifts to a dark green
  tint (`#1a2a1a`/`#2a4a2a`) with the dot turning Signal Green — the only place the toggle's
  own color communicates state rather than gold.

### Navigation
- **Style:** two ghost `.nav-btn` tabs (Deals / Watches) in the header, right-aligned. Active
  tab: gold text and gold bottom emphasis via border-color, not a filled background. Inactive:
  `#888` text, `#222` border. No hover elevation, no icons — text-only.

## 6. Do's and Don'ts

### Do:
- **Do** keep warm gold (`#c9a84c`) as the only saturated accent color used for identity,
  emphasis, and primary actions — per **The One Lamp Rule**.
- **Do** convey depth by stepping between the four near-black surface tones (Void → Panel →
  Raised → Field), not by adding shadows.
- **Do** use Signal Green only for a genuinely-cleared price/hot-deal condition — it's a
  status signal, not a decoration.
- **Do** keep labels small, uppercase, and letter-spaced (9–12px, 2–4px tracking) — that's
  where this system's personality lives.
- **Do** keep the table as the visual center of gravity; filter chrome (sidebar, toolbar)
  should stay quieter than the data it controls.

### Don't:
- **Don't** introduce a second saturated accent color competing with warm gold — if
  something needs to stand out, it's gold or a status color (green/coral/red), never a new
  hue.
- **Don't** add card shadows to the sidebar, toolbar, or table rows — per **The Flat-By-
  Default Rule**, the one shadow in this system belongs to the floating column popover only.
- **Don't** reach for literal watch-dealer/catalog styling (faux leather textures, filigree,
  ornamental serif display type, gold foil effects) — the luxury reference is one color, not
  a costume, per PRODUCT.md's anti-skeuomorphism principle.
- **Don't** push any text past 13px without a deliberate decision — this system has no
  display/headline scale, per **The No-Display Rule**.
- **Don't** use side-stripe borders as a general accent pattern — the one exception
  (`.hot` row's 2px left border) is a specific, load-bearing status signal, not a decorative
  device to reuse elsewhere.
