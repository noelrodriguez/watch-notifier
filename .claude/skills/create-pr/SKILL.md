---
name: create-pr
description: Use whenever a code change is ready to be delivered for review and should go up as a pull request — e.g. the user says "open a PR", "put this up for review", "create a PR", "ship it for review", or you've just finished implementing something and the change should not land directly on main. Handles the full branch → commit → push → PR → open-in-browser flow and respects a repo's CLAUDE.md branch/PR rules. Do NOT use this to merge a PR.
---

# Create a pull request for review

Turn the current change into a clean, reviewable PR. The human reviews and
merges — never commit to main, and never merge the PR yourself.

## Steps

1. **Branch.** If on the default branch (`main`/`master`), create a descriptive
   branch first (`feat/...`, `fix/...`, `chore/...`). If already on a feature
   branch, use it. This is non-negotiable when the repo's `CLAUDE.md` forbids
   direct commits to main.
2. **Commit.** Stage only the files belonging to this change and commit with a
   message that says *what* changed and *why*. End with any trailer the repo
   expects (e.g. a `Co-Authored-By:` line). Don't sweep in unrelated files,
   build artifacts, or local config.
3. **Push.** `git push -u origin <branch>`.
4. **Open the PR.** Prefer `gh pr create` with a clear title and a body covering
   what changed, why, and how it was verified; follow the repo's PR template if
   one exists. If `gh` isn't installed/authenticated, push the branch and open
   the GitHub compare/create-PR page instead so it's one click to publish.
5. **Open in browser** for the user to review (`open <pr-url>` on macOS).
6. **Report** the PR URL back to the user.

## Notes

- A repo's `CLAUDE.md` branch/PR policy overrides this skill — follow it.
- If there are no committable changes (only state churn, generated files, or
  local config), say so and don't create an empty/noise PR.
- If a PR already exists for the branch, push new commits and report the existing
  URL instead of creating a duplicate.
- This pairs with the `pr-merged` skill, which syncs local main after merge.
