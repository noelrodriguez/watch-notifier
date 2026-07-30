# Watch Tracker — Decision Log & Open Items

**Owner:** Noel — noel.rodriguez.shopping@gmail.com

This file is the *why* and the *what's-left*. It deliberately does **not** restate
things that live elsewhere:

- **Architecture, how-it-works, deployment, sources** → `README.md`
- **Watch targets & learned preferences** → `docs/requested_watches.md`
- **Ops runbook / VM access / remaining infra work** → `HANDOVER.md` (local, gitignored)
- **Per-PR change history** → git log (PRs #3–#51)

---

## Objective (original project brief)

Monitor secondary markets for buying watches and get phone alerts for good deals.
First feature: type a brand/model/reference, get current listings ranked by best
deal. Over time, track every watch Noel requests to learn his style and sizes and
refine searches. First target: the Longines Master Collection Chrono Moonphase, 40mm
(details in `docs/requested_watches.md`).

## Decisions (the *why*)

- **Notifications: ntfy.sh** — free, zero-account, and more reliable than the
  in-app Dispatch push path that failed early on (desktop fired; the iPhone push
  never arrived, root cause unconfirmed). A Telegram mirror is still supported via
  env vars if ever wanted.
- **Reddit OAuth uses a pre-existing script app's creds.** Self-serve app
  registration has been closed since Reddit's 2025 crackdown — you *cannot* create a
  new app. This only works because an old script app exists (Noel is a developer on
  it). **Password grant, not a refresh token** — script apps don't issue refresh
  tokens, and the auth-code flow needs an app type that can't be registered anymore.
- **Price recovery is two-layered:** a regex (`parse_price`) reads the common
  `$3,399` / `asking 1750` / `1750 shipped` formats; when it can't (markdown-wrapped
  `**2700**`, odd phrasing), an LLM fallback (`extract_price_llm`, shells `claude -p`
  on the Claude Code subscription) extracts it. After **5 failed attempts** a deal is
  flagged `price = -1` (permanent "gave up" sentinel); the dashboard renders that as
  **"⚠ no price"**.
- **The `claude -p` LLM fallback is NOT on the VM** — the CLI was never installed
  there, so regex + Reddit OAuth has carried 100% of price extraction all along.
  Dropping it removed the only memory spike (why zram was skipped on the VM).
- **Declined:** headless-browser (Playwright) Chrono24 scrape. Revisit only if
  coverage proves too spotty.

## Open items

- [ ] **Multi-watch price parsing.** `parse_price` picks the wrong price on posts
  selling several watches (e.g. post `1uod3c6` "Big Drop": stored $8500 vs actual
  $4175). Both price paths call `parse_price` on the OP comment; it needs to anchor
  on the matched watch's ref/model. (Logged as deferred — verify against current code.)
- [ ] **eBay rebuild** — replace the retired Akamai-blocked HTML scrape with eBay's
  official **Browse API** (free dev key), then re-enable `ENABLE_EBAY`.
- [ ] **`chrono24:test3`** is seeded test data in `data/deals.json` (fake URL, will
  never get a price) — delete it for a truly 0-missing dataset.
- [ ] **Watch-add form validation** — no type/range checks on `size_mm` /
  `price_ceiling` yet.
- [ ] **More watches** → sharpens the learned style/size profile (`data/watches.json`
  or the dashboard's Watches tab). Optionally widen beyond Longines.
- [ ] **SQLite + nightly backups** (VM step 6) — see `HANDOVER.md`.
