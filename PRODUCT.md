# Product

## Register

product

## Users

Noel — the sole user, checking from a desk. He runs an hourly monitor for secondary-market
watch listings (r/watchexchange, eBay, Chrono24) and uses this dashboard to browse matched
deals and manage the watch registry (brand/model/size/price ceiling/reference numbers) that
drives what the monitor looks for. Desktop-first; mobile polish is not a priority.

## Product Purpose

A personal deal-triage tool. The backend monitor already does the scanning and hourly phone
push (via ntfy) for genuinely new listings; this web app is where Noel reviews everything
that's been found, filters/sorts by price, source, and status, and tunes the watch registry
that controls future matches. Success looks like: glance at the table, tell in seconds which
listings are worth a closer look, adjust watch criteria without friction.

## Brand Personality

Clean, modern, dark-minimal SaaS — the Linear / Vercel / Raycast neighborhood: charcoal
background, softly-bordered rounded cards, sparkline/micro-chart accents, one deliberate
accent color rather than a full palette. A gold/amber accent carries a quiet nod to the
watch/luxury subject matter without tipping into literal or ornate "watch dealer" styling.
Precise and calm, not loud — the UI should feel like a well-made instrument, not a showroom.

## Anti-references

None specified. Default guidance applies: avoid generic, cluttered dashboard tropes (identical
card grids, gradient text, side-stripe borders, glassmorphism as decoration).

## Design Principles

- **Data density with clarity** — the core view is a dense listings table; scannability beats
  decoration every time.
- **One accent, used deliberately** — gold/amber marks price and hot-deal status, not applied
  decoratively elsewhere.
- **Desktop-first** — a single user at a desk; don't over-invest in mobile-first patterns.
- **Quiet luxury, not literal skeuomorphism** — the watch subject matter is a tone, not a
  costume; no faux-leather, filigree, or literal dealer-catalog styling.
- **Fast triage over exploration** — every screen should get Noel from "what's new" to
  "is this worth it" in seconds.

## Accessibility & Inclusion

Personal, single-user tool — no formal WCAG target. Basic contrast and readability standards
still apply (this is dark UI; body text must stay clearly legible against the charcoal
background).
