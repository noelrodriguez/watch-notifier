---
name: deliver-feature
description: Use when the user hands over a development request — a feature, enhancement, or non-trivial bug fix — and wants it implemented end-to-end and delivered as a reviewable pull request, not just discussed. Triggers on phrasings like "implement X and open a PR", "build this out", "take this request and ship it", "deliver this", "handle this and let me review", or any change substantial enough to warrant a plan, implementation, tests, and a PR. Prefer this for work spanning multiple files or steps; for a true one-line tweak, just make the edit. Runs a senior-engineer delivery workflow: investigate → concise plan → dispatch implementation agent(s) → dedicated test-coverage agent → branch + PR for review.
---

# Deliver a feature (senior-engineer workflow)

Take a request and deliver it as a reviewable pull request, the way a senior
engineer would: understand the problem, plan tightly, implement, prove it with
tests, and hand over a clean PR. Scale the ceremony to the work — a small change
needs less than a large one — but every delivery ends in a PR the user reviews,
never a direct push to main.

## 1. Investigate before planning

Ground the plan in the actual codebase, not assumptions. Read the relevant code,
its tests, and the project's conventions (including any `CLAUDE.md` — its rules
override this skill). For a bug, reproduce it first; guessing at a fix without
understanding the root cause wastes the agents you're about to dispatch. The goal
of this phase is to know *what* needs to change and *why* before any code moves.

## 2. Write a concise plan

Break the work into the smallest set of well-scoped tasks. Note which are
independent (can run in parallel) and which depend on another's output (must be
sequenced). Keep each task to as few files as possible with a clear definition of
done.

Share the plan with the user and get a quick scope confirmation **before**
dispatching agents. Confirming a plan is cheap; redoing agent work is not. (Their
deep review still happens at the PR.)

## 3. Dispatch implementation agent(s)

Send each task to a separate senior-engineer implementation agent. Run them in
parallel when there's no shared state or ordering dependency (see the
`dispatching-parallel-agents` skill); sequence them otherwise. When agents would
touch overlapping code, give each its own git worktree so they don't collide.

Give every agent enough to act cold: the task, the files involved, the existing
patterns/conventions to match, the definition of done, and the constraint to
**not commit to main**. A good agent prompt stands on its own — it can't see this
conversation.

For small requests, this may be a single agent or even direct implementation;
don't spawn three agents to change one function. Match the process to the work.

## 4. Run a dedicated test-coverage agent

After implementation lands, dispatch **one** separate agent whose only job is
test coverage. It adds or extends tests for the new and changed behavior —
matching the project's existing test framework and conventions — then runs the
full suite and confirms it passes.

Scope: cover the new/changed code paths, including the edge cases that actually
matter (error handling, boundaries, the bug's original trigger). The point is
confidence the change works and won't silently regress — not a coverage
percentage for its own sake.

If tests fail, the change isn't done. Fix the root cause (or send it back to an
implementation agent) before moving on. Never report success on unverified work.

## 5. Open a PR for review

Use the `create-pr` skill to put the work on a branch and open a pull request.
Never commit to main; never merge it yourself — the user reviews and merges.

## 6. Report

Give the user the PR URL, a short summary of what changed, and how it was
verified (tests run, results). Be honest about anything skipped or still open.

## After merge

When the user signals the PR merged, the `pr-merged` skill syncs local main so
the next piece of work branches from merged code.
