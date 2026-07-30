# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

# Project rules

## Branches & PRs (always)
- Never commit changes or features directly to `main`.
- Create a dedicated branch for every change, commit there, and push it.
- Open a pull request for review — do **not** merge it yourself.
- After the PR exists, open it in a browser window for the user to review
  (e.g. `open <pr-url>` on macOS). If `gh` is unavailable, open the GitHub
  compare/create-PR page instead so the PR can be published with one click.

## Deployment / orchestration

- Architecture & deployment (VM, systemd timer, retired git-as-database, Reddit
  OAuth requirement): see `README.md`. Two code-level gotchas worth carrying:
  from datacenter IPs (the VM) the `REDDIT_*` OAuth creds are **required**, not
  optional (anonymous paths are rate-limited / 403-blocked); and Reddit's token
  endpoint returns HTTP 200 even on a rejected grant (handled in `reddit_token`).
- Operational runbook + session handover: `HANDOVER.md` (local, gitignored).

### After-merge deploy (run when a PR merges)

The VM does **not** auto-pull. After a PR lands on `main`, update the box over
Tailscale SSH so the running services pick up the new code:

```bash
ssh noel_rodriguez_personal_gmail_co@watch \
  'sudo -u watch git -C /opt/watch-notifier pull --ff-only && \
   sudo systemctl restart watch-web.service'
```

- The **web app** (`webapp/flask/**`) needs the `watch-web.service` restart —
  gunicorn caches Jinja templates in memory, so a pull alone won't show template
  changes. Static `app.js`/`style.css` are read per-request (but restarting is
  harmless and keeps it simple — always restart).
- The **monitor** (`watch_monitor.py` etc.) needs no restart: the systemd timer
  launches a fresh process every 5 min, so the pull is enough.
- Verify: `curl -s -o /dev/null -w '%{http_code}' localhost:5000/` → `200`, and
  the dashboard is reachable from any Tailscale device at
  `https://watch.tailc4dd26.ts.net/`.

## Design Context

The `webapp/flask` dashboard has a documented design system — see `PRODUCT.md` (register:
product; solo internal tool) and `DESIGN.md` (current visual system: dark tonal layers, one
gold `#c9a84c` accent, "The Midnight Desk"). Target direction is a cleaner, more modern
dark-minimal feel (Linear/Vercel/Raycast neighborhood) while keeping the gold accent — the
current CSS hasn't fully closed that gap yet. Use `/impeccable polish` or `/impeccable live`
for UI work on this app rather than freehand restyling.
