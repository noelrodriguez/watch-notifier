---
name: prime
description: Run this first at the start of a new session to get up to speed on the system. Reads the repo's root .md files and everything under /docs to load full context on what the project is, how it works, and where it stands. Use whenever the user opens a session and says "prime", "get up to speed", "orient yourself", "load context", "read the docs", or otherwise wants Claude grounded in the project before doing work. Supports arguments: "summary" for a written briefing, "scan" to also map the code structure — combinable (e.g. "prime summary scan").
---

# Prime

Your job: read the project's documentation so you understand the system before doing any real work. This is the first thing run in a session — the user wants you grounded, not guessing.

## Arguments

The skill's behavior is set by arguments, which combine freely. No argument = the default: read docs, stay quiet. Order doesn't matter.

- **`summary`** (aliases: `brief`, `full`, `verbose`) — output the written briefing instead of staying quiet.
- **`scan`** (aliases: `code`, `deep`, `map`) — also map the code structure, not just docs. Adds a "Codebase" pass and, in the briefing, a code map.

So `prime scan` maps the code but stays terse; `prime summary` briefs on docs only; `prime summary scan` does both — full briefing including the code map.

## What to read

Always read the docs. `scan` adds a codebase pass on top.

### Docs (always)

Read both of these in full. Documentation explains intent that code alone won't tell you.

1. **Root `.md` files** — every `.md` in the repo root (e.g. `README.md`, `CLAUDE.md`, `PRODUCT.md`, `DESIGN.md`). Discover them; don't assume the list.
2. **Everything under `/docs`** — recurse into subfolders. Handoff summaries, setup guides, and any `plans/` or `specs/` trees are high-signal for current state and recent decisions.

Read the actual files — don't skim filenames. Handoff/summary docs are the fastest path to "where things stand right now," so weight those.

Find them with:

```bash
ls -1 *.md 2>/dev/null; find docs -name '*.md' 2>/dev/null
```

Then read each one. If there's no `/docs` folder or no root `.md` files, just read what exists and say so — don't invent structure. Without `scan`, stop here — don't read source. Docs-only is what keeps the default fast enough to run every session.

### Codebase (only with `scan`)

Map the shape of the code so you know where things live — enough to navigate, not a line-by-line audit. Let the repo's layout and tooling guide you rather than assuming a stack:

- Top-level directories and what each holds.
- Entry points and the main modules/components, and how they connect.
- The stack and how it's run/tested (manifest files like `requirements.txt`, `package.json`, `Makefile`; test dir).

Favor structure-revealing tools (`git ls-files`, `find`, a directory listing) over reading every file. Read source selectively to confirm what a module does — you're building a map, not memorizing the territory.

## What to output

Output depends on whether `summary` was passed — `scan` changes what you read, not whether you stay quiet.

**No `summary`: stay quiet.** Internalize what you read and report readiness in one or two lines. The point is loaded context, not a wall of text the user scrolls past every session. Reflect whether you scanned:

> Read README, CLAUDE, PRODUCT, DESIGN + 6 docs (incl. the 2026-07-05 handoff). Grounded on the watch-notifier system. Ready.

> …+ mapped the code (webapp/, data/, tests/). Ready.

**With `summary`: give the full briefing.** Write a structured orientation:

```markdown
## What this is
[1–2 sentences: what the system does and who it's for.]

## How it works
[The shape of the system — main components, stack, key concepts — drawn from the docs.]

## Where it stands
[Current state, recent decisions, open threads. Lean on handoff/summary docs and any plans/specs.]

## Key docs
[Bulleted paths worth opening, each with a one-line "read this when…".]

## Worth flagging
[Only if you noticed it while reading: stale docs, contradictions, or gaps. Omit the section if nothing stands out — don't manufacture concerns.]
```

If `scan` was also passed, add a **Code map** section: top-level directories, entry points, and where the main pieces live — paths the user can jump to. Skip it when `scan` wasn't passed.

Keep the briefing tight. It orients; it isn't a rewrite of the docs or the code.
